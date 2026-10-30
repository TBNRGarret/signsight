"""Synthetic-only regression tests for the standalone SupSign training notebook."""
import ast
import hashlib
import io
import json
from pathlib import Path
import zipfile

import pytest
from PIL import Image
import yaml

from scripts.supsign_training import (
    CAR35, prepare_supsign, verify_dataset, pack_dataset, restore_dataset,
    train_experiment, evaluate_checkpoint,
)


def split_fixture(groups):
    return [dict(group=group, lines=[f'{c} .5 .5 .2 .2' for c in classes])
            for group, size, classes in groups for _ in range(size)]


def test_split_keeps_a_class_confined_to_second_largest_group_in_train():
    from scripts.supsign_training import choose_splits
    rows = split_fixture([('a', 12, [0]), ('b', 8, [0, 1]), ('c', 4, [0]), ('d', 2, [0])])
    counts, missing = choose_splits(rows, ['common', 'rare'], 42)
    assert counts['train'][1] == 8
    assert not missing['train']
    assert missing['val'] == missing['test'] == ['rare']
    assert {r['split'] for r in rows} == {'train', 'val', 'test'}
    for group in {r['group'] for r in rows}:
        assert len({r['split'] for r in rows if r['group'] == group}) == 1


def test_split_reserves_compatible_holdouts_when_two_groups_are_required_for_a_class():
    from scripts.supsign_training import choose_splits
    rows = split_fixture([('a', 10, [0]), ('b', 8, [1]), ('c', 6, [1]), ('d', 4, [0])])
    original = json.loads(json.dumps(rows))
    counts, missing = choose_splits(rows, ['A', 'B'], 42)
    assert not missing['train'] and counts['train'][0] and counts['train'][1]
    assert {r['split'] for r in rows} == {'train', 'val', 'test'}
    choose_splits(original, ['A', 'B'], 42)
    assert rows == original


def test_impossible_group_coverage_is_reported_without_breaking_groups():
    from scripts.supsign_training import choose_splits
    rows = split_fixture([('a', 3, [0]), ('b', 2, [1]), ('c', 1, [2])])
    with pytest.raises(ValueError, match='train.*coverage'):
        choose_splits(rows, ['A', 'B', 'C'], 42)
    assert all('split' not in row for row in rows)


@pytest.mark.parametrize('tamper', [False, True])
def test_recover_failed_group_split_reuses_audit_and_grouping(tmp_path, monkeypatch, tamper):
    import scripts.supsign_training as training
    source = archive_fixture(tmp_path)
    output = tmp_path/'recovered'
    splitter = training.choose_splits
    def old_split(*args): raise ValueError('Missing train classes after grouping')
    monkeypatch.setattr(training, 'choose_splits', old_split)
    with pytest.raises(ValueError) as caught:
        training.prepare_supsign(source, output, classes=['No_entry', 'No_parking'],
                                 block_size=1, near_threshold=None)
    monkeypatch.setattr(training, 'choose_splits', splitter)
    def forbidden(*args, **kwargs): raise AssertionError('Must reuse the completed audit/grouping')
    monkeypatch.setattr(training, 'audit_dataset', forbidden)
    monkeypatch.setattr(training, 'cluster_records', forbidden)
    if tamper:
        with zipfile.ZipFile(source) as archive:
            entries = {name: archive.read(name) for name in archive.namelist()}
        entries['train/labels/photo_0.txt'] = b'1 .5 .5 .2 .2\n'
        with zipfile.ZipFile(source, 'w') as archive:
            for name, value in entries.items(): archive.writestr(name, value)
        with pytest.raises(ValueError, match='Source ZIP changed'):
            training.recover_failed_preparation(caught.value.__traceback__)
        assert not output.exists()
        return
    manifest = training.recover_failed_preparation(caught.value.__traceback__)
    assert not manifest['missing_classes']['train']
    assert training.verify_dataset(output)['images'] == 18
    assert source.is_file()
    with pytest.raises(FileExistsError):
        training.recover_failed_preparation(caught.value.__traceback__)


def test_recovery_requires_a_completed_prepare_frame():
    from scripts.supsign_training import recover_failed_preparation
    with pytest.raises(ValueError, match='traceback'):
        recover_failed_preparation(None)


