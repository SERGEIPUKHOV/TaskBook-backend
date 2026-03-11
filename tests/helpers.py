from __future__ import annotations


def extract_data(response):
    payload = response.json()
    return payload["data"]


async def register_and_auth(
    client,
    email: str,
    password: str = "password123",
) -> tuple[dict[str, str], dict]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    payload = extract_data(response)
    return {"Authorization": f"Bearer {payload['access_token']}"}, payload
