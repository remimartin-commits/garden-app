"""Pluggable prompt runners for autonomous loop."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import BadRequestError, OpenAI

from app.config import Settings, effective_autonomous_protected_paths, effective_autonomous_write_file_denylist
from app.cursor_runner import resolve_cursor_command, run_cursor_prompt
from app.patch_executor import execute_patch_plan


@dataclass
class AgentRunResult:
    provider: str
    command: str
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    started_at_utc: str
    ended_at_utc: str
    duration_seconds: float
    log_path: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _write_run_log(logs_dir: Path, prefix: str, payload: dict) -> str:
    logs_dir.mkdir(parents=True, exist_ok=True)
    ts = _utc_now().strftime("%Y%m%d-%H%M%S-%f")
    p = logs_dir / f"{prefix}-{ts}.json"
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(p)


def _looks_like_openai_api_cloud_model(model_name: str) -> bool:
    """Heuristic: names that exist on api.openai.com but not on a typical local Ollama install."""
    n = (model_name or "").strip().lower()
    if not n:
        return False
    if n.startswith("gpt-") or n.startswith("o1") or n.startswith("o3") or n.startswith("chatgpt-"):
        return True
    if n.startswith("claude-"):
        return True
    return False


def resolve_openai_compatible_chat_model(settings: Settings) -> str:
    """Model id for patch_executor, openai runner, and schema alignment when using the chat client.

    - With no OPENAI_CHAT_BASE_URL: use OPENAI_CHAT_MODEL (OpenAI API).
    - With a compatible URL: if OPENAI_CHAT_MODEL looks like a cloud-only name, prefer CHAT_MODEL
      (Ollama tag) unless AUTONOMOUS_OPENAI_COMPATIBLE_MODEL is set.
    """
    explicit = (settings.autonomous_openai_compatible_model or "").strip()
    if explicit:
        return explicit
    base = (settings.openai_chat_base_url or "").strip()
    configured = (settings.openai_chat_model or "").strip() or "gpt-4o-mini"
    if not base:
        return configured
    if _looks_like_openai_api_cloud_model(configured):
        local = (settings.chat_model or "").strip()
        if local:
            return local
    return configured


def _strip_line_comments_outside_strings(text: str) -> str:
    """Remove '//' line comments typical of sloppy model JSON.

    Models often emit ``"pytest ...", // note`` — invalid in JSON.
    Comments are stripped only outside of double-quoted string literals.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    in_string = False
    escape_next = False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if escape_next:
                escape_next = False
            elif ch == "\\":
                escape_next = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] not in "\r\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _parse_json_block(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise ValueError(
            "Model returned an empty body — cannot parse JSON. If OPENAI_CHAT_BASE_URL points to "
            "Ollama or another OpenAI-compatible server, the model name must exist on that server "
            "(cloud names like gpt-5.5 will fail). Set AUTONOMOUS_OPENAI_COMPATIBLE_MODEL to your "
            "local tag, or set OPENAI_CHAT_MODEL to a valid local model id."
        )
    if raw.startswith("```"):
        raw = raw.removeprefix("```json").removeprefix("```").strip()
        if raw.endswith("```"):
            raw = raw[:-3].strip()

    preview = raw[:1200].replace("\r", "")

    def _try_load(candidate: str) -> dict[str, Any] | None:
        c = _strip_line_comments_outside_strings(candidate.strip())
        if not c:
            return None
        try:
            data = json.loads(c)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            decoder = json.JSONDecoder()
            idx = c.find("{")
            while idx >= 0:
                try:
                    obj, _end = decoder.raw_decode(c[idx:])
                    if isinstance(obj, dict):
                        return obj
                except json.JSONDecodeError:
                    pass
                idx = c.find("{", idx + 1)
            return None

    for candidate in (raw, raw[raw.find("{") :] if "{" in raw else raw):
        parsed = _try_load(candidate)
        if parsed is not None:
            return parsed

    raise ValueError(
        "Model output is not valid JSON (could not parse a JSON object). Raw preview (first 1200 chars):\n"
        + preview
    )


_project_context_cache: dict[str, tuple[float, str]] = {}
_PROJECT_CONTEXT_TTL_SEC = 90.0


