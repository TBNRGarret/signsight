"""Fine-tune uses reviewed labels, fixed holdouts and synthetic model calls."""
import csv
import importlib
import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image

from test_car35_handoff import fixture, factory
from training.data.common import CAR35, digest_file


def api():
    return importlib.import_module('training.data.finetune')


def review_zip(tmp_path, root, *, split='train', reviewed='yes', label=None, new=False):
    manifest = json.loads((root/'manifest.json').read_text())
    row = next(r for r in manifest['images'] if r['split'] == split)
    image = root/row['image']
    if new:
        image = tmp_path/'new.png'
        Image.effect_noise((32, 24), 40).convert('RGB').save(image)
    target = tmp_path/'review.zip'
    with ZipFile(target, 'w') as z:
        z.writestr('review.json', json.dumps(dict(schema_version=1, names=CAR35,
            base_manifest_sha256=digest_file(root/'manifest.json'))))
        z.write(image, 'images/example.png')
        original = (root/row['label']).read_text()
        z.writestr('labels/example.txt', label if label is not None else original.replace('.2 .2', '.3 .3'))
        z.writestr('review.csv', 'image,label,split,group,reviewed\n'
            f'images/example.png,labels/example.txt,{split},{"new_capture" if new else row["group"]},{reviewed}\n')
    return target


def test_review_corrections_keep_images_splits_and_test_immutable(tmp_path):
    base, _, _, _ = fixture(tmp_path)
    before = {p.relative_to(base):p.read_bytes() for p in base.rglob('*') if p.is_file()}
    archive = review_zip(tmp_path, base)
    output = tmp_path/'fine'
    info = api().prepare_finetune_dataset(base, archive, output)
    assert info['images'] == 3
    manifest = json.loads((output/'manifest.json').read_text())
    assert manifest['finetune_review']['changed_labels'] == {'train':1, 'val':0}
    assert manifest['finetune_review']['review_zip_sha256'] == digest_file(archive)
    for relative, content in before.items():
        assert (base/relative).read_bytes() == content
        if relative.parts[:2] in [('images','test'), ('labels','test')]:
            assert (output/relative).read_bytes() == content


@pytest.mark.parametrize('prefix', ['car35_training_labels_to_review/', 'exports/reviewed/'])
def test_review_accepts_one_wrapped_pack_without_changing_relative_csv_paths(tmp_path, prefix):
    base, _, _, _ = fixture(tmp_path)
    archive = review_zip(tmp_path, base)
    with ZipFile(archive) as z: entries = {prefix+n:z.read(n) for n in z.namelist()}
    with ZipFile(archive, 'w') as z:
        z.writestr(prefix, b'')
        for n, content in entries.items(): z.writestr(n, content)
    api().prepare_finetune_dataset(base, archive, tmp_path/'fine')
    result = json.loads((tmp_path/'fine/manifest.json').read_text())
    assert result['finetune_review']['changed_labels']['train'] == 1
    assert result['finetune_review']['review_zip_sha256'] == digest_file(archive)


@pytest.mark.parametrize('case', ['missing_csv', 'two_packs', 'missing_image', 'oversized'])
def test_review_layout_errors_explain_the_problem_without_publishing(tmp_path, case):
    base, _, _, _ = fixture(tmp_path)
    archive = review_zip(tmp_path, base)
    with ZipFile(archive) as z: entries = {n:z.read(n) for n in z.namelist()}
    if case == 'missing_csv': entries.pop('review.csv')
    if case == 'two_packs': entries.update({'copy/'+n:b for n,b in list(entries.items())})
    if case == 'missing_image': entries.pop('images/example.png')
    if case == 'oversized': entries['review.csv'] = b' ' * (8*1024**2+1)
    with ZipFile(archive, 'w') as z:
        for n,b in entries.items(): z.writestr(n,b)
    message = {'missing_csv':'review.csv', 'two_packs':'multiple',
               'missing_image':'images/example.png', 'oversized':'8 MiB'}[case]
    with pytest.raises(ValueError, match=message):
        api().prepare_finetune_dataset(base, archive, tmp_path/'fine')
    assert not (tmp_path/'fine').exists()


