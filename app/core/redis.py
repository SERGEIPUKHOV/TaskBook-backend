from __future__ import annotations

import time
from collections.abc import Iterable

import redis.asyncio as aioredis

from app.core.config import settings


class InMemoryRedis:
    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float | None]] = {}

    def _purge(self, key: str) -> None:
        entry = self._data.get(key)
        if entry is None:
            return
        _, expires_at = entry
        if expires_at is not None and expires_at <= time.time():
            self._data.pop(key, None)

    async def get(self, key: str) -> str | None:
        self._purge(key)
        entry = self._data.get(key)
        if entry is None:
            return None
        return entry[0]

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        expires_at = time.time() + ex if ex else None
        self._data[key] = (value, expires_at)
        return True

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            deleted += int(self._data.pop(key, None) is not None)
        return deleted

    async def exists(self, key: str) -> int:
        self._purge(key)
        return int(key in self._data)

    async def incr(self, key: str) -> int:
        self._purge(key)
        current_raw = await self.get(key)
        current = int(current_raw or 0) + 1
        expires_at = self._data.get(key, ("", None))[1]
        self._data[key] = (str(current), expires_at)
        return current

    async def expire(self, key: str, ttl: int) -> bool:
        self._purge(key)
        entry = self._data.get(key)
        if entry is None:
            return False
        self._data[key] = (entry[0], time.time() + ttl)
        return True

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


def create_redis_client():
    if settings.REDIS_URL:
        return aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return InMemoryRedis()


redis_client = create_redis_client()


async def invalidate_keys(keys: Iterable[str]) -> None:
    await redis_client.delete(*list(keys))
