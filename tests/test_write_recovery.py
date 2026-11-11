"""Retry contracts use only disposable DBs, generated images and synthetic detection."""
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from backend.app.db.models import UploadedImage, Observation
from backend.app.main import create_app
from sqlalchemy import event
from test_accounts import register, login, headers
from test_images_observations import owner, picture, upload, detect


def keyed(auth, key="capture-request-001"):
    return {**auth, "Idempotency-Key": key}


def send_image(client, auth, data=None, name="photo.png"):
    return client.post("/api/v1/images", headers=auth,
                       files={"file": (name, picture() if data is None else data, "image/png")})


def proposal(image, run):
    return {"image_id": image["id"], "items": [
        {"detection_id": row["id"], "latitude": 10.78, "longitude": 106.70}
        for row in run["detections"]]}


def test_upload_replay_conflict_and_restart(client, application):
    auth = keyed(owner(client))
    first = send_image(client, auth)
    second = send_image(client, auth, name="renamed.png")
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert send_image(client, auth, picture((51, 51))).status_code == 409
    with application.state.session_factory() as db:
        assert db.query(UploadedImage).count() == 1
    assert len(list(application.state.settings.storage_root.glob("*.jpg"))) == 1
    restarted = create_app(application.state.session_factory.kw["bind"], application.state.settings)
    with TestClient(restarted) as again:
        replay = send_image(again, auth)
        assert replay.status_code == 201 and replay.json() == first.json()


def test_upload_key_account_isolation_and_legacy_compatibility(client, application):
    alice = keyed(owner(client))
    original = send_image(client, alice).json()
    register(client, "bob")
    bob = keyed(headers(login(client, "bob")["access_token"]))
    other = send_image(client, bob)
    assert other.status_code == 201 and other.json()["id"] != original["id"]
    assert client.get(original["content_url"], headers=bob).status_code == 404
    legacy = {k: v for k, v in alice.items() if k != "Idempotency-Key"}
    assert send_image(client, legacy).json()["id"] != original["id"]
    assert send_image(client, {"Idempotency-Key": "guest-request-001"}).status_code == 401
    assert send_image(client, keyed(legacy, "short")).status_code == 422


def test_parallel_upload_retries_publish_only_one_file(client, application):
    auth = keyed(owner(client))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: send_image(client, auth), range(4)))
    assert [r.status_code for r in results] == [201] * 4
    assert len({r.json()["id"] for r in results}) == 1
    with application.state.session_factory() as db:
        assert db.query(UploadedImage).count() == 1
    assert len(list(application.state.settings.storage_root.glob("*.jpg"))) == 1


def test_upload_store_failure_rolls_back_receipt(client, application, monkeypatch):
    auth = keyed(owner(client))
    original = application.state.image_store.save
    def fail(*args):
        raise OSError("injected disk failure")
    monkeypatch.setattr(application.state.image_store, "save", fail)
    try:
        send_image(client, auth)
    except OSError:
        pass
    else:
        raise AssertionError("storage failure must propagate")
    monkeypatch.setattr(application.state.image_store, "save", original)
    assert send_image(client, auth).status_code == 201
    assert len(list(application.state.settings.storage_root.glob("*.jpg"))) == 1


def test_submission_replay_keeps_ids_and_conflicts_on_changed_payload(client, application):
    auth = owner(client)
    image = upload(client, auth)
    payload = proposal(image, detect(client, application, auth, image))
    post = lambda body: client.post("/api/v1/observations", headers=keyed(auth), json=body)
    first = post(payload)
    assert first.status_code == 201
    replay = post(payload)
    assert replay.status_code == 201 and replay.json() == first.json()
    payload["items"][0]["latitude"] += .01
    assert post(payload).status_code == 409
    with application.state.session_factory() as db:
        assert db.query(Observation).count() == 2


def test_parallel_submission_retries_and_cross_account_isolation(client, application):
    auth = owner(client)
    image = upload(client, auth)
    payload = proposal(image, detect(client, application, auth, image))
    def post(_):
        return client.post("/api/v1/observations", headers=keyed(auth), json=payload)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(post, range(4)))
    assert [r.status_code for r in results] == [201] * 4
    assert all(r.json() == results[0].json() for r in results)
    register(client, "bob")
    bob = headers(login(client, "bob")["access_token"])
    assert client.post("/api/v1/observations", headers=keyed(bob), json=payload).status_code == 404
    own_image = upload(client, bob)
    own_payload = proposal(own_image, detect(client, application, bob, own_image))
    assert client.post("/api/v1/observations", headers=keyed(bob), json=own_payload).status_code == 201


def test_failed_submission_does_not_consume_key(client, application):
    auth = owner(client)
    image = upload(client, auth)
    payload = proposal(image, detect(client, application, auth, image))
    original = payload["items"][0]["detection_id"]
    payload["items"][0]["detection_id"] = "missing"
    assert client.post("/api/v1/observations", headers=keyed(auth), json=payload).status_code == 404
    payload["items"][0]["detection_id"] = original
    assert client.post("/api/v1/observations", headers=keyed(auth), json=payload).status_code == 201


def test_commit_failure_cleans_file_and_receipt_then_allows_retry(client, application):
    auth = keyed(owner(client))
    engine = application.state.session_factory.kw["bind"]
    def fail(connection):
        raise RuntimeError("injected failed transaction")
    event.listen(engine, "commit", fail)
    try:
        import pytest
        with pytest.raises(RuntimeError, match="failed transaction"):
            send_image(client, auth)
    finally:
        event.remove(engine, "commit", fail)
    assert not list(application.state.settings.storage_root.glob("*.jpg"))
    assert send_image(client, auth).status_code == 201


def test_submission_receipt_survives_restart_and_returns_reviewed_result(client, application):
    from test_accounts import manager
    auth = owner(client)
    image = upload(client, auth)
    payload = proposal(image, detect(client, application, auth, image))
    initial = client.post("/api/v1/observations", headers=keyed(auth), json=payload).json()
    reviewer = headers(manager(client, application)["access_token"])
    result = client.post(f'/api/v1/manager/observations/{initial[0]["id"]}/review',
                         headers=reviewer, json={"action": "accept"})
    assert result.status_code == 200
    restarted = create_app(application.state.session_factory.kw["bind"], application.state.settings)
    with TestClient(restarted) as again:
        replay = again.post("/api/v1/observations", headers=keyed(auth), json=payload)
    assert replay.status_code == 201
    assert [row["id"] for row in replay.json()] == [row["id"] for row in initial]
    assert replay.json()[0]["sign_record_id"] == result.json()["sign_record_id"]
    assert replay.json()[0]["status"] == "accepted"
