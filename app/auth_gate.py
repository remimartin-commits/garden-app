from __future__ import annotations

from urllib.parse import urlencode

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from app import config
from app.auth import SESSION_USER_SESSION_KEY


def _public_path(path: str, method: str) -> bool:
    if path == "/login":
        return True
    if path == "/logout" and method == "POST":
        return True
    if path == "/favicon.ico":
        return True
    if path == "/static/favicon.svg":
        return True
    return False


def _reject_unauthenticated(request: Request) -> Response:
    p = request.url.path
    if p.startswith("/api/") or p == "/openapi.json":
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    next_path = p
    if request.url.query:
        next_path = f"{next_path}?{request.url.query}"
    return RedirectResponse(
        url="/login?" + urlencode({"next": next_path}),
        status_code=302,
    )


class AuthGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not config.auth_gate_enabled():
            return await call_next(request)
        if _public_path(request.url.path, request.method):
            return await call_next(request)
        if request.session.get(SESSION_USER_SESSION_KEY):
            return await call_next(request)
        return _reject_unauthenticated(request)
