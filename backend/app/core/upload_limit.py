"""Bound multipart request bytes before Starlette can spool an oversized upload."""
from fastapi import HTTPException
from starlette.responses import JSONResponse


class UploadLimitMiddleware:
    def __init__(self, app, max_bytes):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST" or scope.get("path", "").rstrip("/") not in ("/api/v1/images", "/api/v1/signs/classify"):
            return await self.app(scope, receive, send)
        for key,value in scope.get("headers", []):
            if key.lower() == b"content-length":
                try:
                    length = int(value)
                    if length < 0:
                        raise ValueError()
                except ValueError:
                    return await JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)(scope,receive,send)
                if length > self.max_bytes:
                    return await JSONResponse({"detail": "Upload request exceeds size limit"}, status_code=413)(scope,receive,send)
        count = 0
        async def limited_receive():
            nonlocal count
            message = await receive()
            if message["type"] == "http.request":
                count += len(message.get("body", b""))
                if count > self.max_bytes:
                    raise HTTPException(413, "Upload request exceeds size limit")
            return message
        await self.app(scope, limited_receive, send)
