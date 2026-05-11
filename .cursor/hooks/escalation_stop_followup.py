"""Cursor Composer hook: inject queued Codebot escalation as the next user message.

When Codebot generates an escalation it writes ``data/user/escalations/pending_chat_inject.json``.
On Agent Chat ``stop``, Cursor runs this script; if the payload is valid and fresh, we emit
``followup_message`` so Cursor auto-submits it as your next message in **this** Composer thread.

Requires: Hooks enabled in Cursor; workspace folder is this repo root (so ``data/user/`` resolves);
``python`` on PATH (Windows: ``py -3`` users should edit hooks.json command).

Docs: https://cursor.com/docs/agent/hooks (stop hook → followup_message).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _ttl_ok(payload: dict) -> bool:
    ttl = int(payload.get("ttl_seconds") or 86400)
    created = str(payload.get("created_at") or "")
    try:
        dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - dt).total_seconds()
        return age <= ttl
    except ValueError:
        return True


def main() -> int:
    stdin_raw = sys.stdin.read()
    try:
        json.loads(stdin_raw) if stdin_raw.strip() else {}
    except json.JSONDecodeError:
        pass

    # Prefer repository root relative to this script, not current working directory.
    # Cursor hook cwd can vary based on how the session was started.
    root = Path(__file__).resolve().parents[2]
    env_root = __import__("os").environ.get("CODEBOT_PROJECT_ROOT", "").strip()
    if env_root:
        root = Path(env_root)

    pending = root / "data" / "user" / "escalations" / "pending_chat_inject.json"
    if not pending.is_file():
        sys.stdout.write("{}\n")
        return 0

    try:
        payload = json.loads(pending.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        sys.stdout.write("{}\n")
        return 0

    text = str(payload.get("handoff_markdown") or "").strip()
    if not text or not _ttl_ok(payload):
        try:
            pending.unlink()
        except OSError:
            pass
        sys.stdout.write("{}\n")
        return 0

    sys.stdout.write(json.dumps({"followup_message": text}, ensure_ascii=True))
    sys.stdout.write("\n")
    sys.stdout.flush()
    try:
        pending.unlink()
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
