from concurrent.futures import ThreadPoolExecutor
from threading import Event

from ai_engine.detection import DetectorUnavailable
from backend.app.db.models import InferenceRun
from test_images_observations import FakeDetector, owner, upload


def test_busy_detector_rejects_without_queueing_and_releases_capacity(client, application):
    auth = owner(client)
    image = upload(client, auth)
    entered, release = Event(), Event()

    class SlowDetector(FakeDetector):
        calls = 0
        def predict(self, image):
            self.calls += 1
            if self.calls == 1:
                entered.set()
                assert release.wait(8)
            return super().predict(image)

    detector = application.state.detector = SlowDetector()
    url = f"/api/v1/images/{image['id']}/detect"
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(client.post, url, headers=auth)
        assert entered.wait(5)
        try:
            busy = pool.submit(client.post, url, headers=auth).result(timeout=2)
            assert busy.status_code == 503
            assert busy.headers['Retry-After'] == '2'
            assert detector.calls == 1
            assert client.get('/').status_code == 200
        finally:
            release.set()
        assert pending.result(timeout=5).status_code == 200
    assert client.post(url, headers=auth).status_code == 200
    with application.state.session_factory() as db:
        assert db.query(InferenceRun).count() == 2


def test_failed_inference_does_not_leak_a_slot(client, application):
    auth = owner(client)
    image = upload(client, auth)
    class Broken(FakeDetector):
        def predict(self, image):
            raise DetectorUnavailable('Synthetic unavailable model')
    application.state.detector = Broken()
    url = f"/api/v1/images/{image['id']}/detect"
    assert client.post(url, headers=auth).status_code == 503
    application.state.detector = FakeDetector()
    assert client.post(url, headers=auth).status_code == 200
