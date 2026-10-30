import copy
import hashlib
import json

import pytest

from ai_engine.config import TAXONOMY
from ai_engine.catalog import SignCatalog, ModelClassMapping


def extended_items():
    return copy.deepcopy(TAXONOMY)+[{'new_id':10,'qcvn_code':'FIXTURE.10','name_vi':'Synthetic additional sign'}]


def mapping_data(catalog, checkpoint):
    return {'schema_version':1,'catalog_sha256':catalog.sha256,
            'checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            'classes':[{'model_class_id':0,'model_name':'No_entry','catalog_id':5,'reviewed':True},
                       {'model_class_id':1,'model_name':'Fixture_extra','catalog_id':10,'reviewed':True}]}


def test_catalog_extension_preserves_legacy_identity_and_ids():
    catalog=SignCatalog(extended_items())
    assert catalog.by_id[0]['qcvn_code']=='P.127 (50)'
    assert catalog.by_id[10]['name_vi']=='Synthetic additional sign'
    assert catalog.sha256==SignCatalog(list(reversed(extended_items()))).sha256
    invalid=extended_items();invalid[0]['qcvn_code']='FIXTURE.CHANGED'
    with pytest.raises(ValueError,match='legacy'):SignCatalog(invalid)
    with pytest.raises(ValueError,match='legacy'):SignCatalog(extended_items()[1:])
    invalid=extended_items();invalid[-1]['new_id']=0
    with pytest.raises(ValueError,match='Duplicate'):SignCatalog(invalid)


def test_explicit_mapping_translates_model_indices_into_stable_catalog_ids(tmp_path):
    catalog=SignCatalog(extended_items())
    checkpoint=tmp_path/'best.pt';checkpoint.write_bytes(b'synthetic weights')
    document=mapping_data(catalog,checkpoint)
    mapping=ModelClassMapping(document,catalog,checkpoint)
    assert mapping.names==['No_entry','Fixture_extra']
    assert mapping.catalog_id(0)==5 and mapping.catalog_id(1)==10
    assert mapping.sha256==ModelClassMapping(json.loads(json.dumps(document)),catalog,checkpoint).sha256


@pytest.mark.parametrize('problem', ['unreviewed','unknown','duplicate','checkpoint','catalog','class_order'])
def test_mapping_rejects_unreviewed_incompatible_or_ambiguous_entries(tmp_path,problem):
    catalog=SignCatalog(extended_items())
    checkpoint=tmp_path/'best.pt';checkpoint.write_bytes(b'fixture')
    document=mapping_data(catalog,checkpoint)
    if problem=='unreviewed':document['classes'][1]['reviewed']=False
    if problem=='unknown':document['classes'][1]['catalog_id']=999
    if problem=='duplicate':document['classes'][1]['catalog_id']=5
    if problem=='checkpoint':document['checkpoint_sha256']='0'*64
    if problem=='catalog':document['catalog_sha256']='0'*64
    if problem=='class_order':document['classes'][1]['model_class_id']=4
    with pytest.raises(ValueError):ModelClassMapping(document,catalog,checkpoint)


def test_detector_translates_indices_and_invalidates_an_edited_mapping(tmp_path,monkeypatch):
    import sys
    from types import SimpleNamespace
    from PIL import Image
    from ai_engine.detection import YoloDetector
    catalog=SignCatalog(extended_items())
    weights=tmp_path/'best.pt';weights.write_bytes(b'synthetic checkpoint')
    path=tmp_path/'mapping.json';path.write_text(json.dumps(mapping_data(catalog,weights)))
    class Tensor:
        def __init__(self,v):self.v=v
        def cpu(self):return self
        def tolist(self):return self.v
    class Model:
        task='detect';names={0:'No_entry',1:'Fixture_extra'}
        def __init__(self,*a,**k):pass
        def predict(self,**k):
            return [SimpleNamespace(boxes=SimpleNamespace(xyxy=Tensor([[1,2,20,22],[2,3,25,28]]),
                        conf=Tensor([.9,.8]),cls=Tensor([0.,1.])))]
    monkeypatch.setitem(sys.modules,'ultralytics',SimpleNamespace(YOLO=Model))
    detector=YoloDetector(weights,catalog=catalog,mapping_path=path)
    result=detector.predict(Image.new('RGB',(32,32)))
    assert [p.predicted_class for p in result.predictions]==[5,10]
    assert [p.model_class_id for p in result.predictions]==[0,1]
    assert result.catalog_sha256==catalog.sha256 and len(result.mapping_sha256)==64
    path.write_text('{}')
    assert detector.status()['ready'] is False