def test_split_feasibility_matches_independent_small_group_search():
    import random
    from itertools import combinations
    from scripts.supsign_training import choose_splits
    for seed in range(40):
        rng = random.Random(seed)
        groups = [(str(i), rng.randint(1, 9), [c for c in range(4) if rng.random() < .5])
                  for i in range(rng.randint(3, 9))]
        for c in range(4):
            if not any(c in labels for _, _, labels in groups): groups[c % len(groups)][2].append(c)
        feasible = any(set().union(*(set(labels) for key, _, labels in groups if key not in pair)) == set(range(4))
                       for pair in combinations([key for key,_,_ in groups], 2))
        rows = split_fixture(groups)
        if not feasible:
            with pytest.raises(ValueError, match='coverage'): choose_splits(rows, list('ABCD'), seed)
        else:
            counts, missing = choose_splits(rows, list('ABCD'), seed)
            assert not missing['train']
            assert {row['split'] for row in rows} == set(('train','val','test'))
            assert all(counts['train'][c] > 0 for c in range(4))


def image_bytes(index):
    # Visually distinct deterministic texture, not a live dataset photo.
    import random
    randomizer = random.Random(index)
    image = Image.frombytes('RGB', (32, 24), bytes(randomizer.randrange(256) for _ in range(32*24*3)))
    stream = io.BytesIO(); image.save(stream, format='PNG'); return stream.getvalue()


def archive_fixture(tmp_path, extra=None):
    target = tmp_path / 'source.zip'
    entries = {'data.yaml': 'names: [No_entry, No_parking, No_trucks]\n'}
    for i in range(18):
        split = ('train', 'valid', 'test')[i % 3]
        entries[f'{split}/images/photo_{i}.png'] = image_bytes(i)
        entries[f'{split}/labels/photo_{i}.txt'] = '0 .5 .5 .4 .4\n1 .2 .2 .1 .1\n2 .8 .8 .1 .1\n'
    entries['test/images/copy.png'] = entries['train/images/photo_0.png']
    entries['test/labels/copy.txt'] = entries['train/labels/photo_0.txt']
    entries.update(extra or {})
    with zipfile.ZipFile(target, 'w') as archive:
        for name, content in entries.items(): archive.writestr(name, content)
    return target


def prepare(tmp_path, **kwargs):
    source = archive_fixture(tmp_path)
    output = tmp_path / 'prepared'
    manifest = prepare_supsign(source, output, classes=['No_parking', 'No_entry'],
                               block_size=1, near_threshold=None, **kwargs)
    return source, output, manifest


def test_prepared_eda_counts_boxes_negatives_and_sizes_without_modifying_dataset(tmp_path):
    from scripts.supsign_training import summarize_prepared_dataset
    _, root, _ = prepare(tmp_path)
    before = {p.relative_to(root): digest for p in root.rglob('*') if p.is_file()
              for digest in [hashlib.sha256(p.read_bytes()).hexdigest()]}
    report = summarize_prepared_dataset(root, imgsz=640)
    assert report['summary']['images'] == 18
    assert report['summary']['boxes'] == 36
    assert report['summary']['duplicates_removed'] == 1
    assert report['summary']['negative_images'] == 0
    assert report['summary']['independent_field_test'] is False
    assert {r['name'] for r in report['class_counts']} == {'No_entry', 'No_parking'}
    assert all(r['short_side_at_input'] > 0 for r in report['boxes'])
    assert before == {p.relative_to(root): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in root.rglob('*') if p.is_file()}


def test_subset_remaps_by_name_deduplicates_and_never_changes_source(tmp_path):
    source = archive_fixture(tmp_path)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    output = tmp_path / 'prepared'
    manifest = prepare_supsign(source, output, classes=['No_parking', 'No_entry'], block_size=1, near_threshold=None)
    assert len(CAR35) == len(set(CAR35)) == 35
    assert manifest['names'] == ['No_parking', 'No_entry']
    assert len(manifest['images']) == 18 and manifest['duplicates_removed'] == 1
    assert len({r['sha256'] for r in manifest['images']}) == 18
    assert {r['split'] for r in manifest['images']} == {'train','val','test'}
    for row in manifest['images']:
        lines=(output/row['label']).read_text().splitlines()
        assert {int(line.split()[0]) for line in lines} == {0,1}
        assert lines[0].startswith('1 ') and lines[1].startswith('0 ')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    assert manifest['split_provenance'] == 'development_heuristic'
    assert manifest['independent_field_test'] is False
    assert verify_dataset(output)['images'] == 18


