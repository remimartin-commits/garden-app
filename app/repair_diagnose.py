"""Build RepairDiagnosis from evidence and state."""

from __future__ import annotations

import re
from typing import Any

from app.repair_extract import merge_evidence, normalize_excerpt
from app.repair_models import diagnosis_dict, FailureType
from app.repair_playbook_lessons import collect_lesson_hints


_PYTEST_COLLECTION_MARKERS = (
    "error collecting",
    "errors during collection",
    "import error while loading",
    "!!!!!!!!!!! interrupted:",
)


def _repair_playbook_hints(last_error: str, verification: str, agent_out: str) -> list[str]:
    """Deterministic hints appended to diagnosis / repair envelope / escalation."""
    blob = f"{last_error}\n{verification}\n{agent_out}"
    return collect_lesson_hints(blob, max_hints=12)


def _classify_type(
    last_error: str, verification: str, agent_out: str
) -> FailureType:
    combined = f"{last_error}\n{verification}\n{agent_out}"
    t = combined.lower()
    ver_lower = (verification or "").lower()

    # Pytest collection/import failures must win over loose JSON-parse heuristics
    # (patch_executor JSON errors often linger in last_error while verification updates).
    if any(m in ver_lower for m in _PYTEST_COLLECTION_MARKERS):
        return "test_failure"

    if "permission" in t or "access denied" in t or "eacces" in t:
        return "permission_error"
    if "modulenotfound" in t or "cannot find module" in t or "no module named" in t:
        return "missing_dependency"
    if "npm err" in t or "build failed" in t or "typescript" in t and "error ts" in t:
        if "npm run build" in t or "build" in last_error.lower():
            return "build_failure"

    # Schema contract: feature_schema and tests call model_json_schema() on entities.
    if "model_json_schema" in combined and (
        "attributeerror" in t or "has no attribute" in t
    ):
        return "test_failure"

    planner_blob = f"{last_error}\n{agent_out}".lower()
    if (
        "expecting value" in planner_blob
        or "jsondecode" in planner_blob
        or "not valid json" in planner_blob
    ):
        return "json_parse_error"

    if "failed" in verification.lower() or "error" in verification.lower():
        if "collecting" in verification or "pytest" in verification:
            return "test_failure"
    if "traceback" in t or "error:" in verification.lower():
        return "runtime_error"
    if "aligned" in t or "alignment" in last_error.lower():
        return "schema_alignment_failure"
    return "unknown"


def build_diagnosis(
    *,
    last_error: str,
    verification_output: str,
    agent_output: str,
    strategy_name: str,
) -> dict[str, Any]:
    evidence = merge_evidence(verification_output, last_error, agent_output)
    py = evidence.get("pytest") or {}
    failing_tests = py.get("failing_tests") or []
    files = list(py.get("file_refs") or [])
    if evidence.get("traceback", {}).get("last_file_line"):
        files.append(str(evidence["traceback"]["last_file_line"]).split(":")[0])

    excerpt_parts = []
    if py.get("short_summary"):
        excerpt_parts.append(str(py["short_summary"])[:2500])
    if evidence.get("json"):
        excerpt_parts.append(str(evidence["json"].get("message", "")))
    excerpt_parts.append(normalize_excerpt(last_error, 1200))
    relevant = "\n---\n".join(excerpt_parts)[:6000]

    ftype = _classify_type(last_error, verification_output, agent_output)
    hints = _repair_playbook_hints(last_error, verification_output, agent_output)
    evidence_blob = f"{last_error}\n{verification_output}\n{agent_output}"

    cause = "See excerpt."
    if ftype == "json_parse_error":
        cause = "Patch planner or tool returned non-JSON or empty body; fix model output or constraints."
    elif ftype == "test_failure":
        cause = "One or more tests failed; align implementation with failing assertions."
    elif ftype == "build_failure":
        cause = "Build or compile step failed; fix types or imports."
    elif hints and "model_json_schema" in evidence_blob:
        cause = (
            "Import/schema contract break: a type no longer exposes model_json_schema() "
            "(common after swapping Pydantic models for dataclasses)."
        )

    conf: Any = "medium"
    if ftype == "unknown":
        conf = "low"
    if failing_tests or files:
        conf = "high"

    needs_human = ftype in ("permission_error", "schema_alignment_failure") and "skipped" not in last_error.lower()

    return diagnosis_dict(
        failure_type=ftype,
        failing_command=str(evidence.get("failing_command_guess") or "pytest / npm / patch_executor"),
        exit_code=_guess_exit_code(verification_output, last_error),
        relevant_error_excerpt=relevant,
        suspected_root_cause=cause,
        affected_files=list(dict.fromkeys([f for f in files if f]))[:32],
        confidence=conf,
        proposed_fix_strategy=strategy_name,
        should_retry=ftype != "permission_error",
        needs_human_review=bool(needs_human),
        repair_hints=hints or None,
    )


def _guess_exit_code(verification: str, last_error: str) -> str | int | None:
    for line in (verification + "\n" + last_error).splitlines():
        m = re.search(r"exit_code[=:]?\s*(\d+)", line, re.I)
        if m:
            return int(m.group(1))
    return None

