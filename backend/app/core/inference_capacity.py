"""Bounded admission per API process; requests never wait in an inference queue."""
from contextlib import contextmanager
from threading import BoundedSemaphore

from fastapi import HTTPException


class InferenceCapacity:
    def __init__(self, limit=1):
        self._slots = BoundedSemaphore(limit)

    @contextmanager
    def claim(self):
        if not self._slots.acquire(blocking=False):
            raise HTTPException(503, 'AI đang xử lý ảnh khác. Vui lòng thử lại sau ít giây.',
                                headers={'Retry-After': '2'})
        try:
            yield
        finally:
            self._slots.release()
