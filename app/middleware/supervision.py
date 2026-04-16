from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

BLOCKED_PREFIXES = (
    "/api/v1/auth/",
    "/api/v1/users/",
    "/api/v1/profile",
    "/api/v1/admin",
)
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
SUPERVISION_PREFIX = "/api/v1/supervision"


class SupervisionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.view_as_user_id = None
        request.state.view_as_enabled = False

        owner_id = request.headers.get("X-View-As", "").strip()
        if not owner_id:
            return await call_next(request)

        request.state.view_as_user_id = owner_id
        request.state.view_as_enabled = True

        if request.url.path.startswith(BLOCKED_PREFIXES) and request.url.path != "/api/v1/users/me":
            return JSONResponse(status_code=403, content={"detail": "Доступ запрещён"})

        if request.method in MUTATING_METHODS and not request.url.path.startswith(SUPERVISION_PREFIX):
            return JSONResponse(status_code=403, content={"detail": "Режим просмотра доступен только для чтения"})

        return await call_next(request)
