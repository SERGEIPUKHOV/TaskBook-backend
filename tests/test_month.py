from __future__ import annotations

from tests.helpers import extract_data


async def test_month_plan_states_and_habits_flow(client, auth_headers):
    plan_response = await client.post(
        "/api/v1/months/2026/3/plan",
        json={
            "main_goal": "March goal",
            "focuses": ["A", "B"],
            "innovations": ["C"],
            "rejections": [],
            "other": "Note",
        },
        headers=auth_headers,
    )
    assert plan_response.status_code == 200
    plan = extract_data(plan_response)
    assert plan["main_goal"] == "March goal"

    state_response = await client.put(
        "/api/v1/months/2026/3/states/10",
        json={"health": 8, "productivity": 7},
        headers=auth_headers,
    )
    assert state_response.status_code == 200
    state = extract_data(state_response)
    assert state["health"] == 8
    assert state["anxiety"] == 0

    create_habit = await client.post(
        "/api/v1/months/2026/3/habits",
        json={"name": "Walk"},
        headers=auth_headers,
    )
    assert create_habit.status_code == 201
    habit = extract_data(create_habit)

    log_response = await client.post(
        f"/api/v1/habits/{habit['id']}/logs/2026-03-10",
        json={},
        headers=auth_headers,
    )
    assert log_response.status_code == 201

    bundle_response = await client.get("/api/v1/months/2026/3/bundle", headers=auth_headers)
    assert bundle_response.status_code == 200
    bundle = extract_data(bundle_response)
    assert bundle["plan"]["main_goal"] == "March goal"
    assert any(item["name"] == "Walk" for item in bundle["grid"]["habits"])
    assert bundle["grid"]["logs"][habit["id"]] == [10]
    assert any(item["date"] == "2026-03-10" and item["anxiety"] == 0 for item in bundle["states"])


async def test_month_states_support_partial_upsert_delete_and_invalid_validation(client, auth_headers):
    empty_bundle_response = await client.get("/api/v1/months/2026/4/bundle", headers=auth_headers)
    assert empty_bundle_response.status_code == 200
    empty_bundle = extract_data(empty_bundle_response)
    assert empty_bundle["plan"] is None
    assert empty_bundle["states"] == []
    assert len(empty_bundle["habits"]) == len(empty_bundle["grid"]["habits"])
    assert empty_bundle["grid"]["days_in_month"] == 30
    assert all(days == [] for days in empty_bundle["grid"]["logs"].values())

    first_upsert_response = await client.put(
        "/api/v1/months/2026/4/states/12",
        json={"health": 7},
        headers=auth_headers,
    )
    assert first_upsert_response.status_code == 200
    first_state = extract_data(first_upsert_response)
    assert first_state["health"] == 7
    assert first_state["productivity"] == 0
    assert first_state["anxiety"] == 0

    second_upsert_response = await client.put(
        "/api/v1/months/2026/4/states/12",
        json={"anxiety": 3},
        headers=auth_headers,
    )
    assert second_upsert_response.status_code == 200
    second_state = extract_data(second_upsert_response)
    assert second_state["health"] == 7
    assert second_state["productivity"] == 0
    assert second_state["anxiety"] == 3

    states_response = await client.get("/api/v1/months/2026/4/states", headers=auth_headers)
    assert states_response.status_code == 200
    states = extract_data(states_response)
    assert len(states) == 1
    assert states[0]["date"] == "2026-04-12"
    assert states[0]["anxiety"] == 3

    delete_response = await client.delete("/api/v1/months/2026/4/states/12", headers=auth_headers)
    assert delete_response.status_code == 204
    assert delete_response.content == b""

    repeat_delete_response = await client.delete("/api/v1/months/2026/4/states/12", headers=auth_headers)
    assert repeat_delete_response.status_code == 204
    assert repeat_delete_response.content == b""

    states_after_delete_response = await client.get("/api/v1/months/2026/4/states", headers=auth_headers)
    assert states_after_delete_response.status_code == 200
    assert extract_data(states_after_delete_response) == []

    invalid_day_response = await client.put(
        "/api/v1/months/2026/2/states/30",
        json={"health": 5},
        headers=auth_headers,
    )
    assert invalid_day_response.status_code == 422
    assert invalid_day_response.json()["detail"] == "Invalid day for month"

    invalid_month_states_response = await client.get("/api/v1/months/2026/13/states", headers=auth_headers)
    assert invalid_month_states_response.status_code == 422
    assert invalid_month_states_response.json()["detail"] == "Invalid month"

    invalid_month_plan_response = await client.get("/api/v1/months/2026/13/plan", headers=auth_headers)
    assert invalid_month_plan_response.status_code == 422
    assert invalid_month_plan_response.json()["detail"] == "Invalid month"

    invalid_month_bundle_response = await client.get("/api/v1/months/2026/13/bundle", headers=auth_headers)
    assert invalid_month_bundle_response.status_code == 422
    assert invalid_month_bundle_response.json()["detail"] == "Invalid month"
