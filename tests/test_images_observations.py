import hashlib
import io
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from PIL import Image

from ai_engine.detection import DetectionResult, Prediction, YoloDetector
from backend.app.db.models import Evidence, ImageDetection, InferenceRun, Observation, SignRecord, UploadedImage
from backend.app.services.image_store import ImageStore, sanitize_image
from backend.app.services.lifecycle_service import check_and_update_lifecycle_status, process_revalidation
from test_accounts import register, login, headers, manager


def picture(size=(100, 80), format="PNG", **kwargs):
    output = io.BytesIO()
    Image.new("RGB", size, "red").save(output, format=format, **kwargs)
    return output.getvalue()


def owner(client):
    register(client)
    return headers(login(client)["access_token"])


def upload(client, auth, data=None, mime="image/png"):
    response = client.post("/api/v1/images", headers=auth, files={"file": ("../../evil.png", picture() if data is None else data, mime)})
    assert response.status_code == 201, response.text
    return response.json()


class FakeDetector:
    def __init__(self, predictions=None):
        self.predictions = [Prediction(0, .93, (1,2,30,40)), Prediction(9, .5, (40,5,95,70))] if predictions is None else predictions

    def predict(self, image):
        return DetectionResult("sha256:" + "a" * 64, self.predictions)


def detect(client, application, auth, image, predictions=None):
    application.state.detector = FakeDetector(predictions)
    response = client.post(f"/api/v1/images/{image['id']}/detect", headers=auth)
    assert response.status_code == 200, response.text
    return response.json()


def submit(client, auth, image, run, **change):
    payload = {"image_id": image["id"], "items": [{"detection_id": row["id"], "latitude": 10.78 + i*.001,
               "longitude": 106.70, "location_source": "manual_pin", **change} for i,row in enumerate(run["detections"])]}
    return client.post("/api/v1/observations", headers=auth, json=payload)


def test_own_observations_filter_status_before_count_and_pagination(client, application):
    auth = owner(client)
    image = upload(client, auth)
    initial = submit(client, auth, image, detect(client, application, auth, image)).json()
    reviewer = headers(manager(client, application)["access_token"])
    for row, action in zip(initial, ("accept", "reject")):
        response = client.post(f'/api/v1/manager/observations/{row["id"]}/review',
                               headers=reviewer, json={"action": action, "comment": "Reviewed in test"})
        assert response.status_code == 200
    pending = submit(client, auth, image, detect(client, application, auth, image)).json()
    register(client, "bob")
    bob = headers(login(client, "bob")["access_token"])
    bob_image = upload(client, bob)
    assert submit(client, bob, bob_image, detect(client, application, bob, bob_image)).status_code == 201

    expected = {"accepted": {initial[0]["id"]}, "rejected": {initial[1]["id"]},
                "pending": {row["id"] for row in pending}}
    for status, ids in expected.items():
        response = client.get('/api/v1/me/observations', headers=auth, params={"status": status})
        assert response.status_code == 200
        result = response.json()
        assert result['total'] == len(ids)
        assert {row['id'] for row in result['items']} == ids
        assert all(row['status'] == status for row in result['items'])
    page = client.get('/api/v1/me/observations?status=pending&offset=1&limit=1', headers=auth).json()
    assert page['total'] == 2 and len(page['items']) == 1 and page['offset'] == 1
    assert page['items'][0]['id'] in expected['pending']
    assert client.get('/api/v1/me/observations', headers=auth).json()['total'] == 4


def test_own_observation_status_filter_validates_values_and_empty_results(client):
    auth = owner(client)
    assert client.get('/api/v1/me/observations?status=unknown', headers=auth).status_code == 422
    result = client.get('/api/v1/me/observations?status=rejected', headers=auth).json()
    assert result['items'] == [] and result['total'] == 0
    assert client.get('/api/v1/me/observations?status=pending').status_code == 401