def test_invalid_labels_and_conflicting_duplicate_annotations_are_quarantined(tmp_path):
    source=archive_fixture(tmp_path, {
        'train/labels/photo_3.txt':'0 .5 .5 .2 0\n',
        'test/labels/copy.txt':'1 .5 .5 .2 .2\n',
        'valid/images/missing.png':image_bytes(99),
    })
    manifest=prepare_supsign(source,tmp_path/'prepared',classes=['No_entry','No_parking'],block_size=1,near_threshold=None)
    assert len(manifest['images']) == 16
    reasons={r['reason'] for r in manifest['excluded']}
    assert {'invalid_annotation','missing_annotation','conflicting_duplicate_labels'} <= reasons
    assert not any(r['source_path'].endswith(('photo_0.png','copy.png','photo_3.png')) for r in manifest['images'])


def test_declared_capture_groups_and_aliases_stay_together(tmp_path):
    source=archive_fixture(tmp_path)
    groups={f'{("train","valid","test")[i%3]}/images/photo_{i}.png':f'trip_{i//3}' for i in range(18)}
    groups['test/images/copy.png']='trip_0'
    manifest=prepare_supsign(source,tmp_path/'prepared',classes=['No_entry'],groups=groups,block_size=1,near_threshold=None)
    assigned={}
    for row in manifest['images']:
        trip=groups[row['source_path'].split('!/',1)[-1]]
        assert assigned.setdefault(trip,row['split']) == row['split']
    assert manifest['split_provenance'] == 'provided_capture_groups'
    assert manifest['independent_field_test'] is False


def test_incomplete_groups_unknown_classes_and_too_few_groups_stop_without_output(tmp_path):
    source=archive_fixture(tmp_path)
    for name,options,match in [
        ('unknown',dict(classes=['not-a-class']),'class'),
        ('incomplete',dict(classes=['No_entry'],groups={'train/images/photo_0.png':'a'}),'group'),
        ('few',dict(classes=['No_entry'],block_size=10000,near_threshold=None),'group'),
    ]:
        output=tmp_path/name
        with pytest.raises(ValueError,match=match): prepare_supsign(source,output,**options)
        assert not output.exists()


def test_near_duplicate_clustering_is_transitive_and_never_crosses_splits(tmp_path):
    from scripts.supsign_training import cluster_records
    rows=[{'sha256':str(i),'source_path':f'x/images/unique{i}.png','aliases':[f'x/images/unique{i}.png'],
           'visual_hash':v} for i,v in enumerate([0,1,3,2**32-1,2**48-1])]
    groups=cluster_records(rows,block_size=1,near_threshold=1)
    assert groups[0] == groups[1] == groups[2]
    assert len(set(groups)) == 3


def test_cache_roundtrip_detects_tampering_and_recipe_changes(tmp_path):
    _,root,manifest=prepare(tmp_path)
    cache=tmp_path/'cache.zip';pack_dataset(root,cache)
    restored=tmp_path/'restored';restore_dataset(cache,restored,expected_recipe=manifest['recipe'])
    assert verify_dataset(restored)['images'] == 18
    assert yaml.safe_load((restored/'data.yaml').read_text())['path'] == '.'
    with pytest.raises(ValueError,match='recipe'):
        restore_dataset(cache,tmp_path/'wrong',expected_recipe={'classes':['wrong']})
    with pytest.raises(FileExistsError):pack_dataset(root,cache)
    row=manifest['images'][0];(restored/row['label']).write_text('0 .5 .5 .01 .01')
    with pytest.raises(ValueError,match='changed'):verify_dataset(restored)
    cache.write_bytes(cache.read_bytes()+b'tampered')
    with pytest.raises(ValueError,match='checksum'):restore_dataset(cache,tmp_path/'bad')


def test_cache_restore_rejects_zip_traversal(tmp_path):
    cache=tmp_path/'unsafe.zip'
    with zipfile.ZipFile(cache,'w') as archive: archive.writestr('../escape.txt','no')
    cache.with_suffix('.zip.sha256').write_text(hashlib.sha256(cache.read_bytes()).hexdigest())
    with pytest.raises(ValueError,match='Unsafe'):restore_dataset(cache,tmp_path/'restored')
    assert not (tmp_path/'escape.txt').exists() and not (tmp_path/'restored').exists()