@pytest.mark.parametrize('case', ['pending', 'test', 'wrong_base', 'bad_bbox', 'unsafe', 'reversed_names'])
def test_review_rejects_invalid_or_ineffective_changes_without_publication(tmp_path, case):
    base, _, _, _ = fixture(tmp_path)
    kwargs = {}
    if case == 'pending': kwargs['reviewed'] = 'no'
    if case == 'test': kwargs['split'] = 'test'
    if case == 'bad_bbox': kwargs['label'] = '0 .5 .5 2 .2\n'
    archive = review_zip(tmp_path, base, **kwargs)
    if case in ('wrong_base','unsafe','reversed_names'):
        with ZipFile(archive) as z: entries = {n:z.read(n) for n in z.namelist()}
        metadata = json.loads(entries['review.json'])
        if case == 'wrong_base': metadata['base_manifest_sha256'] = '0'*64
        if case == 'reversed_names': metadata['names'] = CAR35[::-1]
        entries['review.json'] = json.dumps(metadata).encode()
        if case == 'unsafe': entries['../escape'] = b'bad'
        with ZipFile(archive,'w') as z:
            for n,b in entries.items(): z.writestr(n,b)
    with pytest.raises(ValueError): api().prepare_finetune_dataset(base, archive, tmp_path/'fine')
    assert not (tmp_path/'fine').exists()
    assert not (tmp_path/'escape').exists()


def test_reviewed_unchanged_training_labels_can_be_finetuned(tmp_path):
    base, _, _, _ = fixture(tmp_path)
    label = next((base/'labels/train').glob('*.txt')).read_text()
    archive = review_zip(tmp_path, base, label=label)
    api().prepare_finetune_dataset(base, archive, tmp_path/'fine')
    review = json.loads((tmp_path/'fine/manifest.json').read_text())['finetune_review']
    assert review['reviewed_by_split']['train'] == 1
    assert review['unchanged_labels']['train'] == 1
    assert review['changed_labels']['train'] == review['added_images']['train'] == 0


def test_new_capture_is_added_but_cross_split_near_duplicates_are_rejected(tmp_path):
    base, _, _, _ = fixture(tmp_path)
    archive = review_zip(tmp_path, base, new=True)
    info = api().prepare_finetune_dataset(base, archive, tmp_path/'fine')
    assert info['images'] == 4 and info['split_images']['train'] == 2
    # Different bytes, identical dHash to flat-color held-out fixture images.
    with ZipFile(archive) as z: entries = {n:z.read(n) for n in z.namelist()}
    image = tmp_path/'near.png'; Image.new('RGB',(33,25),(40,50,60)).save(image)
    entries['images/example.png'] = image.read_bytes()
    with ZipFile(archive,'w') as z:
        for n,b in entries.items():z.writestr(n,b)
    with pytest.raises(ValueError,match='near|holdout'):
        api().prepare_finetune_dataset(base, archive, tmp_path/'leaked')


def test_review_pack_is_bound_to_base_and_pending_by_default(tmp_path):
    base, _, _, _ = fixture(tmp_path)
    target = api().create_review_pack(base, tmp_path/'to_review.zip', per_class=1)
    with ZipFile(target) as z:
        metadata = json.loads(z.read('review.json'))
        rows = list(csv.DictReader(z.read('review.csv').decode().splitlines()))
        assert metadata['base_manifest_sha256'] == digest_file(base/'manifest.json')
        assert rows and all(r['split']=='train' and r['reviewed']=='no' for r in rows)
        assert len(rows) == 1  # One image can contain multiple priority classes.


