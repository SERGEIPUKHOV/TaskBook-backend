from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.calendar_connection import CalendarConnection
from app.models.calendar_event import CalendarEvent
from app.models.calendar_provider_account import CalendarProviderAccount
from app.models.habit import Habit
from app.models.planner_link import PlannerLink
from app.models.user import User
from app.services.calendar_ics_service import sync_all_apple_connections
from app.services.calendar_google_service import _google_get, store_google_tokens
from app.services.calendar_sync_service import NormalizedCalendarEvent, reconcile_connection_events
from tests.helpers import extract_data, register_and_auth

ICS_PAYLOAD = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//TaskBook//Calendar Test//EN
X-WR-CALNAME:Team Schedule
BEGIN:VEVENT
UID:event-1@example.com
DTSTAMP:20260405T080000Z
DTSTART:20260310T090000Z
DTEND:20260310T100000Z
SUMMARY:Design Review
DESCRIPTION:Discuss the new calendar flow
LOCATION:Studio
END:VEVENT
BEGIN:VEVENT
UID:event-2@example.com
DTSTAMP:20260405T080000Z
DTSTART;VALUE=DATE:20260312
DTEND;VALUE=DATE:20260313
SUMMARY:Offsite
END:VEVENT
END:VCALENDAR
"""

UPDATED_ICS_PAYLOAD = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//TaskBook//Calendar Test//EN
X-WR-CALNAME:Team Schedule
BEGIN:VEVENT
UID:event-2@example.com
DTSTAMP:20260405T080000Z
DTSTART;VALUE=DATE:20260312
DTEND;VALUE=DATE:20260313
SUMMARY:Offsite
END:VEVENT
END:VCALENDAR
"""


async def seed_google_provider_account(email: str) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        await store_google_tokens(
            session,
            user.id,
            {
                "access_token": "google-access-token",
                "expires_in": 3600,
                "refresh_token": "google-refresh-token",
            },
        )


async def seed_manual_calendar_event(
    email: str,
    *,
    title: str,
    external_event_id: str,
    raw_payload: dict | None = None,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    is_all_day: bool = False,
) -> str:
    async with AsyncSessionLocal() as session:
        user_result = await session.execute(select(User).where(User.email == email))
        user = user_result.scalar_one()

        connection = CalendarConnection(
            user_id=user.id,
            provider="google",
            status="active",
            external_account_id=f"seed-{external_event_id}",
            account_label="Seeded Calendar",
            color="#4285F4",
        )
        session.add(connection)
        await session.flush()

        event = CalendarEvent(
            connection_id=connection.id,
            user_id=user.id,
            external_event_id=external_event_id,
            external_calendar_id="primary",
            title=title,
            description=None,
            location=None,
            starts_at=starts_at or datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc),
            ends_at=ends_at or datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc),
            source_timezone="UTC",
            is_all_day=is_all_day,
            status="confirmed",
            raw_payload=raw_payload or {},
        )
        session.add(event)
        await session.commit()
        return event.id


async def test_calendar_apple_ics_connection_sync_range_and_delete(client, monkeypatch):
    headers, _ = await register_and_auth(client, "calendar-owner@example.com")
    guest_headers, _ = await register_and_auth(client, "calendar-guest@example.com")

    async def fake_fetch(url: str) -> str:
        assert url == "https://example.com/team.ics"
        return ICS_PAYLOAD

    monkeypatch.setattr("app.services.calendar_ics_service.fetch_ics_feed", fake_fetch)

    create_response = await client.post(
        "/api/v1/calendar/apple-ics/connections",
        json={"account_label": "Команда", "ics_url": "https://example.com/team.ics"},
        headers=headers,
    )
    assert create_response.status_code == 200
    connection = extract_data(create_response)
    assert connection["provider"] == "apple"
    assert connection["status"] == "active"
    assert connection["color"] is not None

    reconnect_response = await client.post(
        "/api/v1/calendar/apple-ics/connections",
        json={"account_label": "Команда 2", "ics_url": "https://example.com/team.ics"},
        headers=headers,
    )
    assert reconnect_response.status_code == 200
    assert extract_data(reconnect_response)["color"] == connection["color"]

    list_response = await client.get("/api/v1/calendar/connections", headers=headers)
    assert list_response.status_code == 200
    connections = extract_data(list_response)
    assert len(connections) == 1
    assert connections[0]["account_label"] == "Команда 2"
    assert connections[0]["color"] == connection["color"]

    events_response = await client.get(
        "/api/v1/calendar/events?date_from=2026-03-09&date_to=2026-03-15",
        headers=headers,
    )
    assert events_response.status_code == 200
    events = extract_data(events_response)["events"]
    assert [event["title"] for event in events] == ["Design Review", "Offsite"]
    assert events[0]["provider"] == "apple"
    assert events[1]["is_all_day"] is True

    async def fake_fetch_updated(_: str) -> str:
        return UPDATED_ICS_PAYLOAD

    monkeypatch.setattr("app.services.calendar_ics_service.fetch_ics_feed", fake_fetch_updated)

    sync_response = await client.post(f"/api/v1/calendar/connections/{connection['id']}/sync", headers=headers)
    assert sync_response.status_code == 200

    events_after_sync = await client.get(
        "/api/v1/calendar/events?date_from=2026-03-09&date_to=2026-03-15",
        headers=headers,
    )
    assert events_after_sync.status_code == 200
    remaining_events = extract_data(events_after_sync)["events"]
    assert [event["title"] for event in remaining_events] == ["Offsite"]

    blocked_delete = await client.delete(f"/api/v1/calendar/connections/{connection['id']}", headers=guest_headers)
    assert blocked_delete.status_code == 404

    delete_response = await client.delete(f"/api/v1/calendar/connections/{connection['id']}", headers=headers)
    assert delete_response.status_code == 204

    final_connections = await client.get("/api/v1/calendar/connections", headers=headers)
    assert extract_data(final_connections) == []


