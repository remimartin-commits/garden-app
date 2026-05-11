from __future__ import annotations
import pytest
from app.job_management import complete_job
from app.entities import Job

def test_complete_job_once():
    job_id = 'sample-job-id'
    idempotency_key = 'unique-key'
    data = {'actual_duration_minutes': 30, 'ChecklistResult': 'All completed', 'MaterialLineItem': 'Items used', 'attachments': [], 'completed_at': '2023-10-05T14:48:00', 'system_status': 'done'}
    response = complete_job(job_id, data, idempotency_key)
    assert response['status'] == 'success'
    response_retry = complete_job(job_id, data, idempotency_key)
    assert response_retry['error'] == 'Idempotency key already used'