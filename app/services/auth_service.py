from __future__ import annotations

from datetime import datetime, timezone
import logging

from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import redis_client
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import AuthResponseOut, AuthUserOut
from app.services.habit_service import seed_default_habits_for_user

REFRESH_KEY = "refresh:{user_id}:{jti}"
logger = logging.getLogger(__name__)


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    normalized_email = email.strip().lower()
    result = await db.execute(select(User).where(User.email == normalized_email))
    return result.scalar_one_or_none()


async def store_refresh_token(user_id: str, jti: str) -> None:
    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    await redis_client.set(REFRESH_KEY.format(user_id=user_id, jti=jti), "valid", ex=ttl)


async def revoke_refresh_token(user_id: str, jti: str) -> None:
    await redis_client.delete(REFRESH_KEY.format(user_id=user_id, jti=jti))


async def is_refresh_token_valid(user_id: str, jti: str) -> bool:
    return await redis_client.exists(REFRESH_KEY.format(user_id=user_id, jti=jti)) == 1


def build_auth_response(user: User, access_token: str, refresh_token: str) -> AuthResponseOut:
    return AuthResponseOut(
        access_token=access_token,
        refresh_token=refresh_token,
        user=AuthUserOut.model_validate(user),
    )


async def issue_auth_tokens(user: User) -> AuthResponseOut:
    access_token = create_access_token(user.id)
    refresh_token, jti = create_refresh_token(user.id)
    await store_refresh_token(user.id, jti)
    return build_auth_response(user, access_token, refresh_token)


async def register_user(db: AsyncSession, email: str, password: str) -> AuthResponseOut:
    normalized_email = email.strip().lower()
    logger.info("[AUTH][REGISTER][ATTEMPT] email=%s", normalized_email)
    existing = await get_user_by_email(db, normalized_email)

    if existing:
        logger.warning("[AUTH][REGISTER][FAILED] email=%s reason=DUPLICATE_EMAIL", normalized_email)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пользователь с таким email уже существует")

    user = User(email=normalized_email, hashed_password=hash_password(password))
    db.add(user)
    await db.flush()
    await seed_default_habits_for_user(db, user.id)
    await db.commit()
    await db.refresh(user)
    logger.info("[AUTH][REGISTER][SUCCESS] user_id=%s", user.id)
    return await issue_auth_tokens(user)


async def login_user(db: AsyncSession, email: str, password: str) -> AuthResponseOut:
    normalized_email = email.strip().lower()
    logger.info("[AUTH][LOGIN][ATTEMPT] email=%s", normalized_email)
    user = await get_user_by_email(db, normalized_email)

    if user is None or not verify_password(password, user.hashed_password):
        logger.warning("[AUTH][LOGIN][FAILED] email=%s reason=INVALID_CREDENTIALS", normalized_email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль")

    if not user.is_active:
        logger.warning("[AUTH][LOGIN][FAILED] email=%s reason=INACTIVE_ACCOUNT", normalized_email)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Аккаунт заблокирован")

    user.last_login = datetime.now(timezone.utc)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("[AUTH][LOGIN][SUCCESS] user_id=%s", user.id)
    return await issue_auth_tokens(user)


async def refresh_session(db: AsyncSession, refresh_token: str) -> AuthResponseOut:
    try:
        payload = decode_token(refresh_token)
    except JWTError as exc:
        logger.warning("[AUTH][REFRESH][FAILED] reason=INVALID_TOKEN")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized") from exc

    if payload.get("type") != "refresh":
        logger.warning("[AUTH][REFRESH][FAILED] reason=WRONG_TOKEN_TYPE")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    user_id = str(payload.get("sub", ""))
    jti = str(payload.get("jti", ""))
    if not user_id or not jti or not await is_refresh_token_valid(user_id, jti):
        logger.warning("[AUTH][REFRESH][FAILED] user_id=%s reason=TOKEN_REVOKED_OR_MISSING", user_id or "unknown")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        logger.warning("[AUTH][REFRESH][FAILED] user_id=%s reason=USER_NOT_ACTIVE", user_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    await revoke_refresh_token(user_id, jti)
    logger.info("[AUTH][REFRESH][SUCCESS] user_id=%s", user.id)
    return await issue_auth_tokens(user)


async def logout_user(refresh_token: str) -> None:
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        return

    if payload.get("type") != "refresh":
        return

    user_id = str(payload.get("sub", ""))
    jti = str(payload.get("jti", ""))
    if user_id and jti:
        await revoke_refresh_token(user_id, jti)


async def forgot_password(db: AsyncSession, email: str) -> None:
    user = await get_user_by_email(db, email)
    if user is None:
        return

    token = create_reset_token(user.id)
    payload = decode_token(token)
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    user.reset_token = token
    user.reset_token_expires_at = expires_at
    db.add(user)
    await db.commit()


async def validate_reset_token(db: AsyncSession, token: str) -> bool:
    result = await db.execute(select(User).where(User.reset_token == token))
    user = result.scalar_one_or_none()
    if user is None or user.reset_token_expires_at is None:
        return False
    return user.reset_token_expires_at > datetime.now(timezone.utc)


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    result = await db.execute(select(User).where(User.reset_token == token))
    user = result.scalar_one_or_none()
    if user is None or user.reset_token_expires_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token is invalid")

    if user.reset_token_expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token is invalid")

    user.hashed_password = hash_password(new_password)
    user.reset_token = None
    user.reset_token_expires_at = None
    db.add(user)
    await db.commit()


async def change_password(db: AsyncSession, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный текущий пароль.")

    user.hashed_password = hash_password(new_password)
    user.reset_token = None
    user.reset_token_expires_at = None
    db.add(user)
    await db.commit()


async def delete_account(db: AsyncSession, user: User, password: str) -> None:
    if not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный пароль.")

    await db.delete(user)
    await db.commit()


async def _ensure_seed_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    is_admin: bool,
) -> None:
    existing = await get_user_by_email(db, email)
    if existing:
        return

    user = User(
        email=email,
        hashed_password=hash_password(password),
        is_admin=is_admin,
    )
    db.add(user)
    await db.flush()
    await seed_default_habits_for_user(db, user.id)


async def ensure_seed_users(db: AsyncSession) -> None:
    if settings.SEED_DEMO_USER:
        await _ensure_seed_user(
            db,
            email=settings.DEMO_USER_EMAIL,
            password=settings.DEMO_USER_PASSWORD,
            is_admin=False,
        )

    if settings.SEED_ADMIN_USER:
        await _ensure_seed_user(
            db,
            email=settings.ADMIN_USER_EMAIL,
            password=settings.ADMIN_USER_PASSWORD,
            is_admin=True,
        )

    await db.commit()
