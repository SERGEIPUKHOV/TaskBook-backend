from __future__ import annotations


async def test_openapi_smoke_keeps_phase2_paths_and_204_contracts(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    payload = response.json()
    paths = payload["paths"]

    assert "/api/v1/months/{year}/{month}/bundle" in paths
    assert "/api/v1/days/{year}/{month}/{day}/bundle" in paths
    assert "/api/v1/weeks/{year}/{week_number}/tasks/reorder" in paths
    assert "/api/v1/habits/{habit_id}/logs/{target_date}" in paths

    delete_responses = [
        paths["/api/v1/tasks/{task_id}"]["delete"]["responses"]["204"],
        paths["/api/v1/tasks/{task_id}/status/{target_date}"]["delete"]["responses"]["204"],
        paths["/api/v1/months/{year}/{month}/states/{day}"]["delete"]["responses"]["204"],
        paths["/api/v1/days/events/{event_id}"]["delete"]["responses"]["204"],
        paths["/api/v1/habits/{habit_id}"]["delete"]["responses"]["204"],
    ]
    assert all("content" not in response_schema for response_schema in delete_responses)
