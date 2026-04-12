from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode, urlparse

from app.core.config import settings
from app.core.redis import redis_client

GOOGLE_OAUTH_STATE_TTL_SECONDS = 600
GOOGLE_OAUTH_SCOPE = "https://www.googleapis.com/auth/calendar"
GOOGLE_STATE_KEY = "calendar:google:state:{state}"


@dataclass(slots=True)
class GoogleOAuthState:
    user_id: str
    return_to: str


class CalendarOAuthError(RuntimeError):
    pass


def _default_return_to() -> str:
    base_url = settings.cors_origins_list[0] if settings.cors_origins_list else "http://localhost:3000"
    return f"{base_url.rstrip('/')}/calendar"


def normalize_return_to(return_to: str | None) -> str:
    if not return_to:
        return _default_return_to()

    parsed = urlparse(return_to)
    if not parsed.scheme and return_to.startswith("/"):
        return f"{(settings.cors_origins_list[0] if settings.cors_origins_list else 'http://localhost:3000').rstrip('/')}{return_to}"

    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin in settings.cors_origins_list:
        return return_to

    return _default_return_to()


def ensure_google_oauth_configured() -> None:
    if not settings.GOOGLE_CALENDAR_CLIENT_ID or not settings.GOOGLE_CALENDAR_CLIENT_SECRET:
        raise CalendarOAuthError("Google Calendar OAuth не настроен")

    if not settings.GOOGLE_CALENDAR_REDIRECT_URI:
        raise CalendarOAuthError("Отсутствует GOOGLE_CALENDAR_REDIRECT_URI")


async def create_google_auth_session(user_id: str, return_to: str | None) -> tuple[str, int]:
    ensure_google_oauth_configured()

    normalized_return_to = normalize_return_to(return_to)
    state = secrets.token_urlsafe(32)
    await redis_client.set(
        GOOGLE_STATE_KEY.format(state=state),
        json.dumps({"return_to": normalized_return_to, "user_id": user_id}),
        ex=GOOGLE_OAUTH_STATE_TTL_SECONDS,
    )

    params = urlencode(
        {
            "access_type": "offline",
            "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
            "include_granted_scopes": "true",
            "prompt": "consent",
            "redirect_uri": settings.GOOGLE_CALENDAR_REDIRECT_URI,
            "response_type": "code",
            "scope": GOOGLE_OAUTH_SCOPE,
            "state": state,
        },
    )
    return f"https://accounts.google.com/o/oauth2/v2/auth?{params}", GOOGLE_OAUTH_STATE_TTL_SECONDS


async def consume_google_auth_state(state: str) -> GoogleOAuthState:
    raw_payload = await redis_client.get(GOOGLE_STATE_KEY.format(state=state))
    await redis_client.delete(GOOGLE_STATE_KEY.format(state=state))

    if not raw_payload:
        raise CalendarOAuthError("Google OAuth state устарел или не найден")

    payload = json.loads(raw_payload)
    return GoogleOAuthState(
        user_id=str(payload["user_id"]),
        return_to=normalize_return_to(payload.get("return_to")),
    )
