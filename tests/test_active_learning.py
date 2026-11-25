import csv
import io
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from PIL import Image

from test_car35_handoff import fixture
from test_car35_finetune import review_zip
from training.data.common import CAR35, digest_file


def model_factory():
    class Value:
        def __init__(self,value):self.value=value
        def item(self):return self.value
        def tolist(self):return self.value
    def box(cls,conf):return SimpleNamespace(cls=Value(cls),conf=Value(conf),xyxy=[Value([2,2,20,20])])
    class Model:
        task='detect';names=dict(enumerate(CAR35));calls=0
        def __init__(self,path):pass
        def predict(self,image,**kwargs):
            results=[[box(0,.95)],[],[box(1,.2),box(2,.19)]]
            result=results[self.calls%3];self.calls+=1
            return [SimpleNamespace(boxes=result)]
    return Model


def test_active_pack_ranks_misses_keeps_exploration_and_never_reviews_pseudo_labels(tmp_path):
    from training.experiments.active_learning import build_active_review_pack
    base,_,_,_=fixture(tmp_path)
    existing=review_zip(tmp_path,base)
    pool=tmp_path/'pool';pool.mkdir()
    for name in ('a','b','c'):Image.effect_noise((32,24),50).convert('RGB').save(pool/(name+'.png'))
    (pool/'a-copy.png').write_bytes((pool/'a.png').read_bytes())
    heldout=next((base/'images/val').glob('*'));(pool/'0-holdout.png').write_bytes(heldout.read_bytes())
    checkpoint=tmp_path/'base.pt';checkpoint.write_bytes(b'baseline')
    before=digest_file(existing)
    output=tmp_path/'active.zip'
    summary=build_active_review_pack(pool,existing,base/'manifest.json',checkpoint,output,
        expected_checkpoint_sha256=digest_file(checkpoint),limit=2,yolo_factory=model_factory())
    assert summary['selected']==2 and summary['scanned']==3
    assert summary['excluded']['heldout_exact_duplicate']==1
    assert summary['excluded']['pool_exact_duplicate']==1
    assert digest_file(existing)==before
    with ZipFile(output) as z:
        rows=list(csv.DictReader(io.StringIO(z.read('review.csv').decode('utf-8-sig'))))
        assert len(rows)==3  # Existing reviewed row and two new candidates.
        assert rows[0]['reviewed']=='yes'
        assert all(r['reviewed']=='no' and r['group']=='' and r['split']=='train' for r in rows[1:])
        selection=json.loads(z.read('active_learning.json'))
        assert any(r['reason']=='no_detection' for r in selection['selected_images'])
        assert any(r['selection']=='exploration' for r in selection['selected_images'])
        assert json.loads(z.read('review.json'))['base_manifest_sha256']==digest_file(base/'manifest.json')
        assert all(r['image'] in z.namelist() and r['label'] in z.namelist() for r in rows)
    second=tmp_path/'round2.zip'
    build_active_review_pack(pool,output,base/'manifest.json',checkpoint,second,
        expected_checkpoint_sha256=digest_file(checkpoint),limit=2,yolo_factory=model_factory())
    with ZipFile(second) as z:
        assert len(z.namelist())==len(set(z.namelist()))


def test_active_pack_requires_bound_base_and_never_overwrites_output(tmp_path):
    from training.experiments.active_learning import build_active_review_pack
    base,_,_,_=fixture(tmp_path);existing=review_zip(tmp_path,base)
    pool=tmp_path/'pool';pool.mkdir()
    checkpoint=tmp_path/'base.pt';checkpoint.write_bytes(b'baseline')
    output=tmp_path/'active.zip';output.write_bytes(b'keep')
    with pytest.raises(FileExistsError):
        build_active_review_pack(pool,existing,base/'manifest.json',checkpoint,output,
            expected_checkpoint_sha256=digest_file(checkpoint),yolo_factory=model_factory())
    assert output.read_bytes()==b'keep'
    output.unlink()
    with pytest.raises(ValueError,match='checkpoint'):
        build_active_review_pack(pool,existing,base/'manifest.json',checkpoint,output,
            expected_checkpoint_sha256='0'*64,yolo_factory=model_factory())
