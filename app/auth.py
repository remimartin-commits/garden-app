from __future__ import annotations

from typing import Any

from app import config

SESSION_USER_SESSION_KEY = "owner_username"


def verify_owner_credentials(username: str, password: str) -> bool:
    """True if username/password match configured owner (from env via config)."""
    u = (username or "").strip()
    p = password or ""
    expected = (config.OWNER_PASSWORD or "").strip()
    if not expected:
        return False
    return u == (config.OWNER_USERNAME or "").strip() and p == expected


def authenticate_user(username: str, password: str) -> str | None:
    """Legacy helper: returns a non-empty token string on success."""
    return "session-token" if verify_owner_credentials(username, password) else None


def _permission_set(principal: Any) -> set[str]:
    if isinstance(principal, dict):
        raw = principal.get("permissions", ())
        return set(raw) if isinstance(raw, (list, tuple, set)) else set()
    role = getattr(principal, "role", None)
    if role is None:
        return set()
    plist = getattr(role, "permissions", None) or []
    return set(plist)


def has_permission(principal: Any, *args: Any) -> bool:
    """Check a flat permission key, or (HTTP method, API path) for route-level checks."""
    if len(args) == 1:
        return str(args[0]) in _permission_set(principal)
    if len(args) == 2:
        method, path = str(args[0]).upper(), str(args[1])
        perms = _permission_set(principal)
        if method == "GET" and path.startswith("/api/v1/jobs/"):
            return "jobs.read" in perms
        if method == "POST" and "/jobs/" in path and path.rstrip("/").endswith("complete"):
            return "jobs.complete" in perms
        if method == "POST" and (path == "/api/v1/invoices" or path.startswith("/api/v1/invoices")):
            return bool(perms.intersection({"billing.write", "invoices.post"}))
        if method == "PATCH" and path.startswith("/api/v1/settings/"):
            return bool(perms.intersection({"settings.write", "settings.patch"}))
        return False
    raise TypeError("has_permission expects (principal, perm) or (principal, method, path)")