def _project_context(project_root: Path, settings: Settings | None = None) -> str:
    """List project files for patch prompts; cached briefly to avoid repeated rglob scans."""
    domain = getattr(settings, "autonomous_workspace_domain", "generic") if settings else "generic"
    key = f"{project_root.resolve()}|{domain}"
    now = time.monotonic()
    hit = _project_context_cache.get(key)
    if hit is not None and (now - hit[0]) <= _PROJECT_CONTEXT_TTL_SEC:
        return hit[1]
    files: list[str] = []
    for p in project_root.rglob("*"):
        if p.is_file():
            rel = str(p.relative_to(project_root)).replace("\\", "/")
            if ".venv" in rel or rel.startswith(".git"):
                continue
            files.append(rel)
        if len(files) >= 120:
            break
    text = "\n".join(f"- {f}" for f in files)
    _project_context_cache[key] = (now, text)
    return text


def run_with_cursor(
    *,
    settings: Settings,
    prompt: str,
    project_root: str,
    logs_dir: Path,
) -> AgentRunResult:
    cmd = resolve_cursor_command(settings.cursor_cli_command)
    r = run_cursor_prompt(
        prompt=prompt,
        project_path=project_root,
        command=cmd,
        timeout_seconds=settings.cursor_run_timeout_seconds,
        logs_dir=logs_dir,
    )
    return AgentRunResult(
        provider="cursor",
        command=" ".join(r.command),
        stdout=r.stdout,
        stderr=r.stderr,
        exit_code=r.exit_code,
        timed_out=r.timed_out,
        started_at_utc=r.started_at_utc,
        ended_at_utc=r.ended_at_utc,
        duration_seconds=r.duration_seconds,
        log_path=r.log_path,
    )


def _openai_chat_client(settings: Settings) -> OpenAI:
    api_key = (settings.openai_chat_api_key or settings.openai_api_key or "").strip()
    base_url = (settings.openai_chat_base_url or "").strip().rstrip("/")
    timeout = float(settings.openai_chat_request_timeout_seconds)
    if base_url:
        return OpenAI(api_key=api_key or "ollama", base_url=base_url, timeout=timeout)
    return OpenAI(api_key=api_key, timeout=timeout)


