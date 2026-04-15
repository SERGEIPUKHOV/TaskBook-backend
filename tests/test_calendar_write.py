from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.calendar_connection import CalendarConnection
from app.models.calendar_event import CalendarEvent
from app.models.calendar_provider_account import CalendarProviderAccount
from app.models.planner_link import PlannerLink
from app.models.user import User
import app.services.calendar_write_service as _cws
from app.services.calendar_write_service import (
    _build_updated_rrule,
    backpropagate_google_changes_to_tasks,
    push_habit_event_time_to_google,
    push_habit_schedule_to_google,
    push_habit_title_to_google,
    push_task_event_time_to_google,
    push_task_title_to_google,
    push_task_to_google,
    unlink_task_from_google,
)
from app.services.calendar_sync_service import CalendarSyncError, NormalizedCalendarEvent
from tests.helpers import extract_data, register_and_auth


async def create_task(client, headers, title: str = "Original task") -> dict:
    response = await client.post(
        "/api/v1/weeks/2026/11/tasks",
        json={"title": title, "start_day": 2},
        headers=headers,
    )
    assert response.status_code == 201
    return extract_data(response)


async def create_habit(client, headers, name: str = "Original habit") -> dict:
    response = await client.post(
        "/api/v1/months/2026/3/habits",
        json={"name": name},
        headers=headers,
    )
    assert response.status_code == 201
    return extract_data(response)


async def seed_calendar_import_link(
    email: str,
    *,
    target_kind: str,
    target_id: str,
    provider: str = "google",
    external_account_id: str = "primary",
    external_event_id: str = "google-event-1",
    raw_payload: dict | None = None,
    source_timezone: str = "UTC",
) -> dict[str, str]:
    async with AsyncSessionLocal() as session:
        user_result = await session.execute(select(User).where(User.email == email))
        user = user_result.scalar_one()

        provider_account_id: str | None = None
        if provider == "google":
            provider_account = CalendarProviderAccount(
                user_id=user.id,
                provider="google",
                status="active",
                external_account_id="google-account",
                account_label="Google Calendar",
                access_token_encrypted="ignored",
                refresh_token_encrypted="ignored",
            )
            session.add(provider_account)
            await session.flush()
            provider_account_id = provider_account.id

        connection = CalendarConnection(
            user_id=user.id,
            provider_account_id=provider_account_id,
            provider=provider,
            status="active",
            external_account_id=external_account_id,
            account_label="Imported calendar",
            color="#4285F4",
        )
        session.add(connection)
        await session.flush()

        event = CalendarEvent(
            connection_id=connection.id,
            user_id=user.id,
            external_event_id=external_event_id,
            external_calendar_id=external_account_id,
            title="Imported event",
            description=None,
            location=None,
            starts_at=datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc),
            ends_at=datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc),
            source_timezone=source_timezone,
            is_all_day=False,
            status="confirmed",
            raw_payload=raw_payload or {},
        )
        session.add(event)
        await session.flush()

        session.add(
            PlannerLink(
                user_id=user.id,
                source_kind="calendar_event",
                source_ref=f"{connection.id}:{external_event_id}",
                target_kind=target_kind,
                target_id=target_id,
                link_mode="import_copy",
            ),
        )
        await session.commit()

        return {
            "connection_id": connection.id,
            "event_id": event.id,
            "user_id": user.id,
        }


async def get_user_id(email: str) -> str:
    async with AsyncSessionLocal() as session:
        user_result = await session.execute(select(User).where(User.email == email))
        return user_result.scalar_one().id


def test_build_updated_rrule_replaces_byday() -> None:
    assert _build_updated_rrule("RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR;WKST=MO", [1, 3, 5, 6]) == (
        "RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR,SA;WKST=MO"
    )


def test_build_updated_rrule_preserves_extra_parts() -> None:
    assert _build_updated_rrule("RRULE:FREQ=WEEKLY;BYDAY=MO;COUNT=5;WKST=MO", [2, 4]) == (
        "RRULE:FREQ=WEEKLY;BYDAY=TU,TH;COUNT=5;WKST=MO"
    )


def test_build_updated_rrule_adds_byday_when_missing() -> None:
    assert _build_updated_rrule("RRULE:FREQ=WEEKLY", [5]) == "RRULE:FREQ=WEEKLY;BYDAY=FR"


def test_build_updated_rrule_returns_none_for_non_weekly() -> None:
    assert _build_updated_rrule("RRULE:FREQ=DAILY;BYDAY=MO", [1, 3, 5]) is None


