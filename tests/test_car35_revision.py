"""Reviewed revisions retain the original archive, images, class order and splits."""
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from test_car35_handoff import fixture, factory
from training.data.car35_bundle import verify_car35
from training.data.common import digest_file
from training.data.label_patch import create_label_patch
from training.data.car35_revision import (
    preview_car35_revision, restore_car35_revision, pack_car35_revision,
)


def revision_fixture(tmp_path):
    root, archive, checksum, manifest_sha = fixture(tmp_path)
    original = json.loads((root/'manifest.json').read_text())
    val, test = original['images'][1:]
    edits = [dict(image_sha256=val['sha256'], line_index=2, from_class=2, to_class=1,
                  reviewed=True, reason='Reviewed original pixels: 50'),
             dict(image_sha256=test['sha256'], line_index=2, from_class=2, to_class=4,
                  action='remove_duplicate', retained_line_index=4,
                  reviewed=True, reason='Existing correct 80 box; remove duplicate')]
    patch_dir = tmp_path/'patch'
    create_label_patch(root, patch_dir, edits, expected_manifest_sha256=manifest_sha)
    patch_zip = tmp_path/'patch.zip'
    with ZipFile(patch_zip, 'w') as z:
        for p in sorted(patch_dir.rglob('*')):
            if p.is_file(): z.write(p, p.relative_to(patch_dir).as_posix())
    options = dict(expected_sha256=checksum, expected_source_manifest_sha256=manifest_sha,
                   expected_patch_sha256=digest_file(patch_zip), dataset_version='car35_reviewed_fixture')
    return root, archive, patch_zip, options


def test_revision_preview_and_restoration_produce_the_same_identity_without_mutating_sources(tmp_path):
    root, archive, patch, options = revision_fixture(tmp_path)
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    preview = preview_car35_revision(root, patch, **{k:v for k,v in options.items() if k!='expected_sha256'})
    output = tmp_path/'revised'
    info = restore_car35_revision(archive, patch, output, **options,
                                  expected_manifest_sha256=preview['manifest_sha256'])
    assert info['images']==3 and info['boxes']==104
    assert info['class_counts']['val'][1]==2 and info['class_counts']['val'].get(2, 0)==0
    assert info['split_images']==dict(train=1, val=1, test=1)
    assert info['names']==before_manifest_names(root)
    assert info['kind']=='car35_reviewed_development_v1'
    assert info['dataset_version']=='car35_reviewed_fixture'
    assert info['manifest_sha256']==preview['manifest_sha256']
    assert info['independent_field_test'] is False
    updated = json.loads((output/'manifest.json').read_text())
    original = json.loads(before[Path('manifest.json')])
    assert [(r['sha256'],r['split'],r['group']) for r in updated['images']] == [
        (r['sha256'],r['split'],r['group']) for r in original['images']]
    assert (output/'provenance/v4_manifest.json').read_bytes()==before[Path('manifest.json')]
    for r in original['images']:
        assert (output/r['image']).read_bytes()==before[Path(r['image'])]
    assert {p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}==before
    assert digest_file(archive)==options['expected_sha256']
    assert digest_file(patch)==options['expected_patch_sha256']
    assert not list(output.rglob('*.cache'))
    with pytest.raises(FileExistsError): restore_car35_revision(archive, patch, output, **options)


def before_manifest_names(root):
    return json.loads((root/'manifest.json').read_text())['names']


@pytest.mark.parametrize('field', ['expected_sha256','expected_source_manifest_sha256','expected_patch_sha256'])
def test_revision_rejects_wrong_input_identity_atomically(tmp_path, field):
    _, archive, patch, options = revision_fixture(tmp_path)
    options[field]='0'*64
    with pytest.raises(ValueError): restore_car35_revision(archive, patch, tmp_path/'bad', **options)
    assert not (tmp_path/'bad').exists()


