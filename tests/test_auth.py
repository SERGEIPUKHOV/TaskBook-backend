from __future__ import annotations

from app.core.config import settings
from tests.helpers import extract_data


async def test_auth_register_sets_cookies_and_supports_cookie_profile(client):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": "auth@example.com", "password": "password123"},
    )
    assert register_response.status_code == 200
    session = extract_data(register_response)
    assert session["user"]["email"] == "auth@example.com"
    assert register_response.cookies.get(settings.ACCESS_COOKIE_NAME) == session["access_token"]
    assert register_response.cookies.get(settings.REFRESH_COOKIE_NAME) == session["refresh_token"]
    assert register_response.cookies.get(settings.SESSION_COOKIE_NAME) == "1"

    profile_response = await client.get("/api/v1/users/me")
    assert profile_response.status_code == 200
    assert extract_data(profile_response)["email"] == "auth@example.com"


async def test_auth_login_refresh_logout_and_change_password_support_cookie_session(client):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": "auth@example.com", "password": "password123"},
    )
    assert register_response.status_code == 200

    logout_after_register = await client.post("/api/v1/auth/logout")
    assert logout_after_register.status_code == 200
    assert client.cookies.get(settings.ACCESS_COOKIE_NAME) is None
    assert client.cookies.get(settings.REFRESH_COOKIE_NAME) is None
    assert client.cookies.get(settings.SESSION_COOKIE_NAME) is None

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "auth@example.com", "password": "password123"},
    )
    assert login_response.status_code == 200
    session = extract_data(login_response)
    assert login_response.cookies.get(settings.ACCESS_COOKIE_NAME) == session["access_token"]
    assert login_response.cookies.get(settings.REFRESH_COOKIE_NAME) == session["refresh_token"]
    assert login_response.cookies.get(settings.SESSION_COOKIE_NAME) == "1"

    refresh_response = await client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 200
    refreshed = extract_data(refresh_response)
    assert refreshed["access_token"] != session["access_token"]
    assert refresh_response.cookies.get(settings.ACCESS_COOKIE_NAME) == refreshed["access_token"]
    assert refresh_response.cookies.get(settings.REFRESH_COOKIE_NAME) == refreshed["refresh_token"]
    assert refresh_response.cookies.get(settings.SESSION_COOKIE_NAME) == "1"

    change_response = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "password123", "new_password": "password456"},
    )
    assert change_response.status_code == 200
    assert extract_data(change_response)["ok"] is True

    logout_response = await client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 200
    assert client.cookies.get(settings.ACCESS_COOKIE_NAME) is None
    assert client.cookies.get(settings.REFRESH_COOKIE_NAME) is None
    assert client.cookies.get(settings.SESSION_COOKIE_NAME) is None

    second_refresh = await client.post("/api/v1/auth/refresh")
    assert second_refresh.status_code == 401
