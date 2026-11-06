"""Prepare a downloaded YOLO folder as a versioned CAR35 development dataset.

Only data.yaml and train/valid/test image/label roots are read. Filename numbers
are deliberately not treated as video/capture metadata. Legacy ZIP/cache recipes
are unchanged; this artifact is consumed through its ordinary YOLO data.yaml.
"""
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile

from PIL import Image
import yaml

from training.data.audit import DatasetReader, IMAGE_EXTENSIONS, audit_dataset
from training.data.common import CAR35, SPLITS, digest_file, read_json, write_json
from training.data.supsign import cluster_records, visual_hash
from training.data.folder_splits import choose_folder_splits


class FolderReader(DatasetReader):
    """Reuse the source auditor without recursively scanning a whole workspace."""
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.entries, self.zips, self.warnings = {}, {}, []
        config = self.root/'data.yaml'
        if not config.is_file():
            raise FileNotFoundError(config)
        paths = [config]
        for split in ('train', 'valid', 'test'):
            for kind in ('images', 'labels'):
                directory = self.root/split/kind
                if not directory.is_dir():
                    raise ValueError(f'Missing source directory: {directory}')
                paths.extend(sorted(p for p in directory.rglob('*') if p.is_file()))
        for path in paths:
            if path.is_symlink() or not path.resolve().is_relative_to(self.root):
                raise ValueError('Source symlink resolves outside the dataset')
            name = path.relative_to(self.root).as_posix()
            self.entries[name] = path, None, path.stat().st_size


def _audit(reader, workers, progress):
    """Independent file batches; retain the existing label/geometry/decode audit."""
    images = sorted(n for n in reader.entries if Path(n).suffix.lower() in IMAGE_EXTENSIONS)
    if not images:
        raise ValueError('No source images')
    # Use a bounded number of batches; files are only opened inside the workers.
    batches = [images[start:start+512] for start in range(0, len(images), 512)]
    annotations = {n: v for n, v in reader.entries.items() if Path(n).suffix.lower() not in IMAGE_EXTENSIONS}

    def scan(names):
        partial = object.__new__(DatasetReader)
        partial.root, partial.zips, partial.warnings = reader.root, {}, []
        # Include all labels to preserve the existing ambiguity checks.
        partial.entries = {**annotations, **{n: reader.entries[n] for n in names}}
        return audit_dataset(partial, 'downloaded_supsign', hash_limit=None,
                             verify_decode=True, annotation_format='yolo')

    reports = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = executor.map(scan, batches)
        results = progress(results, desc='Audit source batches (512 images)', unit='batch') if progress else results
        for report in results:
            reports.append(report)
    rows = [r for report in reports for r in report['images']]
    boxes = [b for report in reports for b in report['boxes']]
    issues = [i for report in reports for i in report['issues']]
    summary = dict(dataset='downloaded_supsign', images_total=len(images), images_scanned=len(rows),
                   images_hashed=sum(bool(r['sha256']) for r in rows), partial_scan=False,
                   hash_partial=False, verify_decode=True, annotation_format='yolo', valid_boxes=len(boxes),
                   annotation_status=dict(Counter(r['annotation_status'] for r in rows)),
                   issues=len(issues), class_maps=reports[0]['summary']['class_maps'])
    return dict(summary=summary, images=rows, boxes=boxes, issues=issues)