def test_tampered_patch_labels_cannot_override_reviewed_edits(tmp_path):
    _, archive, patch, options = revision_fixture(tmp_path)
    with ZipFile(patch) as source:
        entries={n:source.read(n) for n in source.namelist()}
    name=next(n for n in entries if n.startswith('labels/'))
    entries[name]=b'0 .5 .5 .2 .2\n'
    with ZipFile(patch,'w') as z:
        for n,b in entries.items(): z.writestr(n,b)
    options['expected_patch_sha256']=digest_file(patch)
    with pytest.raises(ValueError, match='patch|Patch|reviewed'):
        restore_car35_revision(archive,patch,tmp_path/'bad',**options)
    assert not (tmp_path/'bad').exists()


def test_unsafe_patch_zip_is_rejected_before_restoring_large_data(tmp_path):
    _, archive, patch, options = revision_fixture(tmp_path)
    with ZipFile(patch,'a') as z: z.writestr('../escape.txt','bad')
    options['expected_patch_sha256']=digest_file(patch)
    with pytest.raises(ValueError, match='Unsafe|unsafe'):
        restore_car35_revision(archive,patch,tmp_path/'bad',**options)
    assert not (tmp_path/'bad').exists() and not (tmp_path/'escape.txt').exists()


def test_revised_manifest_cannot_regroup_images_or_forge_counts(tmp_path):
    _, archive, patch, options = revision_fixture(tmp_path)
    output=tmp_path/'revised';restore_car35_revision(archive,patch,output,**options)
    path=output/'manifest.json';manifest=json.loads(path.read_text())
    manifest['images'][0]['group']='invented'
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='revision|Revision|provenance'):
        verify_car35(output)


@pytest.mark.parametrize('version', ['../bad','', 'car35/escape'])
def test_revision_requires_a_safe_new_version(tmp_path, version):
    _, archive, patch, options=revision_fixture(tmp_path)
    options['dataset_version']=version
    with pytest.raises(ValueError): restore_car35_revision(archive,patch,tmp_path/'bad',**options)
    assert not (tmp_path/'bad').exists()


def test_revision_roundtrip_and_training_do_not_reuse_v4_run_identity(tmp_path):
    from training.data.car35_bundle import restore_car35_bundle
    from training.experiments.car35 import train_car35, export_car35_run
    root, archive, patch, options=revision_fixture(tmp_path)
    run=tmp_path/'run';calls=[]
    train_car35(root,run,epochs=2,yolo_factory=factory(calls))
    output=tmp_path/'revised';info=restore_car35_revision(archive,patch,output,**options)
    with pytest.raises(ValueError,match='dataset changed'):
        train_car35(output,run,epochs=2,resume=True,yolo_factory=factory(calls))
    bundle=tmp_path/'revised.zip';packed=pack_car35_revision(output,bundle)
    assert packed['manifest_sha256']==info['manifest_sha256']
    assert packed['zip_sha256']==digest_file(bundle)
    assert restore_car35_bundle(bundle,tmp_path/'restored',expected_sha256=packed['zip_sha256'],
        expected_manifest_sha256=info['manifest_sha256'])['boxes']==104
    new_run=tmp_path/'new-run';train_car35(output,new_run,epochs=2,yolo_factory=factory(calls))
    exported=export_car35_run(new_run,output,tmp_path/'result.zip')
    with ZipFile(exported) as z:
        assert 'dataset/provenance/v4_manifest.json' in z.namelist()
        assert 'dataset/provenance/label_patch.json' in z.namelist()
        assert json.loads(z.read('handoff.json'))['dataset']['manifest_sha256']==info['manifest_sha256']


def test_revision_pack_excludes_runtime_label_caches(tmp_path):
    _,archive,patch,options=revision_fixture(tmp_path)
    root=tmp_path/'revised';restore_car35_revision(archive,patch,root,**options)
    (root/'labels/train.cache').write_bytes(b'runtime absolute paths')
    archive=tmp_path/'packed.zip';pack_car35_revision(root,archive)
    with ZipFile(archive) as z: assert 'labels/train.cache' not in z.namelist()


