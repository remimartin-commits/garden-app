"""Subprocess-based runner for Cursor CLI/headless agents."""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class CursorRunResult:
    command: list[str]
    project_path: str
    prompt: str
    stdout: str
    stderr: str
    exit_code: int
    started_at_utc: str
    ended_at_utc: str
    duration_seconds: float
    timed_out: bool
    log_path: str


def resolve_cursor_command(configured: str) -> str:
    """Choose Cursor CLI command from config or PATH."""
    if configured.strip():
        parts = _split_command(configured.strip())
        if not parts:
            raise RuntimeError("CURSOR_CLI_COMMAND is empty after parsing.")
        exe = parts[0]
        # Allow absolute/relative executable paths or PATH-resolved commands.
        if Path(exe).exists() or shutil.which(exe):
            return configured.strip()
        raise RuntimeError(
            f"Configured CURSOR_CLI_COMMAND executable was not found: '{exe}'. "
            "Install Cursor CLI or set CURSOR_CLI_COMMAND to a valid command, "
            "for example 'cursor agent' or 'cursor-agent'."
        )
    # Prefer true headless agent mode when available.
    if shutil.which("cursor-agent"):
        return "cursor-agent"
    if shutil.which("cursor"):
        return "cursor agent"
    raise RuntimeError(
        "Cursor CLI not found. Install Cursor CLI and set CURSOR_CLI_COMMAND "
        "(e.g. 'cursor agent' or 'cursor-agent')."
    )


def _split_command(command: str) -> list[str]:
    return shlex.split(command, posix=False)


def run_cursor_prompt(
    *,
    prompt: str,
    project_path: str,
    command: str,
    timeout_seconds: int,
    logs_dir: Path,
) -> CursorRunResult:
    """Execute Cursor CLI in target project directory and capture outputs."""
    target = Path(project_path).resolve()
    if not target.exists() or not target.is_dir():
        raise ValueError(f"Invalid PROJECT_ROOT: {target}")

    logs_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    started_iso = started.isoformat()
    ts = started.strftime("%Y%m%d-%H%M%S")
    command_parts = _split_command(command)
    if not command_parts:
        raise ValueError("CURSOR_CLI_COMMAND is empty after parsing")

    stdout = ""
    stderr = ""
    timed_out = False
    exit_code = -1
    try:
        proc = subprocess.run(
            command_parts,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            cwd=str(target),
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        exit_code = int(proc.returncode)
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nTimed out after {timeout_seconds} seconds."
        exit_code = 124
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Cursor CLI executable not found: {command_parts[0]}. "
            "Set CURSOR_CLI_COMMAND in .env (e.g. 'cursor agent' or 'cursor-agent')."
        ) from exc

    ended = datetime.now(timezone.utc)
    duration = max(0.0, (ended - started).total_seconds())
    ended_iso = ended.isoformat()
    run_id = f"{ts}-{ended.strftime('%f')}"
    log_path = logs_dir / f"{run_id}.json"
    result = CursorRunResult(
        command=command_parts,
        project_path=str(target),
        prompt=prompt,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        started_at_utc=started_iso,
        ended_at_utc=ended_iso,
        duration_seconds=duration,
        timed_out=timed_out,
        log_path=str(log_path),
    )
    log_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
    return result
