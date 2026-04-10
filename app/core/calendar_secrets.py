from __future__ import annotations

from base64 import urlsafe_b64encode
from functools import lru_cache
from hashlib import sha256

from cryptography.fernet import Fernet

from app.core.config import settings


@lru_cache
def _fernet() -> Fernet:
    material = settings.CALENDAR_SECRETS_KEY.encode("utf-8")
    derived_key = urlsafe_b64encode(sha256(material).digest())
    return Fernet(derived_key)


def encrypt_secret(value: str | None) -> str | None:
    if not value:
        return None

    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None

    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
