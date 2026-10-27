"""Opt-in acceptance checks using installed weights, real inference and temporary DBs.

Run with SIGNSIGHT_TEST_REAL_YOLO=1. The positive-image check needs the local
GTSRB archive; no weights or data are downloaded by these tests.
"""
import hashlib
import io
import json
import os
from pathlib import Path

import pytest
from PIL import Image

from backend.app.db.models import InferenceRun, Observation, SignRecord
from test_accounts import headers, login, manager, register

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    os.getenv("SIGNSIGHT_TEST_REAL_YOLO") != "1",
    reason="Enable SIGNSIGHT_TEST_REAL_YOLO=1 to check the installed local checkpoint",
)


def ready_detector(client, application):
    # Optional external checkpoint keeps local weights out of the public checkout.
    weights = Path(os.environ.get('SIGNSIGHT_TEST_CHECKPOINT', application.state.settings.yolo_weights))
    application.state.detector.weights = weights
    register(client)
    auth = headers(login(client)["access_token"])
    application.state.detector.device = "cpu"
    response = client.get("/api/v1/ai/status", headers=auth)
    assert response.status_code == 200, response.text
    status = response.json()["yolo"]
    assert status["ready"], status
    assert status["confidence_threshold"] == application.state.settings.yolo_confidence
    report = weights.with_name("detection_report.json")
    assert report.is_file(), "Keep the training report with the installed checkpoint"
    expected = json.loads(report.read_text(encoding="utf-8"))["model_version"]
    assert status["model_version"] == expected
    return auth, expected


def uploaded(client, auth, content):
    response = client.post(
        "/api/v1/images", headers=auth,
        files={"file": ("sample.png", content, "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_real_yolo_upload_review_publishes_map_record_and_evidence(client, application):
    sample = Path(os.environ.get('SIGNSIGHT_TEST_IMAGE', ROOT / "archive/Test/11052.png"))
    if not sample.is_file():
        pytest.skip("Local GTSRB test image is not present")
    auth, expected_version = ready_detector(client, application)
    image = uploaded(client, auth, sample.read_bytes())
    response = client.post(f"/api/v1/images/{image['id']}/detect", headers=auth)
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["engine"] == "yolo" and run["task"] == "detection"
    assert run["model_version"] == expected_version
    detection = max(run["detections"], key=lambda row: row["confidence"])
    assert detection["qcvn_code"] == "P.127 (50)" and detection["predicted_class"] == 0
    assert application.state.settings.yolo_confidence <= detection["confidence"] <= 1
    box = detection["bbox"]
    assert 0 <= box["x1"] < box["x2"] <= image["width"]
    assert 0 <= box["y1"] < box["y2"] <= image["height"]
    submitted = client.post("/api/v1/observations", headers=auth, json={
        "image_id": image["id"], "items": [{
            "detection_id": detection["id"], "latitude": 10.7769,
            "longitude": 106.7009, "location_source": "user_confirmed",
        }],
    })
    assert submitted.status_code == 201, submitted.text
    observation = submitted.json()[0]
    assert observation["status"] == "pending"
    assert client.get("/api/v1/map/signs", headers=auth).json()["total"] == 0
    reviewer = headers(manager(client, application)["access_token"])
    reviewed = client.post(
        f"/api/v1/manager/observations/{observation['id']}/review",
        headers=reviewer, json={"action": "accept", "comment": "Local checkpoint acceptance check"},
    )
    assert reviewed.status_code == 200, reviewed.text
    accepted = reviewed.json()
    assert accepted["status"] == "accepted"
    assert accepted["model_version"] == expected_version
    records = client.get("/api/v1/map/signs", headers=auth).json()
    assert records["total"] == 1
    record = records["items"][0]
    assert record["id"] == accepted["sign_record_id"]
    assert record["qcvn_code"] == "P.127 (50)" and record["verification_status"] == "current"
    detail = client.get(f"/api/v1/signs/{record['id']}", headers=auth).json()
    assert len(detail["evidence"]) == 1
    evidence = detail["evidence"][0]
    content = client.get(evidence["content_url"], headers=auth)
    assert content.status_code == 200
    assert hashlib.sha256(content.content).hexdigest() == evidence["sha256"] == image["sha256"]
    history = client.get("/api/v1/me/observations", headers=auth).json()
    assert history["items"][0]["status"] == "accepted"


def test_real_yolo_blank_image_persists_empty_run_without_creating_sign(client, application):
    auth, expected_version = ready_detector(client, application)
    content = io.BytesIO()
    Image.new("RGB", (512, 384), "white").save(content, format="PNG")
    image = uploaded(client, auth, content.getvalue())
    response = client.post(f"/api/v1/images/{image['id']}/detect", headers=auth)
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["model_version"] == expected_version and run["detections"] == []
    persisted = client.get(f"/api/v1/inference-runs/{run['id']}", headers=auth)
    assert persisted.status_code == 200 and persisted.json()["detections"] == []
    assert client.post("/api/v1/observations", headers=auth, json={"image_id": image["id"], "items": []}).status_code == 422
    with application.state.session_factory() as db:
        assert db.query(InferenceRun).count() == 1
        assert db.query(Observation).count() == 0 and db.query(SignRecord).count() == 0
