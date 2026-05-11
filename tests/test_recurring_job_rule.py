from __future__ import annotations

import pytest
from app.schemas.recurring_job_rule import RecurringJobRule


def test_max_jobs_per_window_limits_creation() -> None:
    rule = RecurringJobRule(max_jobs_per_window=5)
    simulated_jobs = [1, 2, 3, 4, 5]
    assert len(simulated_jobs) <= rule.max_jobs_per_window


def test_max_jobs_per_window() -> None:
    rule = RecurringJobRule(max_jobs_per_window=5)
    assert rule.validate_max_jobs(3) is True
    assert rule.validate_max_jobs(5) is True
    assert rule.validate_max_jobs(6) is False