def run_with_openai(
    *,
    settings: Settings,
    prompt: str,
    logs_dir: Path,
) -> AgentRunResult:
    api_key = (settings.openai_chat_api_key or settings.openai_api_key or "").strip()
    base_url = (settings.openai_chat_base_url or "").strip()
    if not api_key and not base_url:
        raise RuntimeError("OpenAI API key or OPENAI_CHAT_BASE_URL is required for autonomous_runner=openai.")
    client = _openai_chat_client(settings)
    model_id = resolve_openai_compatible_chat_model(settings)
    started = _utc_now()
    completion = client.chat.completions.create(
        model=model_id,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a coding agent operating in a local repo. "
                    "Return concise implementation summary, patch plan, and test results."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    out = completion.choices[0].message.content or ""
    ended = _utc_now()
    result = AgentRunResult(
        provider="openai",
        command=f"openai:{model_id}",
        stdout=out,
        stderr="",
        exit_code=0,
        timed_out=False,
        started_at_utc=started.isoformat(),
        ended_at_utc=ended.isoformat(),
        duration_seconds=max(0.0, (ended - started).total_seconds()),
        log_path="",
    )
    payload = asdict(result) | {"prompt": prompt}
    result.log_path = _write_run_log(logs_dir, "openai-run", payload)
    return result


def run_with_patch_executor(
    *,
    settings: Settings,
    prompt: str,
    project_root: str,
    logs_dir: Path,
) -> AgentRunResult:
    api_key = (settings.openai_chat_api_key or settings.openai_api_key or "").strip()
    base_url = (settings.openai_chat_base_url or "").strip()
    if not api_key and not base_url:
        raise RuntimeError("OpenAI API key or OPENAI_CHAT_BASE_URL is required for patch_executor runner.")
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise RuntimeError(f"Invalid PROJECT_ROOT: {root}")
    client = _openai_chat_client(settings)
    model_id = resolve_openai_compatible_chat_model(settings)
    started = _utc_now()
    plan_prompt = (
        "Return strict JSON only with keys: summary, edits, commands.\n"
        "edits is an array of objects with action in [write_file, append_file, replace_in_file].\n"
        "Each edit requires path. write/append require content. replace requires old/new.\n"
        "commands is an array of safe non-destructive command strings ONLY (no trailing notes).\n"
        "Standard JSON ONLY: never use // or /* */ comments, and never trailing commas.\n"
        "Do NOT include delete operations, git reset, force push, or .env edits.\n\n"
        "JSON ESCAPING (critical — invalid JSON is rejected):\n"
        '- For write_file/append_file, every "content" value must be a valid JSON string: '
        'use \\n for newlines and \\" for quotes inside that string.\n'
        "- Prefer replace_in_file or append_file on existing Python files over embedding large JSON "
        "documents inside \"content\".\n"
        "- Never use write_file on core modules (app/entities.py, app/main.py, app/config.py, …); "
        "the executor blocks full replace there — use replace_in_file / append_file.\n"
        "- Avoid inventing parallel schema JSON files unless unavoidable; prefer editing app/entities.py "
        "and similar modules.\n"
        "- If multiple files change, use several smaller edits rather than one huge escaped string.\n\n"
        "Tests and entity models (mandatory):\n"
        "- Any test under tests/ that references a model class (e.g. BusinessProfile) must include an "
        "explicit import such as `from app.entities import BusinessProfile` near the top (after any "
        "`from __future__` line). Never leave tests using bare class names without imports.\n"
        "- In app/entities.py there must be at most one `class <Name>` per entity name. To extend a "
        "model, edit the existing class with replace_in_file — never append a second `class "
        "BusinessProfile` (duplicates break imports and tests).\n"
        "- write_file on app/entities.py is blocked; use replace_in_file or append_file only.\n\n"
        f"PROJECT FILES (partial):\n{_project_context(root, settings)}\n\n"
        f"TASK:\n{prompt}\n"
    )
    sys_msg = (
        "You are a strict JSON patch planner. Output exactly one parseable JSON object (RFC 8259). "
        "No markdown fences, no commentary outside the object. "
        "Respect test imports and single-class-per-name rules for app/entities.py."
    )
    chat_kw: dict[str, Any] = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": plan_prompt},
        ],
        "max_completion_tokens": 16384,
    }
    # Official OpenAI API can enforce JSON mode; many OpenAI-compatible servers do not support it.
    if not base_url:
        try:
            completion = client.chat.completions.create(
                **chat_kw, response_format={"type": "json_object"}
            )
        except BadRequestError:
            completion = client.chat.completions.create(**chat_kw)
    else:
        try:
            completion = client.chat.completions.create(**chat_kw)
        except BadRequestError:
            chat_kw.pop("max_completion_tokens", None)
            completion = client.chat.completions.create(
                model=model_id,
                messages=chat_kw["messages"],
            )
    model_out = completion.choices[0].message.content or "{}"
    plan = _parse_json_block(model_out)
    protected_paths = effective_autonomous_protected_paths(settings, root)
    write_deny = effective_autonomous_write_file_denylist(settings)
    exec_result = execute_patch_plan(
        project_root=root,
        plan=plan,
        command_timeout_seconds=settings.cursor_run_timeout_seconds,
        protected_paths=protected_paths,
        write_file_denylist=write_deny,
    )
    ended = _utc_now()
    stdout = (
        f"summary: {exec_result.summary}\n"
        f"applied_edits: {exec_result.applied_edits}\n"
        f"command_logs:\n" + "\n\n".join(exec_result.command_logs)
    ).strip()
    stderr = "\n".join(exec_result.errors).strip()
    exit_code = 0 if not exec_result.errors else 2
    result = AgentRunResult(
        provider="patch_executor",
        command=(
            f"{'openai-compatible' if base_url else 'openai'}:"
            f"{model_id} -> local_patch_executor"
        ),
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        timed_out=False,
        started_at_utc=started.isoformat(),
        ended_at_utc=ended.isoformat(),
        duration_seconds=max(0.0, (ended - started).total_seconds()),
        log_path="",
    )
    payload = {
        "prompt": prompt,
        "plan": plan,
        "execution": {
            "summary": exec_result.summary,
            "applied_edits": exec_result.applied_edits,
            "command_logs": exec_result.command_logs,
            "errors": exec_result.errors,
        },
        "result": asdict(result),
    }
    result.log_path = _write_run_log(logs_dir, "patch-executor-run", payload)
    return result
