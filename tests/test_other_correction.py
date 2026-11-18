import hashlib

import pytest

from ai_engine.catalog import SignCatalog, ModelClassMapping, json_hash
from ai_engine.config import TAXONOMY
from backend.app.services.catalog_service import require_database_catalog
from test_accounts import headers, manager
from test_images_observations import owner, upload, detect, submit
from ai_engine.detection import Prediction
from test_images_observations import FakeDetector

OTHER = 1000000


def test_others_is_a_manual_option_without_changing_model_catalog_identity():
    catalog = SignCatalog()
    assert catalog.public_items()[-1] == {
        'new_id': OTHER, 'qcvn_code': 'OTHER', 'name_vi': 'Khác / Others'}
    assert catalog.by_id[OTHER]['name_vi'] == 'Khác / Others'
    assert catalog.sha256 == json_hash(TAXONOMY)
    assert len(catalog.items) == len(TAXONOMY)


@pytest.mark.parametrize('extra', [
    {'new_id': OTHER, 'qcvn_code': 'CUSTOM', 'name_vi': 'Collision'},
    {'new_id': 42, 'qcvn_code': 'OTHER', 'name_vi': 'Collision'},
])
def test_supplied_catalog_cannot_reassign_the_reserved_manual_identity(extra):
    with pytest.raises(ValueError, match='reserved'):
        SignCatalog([*TAXONOMY, extra])


def test_model_mapping_cannot_claim_a_manual_others_prediction(tmp_path):
    catalog = SignCatalog()
    weights = tmp_path / 'best.pt'
    weights.write_bytes(b'synthetic checkpoint')
    document = dict(schema_version=1, catalog_sha256=catalog.sha256,
        checkpoint_sha256=hashlib.sha256(weights.read_bytes()).hexdigest(),
        classes=[dict(model_class_id=0, model_name='Unknown', catalog_id=OTHER, reviewed=True)])
    with pytest.raises(ValueError, match='manual'):
        ModelClassMapping(document, catalog, weights)


def test_other_correction_keeps_ai_output_and_flows_through_review(client, application):
    auth = owner(client)
    image = upload(client, auth)
    run = detect(client, application, auth, image)
    invalid = submit(client, auth, image, run, proposed_class=OTHER, correction_reason='')
    assert invalid.status_code == 422
    assert client.get('/api/v1/me/observations', headers=auth).json()['total'] == 0
    submitted = submit(client, auth, image, run, proposed_class=OTHER,
                       correction_reason='Biển trong ảnh chưa có trong danh mục')
    assert submitted.status_code == 201, submitted.text
    observation = submitted.json()[0]
    assert observation['proposed_qcvn_code'] == 'OTHER'
    assert observation['proposed_name_vi'] == 'Khác / Others'
    assert observation['detection']['predicted_class'] == 0
    assert observation['detection']['confidence'] == .93
    reviewer = headers(manager(client, application)['access_token'])
    accepted = client.post('/api/v1/manager/observations/'+observation['id']+'/review',
                          headers=reviewer, json={'action': 'accept'})
    assert accepted.status_code == 200, accepted.text
    sign_id = accepted.json()['sign_record_id']
    sign = client.get('/api/v1/signs/'+sign_id, headers=auth).json()['sign']
    assert (sign['predicted_class'], sign['qcvn_code'], sign['name_vi']) == (OTHER, 'OTHER', 'Khác / Others')
    assert sign['confidence'] == 0 and sign['is_uncertain'] is True
    assert client.get('/api/v1/map/signs?class_id=1000000', headers=auth).json()['total'] == 1
    saved = client.get('/api/v1/inference-runs/'+run['id'], headers=auth).json()
    assert saved['detections'][0] == run['detections'][0]
    require_database_catalog(application.state.session_factory, application.state.catalog)
    history = client.get('/api/v1/me/observations?status=accepted',headers=auth).json()['items'][0]
    assert history['proposed_qcvn_code'] == 'OTHER' and history['sign_record_id'] == sign_id


def test_other_still_requires_a_real_owned_detection(client):
    auth = owner(client)
    image = upload(client, auth)
    response = client.post('/api/v1/observations', headers=auth, json={
        'image_id': image['id'], 'items': [dict(proposed_class=OTHER,
            correction_reason='Other sign', latitude=10.77, longitude=106.7)]})
    assert response.status_code == 422


def test_inference_cannot_invent_the_manual_others_class(client, application):
    auth = owner(client)
    image = upload(client, auth)
    application.state.detector = FakeDetector([Prediction(OTHER, .9, (1, 2, 30, 40))])
    response = client.post('/api/v1/images/'+image['id']+'/detect', headers=auth)
    assert response.status_code == 503