def test_training_small_never_evaluates_test_and_resume_checks_dataset(tmp_path):
    _,root,manifest=prepare(tmp_path)
    calls=[]
    class FakeYOLO:
        task='detect';names={0:'No_parking',1:'No_entry'}
        def __init__(self,model):calls.append(('load',model))
        def train(self,**options):
            calls.append(('train',options));run=Path(options['project'])/options['name']
            (run/'weights').mkdir(exist_ok=True)
            for name in ['best.pt','last.pt']:(run/'weights'/name).write_bytes(b'fixture')
        def val(self,**options):raise AssertionError('train must not evaluate held-out test')
    run=tmp_path/'run'
    train_experiment(root,run,epochs=2,batch=4,yolo_factory=FakeYOLO)
    options=calls[-1][1]
    assert calls[0] == ('load','yolo11s.pt')
    assert options['fliplr'] == options['flipud'] == 0 and options['cache'] is False
    assert options['epochs'] == 2 and options['batch'] == 4
    assert Path(options['data']).is_file() and yaml.safe_load(Path(options['data']).read_text())['path']==str(root.resolve())
    with pytest.raises(FileExistsError):train_experiment(root,run,yolo_factory=FakeYOLO)
    train_experiment(root,run,epochs=2,batch=4,resume=True,yolo_factory=FakeYOLO)
    assert calls[-1][1]['resume'] is True
    request=json.loads((run/'training_request.json').read_text());request['manifest_sha256']='changed'
    (run/'training_request.json').write_text(json.dumps(request))
    with pytest.raises(ValueError,match='dataset'):train_experiment(root,run,resume=True,yolo_factory=FakeYOLO)


def test_test_metrics_are_opt_in_and_taxonomy_is_checked(tmp_path):
    _,root,_=prepare(tmp_path);checkpoint=tmp_path/'best.pt';checkpoint.write_bytes(b'fixture')
    calls=[]
    class FakeYOLO:
        task='detect';names={0:'No_parking',1:'No_entry'}
        def __init__(self,*args):pass
        def val(self,**options):
            calls.append(options)
            return type('Metrics',(),{'results_dict':{'metrics/mAP50-95(B)':.4}})()
    with pytest.raises(ValueError,match='test'):
        evaluate_checkpoint(checkpoint,root,tmp_path/'test',split='test',yolo_factory=FakeYOLO)
    report=evaluate_checkpoint(checkpoint,root,tmp_path/'val',yolo_factory=FakeYOLO)
    assert calls[-1]['split']=='val' and report['independent_field_test'] is False
    FakeYOLO.names={0:'wrong'}
    with pytest.raises(ValueError,match='taxonomy'):
        evaluate_checkpoint(checkpoint,root,tmp_path/'wrong',yolo_factory=FakeYOLO)


def test_notebook_is_reproducible_self_contained_small_and_does_not_auto_run_test():
    from scripts.generate_supsign_notebook import build_notebook
    root=Path(__file__).resolve().parents[1]
    notebook=build_notebook()
    assert notebook==json.loads((root/'notebooks/SignSight_SupSign_YOLO11s_Colab.ipynb').read_text(encoding='utf-8'))
    for cell in notebook['cells']:
        if cell['cell_type']=='code':
            ast.parse(''.join(cell['source']));assert cell['outputs']==[] and cell['execution_count'] is None
    code='\n'.join(''.join(c['source']) for c in notebook['cells'] if c['cell_type']=='code')
    assert 'files.download' in code and 'drive.mount' in code and 'RUN_HELDOUT_TEST = False' in code
    assert 'KAGGLE' not in code and 'kagglehub' not in code
    assert 'SOURCE_ZIP' in code and 'restore_dataset' in code and 'RESUME = False' in code
    assert 'gdown==5.2.0' in code and 'SOURCE_URL' in code and 'SAVE_TO_DRIVE' in code


