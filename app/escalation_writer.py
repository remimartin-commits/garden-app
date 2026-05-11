"""Generate structured escalation messages (Personality AI / EscalationWriter layer)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.escalation_models import EscalationMessage, Urgency, default_constraints
from app.personality_profiles import EscalationPersonality, PersonalityRegistry


def _truncate(s: str, max_chars: int) -> str:
    t = (s or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 40] + "\n… [truncated]"


def _is_placeholder_excerpt(text: str) -> bool:
    """True when text is empty or only separators (e.g. '---'); do not use as primary failure evidence."""
    t = (text or "").strip()
    if not t:
        return True
    collapsed = "".join(ch for ch in t if ch not in "-| \n\r\t")
    return len(collapsed) < 4


def _extract_failing_command(text: str) -> str:
    """Best-effort: last shell-ish line or pytest invocation from verification output."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    for ln in reversed(lines[-80:]):
        if "pytest" in ln.lower() or "npm" in ln.lower() or ln.startswith(">"):
            return _truncate(ln, 500)
    return ""


def _summarize_attempts(repair_history: list[Any]) -> tuple[list[str], str]:
    lines: list[str] = []
    deltas: list[str] = []
    if not isinstance(repair_history, list):
        return ["(no structured repair history yet)"], "Unknown — no repair history."
    for entry in repair_history[-12:]:
        if not isinstance(entry, dict):
            continue
        n = entry.get("attempt_number")
        delta = str(entry.get("failure_delta") or "?")
        strat = str(entry.get("repair_strategy_snapshot") or entry.get("strategy") or "")[:160]
        score = entry.get("quality_score")
        ok = entry.get("validation_ok")
        deltas.append(delta)
        lines.append(
            f"Attempt {n}: strategy={strat!r} score={score} validation_ok={ok} delta={delta}"
        )
    if not lines:
        return ["(no repair attempts recorded)"], "No multi-attempt repair trail yet."
    joined_deltas = ", ".join(deltas[-5:])
    changed = (
        "Failure signal stayed unchanged across attempts."
        if all(d == "unchanged" for d in deltas[-3:])
        else "Failure signal moved between attempts (see deltas)."
    )
    return lines, changed + f" Recent deltas: {joined_deltas}."


def _schema_summary(schema: dict[str, Any] | None) -> str:
    if not schema or not isinstance(schema, dict):
        return "(schema not loaded)"
    bits: list[str] = []
    ents = schema.get("entities") or []
    if isinstance(ents, list) and ents:
        names = []
        for e in ents[:8]:
            if isinstance(e, dict) and e.get("name"):
                names.append(str(e["name"]))
        if names:
            bits.append("Entities: " + ", ".join(names))
    eps = schema.get("api_endpoints") or []
    if isinstance(eps, list) and eps:
        bits.append(f"{len(eps)} API endpoint(s) in schema.")
    goals = schema.get("goals") or schema.get("summary")
    if isinstance(goals, str) and goals.strip():
        bits.append(_truncate(goals.strip(), 400))
    return "; ".join(bits) if bits else "(empty schema summary)"


def _files_from_diagnosis(diagnosis: dict[str, Any] | None) -> list[str]:
    if not isinstance(diagnosis, dict):
        return []
    raw = diagnosis.get("affected_files") or []
    if isinstance(raw, list):
        return [str(x) for x in raw[:24] if str(x).strip()]
    return []


def _failure_label(diagnosis: dict[str, Any] | None, latest_error_excerpt: str) -> str:
    if isinstance(diagnosis, dict) and diagnosis.get("failure_type"):
        return str(diagnosis["failure_type"])
    low = (latest_error_excerpt or "").lower()
    if "json" in low and ("parse" in low or "expecting" in low):
        return "json_parse_error"
    if "failed" in low or "assertion" in low:
        return "test_failure"
    return "unknown"


def _urgency_for_trigger(trigger: str) -> Urgency:
    t = (trigger or "").lower()
    if any(x in t for x in ("budget", "exhausted", "blocked", "destructive", "timeout")):
        return "high"
    if any(x in t for x in ("unchanged", "low_quality", "twice", "needs_review")):
        return "normal"
    return "low"


