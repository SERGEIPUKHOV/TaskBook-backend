from __future__ import annotations

import string

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.user import User
from tests.helpers import extract_data


PASSWORD = "password123"


async def register_user(client, email: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return extract_data(response)


async def promote_to_admin(user_id: str) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one()
        user.is_admin = True
        session.add(user)
        await session.commit()


async def create_week_task(client, access_token: str, title: str) -> None:
    headers = {"Authorization": f"Bearer {access_token}"}
    week_response = await client.get("/api/v1/weeks/2026/11", headers=headers)
    assert week_response.status_code == 200

    task_response = await client.post(
        "/api/v1/weeks/2026/11/tasks",
        json={"title": title, "time_planned": 30, "start_day": 1},
        headers=headers,
    )
    assert task_response.status_code == 201


async def test_admin_endpoints_require_admin_and_allow_user_management(client):
    admin_payload = await register_user(client, "admin@example.com")
    member_payload = await register_user(client, "member@example.com")
    await promote_to_admin(admin_payload["user"]["id"])
    await create_week_task(client, member_payload["access_token"], "Member task A")
    await create_week_task(client, member_payload["access_token"], "Member task B")

    non_admin_stats = await client.get(
        "/api/v1/admin/stats",
        headers={"Authorization": f"Bearer {member_payload['access_token']}"},
    )
    assert non_admin_stats.status_code == 403

    admin_headers = {"Authorization": f"Bearer {admin_payload['access_token']}"}

    stats_response = await client.get("/api/v1/admin/stats", headers=admin_headers)
    assert stats_response.status_code == 200
    stats = extract_data(stats_response)
    assert stats["total_users"] == 2
    assert stats["total_habits"] >= 2
    assert stats["total_tasks"] == 2

    list_response = await client.get("/api/v1/admin/users?page=1&per_page=20", headers=admin_headers)
    assert list_response.status_code == 200
    users_page = extract_data(list_response)
    assert users_page["total"] == 2
    member_row = next(item for item in users_page["items"] if item["email"] == "member@example.com")
    assert member_row["tasks_count"] == 2

    block_response = await client.patch(
        f"/api/v1/admin/users/{member_payload['user']['id']}/block",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert block_response.status_code == 200
    blocked_user = extract_data(block_response)
    assert blocked_user["is_active"] is False
    assert blocked_user["tasks_count"] == 2

    blocked_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "member@example.com", "password": PASSWORD},
    )
    assert blocked_login.status_code == 403


async def test_admin_users_support_search_and_pagination(client):
    admin_payload = await register_user(client, "admin@example.com")
    first_member_payload = await register_user(client, "alpha@example.com")
    second_member_payload = await register_user(client, "beta@example.com")
    third_member_payload = await register_user(client, "gamma@example.com")
    await promote_to_admin(admin_payload["user"]["id"])
    await create_week_task(client, second_member_payload["access_token"], "Beta task")

    admin_headers = {"Authorization": f"Bearer {admin_payload['access_token']}"}

    search_response = await client.get(
        "/api/v1/admin/users?page=1&per_page=10&search=  beta@example.com  ",
        headers=admin_headers,
    )
    assert search_response.status_code == 200
    search_page = extract_data(search_response)
    assert search_page["total"] == 1
    assert search_page["items"][0]["email"] == "beta@example.com"
    assert search_page["items"][0]["tasks_count"] == 1

    first_page_response = await client.get("/api/v1/admin/users?page=1&per_page=2", headers=admin_headers)
    second_page_response = await client.get("/api/v1/admin/users?page=2&per_page=2", headers=admin_headers)
    assert first_page_response.status_code == 200
    assert second_page_response.status_code == 200

    first_page = extract_data(first_page_response)
    second_page = extract_data(second_page_response)
    assert first_page["total"] == 4
    assert first_page["page"] == 1
    assert first_page["per_page"] == 2
    assert len(first_page["items"]) == 2
    assert second_page["page"] == 2
    assert second_page["per_page"] == 2
    assert len(second_page["items"]) == 2

    combined_emails = {item["email"] for item in first_page["items"] + second_page["items"]}
    assert combined_emails == {
        "admin@example.com",
        "alpha@example.com",
        "beta@example.com",
        "gamma@example.com",
    }


