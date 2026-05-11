from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["recurring-job-rules"])


class RecurringJobRuleCreateBody(BaseModel):
    property_id: int | None = None
    frequency: str = ""
    start_date: str = ""
    notes: str = ""


@router.post("/api/v1/recurring-job-rules", status_code=201)
def create_recurring_job_rule(body: RecurringJobRuleCreateBody) -> dict[str, str]:
    if body.property_id is None:
        raise HTTPException(status_code=400, detail="Property ID is required")
    return {"message": "Recurring job rule created successfully."}
