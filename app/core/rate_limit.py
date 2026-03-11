from __future__ import annotations

import logging
import time

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import settings
from app.core.redis import redis_client
from app.core.security import safely_decode_token

logger = logging.getLogger("taskbook.rate_limit")


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.RATE_LIMIT_ENABLED or settings.is_testing:
            return await call_next(request)

        path = request.url.path
        if path in {"/health", "/docs", "/openapi.json", "/redoc"}:
            return await call_next(request)

        client_ip = get_client_ip(request)
        auth_prefix = f"{settings.API_V1_PREFIX}/auth/"
        window = int(time.time() // 60)

        if path.startswith(auth_prefix):
            key = f"rl:auth:{client_ip}:{window}"
            limit = 20
        else:
            authorization = request.headers.get("Authorization", "")
            token = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else ""
            if not token:
                token = request.cookies.get(settings.ACCESS_COOKIE_NAME, "")
            payload = safely_decode_token(token) if token else None
            actor = str(payload.get("sub")) if payload and payload.get("sub") else client_ip
            key = f"rl:app:{actor}:{window}"
            limit = 100

        try:
            current = await redis_client.incr(key)
            if current == 1:
                await redis_client.expire(key, 60)
        except Exception:
            logger.warning(
                "rate_limit_storage_unavailable",
                extra={"client_ip": client_ip, "path": path},
            )
            return await call_next(request)

        if current > limit:
            return JSONResponse(status_code=429, content={"detail": "Too many requests"})

        return await call_next(request)
