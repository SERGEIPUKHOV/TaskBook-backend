from __future__ import annotations

from fastapi import Response

from app.core.config import settings


def _cookie_options(max_age: int | None = None, *, httponly: bool = True) -> dict[str, object]:
    options: dict[str, object] = {
        "httponly": httponly,
        "path": "/",
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "secure": settings.AUTH_COOKIE_SECURE or settings.is_production,
    }
    if max_age is not None:
        options["max_age"] = max_age
    if settings.AUTH_COOKIE_DOMAIN:
        options["domain"] = settings.AUTH_COOKIE_DOMAIN
    return options


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        settings.ACCESS_COOKIE_NAME,
        access_token,
        **_cookie_options(max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60),
    )
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh_token,
        **_cookie_options(max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400),
    )
    response.set_cookie(
        settings.SESSION_COOKIE_NAME,
        "1",
        **_cookie_options(max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, httponly=False),
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(settings.ACCESS_COOKIE_NAME, **_cookie_options())
    response.delete_cookie(settings.REFRESH_COOKIE_NAME, **_cookie_options())
    response.delete_cookie(settings.SESSION_COOKIE_NAME, **_cookie_options(httponly=False))
