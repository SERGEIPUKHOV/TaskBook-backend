from __future__ import annotations

from datetime import date, timedelta

import app.services.task_service as task_service_module
from app.core.database import AsyncSessionLocal
from app.models.task import Task
from app.services.week_service import get_or_create_week
from tests.helpers import extract_data, register_and_auth


class FrozenToday(date):
    @classmethod
    def today(cls) -> "FrozenToday":
        return cls(2026, 4, 18)


def iso_week_ref(target: date) -> tuple[int, int]:
    iso = target.isocalendar()
    return iso.year, iso.week


async def create_task(client, headers: dict[str, str], year: int, week: int, title: str, start_day: int = 1) -> dict:
    response = await client.post(
        f"/api/v1/weeks/{year}/{week}/tasks",
        json={"title": title, "time_planned": 30, "start_day": start_day},
        headers=headers,
    )
    assert response.status_code == 201
    return extract_data(response)


async def test_auto_carry_past_week_moves_open_tasks_and_avoids_duplicates(client, monkeypatch):
    monkeypatch.setattr(task_service_module, "date", FrozenToday)
    headers, payload = await register_and_auth(client, "carry-past@example.com")

    today = FrozenToday.today()
    past_anchor = today - timedelta(days=7)
    past_year, past_week = iso_week_ref(past_anchor)
    past_sunday = date.fromisocalendar(past_year, past_week, 7)
    next_year, next_week = iso_week_ref(past_sunday + timedelta(days=1))

    planned_task = await create_task(client, headers, past_year, past_week, "Auto carry planned")
    manual_moved_task = await create_task(client, headers, past_year, past_week, "Manual moved without carry")
    done_task = await create_task(client, headers, past_year, past_week, "Completed task")
    failed_task = await create_task(client, headers, past_year, past_week, "Failed task")

    manual_moved_response = await client.put(
        f"/api/v1/tasks/{manual_moved_task['id']}/status/{past_sunday.isoformat()}",
        json={"status": "moved"},
        headers=headers,
    )
    assert manual_moved_response.status_code == 200

    done_response = await client.put(
        f"/api/v1/tasks/{done_task['id']}/status/{past_sunday.isoformat()}",
        json={"status": "done"},
        headers=headers,
    )
    assert done_response.status_code == 200

    failed_response = await client.put(
        f"/api/v1/tasks/{failed_task['id']}/status/{past_sunday.isoformat()}",
        json={"status": "failed"},
        headers=headers,
    )
    assert failed_response.status_code == 200

    first_past_tasks_response = await client.get(f"/api/v1/weeks/{past_year}/{past_week}/tasks", headers=headers)
    assert first_past_tasks_response.status_code == 200
    first_past_tasks = extract_data(first_past_tasks_response)

    planned_row = next(task for task in first_past_tasks if task["id"] == planned_task["id"])
    manual_moved_row = next(task for task in first_past_tasks if task["id"] == manual_moved_task["id"])
    done_row = next(task for task in first_past_tasks if task["id"] == done_task["id"])
    failed_row = next(task for task in first_past_tasks if task["id"] == failed_task["id"])

    assert planned_row["statuses"][past_sunday.isoformat()] == "moved"
    assert manual_moved_row["statuses"][past_sunday.isoformat()] == "moved"
    assert done_row["statuses"][past_sunday.isoformat()] == "done"
    assert failed_row["statuses"][past_sunday.isoformat()] == "failed"

    first_next_tasks_response = await client.get(f"/api/v1/weeks/{next_year}/{next_week}/tasks", headers=headers)
    assert first_next_tasks_response.status_code == 200
    first_next_tasks = extract_data(first_next_tasks_response)

    assert [task["carried_from_task_id"] for task in first_next_tasks].count(planned_task["id"]) == 1
    assert [task["carried_from_task_id"] for task in first_next_tasks].count(manual_moved_task["id"]) == 1
    assert all(task["carried_from_task_id"] != done_task["id"] for task in first_next_tasks)
    assert all(task["carried_from_task_id"] != failed_task["id"] for task in first_next_tasks)

    planned_carry = next(task for task in first_next_tasks if task["carried_from_task_id"] == planned_task["id"])
    manual_carry = next(task for task in first_next_tasks if task["carried_from_task_id"] == manual_moved_task["id"])
    assert planned_carry["start_day"] == 1
    assert manual_carry["start_day"] == 1
    assert planned_carry["calendar_export_enabled"] is False
    assert manual_carry["calendar_export_enabled"] is False

    second_past_tasks_response = await client.get(f"/api/v1/weeks/{past_year}/{past_week}/tasks", headers=headers)
    assert second_past_tasks_response.status_code == 200

    second_next_tasks_response = await client.get(f"/api/v1/weeks/{next_year}/{next_week}/tasks", headers=headers)
    assert second_next_tasks_response.status_code == 200
    second_next_tasks = extract_data(second_next_tasks_response)

    assert [task["carried_from_task_id"] for task in second_next_tasks].count(planned_task["id"]) == 1
    assert [task["carried_from_task_id"] for task in second_next_tasks].count(manual_moved_task["id"]) == 1


