from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.autonomous_loop import (
    background_finish_topic_autonomous_start,
    cleanup_isolated_runs,
    failure_debug_payload,
    fix_blocked_task,
    live_code_payload,
    pause_autonomous,
    resume_autonomous,
    reset_autonomous_state,
    run_next_step,
    run_until_blocked,
    start_autonomous_run,
    start_autonomous_topic_run_deferred,
    status_payload,
)
from app.escalation_flow import (
    manual_generate_escalation,
    mark_escalation_resolved,
    resume_after_manual_fix,
)
from app.config import get_settings
from app.escalation_dispatch import (
    clear_pending_cursor_chat_inject,
    peek_pending_handoff_markdown,
    read_pending_cursor_chat_inject_status,
)


router = APIRouter(prefix="/autonomy", tags=["autonomy"])


class AutonomyStartRequest(BaseModel):
    topic: str | None = None
    schema_path: str | None = None


class AutonomyRunUntilBlockedRequest(BaseModel):
    max_iterations: int | None = None


class EscalationTaskBody(BaseModel):
    task_id: str | None = None


@router.get("/status")
def autonomy_status() -> dict[str, Any]:
    return status_payload(get_settings())


@router.get("/live-code")
def autonomy_live_code() -> dict[str, Any]:
    """Latest agent / verification / prompt text for a terminal-style progress view."""
    return live_code_payload(get_settings())


@router.post("/open-output")
def autonomy_open_output() -> dict[str, Any]:
    st = status_payload(get_settings())
    project_root = Path(str(st.get("project_root", "")).strip()).resolve()
    if not project_root.exists():
        raise HTTPException(status_code=404, detail=f"Output path not found: {project_root}")
    try:
        if os.name == "nt":
            os.startfile(str(project_root))  # type: ignore[attr-defined]
        elif os.name == "posix":
            subprocess.Popen(["xdg-open", str(project_root)])
        else:
            subprocess.Popen(["open", str(project_root)])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to open output folder: {exc}") from exc
    return {"ok": True, "project_root": str(project_root)}


@router.get("/debug-failure")
def autonomy_debug_failure() -> dict[str, Any]:
    return failure_debug_payload(get_settings())


@router.post("/cleanup-runs")
def autonomy_cleanup_runs() -> dict[str, Any]:
    return cleanup_isolated_runs(get_settings())


@router.post("/start")
def autonomy_start(
    req: AutonomyStartRequest, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    settings = get_settings()
    topic = (req.topic or "").strip() or None
    try:
        if topic:
            out = start_autonomous_topic_run_deferred(settings, topic)
            background_tasks.add_task(background_finish_topic_autonomous_start, topic)
            return out
        return start_autonomous_run(
            settings=settings,
            topic=None,
            schema_path=req.schema_path,
        )
    except ValueError as exc:
        msg = str(exc)
        if "already bound to a topic" in msg:
            raise HTTPException(
                status_code=409,
                detail=msg + " Use POST /autonomy/reset or the dashboard «Reset» button.",
            ) from exc
        raise HTTPException(status_code=400, detail=msg) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/run-next")
def autonomy_run_next() -> dict[str, Any]:
    try:
        return run_next_step(get_settings())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/run-until-blocked")
def autonomy_run_until_blocked(req: AutonomyRunUntilBlockedRequest) -> dict[str, Any]:
    try:
        return run_until_blocked(get_settings(), max_iterations=req.max_iterations)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/fix-blocked")
def autonomy_fix_blocked() -> dict[str, Any]:
    try:
        return fix_blocked_task(get_settings())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/pause")
def autonomy_pause() -> dict[str, Any]:
    return pause_autonomous(get_settings())


@router.post("/stop")
def autonomy_stop() -> dict[str, Any]:
    """Pause autonomous loop; surface queued escalation + full handoff for clipboard fallback.

    Note: this HTTP handler does **not** fire Cursor's Composer ``stop`` hook — only ending an
    Agent turn inside Cursor does. When ``pending_handoff_markdown`` is present, the dashboard
    copies it to the clipboard so you can paste here immediately.
    """
    settings = get_settings()
    state = pause_autonomous(settings)
    pending = read_pending_cursor_chat_inject_status(settings)
    state["pending_chat_inject"] = pending
    state["pending_handoff_markdown"] = peek_pending_handoff_markdown(settings)
    state["composer_escalation_hint"] = (
        "Escalation is queued. This button cannot post into Composer — either paste from clipboard "
        "(copied automatically when handoff exists) or click Stop inside the Cursor Agent chat "
        "to trigger the hook."
        if pending.get("pending")
        else (
            "Autonomy paused. No Composer escalation queued right now "
            "(nothing in pending_chat_inject.json)."
        )
    )
    return state


@router.post("/resume")
def autonomy_resume() -> dict[str, Any]:
    return resume_autonomous(get_settings())


@router.post("/reset")
def autonomy_reset() -> dict[str, Any]:
    return reset_autonomous_state(get_settings())


@router.post("/escalation/generate")
def autonomy_escalation_generate(req: EscalationTaskBody) -> dict[str, Any]:
    """Generate an escalation file for the current or specified task (manual trigger)."""
    try:
        return manual_generate_escalation(get_settings(), req.task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/escalation/mark-resolved")
def autonomy_escalation_mark_resolved(req: EscalationTaskBody) -> dict[str, Any]:
    if not req.task_id:
        raise HTTPException(status_code=400, detail="task_id is required")
    try:
        return mark_escalation_resolved(get_settings(), req.task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/escalation/resume-manual-fix")
def autonomy_escalation_resume_manual_fix(req: EscalationTaskBody) -> dict[str, Any]:
    if not req.task_id:
        raise HTTPException(status_code=400, detail="task_id is required")
    try:
        return resume_after_manual_fix(get_settings(), req.task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/escalation/handoff-text")
def autonomy_escalation_handoff_text() -> dict[str, Any]:
    """Return latest escalation markdown (full file) for copy/paste."""
    st = status_payload(get_settings())
    insp = st.get("escalation_inspector") or {}
    p = insp.get("latest_escalation_path") or st.get("last_escalation_path")
    if not p:
        return {"text": "", "path": "", "ok": False}
    path = Path(str(p))
    if path.is_file():
        return {"text": path.read_text(encoding="utf-8"), "path": str(path.resolve()), "ok": True}
    return {"text": "", "path": str(p), "ok": False, "detail": "path not found"}


@router.get("/escalation/pending-chat-inject")
def autonomy_escalation_pending_chat_inject() -> dict[str, Any]:
    """Whether an escalation is queued for Cursor ``stop`` hook injection."""
    return read_pending_cursor_chat_inject_status(get_settings())


@router.post("/escalation/clear-pending-chat-inject")
def autonomy_escalation_clear_pending_chat_inject() -> dict[str, Any]:
    ok = clear_pending_cursor_chat_inject(get_settings())
    return {"ok": True, "cleared": ok}
