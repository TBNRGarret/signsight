"""Real-file synthetic fixtures for the downloaded-folder CAR35 preparation."""
import importlib
import importlib.util
import json
import random
from pathlib import Path
import subprocess
import sys

from PIL import Image, PngImagePlugin
import pytest
import yaml


def api():
    return importlib.import_module('training.data.folder_dataset')


def fixture(root):
    root.mkdir()
    (root/'data.yaml').write_text(yaml.safe_dump(dict(names=['No_trucks', 'No_entry', 'No_parking'])))
    for i in range(18):
        split = ('train', 'valid', 'test')[i % 3]
        images, labels = root/split/'images', root/split/'labels'
        images.mkdir(parents=True, exist_ok=True); labels.mkdir(parents=True, exist_ok=True)
        rng = random.Random(i)
        image = Image.frombytes('RGB', (32, 24), bytes(rng.randrange(256) for _ in range(32*24*3)))
        image.save(images/f'{i}.png')
        (labels/f'{i}.txt').write_text('1 .5 .5 .4 .4\n2 .2 .2 .1 .1\n0 .8 .8 .1 .1\n')
    return root


def prepare(source, output, **kwargs):
    return api().prepare_folder_dataset(source, output, classes=['No_parking', 'No_entry'], **kwargs)


def test_filter_remaps_labels_and_never_scans_unrelated_workspace_images(tmp_path):
    source = fixture(tmp_path/'raw')
    (source/'unrelated').mkdir()
    Image.new('RGB', (10, 10)).save(source/'unrelated'/'secret.png')
    original = (source/'train/labels/0.txt').read_bytes()
    manifest = prepare(source, tmp_path/'prepared', near_threshold=None)
    assert manifest['source_summary']['images_scanned'] == 18
    assert manifest['names'] == ['No_parking', 'No_entry']
    assert len(manifest['images']) == 18
    assert len({r['group'] for r in manifest['images']}) == 18
    assert {r['split'] for r in manifest['images']} == {'train', 'val', 'test'}
    for row in manifest['images']:
        lines = (tmp_path/'prepared'/row['label']).read_text().splitlines()
        assert {int(line.split()[0]) for line in lines} == {0, 1}
        assert len(lines) == 2
    assert (source/'train/labels/0.txt').read_bytes() == original
    assert api().verify_folder_dataset(tmp_path/'prepared')['images'] == 18


def test_duplicate_label_conflict_in_out_of_scope_class_is_quarantined(tmp_path):
    source = fixture(tmp_path/'raw')
    same = source/'train/images/0.png'
    (source/'test/images/conflict.png').write_bytes(same.read_bytes())
    (source/'test/labels/conflict.txt').write_text('1 .5 .5 .4 .4\n2 .2 .2 .1 .1\n')
    manifest = prepare(source, tmp_path/'prepared', near_threshold=None)
    assert len(manifest['images']) == 17
    excluded = {r['source_path']: r['reason'] for r in manifest['excluded']}
    assert excluded['train/images/0.png'] == 'conflicting_duplicate_labels'
    assert excluded['test/images/conflict.png'] == 'conflicting_duplicate_labels'


def test_exact_copies_are_deduplicated_and_visual_copies_share_a_split(tmp_path):
    source = fixture(tmp_path/'raw')
    original = source/'train/images/0.png'
    (source/'test/images/exact.png').write_bytes(original.read_bytes())
    (source/'test/labels/exact.txt').write_bytes((source/'train/labels/0.txt').read_bytes())
    metadata = PngImagePlugin.PngInfo(); metadata.add_text('variant', 'same pixels, different file')
    with Image.open(original) as image:
        image.save(source/'valid/images/reencoded.png', pnginfo=metadata)
    (source/'valid/labels/reencoded.txt').write_bytes((source/'train/labels/0.txt').read_bytes())
    manifest = prepare(source, tmp_path/'prepared')
    assert manifest['duplicates_removed'] == 1
    assert len(manifest['images']) == 19
    rows = [r for r in manifest['images'] if any(a.endswith('/0.png') or a.endswith('/reencoded.png') for a in r['aliases'])]
    assert len(rows) == 2
    assert len({r['group'] for r in rows}) == len({r['split'] for r in rows}) == 1


def test_missing_invalid_labels_are_excluded_but_selected_taxonomy_negatives_remain(tmp_path):
    source = fixture(tmp_path/'raw')
    (source/'train/labels/0.txt').unlink()
    (source/'valid/labels/1.txt').write_text('1 .5 .5 -1 .2\n')
    (source/'test/labels/2.txt').write_text('0 .5 .5 .2 .2\n')
    (source/'train/labels/3.txt').write_text('')
    manifest = prepare(source, tmp_path/'prepared', near_threshold=None)
    assert len(manifest['images']) == 16
    assert len(manifest['excluded']) == 2
    assert manifest['negative_images'] == 2
    assert manifest['independent_field_test'] is False
    assert manifest['split_provenance'] == 'dhash_development_groups'


