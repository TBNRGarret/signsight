"""Read-only detection EDA, including files inside ZIPs. No training or remapping."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import random
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image
import yaml

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tif', '.tiff'}


class DatasetReader:
    def __init__(self, root):
        self.root = Path(root).resolve()
        if self.root.is_file() and self.root.suffix.lower() == '.zip':
            paths, base = [self.root], self.root.parent
        elif self.root.is_dir():
            paths, base = sorted(self.root.rglob('*')), self.root
        else:
            raise FileNotFoundError(f'Dataset directory or ZIP not found: {self.root}')
        self.entries, self.zips, self.warnings = {}, {}, []
        for path in paths:
            if not path.is_file() or path.is_symlink():
                continue
            name = path.relative_to(base).as_posix()
            self.entries[name] = (path, None, path.stat().st_size)
            if path.suffix.lower() == '.zip':
                try:
                    archive = zipfile.ZipFile(path)
                    self.zips[name] = archive
                    for item in archive.infolist():
                        if not item.is_dir():
                            self.entries[name + '!/' + item.filename] = (archive, item, item.file_size)
                            if PurePosixPath(item.filename).suffix.lower() in {'.zip', '.rar', '.7z', '.gz', '.tar'}:
                                self.warnings.append(f'Nested archive not expanded: {name}!/{item.filename}')
                except (OSError, zipfile.BadZipFile) as error:
                    self.warnings.append(f'Cannot open archive {name}: {type(error).__name__}')

    def open(self, name):
        source, member, _ = self.entries[name]
        return source.open(member) if member is not None else source.open('rb')

    def read(self, name, max_bytes=256 * 1024 * 1024):
        if self.entries[name][2] > max_bytes:
            raise ValueError(f'Annotation exceeds {max_bytes // 1024**2} MiB read limit')
        with self.open(name) as stream:
            value = stream.read(max_bytes + 1)
        if len(value) > max_bytes:
            raise ValueError('Annotation read limit exceeded')
        return value

    def close(self):
        for archive in self.zips.values():
            archive.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def split_name(name):
    mapping = {'train': 'train', 'training': 'train', 'val': 'val', 'valid': 'val',
               'validation': 'val', 'test': 'test', 'testing': 'test'}
    found = {mapping[part.casefold()] for part in PurePosixPath(name).parts[:-1] if part.casefold() in mapping}
    return next(iter(found)) if len(found) == 1 else 'unknown'


def paired_files(name, extension, directory_pairs, case_names):
    path = PurePosixPath(name)
    candidates = {str(path.with_suffix(extension))}
    parts = list(path.parts)
    for i, part in enumerate(parts[:-1]):
        for before, after in directory_pairs:
            if part.casefold() == before.casefold():
                changed = parts.copy(); changed[i] = after
                candidates.add(str(PurePosixPath(*changed).with_suffix(extension)))
    return sorted({actual for candidate in candidates for actual in case_names.get(candidate.casefold(), [])})


def audit_dataset(reader, dataset, image_limit=None, hash_limit=2000, seed=42,
                  verify_decode=False, progress=None, annotation_format='auto'):
    """All counts refer to scanned images; partial/hash coverage is explicit.

    Zero objects means empty_annotation only for a recognized annotation file.
    Missing/unreadable/ambiguous labels never become verified background images.
    """
    if annotation_format not in {'auto', 'yolo', 'voc', 'coco'}:
        raise ValueError('annotation format must be auto, yolo, voc or coco')
    rng = random.Random(seed)
    images = sorted(name for name in reader.entries if PurePosixPath(name).suffix.lower() in IMAGE_EXTENSIONS)
    if (image_limit is not None and image_limit < 0) or (hash_limit is not None and hash_limit < 0):
        raise ValueError('Limits must be nonnegative or None')
    selected = images if image_limit is None else sorted(rng.sample(images, min(image_limit, len(images))))
    hashed = set(selected if hash_limit is None else rng.sample(selected, min(hash_limit, len(selected))))
    issues, image_rows, boxes, catalogs = [], [], [], []
    case_names = defaultdict(list)
    for name in reader.entries:
        case_names[name.casefold()].append(name)

    def issue(path, message):
        issues.append({'dataset': dataset, 'path': path, 'message': str(message)[:600]})

    for warning in reader.warnings:
        issue('', warning)
    for name in reader.entries:
        suffix = PurePosixPath(name).suffix.lower()
        try:
            names = None
            if suffix in {'.yaml', '.yml'}:
                config = yaml.safe_load(reader.read(name, 1024**2))
                if isinstance(config, dict) and 'names' in config:
                    names = config['names']
            elif PurePosixPath(name).name.casefold() in {'classes.txt', 'obj.names', 'classes.names'}:
                names = reader.read(name, 1024**2).decode('utf-8-sig').splitlines()
            if names is not None:
                if isinstance(names, list):
                    names = dict(enumerate(names))
                if not isinstance(names, dict) or not names:
                    raise ValueError('Invalid class names')
                normalized = {int(key): str(value).strip() for key, value in names.items()}
                if any(key < 0 or not value for key, value in normalized.items()):
                    raise ValueError('Invalid class ID/name')
                catalogs.append((name, normalized))
        except Exception as error:
            issue(name, f'Class metadata: {type(error).__name__}: {error}')

    def catalog_for(image_name):
        matches = [(name, names) for name, names in catalogs
                   if str(PurePosixPath(name).parent) == '.'
                   or image_name.startswith(str(PurePosixPath(name).parent) + '/')]
        if matches:
            depth = max(len(PurePosixPath(name).parent.parts) for name, _ in matches)
            closest = [(name, names) for name, names in matches if len(PurePosixPath(name).parent.parts) == depth]
            if len({json.dumps(names, sort_keys=True) for _, names in closest}) > 1:
                issue(image_name, 'Conflicting class maps at the same directory; class IDs remain unmapped.')
                return ('ambiguous-class-map', {})
            return closest[0]
        unique = {json.dumps(names, sort_keys=True) for _, names in catalogs}
        return catalogs[0] if len(unique) == 1 else ('unmapped', {})

    # COCO indexing: resolve full/suffix names; ambiguous duplicate basenames are errors.
    by_basename = defaultdict(list)
    for name in images:
        by_basename[PurePosixPath(name).name].append(name)
    coco = defaultdict(list)
    for name in reader.entries:
        if annotation_format not in {'auto', 'coco'} or PurePosixPath(name).suffix.lower() != '.json':
            continue
        try:
            content = json.loads(reader.read(name))
            if not isinstance(content, dict) or not {'images', 'annotations', 'categories'} <= content.keys():
                issue(name, 'JSON is not COCO detection; inspect separately (e.g. LabelMe/classification).')
                continue
            categories = {row['id']: str(row['name']) for row in content['categories']}
            annotations = defaultdict(list)
            for annotation in content['annotations']:
                annotations[annotation['image_id']].append(annotation)
            for image in content['images']:
                filename = str(image['file_name']).replace('\\', '/')
                candidates = by_basename[PurePosixPath(filename).name]
                suffix_matches = [key for key in candidates if key == filename or key.endswith('/' + filename)]
                if suffix_matches:
                    candidates = suffix_matches
                # Do not join a JSON in one archive to same-named images in another.
                container = name.split('!/', 1)[0] if '!/' in name else None
                candidates = [key for key in candidates if
                              (key.startswith(container + '!/') if container else '!/' not in key)]
                if len(candidates) != 1:
                    issue(name, f'COCO image reference missing/ambiguous: {filename}')
                    continue
                coco[candidates[0]].append((name, categories, image, annotations[image['id']]))
        except Exception as error:
            issue(name, f'JSON: {type(error).__name__}: {error}')

    iterator = progress(selected, desc=dataset, unit='image') if progress else selected
    for name in iterator:
        row = {'dataset': dataset, 'path': name, 'split': split_name(name), 'parent_folder': str(PurePosixPath(name).parent),
               'width': None, 'height': None, 'mode': None, 'format': None,
               'annotation_status': 'missing_annotation', 'boxes': 0, 'sha256': None}
        image_rows.append(row)
        try:
            with reader.open(name) as stream, Image.open(stream) as image:
                row.update(width=image.width, height=image.height, mode=image.mode)
                if verify_decode:
                    image.load()
            if name in hashed:
                digest = hashlib.sha256()
                with reader.open(name) as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(block)
                row['sha256'] = digest.hexdigest()
        except Exception as error:
            row['annotation_status'] = 'unreadable_image'
            issue(name, f'Image: {type(error).__name__}: {error}')
            continue
        txt = paired_files(name, '.txt', [('images', 'labels')], case_names)
        xml = paired_files(name, '.xml', [('JPEGImages', 'Annotations'), ('images', 'annotations')], case_names)
        options = [('yolo', path) for path in txt] + [('voc', path) for path in xml] + [('coco', entry) for entry in coco[name]]
        if annotation_format != 'auto':
            options = [option for option in options if option[0] == annotation_format]
        if not options:
            continue
        if len(options) > 1:
            row['annotation_status'] = 'ambiguous_annotation'
            issue(name, 'Multiple matching annotations/formats; select a single export/root before training.')
            continue
        kind, annotation = options[0]
        row['format'] = kind
        raw_boxes, bad = [], False
        try:
            if kind == 'yolo':
                source, names = catalog_for(name)
                for line_number, line in enumerate(reader.read(annotation, 8 * 1024**2).decode('utf-8-sig').splitlines(), 1):
                    if not line.strip():
                        continue
                    try:
                        fields = line.split()
                        if len(fields) != 5:
                            raise ValueError('YOLO detection expects 5 columns; segmentation/other format is not inferred')
                        class_id = int(fields[0])
                        if class_id < 0 or names and class_id not in names:
                            raise ValueError('Class ID outside class map')
                        cx, cy, width, height = map(float, fields[1:])
                        raw_boxes.append((str(class_id), names.get(class_id, f'class_{class_id}'), bool(names),
                                          source, cx - width/2, cy - height/2, width, height, 0))
                    except Exception as error:
                        bad = True; issue(annotation, f'Line {line_number}: {error}')
            elif kind == 'voc':
                tree = ET.fromstring(reader.read(annotation, 8 * 1024**2))
                if tree.tag != 'annotation':
                    raise ValueError('Not a VOC annotation')
                for dimension in ('width', 'height'):
                    value = tree.findtext('size/' + dimension)
                    if value is not None and int(value) != row[dimension]:
                        raise ValueError('VOC annotation size differs from image')
                for obj in tree.findall('object'):
                    label = obj.findtext('name')
                    if not label:
                        raise ValueError('VOC object without class name')
                    xmin, ymin, xmax, ymax = [float(obj.findtext('bndbox/' + key)) for key in ('xmin', 'ymin', 'xmax', 'ymax')]
                    raw_boxes.append((label, label, True, 'voc:names', xmin/row['width'], ymin/row['height'],
                                      (xmax-xmin)/row['width'], (ymax-ymin)/row['height'], 0))
            else:
                annotation_path, categories, image, objects = annotation
                for dimension in ('width', 'height'):
                    if dimension in image and int(image[dimension]) != row[dimension]:
                        raise ValueError('COCO annotation size differs from image')
                for obj in objects:
                    class_id = obj['category_id']
                    if class_id not in categories:
                        raise ValueError('COCO category missing from categories')
                    x, y, width, height = map(float, obj['bbox'])
                    raw_boxes.append((str(class_id), categories[class_id], True, annotation_path,
                                      x/row['width'], y/row['height'], width/row['width'], height/row['height'], int(obj.get('iscrowd', 0))))
            for class_id, label, mapped, schema, x, y, width, height, crowd in raw_boxes:
                if not all(math.isfinite(v) for v in (x, y, width, height)) or min(width, height) <= 0 or min(x, y) < -1e-6 or max(x+width, y+height) > 1+1e-6:
                    bad = True; issue(name, 'Invalid bbox: nonfinite, empty, negative, or outside image'); continue
                boxes.append({'dataset': dataset, 'path': name, 'split': row['split'], 'format': kind,
                              'label_namespace': schema, 'class_id': class_id, 'class_name': label, 'class_mapped': mapped,
                              'x_norm': x, 'y_norm': y, 'width_norm': width, 'height_norm': height,
                              'area_fraction': width * height, 'iscrowd': crowd,
                              'short_side_at_640': min(width*row['width'], height*row['height']) * 640 / max(row['width'], row['height'])})
                row['boxes'] += 1
            row['annotation_status'] = 'invalid_annotation' if bad else 'annotated' if row['boxes'] else 'empty_annotation'
        except Exception as error:
            row['annotation_status'] = 'invalid_annotation'
            issue(name, f'{kind}: {type(error).__name__}: {error}')

    summary = {'dataset': dataset, 'root': str(reader.root), 'images_total': len(images), 'images_scanned': len(image_rows),
               'partial_scan': len(selected) < len(images), 'images_hashed': sum(bool(row['sha256']) for row in image_rows),
               'hash_partial': sum(bool(row['sha256']) for row in image_rows) < len(images),
               'verify_decode': verify_decode, 'annotation_format': annotation_format,
               'valid_boxes': len(boxes), 'issues': len(issues),
               'invalid_annotations': sum(row['annotation_status'] == 'invalid_annotation' for row in image_rows),
               'annotation_status': dict(Counter(row['annotation_status'] for row in image_rows)),
               'formats': dict(Counter(row['format'] for row in image_rows if row['format'])),
               'file_extensions': dict(Counter(PurePosixPath(name).suffix.lower() for name in reader.entries)),
               'class_maps': [{'path': name, 'names': names} for name, names in catalogs]}
    return {'summary': summary, 'images': image_rows, 'boxes': boxes, 'issues': issues}


def duplicate_groups(image_rows):
    grouped = defaultdict(list)
    for row in image_rows:
        if row.get('sha256'):
            grouped[row['sha256']].append(row)
    return [{'sha256': digest, 'copies': len(rows), 'cross_dataset': len({r['dataset'] for r in rows}) > 1,
             'cross_split': len({r['split'] for r in rows} - {'unknown'}) > 1,
             'members': [{'dataset': r['dataset'], 'path': r['path'], 'split': r['split']} for r in rows]}
            for digest, rows in grouped.items() if len(rows) > 1]
