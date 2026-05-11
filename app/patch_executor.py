"""Safe patch-plan executor for autonomous code changes."""

from __future__ import annotations

import shlex
import subprocess
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DESTRUCTIVE_PATTERNS = (
    "rm -rf",
    "rmdir /s",
    "del /s",
    "git reset --hard",
    "git clean -fd",
    "git push --force",
    "format c:",
    "mkfs",
)


@dataclass
class PatchExecutionResult:
    summary: str
    applied_edits: list[str]
    command_logs: list[str]
    errors: list[str]


def _resolve_inside_root(project_root: Path, rel_path: str) -> Path:
    p = (project_root / rel_path).resolve()
    root = project_root.resolve()
    if p != root and root not in p.parents:
        raise ValueError(f"path escapes PROJECT_ROOT: {rel_path}")
    return p


def _is_destructive_command(command: str) -> bool:
    c = command.lower()
    return any(p in c for p in DESTRUCTIVE_PATTERNS)


def _normalize_rel(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./").lower()


def _is_protected_rel_path(rel_path: str, protected_paths: list[str]) -> bool:
    target = _normalize_rel(rel_path)
    for protected in protected_paths:
        p = _normalize_rel(protected)
        if not p:
            continue
        if target == p or target.startswith(p + "/"):
            return True
    return False


def _command_touches_protected(command: str, protected_paths: list[str]) -> bool:
    c = command.lower().replace("\\", "/")
    return any(_normalize_rel(p) in c for p in protected_paths if _normalize_rel(p))


def _apply_edit(
    project_root: Path,
    edit: dict[str, Any],
    protected_paths: list[str],
    write_file_denylist: list[str],
) -> str:
    action = str(edit.get("action", "")).strip()
    rel_path = str(edit.get("path", "")).strip()
    if not action or not rel_path:
        raise ValueError("each edit requires action and path")
    if _is_protected_rel_path(rel_path, protected_paths):
        raise ValueError(f"blocked edit to protected path: {rel_path}")
    target = _resolve_inside_root(project_root, rel_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    if action == "write_file":
        if _is_protected_rel_path(rel_path, write_file_denylist):
            raise ValueError(
                f"blocked write_file on {rel_path}: full-file replace is not allowed for this path; "
                "use replace_in_file or append_file for surgical edits."
            )
        content = str(edit.get("content", ""))
        target.write_text(content, encoding="utf-8")
        return f"write_file:{rel_path}"
    if action == "append_file":
        content = str(edit.get("content", ""))
        before = target.read_text(encoding="utf-8") if target.exists() else ""
        target.write_text(before + content, encoding="utf-8")
        return f"append_file:{rel_path}"
    if action == "replace_in_file":
        old = str(edit.get("old", ""))
        new = str(edit.get("new", ""))
        if not target.exists():
            raise ValueError(f"replace_in_file target missing: {rel_path}")
        text = target.read_text(encoding="utf-8")
        if old not in text:
            raise ValueError(f"replace target not found in {rel_path}")
        target.write_text(text.replace(old, new, 1), encoding="utf-8")
        return f"replace_in_file:{rel_path}"

    raise ValueError(f"unsupported edit action: {action}")


def _run_command(
    project_root: Path,
    command: str,
    timeout_seconds: int,
    protected_paths: list[str],
) -> str:
    if _is_destructive_command(command):
        raise ValueError(
            f"destructive command requires human approval and was blocked: {command}"
        )
    if _command_touches_protected(command, protected_paths):
        raise ValueError(
            f"blocked command referencing protected path: {command}"
        )
    args = shlex.split(command, posix=False)
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(project_root)
        if not existing
        else str(project_root) + os.pathsep + existing
    )
    proc = subprocess.run(
        args,
        cwd=str(project_root),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        env=env,
    )
    return (
        f"$ {command}\nexit_code={proc.returncode}\n"
        f"[stdout]\n{proc.stdout}\n[stderr]\n{proc.stderr}"
    )


def _is_parallel_safe_command(command: str) -> bool:
    """Conservatively allow read-mostly verification commands in parallel."""
    c = command.strip().lower()
    if not c:
        return False
    parallel_prefixes = (
        "pytest",
        "python -m pytest",
        "npm test",
        "npm run test",
        "npm run build",
        "pnpm test",
        "pnpm run test",
        "pnpm run build",
        "yarn test",
        "yarn build",
    )
    return any(c.startswith(prefix) for prefix in parallel_prefixes)


def execute_patch_plan(
    *,
    project_root: Path,
    plan: dict[str, Any],
    command_timeout_seconds: int,
    protected_paths: list[str] | None = None,
    write_file_denylist: list[str] | None = None,
) -> PatchExecutionResult:
    edits = plan.get("edits", [])
    commands = plan.get("commands", [])
    summary = str(plan.get("summary", "")).strip()

    applied_edits: list[str] = []
    command_logs: list[str] = []
    errors: list[str] = []
    protected = protected_paths or []
    deny_write = write_file_denylist or []

    if isinstance(edits, list):
        for edit in edits:
            try:
                if isinstance(edit, dict):
                    applied_edits.append(_apply_edit(project_root, edit, protected, deny_write))
                else:
                    errors.append("invalid edit item (must be object)")
            except Exception as exc:
                errors.append(str(exc))

    if isinstance(commands, list):
        parsed_commands: list[str] = []
        for cmd in commands:
            command = str(cmd).strip()
            if command:
                parsed_commands.append(command)

        i = 0
        while i < len(parsed_commands):
            command = parsed_commands[i]
            if not _is_parallel_safe_command(command):
                try:
                    command_logs.append(
                        _run_command(project_root, command, command_timeout_seconds, protected)
                    )
                except Exception as exc:
                    errors.append(str(exc))
                i += 1
                continue

            batch: list[tuple[int, str]] = []
            j = i
            while j < len(parsed_commands) and _is_parallel_safe_command(parsed_commands[j]):
                batch.append((j, parsed_commands[j]))
                j += 1

            if len(batch) == 1:
                try:
                    command_logs.append(
                        _run_command(project_root, batch[0][1], command_timeout_seconds, protected)
                    )
                except Exception as exc:
                    errors.append(str(exc))
                i = j
                continue

            batch_results: list[tuple[int, str, str | None]] = []
            max_workers = min(4, len(batch))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {
                    executor.submit(
                        _run_command, project_root, command_text, command_timeout_seconds, protected
                    ): (index, command_text)
                    for index, command_text in batch
                }
                for future in as_completed(future_map):
                    index, command_text = future_map[future]
                    try:
                        batch_results.append((index, future.result(), None))
                    except Exception as exc:
                        batch_results.append((index, "", f"{command_text}: {exc}"))

            for _, log, err in sorted(batch_results, key=lambda x: x[0]):
                if err:
                    errors.append(err)
                elif log:
                    command_logs.append(log)

            i = j

    return PatchExecutionResult(
        summary=summary,
        applied_edits=applied_edits,
        command_logs=command_logs,
        errors=errors,
    )
