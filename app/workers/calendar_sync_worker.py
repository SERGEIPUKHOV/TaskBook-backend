from __future__ import annotations

import asyncio
import logging
import time
from uuid import uuid4

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import configure_logging
from app.core.redis import redis_client
from app.services.calendar_google_service import sync_all_google_connections
from app.services.calendar_ics_service import sync_all_apple_connections

configure_logging(settings.LOG_LEVEL)

logger = logging.getLogger("taskbook.calendar_sync_worker")
SYNC_LOCK_KEY = "calendar:google:sync-all:lock"


async def try_acquire_sync_lock() -> str | None:
    token = uuid4().hex
    acquired = await redis_client.set(
        SYNC_LOCK_KEY,
        token,
        ex=settings.CALENDAR_SYNC_LOCK_TTL_SECONDS,
        nx=True,
    )
    return token if acquired else None


async def release_sync_lock(token: str) -> None:
    current_token = await redis_client.get(SYNC_LOCK_KEY)
    if current_token == token:
        await redis_client.delete(SYNC_LOCK_KEY)


async def run_sync_cycle() -> int:
    async with AsyncSessionLocal() as session:
        google_synced = await sync_all_google_connections(session)
        apple_synced = await sync_all_apple_connections(session)
    return len(google_synced) + len(apple_synced)


async def worker_loop() -> None:
    interval = max(30, settings.CALENDAR_SYNC_INTERVAL_SECONDS)
    logger.info(
        "calendar_sync_worker_started",
        extra={
            "interval_seconds": interval,
            "lock_ttl_seconds": settings.CALENDAR_SYNC_LOCK_TTL_SECONDS,
        },
    )

    while True:
        cycle_started_at = time.monotonic()
        lock_token = await try_acquire_sync_lock()

        if lock_token is None:
            logger.info("calendar_sync_cycle_skipped_lock_not_acquired")
        else:
            try:
                synced_count = await run_sync_cycle()
                logger.info(
                    "calendar_sync_cycle_completed",
                    extra={"synced_connection_count": synced_count},
                )
            except Exception:
                logger.exception("calendar_sync_cycle_failed")
            finally:
                await release_sync_lock(lock_token)

        elapsed = time.monotonic() - cycle_started_at
        await asyncio.sleep(max(1, interval - elapsed))


async def main() -> None:
    try:
        await worker_loop()
    finally:
        if hasattr(redis_client, "aclose"):
            await redis_client.aclose()
        elif hasattr(redis_client, "close"):
            await redis_client.close()


if __name__ == "__main__":
    asyncio.run(main())