async def test_calendar_google_auth_session_builds_authorize_url(client, auth_headers):
    original_client_id = settings.GOOGLE_CALENDAR_CLIENT_ID
    original_client_secret = settings.GOOGLE_CALENDAR_CLIENT_SECRET
    original_redirect_uri = settings.GOOGLE_CALENDAR_REDIRECT_URI

    settings.GOOGLE_CALENDAR_CLIENT_ID = "google-client-id"
    settings.GOOGLE_CALENDAR_CLIENT_SECRET = "google-client-secret"
    settings.GOOGLE_CALENDAR_REDIRECT_URI = "http://localhost:8000/api/v1/calendar/google/callback"

    try:
        response = await client.post(
            "/api/v1/calendar/google/auth-session",
            json={"return_to": "http://localhost:3001/calendar"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        payload = extract_data(response)
        assert payload["state_expires_in"] == 600

        parsed = urlparse(payload["authorize_url"])
        query = parse_qs(parsed.query)
        assert parsed.netloc == "accounts.google.com"
        assert query["client_id"] == ["google-client-id"]
        assert query["redirect_uri"] == ["http://localhost:8000/api/v1/calendar/google/callback"]
        assert query["scope"] == ["https://www.googleapis.com/auth/calendar"]
        assert query["state"]
    finally:
        settings.GOOGLE_CALENDAR_CLIENT_ID = original_client_id
        settings.GOOGLE_CALENDAR_CLIENT_SECRET = original_client_secret
        settings.GOOGLE_CALENDAR_REDIRECT_URI = original_redirect_uri


async def test_calendar_google_multiselect_selection_sync_and_disconnect(client, monkeypatch):
    email = "calendar-google@example.com"
    headers, _ = await register_and_auth(client, email)
    await seed_google_provider_account(email)

    calendar_items = [
        {
            "accessRole": "owner",
            "backgroundColor": "#4285F4",
            "id": "primary",
            "primary": True,
            "summary": "puhov.kzn@gmail.com",
        },
        {
            "accessRole": "writer",
            "backgroundColor": "#33B679",
            "id": "team@group.calendar.google.com",
            "primary": False,
            "summary": "Команда",
        },
    ]
    synced_calendar_ids: list[str] = []

    async def fake_fetch_google_calendar_list(access_token: str):
        assert access_token == "google-access-token"
        return calendar_items

    async def fake_fetch_google_calendar_item(access_token: str, calendar_id: str):
        assert access_token == "google-access-token"
        return next(item for item in calendar_items if item["id"] == calendar_id)

    async def fake_fetch_google_events(access_token: str, calendar_id: str, sync_cursor: str | None):
        assert access_token == "google-access-token"
        synced_calendar_ids.append(calendar_id)
        if calendar_id == "primary":
            return (
                [
                    NormalizedCalendarEvent(
                        external_event_id="primary-event-1",
                        external_calendar_id=calendar_id,
                        title="Primary Planning",
                        description=None,
                        location=None,
                        starts_at=datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc),
                        ends_at=datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc),
                        source_timezone="UTC",
                        is_all_day=False,
                        status="confirmed",
                        raw_payload={"id": "primary-event-1"},
                    ),
                ],
                "sync-primary",
                sync_cursor is None,
            )

        return (
            [
                NormalizedCalendarEvent(
                    external_event_id="team-event-1",
                    external_calendar_id=calendar_id,
                    title="Team Sync",
                    description=None,
                    location=None,
                    starts_at=datetime(2026, 3, 11, 11, 0, tzinfo=timezone.utc),
                    ends_at=datetime(2026, 3, 11, 11, 30, tzinfo=timezone.utc),
                    source_timezone="UTC",
                    is_all_day=False,
                    status="confirmed",
                    raw_payload={"id": "team-event-1"},
                ),
            ],
            "sync-team",
            sync_cursor is None,
        )

    monkeypatch.setattr("app.services.calendar_google_service._fetch_google_calendar_list", fake_fetch_google_calendar_list)
    monkeypatch.setattr("app.services.calendar_google_service._fetch_google_calendar_item", fake_fetch_google_calendar_item)
    monkeypatch.setattr("app.services.calendar_google_service._fetch_google_events", fake_fetch_google_events)

    options_response = await client.get("/api/v1/calendar/google/calendars", headers=headers)
    assert options_response.status_code == 200
    options_payload = extract_data(options_response)
    assert options_payload["connected"] is True
    assert options_payload["provider_account_label"] == "puhov.kzn@gmail.com"
    assert [item["id"] for item in options_payload["options"]] == ["primary", "team@group.calendar.google.com"]
    assert all(item["selected"] is False for item in options_payload["options"])

    save_response = await client.put(
        "/api/v1/calendar/google/selections",
        json={"calendar_ids": ["primary", "team@group.calendar.google.com"]},
        headers=headers,
    )
    assert save_response.status_code == 200
    selected_connections = extract_data(save_response)
    assert {item["external_account_id"] for item in selected_connections} == {
        "primary",
        "team@group.calendar.google.com",
    }
    assert all(item["provider_account_label"] == "puhov.kzn@gmail.com" for item in selected_connections)
    assert {item["external_account_id"]: item["color"] for item in selected_connections} == {
        "primary": "#4285F4",
        "team@group.calendar.google.com": "#33B679",
    }

    team_connection = next(
        item for item in selected_connections if item["external_account_id"] == "team@group.calendar.google.com"
    )
    patch_response = await client.patch(
        f"/api/v1/calendar/connections/{team_connection['id']}/color",
        json={"color": "#8E24AA"},
        headers=headers,
    )
    assert patch_response.status_code == 200
    assert extract_data(patch_response)["color"] == "#8E24AA"

    preserved_response = await client.put(
        "/api/v1/calendar/google/selections",
        json={"calendar_ids": ["primary", "team@group.calendar.google.com"]},
        headers=headers,
    )
    assert preserved_response.status_code == 200
    preserved_connections = extract_data(preserved_response)
    assert {item["external_account_id"]: item["color"] for item in preserved_connections} == {
        "primary": "#4285F4",
        "team@group.calendar.google.com": "#8E24AA",
    }

    connections_response = await client.get("/api/v1/calendar/connections", headers=headers)
    assert connections_response.status_code == 200
    connections = extract_data(connections_response)
    assert len(connections) == 2
    assert {item["account_label"] for item in connections} == {"puhov.kzn@gmail.com", "Команда"}

    events_response = await client.get(
        "/api/v1/calendar/events?date_from=2026-03-09&date_to=2026-03-15",
        headers=headers,
    )
    assert events_response.status_code == 200
    events = extract_data(events_response)["events"]
    assert [event["title"] for event in events] == ["Primary Planning", "Team Sync"]

    synced_calendar_ids.clear()
    sync_all_response = await client.post("/api/v1/calendar/google/sync-all", headers=headers)
    assert sync_all_response.status_code == 200
    assert set(synced_calendar_ids) == {"primary", "team@group.calendar.google.com"}

    narrow_response = await client.put(
        "/api/v1/calendar/google/selections",
        json={"calendar_ids": ["team@group.calendar.google.com"]},
        headers=headers,
    )
    assert narrow_response.status_code == 200
    narrowed_connections = extract_data(narrow_response)
    assert [item["external_account_id"] for item in narrowed_connections] == ["team@group.calendar.google.com"]

    narrowed_list_response = await client.get("/api/v1/calendar/connections", headers=headers)
    assert narrowed_list_response.status_code == 200
    narrowed_list = extract_data(narrowed_list_response)
    assert [item["external_account_id"] for item in narrowed_list] == ["team@group.calendar.google.com"]

    delete_response = await client.delete("/api/v1/calendar/google/account", headers=headers)
    assert delete_response.status_code == 204

    final_connections = await client.get("/api/v1/calendar/connections", headers=headers)
    assert final_connections.status_code == 200
    assert extract_data(final_connections) == []

    final_options = await client.get("/api/v1/calendar/google/calendars", headers=headers)
    assert final_options.status_code == 200
    assert extract_data(final_options) == {
        "connected": False,
        "options": [],
        "provider_account_label": None,
    }


