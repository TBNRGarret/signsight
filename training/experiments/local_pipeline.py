"""Local Vietnamese detection experiments. Never activates a checkpoint in the API.

Run with: python -m scripts.local_detection_pipeline --help
"""
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import shutil
import sys
import tempfile

import yaml

from scripts.dataset_eda import DatasetReader, audit_dataset, duplicate_groups

SPLITS = ('train', 'val', 'test')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_assignments(path, rows):
    with Path(path).open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['dataset', 'path', 'split', 'group', 'exclude_reason'])
        writer.writeheader(); writer.writerows(rows)


def progress(items, *, desc, unit):
    for index, item in enumerate(items, 1):
        if index == 1 or index % 1000 == 0 or index == len(items):
            print(f'{desc}: {index}/{len(items)} {unit}s', flush=True)
        yield item


def inspect_sources(sources, output, annotation_format='auto'):
    """Full decode/hash audit, including ZIP members; no original file is changed."""
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(f'Choose a new EDA directory: {output}')
    roots = {name: str(Path(root).resolve()) for name, root in sources.items()}
    if not roots or any(not name for name in roots):
        raise ValueError('Provide at least one named source')
    if any(output.is_relative_to(Path(root)) for root in roots.values()):
        raise ValueError('EDA output must be outside every source directory')
    reports, mappings, assignments = {}, {}, []
    for name, root in roots.items():
        print(f'Auditing {name}: decode + SHA-256 for all images...', flush=True)
        with DatasetReader(root) as reader:
            report = audit_dataset(reader, name, hash_limit=None, verify_decode=True, progress=progress,
                                   annotation_format=annotation_format)
            report['archive_warnings'] = reader.warnings
        reports[name] = report
        for box in report['boxes']:
            key = (name, box['label_namespace'], box['class_id'])
            mappings[key] = {'dataset': name, 'namespace': key[1], 'class_id': key[2],
                             'source_name': box['class_name'],
                             'target': box['class_name'] if box['class_mapped'] else None}
        assignments.extend({'dataset': name, 'path': image['path'], 'split': image['split'],
                            'group': '', 'exclude_reason': ''} for image in report['images'])
        summary = report['summary']
        print(f'{name}: {summary["images_scanned"]} images, {summary["valid_boxes"]} boxes, '
              f'{summary["issues"]} issues; details in audit.json', flush=True)
    output.mkdir(parents=True)
    write_json(output / 'audit.json', reports)
    write_json(output / 'duplicate_groups.json', duplicate_groups(
        [row for report in reports.values() for row in report['images']]))
    write_assignments(output / 'assignments.csv', assignments)
    write_json(output / 'plan.json', {
        'sources': roots, 'annotation_format': annotation_format,
        'names': sorted({item['target'] for item in mappings.values() if item['target']}),
        'class_map': list(mappings.values()), 'assignments': 'assignments.csv',
        'reviewed': False, 'split_reviewed': False, 'empty_annotations_reviewed': False,
    })
    print(f'Review {output / "plan.json"} and assignments.csv before prepare.', flush=True)


def split_groups(rows, seed=42):
    """Explicit opt-in re-split, using user-supplied capture groups, never frames."""
    included = [row for row in rows if not row.get('exclude_reason', '').strip()]
    if any(not row.get('group', '').strip() for row in included):
        raise ValueError('Fill a capture/location group for every included image before group split')
    groups = sorted({row['group'].strip() for row in included})
    if len(groups) < 3:
        raise ValueError('Need at least 3 independent groups')
    random.Random(seed).shuffle(groups)
    train = min(len(groups) - 2, max(1, int(len(groups) * .7)))
    val = min(len(groups) - train - 1, max(1, int(len(groups) * .15)))
    chosen = {group: 'train' if i < train else 'val' if i < train + val else 'test'
              for i, group in enumerate(groups)}
    return [dict(row, split=chosen[row['group'].strip()]) if not row.get('exclude_reason', '').strip()
            else dict(row) for row in rows]


