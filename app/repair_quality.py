"""Repair plan scoring, anti-cheating heuristics, failure delta."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.patch_executor import _command_touches_protected, _is_protected_rel_path


class RepairPlanFile(BaseModel):
    path: str
    reason: str = ""
    change_summary: str = ""


class RepairPlanStrict(BaseModel):
    diagnosis_summary: str = ""
    repair_strategy: str = ""
    files_to_modify: list[RepairPlanFile] = Field(default_factory=list)
    commands_to_run_after_patch: list[str] = Field(default_factory=list)
    risk_level: str = "low"
    requires_human_review: bool = False

    @field_validator("risk_level")
    @classmethod
    def risk(cls, v: str) -> str:
        allowed = {"low", "medium", "high"}
        return v if v in allowed else "medium"


def classify_failure_delta(prev_norm: str, next_norm: str) -> str:
    if not prev_norm and not next_norm:
        return "fixed"
    if not next_norm:
        return "fixed"
    if not prev_norm:
        return "changed"
    if prev_norm == next_norm:
        return "unchanged"
    # crude improvement: shorter traceback / fewer FAILED lines
    if next_norm.count("FAILED") < prev_norm.count("FAILED"):
        return "improved"
    if next_norm.count("FAILED") > prev_norm.count("FAILED"):
        return "worsened"
    return "changed"


def excerpt_hash(text: str) -> str:
    return hashlib.sha256(normalize_for_compare(text).encode("utf-8")).hexdigest()[:16]


def normalize_for_compare(text: str) -> str:
    return " ".join((text or "").split()).strip().lower()[:8000]


def filter_protection_violations_from_plan(
    plan: RepairPlanStrict,
    protected_paths: list[str],
) -> tuple[RepairPlanStrict, list[str]]:
    """Drop file targets and shell commands that violate autonomous protected paths."""
    if not protected_paths:
        return plan, []
    removed: list[str] = []
    kept_files: list[RepairPlanFile] = []
    for f in plan.files_to_modify:
        if _is_protected_rel_path(f.path, protected_paths):
            removed.append(f.path)
        else:
            kept_files.append(f)
    kept_cmds: list[str] = []
    for cmd in plan.commands_to_run_after_patch:
        c = str(cmd).strip()
        if not c:
            continue
        if _command_touches_protected(c, protected_paths):
            removed.append(f"(command touches protected path): {c[:120]}")
            continue
        kept_cmds.append(c)
    new_plan = plan.model_copy(
        update={
            "files_to_modify": kept_files,
            "commands_to_run_after_patch": kept_cmds,
        }
    )
    return new_plan, removed


def score_repair_plan(
    plan: RepairPlanStrict,
    *,
    diagnosis_failure_type: str,
    repeated_strategies: list[str],
) -> tuple[int, list[str]]:
    """Return score 0-100 and rejection reasons."""
    reasons: list[str] = []
    score = 55
    if plan.diagnosis_summary.strip():
        score += 10
    if plan.repair_strategy.strip():
        score += 10
    if plan.files_to_modify:
        score += 10
        if len(plan.files_to_modify) <= 3:
            score += 5
        if len(plan.files_to_modify) > 5:
            score -= 25
            reasons.append("too_many_files")
    if plan.commands_to_run_after_patch:
        score += 5
    if plan.risk_level == "low":
        score += 5
    if diagnosis_failure_type == "test_failure" and plan.files_to_modify:
        score += 5
    strat = plan.repair_strategy.lower()
    for rs in repeated_strategies:
        if rs and rs.lower() in strat:
            score -= 20
            reasons.append("repeated_strategy")
    if plan.requires_human_review:
        score -= 15
    return max(0, min(100, score)), reasons


def anti_cheat_flags(
    plan: RepairPlanStrict,
    raw_plan_text: str,
    *,
    protected_paths: list[str] | None = None,
) -> list[str]:
    """Detect discouraged repair patterns (flags only)."""
    flags: list[str] = []
    blob = raw_plan_text.lower() + plan.repair_strategy.lower()
    bad_patterns = [
        (r"\bskip\s+test", "skip_test"),
        (r"delete.*test", "delete_test"),
        (r"remove.*assert", "weaken_assert"),
        (r"pytest\.skip", "pytest_skip"),
        (r"@unittest\.skip", "unittest_skip"),
        (r"except\s+:\s*pass", "bare_except_pass"),
        (r"\.env\b.*write", "env_write"),
    ]
    for pat, name in bad_patterns:
        if re.search(pat, blob):
            flags.append(name)
    for f in plan.files_to_modify:
        p = f.path.lower()
        if "test" in p and any(x in blob for x in ("delete", "remove file", "strip")):
            flags.append("touch_test_file_risk")
    if protected_paths:
        for f in plan.files_to_modify:
            if _is_protected_rel_path(f.path, protected_paths):
                flags.append("targets_protected_path")
        for cmd in plan.commands_to_run_after_patch:
            if _command_touches_protected(str(cmd), protected_paths):
                flags.append("command_touches_protected_path")
    return flags


def parse_repair_plan_json(raw: str) -> RepairPlanStrict | None:
    from app.agent_runner import _strip_line_comments_outside_strings

    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    text = _strip_line_comments_outside_strings(text)
    try:
        import json

        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        return RepairPlanStrict.model_validate(data)
    except Exception:
        return None
