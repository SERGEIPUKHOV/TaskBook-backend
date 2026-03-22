from __future__ import annotations

import pytest

from app.core.config import settings
from tests.helpers import extract_data


@pytest.mark.integration
class TestAuthFlow:
    async def test_register_creates_user_and_sets_cookies(self, client):
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "newuser@taskbook.app", "password": "password123"},
        )

        assert response.status_code == 200
        payload = extract_data(response)
        assert payload["user"]["email"] == "newuser@taskbook.app"
        assert response.cookies.get(settings.ACCESS_COOKIE_NAME) == payload["access_token"]
        assert response.cookies.get(settings.REFRESH_COOKIE_NAME) == payload["refresh_token"]

    async def test_register_duplicate_email_returns_409(self, client):
        first = await client.post(
            "/api/v1/auth/register",
            json={"email": "dupe@taskbook.app", "password": "password123"},
        )
        second = await client.post(
            "/api/v1/auth/register",
            json={"email": "dupe@taskbook.app", "password": "password123"},
        )

        assert first.status_code == 200
        assert second.status_code == 409

    async def test_login_with_valid_credentials_returns_auth_payload(self, client):
        await client.post(
            "/api/v1/auth/register",
            json={"email": "login@taskbook.app", "password": "password123"},
        )
        await client.post("/api/v1/auth/logout")

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "login@taskbook.app", "password": "password123"},
        )

        assert response.status_code == 200
        payload = extract_data(response)
        assert payload["user"]["email"] == "login@taskbook.app"
        assert response.cookies.get(settings.REFRESH_COOKIE_NAME) == payload["refresh_token"]

    async def test_login_with_wrong_password_returns_401(self, client):
        await client.post(
            "/api/v1/auth/register",
            json={"email": "wrongpass@taskbook.app", "password": "password123"},
        )
        await client.post("/api/v1/auth/logout")

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "wrongpass@taskbook.app", "password": "wrongpassword"},
        )

        assert response.status_code == 401

    async def test_refresh_rotates_token_pair(self, client):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"email": "refresh@taskbook.app", "password": "password123"},
        )
        original = extract_data(register_response)

        refresh_response = await client.post("/api/v1/auth/refresh")

        assert refresh_response.status_code == 200
        refreshed = extract_data(refresh_response)
        assert refreshed["access_token"] != original["access_token"]
        assert refreshed["refresh_token"] != original["refresh_token"]

    async def test_logout_invalidates_refresh_for_followup_refresh(self, client):
        await client.post(
            "/api/v1/auth/register",
            json={"email": "logout@taskbook.app", "password": "password123"},
        )

        logout_response = await client.post("/api/v1/auth/logout")
        refresh_response = await client.post("/api/v1/auth/refresh")

        assert logout_response.status_code == 200
        assert refresh_response.status_code == 401

    async def test_protected_endpoint_requires_auth(self, client):
        response = await client.get("/api/v1/users/me")

        assert response.status_code == 401