def prepare_folder_dataset(source, output, *, classes=CAR35, seed=42, near_threshold=4,
                           progress=None, workers=8):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    inputs = [source/s for s in ('train', 'valid', 'test')]
    if output == source or source.is_relative_to(output) or any(
            output.is_relative_to(p) or p.is_relative_to(output) for p in inputs):
        raise ValueError('Output overlaps source image/label roots')
    if not classes or len(set(classes)) != len(classes) or any(not isinstance(c,str) or not c for c in classes):
        raise ValueError('Choose unique target class names')
    if type(workers) is not int or not 1 <= workers <= 32:
        raise ValueError('workers must be 1..32')
    if near_threshold is not None and (type(near_threshold) is not int or not 0 <= near_threshold <= 8):
        raise ValueError('Invalid dHash distance')
    implementation_files = {name:digest_file(Path(__file__).with_name(name)) for name in
                            ('folder_dataset.py','folder_splits.py','audit.py','supsign.py','common.py')}
    implementation_sha256 = hashlib.sha256(json.dumps(implementation_files,sort_keys=True).encode()).hexdigest()
    source_yaml_sha256 = digest_file(source/'data.yaml')
    with FolderReader(source) as reader:
        report = _audit(reader, workers, progress)
        available = {n for catalog in report['summary']['class_maps'] for n in catalog['names'].values()}
        if set(classes)-available:
            raise ValueError(f'Missing source classes: {sorted(set(classes)-available)}')
        by_path = defaultdict(list)
        for box in report['boxes']:
            by_path[box['path']].append(box)
        copies, excluded = defaultdict(list), []
        for image in report['images']:
            if image['annotation_status'] not in ('annotated', 'empty_annotation'):
                excluded.append(dict(source_path=image['path'], reason=image['annotation_status']))
                continue
            if any(not b['class_mapped'] for b in by_path[image['path']]):
                raise ValueError('Unmapped source classes')
            copies[image['sha256']].append(image)
        candidates, duplicates = [], 0

        def convert(item):
            digest, members = item
            signatures = {tuple(sorted((b['class_name'], *(round(b[k],8) for k in
                           ('x_norm','y_norm','width_norm','height_norm'))) for b in by_path[m['path']]))
                          for m in members}
            if len(signatures) != 1:
                return None, [dict(source_path=m['path'],reason='conflicting_duplicate_labels') for m in members], 0
            representative = min(members,key=lambda m:m['path'])
            lines = []
            for box in by_path[representative['path']]:
                if box['class_name'] in classes:
                    cx,cy = box['x_norm']+box['width_norm']/2, box['y_norm']+box['height_norm']/2
                    lines.append(f"{classes.index(box['class_name'])} {cx:.10f} {cy:.10f} {box['width_norm']:.10f} {box['height_norm']:.10f}")
            with reader.open(representative['path']) as stream, Image.open(stream) as image:
                value = visual_hash(image) if near_threshold is not None else 0
                width,height = image.size
            return dict(source_path=representative['path'], aliases=sorted(m['path'] for m in members),
                        sha256=digest, lines=lines, visual_hash=value, width=width, height=height), [], len(members)-1

        with ThreadPoolExecutor(max_workers=workers) as executor:
            results = executor.map(convert, sorted(copies.items()))
            if progress: results=progress(results,desc='Deduplicate / visual hashes',unit='image')
            for row, bad, removed in results:
                excluded.extend(bad); duplicates += removed
                if row is not None: candidates.append(row)
        # No filename aliases are passed to the legacy clustering helper: only
        # dHash edges may join distinct SHA-256 images in this new recipe.
        grouping_rows = [dict(r,aliases=[]) for r in candidates]
        groups = cluster_records(grouping_rows, near_threshold=near_threshold, progress=progress)
        for row, group in zip(candidates, groups): row['group']=group
        if progress: print('Assigning whole groups to 70/15/15 target splits...',flush=True)
        counts, missing = choose_folder_splits(candidates,classes,seed)
        negative_images = sum(not r['lines'] for r in candidates)
        output.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.car35-folder-',dir=output.parent) as temporary:
            stage=Path(temporary)/'dataset';stage.mkdir()
            for split in SPLITS:
                (stage/'images'/split).mkdir(parents=True)
                (stage/'labels'/split).mkdir(parents=True)

            def copy(row):
                row=dict(row)
                suffix=Path(row['source_path']).suffix.lower()
                row['image']=f"images/{row['split']}/{row['sha256']}{suffix}"
                row['label']=f"labels/{row['split']}/{row['sha256']}.txt"
                shutil.copyfile(source/row['source_path'],stage/row['image'])
                if digest_file(stage/row['image']) != row['sha256']:
                    raise ValueError('Source image changed while copying')
                lines=row.pop('lines')
                (stage/row['label']).write_text('\n'.join(lines)+ ('\n' if lines else ''),encoding='utf-8')
                row['label_sha256']=digest_file(stage/row['label'])
                row.pop('visual_hash')
                return row

            with ThreadPoolExecutor(max_workers=workers) as executor:
                results=executor.map(copy,candidates)
                if progress: results=progress(results,desc='Write checked dataset copies',unit='image')
                rows=list(results)
            # With no explicit path, Ultralytics resolves paths beside the YAML.
            # path='.' would instead depend on the training process's cwd.
            config=dict(train='images/train',val='images/val',test='images/test',names=list(classes))
            (stage/'data.yaml').write_text(yaml.safe_dump(config,sort_keys=False),encoding='utf-8')
            settings=dict(version=2,seed=seed,target_ratios=[.7,.15,.15],near_threshold=near_threshold,
                          grouping='sha256_dedup_then_dhash_components',filename_grouping=False,
                          splitting='strongest_class_groups_train_then_ratio_balance',
                          implementation_files=implementation_files,
                          implementation_sha256=implementation_sha256)
            if digest_file(source/'data.yaml') != source_yaml_sha256:
                raise ValueError('Source class mapping changed during preparation')
            manifest=dict(kind='car35_folder_development_v4',names=list(classes),settings=settings,
                          source_summary=report['summary'],source_yaml_sha256=source_yaml_sha256,
                          source_root=str(source),images=rows,excluded=excluded,issues=report['issues'],
                          duplicates_removed=duplicates,negative_images=negative_images,
                          class_counts={s:dict(counts[s]) for s in SPLITS},missing_classes=missing,
                          split_provenance='dhash_development_groups',independent_field_test=False,
                          limitations='dHash groups are development heuristics, not verified trips or physical signs. '
                          'Negatives mean no selected CAR35 label, not no traffic signs. '
                          'No guarantee against every near-duplicate or independent-field leakage. '
                          'This is a new benchmark; do not directly compare its metrics with V3.')
            write_json(stage/'manifest.json',manifest)
            _write_counts(stage,manifest)
            stage.rename(output)
    return manifest


