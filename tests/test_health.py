from __future__ import annotations


async def test_health_reports_db_redis_and_version(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "db": "ok",
        "redis": "ok",
        "version": "6.1.1",
        "environment": "test",
    }