async def test_push_task_title_to_google_without_link_does_nothing(client, monkeypatch):
    email = "calendar-write-task-nolink@example.com"
    headers, _ = await register_and_auth(client, email)
    task = await create_task(client, headers)
    patch_calls: list[tuple[str, str, str, dict]] = []

    async def fake_google_patch(access_token: str, calendar_id: str, event_id: str, body: dict) -> None:
        patch_calls.append((access_token, calendar_id, event_id, body))

    monkeypatch.setattr("app.services.calendar_write_service._google_patch", fake_google_patch)

    async with AsyncSessionLocal() as session:
        await push_task_title_to_google(session, await get_user_id(email), task["id"], "Renamed task")

    assert patch_calls == []


async def test_push_habit_schedule_to_google_without_link_does_nothing(client, monkeypatch):
    email = "calendar-write-schedule-nolink@example.com"
    headers, _ = await register_and_auth(client, email)
    habit = await create_habit(client, headers)
    patch_calls: list[tuple[str, str, str, dict]] = []
    sync_calls: list[tuple[str, str | None]] = []

    async def fake_google_patch(access_token: str, calendar_id: str, event_id: str, body: dict) -> None:
        patch_calls.append((access_token, calendar_id, event_id, body))

    async def fake_sync_google_connection(db, connection, *, provider_account=None) -> None:
        sync_calls.append((connection.id, provider_account.id if provider_account else None))

    monkeypatch.setattr("app.services.calendar_write_service._google_patch", fake_google_patch)
    monkeypatch.setattr("app.services.calendar_google_service.sync_google_connection", fake_sync_google_connection)

    async with AsyncSessionLocal() as session:
        await push_habit_schedule_to_google(session, await get_user_id(email), habit["id"], [1, 3, 5])

    assert patch_calls == []
    assert sync_calls == []


async def test_push_task_title_to_google_ignores_apple_links(client, monkeypatch):
    email = "calendar-write-task-apple@example.com"
    headers, _ = await register_and_auth(client, email)
    task = await create_task(client, headers)
    await seed_calendar_import_link(
        email,
        target_kind="task",
        target_id=task["id"],
        provider="apple",
        external_account_id="apple-feed-1",
        external_event_id="apple-event-1",
    )
    patch_calls: list[tuple[str, str, str, dict]] = []

    async def fake_google_patch(access_token: str, calendar_id: str, event_id: str, body: dict) -> None:
        patch_calls.append((access_token, calendar_id, event_id, body))

    monkeypatch.setattr("app.services.calendar_write_service._google_patch", fake_google_patch)

    async with AsyncSessionLocal() as session:
        await push_task_title_to_google(session, await get_user_id(email), task["id"], "Renamed task")

    assert patch_calls == []


async def test_push_task_title_to_google_patches_linked_google_event(client, monkeypatch):
    email = "calendar-write-task-google@example.com"
    headers, _ = await register_and_auth(client, email)
    task = await create_task(client, headers)
    await seed_calendar_import_link(
        email,
        target_kind="task",
        target_id=task["id"],
        provider="google",
        external_account_id="team@group.calendar.google.com",
        external_event_id="google-task-1",
    )
    patch_calls: list[tuple[str, str, str, dict]] = []

    async def fake_ensure_google_access_token(_provider_account: CalendarProviderAccount) -> tuple[str, bool]:
        return "google-access-token", False

    async def fake_google_patch(access_token: str, calendar_id: str, event_id: str, body: dict) -> None:
        patch_calls.append((access_token, calendar_id, event_id, body))

    monkeypatch.setattr(
        "app.services.calendar_write_service._ensure_google_access_token",
        fake_ensure_google_access_token,
    )
    monkeypatch.setattr("app.services.calendar_write_service._google_patch", fake_google_patch)

    async with AsyncSessionLocal() as session:
        await push_task_title_to_google(session, await get_user_id(email), task["id"], "Renamed task")

    assert patch_calls == [
        (
            "google-access-token",
            "team@group.calendar.google.com",
            "google-task-1",
            {"summary": "Renamed task"},
        ),
    ]


