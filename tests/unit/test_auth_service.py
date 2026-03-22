from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    safely_decode_token,
    verify_password,
)


@pytest.mark.unit
class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        hashed = hash_password("mypassword123")
        assert hashed != "mypassword123"

    def test_verify_correct_password(self):
        hashed = hash_password("mypassword123")
        assert verify_password("mypassword123", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("mypassword123")
        assert verify_password("wrongpassword", hashed) is False

    def test_same_password_generates_different_hashes(self):
        assert hash_password("mypassword123") != hash_password("mypassword123")


@pytest.mark.unit
class TestJwtTokens:
    def test_access_token_contains_user_id_and_type(self):
        token = create_access_token("user-42")
        payload = decode_token(token)
        assert payload["sub"] == "user-42"
        assert payload["type"] == "access"

    def test_refresh_token_contains_matching_jti(self):
        token, jti = create_refresh_token("user-42")
        payload = decode_token(token)
        assert payload["sub"] == "user-42"
        assert payload["type"] == "refresh"
        assert payload["jti"] == jti

    @freeze_time("2026-01-01 10:00:00")
    def test_access_token_is_valid_within_ttl(self):
        token = create_access_token("user-1")
        payload = safely_decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-1"

    @freeze_time("2026-01-01 10:00:00")
    def test_access_token_expires_after_configured_ttl(self):
        token = create_access_token("user-1")
        expired_at = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES + 1,
        )

        with freeze_time(expired_at):
            assert safely_decode_token(token) is None

    def test_tampered_token_is_invalid(self):
        token = create_access_token("user-1")
        header, payload, signature = token.split(".")
        tampered_payload = f"{'A' if payload[0] != 'A' else 'B'}{payload[1:]}"
        tampered = ".".join([header, tampered_payload, signature])
        assert safely_decode_token(tampered) is None
