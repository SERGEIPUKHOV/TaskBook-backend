from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.admin.stats import router as stats_router
from app.api.v1.admin.users import router as users_router

# BLOCK-START: ADMIN_ROUTER_ROOT
# Description: Root admin router that preserves the existing /api/v1/admin/* surface.
router = APIRouter()
router.include_router(users_router)
router.include_router(stats_router)
# BLOCK-END: ADMIN_ROUTER_ROOT

__all__ = ["router"]