async def test_push_habit_title_to_google_prefers_recurring_master_event(client, monkeypatch):
    email = "calendar-write-habit-series@example.com"
    headers, _ = await register_and_auth(client, email)
    habit = await create_habit(client, headers)
    await seed_calendar_import_link(
        email,
        target_kind="habit",
        target_id=habit["id"],
        provider="google",
        external_account_id="primary",
        external_event_id="google-instance-1",
        raw_payload={"recurringEventId": "google-master-1"},
    )
    patch_calls: list[tuple[str, str, str, dict]] = []

    async def fake_ensure_google_access_token(_provider_account: CalendarProviderAccount) -> tuple[str, bool]:
        return "google-access-token", False

    async def fake_google_patch(access_token: str, calendar_id: str, event_id: str, body: dict) -> None:
        patch_calls.append((access_token, calendar_id, event_id, body))

    monkeypatch.setattr(
        "app.services.calendar_write_service._ensure_google_access_token",
        fake_ensure_google_access_token,
    )
    monkeypatch.setattr("app.services.calendar_write_service._google_patch", fake_google_patch)

    async with AsyncSessionLocal() as session:
        await push_habit_title_to_google(session, await get_user_id(email), habit["id"], "Renamed habit")

    assert patch_calls == [
        (
            "google-access-token",
            "primary",
            "google-master-1",
            {"summary": "Renamed habit"},
        ),
    ]


async def test_push_habit_title_to_google_uses_event_id_for_standalone_event(client, monkeypatch):
    email = "calendar-write-habit-standalone@example.com"
    headers, _ = await register_and_auth(client, email)
    habit = await create_habit(client, headers)
    await seed_calendar_import_link(
        email,
        target_kind="habit",
        target_id=habit["id"],
        provider="google",
        external_account_id="primary",
        external_event_id="google-habit-standalone-1",
    )
    patch_calls: list[tuple[str, str, str, dict]] = []

    async def fake_ensure_google_access_token(_provider_account: CalendarProviderAccount) -> tuple[str, bool]:
        return "google-access-token", False

    async def fake_google_patch(access_token: str, calendar_id: str, event_id: str, body: dict) -> None:
        patch_calls.append((access_token, calendar_id, event_id, body))

    monkeypatch.setattr(
        "app.services.calendar_write_service._ensure_google_access_token",
        fake_ensure_google_access_token,
    )
    monkeypatch.setattr("app.services.calendar_write_service._google_patch", fake_google_patch)

    async with AsyncSessionLocal() as session:
        await push_habit_title_to_google(session, await get_user_id(email), habit["id"], "Renamed habit")

    assert patch_calls == [
        (
            "google-access-token",
            "primary",
            "google-habit-standalone-1",
            {"summary": "Renamed habit"},
        ),
    ]


async def test_push_habit_schedule_to_google_patches_rrule_and_syncs(client, monkeypatch):
    email = "calendar-write-schedule-google@example.com"
    headers, _ = await register_and_auth(client, email)
    habit = await create_habit(client, headers)
    link_meta = await seed_calendar_import_link(
        email,
        target_kind="habit",
        target_id=habit["id"],
        provider="google",
        external_account_id="primary",
        external_event_id="google-habit-instance-1",
        raw_payload={"recurringEventId": "google-master-2", "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR;WKST=MO"]},
    )
    patch_calls: list[tuple[str, str, str, dict]] = []
    sync_calls: list[tuple[str, str | None]] = []

    async def fake_ensure_google_access_token(_provider_account: CalendarProviderAccount) -> tuple[str, bool]:
        return "google-access-token", False

    async def fake_google_patch(access_token: str, calendar_id: str, event_id: str, body: dict) -> None:
        patch_calls.append((access_token, calendar_id, event_id, body))

    async def fake_sync_google_connection(db, connection, *, provider_account=None) -> None:
        sync_calls.append((connection.id, provider_account.id if provider_account else None))

    monkeypatch.setattr(
        "app.services.calendar_write_service._ensure_google_access_token",
        fake_ensure_google_access_token,
    )
    monkeypatch.setattr("app.services.calendar_write_service._google_patch", fake_google_patch)
    monkeypatch.setattr("app.services.calendar_google_service.sync_google_connection", fake_sync_google_connection)

    async with AsyncSessionLocal() as session:
        await push_habit_schedule_to_google(session, await get_user_id(email), habit["id"], [1, 3, 5, 6])

    assert patch_calls == [
        (
            "google-access-token",
            "primary",
            "google-master-2",
            {"recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR,SA;WKST=MO"]},
        ),
    ]
    assert len(sync_calls) == 1
    assert sync_calls[0][0] == link_meta["connection_id"]


