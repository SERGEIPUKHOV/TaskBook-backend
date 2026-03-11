from __future__ import annotations

from tests.helpers import extract_data, register_and_auth


async def test_habit_crud_grid_logs_and_ownership(client):
    owner_headers, _ = await register_and_auth(client, "habit-owner@example.com")
    guest_headers, _ = await register_and_auth(client, "habit-guest@example.com")

    list_response = await client.get("/api/v1/months/2026/3/habits", headers=owner_headers)
    assert list_response.status_code == 200
    initial_habits = extract_data(list_response)
    assert len(initial_habits) >= 5

    empty_grid_response = await client.get("/api/v1/months/2026/3/habits/grid", headers=owner_headers)
    assert empty_grid_response.status_code == 200
    empty_grid = extract_data(empty_grid_response)
    assert empty_grid["days_in_month"] == 31
    assert len(empty_grid["habits"]) == len(initial_habits)
    assert all(empty_grid["logs"][habit["id"]] == [] for habit in empty_grid["habits"])

    first_habit_response = await client.post(
        "/api/v1/months/2026/3/habits",
        json={"name": "Walk every day"},
        headers=owner_headers,
    )
    assert first_habit_response.status_code == 201
    first_habit = extract_data(first_habit_response)

    duplicate_create_response = await client.post(
        "/api/v1/months/2026/3/habits",
        json={"name": "  walk every day  "},
        headers=owner_headers,
    )
    assert duplicate_create_response.status_code == 409

    second_habit_response = await client.post(
        "/api/v1/months/2026/3/habits",
        json={"name": "Journal"},
        headers=owner_headers,
    )
    assert second_habit_response.status_code == 201
    second_habit = extract_data(second_habit_response)

    rename_response = await client.patch(
        f"/api/v1/habits/{first_habit['id']}",
        json={"name": "Evening walk"},
        headers=owner_headers,
    )
    assert rename_response.status_code == 200
    renamed_habit = extract_data(rename_response)
    assert renamed_habit["name"] == "Evening walk"

    duplicate_rename_response = await client.patch(
        f"/api/v1/habits/{first_habit['id']}",
        json={"name": " journal "},
        headers=owner_headers,
    )
    assert duplicate_rename_response.status_code == 409

    first_log_response = await client.post(
        f"/api/v1/habits/{first_habit['id']}/logs/2026-03-10",
        json={},
        headers=owner_headers,
    )
    assert first_log_response.status_code == 201

    repeated_log_response = await client.post(
        f"/api/v1/habits/{first_habit['id']}/logs/2026-03-10",
        json={},
        headers=owner_headers,
    )
    assert repeated_log_response.status_code == 201

    filled_grid_response = await client.get("/api/v1/months/2026/3/habits/grid", headers=owner_headers)
    assert filled_grid_response.status_code == 200
    filled_grid = extract_data(filled_grid_response)
    assert filled_grid["logs"][first_habit["id"]] == [10]
    assert filled_grid["logs"][second_habit["id"]] == []

    blocked_patch_response = await client.patch(
        f"/api/v1/habits/{first_habit['id']}",
        json={"name": "Stolen habit"},
        headers=guest_headers,
    )
    assert blocked_patch_response.status_code == 404

    blocked_log_response = await client.post(
        f"/api/v1/habits/{first_habit['id']}/logs/2026-03-10",
        json={},
        headers=guest_headers,
    )
    assert blocked_log_response.status_code == 404

    unlog_response = await client.delete(
        f"/api/v1/habits/{first_habit['id']}/logs/2026-03-10",
        headers=owner_headers,
    )
    assert unlog_response.status_code == 204
    assert unlog_response.content == b""

    repeated_unlog_response = await client.delete(
        f"/api/v1/habits/{first_habit['id']}/logs/2026-03-10",
        headers=owner_headers,
    )
    assert repeated_unlog_response.status_code == 204
    assert repeated_unlog_response.content == b""

    delete_response = await client.delete(
        f"/api/v1/habits/{first_habit['id']}?year=2026&month=3",
        headers=owner_headers,
    )
    assert delete_response.status_code == 204
    assert delete_response.content == b""

    final_list_response = await client.get("/api/v1/months/2026/3/habits", headers=owner_headers)
    assert final_list_response.status_code == 200
    final_habits = extract_data(final_list_response)
    assert all(item["id"] != first_habit["id"] for item in final_habits)
    assert any(item["id"] == second_habit["id"] for item in final_habits)


async def test_habit_validation_returns_422_for_invalid_month_and_blank_name(client, auth_headers):
    invalid_list_response = await client.get("/api/v1/months/2026/13/habits", headers=auth_headers)
    assert invalid_list_response.status_code == 422
    assert invalid_list_response.json()["detail"] == "Invalid month"

    invalid_grid_response = await client.get("/api/v1/months/2026/13/habits/grid", headers=auth_headers)
    assert invalid_grid_response.status_code == 422
    assert invalid_grid_response.json()["detail"] == "Invalid month"

    blank_create_response = await client.post(
        "/api/v1/months/2026/3/habits",
        json={"name": "   "},
        headers=auth_headers,
    )
    assert blank_create_response.status_code == 422
    assert blank_create_response.json()["detail"] == "Habit name is required"

    create_response = await client.post(
        "/api/v1/months/2026/3/habits",
        json={"name": "Stretch"},
        headers=auth_headers,
    )
    assert create_response.status_code == 201
    habit = extract_data(create_response)

    blank_patch_response = await client.patch(
        f"/api/v1/habits/{habit['id']}",
        json={"name": "   "},
        headers=auth_headers,
    )
    assert blank_patch_response.status_code == 422
    assert blank_patch_response.json()["detail"] == "Habit name is required"

    invalid_delete_response = await client.delete(
        f"/api/v1/habits/{habit['id']}?year=2026&month=13",
        headers=auth_headers,
    )
    assert invalid_delete_response.status_code == 422
    assert invalid_delete_response.json()["detail"] == "Invalid month"
