from __future__ import annotations
import pytest
from app.entities import Job

def test_job_entity_creation():
    job = Job(
        job_id=1,
        customer_id=101,
        property_id=202,
        description="Mow the lawn",
        workflow_status="Scheduled"
    )
    assert job.job_id == 1
    assert job.customer_id == 101
    assert job.property_id == 202
    assert job.description == "Mow the lawn"
    assert job.workflow_status == "Scheduled"
    assert job.scheduled_date is None
    assert job.completion_date is None
    assert job.audit_log == []
