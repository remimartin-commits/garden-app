from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(tags=["recurring-job-rules"])

_RULES: dict[int, dict[str, Any]] = {
    1: {
        "id": 1,
        "description": "A sample rule description",
        "paused": False,
        "cadence": "weekly",
        "property_id": 201,
        "customer_id": 101,
        "start_date": "2025-01-01",
        "notes": "",
        "day_of_week": 0,
        "day_of_month": 1,
    },
}
_NEXT_RULE_ID = 2


def _rule_or_404(rule_id: int) -> dict[str, Any]:
    r = _RULES.get(rule_id)
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring job rule not found")
    return r


def _norm_cadence(freq: str) -> Literal["weekly", "monthly"]:
    f = (freq or "weekly").strip().lower()
    if f in ("monthly", "month", "m"):
        return "monthly"
    return "weekly"


def _anchor_datetime(rule: dict[str, Any]) -> datetime:
    raw = (rule.get("start_date") or "").strip()
    try:
        if raw:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = datetime.now(timezone.utc)
    except Exception:
        dt = datetime.now(timezone.utc)
    return dt.replace(hour=9, minute=0, second=0, microsecond=0)


def _preview_weekly(rule: dict[str, Any]) -> list[datetime]:
    anchor = _anchor_datetime(rule)
    target_dow = int(rule.get("day_of_week", 0))
    target_dow = max(0, min(6, target_dow))
    wd = anchor.weekday()
    delta = (target_dow - wd) % 7
    first = anchor + timedelta(days=delta)
    return [first + timedelta(days=7 * i) for i in range(5)]


def _month_add(dt: datetime, months: int) -> datetime:
    y, m, d = dt.year, dt.month, dt.day
    m0 = m - 1 + months
    y += m0 // 12
    m = m0 % 12 + 1
    last = calendar.monthrange(y, m)[1]
    d = min(d, last)
    return dt.replace(year=y, month=m, day=d)


def _preview_monthly(rule: dict[str, Any]) -> list[datetime]:
    anchor = _anchor_datetime(rule)
    dom = int(rule.get("day_of_month", 1))
    dom = max(1, min(28, dom))
    try:
        last = calendar.monthrange(anchor.year, anchor.month)[1]
        safe_day = min(dom, last)
        cur = anchor.replace(day=safe_day)
    except ValueError:
        cur = anchor
    out: list[datetime] = []
    for i in range(5):
        out.append(_month_add(cur, i))
    return out


def _preview_dates(rule: dict[str, Any]) -> list[datetime]:
    cadence = _norm_cadence(str(rule.get("cadence", "weekly")))
    if cadence == "monthly":
        return _preview_monthly(rule)
    return _preview_weekly(rule)


class PauseBody(BaseModel):
    pause: bool = True


class RecurringJobCandidate(BaseModel):
    """Ephemeral preview row (not persisted)."""

    parent_recurring_rule_id: int
    generated_for_date: datetime


class RecurringJobRuleCreateBody(BaseModel):
    property_id: int | None = None
    frequency: str = ""
    start_date: str = ""
    notes: str = ""
    customer_id: int | None = None
    day_of_week: int = Field(default=0, ge=0, le=6)
    day_of_month: int = Field(default=1, ge=1, le=28)


class RecurringJobRulePatchBody(BaseModel):
    description: Optional[str] = None
    cadence: Optional[Literal["weekly", "monthly"]] = None
    start_date: Optional[str] = None
    notes: Optional[str] = None
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    day_of_month: Optional[int] = Field(default=None, ge=1, le=28)
    property_id: Optional[int] = None
    customer_id: Optional[int] = None


@router.get("/api/v1/recurring-job-rules")
def list_recurring_job_rules() -> dict[str, list[dict[str, Any]]]:
    rows = sorted(_RULES.values(), key=lambda r: int(r["id"]), reverse=True)
    return {"rules": rows}


