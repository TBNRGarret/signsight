"""Container bytes may change; trusted manifest and all dataset bytes may not."""
import hashlib
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

from test_car35_handoff import fixture, data_api


def repack(source, target, *, changed=None):
    with ZipFile(source) as original, ZipFile(target, 'w', compression=ZIP_DEFLATED) as archive:
        for name in original.namelist():
            archive.writestr(name, changed.get(name, original.read(name)) if changed else original.read(name))
    return target


def test_repacked_archive_requires_opt_in_and_a_pinned_manifest(tmp_path):
    _, original, checksum, manifest_sha = fixture(tmp_path)
    archive = repack(original, tmp_path/'repacked.zip')
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert actual != checksum
    inspect = data_api().inspect_car35_archive
    with pytest.raises(ValueError, match='ZIP SHA-256 mismatch'):
        inspect(archive, expected_sha256=checksum, expected_manifest_sha256=manifest_sha)
    identity = inspect(archive, expected_sha256=checksum,
                       expected_manifest_sha256=manifest_sha, allow_repacked=True)
    assert identity == dict(archive_sha256=actual, expected_archive_sha256=checksum,
                           manifest_sha256=manifest_sha, repacked=True)
    result = data_api().restore_car35_bundle(archive, tmp_path/'restored',
        expected_sha256=identity['archive_sha256'], expected_manifest_sha256=manifest_sha)
    assert result['images'] == 3 and result['boxes'] == 105


def test_repacking_never_adopts_an_unknown_or_changed_manifest(tmp_path):
    _, original, checksum, manifest_sha = fixture(tmp_path)
    archive = repack(original, tmp_path/'other.zip', changed={'manifest.json': b'{}'})
    with pytest.raises(ValueError, match='manifest SHA-256 mismatch'):
        data_api().inspect_car35_archive(archive, expected_sha256=checksum,
            expected_manifest_sha256=manifest_sha, allow_repacked=True)
    with pytest.raises(ValueError, match='manifest SHA-256'):
        data_api().inspect_car35_archive(original, expected_sha256=checksum,
            expected_manifest_sha256='', allow_repacked=True)


def test_same_manifest_does_not_let_tampered_images_reach_training(tmp_path):
    root, original, checksum, manifest_sha = fixture(tmp_path)
    image = next((root/'images/train').iterdir()).relative_to(root).as_posix()
    archive = repack(original, tmp_path/'tampered.zip', changed={image: b'changed image'})
    identity = data_api().inspect_car35_archive(archive, expected_sha256=checksum,
        expected_manifest_sha256=manifest_sha, allow_repacked=True)
    with pytest.raises(ValueError, match='image/label hash changed'):
        data_api().restore_car35_bundle(archive, tmp_path/'restored',
            expected_sha256=identity['archive_sha256'], expected_manifest_sha256=manifest_sha)
    assert not (tmp_path/'restored').exists()


def test_exact_archive_still_requires_the_expected_manifest(tmp_path):
    _, archive, checksum, manifest_sha = fixture(tmp_path)
    identity = data_api().inspect_car35_archive(archive, expected_sha256=checksum,
        expected_manifest_sha256=manifest_sha)
    assert identity['repacked'] is False
    with pytest.raises(ValueError, match='manifest SHA-256 mismatch'):
        data_api().inspect_car35_archive(archive, expected_sha256=checksum,
            expected_manifest_sha256='0'*64)


@pytest.mark.parametrize('stage', ['eda', 'train'])
def test_notebook_restores_repacked_source_and_records_actual_archive_identity(tmp_path, monkeypatch, stage):
    import os
    import shutil
    import sys
    from training.notebooks.car35 import build_car35_eda_notebook, build_car35_train_notebook
    from test_supsign_training import clear_embedded_modules
    _, original, checksum, manifest_sha = fixture(tmp_path)
    archive = repack(original, tmp_path/'repacked.zip')
    notebook = build_car35_eda_notebook() if stage == 'eda' else build_car35_train_notebook()
    cells = {c['id']: ''.join(c['source']) for c in notebook['cells'] if c['cell_type'] == 'code'}
    work = tmp_path/'runtime'
    clear_embedded_modules(monkeypatch)
    context = dict(sys=sys, os=os)
    exec(cells['config'].replace("Path('/content/signsight_car35')", f'Path({str(work)!r})'), context)
    context.update(SOURCE_URL='synthetic-source-id', APPLY_REVIEWED_PATCH=False,
                   DATASET_SHA256=checksum, EXPECTED_MANIFEST_SHA256=manifest_sha)
    exec(cells['pipeline'], context)
    def transport(source, target, **kwargs):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(archive, target)
        return target
    context['download_drive_zip'] = transport
    exec(cells['prepare'], context)
    assert context['dataset_info']['manifest_sha256'] == manifest_sha
    receipt = context['json'].loads((work/'source_archive_verification.json').read_text())
    assert receipt['repacked'] is True
    assert receipt['expected_archive_sha256'] == checksum
    assert receipt['archive_sha256'] == hashlib.sha256(archive.read_bytes()).hexdigest()
