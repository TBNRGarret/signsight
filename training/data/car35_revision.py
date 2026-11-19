"""Materialize reviewed labels from an immutable V4 ZIP into a new development dataset."""
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import zipfile

from training.data.common import CAR35, SPLITS, digest_file, write_json
from training.data.car35_bundle import restore_car35_bundle, verify_car35
from training.data.label_patch import create_label_patch


REVISION_KIND = 'car35_reviewed_development_v1'


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('Invalid revision SHA-256')
    return value


def _version(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', value):
        raise ValueError('Supply a safe, separately identified dataset version')
    return value


def revision_manifest(source, patch, *, source_sha, patch_document_sha, patch_archive_sha, dataset_version):
    """Deterministic identity; preserve every source image, group and split."""
    _version(dataset_version)
    for value in (source_sha, patch_document_sha, patch_archive_sha): _sha(value)
    if (source.get('kind') != 'car35_folder_development_v4' or source.get('names') != CAR35 or
            source.get('independent_field_test') is not False or
            patch.get('kind') != 'car35_reviewed_label_patch' or patch.get('schema_version') != 2 or
            patch.get('source_manifest_sha256') != source_sha or patch.get('names') != CAR35 or
            patch.get('split_changed') is not False or patch.get('independent_field_test') is not False):
        raise ValueError('Invalid revision source/patch provenance')
    result = deepcopy(source)
    rows = {r['sha256']:r for r in result['images']}
    counts = {s:Counter({int(k):v for k,v in source['class_counts'][s].items()}) for s in SPLITS}
    seen, edited, removed, changed = set(), set(), 0, 0
    changes = patch.get('changes', [])
    if not changes or len(changes) != patch.get('changed_images'):
        raise ValueError('Invalid patch image inventory')
    for item in changes:
        sha = item['image_sha256'];row = rows.get(sha)
        if (row is None or sha in seen or item['split'] != row['split'] or item['label'] != row['label'] or
                item['old_sha256'] != row['label_sha256']):
            raise ValueError('Patch differs from source revision inventory')
        seen.add(sha);row['label_sha256'] = _sha(item['new_sha256'])
        if not item.get('edits'): raise ValueError('Patch has no reviewed edits')
        for edit in item['edits']:
            index = edit.get('line_index');before,after = edit.get('from_class'),edit.get('to_class')
            action = edit.get('action')
            if (edit.get('image_sha256') != sha or edit.get('reviewed') is not True or
                    type(index) is not int or index < 0 or (sha,index) in edited or
                    any(type(c) is not int or not 0 <= c < 35 for c in (before,after)) or
                    action not in ('replace_class','remove_duplicate') or
                    not isinstance(edit.get('reason'),str) or not edit['reason'].strip()):
                raise ValueError('Invalid reviewed revision edit')
            edited.add((sha,index));counts[row['split']][before] -= 1
            if action == 'replace_class':
                counts[row['split']][after] += 1;changed += 1
            else:
                removed += 1
    if (patch.get('removed_boxes') != removed or patch.get('relabeled_boxes') != changed or
            patch.get('changed_boxes') != removed+changed or
            any(v < 0 for c in counts.values() for v in c.values())):
        raise ValueError('Patch revision counts are inconsistent')
    result.update(kind=REVISION_KIND, dataset_version=dataset_version,
        class_counts={s:{str(c):n for c,n in sorted(counts[s].items()) if n} for s in SPLITS},
        missing_classes={s:[name for c,name in enumerate(CAR35) if not counts[s][c]] for s in SPLITS},
        label_revision=dict(schema_version=1, source_manifest_sha256=source_sha,
            patch_document_sha256=patch_document_sha, patch_archive_sha256=patch_archive_sha,
            changed_images=len(changes), relabeled_boxes=changed, removed_boxes=removed,
            split_changed=False, validation_labels_changed=any(c['split']=='val' for c in changes),
            test_labels_changed=any(c['split']=='test' for c in changes)),
        limitations=source.get('limitations','Development split; scene overlap may remain.')+
            ' Reviewed label revision; image/group/split membership is unchanged. '
            'Changed validation/test labels change the evaluation reference. Not an independent field test.')
    return result


def validate_revision_provenance(root, manifest):
    root = Path(root)
    original, patch = root/'provenance/v4_manifest.json', root/'provenance/label_patch.json'
    if any(p.is_symlink() or not p.resolve().is_relative_to(root.resolve()) for p in (original,patch)):
        raise ValueError('Unsafe revision provenance path')
    revision = manifest['label_revision']
    if (digest_file(original) != revision['source_manifest_sha256'] or
            digest_file(patch) != revision['patch_document_sha256']):
        raise ValueError('Revision provenance hash changed')
    expected = revision_manifest(json.loads(original.read_text(encoding='utf-8')),
        json.loads(patch.read_text(encoding='utf-8')), source_sha=revision['source_manifest_sha256'],
        patch_document_sha=revision['patch_document_sha256'], patch_archive_sha=revision['patch_archive_sha256'],
        dataset_version=manifest['dataset_version'])
    if expected != manifest:
        raise ValueError('Revision manifest differs from source/patch provenance')


@contextmanager
def _patch_directory(archive, expected_sha256, parent=None):
    archive = Path(archive).resolve()
    if digest_file(archive) != _sha(expected_sha256): raise ValueError('Patch ZIP checksum mismatch')
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist();seen = set()
        if len(entries) > 10000 or sum(m.file_size for m in entries) > 64*1024**2:
            raise ValueError('Patch ZIP exceeds labels-only size limit')
        for member in entries:
            name = member.filename;relative = PurePosixPath(name)
            if (not name or relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name or
                    name.casefold() in seen or member.flag_bits&1 or
                    (member.external_attr>>16)&0o170000 == 0o120000):
                raise ValueError('Unsafe or duplicate patch ZIP path')
            seen.add(name.casefold())
        if 'patch.json' not in seen or source.getinfo('patch.json').file_size > 1024**2:
            raise ValueError('Missing or oversized patch.json')
        with tempfile.TemporaryDirectory(prefix='.car35-patch-',dir=parent) as temporary:
            root = Path(temporary)
            for member in entries:
                if member.is_dir(): continue
                target = root/member.filename;target.parent.mkdir(parents=True,exist_ok=True)
                with source.open(member) as stream,target.open('wb') as dest: shutil.copyfileobj(stream,dest)
            yield root


def _prepare_revision(root, patch_root, *, source_sha, patch_sha, dataset_version):
    raw = (root/'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != _sha(source_sha): raise ValueError('Source manifest SHA-256 mismatch')
    patch_raw = (patch_root/'patch.json').read_bytes();patch = json.loads(patch_raw)
    with tempfile.TemporaryDirectory(prefix='.replay-patch-',dir=patch_root.parent) as temporary:
        replay_root = Path(temporary)/'replayed'
        edits = [edit for item in patch['changes'] for edit in item['edits']]
        replay = create_label_patch(root,replay_root,edits,expected_manifest_sha256=source_sha)
        if replay != patch: raise ValueError('Patch metadata differs from reviewed edit replay')
        expected_labels = {item['label'] for item in replay['changes']}
        if {p.relative_to(patch_root).as_posix() for p in (patch_root/'labels').rglob('*') if p.is_file()} != expected_labels:
            raise ValueError('Patch label inventory differs from reviewed edits')
        for name in expected_labels:
            if (replay_root/name).read_bytes() != (patch_root/name).read_bytes():
                raise ValueError('Patch label bytes differ from reviewed edit replay')
    manifest = revision_manifest(json.loads(raw),patch,source_sha=source_sha,
        patch_document_sha=hashlib.sha256(patch_raw).hexdigest(), patch_archive_sha=patch_sha,
        dataset_version=dataset_version)
    manifest_bytes = json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8')
    return manifest,manifest_bytes,raw,patch_raw


def preview_car35_revision(root, patch_archive, *, expected_source_manifest_sha256,
                           expected_patch_sha256, dataset_version):
    """Verify source/patch read-only and predict the exact new manifest checksum."""
    root = Path(root).resolve();_version(dataset_version)
    verify_car35(root,expected_manifest_sha256=expected_source_manifest_sha256)
    with _patch_directory(patch_archive,expected_patch_sha256) as patch_root:
        manifest,raw,_,_ = _prepare_revision(root,patch_root,source_sha=expected_source_manifest_sha256,
            patch_sha=expected_patch_sha256,dataset_version=dataset_version)
    return dict(manifest=manifest,manifest_sha256=hashlib.sha256(raw).hexdigest(),
        images=len(manifest['images']),boxes=sum(sum(c.values()) for c in manifest['class_counts'].values()),
        dataset_version=dataset_version,materialized=False)


def restore_car35_revision(archive, patch_archive, output, *, expected_sha256,
        expected_source_manifest_sha256, expected_patch_sha256, dataset_version, expected_manifest_sha256=''):
    """Restore once into owned staging, replay reviewed edits, verify, then publish."""
    output = Path(output).resolve();_version(dataset_version)
    if output.exists(): raise FileExistsError(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with _patch_directory(patch_archive,expected_patch_sha256,output.parent) as patch_root:
        with tempfile.TemporaryDirectory(prefix='.car35-revision-',dir=output.parent) as temporary:
            stage = Path(temporary)/'dataset'
            restore_car35_bundle(archive,stage,expected_sha256=expected_sha256,
                                 expected_manifest_sha256=expected_source_manifest_sha256)
            manifest,raw,original,patch_raw = _prepare_revision(stage,patch_root,
                source_sha=expected_source_manifest_sha256,patch_sha=expected_patch_sha256,dataset_version=dataset_version)
            if expected_manifest_sha256 and hashlib.sha256(raw).hexdigest()!=expected_manifest_sha256:
                raise ValueError('Revised manifest SHA-256 mismatch')
            provenance = stage/'provenance';provenance.mkdir()
            (provenance/'v4_manifest.json').write_bytes(original)
            (provenance/'label_patch.json').write_bytes(patch_raw)
            # Keep historical previews/reports explicitly separate from revised labels.
            historical = provenance/'v4_reports';historical.mkdir()
            for name in ('README.md','report.html','dataset_report.json','previews'):
                if (stage/name).exists(): (stage/name).rename(historical/name)
            for item in json.loads(patch_raw)['changes']:
                shutil.copyfile(patch_root/item['label'],stage/item['label'])
            for split in SPLITS:
                for suffix in ('.cache','.cache.npy'): (stage/'labels'/(split+suffix)).unlink(missing_ok=True)
            (stage/'manifest.json').write_bytes(raw)
            with (stage/'class_counts.csv').open('w',newline='',encoding='utf-8-sig') as stream:
                writer=csv.DictWriter(stream,fieldnames=['class_id','name',*SPLITS]);writer.writeheader()
                for i,name in enumerate(CAR35):
                    writer.writerow(dict(class_id=i,name=name,**{s:manifest['class_counts'][s].get(str(i),0) for s in SPLITS}))
            (stage/'README.md').write_text('# '+dataset_version+'\n\nReviewed label revision of CAR35 V4. '
                'Images/groups/splits are unchanged; historical reports are under provenance/v4_reports. '
                'Changed holdout labels change the evaluation reference. Not an independent field test.\n',encoding='utf-8')
            info=verify_car35(stage,expected_manifest_sha256=hashlib.sha256(raw).hexdigest())
            write_json(stage/'dataset_report.json',info)
            if output.exists(): raise FileExistsError(output)
            stage.rename(output)
    return info


def pack_car35_revision(root, target):
    root,target = Path(root).resolve(),Path(target).resolve()
    if target.is_relative_to(root) or root.is_relative_to(target): raise ValueError('ZIP must be outside dataset')
    sidecar=target.with_suffix(target.suffix+'.sha256')
    if target.exists() or sidecar.exists(): raise FileExistsError(target)
    info=verify_car35(root)
    if info['kind'] != REVISION_KIND: raise ValueError('Expected a reviewed CAR35 revision')
    caches={root/'labels'/(s+suffix) for s in SPLITS for suffix in ('.cache','.cache.npy')}
    paths=sorted(p for p in root.rglob('*') if p.is_file() and p not in caches)
    if any(p.is_symlink() or not p.resolve().is_relative_to(root) for p in paths): raise ValueError('Unsafe revision file')
    target.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(target.parent).free < sum(p.stat().st_size for p in paths)+1024**3:
        raise ValueError('Not enough disk space to pack CAR35 revision')
    with tempfile.TemporaryDirectory(prefix='.pack-revision-',dir=target.parent) as temporary:
        archive=Path(temporary)/'dataset.zip'
        with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_STORED,allowZip64=True) as dest:
            for path in paths: dest.write(path,path.relative_to(root).as_posix())
        checksum=digest_file(archive)
        if target.exists(): raise FileExistsError(target)
        archive.rename(target)
    sidecar.write_text(checksum+'\n',encoding='utf-8')
    return dict(info,zip_sha256=checksum)