async def test_admin_blocking_rejects_self_block_and_other_admin_block(client):
    first_admin_payload = await register_user(client, "admin@example.com")
    second_admin_payload = await register_user(client, "coadmin@example.com")
    member_payload = await register_user(client, "member@example.com")
    await promote_to_admin(first_admin_payload["user"]["id"])
    await promote_to_admin(second_admin_payload["user"]["id"])

    admin_headers = {"Authorization": f"Bearer {first_admin_payload['access_token']}"}

    self_block_response = await client.patch(
        f"/api/v1/admin/users/{first_admin_payload['user']['id']}/block",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert self_block_response.status_code == 400
    assert self_block_response.json()["detail"] == "Cannot change your own active status"

    other_admin_block_response = await client.patch(
        f"/api/v1/admin/users/{second_admin_payload['user']['id']}/block",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert other_admin_block_response.status_code == 400
    assert other_admin_block_response.json()["detail"] == "Cannot change another admin account"

    member_block_response = await client.patch(
        f"/api/v1/admin/users/{member_payload['user']['id']}/block",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert member_block_response.status_code == 200


async def test_admin_can_set_email_reset_password_and_impersonate_user(client):
    admin_payload = await register_user(client, "admin@example.com")
    member_payload = await register_user(client, "member@example.com")
    await register_user(client, "taken@example.com")
    await promote_to_admin(admin_payload["user"]["id"])

    admin_headers = {"Authorization": f"Bearer {admin_payload['access_token']}"}

    set_email_response = await client.patch(
        f"/api/v1/admin/users/{member_payload['user']['id']}/email",
        json={"email": " Renamed@example.com "},
        headers=admin_headers,
    )
    assert set_email_response.status_code == 200
    updated_user = extract_data(set_email_response)
    assert updated_user["email"] == "renamed@example.com"

    duplicate_email_response = await client.patch(
        f"/api/v1/admin/users/{member_payload['user']['id']}/email",
        json={"email": "taken@example.com"},
        headers=admin_headers,
    )
    assert duplicate_email_response.status_code == 400
    assert duplicate_email_response.json()["detail"] == "Email already in use"

    reset_password_response = await client.post(
        f"/api/v1/admin/users/{member_payload['user']['id']}/reset-password",
        headers=admin_headers,
    )
    assert reset_password_response.status_code == 200
    temp_password = extract_data(reset_password_response)["temp_password"]
    assert len(temp_password) == 12
    assert all(character in string.ascii_letters + string.digits for character in temp_password)

    old_password_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "renamed@example.com", "password": PASSWORD},
    )
    assert old_password_login.status_code == 401

    temp_password_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "renamed@example.com", "password": temp_password},
    )
    assert temp_password_login.status_code == 200

    impersonate_response = await client.post(
        f"/api/v1/admin/users/{member_payload['user']['id']}/impersonate",
        headers=admin_headers,
    )
    assert impersonate_response.status_code == 200
    code = extract_data(impersonate_response)["code"]

    client.cookies.clear()
    exchange_response = await client.post("/api/v1/auth/exchange-impersonate", json={"code": code})
    assert exchange_response.status_code == 200
    assert exchange_response.json() == {}

    profile_response = await client.get("/api/v1/users/me")
    assert profile_response.status_code == 200
    assert extract_data(profile_response)["email"] == "renamed@example.com"

    second_exchange_response = await client.post("/api/v1/auth/exchange-impersonate", json={"code": code})
    assert second_exchange_response.status_code == 400
    assert second_exchange_response.json()["detail"] == "Invalid or expired impersonation code"

    inactive_impersonate_response = await client.post(
        f"/api/v1/admin/users/{member_payload['user']['id']}/impersonate",
        headers=admin_headers,
    )
    assert inactive_impersonate_response.status_code == 200
    inactive_code = extract_data(inactive_impersonate_response)["code"]

    block_response = await client.patch(
        f"/api/v1/admin/users/{member_payload['user']['id']}/block",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert block_response.status_code == 200

    client.cookies.clear()
    inactive_exchange_response = await client.post("/api/v1/auth/exchange-impersonate", json={"code": inactive_code})
    assert inactive_exchange_response.status_code == 400
    assert inactive_exchange_response.json()["detail"] == "User not found or inactive"


async def test_admin_extended_actions_reject_self_other_admin_and_missing_user(client):
    first_admin_payload = await register_user(client, "admin@example.com")
    second_admin_payload = await register_user(client, "coadmin@example.com")
    await promote_to_admin(first_admin_payload["user"]["id"])
    await promote_to_admin(second_admin_payload["user"]["id"])

    admin_headers = {"Authorization": f"Bearer {first_admin_payload['access_token']}"}

    for endpoint, method, payload in (
        (f"/api/v1/admin/users/{first_admin_payload['user']['id']}/email", "patch", {"email": "self@example.com"}),
        (f"/api/v1/admin/users/{first_admin_payload['user']['id']}/reset-password", "post", None),
        (f"/api/v1/admin/users/{first_admin_payload['user']['id']}/impersonate", "post", None),
    ):
        response = await getattr(client, method)(endpoint, json=payload, headers=admin_headers)
        assert response.status_code == 400
        assert response.json()["detail"] == "Cannot modify your own account"

    for endpoint, method, payload in (
        (f"/api/v1/admin/users/{second_admin_payload['user']['id']}/email", "patch", {"email": "coadmin+new@example.com"}),
        (f"/api/v1/admin/users/{second_admin_payload['user']['id']}/reset-password", "post", None),
        (f"/api/v1/admin/users/{second_admin_payload['user']['id']}/impersonate", "post", None),
    ):
        response = await getattr(client, method)(endpoint, json=payload, headers=admin_headers)
        assert response.status_code == 400
        assert response.json()["detail"] == "Cannot modify another admin account"

    missing_response = await client.post(
        "/api/v1/admin/users/missing-user/impersonate",
        headers=admin_headers,
    )
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "User not found"
