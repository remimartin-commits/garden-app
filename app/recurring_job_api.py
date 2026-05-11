from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["recurring-job-rules"])


class PauseBody(BaseModel):
    pause: bool = True


class RecurringJobCandidate(BaseModel):
    """Ephemeral preview row (not persisted)."""

    parent_recurring_rule_id: int
    generated_for_date: datetime


# In-memory store keyed by rule id (matches path param).
_RULES: dict[int, dict[str, Any]] = {
    1: {"id": 1, "description": "A sample rule description", "paused": False},
}


def _rule_or_404(rule_id: int) -> dict[str, Any]:
    r = _RULES.get(rule_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Recurring job rule not found")
    return r


@router.post(
    "/api/v1/recurring-job-rules/{rule_id}/preview",
    response_model=list[RecurringJobCandidate],
)
def preview_recurring_jobs(rule_id: int) -> list[RecurringJobCandidate]:
    """Return generated candidate jobs without persistence."""
    _rule_or_404(rule_id)
    start = datetime.now(timezone.utc).replace(microsecond=0)
    return [
        RecurringJobCandidate(
            parent_recurring_rule_id=rule_id,
            generated_for_date=start + timedelta(days=i * 7),
        )
        for i in range(5)
    ]


@router.get("/api/v1/recurring-job-rules/{rule_id}")
def read_recurring_job_rule(rule_id: int) -> dict[str, Any]:
    if rule_id == 1:
        return {"id": 1, "name": "Weekly Lawn Mowing"}
    raise HTTPException(status_code=404, detail="Recurring job rule not found")


@router.post("/api/v1/recurring-job-rules/{rule_id}/pause")
def pause_recurring_job_rule(rule_id: int, body: PauseBody) -> dict[str, Any]:
    """Pause or resume a recurring job rule (explicit ``pause`` flag in JSON body)."""
    rule = _rule_or_404(rule_id)
    rule["paused"] = bool(body.pause)
    return {"status": "success", "job_rule_id": rule_id, "paused": rule["paused"]}
