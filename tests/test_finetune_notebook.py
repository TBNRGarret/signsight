"""Execute the standalone notebook with synthetic datasets/models, without network."""
import ast
import functools
import importlib
import json
import os
import sys
from zipfile import ZipFile

from test_raw_car35 import raw_fixture
from test_car35_handoff import factory
from test_supsign_training import clear_embedded_modules
from test_car35_finetune import review_zip
from test_active_learning import model_factory


def builder():return importlib.import_module('training.notebooks.finetune')


def test_review_then_train_baseline_compare_export_standalone(tmp_path,monkeypatch):
    notebook=builder().build_finetune_notebook()
    cells={c['id']:''.join(c['source']) for c in notebook['cells'] if c['cell_type']=='code'}
    clear_embedded_modules(monkeypatch);monkeypatch.syspath_prepend(str(tmp_path/'unused'))
    ctx=dict(sys=sys,os=os)
    work=tmp_path/'runtime'
    exec(cells['config'].replace("Path('/content/signsight_raw107')",f'Path({str(work)!r})'),ctx)
    archive=raw_fixture(tmp_path/'raw')
    ctx.update(LOCAL_SOURCE_ZIP=str(archive),RAW_ZIP_SHA256='',EXPECTED_BASE_MANIFEST_SHA256='',
               NEAR_HASH_DISTANCE=None,WORKERS=2,DOWNLOAD_RESULTS=False,DEVICE='cpu',EPOCHS=2,MODE='review')
    exec(cells['pipeline'],ctx);exec(cells['prepare'],ctx);exec(cells['review_pack'],ctx)
    assert ctx['REVIEW_PACK'].is_file()
    exec(cells['fine_prepare'],ctx);exec(cells['baseline'],ctx);exec(cells['finetune'],ctx)
    assert not ctx['RUN_DIR'].exists()  # review mode cannot accidentally train.
    original_label=next((ctx['DATASET_ROOT']/'labels/train').glob('*.txt')).read_text()
    review=review_zip(tmp_path,ctx['DATASET_ROOT'],label=original_label)
    # Windows "compress folder" preserves the containing directory.
    with ZipFile(review) as z: entries={'car35_training_labels_to_review/'+n:z.read(n) for n in z.namelist()}
    with ZipFile(review,'w') as z:
        for n,b in entries.items(): z.writestr(n,b)
    checkpoint=tmp_path/'baseline.pt';checkpoint.write_bytes(b'synthetic-baseline')
    ctx.update(MODE='train',LOCAL_REVIEW_ZIP=str(review),LOCAL_CHECKPOINT=str(checkpoint),
               CHECKPOINT_SHA256=ctx['digest_file'](checkpoint))
    exec(cells['fine_prepare'],ctx)
    # A second execution reuses the verified dataset rather than requiring a new runtime.
    exec(cells['fine_prepare'],ctx)
    calls=[]
    ctx['evaluate_car35']=functools.partial(ctx['evaluate_car35'],yolo_factory=factory(calls))
    ctx['finetune_car35']=functools.partial(ctx['finetune_car35'],yolo_factory=factory(calls))
    exec(cells['baseline'],ctx);exec(cells['finetune'],ctx);exec(cells['compare'],ctx)
    from PIL import Image
    photo=tmp_path/'photo.png';Image.new('RGB',(32,24),'red').save(photo)
    photos=tmp_path/'photos.zip'
    with ZipFile(photos,'w') as z:z.write(photo,'photo.png')
    probe_module=importlib.import_module('training.experiments.photo_probe')
    monkeypatch.setattr(probe_module,'probe_photos',functools.partial(probe_module.probe_photos,yolo_factory=model_factory()))
    ctx.update(REGRESSION_URL='1testphotos12345',download_drive_zip=lambda *a,**k:photos)
    exec(cells['regression'],ctx);exec(cells['fine_export'],ctx)
    assert len(calls)==3
    assert calls[0].options['split']==calls[2].options['split']=='val'
    assert calls[1].options['resume'] is False
    assert calls[1].options['optimizer']=='AdamW' and calls[1].options['lr0']==.0003
    assert calls[1].options['fliplr']==0 and calls[1].options['mosaic']==.1
    with ZipFile(ctx['RESULT_ZIP']) as z:
        assert {'run/comparison.json','run/weights/best.pt','run/baseline/evaluation_report.json'}<=set(z.namelist())
        assert not any(n.startswith('dataset/images/') for n in z.namelist())
        assert 'run/photo_probe.json' in z.namelist()
        report=json.loads(z.read('run/photo_probe.json'))
        assert report['independent_field_test'] is False
        assert set(report['models'])=={'baseline','candidate'}


def test_notebook_is_reproducible_clean_and_pins_training_version():
    module=builder();notebook=module.build_finetune_notebook()
    assert notebook==json.loads(module.TARGET.read_text(encoding='utf-8'))
    code='\n'.join(''.join(c['source']) for c in notebook['cells'] if c['cell_type']=='code' and c['id']!='pipeline')
    assert 'ultralytics==8.4.173' in code
    assert "MODE = 'train'" in cells_config(notebook)
    assert 'drive.mount' not in code and 'git clone' not in code
    for cell in notebook['cells']:
        if cell['cell_type']=='code':
            ast.parse(''.join(cell['source']))
            assert cell['outputs']==[] and cell['execution_count'] is None


def cells_config(notebook):
    return ''.join(next(c['source'] for c in notebook['cells'] if c['id']=='config'))
