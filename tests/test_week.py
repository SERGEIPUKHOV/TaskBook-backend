from __future__ import annotations

from tests.helpers import extract_data


async def test_week_tasks_and_day_entries_flow(client, auth_headers):
    week_response = await client.get("/api/v1/weeks/2026/11", headers=auth_headers)
    assert week_response.status_code == 200
    week = extract_data(week_response)
    assert week["week_number"] == 11

    task_response = await client.post(
        "/api/v1/weeks/2026/11/tasks",
        json={"title": "Ship backend", "time_planned": 90, "start_day": 1},
        headers=auth_headers,
    )
    assert task_response.status_code == 201
    task = extract_data(task_response)

    status_response = await client.put(
        f"/api/v1/tasks/{task['id']}/status/2026-03-09",
        json={"status": "done"},
        headers=auth_headers,
    )
    assert status_response.status_code == 200
    assert extract_data(status_response)["status"] == "done"

    event_response = await client.post(
        "/api/v1/days/2026-03-09/events",
        json={"content": "Release prep"},
        headers=auth_headers,
    )
    assert event_response.status_code == 201
    gratitude_response = await client.post(
        "/api/v1/days/2026-03-09/gratitudes",
        json={"content": "Thanks to the team"},
        headers=auth_headers,
    )
    assert gratitude_response.status_code == 201

    bundle_response = await client.get("/api/v1/weeks/2026/11/bundle", headers=auth_headers)
    assert bundle_response.status_code == 200
    bundle = extract_data(bundle_response)
    assert bundle["tasks"][0]["statuses"]["2026-03-09"] == "done"
    assert bundle["key_events"]["2026-03-09"]["content"] == "Release prep"
    assert bundle["gratitudes"]["2026-03-09"]["content"] == "Thanks to the team"


async def test_week_bundle_syncs_moved_tasks_without_duplicates(client, auth_headers):
    initial_week_response = await client.get("/api/v1/weeks/2026/11", headers=auth_headers)
    assert initial_week_response.status_code == 200

    moved_task_response = await client.post(
        "/api/v1/weeks/2026/10/tasks",
        json={"title": "Carry me over", "time_planned": 45, "start_day": 7},
        headers=auth_headers,
    )
    assert moved_task_response.status_code == 201
    moved_task = extract_data(moved_task_response)

    friday_moved_task_response = await client.post(
        "/api/v1/weeks/2026/10/tasks",
        json={"title": "Moved on Friday only", "time_planned": 30, "start_day": 5},
        headers=auth_headers,
    )
    assert friday_moved_task_response.status_code == 201
    friday_moved_task = extract_data(friday_moved_task_response)

    untouched_task_response = await client.post(
        "/api/v1/weeks/2026/10/tasks",
        json={"title": "No statuses at all", "time_planned": 20, "start_day": 4},
        headers=auth_headers,
    )
    assert untouched_task_response.status_code == 201
    untouched_task = extract_data(untouched_task_response)

    done_task_response = await client.post(
        "/api/v1/weeks/2026/10/tasks",
        json={"title": "Already finished", "time_planned": 15, "start_day": 6},
        headers=auth_headers,
    )
    assert done_task_response.status_code == 201
    done_task = extract_data(done_task_response)

    moved_status_response = await client.put(
        f"/api/v1/tasks/{moved_task['id']}/status/2026-03-08",
        json={"status": "moved"},
        headers=auth_headers,
    )
    assert moved_status_response.status_code == 200

    friday_moved_status_response = await client.put(
        f"/api/v1/tasks/{friday_moved_task['id']}/status/2026-03-06",
        json={"status": "moved"},
        headers=auth_headers,
    )
    assert friday_moved_status_response.status_code == 200

    done_status_response = await client.put(
        f"/api/v1/tasks/{done_task['id']}/status/2026-03-08",
        json={"status": "done"},
        headers=auth_headers,
    )
    assert done_status_response.status_code == 200

    first_bundle_response = await client.get("/api/v1/weeks/2026/11/bundle", headers=auth_headers)
    assert first_bundle_response.status_code == 200
    first_bundle = extract_data(first_bundle_response)
    carried_tasks = [task for task in first_bundle["tasks"] if task["carried_from_task_id"] == moved_task["id"]]
    assert len(carried_tasks) == 1
    assert carried_tasks[0]["title"] == "Carry me over"
    assert carried_tasks[0]["start_day"] == 1
    assert all(task["carried_from_task_id"] != done_task["id"] for task in first_bundle["tasks"])
    assert all(task["carried_from_task_id"] != friday_moved_task["id"] for task in first_bundle["tasks"])
    assert all(task["carried_from_task_id"] != untouched_task["id"] for task in first_bundle["tasks"])

    second_bundle_response = await client.get("/api/v1/weeks/2026/11/bundle", headers=auth_headers)
    assert second_bundle_response.status_code == 200
    second_bundle = extract_data(second_bundle_response)
    second_carried_tasks = [task for task in second_bundle["tasks"] if task["carried_from_task_id"] == moved_task["id"]]
    assert len(second_carried_tasks) == 1


