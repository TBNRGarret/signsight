"""Reusable notebook dataset cache; Kaggle/Drive access stays in the notebook."""
import base64
import gzip
import hashlib
import json
import stat
import tempfile
import zipfile
from pathlib import Path

import yaml

from ai_engine.prepare_detection_data import NAMES, build_dataset
from ai_engine.train_detection import validate_dataset

SPLITS = ('train.csv', 'val.csv', 'test.csv')


class DatasetCacheMiss(ValueError):
    """No compatible cache exists and a raw source is needed."""


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_archive(local_roots, source_handle, download):
    def find(roots):
        candidates = set()
        for root in map(Path, roots):
            if root.is_dir():
                for annotation in root.rglob('Train.csv'):
                    if (annotation.parent / 'Test.csv').is_file():
                        candidates.add(annotation.parent.resolve())
        if len(candidates) > 1:
            raise ValueError('Multiple GTSRB sources; set RAW_DATASET_DIR to one archive')
        return next(iter(candidates), None)
    existing = find(local_roots)
    if existing is not None:
        return existing
    downloaded = find([download(source_handle)])
    if downloaded is None:
        raise ValueError('Downloaded raw source lacks Train.csv and Test.csv')
    return downloaded


def restore_splits(payload, checksums, target):
    if set(payload) != set(SPLITS) or set(checksums) != set(SPLITS):
        raise ValueError('Expected exactly train.csv, val.csv and test.csv')
    decoded = {}
    for name in SPLITS:
        data = gzip.decompress(base64.b64decode(payload[name], validate=True))
        if hashlib.sha256(data).hexdigest() != checksums[name]:
            raise ValueError(f'Embedded split checksum mismatch: {name}')
        decoded[name] = data
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    for name, data in decoded.items():
        (target / name).write_bytes(data)
    return target


def _descriptor(csv_root, source_id):
    directory = Path(__file__).parent
    return {'schema': 1, 'source': source_id, 'names': NAMES,
            'splits': {name: _sha(Path(csv_root) / name) for name in SPLITS},
            'code': {name: _sha(directory / name) for name in
                     ('notebook_data.py', 'prepare_detection_data.py', 'train_detection.py')},
            'deduplicate_overlaps': True, 'roi_max_inclusive': False}


def _validate_cache(root, descriptor):
    metadata = json.loads((root / '_signsight_cache.json').read_text(encoding='utf-8'))
    if metadata['descriptor'] != descriptor:
        raise ValueError('Dataset cache descriptor mismatch')
    config = yaml.safe_load((root / 'data.yaml').read_text(encoding='utf-8'))
    if config.get('path') != '.':
        raise ValueError('Dataset cache must have portable path: .')
    if _sha(root / 'manifest.json') != metadata['manifest_sha256']:
        raise ValueError('Dataset cache manifest checksum mismatch')
    report = validate_dataset(root / 'data.yaml')
    if report['sha256'] != metadata['sha256']:
        raise ValueError('Dataset cache checksum mismatch')
    return report


def _safe_extract(bundle, target):
    entries = bundle.infolist()
    if len(entries) > 100000 or sum(entry.file_size for entry in entries) > 8 * 1024**3:
        raise ValueError('Dataset cache ZIP exceeds size limits')
    seen = set()
    for entry in entries:
        path = (target / entry.filename).resolve()
        if (not path.is_relative_to(target.resolve()) or path == target.resolve()
                or '\\' in entry.filename or ':' in entry.filename
                or stat.S_ISLNK(entry.external_attr >> 16) or path in seen):
            raise ValueError('Unsafe dataset cache ZIP path')
        seen.add(path)
    bundle.extractall(target)


def _persist(root, saved, key, descriptor, report):
    saved.mkdir(parents=True, exist_ok=True)
    archive, record = saved / f'{key}.zip', saved / f'{key}.json'
    if archive.exists() or record.exists():
        if not archive.is_file() or not record.is_file():
            raise ValueError('Incomplete persistent cache; choose a new cache folder')
        metadata = json.loads(record.read_text(encoding='utf-8'))
        if (metadata['descriptor'] != descriptor or metadata['sha256'] != report['sha256']
                or metadata['archive_sha256'] != _sha(archive)):
            raise ValueError('Persistent cache checksum mismatch')
        return
    # Only this task's temporary directory is cleaned up. Existing cache is preserved.
    with tempfile.TemporaryDirectory(prefix='.signsight-save-', dir=saved) as temporary:
        staging = Path(temporary)
        packed = staging / 'dataset.zip'
        with zipfile.ZipFile(packed, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(root.rglob('*')):
                if path.is_file():
                    bundle.write(path, path.relative_to(root).as_posix())
        metadata = {'descriptor': descriptor, 'sha256': report['sha256'], 'archive_sha256': _sha(packed)}
        pending = staging / 'metadata.json'
        pending.write_text(json.dumps(metadata, sort_keys=True), encoding='utf-8')
        packed.rename(archive)
        pending.rename(record)


def prepare_cached_dataset(archive, csv_root, local_cache_root, *, source_id, persistent_root=None):
    descriptor = _descriptor(csv_root, source_id)
    key = hashlib.sha256(json.dumps(descriptor, sort_keys=True).encode()).hexdigest()
    prepared = Path(local_cache_root) / 'prepared'
    prepared.mkdir(parents=True, exist_ok=True)
    root = prepared / key
    saved = Path(persistent_root) if persistent_root is not None else None
    if root.exists():
        report = _validate_cache(root, descriptor)
    else:
        with tempfile.TemporaryDirectory(prefix='.signsight-prepare-', dir=prepared) as temporary:
            staging = Path(temporary) / 'dataset'
            packed = saved / f'{key}.zip' if saved is not None else None
            record = saved / f'{key}.json' if saved is not None else None
            if packed is not None and (packed.exists() or record.exists()):
                if not packed.is_file() or not record.is_file():
                    raise ValueError('Incomplete persistent cache; choose a new cache folder')
                metadata = json.loads(record.read_text(encoding='utf-8'))
                if metadata['descriptor'] != descriptor or metadata['archive_sha256'] != _sha(packed):
                    raise ValueError('Persistent cache checksum mismatch')
                staging.mkdir()
                with zipfile.ZipFile(packed) as bundle:
                    _safe_extract(bundle, staging)
                report = _validate_cache(staging, descriptor)
                if report['sha256'] != metadata['sha256']:
                    raise ValueError('Persistent cache dataset checksum mismatch')
            else:
                if archive is None:
                    raise DatasetCacheMiss('No compatible cache; raw source required')
                build_dataset(archive, csv_root, staging, deduplicate_overlaps=True)
                data = staging / 'data.yaml'
                config = yaml.safe_load(data.read_text(encoding='utf-8'))
                config['path'] = '.'
                data.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding='utf-8')
                report = validate_dataset(data)
                (staging / '_signsight_cache.json').write_text(json.dumps({
                    'descriptor': descriptor, 'sha256': report['sha256'],
                    'manifest_sha256': _sha(staging / 'manifest.json')}, sort_keys=True), encoding='utf-8')
            staging.rename(root)
        report['yaml'] = str(root / 'data.yaml')
    if saved is not None:
        _persist(root, saved, key, descriptor, report)
    return root / 'data.yaml', report