def _write_counts(root, manifest):
    with (root/'class_counts.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        fields=['class_id','name',*SPLITS,'total']
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for i,name in enumerate(manifest['names']):
            counts={s:manifest['class_counts'][s].get(i,manifest['class_counts'][s].get(str(i),0)) for s in SPLITS}
            writer.writerow(dict(class_id=i,name=name,**counts,total=sum(counts.values())))


def verify_folder_dataset(root, *, workers=8, progress=None):
    root=Path(root).resolve();manifest=read_json(root/'manifest.json')
    if type(workers) is not int or not 1 <= workers <= 32:
        raise ValueError('workers must be 1..32')
    config=yaml.safe_load((root/'data.yaml').read_text(encoding='utf-8'))
    expected=dict(train='images/train',val='images/val',test='images/test',names=manifest['names'])
    if config != expected: raise ValueError('Dataset YAML changed')
    images,labels,hashes,groups=set(),set(),set(),{}
    counts={s:Counter() for s in SPLITS};split_images=Counter();group_sizes=Counter()
    def check_row(row):
        image,label=(root/row[k] for k in ('image','label'));split=row['split']
        if (split not in SPLITS or not image.resolve().is_relative_to(root) or not label.resolve().is_relative_to(root)
            or image.parent!=root/'images'/split or label!=root/'labels'/split/(image.stem+'.txt')):
            raise ValueError('Unsafe dataset path')
        content=label.read_bytes()
        if digest_file(image)!=row['sha256'] or hashlib.sha256(content).hexdigest()!=row['label_sha256']:
            raise ValueError('Dataset image/label hash changed')
        current=Counter()
        for line in content.decode('utf-8').splitlines():
            if not line.strip():continue
            fields=line.split()
            if len(fields)!=5: raise ValueError('Invalid label columns')
            cls=int(fields[0]);cx,cy,w,h=map(float,fields[1:])
            if (not 0<=cls<len(manifest['names']) or not all(math.isfinite(v) for v in (cx,cy,w,h))
                or min(w,h)<=0 or min(cx-w/2,cy-h/2)<-1e-6 or max(cx+w/2,cy+h/2)>1+1e-6):
                raise ValueError('Invalid class or bbox')
            current[cls]+=1
        return row,image,label,current
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results=executor.map(check_row,manifest['images'])
        if progress:results=progress(results,desc='Verify image/label hashes and boxes',unit='image')
        for row,image,label,current in results:
            split=row['split']
            if row['sha256'] in hashes or (row['group'] in groups and groups[row['group']]!=split):
                raise ValueError('Cross-split group or repeated image hash')
            counts[split].update(current)
            images.add(image);labels.add(label);hashes.add(row['sha256']);groups[row['group']]=split
            split_images[split]+=1;group_sizes[row['group']]+=1
    if images!=set((root/'images').rglob('*.*')) or labels!=set((root/'labels').rglob('*.*')):
        raise ValueError('Dataset inventory changed')
    if set(split_images)!=set(SPLITS):raise ValueError('Empty dataset split')
    for split in SPLITS:
        recorded={int(k):v for k,v in manifest['class_counts'][split].items() if v}
        if dict(counts[split])!=recorded:raise ValueError('Class counts changed')
    return dict(images=len(images),boxes=sum(sum(c.values()) for c in counts.values()),
                names=manifest['names'],split_images=dict(split_images),groups=len(groups),
                split_groups=dict(Counter(groups.values())),largest_group_images=max(group_sizes.values()),
                missing_classes=manifest['missing_classes'],manifest_sha256=digest_file(root/'manifest.json'),
                cross_split_exact_duplicates=0,cross_split_stored_groups=0,
                independent_field_test=False)
