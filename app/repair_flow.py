"""Orchestration helpers: targeted reads, envelope text, history records."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import re

from app.repair_extract import compact_evidence_for_model, merge_evidence, normalize_excerpt
from app.repair_llm import fallback_minimal_prompt_block
from app.repair_quality import (
    RepairPlanStrict,
    anti_cheat_flags,
    classify_failure_delta,
    normalize_for_compare,
    score_repair_plan,
)


def ensure_task_repair_fields(task: dict[str, Any]) -> None:
    task.setdefault("repair_history", [])
    task.setdefault("repair_unchanged_streak", 0)
    task.setdefault("repair_low_quality_streak", 0)
    task.setdefault("last_normalized_error_excerpt", "")


def load_targeted_sources(
    project_root: Path,
    diagnosis: dict[str, Any],
    *,
    extra_relative_paths: list[str] | None = None,
    max_chars_per_file: int = 12000,
) -> str:
    """Load only likely-relevant files for repair (best-effort)."""
    parts: list[str] = []
    seen: set[str] = set()
    ordered_paths: list[str] = list(diagnosis.get("affected_files") or [])
    for raw in extra_relative_paths or []:
        r = str(raw).strip().replace("\\", "/")
        if r and r not in ordered_paths:
            ordered_paths.insert(0, r)
    for raw in ordered_paths:
        rel = str(raw).strip().replace("\\", "/").lstrip("./")
        if not rel or rel in seen:
            continue
        seen.add(rel)
        p = project_root / rel
        if p.is_file():
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
                parts.append(f"### File: {rel}\n```\n{txt[:max_chars_per_file]}\n```")
            except OSError:
                continue
        if len(parts) >= 6:
            break

    return "\n\n".join(parts) if parts else "(no targeted files resolved from diagnosis paths)"


def merge_verification_commands(
    planner_cmds: list[str],
    focused_relative_tests: list[str],
    *,
    max_paths: int = 8,
) -> list[str]:
    """Prepend a single focused pytest invocation when we have marker-related test paths."""
    out: list[str] = []
    seen: set[str] = set()
    rels: list[str] = []
    for p in focused_relative_tests:
        r = str(p).strip().replace("\\", "/").lstrip("./")
        if r and r not in rels:
            rels.append(r)
        if len(rels) >= max_paths:
            break
    if rels:
        focused = "python -m pytest -q --tb=line " + " ".join(rels)
        out.append(focused)
        seen.add(focused)
    for c in planner_cmds:
        s = str(c).strip()
        if not s or s in seen:
            continue
        out.append(s)
        seen.add(s)
    return out


def prior_attempts_digest(task: dict[str, Any], limit: int = 6) -> str:
    hist = task.get("repair_history") or []
    if not isinstance(hist, list) or not hist:
        return "(none)"
    lines: list[str] = []
    for entry in hist[-limit:]:
        if not isinstance(entry, dict):
            continue
        strat = entry.get("repair_strategy_snapshot") or entry.get("strategy") or ""
        delta = entry.get("failure_delta") or ""
        score = entry.get("quality_score")
        lines.append(
            f"- attempt {entry.get('attempt_number')}: delta={delta} score={score} strategy={str(strat)[:120]}"
        )
    return "\n".join(lines) if lines else "(none)"


def build_repair_envelope_text(
    *,
    diagnosis: dict[str, Any],
    plan: RepairPlanStrict | None,
    targeted_sources: str,
    prior_digest: str,
    anti_flags: list[str],
    strategy_name: str,
    use_fallback_only: bool,
    failure_excerpt: str,
    protected_relative_paths: list[str] | None = None,
    task_title: str = "",
    system_adjustment_notes: list[str] | None = None,
) -> str:
    diag_json = json.dumps(diagnosis, indent=2, ensure_ascii=True)[:12000]
    plan_json = ""
    if plan:
        plan_json = plan.model_dump_json(indent=2)[:12000]

    guard = (
        "\n## Anti-cheating guardrails\n"
        "- Do NOT delete or skip tests; do NOT weaken assertions to pass.\n"
        "- Do NOT edit .env / secrets; avoid broad refactors.\n"
        "- Prefer minimal edits to implementation to satisfy tests/task schema.\n"
    )
    if anti_flags:
        guard += f"- Flags raised by automated scan: {', '.join(anti_flags)}\n"

    ftype = str(diagnosis.get("failure_type") or "")
    json_phase2 = ""
    if ftype == "json_parse_error":
        json_phase2 = (
            "\n## Phase 2 JSON (patch_executor) — mandatory shape\n"
            "- Emit exactly ONE JSON object with keys: summary, edits, commands.\n"
            "- Standard JSON only: no // or /* */ comments, no trailing commas, no markdown fences.\n"
            "- commands must be an array of executable shell strings only (no inline notes after strings).\n"
        )

    prot = ""
    pr = list(protected_relative_paths or [])
    if pr:
        lines = "\n".join(f"- {p}" for p in pr[:40])
        prot = (
            "\n## Repository paths blocked for this run (do not patch or reference in commands)\n"
            + lines
            + "\n- If the task names a type that would normally live in a blocked file, add a **new** module "
            "under app/ (allowed) and wire imports from code that is safe to edit.\n"
            "- Match patterns already used in targeted sources (e.g. dataclasses, Pydantic) — do not invent "
            "fictional helper modules.\n"
        )
    title_l = (task_title or "").lower()
    if pr and ("inquiry" in title_l or "entity" in title_l) and any(
        "entities.py" in x.replace("\\", "/") for x in pr
    ):
        prot += (
            "- Inquiry/entity tasks: if ``app/entities.py`` is blocked, implement under a new file such as "
            "`app/inquiry_entity.py` or extend an existing allowed module, then re-export or import from "
            "routes/tests as the project already does.\n"
        )

    adj = ""
    notes = list(system_adjustment_notes or [])
    if notes:
        adj = "\n## System adjustments to the LLM repair plan\n" + "\n".join(f"- {n}" for n in notes) + "\n"

    playbook = ""
    raw_hints = diagnosis.get("repair_hints")
    if isinstance(raw_hints, list) and raw_hints:
        lines = "\n".join(f"- {str(h).strip()}" for h in raw_hints if str(h).strip())
        if lines:
            playbook = (
                "\n## Failure-specific playbook (from diagnostics — apply when signals match)\n"
                f"{lines}\n"
            )

    test_first = ""
    if diagnosis.get("failure_type") == "test_failure":
        test_first = (
            "\n## Test-first repair\n"
            "Infer intended behavior from the failing tests and targeted test files first; "
            "then adjust implementation only.\n"
        )

    block = (
        "\n\n## Structured diagnosis (mandatory context)\n"
        f"{diag_json}\n"
        "\n## Approved repair plan (JSON)\n"
        f"{plan_json or '(planner unavailable — follow diagnosis only)'}\n"
        f"{json_phase2}"
        f"{prot}"
        f"{adj}"
        f"{playbook}"
        f"{test_first}"
        "\n## Targeted sources (read before editing)\n"
        f"{targeted_sources}\n"
        "\n## Prior repair attempts (do not repeat failed strategies)\n"
        f"{prior_digest}\n"
        f"{guard}"
        "\n## Execution instructions\n"
        "Phase 1 is complete (diagnosis + plan). Phase 2: emit STRICT JSON patch plan for "
        "patch_executor with keys summary, edits, commands — edits must implement the plan above.\n"
        f"_Repair strategy hint_: {strategy_name}\n"
    )
    if use_fallback_only:
        block += fallback_minimal_prompt_block(failure_excerpt)
    return block


def append_repair_history(
    task: dict[str, Any],
    *,
    attempt_number: int,
    diagnosis: dict[str, Any],
    plan: RepairPlanStrict | None,
    patch_summary: str,
    files_modified_guess: list[str],
    validation_ok: bool | None,
    excerpt_after: str,
    failure_delta: str,
    quality_score: int | None,
    strategy: str,
) -> None:
    ensure_task_repair_fields(task)
    hist = task["repair_history"]
    if not isinstance(hist, list):
        hist = []
        task["repair_history"] = hist
    hist.append(
        {
            "attempt_number": attempt_number,
            "diagnosis": diagnosis,
            "repair_plan": plan.model_dump() if plan else None,
            "patch_summary": patch_summary[:4000],
            "files_modified": files_modified_guess[:32],
            "validation_result": "pass" if validation_ok else ("fail" if validation_ok is False else "unknown"),
            "error_excerpt_after_attempt": normalize_excerpt(excerpt_after, 4000),
            "failure_delta": failure_delta,
            "quality_score": quality_score,
            "repair_strategy_snapshot": strategy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


def normalized_failure_blob(state: dict[str, Any]) -> str:
    return normalize_for_compare(
        "\n".join(
            [
                str(state.get("last_error", "")),
                str(state.get("last_verification_output", "")),
            ]
        )
    )


def extract_patch_files_from_stdout(stdout: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(r"(?:append_file|write_file|replace_in_file):([^\s]+)", stdout):
        out.append(m.group(1).strip())
    return list(dict.fromkeys(out))[:40]
