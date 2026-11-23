"""Raw 107-class ZIP input, temporary files and synthetic images only."""
import hashlib
import importlib
import json
from pathlib import Path
import random
from zipfile import ZipFile, ZipInfo

from PIL import Image, PngImagePlugin
import pytest
import yaml

from training.data.common import CAR35, digest_file


def api():
    return importlib.import_module('training.data.raw_car35')


def raw_fixture(root, *, duplicate=False, negative=False):
    root.mkdir()
    names = ['No_trucks', *CAR35, *[f'Extra_{i}' for i in range(71)]]
    (root/'data.yaml').write_text(yaml.safe_dump(dict(path='.', train='train/images',
        val='valid/images', test='test/images', nc=107, names=dict(enumerate(names)))))
    for i in range(12):
        split = ('train', 'valid', 'test')[i % 3]
        images, labels = root/split/'images', root/split/'labels'
        images.mkdir(parents=True, exist_ok=True); labels.mkdir(parents=True, exist_ok=True)
        rng = random.Random(i)
        Image.frombytes('RGB', (32,24), bytes(rng.randrange(256) for _ in range(32*24*3))).save(images/f'{i}.png')
        lines = '0 .8 .8 .1 .1\n'
        if not negative or i:
            lines += ''.join(f'{c} .5 .5 .2 .2\n' for c in range(1,36))
        (labels/f'{i}.txt').write_text(lines)
    if duplicate:
        original = root/'train/images/0.png'
        (root/'test/images/exact.png').write_bytes(original.read_bytes())
        label = (root/'train/labels/0.txt').read_bytes()
        (root/'test/labels/exact.txt').write_bytes(label)
        metadata = PngImagePlugin.PngInfo(); metadata.add_text('copy','same scene')
        with Image.open(original) as image:
            image.save(root/'valid/images/reencoded.png', pnginfo=metadata)
        (root/'valid/labels/reencoded.txt').write_bytes(label)
    archive = root.parent/'raw107.zip'
    with ZipFile(archive, 'w') as zip_file:
        for path in sorted(root.rglob('*')):
            if path.is_file(): zip_file.write(path, path.relative_to(root).as_posix())
    return archive


def test_raw_zip_filters_and_remaps_all_35_classes_without_changing_source(tmp_path):
    source = raw_fixture(tmp_path/'raw', negative=True)
    before = digest_file(source)
    out = tmp_path/'prepared'
    info = api().prepare_raw_car35_zip(source, out, dataset_version='raw107_test_v1', near_threshold=None)
    assert info['images'] == 12 and info['boxes'] == 11*35
    assert info['names'] == CAR35 and info['dataset_version'] == 'raw107_test_v1'
    manifest = json.loads((out/'manifest.json').read_text())
    assert manifest['raw_zip_preparation']['source_classes'] == 107
    assert manifest['raw_zip_preparation']['source_zip_sha256'] == before
    assert manifest['negative_images'] == 1
    assert set(info['split_images']) == {'train','val','test'}
    assert digest_file(source) == before
    assert not list(tmp_path.glob('.raw-car35-*'))
    labels = [p.read_text() for p in (out/'labels').rglob('*.txt') if p.read_text().strip()]
    assert all({int(line.split()[0]) for line in label.splitlines()} == set(range(35)) for label in labels)


def test_duplicates_and_related_scenes_never_cross_new_splits(tmp_path):
    source = raw_fixture(tmp_path/'raw', duplicate=True)
    out = tmp_path/'prepared'
    api().prepare_raw_car35_zip(source, out, dataset_version='raw107_test_v1')
    manifest = json.loads((out/'manifest.json').read_text())
    assert manifest['duplicates_removed'] == 1
    related = [r for r in manifest['images'] if any(a.endswith(('/0.png','/reencoded.png')) for a in r['aliases'])]
    assert len(related) == 2
    assert len({r['group'] for r in related}) == len({r['split'] for r in related}) == 1


@pytest.mark.parametrize('attack', ['traversal','duplicate','symlink','wrong_classes'])
def test_unsafe_or_wrong_source_is_rejected_before_publishing(tmp_path, attack):
    source = raw_fixture(tmp_path/'raw')
    with ZipFile(source, 'a') as archive:
        if attack == 'traversal': archive.writestr('../escape.txt', 'bad')
        elif attack == 'duplicate':
            with pytest.warns(UserWarning): archive.writestr('data.yaml','bad')
        elif attack == 'symlink':
            item=ZipInfo('train/images/link.png');item.create_system=3;item.external_attr=0o120777<<16
            archive.writestr(item,'/etc/passwd')
    if attack == 'wrong_classes':
        source=tmp_path/'wrong.zip'
        with ZipFile(source,'w') as archive: archive.writestr('data.yaml',yaml.safe_dump(dict(names=CAR35,nc=35)))
    with pytest.raises(ValueError): api().prepare_raw_car35_zip(source,tmp_path/'out',dataset_version='raw107_test_v1')
    assert not (tmp_path/'out').exists() and not (tmp_path/'escape.txt').exists()


def test_checksum_disk_and_existing_output_guards(tmp_path, monkeypatch):
    from types import SimpleNamespace
    source=raw_fixture(tmp_path/'raw')
    with pytest.raises(ValueError, match='SHA-256'):
        api().prepare_raw_car35_zip(source,tmp_path/'bad',dataset_version='v1',expected_source_sha256='0'*64)
    module=api()
    monkeypatch.setattr(module.shutil,'disk_usage',lambda p:SimpleNamespace(free=0))
    with pytest.raises(ValueError, match='disk space'):
        module.prepare_raw_car35_zip(source,tmp_path/'bad',dataset_version='v1')
    out=tmp_path/'mine';out.mkdir();(out/'keep').write_text('mine')
    with pytest.raises(FileExistsError):module.prepare_raw_car35_zip(source,out,dataset_version='v1')
    assert (out/'keep').read_text() == 'mine'


def test_repeated_preparation_is_stable_and_cache_rejects_changed_recipe_or_labels(tmp_path):
    source=raw_fixture(tmp_path/'raw')
    a=api().prepare_raw_car35_zip(source,tmp_path/'a',dataset_version='v1',near_threshold=None)
    b=api().prepare_raw_car35_zip(source,tmp_path/'b',dataset_version='v1',near_threshold=None)
    assert a['manifest_sha256'] == b['manifest_sha256']
    with pytest.raises(ValueError,match='recipe'):
        api().verify_raw_car35(tmp_path/'a',dataset_version='v1',seed=43,near_threshold=None)
    path=next((tmp_path/'a/labels').rglob('*.txt'));path.write_text('0 .5 .5 .1 .1\n')
    with pytest.raises(ValueError,match='hash changed'):
        api().verify_raw_car35(tmp_path/'a',dataset_version='v1',near_threshold=None)