def test_upload_sanitizes_and_preserves_orientation_without_metadata(client, application):
    auth = owner(client)
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "private camera metadata"
    image = upload(client, auth, picture((60,40), "JPEG", exif=exif), "image/jpeg")
    assert (image["width"],image["height"]) == (40,60)
    assert "storage_key" not in image
    content = client.get(image["content_url"], headers=auth)
    assert content.status_code == 200 and content.headers["cache-control"] == "no-store"
    assert hashlib.sha256(content.content).hexdigest() == image["sha256"]
    with Image.open(io.BytesIO(content.content)) as decoded:
        assert not decoded.getexif()
    with application.state.session_factory() as db:
        row = db.get(UploadedImage, image["id"])
        assert application.state.image_store.path(row.storage_key).is_file()


@pytest.mark.parametrize("data,mime,expected", [(b"", "image/png",400), (b"<svg></svg>","image/png",400),
    (picture(),"image/jpeg",415), (picture(format="GIF"),"image/gif",415)])
def test_bad_uploads_leave_no_rows_or_files(client, application, data, mime, expected):
    auth = owner(client)
    response = client.post("/api/v1/images", headers=auth, files={"file": ("bad",data,mime)})
    assert response.status_code == expected
    with application.state.session_factory() as db:
        assert db.query(UploadedImage).count() == 0
    assert not list(application.state.settings.storage_root.glob("*.jpg"))


def test_limits_and_storage_path_safety(tmp_path):
    with pytest.raises(HTTPException) as error:
        sanitize_image(picture(), "image/png", 100)
    assert error.value.status_code == 413
    with pytest.raises(HTTPException):
        ImageStore(tmp_path).path("../../outside.jpg")


def test_image_owner_acl_and_missing_detector(client, application):
    auth = owner(client)
    image = upload(client,auth)
    register(client,"bob")
    bob = headers(login(client,"bob")["access_token"])
    reviewer = headers(manager(client,application)["access_token"])
    for other in (bob,reviewer):
        for suffix in ("", "/content"):
            assert client.get(f"/api/v1/images/{image['id']}{suffix}",headers=other).status_code == 404
        assert client.post(f"/api/v1/images/{image['id']}/detect",headers=other).status_code == 404
    assert client.get(image["content_url"]).status_code == 401
    application.state.detector = YoloDetector(application.state.settings.storage_root / "absent.pt")
    assert client.post(f"/api/v1/images/{image['id']}/detect",headers=auth).status_code == 503
    with application.state.session_factory() as db:
        assert db.query(InferenceRun).count() == 0


def test_multi_detection_moderation_provenance_and_30_day_freshness(client, application):
    auth = owner(client)
    image = upload(client,auth)
    run = detect(client,application,auth,image)
    assert len(run["detections"]) == 2 and run["detections"][1]["is_uncertain"]
    rows = submit(client,auth,image,run).json()
    assert len(rows) == 2 and all(row["status"] == "pending" for row in rows)
    with application.state.session_factory() as db:
        assert db.query(SignRecord).count() == 0
    path = f"/api/v1/manager/observations/{rows[0]['id']}/review"
    assert client.post(path,headers=auth,json={"action":"accept"}).status_code == 403
    reviewer = headers(manager(client,application)["access_token"])
    assert client.get(image["content_url"],headers=reviewer).status_code == 200
    accepted = client.post(path,headers=reviewer,json={"action":"accept","comment":"Checked position"})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["reviewed_by"] != rows[0]["created_by"]
    assert client.post(path,headers=reviewer,json={"action":"accept"}).status_code == 409
    rejected = client.post(f"/api/v1/manager/observations/{rows[1]['id']}/review",headers=reviewer,json={"action":"reject"})
    assert rejected.json()["status"] == "rejected" and rejected.json()["sign_record_id"] is None
    register(client,"bob")
    bob = headers(login(client,"bob")["access_token"])
    assert client.get(image["content_url"],headers=bob).status_code == 200
    assert client.get(f"/api/v1/observations/{rows[0]['id']}",headers=bob).status_code == 404
    assert client.get(f"/api/v1/inference-runs/{run['id']}",headers=bob).status_code == 404
    with application.state.session_factory() as db:
        record = db.get(SignRecord,accepted.json()["sign_record_id"])
        assert record.confirmation_days == 30 and record.verification_status == "current"
        assert record.expires_at-record.last_confirmed_at == timedelta(days=30)
        assert record.created_by == rows[0]["created_by"] and record.confidence == .93
        evidence = db.query(Evidence).one()
        assert evidence.image_hash == image["sha256"] and evidence.file_size_bytes == image["size_bytes"]
        record.is_uncertain = True
        record.expires_at = datetime.utcnow()-timedelta(seconds=1)
        db.commit()
        check_and_update_lifecycle_status(db)
        assert record.status == "expired" and record.verification_status == "needs_confirmation"
        process_revalidation(db,record.id,"confirm_existing",confirmed_by=accepted.json()["reviewed_by"])
        assert record.expires_at-record.last_confirmed_at == timedelta(days=30)
        assert record.is_uncertain is True


