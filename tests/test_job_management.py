from __future__ import annotations

import pytest

from app.job_management import filter_jobs, preview_recurring_jobs


def test_preview_recurring_jobs() -> None:
    result = preview_recurring_jobs(1)
    assert isinstance(result, list)
    assert len(result) == 3


@pytest.mark.parametrize(
    "criteria, expected_count",
    [
        ({"system_status": "active"}, 3),
        ({"suburb": "Redcliffs"}, 2),
        ({"priority": "high"}, 1),
    ],
)
def test_filter_jobs(criteria: dict[str, str], expected_count: int) -> None:
    result = filter_jobs(**criteria)
    assert len(result) == expected_count
