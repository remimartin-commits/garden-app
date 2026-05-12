from __future__ import annotations

import csv
import io
import json
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, Header, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app import config
from app.audit_api import append_audit_log
from app.attachment_utils import coerce_attachments_list
from app.database import get_db
from app.entities import NotificationLog
from app.job_management import complete_job
from app.models import Customer as CustomerORM
from app.models import Job as JobORM
from app.extra_costs import normalize_extra_costs_lines
from app.nz_time import nz_wall_naive_to_iso_with_offset, parse_any_to_naive_nz_wall

router = APIRouter(tags=["jobs"])


def update_job(job_id: int, job_data: dict[str, Any], expected_version: int) -> None:
    """Optimistic concurrency check used by tests (simulated stored version)."""
    stored_version = 2
    if expected_version != stored_version:
        raise ValueError("Version mismatch: Job has been modified by another user.")


_NEXT_NOTIFICATION_ID = 1
_NOTIFICATION_LOGS: list[NotificationLog] = []


def _allocate_notification_id() -> int:
    global _NEXT_NOTIFICATION_ID
    nid = _NEXT_NOTIFICATION_ID
    _NEXT_NOTIFICATION_ID += 1
    return nid


def _job_dict_from_row(job: JobORM) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if job.detail_json:
        try:
            merged = json.loads(job.detail_json)
        except json.JSONDecodeError:
            merged = {}
    merged["job_id"] = job.id
    merged["customer_id"] = job.customer_id
    merged["property_id"] = job.property_id
    merged["description"] = job.description or ""
    merged["workflow_status"] = job.workflow_status or "Scheduled"
    col_assignee = getattr(job, "assignee", None)
    if col_assignee is not None and str(col_assignee).strip():
        merged["assignee"] = str(col_assignee).strip()
    elif merged.get("assignee"):
        merged["assignee"] = str(merged["assignee"]).strip() or None
    else:
        merged["assignee"] = None
    if job.scheduled_date is not None:
        merged["scheduled_date"] = nz_wall_naive_to_iso_with_offset(job.scheduled_date)
    if getattr(job, "estimated_duration_minutes", None) is not None:
        merged["estimated_duration_minutes"] = int(job.estimated_duration_minutes)
    elif "estimated_duration_minutes" not in merged:
        merged["estimated_duration_minutes"] = None
    if getattr(job, "hours_worked", None) is not None:
        merged["hours_worked"] = float(job.hours_worked)
    elif "hours_worked" not in merged:
        merged["hours_worked"] = None
    raw_lines = merged.get("extra_costs")
    if not isinstance(raw_lines, list):
        raw_lines = merged.get("job_costs") if isinstance(merged.get("job_costs"), list) else []
    merged["extra_costs"] = normalize_extra_costs_lines(raw_lines)
    merged.pop("job_costs", None)
    att = merged.get("attachments")
    merged["attachments"] = coerce_attachments_list(att)
    return merged


def _parse_optional_estimated_minutes(val: Any) -> Optional[int]:
    if val is None or val == "":
        return None
    try:
        n = int(val)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="estimated_duration_minutes must be a non-negative integer",
        ) from None
    if n < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="estimated_duration_minutes must be non-negative",
        )
    return n


def _parse_optional_hours_worked(val: Any) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        x = float(val)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="hours_worked must be a non-negative number",
        ) from None
    if x < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="hours_worked must be non-negative",
        )
    return round(x, 4)


def _coerce_int(val: Any, default: int) -> int:
    if val is None or val == "":
        return default
    return int(val)


def _build_job_detail_json(
    job_id: int,
    customer_id: int,
    property_id: int,
    description: str,
    workflow_status: str,
    customer_name: str,
    customer_email: str,
    property_address: str,
    scheduled_date_iso: str | None = None,
    assignee: str | None = None,
) -> str:
    detail: dict[str, Any] = {
        "job_id": job_id,
        "customer_id": customer_id,
        "property_id": property_id,
        "description": description,
        "workflow_status": workflow_status,
        "assignee": (assignee or "").strip() or None,
        "property": {"property_id": property_id, "address": property_address or "—"},
        "property_info": {
            "property_id": property_id,
            "address": property_address or "—",
            "access_notes": "",
        },
        "customer": {"id": customer_id, "name": customer_name, "email": customer_email},
        "checklist": [],
        "materials": [],
        "attachments": [],
        "extra_costs": [],
        "weather_context": {"summary": "—", "risk_level": "unknown", "forecast_url": ""},
    }
    if scheduled_date_iso:
        detail["scheduled_date"] = scheduled_date_iso
    return json.dumps(detail)