@router.post("/api/v1/recurring-job-rules", status_code=status.HTTP_201_CREATED)
def create_recurring_job_rule(body: RecurringJobRuleCreateBody) -> dict[str, str]:
    if body.property_id is None:
        raise HTTPException(status_code=400, detail="Property ID is required")
    global _NEXT_RULE_ID
    rid = _NEXT_RULE_ID
    _NEXT_RULE_ID += 1
    cadence = _norm_cadence(body.frequency)
    _RULES[rid] = {
        "id": rid,
        "description": (body.notes or "Recurring job").strip() or "Recurring job",
        "paused": False,
        "cadence": cadence,
        "property_id": int(body.property_id),
        "customer_id": body.customer_id,
        "start_date": (body.start_date or "").strip(),
        "notes": (body.notes or "").strip(),
        "day_of_week": int(body.day_of_week),
        "day_of_month": int(body.day_of_month),
    }
    return {"message": "Recurring job rule created successfully."}


@router.get("/api/v1/recurring-job-rules/{rule_id}")
def read_recurring_job_rule(rule_id: int) -> dict[str, Any]:
    _rule_or_404(rule_id)
    if rule_id == 1:
        return {"id": 1, "name": "Weekly Lawn Mowing"}
    r = _RULES[rule_id]
    return {
        "id": r["id"],
        "name": r.get("description") or "Scheduled job",
        "cadence": r.get("cadence"),
        "paused": r.get("paused"),
        "start_date": r.get("start_date"),
        "property_id": r.get("property_id"),
        "customer_id": r.get("customer_id"),
        "day_of_week": r.get("day_of_week"),
        "day_of_month": r.get("day_of_month"),
        "notes": r.get("notes"),
    }


@router.patch("/api/v1/recurring-job-rules/{rule_id}")
def patch_recurring_job_rule(rule_id: int, body: RecurringJobRulePatchBody) -> dict[str, Any]:
    rule = _rule_or_404(rule_id)
    data = body.model_dump(exclude_unset=True)
    if "description" in data and data["description"] is not None:
        rule["description"] = str(data["description"]).strip()
    if "cadence" in data and data["cadence"] is not None:
        rule["cadence"] = data["cadence"]
    if "start_date" in data and data["start_date"] is not None:
        rule["start_date"] = str(data["start_date"]).strip()
    if "notes" in data and data["notes"] is not None:
        rule["notes"] = str(data["notes"]).strip()
    if "day_of_week" in data and data["day_of_week"] is not None:
        rule["day_of_week"] = int(data["day_of_week"])
    if "day_of_month" in data and data["day_of_month"] is not None:
        rule["day_of_month"] = int(data["day_of_month"])
    if "property_id" in data and data["property_id"] is not None:
        rule["property_id"] = int(data["property_id"])
    if "customer_id" in data:
        rule["customer_id"] = data["customer_id"]
    _RULES[rule_id] = rule
    return rule


@router.delete("/api/v1/recurring-job-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring_job_rule(rule_id: int) -> None:
    if rule_id == 1:
        raise HTTPException(status_code=400, detail="Cannot delete the default sample rule")
    if rule_id not in _RULES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring job rule not found")
    del _RULES[rule_id]


@router.post(
    "/api/v1/recurring-job-rules/{rule_id}/preview",
    response_model=list[RecurringJobCandidate],
)
def preview_recurring_jobs(rule_id: int) -> list[RecurringJobCandidate]:
    """Return generated candidate job dates without persistence."""
    rule = _rule_or_404(rule_id)
    dates = _preview_dates(rule)
    return [
        RecurringJobCandidate(parent_recurring_rule_id=rule_id, generated_for_date=d) for d in dates
    ]


@router.post("/api/v1/recurring-job-rules/{rule_id}/pause")
def pause_recurring_job_rule(rule_id: int, body: PauseBody) -> dict[str, Any]:
    """Pause or resume a recurring job rule (explicit ``pause`` flag in JSON body)."""
    rule = _rule_or_404(rule_id)
    rule["paused"] = bool(body.pause)
    return {"status": "success", "job_rule_id": rule_id, "paused": rule["paused"]}
