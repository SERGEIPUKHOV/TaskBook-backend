from __future__ import annotations

from tests.helpers import extract_data, register_and_auth


async def test_days_events_and_gratitudes_support_crud_ownership_and_bundle_reflection(client):
    owner_headers, _ = await register_and_auth(client, "days-owner@example.com")
    guest_headers, _ = await register_and_auth(client, "days-guest@example.com")

    event_response = await client.post(
        "/api/v1/days/2026-03-10/events",
        json={"content": "Первый релиз"},
        headers=owner_headers,
    )
    assert event_response.status_code == 201
    event = extract_data(event_response)

    gratitude_response = await client.post(
        "/api/v1/days/2026-03-10/gratitudes",
        json={"content": "Спасибо команде"},
        headers=owner_headers,
    )
    assert gratitude_response.status_code == 201
    gratitude = extract_data(gratitude_response)

    list_events_response = await client.get("/api/v1/days/2026-03-10/events", headers=owner_headers)
    assert list_events_response.status_code == 200
    assert [item["id"] for item in extract_data(list_events_response)] == [event["id"]]

    list_gratitudes_response = await client.get("/api/v1/days/2026-03-10/gratitudes", headers=owner_headers)
    assert list_gratitudes_response.status_code == 200
    assert [item["id"] for item in extract_data(list_gratitudes_response)] == [gratitude["id"]]

    patch_event_response = await client.patch(
        f"/api/v1/days/events/{event['id']}",
        json={"content": "Обновлённый релиз"},
        headers=owner_headers,
    )
    assert patch_event_response.status_code == 200
    assert extract_data(patch_event_response)["content"] == "Обновлённый релиз"

    patch_gratitude_response = await client.patch(
        f"/api/v1/days/gratitudes/{gratitude['id']}",
        json={"content": "Спасибо всей команде"},
        headers=owner_headers,
    )
    assert patch_gratitude_response.status_code == 200
    assert extract_data(patch_gratitude_response)["content"] == "Спасибо всей команде"

    week_bundle_response = await client.get("/api/v1/weeks/2026/11/bundle", headers=owner_headers)
    assert week_bundle_response.status_code == 200
    week_bundle = extract_data(week_bundle_response)
    assert week_bundle["key_events"]["2026-03-10"]["content"] == "Обновлённый релиз"
    assert week_bundle["gratitudes"]["2026-03-10"]["content"] == "Спасибо всей команде"

    day_bundle_response = await client.get("/api/v1/days/2026/3/10/bundle", headers=owner_headers)
    assert day_bundle_response.status_code == 200
    day_bundle = extract_data(day_bundle_response)
    assert day_bundle["key_event"] == "Обновлённый релиз"
    assert day_bundle["gratitude"] == "Спасибо всей команде"

    blocked_event_patch_response = await client.patch(
        f"/api/v1/days/events/{event['id']}",
        json={"content": "Чужой апдейт"},
        headers=guest_headers,
    )
    assert blocked_event_patch_response.status_code == 404

    blocked_gratitude_delete_response = await client.delete(
        f"/api/v1/days/gratitudes/{gratitude['id']}",
        headers=guest_headers,
    )
    assert blocked_gratitude_delete_response.status_code == 404

    delete_event_response = await client.delete(f"/api/v1/days/events/{event['id']}", headers=owner_headers)
    assert delete_event_response.status_code == 204
    assert delete_event_response.content == b""

    delete_gratitude_response = await client.delete(
        f"/api/v1/days/gratitudes/{gratitude['id']}",
        headers=owner_headers,
    )
    assert delete_gratitude_response.status_code == 204
    assert delete_gratitude_response.content == b""

    events_after_delete_response = await client.get("/api/v1/days/2026-03-10/events", headers=owner_headers)
    assert events_after_delete_response.status_code == 200
    assert extract_data(events_after_delete_response) == []

    gratitudes_after_delete_response = await client.get(
        "/api/v1/days/2026-03-10/gratitudes",
        headers=owner_headers,
    )
    assert gratitudes_after_delete_response.status_code == 200
    assert extract_data(gratitudes_after_delete_response) == []

    week_bundle_after_delete_response = await client.get("/api/v1/weeks/2026/11/bundle", headers=owner_headers)
    assert week_bundle_after_delete_response.status_code == 200
    week_bundle_after_delete = extract_data(week_bundle_after_delete_response)
    assert week_bundle_after_delete["key_events"]["2026-03-10"] is None
    assert week_bundle_after_delete["gratitudes"]["2026-03-10"] is None

    day_bundle_after_delete_response = await client.get("/api/v1/days/2026/3/10/bundle", headers=owner_headers)
    assert day_bundle_after_delete_response.status_code == 200
    day_bundle_after_delete = extract_data(day_bundle_after_delete_response)
    assert day_bundle_after_delete["key_event"] is None
    assert day_bundle_after_delete["gratitude"] is None