def test_splits_are_repeatable_and_single_group_class_stays_in_train(tmp_path):
    source = fixture(tmp_path/'raw')
    for path in source.glob('*/labels/*.txt'):
        if path.stem != '0': path.write_text('1 .5 .5 .4 .4\n')
    a = prepare(source, tmp_path/'a', near_threshold=None)
    b = prepare(source, tmp_path/'b', near_threshold=None)
    assert [(r['sha256'],r['split']) for r in a['images']] == [(r['sha256'],r['split']) for r in b['images']]
    rare = next(r for r in a['images'] if r['source_path'] == 'train/images/0.png')
    assert rare['split'] == 'train'
    assert a['missing_classes']['val'] == a['missing_classes']['test'] == ['No_parking']


@pytest.mark.parametrize('target', ['raw', 'raw/train', 'raw/test/images/child'])
def test_rejects_output_inside_source_before_writing(tmp_path, target):
    source = fixture(tmp_path/'raw')
    with pytest.raises((ValueError, FileExistsError)):
        prepare(source, tmp_path/target)
    assert (source/'train/images/0.png').is_file()


def test_verifier_rejects_label_changes_and_added_images(tmp_path):
    source = fixture(tmp_path/'raw')
    manifest = prepare(source, tmp_path/'prepared', near_threshold=None)
    row = manifest['images'][0]
    label = tmp_path/'prepared'/row['label']; saved = label.read_bytes()
    label.write_text('0 .5 .5 .1 .1\n')
    with pytest.raises(ValueError, match='changed|hash'):
        api().verify_folder_dataset(tmp_path/'prepared')
    label.write_bytes(saved)
    extra = tmp_path/'prepared'/Path(row['image']).parent/'extra.png'
    extra.write_bytes((tmp_path/'prepared'/row['image']).read_bytes())
    with pytest.raises(ValueError, match='inventory'):
        api().verify_folder_dataset(tmp_path/'prepared')


def test_refuses_existing_output_without_overwriting(tmp_path):
    source = fixture(tmp_path/'raw')
    output = tmp_path/'prepared'; output.mkdir(); (output/'keep.txt').write_text('mine')
    with pytest.raises(FileExistsError): prepare(source, output)
    assert (output/'keep.txt').read_text() == 'mine'


def test_training_consumer_resolves_dataset_after_moving_and_changing_cwd(tmp_path, monkeypatch):
    if importlib.util.find_spec('ultralytics') is None:
        pytest.skip('Optional training consumer is not installed')
    source = fixture(tmp_path/'raw')
    prepare(source, tmp_path/'prepared', near_threshold=None)
    moved = tmp_path/'moved'
    (tmp_path/'prepared').rename(moved)
    # Ultralytics monkey-patches Pillow/Torch on import. Isolate that optional
    # consumer so the backend's synthetic inference suite keeps its own runtime.
    script = '''import sys, json, torch
import ultralytics.data.utils as utils
utils.check_font = lambda *a, **kw: None
result = utils.check_det_dataset(sys.argv[1], autodownload=False)
print(json.dumps({s:result[s] for s in ('train','val','test')}))
'''
    run = subprocess.run([sys.executable,'-c',script,str(moved/'data.yaml')],
                         cwd=tmp_path,check=True,capture_output=True,text=True,timeout=90)
    result = json.loads(run.stdout.splitlines()[-1])
    assert Path(result['train']) == moved/'images/train'
    assert Path(result['val']) == moved/'images/val'
    assert Path(result['test']) == moved/'images/test'


def test_group_split_keeps_dominant_rare_class_group_for_learning():
    rows = [dict(group='rare-scene',lines=['0 .5 .5 .2 .2','1 .5 .5 .2 .2']) for _ in range(216)]
    rows += [dict(group=f'rare-{i}',lines=['1 .5 .5 .2 .2']) for i in range(3)]
    rows += [dict(group=f'common-{i}',lines=['0 .5 .5 .2 .2']) for i in range(600)]
    counts, missing = api().choose_folder_splits(rows, ['common','rare'], 42)
    assert counts['train'][1] == 216
    assert counts['val'][1] and counts['test'][1]
    assert not any(missing.values())
    assert len({r['split'] for r in rows if r['group']=='rare-scene'}) == 1
    assert {r['split'] for r in rows if r['group']=='rare-scene'} == {'train'}
    sizes = {s:sum(r['split']==s for r in rows) for s in ('train','val','test')}
    assert abs(sizes['train']/len(rows)-.7) < .02
    assert abs(sizes['val']/len(rows)-.15) < .02
    assert abs(sizes['test']/len(rows)-.15) < .02
