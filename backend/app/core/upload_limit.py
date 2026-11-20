"""Pure-ASGI request body size limit for upload endpoints.

Checks the declared Content-Length first, then counts bytes actually received so that
chunked uploads (no Content-Length) cannot bypass the limit.
"""
from __future__ import annotations

import json


class BodySizeLimitMiddleware:
    def __init__(self, app, path: str, max_bytes: int, message: str):
        self.app, self.path, self.max_bytes, self.message = app, path, max_bytes, message

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != self.path:
            return await self.app(scope, receive, send)

        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None:
            try:
                too_big = int(declared) > self.max_bytes
            except ValueError:
                too_big = True
            if too_big:
                return await self._reject(send)

        received = 0
        exceeded = False
        responded = False

        async def limited_receive():
            nonlocal received, exceeded
            if exceeded:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # FastAPI turns exceptions raised while parsing the body into a generic
                    # 400, so instead stop feeding data and replace the response below.
                    exceeded = True
                    return {"type": "http.disconnect"}
            return message

        async def limited_send(message):
            nonlocal responded
            if exceeded:
                if not responded:
                    responded = True
                    await self._reject(send)
                return  # swallow whatever the app tried to send
            await send(message)

        try:
            await self.app(scope, limited_receive, limited_send)
        except Exception:
            if not exceeded:
                raise
        if exceeded and not responded:
            await self._reject(send)

    async def _reject(self, send):
        body = json.dumps({"error": {"code": "file_too_large", "message": self.message}}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode())],
            }
        )
        await send({"type": "http.response.body", "body": body})
