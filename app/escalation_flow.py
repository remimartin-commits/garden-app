"""Orchestration: escalation recording, resolution, resume-after-manual-fix."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings
from app.escalation_dispatch import (
    dispatch_escalation_modes,
    save_escalation_markdown,
    trigger_hash,
    write_pending_cursor_chat_inject,
)
from app.escalation_models import EscalationResolution
from app.escalation_writer import generate_escalation_message, load_schema_dict
from app.repair_flow import ensure_task_repair_fields, normalized_failure_blob


def ensure_global_escalation_fields(state: dict[str, Any]) -> None:
    state.setdefault("total_escalations", 0)
    state.setdefault("active_escalation", "")  # task id when blocked + escalation generated
    state.setdefault("last_escalation_path", "")
    state.setdefault("last_escalation_summary", "")
    state.setdefault("last_escalation_event", "")


def ensure_task_escalation_fields(task: dict[str, Any]) -> None:
    ensure_task_repair_fields(task)
    task.setdefault("escalation_status", "none")
    task.setdefault("escalation_count", 0)
    task.setdefault("latest_escalation_path", "")
    task.setdefault("latest_escalation_summary", "")
    task.setdefault("last_escalated_at", "")
    task.setdefault("last_escalation_trigger", "")
    task.setdefault("escalation_trigger_flags", [])
    task.setdefault("escalation_resolution", None)
    task.setdefault("escalation_failure_signature_at_generation", "")
    task.setdefault("last_escalation_trigger_hash", "")


def hydrate_escalation_state(state: dict[str, Any]) -> None:
    ensure_global_escalation_fields(state)
    for t in state.get("tasks") or []:
        if isinstance(t, dict):
            ensure_task_escalation_fields(t)


def _escalation_text_is_placeholder(text: str) -> bool:
    """True when excerpt/logs are empty or only separators (e.g. '---') so escalation should fall back."""
    t = (text or "").strip()
    if not t:
        return True
    collapsed = "".join(ch for ch in t if ch not in "-| \n\r\t")
    return len(collapsed) < 4


def _task_index_by_id(state: dict[str, Any], task_id: str) -> int | None:
    for i, t in enumerate(state.get("tasks") or []):
        if isinstance(t, dict) and str(t.get("id")) == str(task_id):
            return i
    return None


def _debounced(task: dict[str, Any], trigger: str, *, force: bool, debounce_seconds: float = 45.0) -> bool:
    """Return True if we should skip duplicate escalation."""
    if force:
        return False
    th = trigger_hash(trigger)
    if str(task.get("last_escalation_trigger_hash") or "") != th:
        return False
    last = str(task.get("last_escalated_at") or "").strip()
    if not last:
        return False
    try:
        prev = datetime.fromisoformat(last.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = (now - prev.replace(tzinfo=timezone.utc)).total_seconds()
        return delta < debounce_seconds
    except ValueError:
        return False


def record_escalation_for_task(
    settings: Settings,
    state: dict[str, Any],
    task_idx: int,
    trigger: str,
    *,
    force: bool = False,
    profile_id: str | None = None,
) -> dict[str, Any] | None:
    """Generate file, update task + global counters. Returns payload or None if skipped."""
    hydrate_escalation_state(state)
    tasks = state.get("tasks") or []
    if task_idx < 0 or task_idx >= len(tasks):
        return None
    task = tasks[task_idx]
    if not isinstance(task, dict):
        return None
    ensure_task_escalation_fields(task)

    if _debounced(task, trigger, force=force):
        return None

    schema_raw = load_schema_dict(str(state.get("schema_path") or ""))
    schema_for_writer: dict[str, Any] | None = None
    if isinstance(schema_raw, dict):
        inner = schema_raw.get("schema")
        schema_for_writer = inner if isinstance(inner, dict) else schema_raw
    rh = task.get("repair_history") if isinstance(task.get("repair_history"), list) else []
    diag = task.get("latest_diagnosis") if isinstance(task.get("latest_diagnosis"), dict) else {}
    excerpt = ""
    if diag.get("relevant_error_excerpt"):
        excerpt = str(diag["relevant_error_excerpt"])
    else:
        excerpt = str(state.get("last_error") or "")[:8000]

    project_root = Path(str(state.get("project_root") or settings.project_root)).resolve()
    project_context = str(project_root)
    run_logs = "\n".join(
        [
            str(state.get("last_verification_output", ""))[-6000:],
            str(state.get("last_cursor_output", ""))[-4000:],
        ]
    ).strip()
    if _escalation_text_is_placeholder(run_logs):
        run_logs = (
            "(No verification or agent output was captured in agent_state.)\n"
            f"status={state.get('status')} runner={state.get('runner')} "
            f"paused={state.get('paused')} last_updated_utc={state.get('last_updated_utc')}\n"
            f"global last_error: {str(state.get('last_error') or '(empty)')[:3000]}\n"
            f"project_root: {project_root}\n"
            f"task id={task.get('id')} task_status={task.get('status')} attempts={task.get('attempts')}\n"
        )
    excerpt = excerpt.strip()
    if _escalation_text_is_placeholder(excerpt):
        excerpt = run_logs[:8000]

    pid = profile_id or getattr(settings, "escalation_profile", None) or "default"
    msg = generate_escalation_message(
        task=task,
        schema=schema_for_writer,
        repair_history=rh,
        latest_diagnosis=diag,
        latest_error_excerpt=excerpt,
        project_context=project_context,
        run_logs=run_logs,
        trigger=trigger,
        profile_id=str(pid),
    )

    path = save_escalation_markdown(settings, msg, task_id=str(task.get("id") or ""), trigger=trigger)
    sig_at_gen = normalized_failure_blob(state)
    raw_md = getattr(settings, "escalation_dispatch_modes", None)
    if raw_md is None:
        raw_md = "file"
    if isinstance(raw_md, str):
        mode_list = [x.strip() for x in str(raw_md).split(",") if x.strip()]
    else:
        mode_list = list(raw_md)
    if not mode_list:
        mode_list = ["file"]
    dispatch = dispatch_escalation_modes(settings, msg, path, mode_list)
    inject_path = write_pending_cursor_chat_inject(
        settings,
        msg.handoff_prompt,
        source_md_path=str(path.resolve()),
    )
    dispatch["cursor_chat_inject"] = (
        {"queued": True, "path": str(inject_path.resolve())}
        if inject_path
        else {"queued": False, "path": ""}
    )

    task["escalation_status"] = "generated"
    task["escalation_count"] = int(task.get("escalation_count") or 0) + 1
    task["latest_escalation_path"] = str(path.resolve())
    task["latest_escalation_summary"] = msg.summary[:1200]
    task["last_escalated_at"] = msg.created_at
    task["last_escalation_trigger"] = trigger[:500]
    task["last_escalation_trigger_hash"] = trigger_hash(trigger)
    task["escalation_failure_signature_at_generation"] = sig_at_gen[:8000]

    state["total_escalations"] = int(state.get("total_escalations") or 0) + 1
    state["active_escalation"] = str(task.get("id") or "")
    state["last_escalation_path"] = str(path.resolve())
    state["last_escalation_summary"] = msg.summary[:1200]
    ev = f"Escalation generated ({trigger[:160]}) → {path.name}"
    if inject_path:
        ev += " | Cursor chat inject queued (submits after Composer agent stops — needs .cursor/hooks)."
    state["last_escalation_event"] = ev

    tasks[task_idx] = task
    state["tasks"] = tasks

    return {
        "ok": True,
        "path": str(path.resolve()),
        "summary": msg.summary,
        "urgency": msg.urgency,
        "dispatch": dispatch,
        "message": msg.to_dict(),
    }


def maybe_flag_trigger_once(task: dict[str, Any], flag: str) -> bool:
    """Return True if this is the first time `flag` is set for this task."""
    ensure_task_escalation_fields(task)
    flags = list(task.get("escalation_trigger_flags") or [])
    if flag in flags:
        return False
    flags.append(flag)
    task["escalation_trigger_flags"] = flags
    return True


def mark_escalation_resolved(
    settings: Settings,
    task_id: str,
    *,
    resolved_by: str = "user",
    resolution_summary: str = "",
    verification_result: str = "",
) -> dict[str, Any]:
    from app.autonomous_loop import load_agent_state, save_agent_state  # noqa: PLC0415

    state = load_agent_state(settings)
    hydrate_escalation_state(state)
    idx = _task_index_by_id(state, task_id)
    if idx is None:
        raise ValueError(f"Unknown task id: {task_id}")
    task = state["tasks"][idx]
    ensure_task_escalation_fields(task)
    rb = resolved_by if resolved_by in ("manual_agent", "user", "autonomous_retry") else "user"
    task["escalation_status"] = "resolved"
    task["escalation_resolution"] = EscalationResolution(
        resolved_by=rb,
        resolution_summary=resolution_summary or "Marked resolved manually.",
        verification_result=verification_result or "",
    ).to_dict()
    state["tasks"][idx] = task
    if str(state.get("active_escalation")) == str(task_id):
        state["active_escalation"] = ""
    save_agent_state(settings, state)
    return state


def resume_after_manual_fix(settings: Settings, task_id: str) -> dict[str, Any]:
    """Re-run verification; compare to signature at escalation; update resolution notes."""
    from app.autonomous_loop import (  # noqa: PLC0415 — avoid circular import at module load
        load_agent_state,
        run_project_verification,
        save_agent_state,
        _state_project_root,
    )

    state = load_agent_state(settings)
    hydrate_escalation_state(state)
    idx = _task_index_by_id(state, task_id)
    if idx is None:
        raise ValueError(f"Unknown task id: {task_id}")
    task = state["tasks"][idx]
    ensure_task_escalation_fields(task)

    prev_sig = str(task.get("escalation_failure_signature_at_generation") or "")
    project_root = Path(_state_project_root(settings, state)).resolve()

    verify = run_project_verification(
        project_root,
        task=task,
        run_full_suite=False,
        parallel_workers=settings.autonomous_parallel_workers,
    )
    state["last_verification_output"] = verify.output
    task["verification_notes"] = verify.output

    new_sig = normalized_failure_blob(state)
    sig_changed = bool(prev_sig) and new_sig != prev_sig

    if verify.success:
        task["escalation_status"] = "resolved"
        task["escalation_resolution"] = EscalationResolution(
            resolved_by="manual_agent",
            resolution_summary="Verification passed after manual fix.",
            verification_result=_truncate_out(verify.output, 4000),
        ).to_dict()
        task["status"] = "pending"
        state["status"] = "running"
        state["last_error"] = ""
        state["tests_failed_streak"] = 0
    elif sig_changed:
        task["escalation_resolution"] = EscalationResolution(
            resolved_by="manual_agent",
            resolution_summary="Failure signature changed after manual edits — review new output.",
            verification_result=_truncate_out(verify.output, 4000),
        ).to_dict()
        record_escalation_for_task(
            settings,
            state,
            idx,
            trigger="resume_after_manual_fix_still_failing_or_changed",
            force=True,
        )
    else:
        task["escalation_resolution"] = EscalationResolution(
            resolved_by="manual_agent",
            resolution_summary="Verification still failing; failure signature unchanged.",
            verification_result=_truncate_out(verify.output, 4000),
        ).to_dict()
        record_escalation_for_task(
            settings,
            state,
            idx,
            trigger="resume_after_manual_fix_same_failure",
            force=True,
        )

    state["tasks"][idx] = task
    save_agent_state(settings, state)
    return state


def _truncate_out(text: str, n: int) -> str:
    t = text or ""
    return t if len(t) <= n else t[: n - 30] + "\n… [truncated]"


def manual_generate_escalation(settings: Settings, task_id: str | None = None) -> dict[str, Any]:
    from app.autonomous_loop import load_agent_state, save_agent_state  # noqa: PLC0415

    state = load_agent_state(settings)
    hydrate_escalation_state(state)
    tid = task_id or str(state.get("current_task_id") or "")
    idx = _task_index_by_id(state, tid) if tid else None
    if idx is None:
        idx = 0 if state.get("tasks") else None
    if idx is None:
        raise ValueError("No tasks in state.")
    out = record_escalation_for_task(
        settings,
        state,
        idx,
        trigger="manual_generate_escalation",
        force=True,
    )
    if out:
        save_agent_state(settings, state)
    return out or {"ok": False, "detail": "Escalation skipped"}
