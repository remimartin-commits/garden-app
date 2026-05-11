from __future__ import annotations

"""Pool reference content helpers (legacy ``site_data`` catalog)."""

from typing import Any

from app.pool.site_data import SERVICES, get_service, list_services


def get_service_by_slug(slug: str) -> dict[str, Any] | None:
    return get_service(slug)


def list_service_pages() -> list[dict[str, Any]]:
    return list_services()


__all__ = [
    "SERVICES",
    "get_service",
    "get_service_by_slug",
    "list_services",
    "list_service_pages",
]
