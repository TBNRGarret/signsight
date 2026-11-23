"""Prepare a raw 107-class YOLO ZIP as a new CAR35 development benchmark."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import zipfile

import yaml

from training.data.common import CAR35, digest_file, read_json, write_json
from training.data.car35_bundle import verify_car35
from training.data.folder_dataset import prepare_folder_dataset


def _recipe(dataset_version, seed, near_threshold):
    if not isinstance(dataset_version, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', dataset_version):
        raise ValueError('Supply a safe new dataset version')
    if type(seed) is not int or (near_threshold is not None and
            (type(near_threshold) is not int or not 0 <= near_threshold <= 8)):
        raise ValueError('Invalid preparation seed/dHash settings')
    files = {name:Path(__file__).with_name(name).read_text(encoding='utf-8') for name in
             ('raw_car35.py','folder_dataset.py','folder_splits.py','audit.py','supsign.py','common.py')}
    return dict(version=1, dataset_version=dataset_version, seed=seed, near_threshold=near_threshold,
                implementation_sha256=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest())


def verify_raw_car35(root, *, dataset_version, seed=42, near_threshold=4, expected_source_sha256=''):
    """Reuse only a fully verified dataset from the same raw preparation recipe."""
    manifest = read_json(Path(root)/'manifest.json')
    raw = manifest.get('raw_zip_preparation', {})
    if raw.get('recipe') != _recipe(dataset_version, seed, near_threshold):
        raise ValueError('Raw CAR35 recipe changed; choose a new dataset version')
    if (raw.get('source_classes') != 107 or
            not re.fullmatch('[a-f0-9]{64}', raw.get('source_zip_sha256', '')) or
            manifest.get('dataset_version') != dataset_version):
        raise ValueError('Invalid raw ZIP provenance')
    if expected_source_sha256 and raw['source_zip_sha256'] != expected_source_sha256.lower():
        raise ValueError('Raw source SHA-256 changed')
    if manifest['settings']['seed'] != seed or manifest['settings']['near_threshold'] != near_threshold:
        raise ValueError('Stored split recipe differs')
    return verify_car35(root)


def _source_entries(archive):
    entries, seen = archive.infolist(), set()
    if len(entries) > 200000 or sum(m.file_size for m in entries) > 64*1024**3:
        raise ValueError('Raw ZIP exceeds preparation limits')
    for member in entries:
        name, path = member.filename, PurePosixPath(member.filename)
        if (not name or path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name or
                name.casefold() in seen or member.flag_bits & 1 or
                (member.external_attr >> 16) & 0o170000 == 0o120000):
            raise ValueError('Unsafe, encrypted or duplicate raw ZIP path')
        seen.add(name.casefold())
    if 'data.yaml' not in seen or archive.getinfo('data.yaml').file_size > 1024**2:
        raise ValueError('Raw ZIP must contain data.yaml at its root')
    config = yaml.safe_load(archive.read('data.yaml'))
    if not isinstance(config, dict): raise ValueError('Invalid raw data.yaml')
    names = config.get('names')
    if isinstance(names, list): names = dict(enumerate(names))
    try:
        normalized = {int(k):v for k,v in names.items()}
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError('Expected a 107-class source catalog') from error
    if (len(names) != 107 or set(normalized) != set(range(107)) or
            config.get('nc', 107) != 107 or any(not isinstance(v,str) or not v for v in normalized.values()) or
            len(set(normalized.values())) != 107 or not set(CAR35) <= set(normalized.values())):
        raise ValueError('Expected a raw 107-class catalog containing all CAR35 names')
    prefixes = tuple(f'{split}/{kind}/' for split in ('train','valid','test') for kind in ('images','labels'))
    for split in ('train','valid','test'):
        for kind in ('images','labels'):
            if not any(not m.is_dir() and m.filename.startswith(f'{split}/{kind}/') for m in entries):
                raise ValueError(f'Missing raw source root: {split}/{kind}')
    expected = dict(train='train/images', val='valid/images', test='test/images')
    if any(config.get(k, v) != v for k,v in expected.items()):
        raise ValueError('Raw YAML paths must use train/valid/test image roots')
    return [m for m in entries if not m.is_dir() and
            (m.filename == 'data.yaml' or m.filename.startswith(prefixes))]


def prepare_raw_car35_zip(source, output, *, dataset_version, seed=42, near_threshold=4,
                          expected_source_sha256='', workers=4, progress=None):
    """Extract to an owned temporary tree, reuse the audited folder pipeline,
    then publish a separately identified dataset. Never edits/deletes source ZIP.
    The historical V4/R3 manifest and patch are not used for this new split.
    """
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists(): raise FileExistsError(output)
    recipe = _recipe(dataset_version, seed, near_threshold)
    if type(workers) is not int or not 1 <= workers <= 32: raise ValueError('workers must be 1..32')
    if expected_source_sha256 and not re.fullmatch('[a-fA-F0-9]{64}', expected_source_sha256):
        raise ValueError('Expected source SHA-256 must contain 64 hexadecimal characters')
    if progress: print('Checking raw ZIP SHA-256...', flush=True)
    actual = digest_file(source)
    if expected_source_sha256 and actual != expected_source_sha256.lower():
        raise ValueError(f'Raw source SHA-256 mismatch: expected {expected_source_sha256}; actual {actual}')
    with zipfile.ZipFile(source) as archive:
        entries = _source_entries(archive)
        output.parent.mkdir(parents=True, exist_ok=True)
        required = 2*sum(m.file_size for m in entries) + 1024**3
        if shutil.disk_usage(output.parent).free < required:
            raise ValueError('Not enough disk space for raw extraction and prepared CAR35')
        with tempfile.TemporaryDirectory(prefix='.raw-car35-', dir=output.parent) as temporary:
            stage = Path(temporary); raw = stage/'source'; raw.mkdir()
            iterator = progress(entries, desc='Extract raw YOLO source', unit='file') if progress else entries
            for member in iterator:
                path = raw/member.filename; path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as reader, path.open('wb') as writer:
                    shutil.copyfileobj(reader, writer, length=1024*1024)
            prepared = stage/'prepared'
            manifest = prepare_folder_dataset(raw, prepared, classes=CAR35, seed=seed,
                near_threshold=near_threshold, workers=workers, progress=progress)
            # Keep repeat runs stable despite the randomly named extraction tree.
            manifest['source_root'] = 'raw_zip_sha256:'+actual
            manifest['dataset_version'] = dataset_version
            manifest['raw_zip_preparation'] = dict(recipe=recipe, source_zip_sha256=actual, source_classes=107)
            manifest['limitations'] += ' Rebuilt from a raw 107-class ZIP; not the historical V4/R3 benchmark. No R3 overlay applied.'
            write_json(prepared/'manifest.json', manifest)
            if progress: print('Verifying all prepared image/label hashes...', flush=True)
            info = verify_raw_car35(prepared, dataset_version=dataset_version, seed=seed,
                near_threshold=near_threshold, expected_source_sha256=actual)
            write_json(prepared/'dataset_report.json', info)
            if digest_file(source) != actual: raise ValueError('Source ZIP changed during preparation')
            if output.exists(): raise FileExistsError(output)
            prepared.rename(output)
    return info
