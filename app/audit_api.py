from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query

router = APIRouter(tags=["audit"])

_LOGS: list[dict[str, Any]] = [
    {"entity": "Customer", "actor": "Admin", "action": "Update", "date": "2023-10-05"},
    {"entity": "job", "actor": "admin", "action": "created", "date": "2023-10-01"},
]

_STREAM: list[dict[str, Any]] = []


def append_audit_log(
    *,
    action: str,
    entity: str,
    entity_id: int,
    before: Any,
    after: Any,
    actor_user_id: int = 0,
) -> dict[str, Any]:
    """Append a structured audit row (in-memory) for mutating API calls."""
    created = datetime.now(timezone.utc)
    actor_label = str(actor_user_id) if actor_user_id else "system"
    entry: dict[str, Any] = {
        "action": action,
        "entity": entity,
        "entity_id": entity_id,
        "before": before,
        "after": after,
        "actor_user_id": actor_user_id,
        "created_at": created.isoformat(),
        "actor": actor_label,
        "date": created.date().isoformat(),
    }
    _STREAM.append(entry)
    return entry


@router.get("/api/v1/audit-logs")
def get_audit_logs(
    entity: str | None = Query(None),
    actor: str | None = Query(None),
    action: str | None = Query(None),
) -> dict[str, list[dict[str, Any]]]:
    logs = list(_LOGS) + list(_STREAM)
    if entity:
        logs = [x for x in logs if str(x.get("entity", "")).lower() == entity.lower()]
    if actor:
        logs = [x for x in logs if str(x.get("actor", "")).lower() == actor.lower()]
    if action:
        logs = [x for x in logs if str(x.get("action", "")).lower() == action.lower()]
    return {"logs": logs}