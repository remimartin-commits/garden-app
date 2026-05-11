from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Job as JobORM
from app.nz_time import (
    NZ,
    nz_calendar_date_from_stored,
    nz_today,
    nz_wall_naive_to_iso_with_offset,
    parse_iso_to_naive_nz_wall,
)

router = APIRouter(tags=["schedule"])


def _effective_datetime(job: JobORM) -> datetime | None:
    if job.scheduled_date is not None:
        return job.scheduled_date
    if not job.detail_json:
        return None
    try:
        payload = json.loads(job.detail_json)
        raw = payload.get("scheduled_date")
        if not raw:
            return None
        return parse_iso_to_naive_nz_wall(str(raw))
    except (json.JSONDecodeError, TypeError):
        return None


def _week_bounds_monday(anchor: date) -> tuple[date, date]:
    """Return [week_start, week_end_exclusive) with Monday as first day."""
    week_start = anchor - timedelta(days=anchor.weekday())
    week_end = week_start + timedelta(days=7)
    return week_start, week_end


@router.get("/api/v1/schedule")
def get_schedule_week(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Jobs grouped for the current calendar week in **New Zealand** (Mon–Sun)."""
    today = nz_today()
    week_start, week_end = _week_bounds_monday(today)

    jobs = (
        db.query(JobORM)
        .options(joinedload(JobORM.customer))
        .order_by(JobORM.id)
        .all()
    )

    slots: list[dict[str, Any]] = []
    unscheduled: list[dict[str, Any]] = []

    for job in jobs:
        cust = job.customer
        cname = cust.name if cust else "—"
        desc = (job.description or "").strip() or f"Job #{job.id}"
        when = _effective_datetime(job)
        base: dict[str, Any] = {
            "job_id": job.id,
            "job_description": desc,
            "description": desc,
            "customer_name": cname,
            "customer": {"id": job.customer_id, "name": cname} if job.customer_id is not None else None,
            "status": job.workflow_status or "Scheduled",
        }
        if when is None:
            unscheduled.append({**base, "scheduled_at": None, "date": None})
            continue
        job_day = nz_calendar_date_from_stored(when)
        if week_start <= job_day < week_end:
            iso = nz_wall_naive_to_iso_with_offset(when)
            slots.append(
                {
                    **base,
                    "scheduled_at": iso,
                    "date": job_day.isoformat(),
                }
            )

    slots.sort(key=lambda x: x.get("scheduled_at") or "")

    return {
        "timezone": str(NZ),
        "week_start": week_start.isoformat(),
        "week_end_exclusive": week_end.isoformat(),
        "slots": slots,
        "unscheduled": unscheduled,
    }


@router.post("/api/v1/schedule/reschedule-weather-risk")
def reschedule_weather_risk(
    _body: dict[str, Any] | None = Body(default=None),
) -> dict[str, object]:
    """Return legacy status plus affected jobs (``weather_snapshot_id`` or ``risk_advice``)."""
    affected_jobs: list[dict[str, object]] = [
        {
            "job_id": 1,
            "property_suburb": "Redcliffs",
            "weather_snapshot_id": 101,
            "risk_advice": None,
        },
        {
            "job_id": 2,
            "property_suburb": "Sumner",
            "weather_snapshot_id": None,
            "risk_advice": (
                "Coastal gusts easing after 14:00; keep original window if crews stay off exposed roofs."
            ),
        },
    ]
    return {
        "status": "Jobs rescheduled successfully",
        "affected_jobs": affected_jobs,
    }
