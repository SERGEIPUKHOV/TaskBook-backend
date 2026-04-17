from __future__ import annotations

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.tracker_goal import TrackerGoal
from app.models.user import User
from tests.helpers import extract_data, register_and_auth


async def enable_tasktracker(user_id: str) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one()
        user.tasktracker_enabled = True
        session.add(user)
        await session.commit()


async def register_tracker_user(client, email: str) -> tuple[dict[str, str], dict]:
    headers, payload = await register_and_auth(client, email)
    await enable_tasktracker(payload["user"]["id"])
    return headers, payload


async def create_sprint(client, headers: dict[str, str], title: str, start_date: str, end_date: str) -> dict:
    response = await client.post(
        "/api/v1/tracker/sprints",
        json={"title": title, "start_date": start_date, "end_date": end_date},
        headers=headers,
    )
    assert response.status_code == 201
    return extract_data(response)


async def create_goal(client, headers: dict[str, str], sprint_id: str, payload: dict) -> dict:
    response = await client.post(
        f"/api/v1/tracker/sprints/{sprint_id}/goals",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 201
    return extract_data(response)


async def test_tracker_requires_access_flag(client):
    headers, _ = await register_and_auth(client, "tracker-disabled@example.com")

    response = await client.get("/api/v1/tracker/sprints", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "TaskTracker not enabled"


async def test_tracker_sprint_activation_and_switching(client):
    headers, _ = await register_tracker_user(client, "tracker-owner@example.com")

    first = await create_sprint(client, headers, "Sprint 1", "2026-04-01", "2026-04-30")
    assert first["is_active"] is True

    second = await create_sprint(client, headers, "Sprint 2", "2026-05-01", "2026-05-31")
    assert second["is_active"] is True

    list_response = await client.get("/api/v1/tracker/sprints", headers=headers)
    assert list_response.status_code == 200
    sprints = extract_data(list_response)
    assert [sprint["title"] for sprint in sprints] == ["Sprint 2", "Sprint 1"]
    assert sprints[0]["is_active"] is True
    assert sprints[1]["is_active"] is False

    patch_response = await client.patch(
        f"/api/v1/tracker/sprints/{first['id']}",
        json={"is_active": True},
        headers=headers,
    )
    assert patch_response.status_code == 200
    patched = extract_data(patch_response)
    assert patched["is_active"] is True

    list_response = await client.get("/api/v1/tracker/sprints", headers=headers)
    sprints = extract_data(list_response)
    first_row = next(item for item in sprints if item["id"] == first["id"])
    second_row = next(item for item in sprints if item["id"] == second["id"])
    assert first_row["is_active"] is True
    assert second_row["is_active"] is False


async def test_tracker_goal_tree_and_status_patch(client):
    headers, _ = await register_tracker_user(client, "tracker-tree@example.com")
    sprint = await create_sprint(client, headers, "Main", "2026-04-01", "2026-04-30")
    meta = await create_goal(
        client,
        headers,
        sprint["id"],
        {"section": "money", "level": 1, "title": "Meta goal", "sort_order": 1},
    )
    goal = await create_goal(
        client,
        headers,
        sprint["id"],
        {
            "section": "money",
            "level": 2,
            "parent_id": meta["id"],
            "title": "Main goal",
            "hypothesis": "If I keep sales rhythm",
            "sort_order": 2,
        },
    )
    subgoal = await create_goal(
        client,
        headers,
        sprint["id"],
        {
            "section": "money",
            "level": 3,
            "parent_id": goal["id"],
            "title": "Reach 50 warm leads",
            "deadline_date": "2026-04-16",
            "sort_order": 3,
        },
    )

    list_response = await client.get(f"/api/v1/tracker/sprints/{sprint['id']}/goals", headers=headers)
    assert list_response.status_code == 200
    tree = extract_data(list_response)
    assert len(tree) == 1
    assert tree[0]["title"] == "Meta goal"
    assert tree[0]["children"][0]["title"] == "Main goal"
    assert tree[0]["children"][0]["children"][0]["id"] == subgoal["id"]

    patch_response = await client.patch(
        f"/api/v1/tracker/goals/{subgoal['id']}",
        json={"status": "done_with_delay"},
        headers=headers,
    )
    assert patch_response.status_code == 200
    patched = extract_data(patch_response)
    assert patched["status"] == "done_with_delay"


async def test_tracker_deadlines_for_week_and_day_use_active_sprint_with_breadcrumb(client):
    headers, _ = await register_tracker_user(client, "tracker-deadlines@example.com")
    inactive_sprint = await create_sprint(client, headers, "Old sprint", "2026-03-01", "2026-03-31")
    old_meta = await create_goal(
        client,
        headers,
        inactive_sprint["id"],
        {"section": "health", "level": 1, "title": "Old meta"},
    )
    old_goal = await create_goal(
        client,
        headers,
        inactive_sprint["id"],
        {"section": "health", "level": 2, "parent_id": old_meta["id"], "title": "Old goal", "hypothesis": "Old"},
    )
    await create_goal(
        client,
        headers,
        inactive_sprint["id"],
        {
            "section": "health",
            "level": 3,
            "parent_id": old_goal["id"],
            "title": "Old deadline",
            "deadline_date": "2026-04-16",
        },
    )

    active_sprint = await create_sprint(client, headers, "Active sprint", "2026-04-01", "2026-04-30")
    meta = await create_goal(
        client,
        headers,
        active_sprint["id"],
        {"section": "state", "level": 1, "title": "Calm meta"},
    )
    goal = await create_goal(
        client,
        headers,
        active_sprint["id"],
        {"section": "state", "level": 2, "parent_id": meta["id"], "title": "Stable sleep", "hypothesis": "Lights off earlier"},
    )
    await create_goal(
        client,
        headers,
        active_sprint["id"],
        {
            "section": "state",
            "level": 3,
            "parent_id": goal["id"],
            "title": "Sleep by 23:00",
            "deadline_date": "2026-04-16",
        },
    )
    await create_goal(
        client,
        headers,
        active_sprint["id"],
        {
            "section": "state",
            "level": 3,
            "parent_id": goal["id"],
            "title": "Breathing reset",
            "deadline_date": "2026-04-19",
        },
    )

    week_response = await client.get("/api/v1/tracker/deadlines/week?week_year=2026&week_num=16", headers=headers)
    assert week_response.status_code == 200
    week_deadlines = extract_data(week_response)
    assert [item["title"] for item in week_deadlines] == ["Sleep by 23:00", "Breathing reset"]
    assert week_deadlines[0]["breadcrumb"] == ["Calm meta", "Stable sleep", "Sleep by 23:00"]

    day_response = await client.get("/api/v1/tracker/deadlines/day?date=2026-04-16", headers=headers)
    assert day_response.status_code == 200
    day_deadlines = extract_data(day_response)
    assert len(day_deadlines) == 1
    assert day_deadlines[0]["title"] == "Sleep by 23:00"


async def test_delete_sprint_and_goal_remove_descendants(client):
    headers, _ = await register_tracker_user(client, "tracker-delete@example.com")
    sprint = await create_sprint(client, headers, "Delete me", "2026-04-01", "2026-04-30")
    meta = await create_goal(client, headers, sprint["id"], {"section": "relations", "level": 1, "title": "Meta"})
    goal = await create_goal(
        client,
        headers,
        sprint["id"],
        {"section": "relations", "level": 2, "parent_id": meta["id"], "title": "Goal", "hypothesis": "Talk more"},
    )
    child = await create_goal(
        client,
        headers,
        sprint["id"],
        {"section": "relations", "level": 3, "parent_id": goal["id"], "title": "Subgoal", "deadline_date": "2026-04-20"},
    )

    delete_goal_response = await client.delete(f"/api/v1/tracker/goals/{goal['id']}", headers=headers)
    assert delete_goal_response.status_code == 204

    async with AsyncSessionLocal() as session:
        goals_result = await session.execute(select(TrackerGoal).where(TrackerGoal.sprint_id == sprint["id"]))
        remaining = goals_result.scalars().all()
        assert [item.id for item in remaining] == [meta["id"]]

    await create_goal(
        client,
        headers,
        sprint["id"],
        {"section": "relations", "level": 2, "parent_id": meta["id"], "title": "Goal 2", "hypothesis": "Again"},
    )
    invalid_child_response = await client.post(
        f"/api/v1/tracker/sprints/{sprint['id']}/goals",
        json={
            "section": "relations",
            "level": 3,
            "parent_id": meta["id"],
            "title": "Broken nesting",
            "deadline_date": "2026-04-22",
        },
        headers=headers,
    )
    assert invalid_child_response.status_code == 422

    delete_sprint_response = await client.delete(f"/api/v1/tracker/sprints/{sprint['id']}", headers=headers)
    assert delete_sprint_response.status_code == 204

    async with AsyncSessionLocal() as session:
        goals_result = await session.execute(select(TrackerGoal).where(TrackerGoal.sprint_id == sprint["id"]))
        assert goals_result.scalars().all() == []