async def test_google_get_retries_transient_transport_errors(monkeypatch):
    attempts = 0

    async def fake_sleep(_seconds: float):
        return None

    async def fake_request(self, method: str, url: str, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ConnectError("dns temporary failure", request=httpx.Request(method, url))
        return httpx.Response(200, json={"items": []}, request=httpx.Request(method, url))

    monkeypatch.setattr("app.services.calendar_google_service.asyncio.sleep", fake_sleep)
    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    payload = await _google_get("google-access-token", "/users/me/calendarList")
    assert payload == {"items": []}
    assert attempts == 3


async def test_calendar_google_sync_all_surfaces_transient_network_error_without_500(client, monkeypatch):
    email = "calendar-google-network@example.com"
    headers, _ = await register_and_auth(client, email)
    await seed_google_provider_account(email)

    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        provider_account = (
            await session.execute(
                select(CalendarProviderAccount).where(
                    CalendarProviderAccount.user_id == user.id,
                    CalendarProviderAccount.provider == "google",
                )
            )
        ).scalar_one()
        connection = CalendarConnection(
            user_id=user.id,
            provider_account_id=provider_account.id,
            provider="google",
            status="active",
            external_account_id="primary",
            account_label="Primary",
        )
        session.add(connection)
        await session.commit()

    async def fake_sleep(_seconds: float):
        return None

    original_request = httpx.AsyncClient.request

    async def fake_request(self, method: str, url: str, **kwargs):
        if "googleapis.com" not in str(url) and "accounts.google.com" not in str(url):
            return await original_request(self, method, url, **kwargs)
        raise httpx.ConnectError("dns temporary failure", request=httpx.Request(method, url))

    monkeypatch.setattr("app.services.calendar_google_service.asyncio.sleep", fake_sleep)
    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    response = await client.post("/api/v1/calendar/google/sync-all", headers=headers)
    assert response.status_code == 200
    payload = extract_data(response)
    assert len(payload) == 1
    assert payload[0]["status"] == "error"
    assert "temporarily unavailable" in payload[0]["last_error"]
    assert "dns temporary failure" in payload[0]["last_error"]


async def test_sync_all_apple_connections_returns_empty_list_for_empty_db():
    async with AsyncSessionLocal() as session:
        assert await sync_all_apple_connections(session) == []


async def test_calendar_connection_color_patch_validates_and_scopes_to_owner(client, monkeypatch):
    headers, _ = await register_and_auth(client, "calendar-colors-owner@example.com")
    guest_headers, _ = await register_and_auth(client, "calendar-colors-guest@example.com")

    async def fake_fetch(_: str) -> str:
        return ICS_PAYLOAD

    monkeypatch.setattr("app.services.calendar_ics_service.fetch_ics_feed", fake_fetch)

    create_response = await client.post(
        "/api/v1/calendar/apple-ics/connections",
        json={"account_label": "Команда", "ics_url": "https://example.com/colors.ics"},
        headers=headers,
    )
    assert create_response.status_code == 200
    connection_id = extract_data(create_response)["id"]

    patch_response = await client.patch(
        f"/api/v1/calendar/connections/{connection_id}/color",
        json={"color": "#F4511E"},
        headers=headers,
    )
    assert patch_response.status_code == 200
    assert extract_data(patch_response)["color"] == "#F4511E"

    invalid_response = await client.patch(
        f"/api/v1/calendar/connections/{connection_id}/color",
        json={"color": "orange"},
        headers=headers,
    )
    assert invalid_response.status_code == 422

    forbidden_response = await client.patch(
        f"/api/v1/calendar/connections/{connection_id}/color",
        json={"color": "#0B8043"},
        headers=guest_headers,
    )
    assert forbidden_response.status_code == 404


async def test_calendar_event_import_creates_task_link_and_returns_existing_on_repeat(client, monkeypatch):
    headers, _ = await register_and_auth(client, "calendar-import-task@example.com")

    async def fake_fetch(url: str) -> str:
        assert url == "https://example.com/team.ics"
        return ICS_PAYLOAD

    monkeypatch.setattr("app.services.calendar_ics_service.fetch_ics_feed", fake_fetch)

    create_response = await client.post(
        "/api/v1/calendar/apple-ics/connections",
        json={"account_label": "Команда", "ics_url": "https://example.com/team.ics"},
        headers=headers,
    )
    assert create_response.status_code == 200

    events_response = await client.get(
        "/api/v1/calendar/events?date_from=2026-03-09&date_to=2026-03-15",
        headers=headers,
    )
    assert events_response.status_code == 200
    design_review = next(
        event for event in extract_data(events_response)["events"] if event["title"] == "Design Review"
    )
    assert design_review["suggested_target_type"] == "task"
    assert design_review["planner_link"] is None

    import_response = await client.post(
        f"/api/v1/calendar/events/{design_review['id']}/import",
        json={
            "target_type": "task",
            "title": "Design Review",
            "year": 2026,
            "week": 11,
            "start_day": 2,
            "time_planned": 2,
            "is_priority": True,
        },
        headers=headers,
    )
    assert import_response.status_code == 200
    import_payload = extract_data(import_response)
    assert import_payload["status"] == "created"
    assert import_payload["planner_link"]["target_kind"] == "task"
    assert import_payload["planner_link"]["open_path"] == "/week/2026/11"

    repeated_import = await client.post(
        f"/api/v1/calendar/events/{design_review['id']}/import",
        json={
            "target_type": "task",
            "title": "Design Review",
            "year": 2026,
            "week": 11,
            "start_day": 2,
            "time_planned": 2,
            "is_priority": True,
        },
        headers=headers,
    )
    assert repeated_import.status_code == 200
    assert extract_data(repeated_import)["status"] == "existing"

    events_after_import = await client.get(
        "/api/v1/calendar/events?date_from=2026-03-09&date_to=2026-03-15",
        headers=headers,
    )
    imported_event = next(
        event for event in extract_data(events_after_import)["events"] if event["id"] == design_review["id"]
    )
    assert imported_event["planner_link"] == {
        "id": import_payload["planner_link"]["id"],
        "link_mode": "import_copy",
        "open_path": "/week/2026/11",
        "target_id": import_payload["planner_link"]["target_id"],
        "target_kind": "task",
    }


async def test_calendar_event_import_suggests_habit_for_recurring_event_and_imports_habit(client):
    email = "calendar-import-habit@example.com"
    headers, _ = await register_and_auth(client, email)
    event_id = await seed_manual_calendar_event(
        email,
        title="Weekly Piano",
        external_event_id="recurring-1",
        raw_payload={"recurringEventId": "series-1"},
        starts_at=datetime(2026, 3, 12, 18, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 3, 12, 19, 0, tzinfo=timezone.utc),
    )

    events_response = await client.get(
        "/api/v1/calendar/events?date_from=2026-03-09&date_to=2026-03-15",
        headers=headers,
    )
    assert events_response.status_code == 200
    recurring_event = next(event for event in extract_data(events_response)["events"] if event["id"] == event_id)
    assert recurring_event["suggested_target_type"] == "habit"
    assert recurring_event["planner_link"] is None

    import_response = await client.post(
        f"/api/v1/calendar/events/{event_id}/import",
        json={
            "target_type": "habit",
            "title": "Weekly Piano",
            "year": 2026,
            "month": 3,
        },
        headers=headers,
    )
    assert import_response.status_code == 200
    payload = extract_data(import_response)
    assert payload["status"] == "created"
    assert payload["planner_link"]["target_kind"] == "habit"
    assert payload["planner_link"]["open_path"] == "/month/2026/3"

    events_after_import = await client.get(
        "/api/v1/calendar/events?date_from=2026-03-09&date_to=2026-03-15",
        headers=headers,
    )
    imported_event = next(event for event in extract_data(events_after_import)["events"] if event["id"] == event_id)
    assert imported_event["planner_link"]["target_kind"] == "habit"
    assert imported_event["planner_link"]["open_path"] == "/month/2026/3"


async def test_calendar_events_mark_future_instances_of_linked_recurring_series(client):
    email = "calendar-linked-series@example.com"
    headers, _ = await register_and_auth(client, email)
    first_event_id = await seed_manual_calendar_event(
        email,
        title="Weekly Piano",
        external_event_id="recurring-series-1",
        raw_payload={"recurringEventId": "series-linked-1"},
        starts_at=datetime(2026, 3, 12, 18, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 3, 12, 19, 0, tzinfo=timezone.utc),
    )
    future_event_id = await seed_manual_calendar_event(
        email,
        title="Weekly Piano",
        external_event_id="recurring-series-2",
        raw_payload={"recurringEventId": "series-linked-1"},
        starts_at=datetime(2026, 3, 19, 18, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 3, 19, 19, 0, tzinfo=timezone.utc),
    )
    one_off_event_id = await seed_manual_calendar_event(
        email,
        title="One-off Review",
        external_event_id="single-series-1",
        starts_at=datetime(2026, 3, 19, 9, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 3, 19, 10, 0, tzinfo=timezone.utc),
    )

    import_response = await client.post(
        f"/api/v1/calendar/events/{first_event_id}/import",
        json={
            "target_type": "habit",
            "title": "Weekly Piano",
            "year": 2026,
            "month": 3,
        },
        headers=headers,
    )
    assert import_response.status_code == 200

    next_week_events_response = await client.get(
        "/api/v1/calendar/events?date_from=2026-03-16&date_to=2026-03-22",
        headers=headers,
    )
    assert next_week_events_response.status_code == 200
    events = extract_data(next_week_events_response)["events"]

    future_event = next(event for event in events if event["id"] == future_event_id)
    one_off_event = next(event for event in events if event["id"] == one_off_event_id)

    assert future_event["planner_link"] is None
    assert future_event["series_linked"] is True
    assert one_off_event["series_linked"] is False


async def test_google_recurring_time_shift_rebinds_habit_link_to_new_instance(client):
    email = "calendar-linked-series-time-shift@example.com"
    headers, _ = await register_and_auth(client, email)
    original_event_id = await seed_manual_calendar_event(
        email,
        title="Баня",
        external_event_id="habit-series-old-instance",
        raw_payload={"recurringEventId": "habit-series-master-1"},
        starts_at=datetime(2026, 4, 18, 6, 30, tzinfo=timezone.utc),
        ends_at=datetime(2026, 4, 18, 8, 0, tzinfo=timezone.utc),
    )

    import_response = await client.post(
        f"/api/v1/calendar/events/{original_event_id}/import",
        json={
            "target_type": "habit",
            "title": "Баня",
            "year": 2026,
            "month": 4,
        },
        headers=headers,
    )
    assert import_response.status_code == 200
    imported_link = extract_data(import_response)["planner_link"]

    async with AsyncSessionLocal() as session:
        event_result = await session.execute(select(CalendarEvent).where(CalendarEvent.id == original_event_id))
        original_event = event_result.scalar_one()
        connection_result = await session.execute(
            select(CalendarConnection).where(CalendarConnection.id == original_event.connection_id)
        )
        connection = connection_result.scalar_one()

        await reconcile_connection_events(
            session,
            connection,
            [
                NormalizedCalendarEvent(
                    external_event_id="habit-series-new-instance",
                    external_calendar_id="primary",
                    title="Баня",
                    description=None,
                    location=None,
                    starts_at=datetime(2026, 4, 18, 7, 30, tzinfo=timezone.utc),
                    ends_at=datetime(2026, 4, 18, 9, 0, tzinfo=timezone.utc),
                    source_timezone="Europe/Moscow",
                    is_all_day=False,
                    status="confirmed",
                    raw_payload={
                        "id": "habit-series-new-instance",
                        "recurringEventId": "habit-series-master-1",
                    },
                )
            ],
            full_sync=True,
            sync_cursor="sync-shift-1",
        )

    events_response = await client.get(
        "/api/v1/calendar/events?date_from=2026-04-13&date_to=2026-04-19",
        headers=headers,
    )
    assert events_response.status_code == 200
    events = extract_data(events_response)["events"]
    shifted_event = next(event for event in events if event["external_event_id"] == "habit-series-new-instance")
    assert shifted_event["planner_link"] == imported_link

    habits_response = await client.get("/api/v1/months/2026/4/habits", headers=headers)
    assert habits_response.status_code == 200
    habit = next(item for item in extract_data(habits_response) if item["id"] == imported_link["target_id"])
    assert habit["linked_event_time"] == {
        "starts_at": "2026-04-18T07:30:00+00:00",
        "ends_at": "2026-04-18T09:00:00+00:00",
    }

    async with AsyncSessionLocal() as session:
        link_result = await session.execute(
            select(PlannerLink).where(
                PlannerLink.target_kind == "habit",
                PlannerLink.target_id == imported_link["target_id"],
                PlannerLink.source_kind == "calendar_event",
                PlannerLink.link_mode == "import_copy",
            )
        )
        re_bound_link = link_result.scalar_one()
        assert re_bound_link.source_ref.endswith(":habit-series-new-instance")


async def test_calendar_event_unlocks_after_imported_task_is_deleted(client):
    email = "calendar-deleted-task@example.com"
    headers, _ = await register_and_auth(client, email)
    event_id = await seed_manual_calendar_event(
        email,
        title="Design Review",
        external_event_id="task-delete-1",
        starts_at=datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 3, 10, 10, 0, tzinfo=timezone.utc),
    )

    import_response = await client.post(
        f"/api/v1/calendar/events/{event_id}/import",
        json={
            "target_type": "task",
            "title": "Design Review",
            "year": 2026,
            "week": 11,
            "start_day": 2,
            "time_planned": 2,
            "is_priority": False,
        },
        headers=headers,
    )
    assert import_response.status_code == 200
    task_id = extract_data(import_response)["planner_link"]["target_id"]

    delete_response = await client.delete(f"/api/v1/tasks/{task_id}", headers=headers)
    assert delete_response.status_code == 204

    events_response = await client.get(
        "/api/v1/calendar/events?date_from=2026-03-09&date_to=2026-03-15",
        headers=headers,
    )
    assert events_response.status_code == 200
    event = next(item for item in extract_data(events_response)["events"] if item["id"] == event_id)
    assert event["planner_link"] is None
    assert event["series_linked"] is False