async def test_push_habit_event_time_to_google_patches_master_event(client, monkeypatch):
    email = "calendar-write-habit-time@example.com"
    headers, _ = await register_and_auth(client, email)
    habit = await create_habit(client, headers)
    await seed_calendar_import_link(
        email,
        target_kind="habit",
        target_id=habit["id"],
        provider="google",
        external_account_id="primary",
        external_event_id="google-habit-instance-time",
        raw_payload={"recurringEventId": "google-master-time"},
    )
    patch_calls: list[tuple[str, str, str, dict]] = []

    async def fake_ensure_google_access_token(_provider_account: CalendarProviderAccount) -> tuple[str, bool]:
        return "google-access-token", False

    async def fake_google_patch(access_token: str, calendar_id: str, event_id: str, body: dict) -> None:
        patch_calls.append((access_token, calendar_id, event_id, body))

    async def fake_fetch_google_event(access_token: str, calendar_id: str, event_id: str) -> dict:
        return {
            "start": {"dateTime": "2026-03-10T09:30:00+00:00"},
            "end": {"dateTime": "2026-03-10T11:00:00+00:00"},
        }

    monkeypatch.setattr(
        "app.services.calendar_write_service._ensure_google_access_token",
        fake_ensure_google_access_token,
    )
    monkeypatch.setattr("app.services.calendar_write_service._google_patch", fake_google_patch)
    monkeypatch.setattr(_cws, "_fetch_google_event", fake_fetch_google_event)

    async with AsyncSessionLocal() as session:
        await push_habit_event_time_to_google(session, await get_user_id(email), habit["id"], "10:30", "11:45")

    assert patch_calls == [
        (
            "google-access-token",
            "primary",
            "google-master-time",
            {
                "start": {"dateTime": "2026-03-10T10:30:00+00:00", "timeZone": "UTC"},
                "end": {"dateTime": "2026-03-10T11:45:00+00:00", "timeZone": "UTC"},
            },
        ),
    ]


async def test_push_habit_event_time_to_google_preserves_master_timezone(client, monkeypatch):
    email = "calendar-write-habit-time-tz@example.com"
    headers, _ = await register_and_auth(client, email)
    habit = await create_habit(client, headers)
    await seed_calendar_import_link(
        email,
        target_kind="habit",
        target_id=habit["id"],
        provider="google",
        external_account_id="primary",
        external_event_id="google-habit-instance-time-tz",
        raw_payload={"recurringEventId": "google-master-time-tz"},
        source_timezone="Europe/Moscow",
    )
    patch_calls: list[tuple[str, str, str, dict]] = []

    async def fake_ensure_google_access_token(_provider_account: CalendarProviderAccount) -> tuple[str, bool]:
        return "google-access-token", False

    async def fake_google_patch(access_token: str, calendar_id: str, event_id: str, body: dict) -> None:
        patch_calls.append((access_token, calendar_id, event_id, body))

    async def fake_fetch_google_event(access_token: str, calendar_id: str, event_id: str) -> dict:
        return {
            "start": {"dateTime": "2026-03-10T09:30:00+03:00", "timeZone": "Europe/Moscow"},
            "end": {"dateTime": "2026-03-10T11:00:00+03:00", "timeZone": "Europe/Moscow"},
        }

    monkeypatch.setattr(
        "app.services.calendar_write_service._ensure_google_access_token",
        fake_ensure_google_access_token,
    )
    monkeypatch.setattr("app.services.calendar_write_service._google_patch", fake_google_patch)
    monkeypatch.setattr(_cws, "_fetch_google_event", fake_fetch_google_event)

    async with AsyncSessionLocal() as session:
        await push_habit_event_time_to_google(session, await get_user_id(email), habit["id"], "10:30", "11:45")

    assert patch_calls == [
        (
            "google-access-token",
            "primary",
            "google-master-time-tz",
            {
                "start": {"dateTime": "2026-03-10T10:30:00+03:00", "timeZone": "Europe/Moscow"},
                "end": {"dateTime": "2026-03-10T11:45:00+03:00", "timeZone": "Europe/Moscow"},
            },
        ),
    ]


