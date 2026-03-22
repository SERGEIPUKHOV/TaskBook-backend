from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.auth.deps import get_current_user, get_optional_user
from app.api.v1.auth.password import router as password_router
from app.api.v1.auth.register import router as register_router
from app.api.v1.auth.sessions import router as sessions_router

# BLOCK-START: AUTH_ROUTER_ROOT
# Description: Root auth router package that preserves the existing /api/v1/auth/* surface.
router = APIRouter()
router.include_router(register_router)
router.include_router(sessions_router)
router.include_router(password_router)
# BLOCK-END: AUTH_ROUTER_ROOT

__all__ = ["get_current_user", "get_optional_user", "router"]