async def test_week_bundle_removes_carried_task_after_retroactive_source_change(client, auth_headers):
    await client.get("/api/v1/weeks/2026/11", headers=auth_headers)

    moved_task_response = await client.post(
        "/api/v1/weeks/2026/10/tasks",
        json={"title": "Should disappear", "time_planned": 50, "start_day": 7},
        headers=auth_headers,
    )
    assert moved_task_response.status_code == 201
    moved_task = extract_data(moved_task_response)

    moved_status_response = await client.put(
        f"/api/v1/tasks/{moved_task['id']}/status/2026-03-08",
        json={"status": "moved"},
        headers=auth_headers,
    )
    assert moved_status_response.status_code == 200

    first_bundle_response = await client.get("/api/v1/weeks/2026/11/bundle", headers=auth_headers)
    assert first_bundle_response.status_code == 200
    first_bundle = extract_data(first_bundle_response)
    carried_tasks = [task for task in first_bundle["tasks"] if task["carried_from_task_id"] == moved_task["id"]]
    assert len(carried_tasks) == 1

    done_status_response = await client.put(
        f"/api/v1/tasks/{moved_task['id']}/status/2026-03-08",
        json={"status": "done"},
        headers=auth_headers,
    )
    assert done_status_response.status_code == 200

    second_bundle_response = await client.get("/api/v1/weeks/2026/11/bundle", headers=auth_headers)
    assert second_bundle_response.status_code == 200
    second_bundle = extract_data(second_bundle_response)
    assert all(task["carried_from_task_id"] != moved_task["id"] for task in second_bundle["tasks"])