def test_revision_disk_full_does_not_publish_partial_dataset(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import training.data.car35_revision as module
    _,archive,patch,options=revision_fixture(tmp_path)
    monkeypatch.setattr(module.shutil,'disk_usage',lambda p:SimpleNamespace(free=0))
    with pytest.raises(ValueError,match='disk space'):
        restore_car35_revision(archive,patch,tmp_path/'bad',**options)
    assert not (tmp_path/'bad').exists()
    assert not list(tmp_path.glob('.car35-*'))


@pytest.mark.parametrize('stage',['eda','train'])
def test_standalone_notebooks_materialize_the_reviewed_revision_before_using_it(tmp_path,monkeypatch,stage):
    import functools
    import importlib
    import os
    import shutil
    import sys
    from test_supsign_training import clear_embedded_modules
    root,archive,patch,options=revision_fixture(tmp_path)
    preview=preview_car35_revision(root,patch,**{k:v for k,v in options.items() if k!='expected_sha256'})
    builder=importlib.import_module('training.notebooks.car35')
    notebook=builder.build_car35_eda_notebook() if stage=='eda' else builder.build_car35_train_notebook()
    cells={c['id']:''.join(c['source']) for c in notebook['cells'] if c['cell_type']=='code'}
    work=tmp_path/'runtime'
    clear_embedded_modules(monkeypatch);monkeypatch.syspath_prepend(str(work/'unused'))
    context=dict(sys=sys,os=os)
    exec(cells['config'].replace("Path('/content/signsight_car35')",f'Path({str(work)!r})'),context)
    context.update(SOURCE_URL='source-fixture',DATASET_SHA256=options['expected_sha256'],
        EXPECTED_MANIFEST_SHA256=options['expected_source_manifest_sha256'],
        APPLY_REVIEWED_PATCH=True,PATCH_URL='patch-fixture',PATCH_SHA256=options['expected_patch_sha256'],
        REVISED_DATASET_VERSION=options['dataset_version'],EXPECTED_REVISED_MANIFEST_SHA256=preview['manifest_sha256'],
        DOWNLOAD_RESULTS=False,EXPORT_REVISED_DATASET=False,DEVICE='cpu',EPOCHS=2)
    exec(cells['pipeline'],context)
    assert 'training/data/car35_revision.py' in context['TRAINING_FILES']
    def transport(source,target,**kwargs):
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(patch if source=='patch-fixture' else archive,target)
        return target
    context['download_drive_zip']=transport
    exec(cells['prepare'],context)
    assert context['dataset_info']['kind']=='car35_reviewed_development_v1'
    assert context['dataset_info']['manifest_sha256']==preview['manifest_sha256']
    if stage=='train':
        calls=[]
        context['train_car35']=functools.partial(context['train_car35'],yolo_factory=factory(calls))
        context['evaluate_car35']=functools.partial(context['evaluate_car35'],yolo_factory=factory(calls))
        exec(cells['train'],context);exec(cells['evaluate'],context)
    else:
        import matplotlib
        matplotlib.use('Agg');exec(cells['eda'],context)
        context['EXPORT_REVISED_DATASET']=True
    exec(cells['export'],context)
    assert context['RESULT_ZIP'].is_file()
    if stage=='eda':
        assert context['PREPARED_ZIP'].is_file()
        assert context['prepared_handoff']['boxes']==104
        assert context['prepared_handoff']['manifest_sha256']==preview['manifest_sha256']
    first=context['dataset_info']['manifest_sha256']
    context['download_drive_zip']=lambda *a,**k:pytest.fail('Verified revision must be reused without download')
    exec(cells['prepare'],context)
    assert context['dataset_info']['manifest_sha256']==first


def test_notebook_refuses_missing_patch_link_before_large_source_download(tmp_path):
    import os
    import sys
    from training.notebooks.car35 import build_car35_train_notebook
    cells={c['id']:''.join(c['source']) for c in build_car35_train_notebook()['cells'] if c['cell_type']=='code'}
    context=dict(sys=sys,os=os)
    exec(cells['config'].replace("Path('/content/signsight_car35')",f'Path({str(tmp_path)!r})'),context)
    context.update(SOURCE_URL='source-id',download_drive_zip=lambda *a,**k:pytest.fail('Do not download yet'))
    with pytest.raises(AssertionError,match='PATCH_URL'): exec(cells['prepare'],context)