async def test_calendar_recurring_series_unlocks_after_imported_habit_is_deleted(client):
    email = "calendar-deleted-habit@example.com"
    headers, _ = await register_and_auth(client, email)
    first_event_id = await seed_manual_calendar_event(
        email,
        title="Weekly Piano",
        external_event_id="habit-delete-1",
        raw_payload={"recurringEventId": "series-delete-1"},
        starts_at=datetime(2026, 3, 12, 18, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 3, 12, 19, 0, tzinfo=timezone.utc),
    )
    future_event_id = await seed_manual_calendar_event(
        email,
        title="Weekly Piano",
        external_event_id="habit-delete-2",
        raw_payload={"recurringEventId": "series-delete-1"},
        starts_at=datetime(2026, 3, 19, 18, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 3, 19, 19, 0, tzinfo=timezone.utc),
    )

    import_response = await client.post(
        f"/api/v1/calendar/events/{first_event_id}/import",
        json={
            "target_type": "habit",
            "title": "Weekly Piano",
            "year": 2026,
            "month": 3,
        },
        headers=headers,
    )
    assert import_response.status_code == 200
    habit_id = extract_data(import_response)["planner_link"]["target_id"]

    delete_response = await client.delete(f"/api/v1/habits/{habit_id}?year=2026&month=3", headers=headers)
    assert delete_response.status_code == 204

    events_response = await client.get(
        "/api/v1/calendar/events?date_from=2026-03-16&date_to=2026-03-22",
        headers=headers,
    )
    assert events_response.status_code == 200
    future_event = next(item for item in extract_data(events_response)["events"] if item["id"] == future_event_id)
    assert future_event["planner_link"] is None
    assert future_event["series_linked"] is False