def test_class_correction_cannot_forge_original_ai_confidence(client, application):
    auth = owner(client)
    image = upload(client,auth)
    run = detect(client,application,auth,image,[Prediction(0,.93,(0,0,30,30))])
    assert submit(client,auth,image,run,confidence=1).status_code == 422
    assert submit(client,auth,image,run,proposed_class=9).status_code == 422
    response = submit(client,auth,image,run,proposed_class=9,correction_reason="Wrong symbol")
    assert response.status_code == 201, response.text
    row = response.json()[0]
    reviewer = headers(manager(client,application)["access_token"])
    accepted = client.post(f"/api/v1/manager/observations/{row['id']}/review",headers=reviewer,json={"action":"accept"}).json()
    assert accepted["detection"]["predicted_class"] == 0 and accepted["detection"]["confidence"] == .93
    with application.state.session_factory() as db:
        record = db.get(SignRecord,accepted["sign_record_id"])
        assert record.predicted_class == 9 and record.confidence == 0 and record.is_uncertain


def test_observation_batch_is_atomic_and_cannot_reuse_other_images(client,application):
    auth = owner(client)
    image = upload(client,auth)
    run = detect(client,application,auth,image)
    second_image = upload(client,auth)
    assert submit(client,auth,second_image,run).status_code == 404
    one = {**run,"detections":run["detections"][:1]}
    assert submit(client,auth,image,one).status_code == 201
    assert submit(client,auth,image,run).status_code == 409
    with application.state.session_factory() as db:
        assert db.query(Observation).count() == 1
    assert client.get("/api/v1/me/observations",headers=auth).json()["total"] == 1


def test_zero_detections_is_valid_and_integrity_checked(client,application):
    auth = owner(client)
    image = upload(client,auth)
    run = detect(client,application,auth,image,[])
    assert run["detections"] == []
    with application.state.session_factory() as db:
        row = db.get(UploadedImage,image["id"])
        application.state.image_store.path(row.storage_key).write_bytes(b"tampered")
    assert client.get(image["content_url"],headers=auth).status_code == 503


def test_upload_body_and_file_limits(client,application):
    auth = owner(client)
    over = b'x'*(application.state.settings.max_upload_bytes+1)
    response = client.post('/api/v1/images',headers=auth,files={'file':('large.png',over,'image/png')})
    assert response.status_code == 413
    assert client.post('/api/v1/images',headers={**auth,'Content-Length':str(len(over)+65536)},content=b'').status_code == 413
    with application.state.session_factory() as db:
        assert db.query(UploadedImage).count() == 0


