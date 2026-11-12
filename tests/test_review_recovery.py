from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.db.models import Evidence, SignAudit, SignRecord, WriteReceipt
from test_accounts import headers, manager, login
from test_images_observations import owner, upload, detect, submit
from test_reports_policy import report
from test_navigation_map import add_sign
from test_duplicate_review import candidate


def prepare(client, application, kind):
    auth = owner(client)
    if kind == "observations":
        image = upload(client, auth)
        row = submit(client, auth, image, detect(client, application, auth, image)).json()[0]
        action = "accept"
    elif kind == "reports":
        image = upload(client, auth)
        row = report(client, auth, image, add_sign(application)).json()
        action = "accept"
    else:
        row = {"id": candidate(application, add_sign(application, lat=10.7801), add_sign(application))}
        action = "merge"
    return auth, row["id"], {"action": action, **({"comment": "Verified evidence"} if kind != "duplicates" else {})}


@pytest.mark.parametrize("kind", ["observations", "reports", "duplicates"])
def test_review_replay_is_atomic_persistent_and_role_scoped(client, application, kind):
    user, resource_id, payload = prepare(client, application, kind)
    path = f"/api/v1/manager/{kind}/{resource_id}/review"
    auth = {**headers(manager(client, application)["access_token"]), "Idempotency-Key": "review-request-001"}
    first = client.post(path, headers=auth, json=payload)
    assert first.status_code == 200, first.text
    if kind == 'duplicates':
        detail = path.removesuffix('/review')
        assert client.get(detail, headers=auth).json()['status'] == 'confirmed_duplicate'
        assert client.get(detail, headers=user).status_code == 403
        assert client.get(detail).status_code == 401
    with application.state.session_factory() as db:
        counts = (db.query(Evidence).count(), db.query(SignAudit).count(), db.query(SignRecord).count())
    replay = client.post(path, headers=auth, json=payload)
    assert replay.status_code == 200 and replay.json() == first.json()
    changed = {**payload, "action": "dismiss" if kind == "duplicates" else "reject"}
    assert client.post(path, headers=auth, json=changed).status_code == 409
    assert client.post(path.replace(resource_id, "missing-id"), headers=auth, json=payload).status_code == 409
    assert client.post(path, headers={**user, "Idempotency-Key": auth["Idempotency-Key"]}, json=payload).status_code == 403
    assert client.post(path, json=payload).status_code == 401
    other = {**headers(login(client, "owner")["access_token"]), "Idempotency-Key": auth["Idempotency-Key"]}
    assert client.post(path, headers=other, json=payload).status_code == 409  # Different actor, no replay receipt.
    restarted = create_app(application.state.session_factory.kw["bind"], application.state.settings)
    with TestClient(restarted) as again:
        assert again.post(path, headers=auth, json=payload).json() == first.json()
    with application.state.session_factory() as db:
        assert counts == (db.query(Evidence).count(), db.query(SignAudit).count(), db.query(SignRecord).count())
        assert db.query(WriteReceipt).count() == 1


@pytest.mark.parametrize("kind", ["observations", "reports", "duplicates"])
def test_parallel_review_retries_apply_effects_once(client, application, kind):
    _, resource_id, payload = prepare(client, application, kind)
    auth = {**headers(manager(client, application)["access_token"]), "Idempotency-Key": "parallel-review-001"}
    path = f"/api/v1/manager/{kind}/{resource_id}/review"
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post(path, headers=auth, json=payload), range(4)))
    assert [row.status_code for row in results] == [200] * 4
    assert all(row.json() == results[0].json() for row in results)
    with application.state.session_factory() as db:
        assert db.query(WriteReceipt).count() == 1
        assert db.query(Evidence).count() == (0 if kind == "duplicates" else 1)
        assert db.query(SignAudit).count() == (2 if kind == "duplicates" else 1 if kind == "reports" else 0)


def test_failed_review_does_not_consume_the_request_key(client, application):
    _, resource_id, payload = prepare(client, application, "reports")
    auth = {**headers(manager(client, application)["access_token"]), "Idempotency-Key": "failed-review-001"}
    from backend.app.db.models import SignReport
    with application.state.session_factory() as db:
        record = db.get(SignRecord, db.get(SignReport, resource_id).record_id)
        record.revision += 1
        db.commit()
    path = f"/api/v1/manager/reports/{resource_id}/review"
    assert client.post(path, headers=auth, json=payload).status_code == 409
    with application.state.session_factory() as db:
        assert db.query(WriteReceipt).count() == 0
        assert db.get(SignReport, resource_id).status == "pending"
    assert client.post(path, headers=auth, json={"action": "reject"}).status_code == 200