async def test_calendar_ignores_stale_habit_links_for_inactive_months(client):
    email = "calendar-stale-habit-link@example.com"
    headers, _ = await register_and_auth(client, email)
    event_id = await seed_manual_calendar_event(
        email,
        title="Тренировка",
        external_event_id="stale-habit-1",
        raw_payload={"recurringEventId": "series-stale-1"},
        starts_at=datetime(2026, 4, 15, 11, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 4, 15, 13, 30, tzinfo=timezone.utc),
    )

    async with AsyncSessionLocal() as session:
        user_result = await session.execute(select(User).where(User.email == email))
        user = user_result.scalar_one()
        event_result = await session.execute(select(CalendarEvent).where(CalendarEvent.id == event_id))
        event = event_result.scalar_one()

        habit = Habit(
            user_id=user.id,
            name="Тренировка",
            order=1,
            source="user",
            starts_at_month_key="2026-03",
            ends_before_month_key="2026-04",
        )
        session.add(habit)
        await session.flush()

        session.add(
            PlannerLink(
                user_id=user.id,
                source_kind="calendar_event",
                source_ref=f"{event.connection_id}:{event.external_event_id}",
                target_kind="habit",
                target_id=habit.id,
                link_mode="import_copy",
            ),
        )
        await session.commit()

    events_response = await client.get(
        "/api/v1/calendar/events?date_from=2026-04-13&date_to=2026-04-19",
        headers=headers,
    )
    assert events_response.status_code == 200
    event = next(item for item in extract_data(events_response)["events"] if item["id"] == event_id)
    assert event["planner_link"] is None
    assert event["series_linked"] is False


