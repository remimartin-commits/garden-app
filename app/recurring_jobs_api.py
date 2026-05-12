from __future__ import annotations

import calendar
from datetime import datetime, timedelta
from typing import Any, Literal, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app import config
from app.attachment_utils import coerce_attachments_list
from app.extra_costs import normalize_extra_costs_lines
from app.property_api import _get_active_property
from app.s3_uploads import (
    delete_all_stored_attachments_in_list,
    delete_attachments_removed_from_lists,
    enrich_attachments_for_display,
)

router = APIRouter(tags=["recurring-job-rules"])

_NZ = ZoneInfo("Pacific/Auckland")

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
        "extra_costs": [],
        "instances_worked": 0,
        "attachments": [],
    },
}
_NEXT_RULE_ID = 2


def _norm_instances_worked(val: Any) -> int:
    if val is None or val == "":
        return 0
    try:
        n = int(val)
    except (TypeError, ValueError):
        return 0
    return max(0, n)


def _norm_hours_per_instance_in(raw: Any) -> float | None:
    """Persisted hours per visit for hourly billing; None = UI default (1 hr)."""
    if raw is None or raw == "":
        return None
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return None
    if x <= 0:
        return None
    return round(x, 4)


def _hours_per_instance_out(rule: dict[str, Any]) -> float | None:
    return _norm_hours_per_instance_in(rule.get("hours_per_instance"))


def _property_address_for(property_id: Any) -> str | None:
    """Resolve street address from the properties directory when the ID is known."""
    if property_id is None:
        return None
    try:
        pid = int(property_id)
    except (TypeError, ValueError):
        return None
    sp = _get_active_property(pid)
    if sp is None:
        return None
    addr = (sp.address or "").strip()
    return addr or None


def _rule_or_404(rule_id: int) -> dict[str, Any]:
    r = _RULES.get(rule_id)
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring job rule not found")
    return r


def _rule_to_response(rule: dict[str, Any]) -> dict[str, Any]:
    """Stable API shape for list/get/patch (includes extra cost lines)."""
    desc = str(rule.get("description") or rule.get("notes") or "").strip()
    return {
        "id": int(rule["id"]),
        "description": desc or "Recurring job",
        "paused": bool(rule.get("paused", False)),
        "cadence": str(rule.get("cadence") or "weekly"),
        "start_date": str(rule.get("start_date") or ""),
        "property_id": rule.get("property_id"),
        "property_address": _property_address_for(rule.get("property_id")),
        "customer_id": rule.get("customer_id"),
        "day_of_week": int(rule.get("day_of_week", 0)),
        "day_of_month": int(rule.get("day_of_month", 1)),
        "notes": str(rule.get("notes") or ""),
        "extra_costs": normalize_extra_costs_lines(rule.get("extra_costs", [])),
        "instances_worked": _norm_instances_worked(rule.get("instances_worked")),
        "hours_per_instance": _hours_per_instance_out(rule),
        "attachments": enrich_attachments_for_display(coerce_attachments_list(rule.get("attachments"))),
    }


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
                dt = dt.replace(tzinfo=_NZ)
            else:
                dt = dt.astimezone(_NZ)
        else:
            dt = datetime.now(_NZ)
    except Exception:
        dt = datetime.now(_NZ)
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
    extra_costs: list[Any] | None = None
    instances_worked: int | None = Field(default=None, ge=0)
    hours_per_instance: float | None = Field(default=None, gt=0)


class RecurringJobRulePatchBody(BaseModel):
    description: Optional[str] = None
    cadence: Optional[Literal["weekly", "monthly"]] = None
    start_date: Optional[str] = None
    notes: Optional[str] = None
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    day_of_month: Optional[int] = Field(default=None, ge=1, le=28)
    property_id: Optional[int] = None
    customer_id: Optional[int] = None
    extra_costs: Optional[list[Any]] = None
    instances_worked: Optional[int] = Field(default=None, ge=0)
    hours_per_instance: Optional[float] = Field(default=None, gt=0)
    attachments: Optional[list[Any]] = None


@router.get("/api/v1/recurring-job-rules")
def list_recurring_job_rules() -> dict[str, list[dict[str, Any]]]:
    rows = sorted(_RULES.values(), key=lambda r: int(r["id"]), reverse=True)
    return {"rules": [_rule_to_response(r) for r in rows]}


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
        "extra_costs": normalize_extra_costs_lines(body.extra_costs or []),
        "instances_worked": _norm_instances_worked(
            body.instances_worked if body.instances_worked is not None else 0
        ),
        "attachments": [],
    }
    hpi = _norm_hours_per_instance_in(body.hours_per_instance)
    if hpi is not None:
        _RULES[rid]["hours_per_instance"] = hpi
    return {"message": "Recurring job rule created successfully."}


@router.get("/api/v1/recurring-job-rules/{rule_id}")
def read_recurring_job_rule(rule_id: int) -> dict[str, Any]:
    rule = _rule_or_404(rule_id)
    return _rule_to_response(rule)


@router.patch("/api/v1/recurring-job-rules/{rule_id}")
def patch_recurring_job_rule(rule_id: int, body: RecurringJobRulePatchBody) -> dict[str, Any]:
    rule = _rule_or_404(rule_id)
    before_attachments = coerce_attachments_list(list(rule.get("attachments") or []))
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
    if "extra_costs" in data and data["extra_costs"] is not None:
        rule["extra_costs"] = normalize_extra_costs_lines(data["extra_costs"])
    if "instances_worked" in data and data["instances_worked"] is not None:
        rule["instances_worked"] = _norm_instances_worked(data["instances_worked"])
    if "hours_per_instance" in data:
        hraw = data["hours_per_instance"]
        if hraw is None or hraw == "":
            rule.pop("hours_per_instance", None)
        else:
            hpi = _norm_hours_per_instance_in(hraw)
            if hpi is None:
                rule.pop("hours_per_instance", None)
            else:
                rule["hours_per_instance"] = hpi
    if "attachments" in data and data["attachments"] is not None:
        rule["attachments"] = coerce_attachments_list(data["attachments"])
    _RULES[rule_id] = rule
    if "attachments" in data and data["attachments"] is not None:
        delete_attachments_removed_from_lists(before_attachments, rule["attachments"])
    return _rule_to_response(rule)


@router.delete("/api/v1/recurring-job-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring_job_rule(rule_id: int) -> None:
    if rule_id == 1:
        raise HTTPException(status_code=400, detail="Cannot delete the default sample rule")
    if rule_id not in _RULES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring job rule not found")
    rule = _RULES[rule_id]
    delete_all_stored_attachments_in_list(coerce_attachments_list(rule.get("attachments")))
    del _RULES[rule_id]


@router.post("/api/v1/recurring-job-rules/{rule_id}/attachments")
async def post_recurring_rule_attachment(
    rule_id: int,
    file: UploadFile = File(...),
) -> dict[str, str]:
    if not config.s3_job_attachments_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo storage is not configured. Set S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, "
            "S3_SECRET_ACCESS_KEY, S3_BUCKET_NAME, and S3_PUBLIC_BASE_URL.",
        )
    rule = _rule_or_404(rule_id)
    body = await file.read()
    try:
        from app.s3_uploads import upload_job_image

        item = upload_job_image(
            scope="recurring",
            scope_id=rule_id,
            original_filename=file.filename or "photo.jpg",
            content_type=file.content_type,
            body=body,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    atts = coerce_attachments_list(rule.get("attachments"))
    atts.append(item)
    rule["attachments"] = atts
    _RULES[rule_id] = rule
    disp = enrich_attachments_for_display([item])
    return disp[0] if disp else item


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
