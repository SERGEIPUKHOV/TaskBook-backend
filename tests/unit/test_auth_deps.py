from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from freezegun import freeze_time
from jose import jwt

from app.api.v1.auth.deps import get_current_user, get_optional_user
from app.core.config import settings
from app.core.security import ALGORITHM, create_access_token


def make_db_with_user(user):
    result = Mock()
    result.scalar_one_or_none.return_value = user
    db = AsyncMock()
    db.execute.return_value = result
    return db


@pytest.mark.unit
class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_returns_user_for_valid_cookie_token(self):
        token = create_access_token("user-1")
        request = SimpleNamespace(cookies={settings.ACCESS_COOKIE_NAME: token})
        user = SimpleNamespace(id="user-1", is_active=True)
        db = make_db_with_user(user)

        resolved = await get_current_user(request=request, credentials=None, db=db)

        assert resolved is user

    @pytest.mark.asyncio
    async def test_prefers_bearer_credentials_over_cookie(self):
        bearer_token = create_access_token("user-2")
        request = SimpleNamespace(cookies={settings.ACCESS_COOKIE_NAME: "cookie-token"})
        credentials = SimpleNamespace(credentials=bearer_token)
        user = SimpleNamespace(id="user-2", is_active=True)
        db = make_db_with_user(user)

        resolved = await get_current_user(request=request, credentials=credentials, db=db)

        assert resolved is user

    @pytest.mark.asyncio
    async def test_raises_401_for_expired_token(self):
        with freeze_time("2026-01-01 10:00:00"):
            token = create_access_token("user-1")

        request = SimpleNamespace(cookies={settings.ACCESS_COOKIE_NAME: token})
        db = make_db_with_user(SimpleNamespace(id="user-1", is_active=True))

        with freeze_time("2026-01-01 10:31:00"):
            with pytest.raises(Exception) as exc_info:
                await get_current_user(request=request, credentials=None, db=db)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_raises_401_for_tampered_token(self):
        token = create_access_token("user-1")
        header, payload, signature = token.split(".")
        broken_payload = f"{'A' if payload[0] != 'A' else 'B'}{payload[1:]}"
        tampered = ".".join([header, broken_payload, signature])
        request = SimpleNamespace(cookies={settings.ACCESS_COOKIE_NAME: tampered})
        db = make_db_with_user(SimpleNamespace(id="user-1", is_active=True))

        with pytest.raises(Exception) as exc_info:
            await get_current_user(request=request, credentials=None, db=db)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_raises_401_if_user_is_missing(self):
        token = create_access_token("user-404")
        request = SimpleNamespace(cookies={settings.ACCESS_COOKIE_NAME: token})
        db = make_db_with_user(None)

        with pytest.raises(Exception) as exc_info:
            await get_current_user(request=request, credentials=None, db=db)

        assert exc_info.value.status_code == 401


@pytest.mark.unit
class TestGetOptionalUser:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_token_is_provided(self):
        request = SimpleNamespace(cookies={})
        db = make_db_with_user(None)

        resolved = await get_optional_user(request=request, credentials=None, db=db)

        assert resolved is None

    @pytest.mark.asyncio
    async def test_returns_user_when_cookie_token_is_valid(self):
        token = create_access_token("user-3")
        request = SimpleNamespace(cookies={settings.ACCESS_COOKIE_NAME: token})
        user = SimpleNamespace(id="user-3", is_active=True)
        db = make_db_with_user(user)

        resolved = await get_optional_user(request=request, credentials=None, db=db)

        assert resolved is user

    @pytest.mark.asyncio
    async def test_raises_401_for_wrong_token_type(self):
        refresh_payload = {"sub": "user-1", "jti": "jti-1", "type": "refresh"}
        refresh_token = jwt.encode(refresh_payload, settings.SECRET_KEY, algorithm=ALGORITHM)
        request = SimpleNamespace(cookies={settings.ACCESS_COOKIE_NAME: refresh_token})
        db = make_db_with_user(SimpleNamespace(id="user-1", is_active=True))

        with pytest.raises(Exception) as exc_info:
            await get_optional_user(request=request, credentials=None, db=db)

        assert exc_info.value.status_code == 401