async def test_import_habit_name_conflict_with_calendar_source(client):
    email = "calendar-import-habit-conflict-source@example.com"
    headers, _ = await register_and_auth(client, email)
    first_event_id = await seed_manual_calendar_event(
        email,
        title="Weekly Piano",
        external_event_id="recurring-conflict-1",
        raw_payload={"recurringEventId": "series-conflict-1"},
        starts_at=datetime(2026, 3, 12, 18, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 3, 12, 19, 0, tzinfo=timezone.utc),
    )
    second_event_id = await seed_manual_calendar_event(
        email,
        title="  weekly piano  ",
        external_event_id="recurring-conflict-2",
        raw_payload={"recurringEventId": "series-conflict-2"},
        starts_at=datetime(2026, 3, 19, 18, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 3, 19, 19, 0, tzinfo=timezone.utc),
    )

    first_import = await client.post(
        f"/api/v1/calendar/events/{first_event_id}/import",
        json={
            "target_type": "habit",
            "title": "Weekly Piano",
            "year": 2026,
            "month": 3,
        },
        headers=headers,
    )
    assert first_import.status_code == 200
    first_payload = extract_data(first_import)
    assert first_payload["status"] == "created"

    second_import = await client.post(
        f"/api/v1/calendar/events/{second_event_id}/import",
        json={
            "target_type": "habit",
            "title": "  weekly piano  ",
            "year": 2026,
            "month": 3,
        },
        headers=headers,
    )
    assert second_import.status_code == 200
    second_payload = extract_data(second_import)
    assert second_payload["status"] == "existing"
    assert second_payload["planner_link"]["target_kind"] == "habit"
    assert second_payload["planner_link"]["target_id"] == first_payload["planner_link"]["target_id"]
    assert second_payload["planner_link"]["open_path"] == "/month/2026/3"