@pytest.mark.parametrize('save_to_drive', [False, True])
def test_notebook_can_use_local_outputs_or_mount_the_current_account(tmp_path, monkeypatch, save_to_drive):
    import os, sys, types
    from scripts.generate_supsign_notebook import build_notebook
    source = next(''.join(c['source']) for c in build_notebook()['cells'] if c['id']=='config')
    assert 'SAVE_TO_DRIVE' in source
    work, persist = tmp_path/'runtime', tmp_path/'current-account'
    source = source.replace("WORK = Path('/content/signsight_supsign')", f'WORK = Path({str(work)!r})')
    source = source.replace("DRIVE_OUTPUT_ROOT = Path('/content/drive/MyDrive/SignSight/supsign_training')",
                            f'DRIVE_OUTPUT_ROOT = Path({str(persist)!r})')
    source = source.replace('SAVE_TO_DRIVE = True', f'SAVE_TO_DRIVE = {save_to_drive}')
    mounts=[]
    monkeypatch.setitem(sys.modules, 'google.colab', types.SimpleNamespace(
        drive=types.SimpleNamespace(mount=lambda path: mounts.append(path))))
    monkeypatch.setenv('YOLO_CONFIG_DIR', str(tmp_path/'settings'))
    context={'os':os}
    exec(source,context)
    assert len(mounts) == int(save_to_drive)
    assert context['PERSIST'] == (persist if save_to_drive else work/'outputs')
    assert context['SOURCE_ZIP'].is_relative_to(work)
    first = context['SOURCE_ZIP'];first.parent.mkdir(parents=True, exist_ok=True);first.write_bytes(b'old source')
    second={"os":os}
    exec(source.replace("DATASET_VERSION = 'supsign107-car35-v3'", "DATASET_VERSION = 'different-source-v4'"),second)
    assert second['SOURCE_ZIP'] != first
    assert first.read_bytes() == b'old source'


def test_cache_does_not_delete_an_existing_partial_file(tmp_path):
    _,root,_=prepare(tmp_path)
    target=tmp_path/'cache.zip';partial=tmp_path/'cache.zip.part';partial.write_bytes(b'keep-my-partial')
    with pytest.raises(FileExistsError):pack_dataset(root,target)
    assert partial.read_bytes()==b'keep-my-partial'