def prepare_dataset(plan_path, output):
    plan_path, output = Path(plan_path).resolve(), Path(output).resolve()
    plan = read_json(plan_path)
    if output.exists():
        raise FileExistsError(f'Output exists: {output}')
    if any(output.is_relative_to(Path(root).resolve()) for root in plan['sources'].values()):
        raise ValueError('Prepared output must be outside every source directory')
    if plan.get('reviewed') is not True or plan.get('split_reviewed') is not True:
        raise ValueError('Set reviewed and split_reviewed only after inspecting labels and split provenance')
    names = plan['names']
    if not isinstance(names, list) or not names or any(not isinstance(n, str) or not n.strip() for n in names) or len(set(names)) != len(names):
        raise ValueError('names must be a nonempty list of unique class names')
    class_map = {}
    source_names = {}
    for item in plan['class_map']:
        key = (item['dataset'], item['namespace'], str(item['class_id']))
        if key in class_map or item['target'] not in names:
            raise ValueError(f'Missing/duplicate class mapping: {key}')
        class_map[key] = names.index(item['target'])
        source_names[key] = item['source_name']
    with (plan_path.parent / plan['assignments']).open(newline='', encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream))
    assignments = {(row['dataset'], row['path']): row for row in rows}
    if len(assignments) != len(rows):
        raise ValueError('Duplicate assignment rows')
    output.parent.mkdir(parents=True, exist_ok=True)
    # TemporaryDirectory owns only this newly created directory; originals are read-only.
    with tempfile.TemporaryDirectory(prefix='.prepare-', dir=output.parent) as temporary, ExitStack() as stack:
        stage = Path(temporary) / 'dataset'; stage.mkdir()
        records, seen_hashes, seen_groups, observed = [], {}, {}, set()
        class_counts = {split: Counter() for split in SPLITS}
        excluded = []
        for dataset, root in plan['sources'].items():
            reader = stack.enter_context(DatasetReader(root))
            report = audit_dataset(reader, dataset, hash_limit=None, verify_decode=True, progress=progress,
                                   annotation_format=plan.get('annotation_format', 'auto'))
            if reader.warnings:
                raise ValueError(f'Unexpanded/broken archive in source {dataset}: {reader.warnings[:3]}')
            boxes = defaultdict(list)
            for box in report['boxes']:
                boxes[box['path']].append(box)
            for image in report['images']:
                key = (dataset, image['path']); observed.add(key)
                if key not in assignments:
                    raise ValueError(f'New/unassigned image; rerun EDA: {key}')
                assignment = assignments[key]
                if assignment.get('exclude_reason', '').strip():
                    excluded.append(assignment); continue
                split, group = assignment['split'], assignment.get('group', '').strip()
                if split not in SPLITS:
                    raise ValueError(f'Unknown split; fill assignments.csv or use group split: {key}')
                status = image['annotation_status']
                if status not in ('annotated', 'empty_annotation'):
                    raise ValueError(f'{key}: {status}; fix or explicitly exclude this image')
                if status == 'empty_annotation' and plan.get('empty_annotations_reviewed') is not True:
                    raise ValueError(f'Review empty annotations as verified negatives first: {key}')
                digest = image['sha256']
                if digest in seen_hashes and seen_hashes[digest] != split:
                    raise ValueError(f'Identical image leaks across splits: {key}')
                seen_hashes[digest] = split
                if group and group in seen_groups and seen_groups[group] != split:
                    raise ValueError(f'Capture group leaks across splits: {group}')
                if group:
                    seen_groups[group] = split
                lines = []
                for box in boxes[image['path']]:
                    mapping = (dataset, box['label_namespace'], box['class_id'])
                    if (mapping not in class_map or box['iscrowd']
                            or source_names[mapping] != box['class_name']):
                        raise ValueError(f'Unmapped class or COCO crowd requires review: {key}, {mapping}')
                    class_id = class_map[mapping]
                    x = box['x_norm'] + box['width_norm'] / 2
                    y = box['y_norm'] + box['height_norm'] / 2
                    lines.append(f'{class_id} {x:.10f} {y:.10f} {box["width_norm"]:.10f} {box["height_norm"]:.10f}')
                    class_counts[split][class_id] += 1
                filename = hashlib.sha256(json.dumps(key).encode()).hexdigest() + Path(image['path']).suffix.lower()
                relative = Path('images') / split / filename
                destination = stage / relative; destination.parent.mkdir(parents=True, exist_ok=True)
                with reader.open(image['path']) as source, destination.open('wb') as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
                if file_hash(destination) != digest:
                    raise ValueError(f'Source image changed during preparation: {key}')
                label_relative = Path('labels') / split / Path(filename).with_suffix('.txt')
                label = stage / label_relative; label.parent.mkdir(parents=True, exist_ok=True)
                label.write_text('\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8')
                records.append({'source_dataset': dataset, 'source_path': image['path'], 'split': split,
                                'group': group, 'image': relative.as_posix(), 'sha256': digest,
                                'label': label_relative.as_posix(), 'label_sha256': file_hash(label)})
        if set(assignments) != observed:
            raise ValueError('Stale assignments: source images removed or source selection changed; rerun EDA')
        if {record['split'] for record in records} != set(SPLITS):
            raise ValueError('Each of train, val and independent test must contain images')
        missing_train = [names[i] for i in range(len(names)) if not class_counts['train'][i]]
        if missing_train:
            raise ValueError(f'Every target class needs train annotations; missing: {missing_train}')
        config = {'path': str(output), **{split: f'images/{split}' for split in SPLITS}, 'names': names}
        (stage / 'data.yaml').write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding='utf-8')
        manifest = {'kind': 'vietnam_local_experiment', 'names': names, 'class_map': plan['class_map'],
                    'annotation_format': plan.get('annotation_format', 'auto'),
                    'sources': plan['sources'], 'images': records, 'excluded': excluded,
                    'class_counts': class_counts,
                    'missing_classes': {s: [names[i] for i in range(len(names)) if not class_counts[s][i]] for s in SPLITS},
                    'group_coverage': sum(bool(r['group']) for r in records),
                    'limitations': 'Exact-byte duplicate check only. Review near-duplicate frames, split provenance, and missing classes.'}
        write_json(stage / 'manifest.json', manifest)
        # rename refuses to replace an existing directory on Windows.
        stage.rename(output)
    print(f'Prepared {len(records)} images: {output / "data.yaml"}', flush=True)
    return manifest