async def test_import_habit_name_conflict_manual(client):
    email = "calendar-import-habit-conflict-manual@example.com"
    headers, _ = await register_and_auth(client, email)
    event_id = await seed_manual_calendar_event(
        email,
        title="Weekly Piano",
        external_event_id="recurring-conflict-manual",
        raw_payload={"recurringEventId": "series-conflict-manual"},
        starts_at=datetime(2026, 3, 12, 18, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 3, 12, 19, 0, tzinfo=timezone.utc),
    )

    create_habit_response = await client.post(
        "/api/v1/months/2026/3/habits",
        json={"name": "Weekly Piano"},
        headers=headers,
    )
    assert create_habit_response.status_code == 201

    import_response = await client.post(
        f"/api/v1/calendar/events/{event_id}/import",
        json={
            "target_type": "habit",
            "title": "Weekly Piano",
            "year": 2026,
            "month": 3,
        },
        headers=headers,
    )
    assert import_response.status_code == 409
    assert import_response.json()["detail"] == (
        "Привычка «Weekly Piano» уже существует. Измените название и создайте снова или отмените."
    )


async def test_calendar_task_feed_links_and_public_ics_export(client):
    headers, _ = await register_and_auth(client, "calendar-task-feed@example.com")

    work_task_response = await client.post(
        "/api/v1/weeks/2026/11/tasks",
        json={"title": "Client workshop", "time_planned": 120, "start_day": 2},
        headers=headers,
    )
    assert work_task_response.status_code == 201
    work_task = extract_data(work_task_response)

    default_task_response = await client.post(
        "/api/v1/weeks/2026/11/tasks",
        json={"title": "Plan week review", "time_planned": 45, "start_day": 5},
        headers=headers,
    )
    assert default_task_response.status_code == 201
    default_task = extract_data(default_task_response)

    hidden_task_response = await client.post(
        "/api/v1/weeks/2026/11/tasks",
        json={"title": "Keep private", "time_planned": 15, "start_day": 3},
        headers=headers,
    )
    assert hidden_task_response.status_code == 201
    hidden_task = extract_data(hidden_task_response)

    patch_work_task = await client.patch(
        f"/api/v1/tasks/{work_task['id']}",
        json={"calendar_export_enabled": True, "calendar_export_bucket": "work"},
        headers=headers,
    )
    assert patch_work_task.status_code == 200

    patch_default_task = await client.patch(
        f"/api/v1/tasks/{default_task['id']}",
        json={"calendar_export_enabled": True, "calendar_export_bucket": "default"},
        headers=headers,
    )
    assert patch_default_task.status_code == 200

    patch_hidden_task = await client.patch(
        f"/api/v1/tasks/{hidden_task['id']}",
        json={"calendar_export_enabled": False, "calendar_export_bucket": "personal"},
        headers=headers,
    )
    assert patch_hidden_task.status_code == 200

    links_response = await client.get("/api/v1/calendar/feeds/tasks/links", headers=headers)
    assert links_response.status_code == 200
    links = {item["bucket"]: item for item in extract_data(links_response)}
    assert set(links) == {"default", "work", "personal", "family"}
    assert links["default"]["task_count"] == 1
    assert links["work"]["task_count"] == 1
    assert links["personal"]["task_count"] == 0
    assert links["family"]["task_count"] == 0
    assert links["work"]["feed_path"].startswith("/api/v1/calendar/feeds/tasks/")

    work_feed_response = await client.get(links["work"]["feed_path"])
    assert work_feed_response.status_code == 200
    assert work_feed_response.headers["content-type"].startswith("text/calendar")
    assert "SUMMARY:Client workshop" in work_feed_response.text
    assert "SUMMARY:Plan week review" not in work_feed_response.text
    assert "SUMMARY:Keep private" not in work_feed_response.text
    assert "DTSTART;VALUE=DATE:20260310" in work_feed_response.text

    default_feed_response = await client.get(links["default"]["feed_path"])
    assert default_feed_response.status_code == 200
    assert "SUMMARY:Plan week review" in default_feed_response.text
    assert "SUMMARY:Client workshop" not in default_feed_response.text
    assert "DTSTART;VALUE=DATE:20260313" in default_feed_response.text


async def test_calendar_sync_worker_counts_google_and_apple_connections(monkeypatch):
    async def fake_sync_all_google_connections(_session):
        return [object(), object()]

    async def fake_sync_all_apple_connections(_session):
        return [object()]

    monkeypatch.setattr("app.workers.calendar_sync_worker.sync_all_google_connections", fake_sync_all_google_connections)
    monkeypatch.setattr("app.workers.calendar_sync_worker.sync_all_apple_connections", fake_sync_all_apple_connections)

    from app.workers.calendar_sync_worker import run_sync_cycle

    assert await run_sync_cycle() == 3
