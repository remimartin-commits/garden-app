from __future__ import annotations
import pytest
from app.entities import JobCompletion

def test_mobile_offline_sync_success():
    job_completion = JobCompletion(client_id='abc123', client_updated_at='2023-10-01T12:00:00', expected_version=3)
    # Simulating a clean application of job update
    server_response = job_completion.submit_update()
    assert server_response == 'success', f'Unexpected response: {server_response}'

def test_mobile_offline_sync_conflict():
    job_completion = JobCompletion(client_id='abc123', client_updated_at='2023-10-01T12:00:00', expected_version=2)
    # Simulating a conflict scenario
    server_response = job_completion.submit_update()
    assert 'conflict' in server_response, f'Expected conflict in server response: {server_response}'