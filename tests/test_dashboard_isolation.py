from __future__ import annotations

from datetime import date

from tests.helpers import extract_data


async def test_dashboard_and_user_isolation(client):
    current_year, current_week, _ = date.today().isocalendar()
    first_user = await client.post(
        "/api/v1/auth/register",
        json={"email": "alpha@example.com", "password": "password123"},
    )
    second_user = await client.post(
        "/api/v1/auth/register",
        json={"email": "beta@example.com", "password": "password123"},
    )

    first_headers = {"Authorization": f"Bearer {extract_data(first_user)['access_token']}"}
    second_headers = {"Authorization": f"Bearer {extract_data(second_user)['access_token']}"}

    created_task = await client.post(
        f"/api/v1/weeks/{current_year}/{current_week}/tasks",
        json={"title": "Private task", "start_day": 1},
        headers=first_headers,
    )
    task_id = extract_data(created_task)["id"]

    blocked_update = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "Hacked"},
        headers=second_headers,
    )
    assert blocked_update.status_code == 404

    dashboard_response = await client.get("/api/v1/dashboard", headers=first_headers)
    assert dashboard_response.status_code == 200
    dashboard = extract_data(dashboard_response)
    assert dashboard["current_week"]["week_number"] >= 1
    assert any(task["id"] == task_id for task in dashboard["tasks"])
