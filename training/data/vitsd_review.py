"""Read-only ZIP audit and CAR35 review evidence. Never prepares a training split."""
from collections import Counter, defaultdict
import csv
import hashlib
from html import escape
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import zipfile

from PIL import Image, ImageDraw, ImageOps

from training.data.audit import DatasetReader, audit_dataset
from training.data.common import CAR35, digest_file, write_json


def _validate_zip(path):
    with zipfile.ZipFile(path) as archive:
        seen = set()
        for item in archive.infolist():
            name = PurePosixPath(item.filename)
            key = str(name).casefold()
            if (name.is_absolute() or '..' in name.parts or '\\' in item.filename
                    or ':' in item.filename or key in seen or item.flag_bits & 1
                    or (item.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError('Unsafe, encrypted or duplicate ZIP member: ' + item.filename)
            seen.add(key)


def copy_zip_to_local(source, target, *, progress=None):
    """Copy the mounted ZIP once, checking its receipt on reuse; no extraction."""
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target:
        raise ValueError('Local staging must differ from the mounted source')
    stat = source.stat()
    identity = dict(source=str(source), size=stat.st_size, mtime_ns=stat.st_mtime_ns)
    receipt = target.with_suffix(target.suffix + '.source.json')
    if target.exists():
        if not receipt.is_file():
            raise FileExistsError('Existing local ZIP has no receipt; choose a new target')
        saved = json.loads(receipt.read_text(encoding='utf-8'))
        if saved['source_identity'] != identity or digest_file(target) != saved['sha256']:
            raise ValueError('Source or local ZIP changed; choose a new staging path')
        _validate_zip(target)
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(target.parent).free < stat.st_size + 512 * 1024**2:
        raise OSError('Not enough local disk space for the ZIP and report; use another runtime/disk')
    _validate_zip(source)
    partial = target.with_suffix(target.suffix + '.part')
    if partial.exists():
        raise FileExistsError('An interrupted local copy exists; remove only its .part or choose a new target')
    digest, copied = hashlib.sha256(), 0
    try:
        with source.open('rb') as incoming, partial.open('xb') as outgoing:
            for block in iter(lambda: incoming.read(8 * 1024**2), b''):
                outgoing.write(block); digest.update(block); copied += len(block)
                if progress:
                    progress(copied)
        after = source.stat()
        if copied != stat.st_size or (after.st_size, after.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
            raise ValueError('Mounted source changed during copy')
        _validate_zip(partial)
        if target.exists():
            raise FileExistsError(target)
        partial.rename(target)
        write_json(receipt, dict(source_identity=identity, sha256=digest.hexdigest()))
    finally:
        if partial.exists():
            partial.unlink()  # This invocation created this staging file.
    return target


def audit_zip(source, *, annotation_format='yolo', image_limit=None, cache_dir=None, progress=None):
    """Fully decode/hash the selected scope. Cache identity includes source and code."""
    if annotation_format not in ('yolo', 'coco'):
        raise ValueError('Choose yolo or coco explicitly; formats are not merged')
    source = Path(source).resolve()
    _validate_zip(source)
    from training.data import audit as audit_module
    implementation = hashlib.sha256((Path(__file__).read_bytes() + Path(audit_module.__file__).read_bytes())).hexdigest()
    request = dict(source_path=str(source), source_sha256=digest_file(source), annotation_format=annotation_format,
                   image_limit=image_limit, verify_decode=True, hash_limit=None, implementation=implementation)
    cache = None
    if cache_dir is not None:
        directory = Path(cache_dir); directory.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        cache = directory / (key + '.json')
        checksum = cache.with_suffix('.json.sha256')
        if cache.is_file():
            if not checksum.is_file() or checksum.read_text().strip() != digest_file(cache):
                raise ValueError('Audit cache changed; choose a fresh cache directory')
            saved = json.loads(cache.read_text(encoding='utf-8'))
            if saved['request'] != request:
                raise ValueError('Audit cache request changed')
            return saved['report']
    with DatasetReader(source) as reader:
        if reader.warnings:
            raise ValueError('Unsupported archive contents: ' + str(reader.warnings[:3]))
        report = audit_dataset(reader, 'vitsd', annotation_format=annotation_format,
                               image_limit=image_limit, hash_limit=None, verify_decode=True, progress=progress)
    report['summary']['source_sha256'] = request['source_sha256']
    report['summary']['audit_implementation_sha256'] = implementation
    # JSON object keys (class IDs) must have the same representation before and
    # after cache restore, not int on the first run and str on the second.
    report = json.loads(json.dumps(report, ensure_ascii=False, allow_nan=False))
    if cache is not None:
        with cache.open('x', encoding='utf-8') as stream:
            json.dump(dict(request=request, report=report), stream, ensure_ascii=False, allow_nan=False)
        checksum.write_text(digest_file(cache), encoding='utf-8')
    return report


def load_reference(path):
    """Read only CAR35 manifest metadata, from JSON or a ZIP containing one manifest."""
    if not path:
        return None
    path = Path(path)
    if path.suffix.lower() == '.zip':
        _validate_zip(path)
        with zipfile.ZipFile(path) as archive:
            matches = [n for n in archive.namelist() if PurePosixPath(n).name == 'manifest.json']
            if len(matches) != 1:
                raise ValueError('Reference ZIP must contain exactly one manifest.json')
            if archive.getinfo(matches[0]).file_size > 128 * 1024**2:
                raise ValueError('Reference manifest exceeds read limit')
            manifest = json.loads(archive.read(matches[0]).decode('utf-8-sig'))
    else:
        if path.stat().st_size > 128 * 1024**2:
            raise ValueError('Reference manifest exceeds read limit')
        manifest = json.loads(path.read_text(encoding='utf-8-sig'))
    rows = manifest.get('images')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Reference manifest must contain image hashes and splits')
    hashes = defaultdict(set)
    for row in rows:
        digest, split = row.get('sha256', ''), row.get('split')
        if not re.fullmatch('[a-f0-9]{64}', digest) or split not in ('train', 'val', 'test'):
            raise ValueError('Invalid reference SHA-256 or split')
        hashes[digest].add(split)
    return {key: sorted(values) for key, values in hashes.items()}


def build_review(report, *, reference=None):
    by_image, hashes = defaultdict(list), defaultdict(list)
    for box in report['boxes']:
        by_image[box['path']].append(box)
    for row in report['images']:
        if row['sha256']:
            hashes[row['sha256']].append(row)
    duplicates, conflicting = [], set()
    for digest, rows in sorted(hashes.items()):
        if len(rows) < 2:
            continue
        signatures = set()
        for row in rows:
            signature = tuple(sorted((b['class_name'], b['class_mapped'], b['iscrowd'],
                                      *(round(b[k], 8) for k in ('x_norm', 'y_norm', 'width_norm', 'height_norm')))
                                     for b in by_image[row['path']]))
            signatures.add((row['annotation_status'], signature))
        conflict = len(signatures) > 1
        if conflict:
            conflicting.add(digest)
        duplicates.append(dict(sha256=digest, copies=len(rows), label_conflict=conflict,
                               cross_split=len({r['split'] for r in rows} - {'unknown'}) > 1,
                               paths=[r['path'] for r in rows]))
    catalog = {}
    for entry in report['summary']['class_maps']:
        for key, name in entry['names'].items():
            catalog[entry['path'], str(key)] = name
    for b in report['boxes']:
        catalog[b['label_namespace'], str(b['class_id'])] = b['class_name']
    mapping = [dict(namespace=namespace, source_id=key, source_name=name,
                    candidate_target_id=CAR35.index(name) if name in CAR35 else '',
                    candidate_target_name=name if name in CAR35 else '', approved=False,
                    action='review_exact_name' if name in CAR35 else 'review_exclude_or_map')
               for (namespace, key), name in sorted(catalog.items())]
    decisions, overlap = [], []
    for row in report['images']:
        boxes = by_image[row['path']]
        reasons = []
        if row['annotation_status'] not in ('annotated', 'empty_annotation'):
            reasons.append(row['annotation_status'])
        if any(not b['class_mapped'] or b['iscrowd'] for b in boxes):
            reasons.append('unmapped_or_crowd_annotation')
        if row['sha256'] in conflicting:
            reasons.append('conflicting_duplicate_annotations')
        selected = [b for b in boxes if b['class_mapped'] and b['class_name'] in CAR35]
        decision = 'quarantine' if reasons else 'review_car35' if selected else 'review_background'
        decisions.append(dict(path=row['path'], split=row['split'], sha256=row['sha256'],
                              annotation_status=row['annotation_status'], decision=decision,
                              reason=';'.join(reasons), car35_boxes=len(selected)))
        if reference is not None and row['sha256'] in reference:
            overlap.append(dict(path=row['path'], split=row['split'], sha256=row['sha256'],
                                reference_splits=';'.join(reference[row['sha256']])))
    summary = dict(source=report['summary'], training_ready=False, mapping_approved=False,
                   independent_field_test=False, unique_hashed_images=len(hashes),
                   duplicate_groups=len(duplicates), conflicting_duplicate_groups=len(conflicting),
                   decisions=dict(Counter(r['decision'] for r in decisions)),
                   reference_exact_check='not_supplied' if reference is None else 'checked',
                   reference_images=None if reference is None else len(reference),
                   reference_inventory_sha256=None if reference is None else hashlib.sha256(
                       json.dumps(reference, sort_keys=True).encode()).hexdigest(),
                   reference_overlap_images=len(overlap) if reference is not None else None,
                   reference_near_check='not_checked',
                   limitations='Review candidates only. No images, labels or splits changed. '
                               'Exact-name mapping is unapproved. dHash is a heuristic, not capture metadata. '
                               'A hash manifest cannot establish cross-source scene independence.')
    return dict(summary=summary, mapping=mapping, decisions=decisions, duplicates=duplicates,
                reference_overlap=overlap)


def _csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def _near_edges(reader, rows, threshold, progress):
    """BK-tree spanning forest: bounded by images, never an all-pairs matrix."""
    parent = list(range(len(rows)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    tree, edges = None, []
    values = progress(list(enumerate(rows)), desc='Visual hashes / candidate groups', unit='image') if progress else enumerate(rows)
    for i, row in values:
        if row['annotation_status'] == 'unreadable_image':
            continue
        with reader.open(row['path']) as stream, Image.open(stream) as image:
            pixels = list(image.convert('L').resize((9, 8), Image.Resampling.LANCZOS).tobytes())
        value = 0
        for y in range(8):
            for x in range(8):
                value = (value << 1) | (pixels[y*9+x] > pixels[y*9+x+1])
        if tree is None:
            tree = (value, i, {}); continue
        pending = [tree]
        while pending:
            other, j, children = pending.pop()
            distance = (value ^ other).bit_count()
            a, b = find(i), find(j)
            if distance <= threshold and a != b:
                parent[max(a, b)] = min(a, b)
                edges.append(dict(left=row['path'], right=rows[j]['path'], distance=distance,
                                  same_sha256=row['sha256'] == rows[j]['sha256'],
                                  cross_split=row['split'] != rows[j]['split']))
            pending.extend(child for edge, child in children.items()
                           if distance-threshold <= edge <= distance+threshold)
        node = tree
        while True:
            distance = (value ^ node[0]).bit_count()
            if distance == 0:
                break
            if distance not in node[2]:
                node[2][distance] = (value, i, {}); break
            node = node[2][distance]
    sizes = Counter(find(i) for i in range(len(rows)) if rows[i]['sha256'])
    return edges, dict(candidate_groups=len(sizes), largest_candidate_group=max(sizes.values(), default=0),
                       joining_edges=len(edges), cross_split_edges=sum(e['cross_split'] for e in edges),
                       threshold=threshold, all_pairs=False, split_changed=False)


def _sheet(reader, rows, boxes, target, title):
    width, height, columns = 360, 240, 3
    sheet = Image.new('RGB', (width*columns, height*((len(rows)+columns-1)//columns)), '#18212b')
    canvas = ImageDraw.Draw(sheet)
    for i, row in enumerate(rows):
        x, y = (i % columns)*width, (i // columns)*height
        with reader.open(row['path']) as stream, Image.open(stream) as source:
            image = source.convert('RGB')
        draw = ImageDraw.Draw(image)
        for b in boxes[row['path']]:
            left, top = b['x_norm']*image.width, b['y_norm']*image.height
            draw.rectangle((left, top, left+b['width_norm']*image.width, top+b['height_norm']*image.height),
                           outline='yellow', width=2)
            draw.text((max(0, left), max(0, top-12)), b['class_name'].encode('ascii', 'replace').decode(), fill='yellow')
        image = ImageOps.contain(image, (width-8, height-48))
        sheet.paste(image, (x+(width-image.width)//2, y+4))
        caption = f"{row['split']} | {PurePosixPath(row['path']).name}"
        canvas.text((x+4, y+height-40), title[:50], fill='white')
        canvas.text((x+4, y+height-24), caption[:52], fill='white')
    sheet.save(target, quality=85)


def write_review(source, report, review, output, *, near_threshold=4, progress=None):
    """Publish a new, portable report with bounded previews; no training output."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    if near_threshold is not None and (type(near_threshold) is not int or not 0 <= near_threshold <= 8):
        raise ValueError('near_threshold must be None or an integer from 0 to 8')
    if digest_file(source) != report['summary']['source_sha256']:
        raise ValueError('Source ZIP changed after audit')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.vitsd-review-', dir=output.parent) as temporary, DatasetReader(source) as reader:
        stage = Path(temporary)/'report'; stage.mkdir(); (stage/'previews').mkdir()
        summary = dict(review['summary'])
        write_json(stage/'source_summary.json', report['summary'])
        write_json(stage/'exact_duplicates.json', review['duplicates'])
        for name, rows, fields in [
            ('images', report['images'], list(report['images'][0]) if report['images'] else ['path']),
            ('boxes', report['boxes'], list(report['boxes'][0]) if report['boxes'] else ['path', 'class_name']),
            ('issues', report['issues'], ['dataset', 'path', 'message']),
            ('mapping_candidates', review['mapping'], ['namespace', 'source_id', 'source_name', 'candidate_target_id', 'candidate_target_name', 'approved', 'action']),
            ('decisions', review['decisions'], ['path', 'split', 'sha256', 'annotation_status', 'decision', 'reason', 'car35_boxes']),
            ('reference_overlap', review['reference_overlap'], ['path', 'split', 'sha256', 'reference_splits']),
        ]:
            _csv(stage/(name+'.csv'), rows, fields)
        _csv(stage/'quarantine.csv', [r for r in review['decisions'] if r['decision']=='quarantine'],
             ['path', 'split', 'sha256', 'annotation_status', 'decision', 'reason', 'car35_boxes'])
        boxes, image_map = defaultdict(list), {r['path']: r for r in report['images']}
        for b in report['boxes']:
            boxes[b['path']].append(b)
        counts = Counter((b['class_name'], b['split']) for b in report['boxes'])
        class_rows = [dict(name=name, **{s: counts[name, s] for s in ('train', 'val', 'test', 'unknown')})
                      for name in sorted({b['class_name'] for b in report['boxes']})]
        _csv(stage/'class_counts.csv', class_rows, ['name', 'train', 'val', 'test', 'unknown'])
        summary['class_counts_basis'] = 'Geometrically valid source boxes, including valid boxes in images with other annotation errors; not cleaned training counts.'
        summary['near_duplicates'] = dict(status='disabled')
        edges = []
        if near_threshold is not None:
            edges, info = _near_edges(reader, report['images'], near_threshold, progress)
            summary['near_duplicates'] = dict(status='review_candidates', **info)
        _csv(stage/'near_duplicate_edges.csv', edges, ['left', 'right', 'distance', 'same_sha256', 'cross_split'])
        previews = []
        for cls, name in enumerate(CAR35):
            paths = sorted({b['path'] for b in report['boxes'] if b['class_mapped'] and b['class_name'] == name})[:6]
            if paths:
                filename = f'previews/car35_{cls:02d}.jpg'
                _sheet(reader, [image_map[p] for p in paths], boxes, stage/filename, name)
                previews.append((name, filename))
        samples = [image_map[r['path']] for r in review['decisions']
                   if r['decision']=='quarantine' and image_map[r['path']]['annotation_status']!='unreadable_image'][:6]
        if samples:
            _sheet(reader, samples, boxes, stage/'previews/quarantine.jpg', 'QUARANTINE - inspect source labels')
            previews.append(('Quarantine examples', 'previews/quarantine.jpg'))
        if edges:
            # Diverse distances; at most six pairs, one bounded sheet.
            chosen, seen_distances = [], set()
            for edge in edges:
                if edge['distance'] not in seen_distances:
                    chosen.append(edge); seen_distances.add(edge['distance'])
                if len(chosen) == 6:
                    break
            _sheet(reader, [image_map[e[k]] for e in chosen for k in ('left', 'right')], boxes,
                   stage/'previews/near_pairs.jpg', 'Near candidates: consecutive left/right tiles')
            previews.append(('Near-duplicate pair samples (consecutive tiles)', 'previews/near_pairs.jpg'))
        write_json(stage/'summary.json', summary)
        links = ''.join(f'<li><a href="{p.name}">{p.name}</a></li>' for p in sorted(stage.iterdir()) if p.is_file())
        cards = ''.join(f'<h2>{escape(name)}</h2><img src="{escape(path)}" alt="{escape(name)}">' for name, path in previews)
        page = ('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>ViTSD CAR35 cleaning review</title><style>body{font:16px/1.5 system-ui;max-width:1150px;margin:auto;padding:24px}'
                'img{max-width:100%;height:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#1763a6}</style>'
                '<h1>ViTSD → CAR35: cleaning review</h1><p>No source edits, split or training dataset produced. '
                'Mapping and dHash links need human review. Counts include source defects; read quarantine.csv. '
                'Previews are bounded examples, not representative samples. Reference hashes check exact overlap only.</p>'
                '<h2>Summary</h2><pre>'+escape(json.dumps(summary, ensure_ascii=False, indent=2))+'</pre>'
                '<h2>Files</h2><ul>'+links+'</ul>'+cards)
        (stage/'index.html').write_text(page, encoding='utf-8')
        stage.rename(output)
    return summary