def build_handoff_prompt(
    *,
    title: str,
    task_title: str,
    task_description: str,
    expected_behavior: str,
    actual_behavior: str,
    failure: str,
    attempted_lines: list[str],
    what_changed: str,
    likely_files: list[str],
    constraints: list[str],
    next_steps: list[str],
    full_log_paths: list[str],
    profile: EscalationPersonality,
) -> str:
    """Paste-ready prompt for the default / manual Cursor agent."""
    attempts = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(attempted_lines[:12]))
    if not attempts.strip():
        attempts = "1. (No prior autonomous repair attempts recorded for this escalation.)"
    files = ", ".join(likely_files[:16]) if likely_files else "(not inferred — inspect failing tests/traceback)"
    cons = "\n".join(f"- {c}" for c in constraints)
    steps = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(next_steps[:5]))
    logs = "\n".join(full_log_paths[:12]) if full_log_paths else "(see project root and data/user for agent_state)"
    tone = profile.style_instructions[:400]
    return (
        "Hi, I'm the autonomous codebot. I'm blocked and need debugging help.\n\n"
        f"Task:\n{task_title}\n{task_description}\n\n"
        f"Expected:\n{expected_behavior}\n\n"
        f"Actual:\n{actual_behavior}\n\n"
        f"Failure:\n{failure}\n\n"
        f"What I already tried:\n{attempts}\n\n"
        f"What changed:\n{what_changed}\n\n"
        f"Likely files:\n{files}\n\n"
        f"Constraints:\n{cons}\n\n"
        f"Please debug this by:\n{steps}\n\n"
        f"Full logs (paths — not inlined):\n{logs}\n\n"
        f"[Writer profile: {profile.label}; tone notes for the maintainer: {tone}]\n"
        f"[Escalation title: {title}]\n"
    )