async def test_week_tasks_support_reorder_update_delete_and_status_reset(client, auth_headers):
    first_task_response = await client.post(
        "/api/v1/weeks/2026/11/tasks",
        json={"title": "Task A", "time_planned": 15, "start_day": 1},
        headers=auth_headers,
    )
    assert first_task_response.status_code == 201
    first_task = extract_data(first_task_response)

    second_task_response = await client.post(
        "/api/v1/weeks/2026/11/tasks",
        json={"title": "Task B", "time_planned": 30, "start_day": 3},
        headers=auth_headers,
    )
    assert second_task_response.status_code == 201
    second_task = extract_data(second_task_response)

    third_task_response = await client.post(
        "/api/v1/weeks/2026/11/tasks",
        json={"title": "Task C", "time_planned": 45, "start_day": 5},
        headers=auth_headers,
    )
    assert third_task_response.status_code == 201
    third_task = extract_data(third_task_response)

    reordered_ids = [third_task["id"], first_task["id"], second_task["id"]]
    reorder_response = await client.post(
        "/api/v1/weeks/2026/11/tasks/reorder",
        json={"task_ids": reordered_ids},
        headers=auth_headers,
    )
    assert reorder_response.status_code == 200
    reordered_tasks = extract_data(reorder_response)
    assert [item["id"] for item in reordered_tasks] == reordered_ids
    assert [item["order"] for item in reordered_tasks] == [0, 1, 2]

    list_response = await client.get("/api/v1/weeks/2026/11/tasks", headers=auth_headers)
    assert list_response.status_code == 200
    listed_tasks = extract_data(list_response)
    assert [item["id"] for item in listed_tasks] == reordered_ids

    patch_response = await client.patch(
        f"/api/v1/tasks/{third_task['id']}",
        json={
            "title": "Task C updated",
            "time_planned": 50,
            "time_actual": 35,
            "is_priority": True,
            "start_day": 2,
        },
        headers=auth_headers,
    )
    assert patch_response.status_code == 200
    patched_task = extract_data(patch_response)
    assert patched_task["title"] == "Task C updated"
    assert patched_task["time_planned"] == 50
    assert patched_task["time_actual"] == 35
    assert patched_task["is_priority"] is True
    assert patched_task["start_day"] == 2

    invalid_status_response = await client.put(
        f"/api/v1/tasks/{third_task['id']}/status/2026-03-20",
        json={"status": "done"},
        headers=auth_headers,
    )
    assert invalid_status_response.status_code == 422
    assert invalid_status_response.json()["detail"] == "Date is outside task week"

    status_response = await client.put(
        f"/api/v1/tasks/{third_task['id']}/status/2026-03-10",
        json={"status": "moved"},
        headers=auth_headers,
    )
    assert status_response.status_code == 200
    assert extract_data(status_response)["status"] == "moved"

    bundle_response = await client.get("/api/v1/weeks/2026/11/bundle", headers=auth_headers)
    assert bundle_response.status_code == 200
    bundle = extract_data(bundle_response)
    bundled_task = next(task for task in bundle["tasks"] if task["id"] == third_task["id"])
    assert bundled_task["statuses"]["2026-03-10"] == "moved"

    planned_response = await client.put(
        f"/api/v1/tasks/{third_task['id']}/status/2026-03-10",
        json={"status": "planned"},
        headers=auth_headers,
    )
    assert planned_response.status_code == 200
    assert extract_data(planned_response)["status"] == "planned"

    bundle_after_reset_response = await client.get("/api/v1/weeks/2026/11/bundle", headers=auth_headers)
    assert bundle_after_reset_response.status_code == 200
    bundle_after_reset = extract_data(bundle_after_reset_response)
    reset_task = next(task for task in bundle_after_reset["tasks"] if task["id"] == third_task["id"])
    assert "2026-03-10" not in reset_task["statuses"]

    delete_status_response = await client.delete(
        f"/api/v1/tasks/{third_task['id']}/status/2026-03-10",
        headers=auth_headers,
    )
    assert delete_status_response.status_code == 204
    assert delete_status_response.content == b""

    repeat_delete_status_response = await client.delete(
        f"/api/v1/tasks/{third_task['id']}/status/2026-03-10",
        headers=auth_headers,
    )
    assert repeat_delete_status_response.status_code == 204
    assert repeat_delete_status_response.content == b""

    mismatch_reorder_response = await client.post(
        "/api/v1/weeks/2026/11/tasks/reorder",
        json={"task_ids": [third_task["id"], first_task["id"]]},
        headers=auth_headers,
    )
    assert mismatch_reorder_response.status_code == 422
    assert mismatch_reorder_response.json()["detail"] == "Task ids mismatch"

    delete_task_response = await client.delete(f"/api/v1/tasks/{second_task['id']}", headers=auth_headers)
    assert delete_task_response.status_code == 204
    assert delete_task_response.content == b""

    final_tasks_response = await client.get("/api/v1/weeks/2026/11/tasks", headers=auth_headers)
    assert final_tasks_response.status_code == 200
    final_tasks = extract_data(final_tasks_response)
    assert all(task["id"] != second_task["id"] for task in final_tasks)


async def test_week_validation_rejects_invalid_iso_week(client, auth_headers):
    invalid_week_response = await client.get("/api/v1/weeks/2026/54", headers=auth_headers)
    assert invalid_week_response.status_code == 422
    assert invalid_week_response.json()["detail"] == "Invalid ISO week"