async def test_push_habit_schedule_to_google_fetches_master_rrule_when_missing_locally(client, monkeypatch):
    email = "calendar-write-schedule-fetch@example.com"
    headers, _ = await register_and_auth(client, email)
    habit = await create_habit(client, headers)
    await seed_calendar_import_link(
        email,
        target_kind="habit",
        target_id=habit["id"],
        provider="google",
        external_account_id="primary",
        external_event_id="google-habit-instance-fetch",
        raw_payload={"recurringEventId": "google-master-fetch"},
    )
    patch_calls: list[tuple[str, str, str, dict]] = []

    async def fake_ensure_google_access_token(_provider_account: CalendarProviderAccount) -> tuple[str, bool]:
        return "google-access-token", False

    async def fake_google_get(access_token: str, path: str, params=None) -> dict:
        assert access_token == "google-access-token"
        assert path == "/calendars/primary/events/google-master-fetch"
        return {"recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=TU,TH;WKST=MO"]}

    async def fake_google_patch(access_token: str, calendar_id: str, event_id: str, body: dict) -> None:
        patch_calls.append((access_token, calendar_id, event_id, body))

    async def fake_sync_google_connection(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(
        "app.services.calendar_write_service._ensure_google_access_token",
        fake_ensure_google_access_token,
    )
    monkeypatch.setattr("app.services.calendar_google_service._google_get", fake_google_get)
    monkeypatch.setattr("app.services.calendar_write_service._google_patch", fake_google_patch)
    monkeypatch.setattr("app.services.calendar_google_service.sync_google_connection", fake_sync_google_connection)

    async with AsyncSessionLocal() as session:
        await push_habit_schedule_to_google(session, await get_user_id(email), habit["id"], [2, 4, 6])

    assert patch_calls == [
        (
            "google-access-token",
            "primary",
            "google-master-fetch",
            {"recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=TU,TH,SA;WKST=MO"]},
        ),
    ]


async def test_push_task_title_to_google_swallows_google_errors(client, monkeypatch):
    email = "calendar-write-task-errors@example.com"
    headers, _ = await register_and_auth(client, email)
    task = await create_task(client, headers)
    await seed_calendar_import_link(
        email,
        target_kind="task",
        target_id=task["id"],
        provider="google",
        external_account_id="primary",
        external_event_id="google-task-error-1",
    )

    async def fake_ensure_google_access_token(_provider_account: CalendarProviderAccount) -> tuple[str, bool]:
        return "google-access-token", False

    async def fake_google_patch(*_args, **_kwargs) -> None:
        raise RuntimeError("Google unavailable")

    monkeypatch.setattr(
        "app.services.calendar_write_service._ensure_google_access_token",
        fake_ensure_google_access_token,
    )
    monkeypatch.setattr("app.services.calendar_write_service._google_patch", fake_google_patch)

    async with AsyncSessionLocal() as session:
        await push_task_title_to_google(session, await get_user_id(email), task["id"], "Renamed task")


async def test_push_habit_schedule_to_google_swallows_google_errors(client, monkeypatch):
    email = "calendar-write-schedule-errors@example.com"
    headers, _ = await register_and_auth(client, email)
    habit = await create_habit(client, headers)
    await seed_calendar_import_link(
        email,
        target_kind="habit",
        target_id=habit["id"],
        provider="google",
        external_account_id="primary",
        external_event_id="google-habit-error-1",
        raw_payload={"recurringEventId": "google-master-error", "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO"]},
    )

    async def fake_ensure_google_access_token(_provider_account: CalendarProviderAccount) -> tuple[str, bool]:
        return "google-access-token", False

    async def fake_google_patch(*_args, **_kwargs) -> None:
        raise RuntimeError("Google unavailable")

    monkeypatch.setattr(
        "app.services.calendar_write_service._ensure_google_access_token",
        fake_ensure_google_access_token,
    )
    monkeypatch.setattr("app.services.calendar_write_service._google_patch", fake_google_patch)

    async with AsyncSessionLocal() as session:
        await push_habit_schedule_to_google(session, await get_user_id(email), habit["id"], [1, 3, 5])


async def test_patch_task_route_stays_200_when_writeback_fails(client, monkeypatch):
    email = "calendar-write-task-route@example.com"
    headers, _ = await register_and_auth(client, email)
    task = await create_task(client, headers)

    async def fake_push_task_title_to_google(*_args, **_kwargs) -> None:
        raise RuntimeError("Google unavailable")

    monkeypatch.setattr("app.api.v1.tasks.push_task_title_to_google", fake_push_task_title_to_google)

    response = await client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"title": "Renamed via route"},
        headers=headers,
    )

    assert response.status_code == 200
    assert extract_data(response)["title"] == "Renamed via route"


