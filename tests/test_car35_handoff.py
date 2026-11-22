"""Standalone CAR35 ZIP workflow uses temporary data and synthetic training."""
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile, ZipInfo
import hashlib
import importlib
import json

import pytest
from PIL import Image
import yaml

from training.data.common import CAR35


def fixture(tmp_path):
    root=tmp_path/'fixture';root.mkdir()
    rows=[]
    for i,split in enumerate(('train','val','test')):
        image_dir=root/'images'/split;label_dir=root/'labels'/split
        image_dir.mkdir(parents=True);label_dir.mkdir(parents=True)
        raw=image_dir/'source.png';Image.new('RGB',(20,16),(i*70,30,60)).save(raw)
        digest=hashlib.sha256(raw.read_bytes()).hexdigest();image=raw.rename(image_dir/(digest+'.png'))
        label=label_dir/(digest+'.txt');label.write_text(''.join(f'{c} .5 .5 .2 .2\n' for c in range(35)))
        rows.append(dict(image=image.relative_to(root).as_posix(),label=label.relative_to(root).as_posix(),
                         sha256=digest,label_sha256=hashlib.sha256(label.read_bytes()).hexdigest(),group=f'g{i}',split=split))
    manifest=dict(kind='car35_folder_development_v4',names=CAR35,images=rows,independent_field_test=False,
                  class_counts={s:{str(c):1 for c in range(35)} for s in ('train','val','test')},
                  limitations='Synthetic development fixture; no field claims.')
    (root/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    (root/'data.yaml').write_text(yaml.safe_dump(dict(train='images/train',val='images/val',test='images/test',names=CAR35)))
    archive=tmp_path/'car35.zip'
    with ZipFile(archive,'w') as z:
        for p in sorted(root.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(root).as_posix())
    return root,archive,hashlib.sha256(archive.read_bytes()).hexdigest(),hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()


def data_api():return importlib.import_module('training.data.car35_bundle')
def experiment():return importlib.import_module('training.experiments.car35')


def test_restore_checks_all_content_and_preserves_exact_split(tmp_path):
    original,archive,checksum,manifest_sha=fixture(tmp_path)
    output=tmp_path/'restored'
    info=data_api().restore_car35_bundle(archive,output,expected_sha256=checksum,expected_manifest_sha256=manifest_sha)
    assert info['images']==3 and info['boxes']==105
    assert info['split_images']==dict(train=1,val=1,test=1)
    assert info['names']==CAR35
    for source in original.rglob('*'):
        if source.is_file():assert source.read_bytes()==(output/source.relative_to(original)).read_bytes()
    with pytest.raises(FileExistsError):
        data_api().restore_car35_bundle(archive,output,expected_sha256=checksum)


def test_bad_archive_checksum_does_not_publish_dataset(tmp_path):
    _,archive,_,_=fixture(tmp_path)
    with pytest.raises(ValueError,match='checksum|SHA'):
        data_api().restore_car35_bundle(archive,tmp_path/'bad',expected_sha256='0'*64)
    assert not (tmp_path/'bad').exists()


@pytest.mark.parametrize('attack',['traversal','duplicate','symlink'])
def test_unsafe_zip_members_are_rejected(tmp_path,attack):
    _,archive,_,_=fixture(tmp_path)
    with ZipFile(archive,'a') as z:
        if attack=='traversal':z.writestr('../escape.txt','bad')
        elif attack=='duplicate':
            with pytest.warns(UserWarning):z.writestr('data.yaml','bad')
        else:
            info=ZipInfo('link');info.create_system=3;info.external_attr=(0o120777<<16);z.writestr(info,'/etc/passwd')
    checksum=hashlib.sha256(archive.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match='Unsafe|duplicate|ZIP'):
        data_api().restore_car35_bundle(archive,tmp_path/'bad',expected_sha256=checksum)
    assert not (tmp_path/'escape.txt').exists() and not (tmp_path/'bad').exists()


def test_manifest_binding_and_label_tampering_are_rejected(tmp_path):
    root,_,_,manifest_sha=fixture(tmp_path)
    with pytest.raises(ValueError,match='manifest'):
        data_api().verify_car35(root,expected_manifest_sha256='0'*64)
    next((root/'labels').rglob('*.txt')).write_text('0 .5 .5 .2 .2\n')
    with pytest.raises(ValueError,match='hash|changed'):
        data_api().verify_car35(root,expected_manifest_sha256=manifest_sha)


def factory(calls):
    class SyntheticYOLO:
        def __init__(self,weights):self.weights=weights;self.names=dict(enumerate(CAR35));self.task='detect';calls.append(self)
        def train(self,**kwargs):
            self.options=kwargs;out=Path(kwargs['project'])/kwargs['name'];(out/'weights').mkdir(parents=True,exist_ok=True)
            (out/'weights/best.pt').write_bytes(b'synthetic-best');(out/'weights/last.pt').write_bytes(b'synthetic-last')
        def val(self,**kwargs):
            self.options=kwargs
            return SimpleNamespace(results_dict={'metrics/mAP50(B)':.4})
    return SyntheticYOLO


def test_train_uses_official_small_weights_and_guards_resume(tmp_path):
    root,_,_,_=fixture(tmp_path);calls=[];run=tmp_path/'run'
    best=experiment().train_car35(root,run,epochs=2,batch=4,device='cpu',yolo_factory=factory(calls))
    assert best==run/'weights/best.pt' and best.is_file()
    assert calls[0].weights=='yolo11s.pt'
    options=calls[0].options
    assert options['fliplr']==options['flipud']==0 and options['cache'] is False
    assert options['save_period']==5 and options['split']=='val'
    with pytest.raises(FileExistsError):experiment().train_car35(root,run,yolo_factory=factory(calls))
    with pytest.raises(ValueError,match='settings'):
        experiment().train_car35(root,run,epochs=2,batch=8,resume=True,yolo_factory=factory(calls))
    experiment().train_car35(root,run,epochs=2,batch=4,device='cpu',resume=True,yolo_factory=factory(calls))
    assert calls[-1].weights==str(run/'weights/last.pt') and calls[-1].options['resume'] is True


def test_test_evaluation_is_explicit_and_export_contains_identity(tmp_path):
    root,_,_,_=fixture(tmp_path);calls=[];run=tmp_path/'run'
    checkpoint=experiment().train_car35(root,run,epochs=2,yolo_factory=factory(calls))
    with pytest.raises(ValueError,match='test'):
        experiment().evaluate_car35(checkpoint,root,tmp_path/'eval',split='test',yolo_factory=factory(calls))
    report=experiment().evaluate_car35(checkpoint,root,tmp_path/'eval',yolo_factory=factory(calls))
    assert report['split']=='val' and report['split_images']==1
    archive=experiment().export_car35_run(run,root,tmp_path/'results.zip')
    with ZipFile(archive) as z:
        assert {'run/weights/best.pt','run/weights/last.pt','dataset/manifest.json','handoff.json'}<=set(z.namelist())
        handoff=json.loads(z.read('handoff.json'))
        assert handoff['independent_field_test'] is False and handoff['dataset']['images']==3


@pytest.mark.parametrize('stage',['eda','train'])
def test_car35_notebook_runs_standalone_on_prepared_zip(tmp_path,monkeypatch,stage):
    import functools
    import os
    import shutil
    import sys
    from test_supsign_training import clear_embedded_modules
    builder=importlib.import_module('training.notebooks.car35')
    notebook=builder.build_car35_eda_notebook() if stage=='eda' else builder.build_car35_train_notebook()
    _,archive,checksum,manifest_sha=fixture(tmp_path)
    work=tmp_path/'runtime'
    clear_embedded_modules(monkeypatch)
    monkeypatch.syspath_prepend(str(work/'unused'))
    context=dict(sys=sys,os=os)
    cells={c['id']:''.join(c['source']) for c in notebook['cells'] if c['cell_type']=='code'}
    code=cells['config'].replace("Path('/content/signsight_car35')",f'Path({str(work)!r})')
    exec(code,context)
    context.update(SOURCE_URL='synthetic-file-id',DATASET_SHA256=checksum,APPLY_REVIEWED_PATCH=False,
                   EXPECTED_MANIFEST_SHA256=manifest_sha,DOWNLOAD_RESULTS=False,EPOCHS=2,BATCH=4,DEVICE='cpu')
    exec(cells['pipeline'],context)
    def local_transport(source,target,**kwargs):
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(archive,target);return target
    context['download_drive_zip']=local_transport
    exec(cells['prepare'],context)
    assert context['dataset_info']['split_images']==dict(train=1,val=1,test=1)
    if stage=='train':
        calls=[]
        context['train_car35']=functools.partial(context['train_car35'],yolo_factory=factory(calls))
        context['evaluate_car35']=functools.partial(context['evaluate_car35'],yolo_factory=factory(calls))
        exec(cells['train'],context);exec(cells['evaluate'],context)
        assert [c.options['split'] for c in calls]==['val','val']
    else:
        import matplotlib
        matplotlib.use('Agg')
        exec(cells['eda'],context)
    exec(cells['export'],context)
    assert context['RESULT_ZIP'].is_file()
    with ZipFile(context['RESULT_ZIP']) as exported:
        receipt = 'run/source_archive_verification.json' if stage=='train' else 'source_archive_verification.json'
        assert receipt in exported.namelist()
    assert hashlib.sha256((context['DATASET_ROOT']/'manifest.json').read_bytes()).hexdigest()==manifest_sha


def test_active_car35_notebooks_reproduce_from_builder_and_have_clean_cells():
    import ast
    builder=importlib.import_module('training.notebooks.car35')
    for target,build in ((builder.EDA_TARGET,builder.build_car35_eda_notebook),
                         (builder.TRAIN_TARGET,builder.build_car35_train_notebook)):
        notebook=build()
        assert notebook==json.loads(target.read_text(encoding='utf-8'))
        for cell in notebook['cells']:
            if cell['cell_type']=='code':
                ast.parse(''.join(cell['source']))
                assert cell['outputs']==[] and cell['execution_count'] is None


def test_yolo_label_cache_artifacts_do_not_block_verify_but_extra_labels_do(tmp_path):
    root,_,_,_=fixture(tmp_path)
    for name in ('train.cache','val.cache','test.cache','train.cache.npy'):
        (root/'labels'/name).write_bytes(b'synthetic YOLO label cache')
    assert data_api().verify_car35(root)['images']==3
    (root/'labels/train/extra.txt').write_text('0 .5 .5 .1 .1\n')
    with pytest.raises(ValueError,match='inventory'):
        data_api().verify_car35(root)


def test_enabling_final_test_after_validation_keeps_both_evaluation_runs(tmp_path,monkeypatch):
    import functools
    import os
    import sys
    from test_supsign_training import clear_embedded_modules
    builder=importlib.import_module('training.notebooks.car35')
    cells={c['id']:''.join(c['source']) for c in builder.build_car35_train_notebook()['cells'] if c['cell_type']=='code'}
    root,_,_,_=fixture(tmp_path);work=tmp_path/'runtime'
    clear_embedded_modules(monkeypatch);monkeypatch.syspath_prepend(str(work/'unused'))
    context=dict(sys=sys,os=os)
    exec(cells['config'].replace("Path('/content/signsight_car35')",f'Path({str(work)!r})'),context)
    exec(cells['pipeline'],context)
    context.update(DATASET_ROOT=root,EPOCHS=2,BATCH=4,DEVICE='cpu')
    calls=[]
    context['train_car35']=functools.partial(context['train_car35'],yolo_factory=factory(calls))
    context['evaluate_car35']=functools.partial(context['evaluate_car35'],yolo_factory=factory(calls))
    exec(cells['train'],context);exec(cells['evaluate'],context)
    first=context['RUN_DIR']/'validation/evaluation_report.json'
    before=first.read_bytes()
    context['RUN_HELDOUT_TEST']=True
    exec(cells['evaluate'],context)
    assert first.read_bytes()==before
    assert calls[-1].options['split']=='test'
    assert len(list(context['RUN_DIR'].glob('validation*/evaluation_report.json')))==2
    assert len(list(context['RUN_DIR'].glob('test*/evaluation_report.json')))==1