def test_review_rolls_back_when_evidence_write_fails(client,application,monkeypatch):
    from sqlalchemy import event
    auth = owner(client); image = upload(client,auth); run = detect(client,application,auth,image)
    row = submit(client,auth,image,run).json()[0]
    reviewer = headers(manager(client,application)['access_token'])
    def fail(*args):
        raise RuntimeError('evidence storage failed')
    event.listen(Evidence,'before_insert',fail)
    try:
        with pytest.raises(RuntimeError,match='evidence storage failed'):
            client.post(f"/api/v1/manager/observations/{row['id']}/review",headers=reviewer,json={'action':'accept'})
    finally:
        event.remove(Evidence,'before_insert',fail)
    with application.state.session_factory() as db:
        assert db.get(Observation,row['id']).status == 'pending'
        assert db.query(SignRecord).count() == 0 and db.query(Evidence).count() == 0


def test_concurrent_reviews_publish_exactly_one_record(client,application):
    from concurrent.futures import ThreadPoolExecutor
    auth = owner(client); image = upload(client,auth); run = detect(client,application,auth,image)
    row = submit(client,auth,image,run).json()[0]
    reviewer = headers(manager(client,application)['access_token'])
    path = f"/api/v1/manager/observations/{row['id']}/review"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.post(path,headers=reviewer,json={'action':'accept'}).status_code,range(2)))
    assert sorted(results) == [200,409]
    with application.state.session_factory() as db:
        assert db.query(SignRecord).count() == 1 and db.query(Evidence).count() == 1


def test_real_cnn_classification_has_provenance_and_no_box(client,application):
    from ai_engine.inference import classifier
    if classifier.model is None:
        pytest.skip('Real CNN checkpoint not present in this checkout')
    auth = owner(client); image = upload(client,auth)
    result = client.post(f"/api/v1/images/{image['id']}/classify",headers=auth)
    assert result.status_code == 200, result.text
    run = result.json()
    assert run['engine'] == 'cnn' and run['task'] == 'classification'
    assert run['model_version'].startswith('sha256:') and run['detections'][0]['bbox'] is None


@pytest.mark.parametrize('prediction',[Prediction(0,.8,(1,2,101,30)),Prediction(0,.8,(1,2,0,30)),Prediction(999,.8,(1,2,30,30)),Prediction(0,float('nan'),(1,2,30,30))])
def test_invalid_adapter_output_never_persists(client,application,prediction):
    auth = owner(client); image = upload(client,auth); application.state.detector = FakeDetector([prediction])
    assert client.post(f"/api/v1/images/{image['id']}/detect",headers=auth).status_code == 503
    with application.state.session_factory() as db:
        assert db.query(InferenceRun).count() == 0 and db.query(ImageDetection).count() == 0


def test_upload_file_removed_if_database_commit_fails(client,application):
    from sqlalchemy import event
    auth = owner(client)
    def fail(*args): raise RuntimeError('upload database failed')
    event.listen(UploadedImage,'before_insert',fail)
    try:
        with pytest.raises(RuntimeError,match='upload database failed'):
            upload(client,auth)
    finally:
        event.remove(UploadedImage,'before_insert',fail)
    assert list(application.state.image_store.root.glob('*.jpg')) == []
    with application.state.session_factory() as db:
        assert db.query(UploadedImage).count() == 0


def test_chunked_upload_cannot_bypass_request_limit(client,application):
    auth = owner(client)
    prefix = b'--bound\r\nContent-Disposition: form-data; name="file"; filename="large.png"\r\nContent-Type: image/png\r\n\r\n'
    limit = application.state.settings.max_upload_bytes+65536
    chunks = iter([prefix,b'x'*(limit+1),b'\r\n--bound--\r\n'])
    response = client.post('/api/v1/images',headers={**auth,'Content-Type':'multipart/form-data; boundary=bound'},content=chunks)
    assert response.status_code == 413, response.text


def test_absent_cnn_does_not_persist_a_simulated_result(client,application,monkeypatch):
    from backend.app.api.v1.endpoints.images import classifier
    auth = owner(client); image = upload(client,auth)
    monkeypatch.setattr(classifier,'model',None)
    assert client.post(f"/api/v1/images/{image['id']}/classify",headers=auth).status_code == 503
    with application.state.session_factory() as db:
        assert db.query(InferenceRun).count() == 0