def verify_prepared(data):
    data = Path(data).resolve(); root = data.parent
    config, manifest = yaml.safe_load(data.read_text(encoding='utf-8')), read_json(root / 'manifest.json')
    if config.get('names') != manifest['names'] or Path(config.get('path', '')).resolve() != root:
        raise ValueError('Dataset path/names changed since preparation')
    if any(config.get(split) != f'images/{split}' for split in SPLITS):
        raise ValueError('Split paths changed since preparation')
    expected = set()
    seen_hashes, seen_groups = {}, {}
    for record in manifest['images']:
        split = record['split']
        image, label = (root / record[key] for key in ('image', 'label'))
        if split not in SPLITS or not image.resolve().is_relative_to(root) or not label.resolve().is_relative_to(root):
            raise ValueError('Unsafe manifest path or split')
        if image in expected or image.parent != root / 'images' / split or label != root / 'labels' / split / image.with_suffix('.txt').name:
            raise ValueError('Manifest contains repeated or misplaced image/label')
        expected.add(image)
        if file_hash(image) != record['sha256'] or file_hash(label) != record['label_sha256']:
            raise ValueError(f'Prepared image/label changed; prepare a new version: {image}')
        for value, seen in ((record['sha256'], seen_hashes), (record.get('group'), seen_groups)):
            if value and value in seen and seen[value] != split:
                raise ValueError('Manifest contains cross-split content/group leakage')
            if value:
                seen[value] = split
    with DatasetReader(root) as reader:
        audit = audit_dataset(reader, 'prepared', hash_limit=0, verify_decode=True)
    actual = {root / row['path'] for row in audit['images']}
    if actual != expected or {r['split'] for r in audit['images']} != set(SPLITS):
        raise ValueError('Prepared image inventory changed or a split is empty')
    if any(r['annotation_status'] not in ('annotated', 'empty_annotation') for r in audit['images']):
        raise ValueError('Invalid prepared labels/images')
    return {'images': len(expected), 'names': manifest['names'], 'manifest_sha256': file_hash(root / 'manifest.json'),
            'splits': dict(Counter(r['split'] for r in audit['images'])),
            'missing_classes': manifest['missing_classes'], 'group_coverage': manifest['group_coverage']}


