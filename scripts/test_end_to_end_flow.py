"""
End-to-End Integration Test for SignSight Platform
Runs against a temporary database, using an explicitly authenticated administrator.
Checks account setup, CNN classification API, manual records, duplicates, route
query and revalidation. Phone-browser UI and YOLO quality require separate acceptance checks.
"""

import os
import sys
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient
from PIL import Image
from backend.app.core.settings import Settings
from backend.app.db.database import make_engine
from backend.app.main import create_app
from backend.manage import bootstrap_admin

def run_flow(client):

    print("=" * 60)
    print("RUNNING SIGNSIGHT END-TO-END INTEGRATION TEST")
    print("=" * 60)

    # 1. Healthcheck / Root endpoint
    resp = client.get("/")
    assert resp.status_code == 200, f"Root failed: {resp.text}"
    print("[PASS] Root API Healthcheck: OK")
    print(f"       Supported classes: {resp.json()['supported_classes_count']}")

    token_response = client.post('/api/v1/auth/login', json={
        'username': 'e2e_admin', 'password': 'Temporary-test-password-123',
    })
    assert token_response.status_code == 200
    client.headers['Authorization'] = f"Bearer {token_response.json()['access_token']}"
    print('[PASS] Administrator login')
    image = BytesIO()
    Image.new('RGB', (64, 64), (230, 20, 20)).save(image, format='PNG')
    inference = client.post('/api/v1/signs/classify', files={'file': ('sample.png', image.getvalue(), 'image/png')})
    assert inference.status_code == 200, inference.text
    assert len(inference.json()['probabilities']) == 10
    print('[PASS] Authenticated classification API contract (synthetic image)')

    # 2. Register first traffic sign (P.127 50km/h) near Swinburne HCM (10.7800, 106.7000)
    sign1_payload = {
        "predicted_class": 0,  # P.127 (50)
        "confidence": 0.94,
        "latitude": 10.78000,
        "longitude": 106.70000,
        "location_source": "device",
    }
    r1 = client.post("/api/v1/signs/register", json=sign1_payload)
    assert r1.status_code == 200, f"Register 1 failed: {r1.text}"
    s1 = r1.json()
    assert s1['created_by'] == token_response.json()['user']['id']
    print(f"[PASS] Registered Sign 1: ID={s1['id'][:8]} | {s1['qcvn_code']} ({s1['name_vi']})")
    print(f"       Status={s1['status']} | Expires At={s1['expires_at']}")

    # 3. Register a near-duplicate observation (12 meters away, same class)
    # 0.0001 deg lat is ~11 meters
    sign2_payload = {
        "predicted_class": 0,  # P.127 (50)
        "confidence": 0.88,
        "latitude": 10.78010,
        "longitude": 106.70000,
        "location_source": "device",
    }
    r2 = client.post("/api/v1/signs/register", json=sign2_payload)
    assert r2.status_code == 200, f"Register 2 failed: {r2.text}"
    s2 = r2.json()
    print(f"[PASS] Registered Sign 2: ID={s2['id'][:8]} | Detected Duplicates: {s2['possible_duplicate_count']}")
    assert s2['possible_duplicate_count'] > 0, "Duplicate candidate should be detected!"

    # 4. Check Duplicate Candidates API
    r_dup = client.get("/api/v1/revalidation/duplicates")
    assert r_dup.status_code == 200
    dups = r_dup.json()
    print(f"[PASS] Duplicate candidate query returned {len(dups)} candidate pair(s)")
    if dups:
        print(f"       Distance: {dups[0]['distance_meters']}m | Class Match: {dups[0]['class_match']}")

    # 5. Test Navigation Route Sign Retrieval
    # Create a simulated driving route passing by Sign 1 and 2
    route_payload = {
        "waypoints": [
            {"latitude": 10.77950, "longitude": 106.70000},
            {"latitude": 10.78005, "longitude": 106.70000},
            {"latitude": 10.78060, "longitude": 106.70000}
        ],
        "buffer_meters": 35.0
    }
    r_nav = client.post("/api/v1/navigation/route-signs", json=route_payload)
    assert r_nav.status_code == 200, f"Navigation failed: {r_nav.text}"
    nav_res = r_nav.json()
    print(f"[PASS] Navigation Route Query: Found {nav_res['total_signs']} sign(s) along route corridor")
    print(f"       Active={nav_res['active_signs_count']}, Buffer={nav_res['buffer_meters']}m")
    assert nav_res['total_signs'] >= 2, "Expected both signs to be detected along the route"

    # 6. Test Lifecycle Revalidation
    reval_payload = {
        "action": "confirm_existing",
        "comment": "Biển báo 50km/h vẫn còn rõ nét trên đường Nguyễn Thị Minh Khai.",
    }
    r_reval = client.post(f"/api/v1/revalidation/{s1['id']}", json=reval_payload)
    assert r_reval.status_code == 200, f"Revalidation failed: {r_reval.text}"
    s1_updated = r_reval.json()
    print(f"[PASS] Revalidation Confirmation: Sign {s1_updated['id'][:8]} status is {s1_updated['status']}")
    print(f"       New Expiration Date: {s1_updated['expires_at']}")

    print("=" * 60)
    print("ALL INTEGRATION CHECKS PASSED (isolated database)")
    print("=" * 60)

def run_tests():
    with TemporaryDirectory(prefix='signsight-e2e-') as temporary:
        db_path = Path(temporary) / 'test.db'
        test_engine = make_engine(f'sqlite:///{db_path}')
        try:
            app = create_app(test_engine, Settings())
            with TestClient(app) as client:
                bootstrap_admin('e2e_admin', 'e2e@example.com', 'Temporary-test-password-123', app.state.session_factory)
                run_flow(client)
        finally:
            test_engine.dispose()


if __name__ == "__main__":
    run_tests()
