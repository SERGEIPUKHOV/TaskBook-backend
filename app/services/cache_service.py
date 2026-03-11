from __future__ import annotations

from app.core.redis import redis_client


def dashboard_cache_key(user_id: str) -> str:
    return f"dashboard:{user_id}"


async def invalidate_dashboard(user_id: str) -> None:
    await redis_client.delete(dashboard_cache_key(user_id))