def run_model(command, data, model, output, *, allow_download=False, epochs=50, imgsz=640,
              batch=2, device='0', split='test', yolo_factory=None):
    output, data = Path(output).resolve(), Path(data).resolve()
    if output.exists():
        raise FileExistsError(f'Choose a new run directory: {output}')
    if output.is_relative_to(data.parent):
        raise ValueError('Run output must be outside the prepared dataset')
    if epochs < 1 or imgsz < 32 or batch < 1 or split not in ('val', 'test'):
        raise ValueError('Invalid training/evaluation settings')
    if not Path(model).is_file() and (command != 'train' or not allow_download):
        raise ValueError('Supply a local checkpoint, or allow official weight download with --allow-download')
    if not Path(model).is_file() and model not in ('yolo11n.pt', 'yolo11s.pt', 'yolo11m.pt', 'yolo11l.pt', 'yolo11x.pt'):
        raise ValueError('Download supports official YOLO11 model names only')
    dataset = verify_prepared(data)
    if yolo_factory is None:
        from ai_engine.detection import configure_ultralytics
        configure_ultralytics()
        from ultralytics import YOLO
        yolo_factory = YOLO
    detector = yolo_factory(str(model), task='detect')
    options = dict(data=str(data), imgsz=imgsz, batch=batch, device=device, workers=0,
                   project=str(output.parent), name=output.name, exist_ok=False, plots=True)
    metrics = None
    if command == 'train':
        detector.train(**options, epochs=epochs, seed=42, deterministic=True, cache=False,
                       amp=False, fliplr=0., flipud=0., degrees=5.)
        checkpoint = Path(detector.trainer.best)
    elif command == 'evaluate':
        if detector.task != 'detect' or [detector.names[i] for i in range(len(detector.names))] != dataset['names']:
            raise ValueError('Checkpoint taxonomy/task does not match the prepared dataset')
        result = detector.val(**options, split=split)
        metrics = {key: float(value) for key, value in result.results_dict.items()}
        checkpoint = Path(model).resolve()
    else:
        raise ValueError(f'Unknown model command: {command}')
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / 'pipeline_report.json', {
        'created_at': datetime.now(timezone.utc).isoformat(), 'command': command, **dataset,
        'checkpoint': str(checkpoint.resolve()), 'checkpoint_sha256': file_hash(checkpoint),
        'settings': {**options, 'epochs': epochs if command == 'train' else None,
                     **({'seed': 42, 'deterministic': True, 'cache': False, 'amp': False,
                         'fliplr': 0., 'flipud': 0., 'degrees': 5.} if command == 'train' else {'split': split})},
        'test_evaluated': command == 'evaluate' and split == 'test', 'metrics': metrics,
        'limitation': 'Experimental taxonomy; API integration requires explicit mapping and a compatible detector.',
    })
    print(f'Results: {output}', flush=True)


def main():
    # Windows redirected terminals may otherwise use cp1252, breaking Vietnamese class names.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    eda = commands.add_parser('eda', help='Full local/ZIP audit and review-plan draft')
    eda.add_argument('--source', action='append', required=True, metavar='NAME=FOLDER')
    eda.add_argument('--output', type=Path, required=True)
    eda.add_argument('--annotation-format', choices=('auto', 'yolo', 'voc', 'coco'), default='auto')
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--plan', type=Path, required=True)
    prepare.add_argument('--output', type=Path, required=True)
    splitter = commands.add_parser('split', help='Optional group re-split; writes a new CSV')
    splitter.add_argument('--assignments', type=Path, required=True)
    splitter.add_argument('--output', type=Path, required=True)
    splitter.add_argument('--seed', type=int, default=42)
    validate = commands.add_parser('validate')
    validate.add_argument('--data', type=Path, required=True)
    for command in ('train', 'evaluate'):
        runner = commands.add_parser(command)
        runner.add_argument('--data', type=Path, required=True)
        runner.add_argument('--model', required=True)
        runner.add_argument('--output', type=Path, required=True)
        runner.add_argument('--allow-download', action='store_true')
        runner.add_argument('--epochs', type=int, default=50)
        runner.add_argument('--imgsz', type=int, default=640)
        runner.add_argument('--batch', type=int, default=2)
        runner.add_argument('--device', default='0')
        runner.add_argument('--split', choices=('val', 'test'), default='test')
    args = parser.parse_args()
    try:
        if args.command == 'eda':
            pairs = [source.split('=', 1) for source in args.source]
            if any(len(pair) != 2 for pair in pairs) or len({pair[0] for pair in pairs}) != len(pairs):
                raise ValueError('Use unique --source NAME=FOLDER entries')
            inspect_sources(dict(pairs), args.output, args.annotation_format)
        elif args.command == 'prepare':
            prepare_dataset(args.plan, args.output)
        elif args.command == 'split':
            if args.output.exists() or args.output.resolve() == args.assignments.resolve():
                raise FileExistsError('Choose a new assignments output file')
            with args.assignments.open(newline='', encoding='utf-8-sig') as stream:
                rows = split_groups(list(csv.DictReader(stream)), args.seed)
            write_assignments(args.output, rows)
        elif args.command == 'validate':
            print(json.dumps(verify_prepared(args.data), indent=2, ensure_ascii=False))
        else:
            run_model(**vars(args))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'Pipeline stopped: {error}\n')


if __name__ == '__main__':
    main()