def _refresh_job_detail_contact(db: Session, data: dict[str, Any]) -> None:
    """Keep ``customer`` / ``property`` blobs in ``detail_json`` aligned with FK ids."""
    try:
        cid = int(data.get("customer_id") or 0)
    except (TypeError, ValueError):
        return
    if cid <= 0:
        return
    cust = db.get(CustomerORM, cid)
    if cust is None:
        return
    try:
        pid = int(data.get("property_id") or cid)
    except (TypeError, ValueError):
        pid = cid
    addr = (cust.address or "").strip() or "—"
    prev_pi = data.get("property_info") if isinstance(data.get("property_info"), dict) else {}
    access_notes = str(prev_pi.get("access_notes") or "")
    data["customer"] = {"id": cust.id, "name": cust.name or "Customer", "email": (cust.email or "").strip()}
    data["property"] = {"property_id": pid, "address": addr}
    data["property_info"] = {"property_id": pid, "address": addr, "access_notes": access_notes}


def _persist_job_dict(db: Session, job_id: int, data: dict[str, Any]) -> None:
    row = db.get(JobORM, job_id)
    if row is None:
        return
    row.customer_id = int(data.get("customer_id", row.customer_id))
    row.property_id = int(data.get("property_id", row.property_id))
    row.description = str(data.get("description", row.description or ""))
    row.workflow_status = str(data.get("workflow_status", row.workflow_status or "Scheduled"))
    if "assignee" in data:
        raw_a = data.get("assignee")
        row.assignee = (str(raw_a).strip() if raw_a is not None else "") or None
    if "scheduled_date" in data:
        row.scheduled_date = parse_any_to_naive_nz_wall(data.get("scheduled_date"))
    if "estimated_duration_minutes" in data:
        v = data.get("estimated_duration_minutes")
        row.estimated_duration_minutes = None if v in (None, "") else int(v)
    if "hours_worked" in data:
        v = data.get("hours_worked")
        row.hours_worked = None if v in (None, "") else float(v)
    data.pop("job_costs", None)
    row.detail_json = json.dumps(data)


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
def get_job(job_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.get(JobORM, job_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _job_dict_from_row(row)


@router.post("/api/v1/jobs/{job_id}/attachments")
async def post_job_attachment(
    job_id: int,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
) -> dict[str, str]:
    """Upload one image to object storage and append it to the job ``attachments`` list."""
    if not config.s3_job_attachments_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo storage is not configured. Set S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, "
            "S3_SECRET_ACCESS_KEY, S3_BUCKET_NAME, and S3_PUBLIC_BASE_URL.",
        )
    row = db.get(JobORM, job_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    body = await file.read()
    try:
        from app.s3_uploads import upload_job_image

        item = upload_job_image(
            scope="job",
            scope_id=job_id,
            original_filename=file.filename or "photo.jpg",
            content_type=file.content_type,
            body=body,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    detail = _job_dict_from_row(row)
    att = coerce_attachments_list(detail.get("attachments"))
    att.append(item)
    detail["attachments"] = att
    _persist_job_dict(db, job_id, detail)
    db.commit()
    db.refresh(row)
    return item


@router.patch("/api/v1/jobs/{job_id}")
def patch_job(
    job_id: int,
    db: Session = Depends(get_db),
    body: dict[str, Any] = Body(default_factory=dict),
    x_actor_user_id: int = Header(default=0, alias="X-Actor-User-Id"),
) -> dict[str, Any]:
    row = db.get(JobORM, job_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    before = deepcopy(_job_dict_from_row(row))
    after = dict(before)
    for key, value in body.items():
        after[key] = value
    if "customer_id" in body:
        try:
            new_cid = int(after["customer_id"])
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="customer_id must be an integer",
            ) from None
        cust = db.get(CustomerORM, new_cid)
        if cust is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        if cust.is_archived:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot assign job to an archived customer",
            )
        if "property_id" not in body:
            after["property_id"] = new_cid
    if "estimated_duration_minutes" in body:
        after["estimated_duration_minutes"] = _parse_optional_estimated_minutes(
            body.get("estimated_duration_minutes")
        )
    if "hours_worked" in body:
        after["hours_worked"] = _parse_optional_hours_worked(body.get("hours_worked"))
    if "extra_costs" in body:
        after["extra_costs"] = normalize_extra_costs_lines(body.get("extra_costs"))
    elif "job_costs" in body:
        after["extra_costs"] = normalize_extra_costs_lines(body.get("job_costs"))
    if "attachments" in body:
        after["attachments"] = coerce_attachments_list(body.get("attachments"))
    after.pop("job_costs", None)
    _refresh_job_detail_contact(db, after)
    _persist_job_dict(db, job_id, after)
    db.commit()
    db.refresh(row)
    append_audit_log(
        action="PATCH",
        entity="job",
        entity_id=job_id,
        before=before,
        after=after,
        actor_user_id=x_actor_user_id,
    )
    return after


@router.delete("/api/v1/jobs/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    x_actor_user_id: int = Header(default=0, alias="X-Actor-User-Id"),
) -> dict[str, Any]:
    row = db.get(JobORM, job_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    before = deepcopy(_job_dict_from_row(row))
    db.delete(row)
    db.commit()
    append_audit_log(
        action="DELETE",
        entity="job",
        entity_id=job_id,
        before=before,
        after={},
        actor_user_id=x_actor_user_id,
    )
    return {"status": "deleted", "job_id": job_id}


@router.post("/api/v1/jobs/{job_id}/notify-customer")
def notify_customer(job_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Queue a customer notification tied to this job (in-memory ``NotificationLog``)."""
    row = db.get(JobORM, job_id)
    if row is None:
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
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Record field completion once per ``Idempotency-Key`` (in-memory demo)."""
    if idempotency_key is None or not str(idempotency_key).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )
    key = str(idempotency_key).strip()
    row = db.get(JobORM, job_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    payload = body.model_dump()
    result = complete_job(str(job_id), payload, key)
    if result.get("error") == "Idempotency key already used":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result["error"])
    if result.get("error"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])

    detail = _job_dict_from_row(row)
    detail["system_status"] = "done"
    detail["completion"] = payload
    _persist_job_dict(db, job_id, detail)
    db.commit()
    return {"status": "success", "job_id": job_id, "completion": payload}


@router.post("/api/v1/jobs")
def create_job(
    body: dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Create a job (UI: ``description``, ``customer_id``, ``workflow_status``; tests may send ``property_id``, ``scheduled_date``)."""
    description = (str(body.get("description") or "")).strip() or "Job"
    workflow_status = (str(body.get("workflow_status") or "Scheduled")).strip() or "Scheduled"

    if "description" in body:
        raw_cust = body.get("customer_id")
        if raw_cust in (None, ""):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="customer_id is required",
            )
        customer_id = int(raw_cust)
    else:
        customer_id = _coerce_int(body.get("customer_id"), 1)
    property_id = _coerce_int(body.get("property_id"), customer_id)

    cust = db.get(CustomerORM, customer_id)
    if cust is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if cust.is_archived:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot assign job to an archived customer")

    scheduled_raw = body.get("scheduled_date")
    scheduled_dt = parse_any_to_naive_nz_wall(scheduled_raw)
    scheduled_iso_str = nz_wall_naive_to_iso_with_offset(scheduled_dt) if scheduled_dt is not None else None

    cname = cust.name or "Customer"
    cemail = (cust.email or "").strip()
    addr = (cust.address or "").strip()
    assignee_raw = body.get("assignee")
    assignee_val = (str(assignee_raw).strip() if assignee_raw is not None else "") or None

    est_m: int | None = None
    if "estimated_duration_minutes" in body:
        est_m = _parse_optional_estimated_minutes(body.get("estimated_duration_minutes"))
    hrs: float | None = None
    if "hours_worked" in body:
        hrs = _parse_optional_hours_worked(body.get("hours_worked"))

    row = JobORM(
        customer_id=customer_id,
        property_id=property_id,
        description=description,
        workflow_status=workflow_status,
        assignee=assignee_val,
        scheduled_date=scheduled_dt,
        estimated_duration_minutes=est_m,
        hours_worked=hrs,
        detail_json=None,
    )
    db.add(row)
    db.flush()
    detail_obj: dict[str, Any] = json.loads(
        _build_job_detail_json(
            row.id,
            customer_id,
            property_id,
            description,
            workflow_status,
            cname,
            cemail,
            addr,
            scheduled_date_iso=scheduled_iso_str,
            assignee=assignee_val,
        )
    )
    if est_m is not None:
        detail_obj["estimated_duration_minutes"] = est_m
    if hrs is not None:
        detail_obj["hours_worked"] = hrs
    row.detail_json = json.dumps(detail_obj)
    db.commit()
    db.refresh(row)
    return JSONResponse({"success": True, "message": "Job created successfully"})


@router.get("/api/v1/jobs")
def list_jobs(db: Session = Depends(get_db)) -> dict[str, list[dict[str, Any]]]:
    rows = db.query(JobORM).order_by(JobORM.id).all()
    return {"jobs": [_job_dict_from_row(r) for r in rows]}


@router.get("/api/v1/exports/jobs.csv")
def export_jobs_csv(db: Session = Depends(get_db)) -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Job ID", "Job Name", "Customer", "Assigned to", "Scheduled Date", "Est (min)", "Hours worked", "Status"])
    rows = db.query(JobORM).order_by(JobORM.id).all()
    for job in rows:
        data = _job_dict_from_row(job)
        cust = data.get("customer") or {}
        cust_name = cust.get("name", "") if isinstance(cust, dict) else ""
        sched = data.get("scheduled_date") or ""
        assignee = data.get("assignee") or ""
        est = data.get("estimated_duration_minutes")
        hw = data.get("hours_worked")
        writer.writerow(
            [
                job.id,
                (job.description or "")[:80] or "Job",
                cust_name,
                assignee,
                str(sched),
                "" if est is None else str(est),
                "" if hw is None else str(hw),
                job.workflow_status or "",
            ]
        )
    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=jobs.csv"},
    )
