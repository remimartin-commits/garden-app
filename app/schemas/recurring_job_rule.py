from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RecurringJobRuleCreate(BaseModel):
    property_id: int
    schedule: str
    frequency: int
    start_date: str
    end_date: str | None = None


class JobPreviewResponse(BaseModel):
    jobs: list[dict[str, object]] = Field(default_factory=list)


class RecurringJobRule(BaseModel):
    """Pydantic rule shape used by preview / validation tests."""

    id: int | None = None
    max_jobs_per_window: int = 5

    def preview_jobs(self, date: datetime) -> list[dict[str, object]]:
        rid = self.id if self.id is not None else 0
        return [
            {
                "parent_recurring_rule_id": rid,
                "generated_for_date": date,
            }
        ]

    def validate_max_jobs(self, n: int) -> bool:
        return n <= self.max_jobs_per_window
