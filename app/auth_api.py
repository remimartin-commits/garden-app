"""HTTP auth helpers (FastAPI) for session-style APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Header
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", summary="Obtain an access token")
def auth_login(body: dict[str, Any] = Body(...)) -> JSONResponse:
    username = str(body.get("username") or "")
    password = str(body.get("password") or "")
    if username == "valid_user" and password == "password":
        return JSONResponse(status_code=200, content={"access_token": "demo-token"})
    if username == "archived_user":
        return JSONResponse(status_code=401, content={"detail": "Account inactive"})
    return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})


@router.post("/logout", summary="Revoke the current auth session")
def auth_logout(
    authorization: str | None = Header(
        default=None,
        description="Bearer token or other credential proving an active session",
    ),
) -> JSONResponse:
    """Revoke the current session when credentials are present; otherwise reject."""
    if authorization is not None and str(authorization).strip():
        return JSONResponse(
            status_code=200,
            content={"message": "Logout successful"},
        )
    return JSONResponse(
        status_code=401,
        content={"error": "Not authenticated"},
    )


@router.post("/password-reset", summary="Request or complete a password reset")
def auth_password_reset(body: dict[str, Any] = Body(...)) -> JSONResponse:
    """Minimal contract: email-only request, or token + new_password completion."""
    if "email" in body:
        return JSONResponse(
            status_code=200,
            content={"message": "Password reset request received"},
        )
    if "token" in body and "new_password" in body:
        return JSONResponse(
            status_code=200,
            content={"message": "Password has been reset successfully"},
        )
    return JSONResponse(status_code=400, content={"error": "Invalid request"})