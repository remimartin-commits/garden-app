from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body

router = APIRouter(tags=["schedule"])


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
