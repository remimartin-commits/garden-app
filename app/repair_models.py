"""Structured types for evidence-based autonomous repair."""

from __future__ import annotations

from typing import Any, Literal

FailureType = Literal[
    "test_failure",
    "build_failure",
    "runtime_error",
    "json_parse_error",
    "schema_alignment_failure",
    "missing_dependency",
    "permission_error",
    "unknown",
]

Confidence = Literal["low", "medium", "high"]
FailureDelta = Literal["fixed", "improved", "changed", "unchanged", "worsened"]
RiskLevel = Literal["low", "medium", "high"]


def diagnosis_dict(
    *,
    failure_type: FailureType,
    failing_command: str,
    exit_code: str | int | None,
    relevant_error_excerpt: str,
    suspected_root_cause: str,
    affected_files: list[str],
    confidence: Confidence,
    proposed_fix_strategy: str,
    should_retry: bool,
    needs_human_review: bool,
    repair_hints: list[str] | None = None,
) -> dict[str, Any]:
    rh = [str(x).strip() for x in (repair_hints or []) if str(x).strip()]
    out: dict[str, Any] = {
        "failure_type": failure_type,
        "failing_command": failing_command,
        "exit_code": exit_code,
        "relevant_error_excerpt": relevant_error_excerpt[:8000],
        "suspected_root_cause": suspected_root_cause[:4000],
        "affected_files": affected_files[:64],
        "confidence": confidence,
        "proposed_fix_strategy": proposed_fix_strategy[:4000],
        "should_retry": should_retry,
        "needs_human_review": needs_human_review,
    }
    if rh:
        out["repair_hints"] = rh[:24]
    return out

