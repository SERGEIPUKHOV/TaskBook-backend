from __future__ import annotations

from tests.helpers import extract_data, register_and_auth


async def test_supervision_pending_grant_activates_after_supervisor_registers(client):
    owner_headers, _ = await register_and_auth(client, "owner@example.com")

    create_response = await client.post(
        "/api/v1/supervision/grants",
        json={"supervisor_email": "supervisor@example.com", "sections": ["month", "calendar"]},
        headers=owner_headers,
    )
    assert create_response.status_code == 200
    grant = extract_data(create_response)
    assert grant["status"] == "pending"
    assert grant["supervisor_id"] is None

    supervisor_headers, _ = await register_and_auth(client, "supervisor@example.com")

    owners_response = await client.get("/api/v1/supervision/owners", headers=supervisor_headers)
    assert owners_response.status_code == 200
    owners = extract_data(owners_response)
    assert len(owners) == 1
    assert owners[0]["owner_email"] == "owner@example.com"
    assert owners[0]["owner_id"]
    assert owners[0]["sections"] == ["month", "calendar"]

    grants_response = await client.get("/api/v1/supervision/grants", headers=owner_headers)
    assert grants_response.status_code == 200
    grants = extract_data(grants_response)
    assert grants[0]["status"] == "active"
    assert grants[0]["supervisor_id"] is not None


async def test_supervision_view_as_allows_only_granted_reads(client):
    owner_headers, owner_payload = await register_and_auth(client, "owner2@example.com")
    supervisor_headers, _ = await register_and_auth(client, "supervisor2@example.com")

    create_response = await client.post(
        "/api/v1/supervision/grants",
        json={"supervisor_email": "supervisor2@example.com", "sections": ["month"]},
        headers=owner_headers,
    )
    assert create_response.status_code == 200

    view_headers = {
        **supervisor_headers,
        "X-View-As": owner_payload["user"]["id"],
    }

    allowed_response = await client.get("/api/v1/months/2026/4/plan", headers=view_headers)
    assert allowed_response.status_code == 200

    denied_response = await client.get("/api/v1/dashboard", headers=view_headers)
    assert denied_response.status_code == 403

    blocked_mutation = await client.post(
        "/api/v1/months/2026/4/plan",
        json={"main_goal": "test"},
        headers=view_headers,
    )
    assert blocked_mutation.status_code == 403

    # /api/v1/users/me is intentionally allowed in view-as mode so the supervisor's
    # own profile loads (supervision-viewas-bar fix, v9.54.35)
    allowed_profile = await client.get("/api/v1/users/me", headers=view_headers)
    assert allowed_profile.status_code == 200


async def test_supervision_rejects_self_grant(client):
    owner_headers, _ = await register_and_auth(client, "self-owner@example.com")

    response = await client.post(
        "/api/v1/supervision/grants",
        json={"supervisor_email": "self-owner@example.com", "sections": ["week"]},
        headers=owner_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Нельзя добавить себя как супервайзера"
