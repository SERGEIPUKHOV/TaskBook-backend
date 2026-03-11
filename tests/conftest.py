from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.helpers import extract_data

TEST_DB_PATH = Path(__file__).resolve().parent / "test.db"

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
os.environ["REDIS_URL"] = ""
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["SEED_DEMO_USER"] = "false"
os.environ["SEED_ADMIN_USER"] = "false"

from app.main import app
from app.core.database import engine
from app.models.base import Base


@pytest_asyncio.fixture(autouse=True)
async def reset_db():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    access_token = extract_data(response)["access_token"]
    return {"Authorization": f"Bearer {access_token}"}