async def test_patch_habit_route_stays_200_when_writeback_fails(client, monkeypatch):
    email = "calendar-write-habit-route@example.com"
    headers, _ = await register_and_auth(client, email)
    habit = await create_habit(client, headers)

    async def fake_push_habit_title_to_google(*_args, **_kwargs) -> None:
        raise RuntimeError("Google unavailable")

    monkeypatch.setattr("app.api.v1.habits.push_habit_title_to_google", fake_push_habit_title_to_google)

    response = await client.patch(
        f"/api/v1/habits/{habit['id']}",
        json={"name": "  Renamed via route  "},
        headers=headers,
    )

    assert response.status_code == 200
    assert extract_data(response)["name"] == "Renamed via route"


async def test_patch_habit_route_stays_200_when_schedule_writeback_fails(client, monkeypatch):
    email = "calendar-write-habit-schedule-route@example.com"
    headers, _ = await register_and_auth(client, email)
    habit = await create_habit(client, headers)

    async def fake_push_habit_schedule_to_google(*_args, **_kwargs) -> None:
        raise RuntimeError("Google unavailable")

    monkeypatch.setattr("app.api.v1.habits.push_habit_schedule_to_google", fake_push_habit_schedule_to_google)

    response = await client.patch(
        f"/api/v1/habits/{habit['id']}",
        json={"schedule_days": [5, 1, 3]},
        headers=headers,
    )

    assert response.status_code == 200
    assert extract_data(response)["schedule_days"] == [1, 3, 5]


