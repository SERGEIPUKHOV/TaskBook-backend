from __future__ import annotations

from tests.helpers import extract_data


async def test_day_bundle_returns_tasks_habits_state_and_reflection(client, auth_headers):
    habits_response = await client.get("/api/v1/months/2026/3/habits", headers=auth_headers)
    assert habits_response.status_code == 200
    habits = extract_data(habits_response)
    assert habits

    task_response = await client.post(
        "/api/v1/weeks/2026/11/tasks",
        json={"title": "Написать day bundle", "time_planned": 60, "start_day": 2},
        headers=auth_headers,
    )
    assert task_response.status_code == 201
    task = extract_data(task_response)

    status_response = await client.put(
        f"/api/v1/tasks/{task['id']}/status/2026-03-10",
        json={"status": "done"},
        headers=auth_headers,
    )
    assert status_response.status_code == 200

    habit_log_response = await client.post(
        f"/api/v1/habits/{habits[0]['id']}/logs/2026-03-10",
        json={},
        headers=auth_headers,
    )
    assert habit_log_response.status_code == 201

    state_response = await client.put(
        "/api/v1/months/2026/3/states/10",
        json={"health": 7, "productivity": 8, "anxiety": 3},
        headers=auth_headers,
    )
    assert state_response.status_code == 200

    event_response = await client.post(
        "/api/v1/days/2026-03-10/events",
        json={"content": "Спринт завершён"},
        headers=auth_headers,
    )
    assert event_response.status_code == 201

    gratitude_response = await client.post(
        "/api/v1/days/2026-03-10/gratitudes",
        json={"content": "Спасибо команде"},
        headers=auth_headers,
    )
    assert gratitude_response.status_code == 201

    bundle_response = await client.get("/api/v1/days/2026/3/10/bundle", headers=auth_headers)
    assert bundle_response.status_code == 200
    bundle = extract_data(bundle_response)

    assert bundle["date"] == "2026-03-10"
    assert bundle["day_of_week"] == 2
    assert bundle["iso_week"] == 11
    assert bundle["tasks"][0]["title"] == "Написать day bundle"
    assert bundle["tasks"][0]["status"] == "done"
    assert bundle["habits"][0]["completed"] is True
    assert bundle["daily_state"] == {"health": 7, "productivity": 8, "anxiety": 3}
    assert bundle["key_event"] == "Спринт завершён"
    assert bundle["gratitude"] == "Спасибо команде"


async def test_day_bundle_rejects_invalid_date(client, auth_headers):
    response = await client.get("/api/v1/days/2026/2/30/bundle", headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid date"
