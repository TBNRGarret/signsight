import io
import json

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from ai_engine.catalog import SignCatalog
from ai_engine.detection import DetectionResult, Prediction
from backend.app.core.settings import Settings
from backend.app.db.database import make_engine
from backend.app.main import create_app
from test_accounts import register,login,headers,manager
from test_catalog_mapping import extended_items
from test_navigation_map import add_sign


@pytest.fixture
def runtime(tmp_path):
    catalog=tmp_path/'catalog.json';catalog.write_text(json.dumps(extended_items()))
    engine=make_engine(f'sqlite:///{tmp_path / "runtime.db"}')
    app=create_app(engine,Settings(storage_root=tmp_path/'images',catalog_path=catalog))
    class Detector:
        def predict(self,image):
            return DetectionResult('fixture-model',[
                Prediction(5,.95,(1,1,20,20),0),Prediction(10,.9,(22,22,45,45),1)],
                mapping_sha256='a'*64,catalog_sha256=app.state.catalog.sha256)
    app.state.detector=Detector()
    with TestClient(app) as client: yield app,client
    engine.dispose()


def test_extended_catalog_flows_through_inference_correction_review_and_map(runtime):
    app,client=runtime
    legacy_id=add_sign(app)
    register(client);auth=headers(login(client)['access_token'])
    catalog=client.get('/api/v1/taxonomy',headers=auth).json()
    assert len(catalog['items'])==11 and catalog['items'][-1]['new_id']==10
    data=io.BytesIO();Image.new('RGB',(64,64),'red').save(data,format='PNG')
    image=client.post('/api/v1/images',headers=auth,files={'file':('test.png',data.getvalue(),'image/png')}).json()
    detected=client.post(f"/api/v1/images/{image['id']}/detect",headers=auth)
    assert detected.status_code==200,detected.text
    run=detected.json()
    assert run['mapping_sha256']=='a'*64 and run['catalog_sha256']==app.state.catalog.sha256
    assert [(d['predicted_class'],d['model_class_id']) for d in run['detections']]==[(5,0),(10,1)]
    assert run['detections'][1]['qcvn_code']=='FIXTURE.10'
    submitted=client.post('/api/v1/observations',headers=auth,json={'image_id':image['id'],'items':[
        {'detection_id':run['detections'][0]['id'],'latitude':10.777,'longitude':106.701,
         'proposed_class':10,'correction_reason':'Synthetic label correction'}]})
    assert submitted.status_code==201,submitted.text
    assert submitted.json()[0]['proposed_qcvn_code']=='FIXTURE.10'
    assert submitted.json()[0]['proposed_name_vi']=='Synthetic additional sign'
    staff=headers(manager(client,app)['access_token'])
    accepted=client.post(f"/api/v1/manager/observations/{submitted.json()[0]['id']}/review",
                        headers=staff,json={'action':'accept'})
    assert accepted.status_code==200,accepted.text
    sign_id=accepted.json()['sign_record_id']
    detail=client.get(f'/api/v1/signs/{sign_id}',headers=auth).json()['sign']
    assert detail['predicted_class']==10 and detail['qcvn_code']=='FIXTURE.10'
    assert client.get('/api/v1/map/signs?class_id=10',headers=auth).json()['total']==1
    assert client.get('/api/v1/map/signs?class_id=999',headers=auth).status_code==422
    assert client.get(f'/api/v1/signs/{legacy_id}',headers=auth).json()['sign']['predicted_class']==0
    report=client.post(f'/api/v1/signs/{legacy_id}/reports',headers=auth,json={
        'action':'correct_class','image_id':image['id'],'comment':'Synthetic corrected sign','proposed_class':10})
    assert report.status_code==201,report.text
    assert client.post(f"/api/v1/manager/reports/{report.json()['id']}/review",headers=staff,
                       json={'action':'accept'}).status_code==200
    assert client.get(f'/api/v1/signs/{legacy_id}',headers=auth).json()['sign']['predicted_class']==10
    stored=client.get(f"/api/v1/inference-runs/{run['id']}",headers=auth).json()
    assert stored['detections'][0]['predicted_class']==5  # Original output stays immutable.


def test_registered_custom_catalog_id_cannot_be_reassigned_on_restart(runtime,tmp_path):
    app,client=runtime
    items=extended_items();items[-1]['name_vi']='Changed meaning'
    path=tmp_path/'changed.json';path.write_text(json.dumps(items))
    other=create_app(app.state.session_factory.kw['bind'],Settings(storage_root=tmp_path/'images',catalog_path=path))
    with pytest.raises(RuntimeError,match='catalog'):
        with TestClient(other):pass


def test_registered_catalog_can_append_new_identity_without_changing_existing_ids(runtime,tmp_path):
    app,client=runtime
    items=extended_items()+[{'new_id':42,'qcvn_code':'FIXTURE.42','name_vi':'Synthetic extension'}]
    path=tmp_path/'appended.json';path.write_text(json.dumps(items))
    other=create_app(app.state.session_factory.kw['bind'],Settings(storage_root=tmp_path/'images',catalog_path=path))
    with TestClient(other):assert other.state.catalog.by_id[10]['qcvn_code']=='FIXTURE.10'


def test_unknown_catalog_correction_is_rejected_with_no_observation(runtime):
    app,client=runtime
    register(client);auth=headers(login(client)['access_token'])
    data=io.BytesIO();Image.new('RGB',(64,64),'blue').save(data,format='PNG')
    image=client.post('/api/v1/images',headers=auth,files={'file':('a.png',data.getvalue(),'image/png')}).json()
    run=client.post(f"/api/v1/images/{image['id']}/detect",headers=auth).json()
    response=client.post('/api/v1/observations',headers=auth,json={'image_id':image['id'],'items':[
        {'detection_id':run['detections'][0]['id'],'latitude':10.7,'longitude':106.7,
         'proposed_class':999,'correction_reason':'Unknown class'}]})
    assert response.status_code==422
    assert client.get('/api/v1/me/observations',headers=auth).json()['total']==0
    other=create_app(app.state.session_factory.kw['bind'],Settings(storage_root=app.state.settings.storage_root))
    with pytest.raises(RuntimeError,match='catalog'):
        with TestClient(other): pass
