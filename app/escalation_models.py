"""Structured escalation payloads for manual / default-agent handoff."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

Urgency = Literal["low", "normal", "high"]


@dataclass
class EscalationMessage:
    title: str
    urgency: Urgency
    summary: str
    current_task: str
    expected_behavior: str
    actual_behavior: str
    failure_type: str
    key_error_excerpt: str
    files_likely_involved: list[str]
    attempted_fixes: list[str]
    what_changed_between_attempts: str
    suspected_root_cause: str
    constraints: list[str]
    requested_help: str
    suggested_next_steps: list[str]
    raw_context_paths: list[str]
    created_at: str
    handoff_prompt: str = ""
    profile_id: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EscalationResolution:
    resolved_by: str  # manual_agent | user | autonomous_retry
    resolution_summary: str
    verification_result: str
    resolved_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_constraints() -> list[str]:
    return [
        "Do not delete or weaken tests.",
        "Do not broaden scope beyond the current task.",
        "Prefer the smallest fix that satisfies the schema.",
        "Preserve existing UI/API behavior unless the task requires changing it.",
    ]
