"""Retired writers must not destroy readable inference history."""
from ai_engine.detection import DetectionResult, Prediction
from backend.app.db.models import UploadedImage
from backend.app.services.observation_service import persist_run
from test_images_observations import owner, upload, picture


def test_classification_is_retired_after_authentication(client):
    auth = owner(client)
    image = upload(client, auth)
    path = f"/api/v1/images/{image['id']}/classify"
    assert client.post(path).status_code == 401
    assert client.post(path, headers=auth).status_code == 410
    assert client.post('/api/v1/signs/classify', headers=auth,
                       files={'file': ('sign.png', picture(), 'image/png')}).status_code == 410
    status = client.get('/api/v1/ai/status', headers=auth).json()
    assert status['cnn']['retired'] is True and status['cnn']['ready'] is False


def test_retiring_classification_preserves_private_cnn_history(client, application):
    auth = owner(client); image = upload(client, auth)
    with application.state.session_factory() as db:
        stored = db.get(UploadedImage, image['id'])
        run = persist_run(db, stored, 'cnn', DetectionResult('sha256:legacy', [Prediction(0, .9, None)]), application.state.catalog)
        run_id = run.id
    path = f'/api/v1/inference-runs/{run_id}'
    assert client.get(path).status_code == 401
    response = client.get(path, headers=auth)
    assert response.status_code == 200
    assert response.json()['engine'] == 'cnn'
    assert response.json()['task'] == 'classification'
    assert response.json()['detections'][0]['bbox'] is None

