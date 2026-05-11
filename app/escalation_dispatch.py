"""Persist escalation prompts and optional clipboard dispatch."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.escalation_models import EscalationMessage

PENDING_CHAT_INJECT_FILENAME = "pending_chat_inject.json"


def escalations_dir(settings) -> Path:
    d = Path(settings.user_data_dir) / "escalations"
    d.mkdir(parents=True, exist_ok=True)
    return d


def pending_chat_inject_path(settings) -> Path:
    return escalations_dir(settings) / PENDING_CHAT_INJECT_FILENAME


def write_pending_cursor_chat_inject(settings, handoff_markdown: str, *, source_md_path: str = "") -> Path | None:
    """Queue text for the Cursor ``stop`` hook (followup_message). Returns path or None if disabled."""
    if not getattr(settings, "escalation_cursor_inject_enabled", True):
        return None
    text = (handoff_markdown or "").strip()
    if not text:
        return None
    max_c = int(getattr(settings, "escalation_cursor_inject_max_chars", 12000) or 12000)
    if len(text) > max_c:
        note = f"\n\n[Truncated to {max_c} chars — full handoff: {source_md_path or 'see data/user/escalations/*.md'}]\n"
        text = text[: max_c - len(note)] + note
    payload = {
        "version": 1,
        "handoff_markdown": text,
        "source_md_path": source_md_path,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ttl_seconds": 86400,
    }
    path = pending_chat_inject_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return path


def clear_pending_cursor_chat_inject(settings) -> bool:
    path = pending_chat_inject_path(settings)
    if path.is_file():
        path.unlink()
        return True
    return False


def peek_pending_handoff_markdown(settings) -> str | None:
    """Return queued handoff text without consuming the pending file."""
    path = pending_chat_inject_path(settings)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        t = str(data.get("handoff_markdown") or "").strip()
        return t or None
    except (json.JSONDecodeError, OSError):
        return None


def read_pending_cursor_chat_inject_status(settings) -> dict[str, Any]:
    path = pending_chat_inject_path(settings)
    if not path.is_file():
        return {"pending": False, "path": str(path.resolve())}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"pending": True, "path": str(path.resolve()), "error": "invalid_json"}
    text = str(data.get("handoff_markdown") or "")
    return {
        "pending": True,
        "path": str(path.resolve()),
        "created_at": data.get("created_at"),
        "preview": text[:280] + ("…" if len(text) > 280 else ""),
        "chars": len(text),
    }


def save_escalation_markdown(
    settings,
    message: EscalationMessage,
    *,
    task_id: str,
    trigger: str,
) -> Path:
    """Write markdown file; returns path."""
    root = escalations_dir(settings)
    safe_tid = "".join(c if c.isalnum() or c in "-_" else "-" for c in task_id)[:80]
    stamp = message.created_at.replace(":", "").replace("+", "plus")
    fn = f"escalation-{safe_tid}-{stamp}.md"
    path = root / fn
    meta = (
        "---\n"
        f'task_id: "{task_id}"\n'
        f'trigger: "{trigger[:400].replace(chr(34), chr(39))}"\n'
        f"urgency: {message.urgency}\n"
        f'failure_type: "{message.failure_type}"\n'
        f"created_at: {message.created_at}\n"
        "---\n\n"
    )
    body = message.handoff_prompt + "\n\n---\n\n## Structured fields (machine-readable)\n\n```json\n"
    body += __import__("json").dumps(message.to_dict(), indent=2, ensure_ascii=True)[:120000]
    body += "\n```\n"
    path.write_text(meta + body, encoding="utf-8")
    return path


def dispatch_escalation_modes(
    settings,
    message: EscalationMessage,
    written_path: Path,
    modes: list[str] | None,
) -> dict[str, Any]:
    """Run optional clipboard / webhook / desktop stubs."""
    raw_modes = modes or ["file"]
    if isinstance(raw_modes, str):
        raw_modes = [m.strip() for m in raw_modes.split(",") if m.strip()]
    out: dict[str, Any] = {"file": str(written_path.resolve())}
    for mode in raw_modes:
        m = mode.strip().lower()
        if m == "file":
            continue
        if m == "clipboard":
            out["clipboard"] = _try_clipboard(message.handoff_prompt)
        elif m == "webhook":
            out["webhook"] = {"status": "not_configured", "hint": "Reserved for future POST endpoint."}
        elif m == "desktop_notification":
            out["desktop_notification"] = {"status": "not_configured", "hint": "Reserved for OS notifications."}
        else:
            out.setdefault("unknown_modes", []).append(mode)
    return out


def _try_clipboard(text: str) -> dict[str, Any]:
    try:
        import pyperclip  # type: ignore

        pyperclip.copy(text)
        return {"ok": True, "via": "pyperclip"}
    except Exception:
        pass
    try:
        import tkinter as tk  # noqa: PLC0415

        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()
        r.destroy()
        return {"ok": True, "via": "tkinter"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def trigger_hash(trigger: str) -> str:
    return hashlib.sha256((trigger or "").encode()).hexdigest()[:16]
