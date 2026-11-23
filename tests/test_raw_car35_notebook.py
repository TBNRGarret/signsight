"""The raw-107 notebook runs standalone; no Drive, model or user data accessed."""
import ast
import functools
import importlib
import json
import os
from pathlib import Path
import shutil
import sys
from zipfile import ZipFile

import pytest

from test_raw_car35 import raw_fixture
from test_car35_handoff import factory
from test_supsign_training import clear_embedded_modules


def builder():
    return importlib.import_module('training.notebooks.raw_car35')


def test_standalone_raw_notebook_prepares_trains_evaluates_exports_and_reuses_cache(tmp_path, monkeypatch):
    import matplotlib
    matplotlib.use('Agg')
    archive = raw_fixture(tmp_path/'raw')
    module = builder(); notebook = module.build_raw_car35_notebook()
    cells = {c['id']: ''.join(c['source']) for c in notebook['cells'] if c['cell_type']=='code'}
    clear_embedded_modules(monkeypatch)
    work=tmp_path/'runtime';context=dict(sys=sys,os=os)
    monkeypatch.syspath_prepend(str(work/'unused'))
    exec(cells['config'].replace("Path('/content/signsight_raw107')",f'Path({str(work)!r})'),context)
    context.update(SOURCE_URL='synthetic_source_file_123',NEAR_HASH_DISTANCE=None,WORKERS=2,
                   DEVICE='cpu',EPOCHS=2,BATCH=4,DOWNLOAD_RESULTS=False)
    exec(cells['pipeline'],context)
    downloads=[]
    def transport(source,target,**kwargs):
        downloads.append(source);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(archive,target);return target
    context['download_drive_zip']=transport
    exec(cells['prepare'],context)
    assert context['dataset_info']['images']==12
    assert context['dataset_info']['names']==context['CAR35']
    first=context['dataset_info']['manifest_sha256']
    calls=[]
    context['train_car35']=functools.partial(context['train_car35'],yolo_factory=factory(calls))
    context['evaluate_car35']=functools.partial(context['evaluate_car35'],yolo_factory=factory(calls))
    exec(cells['eda'],context);exec(cells['train'],context)
    exec(cells['evaluate'],context);exec(cells['export'],context)
    assert [c.options['split'] for c in calls]==['val','val']
    with ZipFile(context['RESULT_ZIP']) as result:
        assert 'run/weights/best.pt' in result.namelist()
        assert 'run/eda/class_counts.csv' in result.namelist()
        manifest=json.loads(result.read('dataset/manifest.json'))
        assert manifest['raw_zip_preparation']['source_classes']==107
        assert manifest['dataset_version']==context['DATASET_VERSION']
    context['download_drive_zip']=lambda *a,**k:pytest.fail('Verified cache should avoid downloads')
    exec(cells['prepare'],context)
    assert context['dataset_info']['manifest_sha256']==first
    assert len(downloads)==1
    context['SEED']=43
    with pytest.raises(ValueError,match='recipe'):exec(cells['prepare'],context)


def test_local_raw_zip_is_reused_without_downloading(tmp_path,monkeypatch):
    archive=raw_fixture(tmp_path/'raw')
    cells={c['id']:''.join(c['source']) for c in builder().build_raw_car35_notebook()['cells'] if c['cell_type']=='code'}
    clear_embedded_modules(monkeypatch)
    monkeypatch.syspath_prepend(str(tmp_path/'unused'))
    context=dict(sys=sys,os=os)
    exec(cells['config'].replace("Path('/content/signsight_raw107')",f'Path({str(tmp_path/"runtime")!r})'),context)
    context.update(LOCAL_SOURCE_ZIP=str(archive),NEAR_HASH_DISTANCE=None)
    exec(cells['pipeline'],context)
    context['download_drive_zip']=lambda *a,**k:pytest.fail('Explicit local ZIP should be reused')
    exec(cells['prepare'],context)
    assert context['dataset_info']['images']==12 and archive.is_file()


def test_raw_notebook_is_reproducible_clean_and_contains_no_v4_patch_gate():
    module=builder();notebook=module.build_raw_car35_notebook()
    assert notebook==json.loads(module.TARGET.read_text(encoding='utf-8'))
    code='\n'.join(''.join(c['source']) for c in notebook['cells'] if c['cell_type']=='code' and c['id']!='pipeline')
    assert 'PATCH_URL' not in code and 'EXPECTED_REVISED_MANIFEST_SHA256' not in code
    assert 'drive.mount' not in code and 'git clone' not in code
    for cell in notebook['cells']:
        if cell['cell_type']=='code':
            ast.parse(''.join(cell['source']))
            assert cell['execution_count'] is None and cell['outputs']==[]
