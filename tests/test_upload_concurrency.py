import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from backend.app.api.v1.endpoints import images
from test_images_observations import owner, picture


def test_slow_upload_decoder_does_not_stall_event_loop(client, application, monkeypatch):
    auth = owner(client)
    entered, release = threading.Event(), threading.Event()
    original = images.sanitize_image
    def slow(*args):
        entered.set()
        assert release.wait(8), "test failed to release decoder"
        return original(*args)
    monkeypatch.setattr(images, "sanitize_image", slow)

    async def tick():
        await asyncio.sleep(0)
        return "responsive"

    with ThreadPoolExecutor(max_workers=2) as pool:
        upload = pool.submit(client.post, "/api/v1/images", headers=auth,
                             files={"file": ("phone.png", picture(), "image/png")})
        assert entered.wait(5)
        probe = pool.submit(client.portal.call, tick)
        try:
            assert probe.result(timeout=1) == "responsive"
        finally:
            release.set()
        assert upload.result(timeout=5).status_code == 201
