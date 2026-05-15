"""Custom middleware for the Context Recall API server."""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("contextrecall.api.middleware")

DEFAULT_MAX_BODY_BYTES = 5 * 1024 * 1024  # 5 MB


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose declared Content-Length exceeds ``max_bytes``.

    Returns HTTP 413 (Payload Too Large) when the limit is exceeded so the
    daemon does not spend memory buffering oversized payloads.
    """

    def __init__(self, app, max_bytes: int = DEFAULT_MAX_BODY_BYTES) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                return JSONResponse(
                    {"detail": "Invalid Content-Length header"},
                    status_code=400,
                )
            if declared > self.max_bytes:
                logger.warning(
                    "Rejecting request with Content-Length=%d > limit=%d",
                    declared,
                    self.max_bytes,
                )
                return JSONResponse(
                    {"detail": "Request body too large"},
                    status_code=413,
                )
        return await call_next(request)
