from __future__ import annotations
from app.entities import JobStatusDefinition

def test_job_status_definition_creation():
    job_status = JobStatusDefinition(
        name="Scheduled",
        description="The job is scheduled to be completed",
        is_active=True,
        system_status_category="In Progress",
        quote_state="Awaiting Payment",
        invoice_state="Pending"
    )
    assert job_status.name == "Scheduled"
    assert job_status.description == "The job is scheduled to be completed"
    assert job_status.is_active is True
    assert job_status.system_status_category == "In Progress"
    assert job_status.quote_state == "Awaiting Payment"
    assert job_status.invoice_state == "Pending"