async def test_patch_habit_event_time_route_stays_200_when_writeback_fails(client, monkeypatch):
    email = "calendar-write-habit-time-route@example.com"
    headers, _ = await register_and_auth(client, email)
    habit = await create_habit(client, headers)

    async def fake_push_habit_event_time_to_google(*_args, **_kwargs) -> None:
        raise RuntimeError("Google unavailable")

    monkeypatch.setattr("app.api.v1.habits.push_habit_event_time_to_google", fake_push_habit_event_time_to_google)

    response = await client.patch(
        f"/api/v1/habits/{habit['id']}/event-time",
        json={"starts_at": "09:00", "ends_at": "10:00"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["data"] is None


# ── push_task_to_google ────────────────────────────────────────────────────────

async def test_push_task_to_google_creates_event_and_planner_link(client, monkeypatch):
    email = "cw-task-export-ok@example.com"
    headers, _ = await register_and_auth(client, email)
    task = await create_task(client, headers, "Export me")

    link_meta = await seed_calendar_import_link(
        email,
        target_kind="task",
        target_id="__seed_only__",  # unrelated link, won't affect task
        provider="google",
        external_account_id="primary",
        external_event_id="unrelated-event",
    )
    connection_id = link_meta["connection_id"]
    user_id = link_meta["user_id"]

    post_calls: list[dict] = []

    async def fake_ensure_google_access_token(_pa) -> tuple[str, bool]:
        return "tok", False

    async def fake_google_post_event(_token, _cal_id, body: dict) -> dict:
        post_calls.append(body)
        return {"id": "new-google-event-123"}

    import app.services.calendar_write_service as _cws2
    monkeypatch.setattr("app.services.calendar_write_service._ensure_google_access_token", fake_ensure_google_access_token)
    monkeypatch.setattr(_cws2, "_google_post_event", fake_google_post_event)

    async with AsyncSessionLocal() as session:
        ext_id = await push_task_to_google(session, str(user_id), task["id"], str(connection_id))

    assert ext_id == "new-google-event-123"
    assert len(post_calls) == 1
    assert post_calls[0]["summary"] == "Export me"

    async with AsyncSessionLocal() as session:
        link_result = await session.execute(
            select(PlannerLink).where(
                PlannerLink.target_id == task["id"],
                PlannerLink.target_kind == "task",
                PlannerLink.link_mode == "export_copy",
            )
        )
        link = link_result.scalar_one_or_none()
    assert link is not None
    assert f":{ext_id}" in link.source_ref


async def test_push_task_to_google_raises_when_connection_missing(client, monkeypatch):
    email = "cw-task-export-no-conn@example.com"
    headers, _ = await register_and_auth(client, email)
    task = await create_task(client, headers)
    user_id = await get_user_id(email)

    async with AsyncSessionLocal() as session:
        try:
            await push_task_to_google(session, user_id, task["id"], "nonexistent-connection-id")
            assert False, "should have raised"
        except CalendarSyncError:
            pass


async def test_push_task_to_google_removes_existing_link_before_creating(client, monkeypatch):
    email = "cw-task-export-relink@example.com"
    headers, _ = await register_and_auth(client, email)
    task = await create_task(client, headers, "Relink task")

    link_meta = await seed_calendar_import_link(
        email,
        target_kind="task",
        target_id=task["id"],
        provider="google",
        external_account_id="primary",
        external_event_id="old-google-event",
    )
    connection_id = link_meta["connection_id"]
    user_id = link_meta["user_id"]

    async def fake_ensure_google_access_token(_pa) -> tuple[str, bool]:
        return "tok", False

    async def fake_google_post_event(_token, _cal_id, _body) -> dict:
        return {"id": "new-google-event-relink"}

    import app.services.calendar_write_service as _cws2
    monkeypatch.setattr("app.services.calendar_write_service._ensure_google_access_token", fake_ensure_google_access_token)
    monkeypatch.setattr(_cws2, "_google_post_event", fake_google_post_event)

    async with AsyncSessionLocal() as session:
        await push_task_to_google(session, str(user_id), task["id"], str(connection_id))

    async with AsyncSessionLocal() as session:
        links_result = await session.execute(
            select(PlannerLink).where(
                PlannerLink.target_id == task["id"],
                PlannerLink.target_kind == "task",
            )
        )
        links = links_result.scalars().all()
    assert len(links) == 1
    assert links[0].link_mode == "export_copy"
    assert "new-google-event-relink" in links[0].source_ref


# ── unlink_task_from_google ───────────────────────────────────────────────────

async def test_unlink_task_from_google_removes_link_keeps_event(client):
    email = "cw-task-unlink@example.com"
    headers, _ = await register_and_auth(client, email)
    task = await create_task(client, headers, "Unlink me")

    link_meta = await seed_calendar_import_link(
        email,
        target_kind="task",
        target_id=task["id"],
        provider="google",
        external_account_id="primary",
        external_event_id="google-unlink-event",
    )
    user_id = link_meta["user_id"]
    event_id = link_meta["event_id"]

    async with AsyncSessionLocal() as session:
        await unlink_task_from_google(session, str(user_id), task["id"])

    async with AsyncSessionLocal() as session:
        link_result = await session.execute(
            select(PlannerLink).where(PlannerLink.target_id == task["id"])
        )
        assert link_result.scalar_one_or_none() is None

        event_result = await session.execute(
            select(CalendarEvent).where(CalendarEvent.id == event_id)
        )
        assert event_result.scalar_one_or_none() is not None


async def test_unlink_task_from_google_noop_when_no_link(client):
    email = "cw-task-unlink-noop@example.com"
    headers, _ = await register_and_auth(client, email)
    task = await create_task(client, headers)
    user_id = await get_user_id(email)

    async with AsyncSessionLocal() as session:
        await unlink_task_from_google(session, user_id, task["id"])


# ── push_task_event_time_to_google ────────────────────────────────────────────

async def test_push_task_event_time_to_google_patches_linked_event(client, monkeypatch):
    email = "cw-task-event-time@example.com"
    headers, _ = await register_and_auth(client, email)
    task = await create_task(client, headers, "Timed task")

    await seed_calendar_import_link(
        email,
        target_kind="task",
        target_id=task["id"],
        provider="google",
        external_account_id="primary",
        external_event_id="google-task-time-1",
    )
    user_id = await get_user_id(email)
    patch_calls: list[tuple] = []

    async def fake_ensure_google_access_token(_pa) -> tuple[str, bool]:
        return "tok", False

    async def fake_google_patch(token, cal_id, event_id, body) -> None:
        patch_calls.append((token, cal_id, event_id, body))

    monkeypatch.setattr("app.services.calendar_write_service._ensure_google_access_token", fake_ensure_google_access_token)
    monkeypatch.setattr("app.services.calendar_write_service._google_patch", fake_google_patch)

    async with AsyncSessionLocal() as session:
        await push_task_event_time_to_google(session, user_id, task["id"], "10:00", "11:30")

    assert len(patch_calls) == 1
    body = patch_calls[0][3]
    assert "start" in body and "end" in body


async def test_push_task_event_time_to_google_noop_when_no_link(client, monkeypatch):
    email = "cw-task-event-time-noop@example.com"
    headers, _ = await register_and_auth(client, email)
    task = await create_task(client, headers)
    user_id = await get_user_id(email)
    patch_calls: list = []

    async def fake_google_patch(*_args, **_kwargs) -> None:
        patch_calls.append(True)

    monkeypatch.setattr("app.services.calendar_write_service._google_patch", fake_google_patch)

    async with AsyncSessionLocal() as session:
        await push_task_event_time_to_google(session, user_id, task["id"], "10:00", "11:00")

    assert patch_calls == []


# ── backpropagate_google_changes_to_tasks ─────────────────────────────────────

async def _make_normalized_event(
    external_event_id: str,
    title: str,
    status: str = "confirmed",
    starts_at: datetime | None = None,
) -> NormalizedCalendarEvent:
    return NormalizedCalendarEvent(
        external_event_id=external_event_id,
        external_calendar_id="primary",
        title=title,
        description=None,
        location=None,
        starts_at=starts_at or datetime(2026, 3, 9, 9, 0, tzinfo=timezone.utc),
        ends_at=starts_at or datetime(2026, 3, 9, 10, 0, tzinfo=timezone.utc),
        source_timezone="UTC",
        is_all_day=False,
        status=status,
        raw_payload={},
    )


async def test_backpropagate_renames_task_when_google_event_title_changes(client):
    email = "cw-backprop-rename@example.com"
    headers, _ = await register_and_auth(client, email)
    task = await create_task(client, headers, "Old title")

    link_meta = await seed_calendar_import_link(
        email,
        target_kind="task",
        target_id=task["id"],
        provider="google",
        external_account_id="primary",
        external_event_id="google-backprop-rename",
    )
    connection_id = str(link_meta["connection_id"])
    user_id = str(link_meta["user_id"])

    events = [await _make_normalized_event("google-backprop-rename", "New title from Google")]

    async with AsyncSessionLocal() as session:
        await backpropagate_google_changes_to_tasks(session, connection_id, user_id, events)

    response = await client.get(f"/api/v1/weeks/2026/11/tasks", headers=headers)
    tasks = response.json()["data"]
    task_data = next(t for t in tasks if t["id"] == task["id"])
    assert task_data["title"] == "New title from Google"


async def test_backpropagate_removes_link_when_event_cancelled(client):
    email = "cw-backprop-cancel@example.com"
    headers, _ = await register_and_auth(client, email)
    task = await create_task(client, headers, "Linked task")

    link_meta = await seed_calendar_import_link(
        email,
        target_kind="task",
        target_id=task["id"],
        provider="google",
        external_account_id="primary",
        external_event_id="google-backprop-cancel",
    )
    connection_id = str(link_meta["connection_id"])
    user_id = str(link_meta["user_id"])

    events = [await _make_normalized_event("google-backprop-cancel", "Cancelled event", status="cancelled")]

    async with AsyncSessionLocal() as session:
        await backpropagate_google_changes_to_tasks(session, connection_id, user_id, events)

    async with AsyncSessionLocal() as session:
        link_result = await session.execute(
            select(PlannerLink).where(PlannerLink.target_id == task["id"])
        )
        assert link_result.scalar_one_or_none() is None


async def test_backpropagate_updates_start_day_when_date_changes(client):
    email = "cw-backprop-date@example.com"
    headers, _ = await register_and_auth(client, email)
    task = await create_task(client, headers, "Moved task")

    link_meta = await seed_calendar_import_link(
        email,
        target_kind="task",
        target_id=task["id"],
        provider="google",
        external_account_id="primary",
        external_event_id="google-backprop-date",
    )
    connection_id = str(link_meta["connection_id"])
    user_id = str(link_meta["user_id"])

    # Week 11 of 2026: Mon 2026-03-09 .. Sun 2026-03-15
    # Move event to Wednesday 2026-03-11 → start_day = 3
    new_starts_at = datetime(2026, 3, 11, 9, 0, tzinfo=timezone.utc)
    events = [await _make_normalized_event("google-backprop-date", "Moved task", starts_at=new_starts_at)]

    async with AsyncSessionLocal() as session:
        await backpropagate_google_changes_to_tasks(session, connection_id, user_id, events)

    response = await client.get("/api/v1/weeks/2026/11/tasks", headers=headers)
    tasks = response.json()["data"]
    task_data = next(t for t in tasks if t["id"] == task["id"])
    assert task_data["start_day"] == 3


async def test_backpropagate_noop_when_no_task_links(client):
    email = "cw-backprop-noop@example.com"
    await register_and_auth(client, email)
    user_id = await get_user_id(email)

    events = [await _make_normalized_event("google-no-link", "Some event")]

    async with AsyncSessionLocal() as session:
        await backpropagate_google_changes_to_tasks(session, "fake-connection-id", user_id, events)
