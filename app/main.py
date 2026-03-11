from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db, init_models
from app.core.logging import configure_logging
from app.core.observability import init_sentry
from app.core.rate_limit import RateLimitMiddleware, get_client_ip
from app.core.redis import redis_client
from app.services.auth_service import ensure_seed_users

configure_logging(settings.LOG_LEVEL)
init_sentry()

logger = logging.getLogger("taskbook.api")
LOG_EXCLUDED_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        await init_models()

    if settings.SEED_DEMO_USER or settings.SEED_ADMIN_USER:
        async with AsyncSessionLocal() as session:
            await ensure_seed_users(session)

    yield

    if hasattr(redis_client, "aclose"):
        await redis_client.aclose()
    elif hasattr(redis_client, "close"):
        await redis_client.close()


app = FastAPI(title="TaskBook API", version=settings.APP_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    if request.url.path in LOG_EXCLUDED_PATHS:
        return await call_next(request)

    start = time.perf_counter()
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    client_ip = get_client_ip(request)

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.exception(
            "request_failed",
            extra={
                "client_ip": client_ip,
                "duration_ms": duration_ms,
                "method": request.method,
                "path": request.url.path,
                "request_id": request_id,
            },
        )
        raise

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers.setdefault("X-Request-ID", request_id)
    logger.info(
        "request_completed",
        extra={
            "client_ip": client_ip,
            "duration_ms": duration_ms,
            "method": request.method,
            "path": request.url.path,
            "request_id": request_id,
            "status_code": response.status_code,
        },
    )
    return response


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    db_ok = False
    redis_ok = False

    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.exception("health_db_check_failed")

    try:
        redis_ok = bool(await redis_client.ping())
    except Exception:
        logger.exception("health_redis_check_failed")

    status_text = "ok" if db_ok and redis_ok else "degraded"
    status_code = 200 if status_text == "ok" else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": status_text,
            "db": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else "error",
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
        },
    )
