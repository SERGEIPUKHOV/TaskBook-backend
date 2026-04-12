from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.calendar_connection import CalendarConnection
from app.models.calendar_event import CalendarEvent
from app.models.calendar_provider_account import CalendarProviderAccount
from app.models.planner_link import PlannerLink
from app.models.user import User
from app.services.calendar_write_service import push_habit_title_to_google, push_task_title_to_google
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
            source_timezone="UTC",
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