async def test_auto_carry_cascades_current_week_until_today(client, monkeypatch):
    monkeypatch.setattr(task_service_module, "date", FrozenToday)
    headers, _ = await register_and_auth(client, "carry-current@example.com")

    today = FrozenToday.today()
    current_year, current_week = iso_week_ref(today)
    current_task = await create_task(client, headers, current_year, current_week, "Current week task", start_day=2)

    current_tasks_response = await client.get(f"/api/v1/weeks/{current_year}/{current_week}/tasks", headers=headers)
    assert current_tasks_response.status_code == 200
    current_tasks = extract_data(current_tasks_response)
    current_row = next(task for task in current_tasks if task["id"] == current_task["id"])

    expected_moved_dates = {
        date.fromisocalendar(current_year, current_week, iso_day).isoformat()
        for iso_day in range(2, today.isoweekday())
    }
    assert set(current_row["statuses"]) == expected_moved_dates
    assert all(status == "moved" for status in current_row["statuses"].values())

    current_sunday = date.fromisocalendar(current_year, current_week, 7)
    next_year, next_week = iso_week_ref(current_sunday + timedelta(days=1))
    next_week_tasks_response = await client.get(f"/api/v1/weeks/{next_year}/{next_week}/tasks", headers=headers)
    assert next_week_tasks_response.status_code == 200
    next_week_tasks = extract_data(next_week_tasks_response)
    assert all(task["carried_from_task_id"] != current_task["id"] for task in next_week_tasks)


async def test_auto_carry_cascades_across_existing_chain_until_today(client, monkeypatch):
    monkeypatch.setattr(task_service_module, "date", FrozenToday)
    headers, payload = await register_and_auth(client, "carry-chain@example.com")

    today = FrozenToday.today()
    previous_year, previous_week = iso_week_ref(today - timedelta(days=7))
    current_year, current_week = iso_week_ref(today)

    original_task = await create_task(client, headers, previous_year, previous_week, "Broken chain source", start_day=1)

    async with AsyncSessionLocal() as session:
        current_week_record = await get_or_create_week(session, payload["user"]["id"], current_year, current_week)
        session.add(
            Task(
                user_id=payload["user"]["id"],
                week_id=current_week_record.id,
                title="Broken chain source",
                time_planned=30,
                time_actual=0,
                is_priority=False,
                order=0,
                start_day=1,
                carried_from_task_id=original_task["id"],
                calendar_export_enabled=False,
                calendar_export_bucket=None,
            ),
        )
        await session.commit()

    current_tasks_response = await client.get(f"/api/v1/weeks/{current_year}/{current_week}/tasks", headers=headers)
    assert current_tasks_response.status_code == 200
    current_tasks = extract_data(current_tasks_response)
    current_carries = [task for task in current_tasks if task["carried_from_task_id"] == original_task["id"]]
    assert len(current_carries) == 1

    current_carry = current_carries[0]
    expected_current_dates = {
        date.fromisocalendar(current_year, current_week, iso_day).isoformat()
        for iso_day in range(1, today.isoweekday())
    }
    assert set(current_carry["statuses"]) == expected_current_dates
    assert all(status == "moved" for status in current_carry["statuses"].values())

    previous_tasks_response = await client.get(f"/api/v1/weeks/{previous_year}/{previous_week}/tasks", headers=headers)
    assert previous_tasks_response.status_code == 200
    previous_tasks = extract_data(previous_tasks_response)
    previous_row = next(task for task in previous_tasks if task["id"] == original_task["id"])

    expected_previous_dates = {
        date.fromisocalendar(previous_year, previous_week, iso_day).isoformat()
        for iso_day in range(1, 8)
    }
    assert set(previous_row["statuses"]) == expected_previous_dates
    assert all(status == "moved" for status in previous_row["statuses"].values())
