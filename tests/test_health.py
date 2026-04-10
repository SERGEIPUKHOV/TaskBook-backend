from __future__ import annotations

from app.core.config import settings


async def test_health_reports_db_redis_and_version(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "db": "ok",
        "redis": "ok",
        "version": settings.APP_VERSION,
        "environment": "test",
    }