def generate_escalation_message(
    *,
    task: dict[str, Any],
    schema: dict[str, Any] | None,
    repair_history: list[Any],
    latest_diagnosis: dict[str, Any] | None,
    latest_error_excerpt: str,
    project_context: str,
    run_logs: str,
    trigger: str = "",
    profile_id: str = "default",
) -> EscalationMessage:
    """Build a structured escalation + paste-ready handoff (deterministic core).

    When OPENAI is configured, callers may optionally post-process elsewhere; this function
    stays deterministic for tests and offline use.
    """
    profile = PersonalityRegistry.get(profile_id)
    title_s = str(task.get("title") or "Current task")
    desc = str(task.get("description") or "").strip()
    tid = str(task.get("id") or "")
    expected_behavior = _schema_summary(schema) if schema else _truncate(str(task.get("description") or ""), 1200)
    verification_hint = str(task.get("verification_notes") or "")[:800]
    agent_ctx = (latest_error_excerpt or "").strip()
    if _is_placeholder_excerpt(agent_ctx):
        agent_ctx = (run_logs or "").strip()
    if _is_placeholder_excerpt(agent_ctx):
        agent_ctx = "(no verification, agent output, or error excerpt was available)"
    actual_behavior = _truncate(
        "Latest verification excerpt:\n"
        + _truncate(verification_hint, 600)
        + "\n\nAgent/stderr context:\n"
        + _truncate(agent_ctx, 900),
        2200,
    )
    excerpt_src = ""
    if isinstance(latest_diagnosis, dict) and latest_diagnosis.get("relevant_error_excerpt"):
        diag_ex = str(latest_diagnosis["relevant_error_excerpt"])
        if not _is_placeholder_excerpt(diag_ex):
            excerpt_src = diag_ex
    if not excerpt_src.strip() or _is_placeholder_excerpt(excerpt_src):
        excerpt_src = (latest_error_excerpt or "").strip() or (run_logs or "").strip()
    if _is_placeholder_excerpt(excerpt_src):
        excerpt_src = agent_ctx if not _is_placeholder_excerpt(agent_ctx) else "(no error excerpt available)"
    key_excerpt = _truncate(excerpt_src, 2500)
    failure_type = _failure_label(latest_diagnosis, excerpt_src)

    attempted, changed_summary = _summarize_attempts(repair_history)
    files_li = _files_from_diagnosis(latest_diagnosis)
    if not files_li and isinstance(latest_diagnosis, dict):
        fc = str(latest_diagnosis.get("failing_command") or "").strip()
        if fc:
            attempted.insert(0, f"Diagnosis failing_command: {fc}")

    suspected = ""
    if isinstance(latest_diagnosis, dict):
        suspected = str(latest_diagnosis.get("suspected_root_cause") or "").strip()
    if not suspected:
        suspected = "Uncertain — evidence incomplete; see excerpt and logs."

    cmd_guess = ""
    if isinstance(latest_diagnosis, dict):
        cmd_guess = str(latest_diagnosis.get("failing_command") or "").strip()
    if not cmd_guess:
        cmd_guess = _extract_failing_command(str(task.get("verification_notes") or ""))

    next_steps: list[str] = []
    if cmd_guess:
        next_steps.append(f"Re-run the failing command to reproduce: `{cmd_guess}`")
    if files_li:
        next_steps.append(f"Inspect and trace: {', '.join(files_li[:4])}")
    else:
        next_steps.append("Open the failing test output above and follow the first traceback frame into app code.")
    next_steps.append("Propose or apply the smallest change that satisfies the task schema and passes verification.")

    hint_steps: list[str] = []
    if isinstance(latest_diagnosis, dict):
        rh = latest_diagnosis.get("repair_hints")
        if isinstance(rh, list):
            hint_steps = [str(x).strip() for x in rh if str(x).strip()]
    merged_steps = hint_steps + next_steps

    constraints = default_constraints()
    summary = (
        f"{title_s} ({tid}) is blocked after autonomous repair quota or guardrail: {_truncate(trigger, 200)}. "
        f"Failure type: {failure_type}. "
        + changed_summary
    )

    raw_paths = []
    pl = Path(project_context)
    if pl.exists():
        raw_paths.append(str(pl.resolve()))
    for token in re.findall(r"[A-Za-z]:[^:\n]+\.(?:log|txt)|(?:[/\\\\][^\s]+\.(?:py|json))", run_logs or ""):
        if len(token) < 260:
            raw_paths.append(token)

    urgency: Urgency = _urgency_for_trigger(trigger)
    requested = (
        "Please diagnose using the failure excerpt, reproduce with the command line if present, "
        "and apply the smallest safe fix aligned with the schema task."
    )

    msg = EscalationMessage(
        title=f"Escalation: {title_s}"[:200],
        urgency=urgency,
        summary=_truncate(summary, 1600),
        current_task=f"{tid}: {title_s}\n{desc}",
        expected_behavior=_truncate(expected_behavior, 2000),
        actual_behavior=actual_behavior,
        failure_type=failure_type,
        key_error_excerpt=key_excerpt,
        files_likely_involved=files_li[:32],
        attempted_fixes=attempted,
        what_changed_between_attempts=_truncate(changed_summary, 1200),
        suspected_root_cause=_truncate(suspected, 1500),
        constraints=constraints,
        requested_help=requested,
        suggested_next_steps=merged_steps[:10],
        raw_context_paths=raw_paths[:24],
        created_at=datetime.now(timezone.utc).isoformat(),
        profile_id=profile.id,
    )
    msg.handoff_prompt = build_handoff_prompt(
        title=msg.title,
        task_title=title_s,
        task_description=desc,
        expected_behavior=msg.expected_behavior,
        actual_behavior=msg.actual_behavior,
        failure=f"{failure_type}: {_truncate(key_excerpt, 700)}",
        attempted_lines=msg.attempted_fixes,
        what_changed=msg.what_changed_between_attempts,
        likely_files=msg.files_likely_involved,
        constraints=constraints,
        next_steps=msg.suggested_next_steps,
        full_log_paths=msg.raw_context_paths,
        profile=profile,
    )
    return msg


def load_schema_dict(schema_path: str | None) -> dict[str, Any] | None:
    if not schema_path:
        return None
    p = Path(schema_path)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None