@pytest.mark.parametrize('use_gdown', [False, True])
def test_notebook_runs_prepare_train_evaluate_export_then_restores_cache(tmp_path, monkeypatch, use_gdown):
    from scripts.generate_supsign_notebook import build_notebook
    import shutil
    import sys
    import types
    import matplotlib
    matplotlib.use('Agg')
    notebook=build_notebook()
    cells={cell['id']:''.join(cell['source']) for cell in notebook['cells'] if cell['cell_type']=='code'}
    source=archive_fixture(tmp_path);work=tmp_path/'work';work.mkdir();persist=tmp_path/'drive';persist.mkdir()
    downloaded=[];calls=[]
    downloads=[]
    def download(**options):
        downloads.append(options)
        payload = source if options['id']=='fixture_source_12345' else persist/'dataset.zip'
        Path(options['output']).write_bytes(payload.read_bytes())
        return options['output']
    monkeypatch.setitem(sys.modules,'gdown',types.SimpleNamespace(download=download))
    files=types.ModuleType('google.colab.files');files.download=lambda path:downloaded.append(Path(path))
    colab=types.ModuleType('google.colab');colab.files=files
    monkeypatch.setitem(sys.modules,'google.colab',colab);monkeypatch.setitem(sys.modules,'google.colab.files',files)
    class FakeYOLO:
        task='detect';names={0:'No_entry',1:'No_parking'}
        def __init__(self,model):calls.append(('load',str(model)))
        def train(self,**options):
            calls.append(('train',options));root=Path(options['project'])/options['name']
            (root/'weights').mkdir()
            (root/'weights/best.pt').write_bytes(b'best');(root/'weights/last.pt').write_bytes(b'last')
        def val(self,**options):
            calls.append(('val',options))
            return type('Metrics',(),{'results_dict':{'metrics/mAP50(B)':.6}})()
    monkeypatch.setitem(sys.modules,'ultralytics',types.SimpleNamespace(YOLO=FakeYOLO))
    context=dict(WORK=work,PERSIST=persist,SOURCE_ZIP=source,SOURCE_URL='',SOURCE_SHA256='',
                 PREPARED_CACHE_URL='',PREPARED_CACHE_SHA256='',SAVE_TO_DRIVE=True,GROUPS_CSV=None,SEED=42,
                 FRAME_BLOCK_SIZE=1,NEAR_HASH_DISTANCE=None,CACHE_ZIP=persist/'dataset.zip',
                 DATASET_ROOT=work/'prepared',RUN_DIR=persist/'runs/first',RUN_NAME='first',
                 EPOCHS=2,IMAGE_SIZE=640,BATCH=4,RESUME=False,SMOKE=False,RUN_HELDOUT_TEST=False,
                 DATASET_VERSION='fixture-v1',LABEL_REVIEWED=True,
                 sys=sys,shutil=shutil,json=json,Path=Path)
    if use_gdown:
        context.update(SOURCE_URL='https://drive.google.com/file/d/fixture_source_12345/view',
                       SOURCE_ZIP=work/'source_supsign.zip')
    monkeypatch.syspath_prepend(str(work/'pipeline'))
    for name in ('scripts.supsign_training','scripts.dataset_eda','scripts.colab_downloads','scripts'):
        monkeypatch.delitem(sys.modules,name,raising=False)
    exec(cells['pipeline'],context)
    # A two-class fixture exercises the real notebook flow without live images/weights/GPU.
    context['CAR35']=['No_entry','No_parking']
    context['RECIPE']=context['recipe'](context['CAR35'],42,1,None,None)
    # The small fixture needs little disk; test the notebook's preflight without allocating GBs.
    monkeypatch.setattr(shutil,'disk_usage',lambda _:types.SimpleNamespace(free=100*1024**3))
    # Reproduce the old split failure, then exercise the actual recovery cell.
    training = sys.modules['scripts.supsign_training']
    splitter = training.choose_splits
    def failed_split(*args): raise ValueError('Missing train classes after grouping')
    monkeypatch.setattr(training, 'choose_splits', failed_split)
    try:
        exec(cells['prepare'],context)
    except ValueError as error:
        context['_SIGNSIGHT_PREP_TRACEBACK'] = error.__traceback__
    else:
        raise AssertionError('Expected the previous split failure')
    root = Path(__file__).resolve().parents[1]
    import urllib.request
    monkeypatch.setattr(urllib.request, 'urlopen', lambda *a, **k:
                        io.BytesIO((root/'scripts/supsign_training.py').read_bytes()))
    def no_audit(*args, **kwargs): raise AssertionError('Recovery must not re-audit images')
    monkeypatch.setattr(sys.modules['scripts.dataset_eda'], 'audit_dataset', no_audit)
    exec((root/'scripts/recover_supsign_colab.py').read_text(),context)
    exec(cells['prepare'],context);exec(cells['eda'],context);exec(cells['preview'],context)
    exec(cells['train'],context);exec(cells['evaluate'],context);exec(cells['export'],context)
    assert context['BEST'].is_file() and len(downloaded)==1
    assert [kind for kind,_ in calls].count('train')==1
    assert [options['split'] for kind,options in calls if kind=='val']==['val']
    with zipfile.ZipFile(downloaded[0]) as archive:
        assert 'run/weights/best.pt' in archive.namelist() and 'dataset/manifest.json' in archive.namelist()
        assert 'eda/boxes.csv' in archive.namelist() and 'eda/eda_overview.png' in archive.namelist()
        assert not any(name.startswith('dataset/images/') for name in archive.namelist())
    # A fresh runtime only needs the persisted prepared ZIP, not the raw archive.
    source.unlink();context['DATASET_ROOT']=work/'restored'
    if use_gdown:
        assert len(downloads)==1 and downloads[0]['use_cookies'] is False
        context['SOURCE_ZIP'].unlink()
        context.update(CACHE_ZIP=tmp_path/'new-account'/'dataset.zip',
                       PREPARED_CACHE_URL='fixture_cache_12345',
                       PREPARED_CACHE_SHA256=hashlib.sha256((persist/'dataset.zip').read_bytes()).hexdigest())
    exec(cells['prepare'],context)
    assert context['DATASET_ROOT'].is_dir() and len(context['manifest']['images'])==18
    if use_gdown:
        assert [d['id'] for d in downloads] == ['fixture_source_12345','fixture_cache_12345']


def test_cache_cannot_archive_itself_inside_the_dataset(tmp_path,monkeypatch):
    _,root,_=prepare(tmp_path)
    def forbidden(*args,**kwargs):raise AssertionError('Must reject self-archive before opening ZIP')
    monkeypatch.setattr('scripts.supsign_training.zipfile.ZipFile',forbidden)
    with pytest.raises(ValueError,match='outside'):pack_dataset(root,root/'recursive.zip')
    assert not (root/'recursive.zip').exists()


def test_pretrained_download_failure_can_retry_without_an_empty_run(tmp_path):
    _,root,_=prepare(tmp_path);run=tmp_path/'run'
    def unavailable(_):raise OSError('offline')
    with pytest.raises(OSError,match='offline'):train_experiment(root,run,yolo_factory=unavailable)
    assert not run.exists()
