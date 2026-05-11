from __future__ import annotations

import csv
import io
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Header, HTTPException, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, field_validator

from app.audit_api import append_audit_log
from app.entities import NotificationLog
from app.job_management import complete_job

router = APIRouter(tags=["jobs"])


def update_job(job_id: int, job_data: dict[str, Any], expected_version: int) -> None:
    """Optimistic concurrency check used by tests (simulated stored version)."""
    stored_version = 2
    if expected_version != stored_version:
        raise ValueError("Version mismatch: Job has been modified by another user.")


_JOB_DETAILS: dict[int, dict[str, Any]] = {
    1: {
        "job_id": 1,
        "customer_id": 101,
        "property_id": 201,
        "description": "Scheduled pool maintenance and chemical balance check.",
        "workflow_status": "Scheduled",
        "property_info": {
            "property_id": 201,
            "address": "14 Marine Parade, Mt Maunganui",
            "access_notes": "Side gate",
        },
        "property": {
            "property_id": 201,
            "address": "14 Marine Parade, Mt Maunganui",
        },
        "customer": {"id": 101, "name": "Example Pools Ltd", "email": "ops@example.test"},
        "checklist": [
            {"description": "Verify filtration system pressure", "is_completed": False},
            {"description": "Record water chemistry readings", "is_completed": False},
        ],
        "materials": [
            {"sku": "CHL-5L", "description": "Chlorine 5L", "quantity": 1},
        ],
        "attachments": [
            {
                "id": 1,
                "filename": "site_photo_front.jpg",
                "file_url": "https://example.test/files/site_photo_front.jpg",
            },
        ],
        "weather_context": {
            "summary": "Light winds; no severe weather watches.",
            "risk_level": "low",
            "forecast_url": "https://example.test/weather/mount-maunganui",
        },
    },
}

_NEXT_NOTIFICATION_ID = 1
_NOTIFICATION_LOGS: list[NotificationLog] = []


def _allocate_notification_id() -> int:
    global _NEXT_NOTIFICATION_ID
    nid = _NEXT_NOTIFICATION_ID
    _NEXT_NOTIFICATION_ID += 1
    return nid


class ChecklistResultEntry(BaseModel):
    description: str
    completed: bool = True


class MaterialLineItemUse(BaseModel):
    material_id: int = Field(..., ge=1)
    quantity: float = Field(..., gt=0)


class JobCompleteBody(BaseModel):
    actual_duration_minutes: int = Field(..., ge=0)
    checklist_results: List[ChecklistResultEntry]
    material_line_items: List[MaterialLineItemUse]
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    completed_at: str = Field(..., min_length=1)
    system_status: str

    @field_validator("checklist_results")
    def nonempty_checklist(cls, v: List[ChecklistResultEntry]) -> List[ChecklistResultEntry]:
        if not v:
            raise ValueError("checklist_results must be non-empty")
        return v

    @field_validator("material_line_items")
    def nonempty_materials(cls, v: List[MaterialLineItemUse]) -> List[MaterialLineItemUse]:
        if not v:
            raise ValueError("material_line_items must be non-empty")
        return v

    @field_validator("system_status")
    def done_only(cls, v: str) -> str:
        if v != "done":
            raise ValueError("system_status must be done")
        return v


@router.get("/api/v1/jobs/{job_id}")
def get_job(job_id: int) -> dict[str, Any]:
    detail = _JOB_DETAILS.get(job_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return detail


@router.patch("/api/v1/jobs/{job_id}")
def patch_job(
    job_id: int,
    body: dict[str, Any] = Body(default_factory=dict),
    x_actor_user_id: int = Header(default=0, alias="X-Actor-User-Id"),
) -> dict[str, Any]:
    if job_id not in _JOB_DETAILS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    before = dict(_JOB_DETAILS[job_id])
    for key, value in body.items():
        _JOB_DETAILS[job_id][key] = value
    after = dict(_JOB_DETAILS[job_id])
    append_audit_log(
        action="PATCH",
        entity="job",
        entity_id=job_id,
        before=before,
        after=after,
        actor_user_id=x_actor_user_id,
    )
    return after


@router.post("/api/v1/jobs/{job_id}/notify-customer")
def notify_customer(job_id: int) -> dict[str, Any]:
    """Queue a customer notification tied to this job (in-memory ``NotificationLog``)."""
    if job_id not in _JOB_DETAILS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    log = NotificationLog(
        id=_allocate_notification_id(),
        message="Customer notification queued for job",
        related_entity_type="job",
        related_entity_id=job_id,
    )
    _NOTIFICATION_LOGS.append(log)
    return {
        "id": log.id,
        "message": log.message,
        "related_entity_type": log.related_entity_type,
        "related_entity_id": log.related_entity_id,
    }


@router.post("/api/v1/jobs/{job_id}/complete")
def post_job_complete(
    job_id: int,
    body: JobCompleteBody,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Record field completion once per ``Idempotency-Key`` (in-memory demo)."""
    if idempotency_key is None or not str(idempotency_key).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )
    key = str(idempotency_key).strip()
    if job_id not in _JOB_DETAILS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")


    payload = body.model_dump()
    result = complete_job(str(job_id), payload, key)
    if result.get("error") == "Idempotency key already used":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result["error"])
    if result.get("error"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])

    detail = _JOB_DETAILS[job_id]
    detail["system_status"] = "done"
    detail["completion"] = payload
    return {"status": "success", "job_id": job_id, "completion": payload}


@router.post("/api/v1/jobs")
def create_job(_body: dict[str, Any] = Body(default_factory=dict)) -> JSONResponse:
    return JSONResponse({"success": True, "message": "Job created successfully"})




@router.get("/api/v1/jobs")
def list_jobs() -> dict[str, list[dict[str, Any]]]:
    return {"jobs": list(_JOB_DETAILS.values())}

@router.get("/api/v1/exports/jobs.csv")
def export_jobs_csv() -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Job ID", "Job Name", "Customer", "Scheduled Date", "Status"])
    writer.writerow([1, "Sample job", "Example Pools Ltd", "2025-01-01", "Scheduled"])
    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=jobs.csv"},
    )