def test_finetune_starts_from_bound_checkpoint_with_low_lr_not_resume(tmp_path):
    base, _, _, _ = fixture(tmp_path)
    root = tmp_path/'fine'; api().prepare_finetune_dataset(base, review_zip(tmp_path,base), root)
    checkpoint = tmp_path/'baseline.pt';checkpoint.write_bytes(b'synthetic-baseline')
    module = importlib.import_module('training.experiments.finetune')
    calls=[]
    best = module.finetune_car35(checkpoint, root, tmp_path/'run',
        expected_checkpoint_sha256=digest_file(checkpoint), epochs=2, device='cpu', yolo_factory=factory(calls))
    assert best.is_file() and calls[0].weights == str(checkpoint.resolve())
    options=calls[0].options
    assert options['resume'] is False and options['optimizer']=='AdamW' and options['lr0']==.0003
    assert options['fliplr']==options['flipud']==0 and options['warmup_bias_lr']==0
    request=json.loads((tmp_path/'run/training_request.json').read_text())
    assert request['settings']['initial_checkpoint_sha256']==digest_file(checkpoint)
    with pytest.raises(ValueError,match='checkpoint'):
        module.finetune_car35(checkpoint, root, tmp_path/'bad', expected_checkpoint_sha256='0'*64,
            yolo_factory=factory(calls))
    assert len(calls)==1 and not (tmp_path/'bad').exists()


def test_controlled_pilot_accepts_reviewed_unchanged_labels_and_records_options(tmp_path):
    base, _, _, _ = fixture(tmp_path)
    label = next((base/'labels/train').glob('*.txt')).read_text()
    root = tmp_path/'fine'
    api().prepare_finetune_dataset(base, review_zip(tmp_path,base,label=label), root)
    checkpoint=tmp_path/'baseline.pt';checkpoint.write_bytes(b'baseline')
    calls=[]
    module=importlib.import_module('training.experiments.finetune')
    module.finetune_car35(checkpoint,root,tmp_path/'pilot',expected_checkpoint_sha256=digest_file(checkpoint),
                         device='cpu',yolo_factory=factory(calls))
    options=calls[0].options
    assert options['epochs']==15 and options['patience']==5
    assert options['optimizer']=='AdamW' and options['lr0']==.0003
    assert options['fliplr']==options['flipud']==0 and options['mosaic']==.1
    assert options['cos_lr'] is True and options['resume'] is False
    request=json.loads((tmp_path/'pilot/training_request.json').read_text())
    assert request['review']['unchanged_labels']['train']==1
    assert request['settings']['mosaic']==.1 and request['settings']['patience']==5


def test_checkpoint_loader_extracts_only_pinned_best_and_preserves_existing_file(tmp_path):
    module=importlib.import_module('training.experiments.finetune')
    archive=tmp_path/'results.zip'
    with ZipFile(archive,'w') as z:
        z.writestr('run/weights/best.pt',b'best');z.writestr('../ignored',b'not extracted')
    expected=__import__('hashlib').sha256(b'best').hexdigest()
    target=module.restore_initial_checkpoint(archive,tmp_path/'best.pt',expected_sha256=expected)
    assert target.read_bytes()==b'best' and not (tmp_path.parent/'ignored').exists()
    with pytest.raises(ValueError,match='checkpoint'):
        module.restore_initial_checkpoint(archive,target,expected_sha256='0'*64)
    assert target.read_bytes()==b'best'


def test_existing_holdout_cannot_be_moved_into_training(tmp_path):
    base,_,_,_=fixture(tmp_path)
    archive=review_zip(tmp_path,base,split='val')
    with ZipFile(archive) as z: entries={n:z.read(n) for n in z.namelist()}
    entries['review.csv']=entries['review.csv'].replace(b',val,',b',train,')
    with ZipFile(archive,'w') as z:
        for n,b in entries.items():z.writestr(n,b)
    with pytest.raises(ValueError,match='move'):
        api().prepare_finetune_dataset(base,archive,tmp_path/'fine')


def test_new_val_capture_group_cannot_also_appear_in_train(tmp_path):
    base,_,_,_=fixture(tmp_path)
    archive=review_zip(tmp_path,base,new=True)
    image=tmp_path/'other.png';Image.effect_noise((32,24),60).convert('RGB').save(image)
    with ZipFile(archive) as z:entries={n:z.read(n) for n in z.namelist()}
    entries['images/other.png']=image.read_bytes();entries['labels/other.txt']=entries['labels/example.txt']
    entries['review.csv']+=b'images/other.png,labels/other.txt,val,new_capture,yes\n'
    with ZipFile(archive,'w') as z:
        for n,b in entries.items():z.writestr(n,b)
    with pytest.raises(ValueError,match='group'):
        api().prepare_finetune_dataset(base,archive,tmp_path/'fine')
