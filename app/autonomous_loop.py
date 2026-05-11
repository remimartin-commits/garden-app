"""Autonomous schema loop that runs Cursor CLI + verification + alignment."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from app.config import Settings, effective_autonomous_protected_paths
from app.escalation_dispatch import read_pending_cursor_chat_inject_status
from app.escalation_flow import (
    hydrate_escalation_state,
    maybe_flag_trigger_once,
    record_escalation_for_task,
)
from app.cursor_runner import resolve_cursor_command
from app.agent_runner import (
    AgentRunResult,
    resolve_openai_compatible_chat_model,
    run_with_cursor,
    run_with_openai,
    run_with_patch_executor,
)
from app.feature_schema import (
    align_feature_loop_with_autonomous_task,
    evaluate_and_advance_feature_loop,
    generate_next_cursor_prompts,
    generate_and_store_feature_schema,
    reset_feature_loop_state,
)
from app.repair_diagnose import build_diagnosis
from app.repair_extract import compact_evidence_for_model, merge_evidence
from app.repair_playbook_lessons import collect_lesson_hints
from app.repair_flow import (
    append_repair_history,
    build_repair_envelope_text,
    ensure_task_repair_fields,
    extract_patch_files_from_stdout,
    load_targeted_sources,
    merge_verification_commands,
    normalized_failure_blob,
    prior_attempts_digest,
)
from app.repair_llm import request_repair_plan_json
from app.repair_quality import (
    RepairPlanStrict,
    anti_cheat_flags,
    classify_failure_delta,
    filter_protection_violations_from_plan,
    score_repair_plan,
)

logger = logging.getLogger(__name__)

BLOCK_PHRASES = [
    "i cannot",
    "manual step required",
    "permission denied",
    "merge conflict",
    "cannot access",
]
CLI_UNSUPPORTED_PHRASES = [
    "run with 'cursor -' to read output from another program",
    "reading from stdin via:",
]
DESTRUCTIVE_HINTS = [
    "rm -rf",
    "git reset --hard",
    "git push --force",
    "del /s",
    "rmdir /s",
    ".env",
]

# Taught to autofix for alignment-vs-task drift (schema loop vs Execution anchor).
SCHEMA_LOOP_DRIFT_TIP = (
    "If alignment complains the work targeted the wrong entity or step: follow ONLY the Execution anchor "
    "(current task id/title/description) and ignore conflicting lines in the generated schema-loop prompt. "
    "Fix import-time errors in shared modules first (e.g. broken Pydantic models in app/entities) so tests load."
)


def _looks_like_alignment_step_mismatch(text: str) -> bool:
    """True when notes suggest implementing the wrong step/entity vs what was asked."""
    t = (text or "").lower()
    if not t.strip():
        return False
    if any(
        s in t
        for s in (
            "not aligned with the requested",
            "step was to implement",
            "requested schema step",
            "output summary and edits focus",
            "while the requested",
            "focused on implementing",
        )
    ):
        return True
    if ("not aligned" in t or "alignment failed" in t) and (
        "entity" in t and any(x in t for x in ("focus", "instead", "while the", "but the output", "but the"))
    ):
        return True
    return False


# Substrings matched against a normalized "Entity: FooBar" name → pytest stems in tests/
_ENTITY_NAME_MARKERS: list[tuple[str, list[str]]] = [
    # Must precede generic "profile" match — "businessprofile" contains "profile" as substring.
    ("businessprofile", ["test_entities"]),
    ("servicearea", ["test_service_area_entity", "test_service_areas_api"]),
    ("service_area", ["test_service_area_entity", "test_service_areas_api"]),
    ("faq", ["test_faq_entity"]),
    ("testimonial", ["test_testimonial_entity"]),
    ("quoteenquir", ["test_quote_enquiries", "test_quote_enquiries_api", "test_quote_enquiry_entity"]),
    ("inquir", ["test_quote_enquiries", "test_quote_enquiries_api", "test_quote_enquiry_entity"]),
    ("project", ["test_project_entity", "test_projects_api", "test_project_detail_endpoint"]),
    ("service", ["test_service_entity", "test_services_api", "test_service_detail_api"]),
    ("page", ["test_page_entity", "test_page_content_api"]),
    # Website / CMS-style entities often exercise page + content contracts
    ("theme", ["test_page_entity", "test_page_content_api"]),
    ("website", ["test_page_entity", "test_page_content_api"]),
    ("profile", ["test_page_entity", "test_project_entity"]),
    ("gallery", ["test_page_entity", "test_page_content_api"]),
    ("settings", ["test_page_entity", "test_page_content_api"]),
]


@dataclass
class VerificationResult:
    checks_run: list[str]
    output: str
    success: bool
    failures: list[str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso_utc(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _recover_stale_running_state(state: dict[str, Any], *, stale_seconds: int = 900) -> bool:
    """Reset obviously stale 'running' markers (e.g. crashed worker before first output).

    Must NOT run on read-only status polling: while ``run_next_step`` is in flight, another
    request could otherwise think the step is stale (``last_updated_utc`` is not heartbeat-updated
    during long agent runs) and repeatedly cancel work.
    Only clears tasks that never produced cursor output or verification notes.
    """
    if str(state.get("status", "")).lower() != "running":
        return False
    updated_at = _parse_iso_utc(str(state.get("last_updated_utc", "")))
    if not updated_at:
        return False
    age = (datetime.now(timezone.utc) - updated_at).total_seconds()
    if age < stale_seconds:
        return False
    tasks = state.get("tasks", [])
    changed = False
    for task in tasks:
        if str(task.get("status", "")).lower() != "running":
            continue
        attempts = int(task.get("attempts", 0) or 0)
        has_output = bool(str(task.get("last_cursor_output", "")).strip())
        has_verify = bool(str(task.get("verification_notes", "")).strip())
        if attempts <= 0 and not (has_output or has_verify):
            task["status"] = "pending"
            changed = True
    if changed and not any(str(t.get("status", "")).lower() == "running" for t in tasks):
        state["current_task_id"] = ""
        state["status"] = "blocked"
        state["tests_failed_streak"] = 0
        state["last_error"] = (
            "Recovered stale running state automatically; task was reset to pending for retry."
        )
    return changed


def _recover_stale_patch_executor_running_on_status(
    settings: Settings,
    state: dict[str, Any],
) -> bool:
    """Conservative stale recovery for patch_executor on read-only status polls.

    patch_executor can sit inside a single LLM HTTP call for a long time (especially on
    OpenAI-compatible local servers) without updating ``last_updated_utc``. That phase is
    not bounded by ``cursor_run_timeout_seconds`` (which applies to post-plan shell commands).
    We therefore use ``patch_executor_stale_step_seconds`` (default 1 hour) before treating
    the run as dead and moving tasks to needs_review.
    """
    if str(state.get("status", "")).lower() != "running":
        return False
    if bool(state.get("paused")):
        return False
    runner = str(state.get("runner") or settings.autonomous_runner).lower()
    if runner not in {"patch_executor", "openai"}:
        return False
    updated_at = _parse_iso_utc(str(state.get("last_updated_utc", "")))
    if not updated_at:
        return False
    # LLM phase can exceed cursor_run_timeout_seconds; use a dedicated wall-clock bound.
    stale_seconds = max(int(settings.patch_executor_stale_step_seconds), 300)
    age = (datetime.now(timezone.utc) - updated_at).total_seconds()
    if age < stale_seconds:
        return False

    tasks = state.get("tasks") or []
    changed = False
    first_running_id = ""
    for task in tasks:
        if not isinstance(task, dict):
            continue
        if str(task.get("status", "")).lower() != "running":
            continue
        if not first_running_id:
            first_running_id = str(task.get("id", ""))
        task["status"] = "needs_review"
        changed = True
    if not changed:
        return False

    state["status"] = "blocked"
    state["tests_failed_streak"] = 0
    if first_running_id:
        state["current_task_id"] = first_running_id
    prev_err = str(state.get("last_error", "")).strip()
    msg = (
        "Recovered stale running state automatically during status poll; "
        "runner exceeded expected timeout without state progress "
        f"(threshold {stale_seconds}s, setting patch_executor_stale_step_seconds)."
    )
    state["last_error"] = (prev_err + " " + msg).strip() if prev_err else msg
    return True


def _agent_state_path(settings: Settings) -> Path:
    settings.user_data_dir.mkdir(parents=True, exist_ok=True)
    return settings.user_data_dir / "agent_state.json"


def _cursor_runs_dir(settings: Settings) -> Path:
    p = settings.user_data_dir / "cursor_runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else default
    except Exception:
        return default


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _project_root(settings: Settings) -> Path:
    root = settings.project_root.resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Invalid PROJECT_ROOT: {root}")
    return root


def _state_project_root(settings: Settings, state: dict[str, Any]) -> Path:
    raw = str(state.get("project_root", "")).strip()
    root = Path(raw).resolve() if raw else settings.project_root.resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Invalid project root in state: {root}")
    return root


def _slugify_topic(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return cleaned[:24] or "autonomous-run"


def _create_isolated_run_workspace(settings: Settings, source_root: Path, label: str) -> Path:
    runs_dir = settings.autonomous_runs_dir.resolve()
    runs_dir.mkdir(parents=True, exist_ok=True)
    _cleanup_old_isolated_runs(settings, runs_dir)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short_hash = hashlib.sha1((label or "run").encode("utf-8")).hexdigest()[:8]
    run_dir = runs_dir / f"{_slugify_topic(label)}-{short_hash}-{ts}"

    def _ignore(src: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        src_path = Path(src)
        try:
            rel = src_path.resolve().relative_to(source_root.resolve()).as_posix()
        except Exception:
            rel = ""
        if rel in {"", "."}:
            for n in [".git", ".venv", ".pytest_cache", "__pycache__", ".chroma", "outputs"]:
                if n in names:
                    ignored.add(n)
        if rel == "data" and "user" in names:
            # user history can contain very long filenames; regenerate in isolated run.
            ignored.add("user")
        return ignored

    try:
        shutil.copytree(source_root, run_dir, ignore=_ignore)
    except Exception as exc:
        raise RuntimeError(f"Unable to create isolated run workspace at {run_dir}: {exc}") from exc
    return run_dir


def _cleanup_old_isolated_runs(settings: Settings, runs_dir: Path) -> None:
    """Prune old autogenerated run folders, preserving newest N."""
    if not settings.autonomous_cleanup_runs_on_start:
        return
    keep = max(1, int(settings.autonomous_run_retention))
    if not runs_dir.exists():
        return
    auto_pattern = re.compile(r".*-\d{8}-\d{6}$")
    candidates: list[Path] = []
    for item in runs_dir.iterdir():
        if not item.is_dir():
            continue
        if not auto_pattern.match(item.name):
            # Preserve manually named folders (e.g., curated snapshots).
            continue
        candidates.append(item)
    if len(candidates) <= keep:
        return
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for old in candidates[keep:]:
        try:
            shutil.rmtree(old, ignore_errors=False)
        except Exception:
            # Ignore cleanup failures; run creation should still proceed.
            continue


def cleanup_isolated_runs(settings: Settings) -> dict[str, Any]:
    """Prune old autogenerated run folders immediately and report what remains."""
    runs_dir = settings.autonomous_runs_dir.resolve()
    runs_dir.mkdir(parents=True, exist_ok=True)
    keep = max(1, int(settings.autonomous_run_retention))
    auto_pattern = re.compile(r".*-\d{8}-\d{6}$")
    candidates = [item for item in runs_dir.iterdir() if item.is_dir() and auto_pattern.match(item.name)]
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    deleted: list[str] = []
    for old in candidates[keep:]:
        try:
            shutil.rmtree(old, ignore_errors=False)
            deleted.append(old.name)
        except Exception:
            continue
    remaining = [item.name for item in runs_dir.iterdir() if item.is_dir()]
    remaining.sort()
    return {
        "ok": True,
        "runs_dir": str(runs_dir),
        "retention": keep,
        "deleted": deleted,
        "remaining": remaining,
    }


def _build_tasks_from_schema(schema_path: str) -> list[dict[str, Any]]:
    raw = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    schema = raw.get("schema", {})
    items: list[dict[str, Any]] = []
    idx = 1
    for entity in schema.get("entities", []) or []:
        name = (entity or {}).get("name", f"entity-{idx}")
        items.append(
            {
                "id": f"task-{idx}",
                "title": f"Entity: {name}",
                "description": f"Implement entity {name} and required fields.",
                "status": "pending",
                "last_prompt": "",
                "last_cursor_output": "",
                "verification_notes": "",
                "attempts": 0,
            }
        )
        idx += 1
    for endpoint in schema.get("api_endpoints", []) or []:
        method = (endpoint or {}).get("method", "GET")
        path = (endpoint or {}).get("path", "/")
        items.append(
            {
                "id": f"task-{idx}",
                "title": f"Endpoint: {method} {path}",
                "description": (endpoint or {}).get("purpose", "Implement endpoint behavior."),
                "status": "pending",
                "last_prompt": "",
                "last_cursor_output": "",
                "verification_notes": "",
                "attempts": 0,
            }
        )
        idx += 1
    for criterion in schema.get("acceptance_criteria", []) or []:
        if isinstance(criterion, str) and criterion.strip():
            items.append(
                {
                    "id": f"task-{idx}",
                    "title": f"Acceptance: {criterion[:80]}",
                    "description": criterion,
                    "status": "pending",
                    "last_prompt": "",
                    "last_cursor_output": "",
                    "verification_notes": "",
                    "attempts": 0,
                }
            )
            idx += 1
    if not items:
        items.append(
            {
                "id": "task-1",
                "title": "Initial vertical slice",
                "description": "Implement minimal feature behavior from schema summary/goals.",
                "status": "pending",
                "last_prompt": "",
                "last_cursor_output": "",
                "verification_notes": "",
                "attempts": 0,
            }
        )
    return items


def _new_state(settings: Settings) -> dict[str, Any]:
    return {
        "status": "idle",
        "paused": False,
        "schema_path": "",
        "project_root": str(settings.project_root.resolve()),
        "cursor_cli_command": "",
        "runner": settings.autonomous_runner,
        "current_task_id": "",
        "tasks": [],
        "last_cursor_output": "",
        "last_verification_output": "",
        "tests_failed_streak": 0,
        "last_error": "",
        "last_updated_utc": _utc_now(),
        "total_escalations": 0,
        "active_escalation": "",
        "last_escalation_path": "",
        "last_escalation_summary": "",
        "last_escalation_event": "",
        "locked_run_topic": "",
        "locked_run_schema_sha256": "",
    }


def load_agent_state(settings: Settings) -> dict[str, Any]:
    state = _load_json(_agent_state_path(settings), _new_state(settings))
    state.setdefault("locked_run_topic", "")
    state.setdefault("locked_run_schema_sha256", "")
    hydrate_escalation_state(state)
    return state


def save_agent_state(settings: Settings, state: dict[str, Any]) -> None:
    state["last_updated_utc"] = _utc_now()
    _save_json(_agent_state_path(settings), state)


def _contains_phrase(text: str, phrases: list[str]) -> bool:
    t = (text or "").lower()
    return any(p in t for p in phrases)


def _set_task_status(state: dict[str, Any], task_index: int, status: str) -> None:
    if 0 <= task_index < len(state.get("tasks", [])):
        state["tasks"][task_index]["status"] = status


def _active_task_index(state: dict[str, Any], step_index: int) -> int:
    tasks = state.get("tasks", [])
    if not tasks:
        return 0
    idx = min(step_index, max(0, len(tasks) - 1))
    # If schema loop state lags, avoid re-running already completed tasks.
    if str(tasks[idx].get("status", "")).lower() == "complete":
        for i, task in enumerate(tasks):
            if str(task.get("status", "")).lower() != "complete":
                return i
    return idx


def _next_incomplete_task_index(state: dict[str, Any]) -> int | None:
    for i, task in enumerate(state.get("tasks", [])):
        if str(task.get("status", "")).lower() != "complete":
            return i
    return None


def _next_runnable_task_index(state: dict[str, Any]) -> int | None:
    """Next task eligible for an automatic step (skip complete and needs_review)."""
    for i, task in enumerate(state.get("tasks", [])):
        if not isinstance(task, dict):
            continue
        s = str(task.get("status", "pending") or "pending").lower()
        if s in ("complete", "needs_review"):
            continue
        return i
    return None


def _all_tasks_complete(state: dict[str, Any]) -> bool:
    tasks = state.get("tasks") or []
    if not tasks:
        return True
    return all(
        isinstance(t, dict) and str(t.get("status", "")).lower() == "complete" for t in tasks
    )


def autonomous_run_topic_lock_active(state: dict[str, Any]) -> bool:
    """True while a feature schema run is in flight; blocks starting another topic/schema."""
    if str(state.get("status", "")).lower() == "starting":
        return True
    sp = str(state.get("schema_path") or "").strip()
    if not sp:
        return False
    tasks = state.get("tasks") or []
    if not tasks:
        return True
    st = str(state.get("status") or "").lower()
    if st == "complete" and _all_tasks_complete(state):
        return False
    return True


def _assert_locked_schema_unchanged(state: dict[str, Any]) -> None:
    """Refuse to continue if the on-disk schema bytes changed since run start."""
    expected = str(state.get("locked_run_schema_sha256") or "").strip()
    if not expected:
        return
    raw = str(state.get("schema_path") or "").strip()
    if not raw:
        raise ValueError("Locked run is missing schema_path.")
    path = Path(raw).expanduser()
    if not path.is_file():
        raise ValueError(f"Locked feature schema file is missing: {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(
            "The feature schema file for this run changed on disk since the run started. "
            "Refusing to continue so the agent cannot drift to a different spec. "
            "Use POST /autonomy/reset to start over, or restore the original schema file."
        )


def _run_topic_lock_prompt_addon(state: dict[str, Any]) -> str:
    """Prompt text that keeps the agent on the started topic and schema."""
    topic = str(state.get("locked_run_topic") or "").strip()
    schema_ref = str(state.get("schema_path") or "").strip()
    if not schema_ref:
        return ""
    lines = [
        "\n\nTopic lock (mandatory):",
        f"- This autonomous run is bound to feature schema file: `{schema_ref}`.",
        "- Implement ONLY work justified by that schema and its current task list.",
        "- Do not pivot to unrelated products, APIs, or features not implied by this schema.",
        "- Ignore any loop boilerplate or examples that contradict this schema file.",
    ]
    if topic:
        lines.insert(2, f"- Original topic / charter: {topic}")
    return "\n".join(lines)


def _repair_focus_task_index(state: dict[str, Any]) -> int | None:
    """Task index for repair_mode (may still be needs_review)."""
    tasks = state.get("tasks") or []
    tid = str(state.get("current_task_id") or "")
    if tid:
        for i, t in enumerate(tasks):
            if isinstance(t, dict) and str(t.get("id")) == tid:
                return i
    for i, t in enumerate(tasks):
        if isinstance(t, dict) and str(t.get("status", "")).lower() == "needs_review":
            return i
    return None


def _focused_pytest_targets(project_root: Path, task: dict[str, Any] | None) -> list[str]:
    if not task:
        return []
    markers = _task_related_test_markers(task)
    if not markers:
        return []
    tests_dir = project_root / "tests"
    if not tests_dir.is_dir():
        return []
    targets: list[str] = []
    for marker in markers:
        candidate = tests_dir / f"{marker}.py"
        if candidate.is_file():
            targets.append(str(candidate.relative_to(project_root)).replace("\\", "/"))
    deduped: list[str] = []
    for target in targets:
        if target not in deduped:
            deduped.append(target)
    # Agent-generated tests/test_entities.py is easy to miss in keyword heuristics; always run it
    # for schema "Entity: …" tasks when the file exists (e.g. BusinessProfile).
    if task and re.search(r"entity:\s*", str(task.get("title", "")), flags=re.I):
        ent_probe = tests_dir / "test_entities.py"
        if ent_probe.is_file():
            rel = str(ent_probe.relative_to(project_root)).replace("\\", "/")
            if rel not in deduped:
                deduped.append(rel)
    return deduped


def _synthetic_alignment_failure(notes: str) -> dict[str, Any]:
    """Minimal shape compatible with callers that read verdict.aligned / verdict.notes."""
    return {
        "done": False,
        "advanced": False,
        "verdict": {
            "aligned": False,
            "confidence": 0.0,
            "missing_requirements": [],
            "notes": notes,
        },
    }


def run_project_verification(
    project_root: Path,
    *,
    task: dict[str, Any] | None = None,
    run_full_suite: bool = True,
    parallel_workers: int = 4,
) -> VerificationResult:
    checks: list[str] = []
    outputs: list[str] = []
    failures: list[str] = []
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(project_root)
        if not existing
        else str(project_root) + os.pathsep + existing
    )

    tier1: list[tuple[int, list[str], str]] = []
    tier2: list[tuple[int, list[str], str]] = []
    i1 = 0
    i2 = 0

    def add_tier1(cmd: list[str], name: str) -> None:
        nonlocal i1
        tier1.append((i1, cmd, name))
        i1 += 1

    def add_tier2(cmd: list[str], name: str) -> None:
        nonlocal i2
        tier2.append((i2, cmd, name))
        i2 += 1

    def run_cmd(index: int, cmd: list[str], name: str) -> tuple[int, str, str, bool]:
        try:
            r = subprocess.run(
                cmd,
                cwd=str(project_root),
                text=True,
                capture_output=True,
                timeout=300,
                env=env,
            )
            snippet = f"$ {' '.join(cmd)}\n{r.stdout}\n{r.stderr}".strip()
            return index, name, snippet, r.returncode != 0
        except Exception as exc:
            return index, name, f"$ {' '.join(cmd)}\nERROR: {exc}", True

    def run_tier(tier: list[tuple[int, list[str], str]]) -> list[tuple[int, str, str, bool]]:
        if not tier:
            return []
        results: list[tuple[int, str, str, bool]] = []
        max_workers = max(1, min(parallel_workers, len(tier)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(run_cmd, index, cmd, name) for index, cmd, name in tier
            ]
            for future in as_completed(futures):
                results.append(future.result())
        return sorted(results, key=lambda x: x[0])

    if (project_root / "package.json").is_file():
        if run_full_suite:
            add_tier1(["npm", "test"], "npm test")
            add_tier1(["npm", "run", "build"], "npm run build")
        else:
            add_tier1(["npm", "run", "build"], "npm run build")

    pytest_base = ["pytest", "-q", "--tb=line"]
    if (
        (project_root / "pyproject.toml").is_file()
        or (project_root / "pytest.ini").is_file()
        or (project_root / "tests").is_dir()
    ):
        focused_targets = _focused_pytest_targets(project_root, task)
        if focused_targets and run_full_suite:
            add_tier1(pytest_base + focused_targets, "pytest (focused)")
            add_tier2(pytest_base, "pytest (full suite)")
        elif focused_targets:
            add_tier1(pytest_base + focused_targets, "pytest (focused)")
        else:
            add_tier1(pytest_base, "pytest")

    for _, name, snippet, failed in run_tier(tier1):
        checks.append(name)
        outputs.append(snippet)
        if failed:
            failures.append(name)

    if tier2:
        if failures:
            outputs.append(
                "[verification]\nSkipped pytest (full suite): earlier checks failed "
                "(staged verification avoids re-running the whole suite when focused/npm already failed)."
            )
        else:
            for _, name, snippet, failed in run_tier(tier2):
                checks.append(name)
                outputs.append(snippet)
                if failed:
                    failures.append(name)

    out = "\n\n".join(outputs) if outputs else "No verification checks detected."
    return VerificationResult(
        checks_run=checks,
        output=out,
        success=len(failures) == 0,
        failures=failures,
    )


def _attach_starting_for_topic(state: dict[str, Any], topic: str) -> None:
    state["status"] = "starting"
    state["last_error"] = (
        "Generating feature schema (OpenAI GPT-5.5 draft → Anthropic Opus audit → OpenAI GPT-5.5 finalize). "
        "This step often takes 1–3 minutes. The dashboard polls /autonomy/status while you wait."
    )
    state["schema_path"] = ""
    state["tasks"] = []
    state["locked_run_topic"] = (topic or "").strip()
    state["locked_run_schema_sha256"] = ""


def _bootstrap_autonomous_run_before_schema(
    settings: Settings, topic: str | None, schema_path: str | None
) -> tuple[dict[str, Any], Literal["topic", "schema_only"]]:
    if not topic and not schema_path:
        raise ValueError("Provide either topic or schema_path")

    prior = load_agent_state(settings)
    if autonomous_run_topic_lock_active(prior):
        raise ValueError(
            "An autonomous run is already bound to a topic and feature schema. "
            "Finish the current run, or call POST /autonomy/reset before starting a different topic."
        )

    source_root = _project_root(settings)
    state = _new_state(settings)
    state["status"] = "running"
    if settings.autonomous_runner in {"cursor", "auto"}:
        state["cursor_cli_command"] = resolve_cursor_command(settings.cursor_cli_command)
    else:
        state["cursor_cli_command"] = ""
    run_root = source_root
    if settings.autonomous_isolate_runs:
        run_label = topic or Path(schema_path or "autonomous-run").stem
        run_root = _create_isolated_run_workspace(settings, source_root, run_label)
    state["project_root"] = str(run_root.resolve())

    if topic:
        _attach_starting_for_topic(state, topic)
        return state, "topic"
    return state, "schema_only"


def _finish_topic_schema_and_first_step(settings: Settings, expected_topic: str) -> dict[str, Any] | None:
    """Continue after state was saved with status=starting. Returns None if state was reset or superseded."""
    state = load_agent_state(settings)
    if str(state.get("status", "")).lower() != "starting":
        return None
    if (state.get("locked_run_topic") or "").strip() != (expected_topic or "").strip():
        return None
    try:
        schema_result = generate_and_store_feature_schema(expected_topic, settings)
        resolved_schema = schema_result["path"]
    except Exception as exc:
        state = load_agent_state(settings)
        if str(state.get("status", "")).lower() == "starting" and (
            state.get("locked_run_topic") or ""
        ).strip() == (expected_topic or "").strip():
            state["status"] = "failed"
            state["last_error"] = f"Schema generation failed: {exc}"[:4000]
            state["locked_run_topic"] = ""
            state["schema_path"] = ""
            state["tasks"] = []
            save_agent_state(settings, state)
        raise

    reset_feature_loop_state(resolved_schema)
    state = load_agent_state(settings)
    if str(state.get("status", "")).lower() != "starting":
        return None
    if (state.get("locked_run_topic") or "").strip() != (expected_topic or "").strip():
        return None
    state["schema_path"] = resolved_schema
    state["tasks"] = _build_tasks_from_schema(resolved_schema)
    schema_file = Path(resolved_schema)
    if schema_file.is_file():
        state["locked_run_schema_sha256"] = hashlib.sha256(schema_file.read_bytes()).hexdigest()
    else:
        state["locked_run_schema_sha256"] = ""
    save_agent_state(settings, state)
    return run_next_step(settings)


def background_finish_topic_autonomous_start(expected_topic: str) -> None:
    """Run schema generation + first step after HTTP returned (see POST /autonomy/start)."""
    from app.config import get_settings

    settings = get_settings()
    try:
        out = _finish_topic_schema_and_first_step(settings, expected_topic)
        if out is None:
            logger.info(
                "Topic start background job skipped (state no longer 'starting' for topic %r).",
                expected_topic,
            )
    except Exception:
        logger.exception("Autonomous topic start (schema + first step) failed for topic %r", expected_topic)


def start_autonomous_topic_run_deferred(settings: Settings, topic: str) -> dict[str, Any]:
    """Persist starting state and return status immediately; caller schedules background_finish_topic_autonomous_start."""
    state, phase = _bootstrap_autonomous_run_before_schema(settings, topic, None)
    if phase != "topic":
        raise RuntimeError("internal: expected topic phase")
    save_agent_state(settings, state)
    return status_payload(settings)


def start_autonomous_run(settings: Settings, topic: str | None, schema_path: str | None) -> dict[str, Any]:
    state, phase = _bootstrap_autonomous_run_before_schema(settings, topic, schema_path)
    if phase == "topic":
        save_agent_state(settings, state)
        out = _finish_topic_schema_and_first_step(settings, (topic or "").strip())
        if out is None:
            raise RuntimeError("Autonomous start could not continue (state changed).")
        return out

    resolved_schema = str(Path(schema_path or "").resolve())
    reset_feature_loop_state(resolved_schema)
    state["schema_path"] = resolved_schema
    state["tasks"] = _build_tasks_from_schema(resolved_schema)
    state["locked_run_topic"] = ""
    schema_file = Path(resolved_schema)
    if schema_file.is_file():
        state["locked_run_schema_sha256"] = hashlib.sha256(schema_file.read_bytes()).hexdigest()
    else:
        state["locked_run_schema_sha256"] = ""
    save_agent_state(settings, state)
    return run_next_step(settings)


def _mark_needs_review(
    settings: Settings,
    state: dict[str, Any],
    idx: int,
    reason: str,
    *,
    escalation_trigger: str | None = None,
) -> None:
    _set_task_status(state, idx, "needs_review")
    state["status"] = "blocked"
    state["last_error"] = reason
    # Streak is only meaningful while stepping; do not let it grow unbounded across blocks/repairs.
    state["tests_failed_streak"] = 0
    tr = (escalation_trigger or reason)[:500]
    record_escalation_for_task(settings, state, idx, tr, force=False)


def _verdict_reason(verdict: dict[str, Any] | None, fallback: str) -> str:
    if not verdict:
        return fallback
    notes = str(verdict.get("notes", "")).strip()
    missing = verdict.get("missing_requirements", [])
    if notes:
        return notes
    if isinstance(missing, list) and missing:
        return "Missing requirements: " + "; ".join(str(x) for x in missing[:5])
    return fallback


def _extract_verification_focus(verification_text: str) -> tuple[list[str], str]:
    """Return failing test ids and a short failure snippet."""
    text = verification_text or ""
    failing_tests: list[str] = []
    for m in re.finditer(r"^FAILED\s+([^\s]+)", text, flags=re.MULTILINE):
        failing_tests.append(m.group(1).strip())
    # Keep unique ordering
    deduped: list[str] = []
    for t in failing_tests:
        if t not in deduped:
            deduped.append(t)

    snippet = ""
    marker = "short test summary info"
    idx = text.lower().find(marker)
    if idx >= 0:
        snippet = text[idx : idx + 1800]
    else:
        # fallback to tail
        snippet = text[-1800:]
    return deduped[:20], snippet


def _extract_failure_details(verification_text: str) -> dict[str, str]:
    """Extract structured failure clues from pytest output."""
    text = verification_text or ""
    failing_tests, _ = _extract_verification_focus(text)
    details: dict[str, str] = {
        "test_id": failing_tests[0] if failing_tests else "",
        "exception_type": "",
        "file_path": "",
        "line": "",
        "assertion_hint": "",
    }
    m_exc = re.search(r"^E\s+([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception))\b", text, flags=re.MULTILINE)
    if m_exc:
        details["exception_type"] = m_exc.group(1).strip()
    m_file = re.search(r"^([^\n:]+\.py):(\d+):\s*(?:in\s+[^\n]+)?$", text, flags=re.MULTILINE)
    if m_file:
        details["file_path"] = m_file.group(1).strip().replace("\\", "/")
        details["line"] = m_file.group(2).strip()
    m_assert = re.search(r"^E\s+assert\s+(.+)$", text, flags=re.MULTILINE)
    if m_assert:
        details["assertion_hint"] = m_assert.group(1).strip()[:220]
    return details


def _failure_fingerprint_from_text(verification_text: str) -> str:
    details = _extract_failure_details(verification_text)
    parts = [
        details.get("test_id", "") or "no-test-id",
        details.get("exception_type", "") or "no-exception",
        details.get("file_path", "") or "no-file",
        details.get("line", "") or "0",
    ]
    return "|".join(parts)


def _autofix_memory_path(settings: Settings) -> Path:
    settings.user_data_dir.mkdir(parents=True, exist_ok=True)
    return settings.user_data_dir / "autofix_memory.json"


def _load_autofix_memory(settings: Settings) -> dict[str, Any]:
    return _load_json(_autofix_memory_path(settings), {"patterns": {}})


def _save_autofix_memory(settings: Settings, memory: dict[str, Any]) -> None:
    _save_json(_autofix_memory_path(settings), memory)


def _error_key(text: str) -> str:
    lowered = (text or "").lower()
    if _looks_like_alignment_step_mismatch(text):
        return "alignment_step_mismatch"
    if "syntaxerror" in lowered:
        return "syntaxerror"
    if "modulenotfounderror" in lowered:
        return "modulenotfounderror"
    if "importerror" in lowered:
        return "importerror"
    if "keyerror" in lowered:
        return "keyerror"
    if "assertionerror" in lowered or "assert " in lowered:
        return "assertionerror"
    if "timed out" in lowered:
        return "timeout"
    return "generic"


def _current_failure_signature(state: dict[str, Any]) -> str:
    task_id = str(state.get("current_task_id", "unknown"))
    task_title = ""
    for task in state.get("tasks", []):
        if str(task.get("id")) == task_id:
            task_title = str(task.get("title", ""))
            break
    verification_text = str(state.get("last_verification_output", ""))
    fingerprint = _failure_fingerprint_from_text(verification_text)
    ek = _error_key(
        str(state.get("last_error", "")) + "\n" + verification_text
    )
    return f"{task_id}|{task_title}|{fingerprint}|{ek}"


def _general_failure_signature(state: dict[str, Any]) -> str:
    verification_text = str(state.get("last_verification_output", ""))
    fingerprint = _failure_fingerprint_from_text(verification_text)
    ek = _error_key(
        str(state.get("last_error", "")) + "\n" + verification_text
    )
    return f"general|{fingerprint}|{ek}"


def _heuristic_repair_tips(verification_text: str, last_error: str) -> list[str]:
    text = (verification_text or "") + "\n" + (last_error or "")
    lowered = text.lower()
    tips: list[str] = list(collect_lesson_hints(text, max_hints=3))
    if "keyerror" in lowered:
        tips.append("Preserve existing response keys and add any missing key expected by tests.")
    if "assertionerror" in lowered and "==" in text:
        tips.append("Normalize response values to canonical forms expected by tests (e.g., Fibreglass).")
    if "syntaxerror" in lowered:
        tips.append("Fix syntax/import errors first so pytest collection succeeds.")
    if "modulenotfounderror" in lowered or "importerror" in lowered:
        tips.append("Fix import/module path issues before feature-level behavior changes.")
    if "timed out" in lowered:
        tips.append("Use focused tests first, then full suite; avoid long exploratory commands.")
    if (
        "insufficient for full alignment" in lowered
        or "significant regressions across other api routes" in lowered
        or "focused tests" in lowered
    ):
        tips.append(
            "If focused task tests pass but unrelated suites fail, preserve task progress and defer unrelated fixes."
        )
    if _looks_like_alignment_step_mismatch(text):
        if SCHEMA_LOOP_DRIFT_TIP not in tips:
            tips.insert(0, SCHEMA_LOOP_DRIFT_TIP)
    if not tips:
        tips.append("Make minimal targeted code edits and prove with focused test evidence.")
    seen: set[str] = set()
    deduped: list[str] = []
    for t in tips:
        if t in seen:
            continue
        seen.add(t)
        deduped.append(t)
    return deduped[:7]


def _tip_confidence(successes: int, attempts: int) -> float:
    """Smoothed win-rate score for ranking learned tips."""
    if attempts <= 0:
        return 0.0
    # Laplace smoothing keeps low-sample tips from dominating.
    return (successes + 1.0) / (attempts + 2.0)


def _ranked_tips_from_item(item: dict[str, Any]) -> list[str]:
    tip_stats = item.get("tip_stats", {})
    if not isinstance(tip_stats, dict):
        tip_stats = {}
    ranked: list[tuple[float, str]] = []
    for raw_tip, raw_meta in tip_stats.items():
        tip = str(raw_tip).strip()
        if not tip:
            continue
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        attempts = int(meta.get("attempts", 0) or 0)
        successes = int(meta.get("successes", 0) or 0)
        # Demote chronic losers: repeated use, never helped.
        if attempts >= 3 and successes == 0:
            continue
        score = _tip_confidence(successes, attempts)
        # Small boost for explicit successful tips from prior schema.
        successful_tips = item.get("successful_tips", [])
        if isinstance(successful_tips, list) and tip in [str(t) for t in successful_tips]:
            score += 0.05
        ranked.append((score, tip))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [tip for _, tip in ranked]


def _memory_tips_for_signature(settings: Settings, signature: str) -> list[str]:
    memory = _load_autofix_memory(settings)
    patterns = memory.get("patterns", {})
    if not isinstance(patterns, dict):
        return []
    item = patterns.get(signature, {})
    if not isinstance(item, dict):
        return []
    ranked = _ranked_tips_from_item(item)
    if ranked:
        return ranked[:8]
    # Backward-compatible fallback for old memory shape.
    tips = item.get("successful_tips", [])
    if isinstance(tips, list):
        return [str(t) for t in tips[:5]]
    return []


def _memory_tips_for_signatures(settings: Settings, signatures: list[str]) -> list[str]:
    merged: list[str] = []
    for sig in signatures:
        for tip in _memory_tips_for_signature(settings, sig):
            if tip not in merged:
                merged.append(tip)
    return merged[:8]


def _memory_strategy_scores(settings: Settings, signatures: list[str]) -> dict[str, float]:
    memory = _load_autofix_memory(settings)
    patterns = memory.get("patterns", {})
    if not isinstance(patterns, dict):
        return {}
    scores: dict[str, list[float]] = {}
    for sig in signatures:
        item = patterns.get(sig, {})
        if not isinstance(item, dict):
            continue
        tip_stats = item.get("tip_stats", {})
        if not isinstance(tip_stats, dict):
            continue
        for raw_tip, raw_meta in tip_stats.items():
            tip = str(raw_tip).strip().lower()
            if not tip.startswith("strategy:"):
                continue
            strategy = tip.split(":", 1)[1].strip()
            meta = raw_meta if isinstance(raw_meta, dict) else {}
            attempts = int(meta.get("attempts", 0) or 0)
            successes = int(meta.get("successes", 0) or 0)
            scores.setdefault(strategy, []).append(_tip_confidence(successes, attempts))
    return {k: sum(v) / max(1, len(v)) for k, v in scores.items()}


def _update_autofix_memory(
    settings: Settings,
    *,
    signature: str,
    used_tips: list[str],
    success: bool,
    note: str,
) -> None:
    memory = _load_autofix_memory(settings)
    patterns = memory.setdefault("patterns", {})
    if not isinstance(patterns, dict):
        memory["patterns"] = {}
        patterns = memory["patterns"]
    item = patterns.get(signature, {})
    if not isinstance(item, dict):
        item = {}
    item["attempts"] = int(item.get("attempts", 0)) + 1
    if success:
        item["successes"] = int(item.get("successes", 0)) + 1
        item["successful_tips"] = used_tips[:5]
    tip_stats = item.get("tip_stats", {})
    if not isinstance(tip_stats, dict):
        tip_stats = {}
    for raw_tip in used_tips[:12]:
        tip = str(raw_tip).strip()
        if not tip:
            continue
        meta = tip_stats.get(tip, {})
        if not isinstance(meta, dict):
            meta = {}
        meta["attempts"] = int(meta.get("attempts", 0)) + 1
        if success:
            meta["successes"] = int(meta.get("successes", 0)) + 1
            meta["last_success_utc"] = _utc_now()
        meta["last_used_utc"] = _utc_now()
        tip_stats[tip] = meta
    item["tip_stats"] = tip_stats
    item["last_note"] = note[:500]
    item["last_updated_utc"] = _utc_now()
    patterns[signature] = item
    _save_autofix_memory(settings, memory)


def _update_autofix_memory_for_signatures(
    settings: Settings,
    *,
    signatures: list[str],
    used_tips: list[str],
    success: bool,
    note: str,
) -> None:
    for signature in signatures:
        _update_autofix_memory(
            settings,
            signature=signature,
            used_tips=used_tips,
            success=success,
            note=note,
        )


def _classify_blocker(reason: str, verification_text: str, agent_output: str) -> str:
    combined = "\n".join([reason or "", verification_text or "", agent_output or ""])
    text = combined.lower()
    compact = text.replace(" ", "")
    if _looks_like_alignment_step_mismatch(combined):
        return "alignment_drift"
    if (
        "notvalidjson" in compact
        or "invalidjson" in compact
        or "expectingvalue" in compact
        or "jsondecodeerror" in compact
        or "not valid json" in text
        or ("expecting value" in text and "char" in text)
    ):
        return "json_parse"
    if "syntaxerror" in text:
        return "syntax"
    if "error collecting" in text or "modulenotfounderror" in text or "importerror" in text:
        return "import_or_collection"
    if "failed" in text or "assertionerror" in text:
        return "test_failure"
    if "alignment failed" in text or "not aligned" in text:
        return "alignment"
    if "timed out" in text:
        return "timeout"
    return "generic"


def _playbook_type(
    task: dict[str, Any],
    verification_text: str,
    blocker_type: str,
    *,
    last_error: str = "",
    agent_output: str = "",
) -> str:
    combined = "\n".join([last_error or "", verification_text or "", agent_output or ""])
    if _looks_like_alignment_step_mismatch(combined):
        return "schema_loop_task_mismatch"
    details = _extract_failure_details(verification_text)
    lower = (verification_text or "").lower()
    exc = details.get("exception_type", "").lower()
    task_text = f"{task.get('title', '')}\n{task.get('description', '')}".lower()
    if "404" in lower and "/autonomy/" in lower:
        return "missing_autonomy_routes"
    if "422" in lower and ("quote" in task_text or "enquir" in task_text):
        return "quote_validation_contract"
    if exc == "keyerror":
        return "response_shape_keyerror"
    if "assert " in lower or exc == "assertionerror":
        return "assertion_mismatch"
    if blocker_type == "import_or_collection":
        return "import_or_collection"
    if blocker_type == "timeout":
        return "timeout"
    return "generic"


def _playbook_directives(playbook_type: str) -> str:
    if playbook_type == "schema_loop_task_mismatch":
        return (
            "- Follow ONLY the Execution anchor task (id/title/description); ignore conflicting schema-loop wording.\n"
            "- Implement or fix the anchored entity/step in code; do not pivot to a different entity the model mentioned.\n"
            "- If app/entities or imports fail at collection time, fix broken validators/models first, then the anchored work.\n"
        )
    if playbook_type == "missing_autonomy_routes":
        return "- Restore and verify /autonomy/* routes before task-specific edits.\n"
    if playbook_type == "quote_validation_contract":
        return "- Preserve quote-enquiry payload aliases and ensure valid sample submits with HTTP 201.\n"
    if playbook_type == "response_shape_keyerror":
        return "- Keep response keys backward-compatible; add missing keys without removing existing ones.\n"
    if playbook_type == "assertion_mismatch":
        return "- Match canonical expected values exactly; avoid broad refactors.\n"
    if playbook_type == "import_or_collection":
        return "- Fix import/test collection first, then rerun focused tests.\n"
    if playbook_type == "timeout":
        return "- Use deterministic minimal edits and shortest focused verification first.\n"
    return "- Apply the smallest edit that addresses the first failing test.\n"


def _repair_directives_for(blocker_type: str) -> str:
    common = (
        "- Make concrete code edits, not only validation text.\n"
        "- Keep scope limited to the current task and failing checks.\n"
        "- Run focused tests first, then full verification.\n"
    )
    if blocker_type == "syntax":
        return common + "- First fix Python syntax/import-time errors so tests can collect.\n"
    if blocker_type == "import_or_collection":
        return common + "- First restore import/test collection, then repair failing behavior.\n"
    if blocker_type == "test_failure":
        return common + "- Preserve existing response contracts unless failing tests require changes.\n"
    if blocker_type == "alignment":
        return common + "- Ensure output includes changed files, rationale, and pass/fail evidence.\n"
    if blocker_type == "alignment_drift":
        return common + (
            "- Treat the current task anchor as source of truth if alignment text references a different step.\n"
            "- Repair shared import failures (e.g. entities module) before proving entity-specific tests.\n"
        )
    if blocker_type == "json_parse":
        return common + (
            "- Patch executor accepts strict JSON only: no // or /* */ comments and no trailing commas.\n"
            "- Phase 2 output must use keys summary, edits, commands — commands as plain strings only.\n"
        )
    if blocker_type == "timeout":
        return common + "- Prefer small deterministic edits and shorter verification commands first.\n"
    return common


def _strategy_directives(strategy: str) -> str:
    s = (strategy or "").strip().lower()
    if s == "task_anchor_first":
        return (
            "- Strategy: task_anchor_first.\n"
            "- Implement only what the Execution anchor names; ignore unrelated schema-loop lines.\n"
            "- Fix import/collection failures in shared code before proving the anchored change.\n"
        )
    if s == "contract_preserving":
        return (
            "- Strategy: contract_preserving.\n"
            "- Keep response shape and key names stable; fix behavior with minimal internal changes.\n"
        )
    if s == "schema_normalizing":
        return (
            "- Strategy: schema_normalizing.\n"
            "- Normalize values and formats to expected canonical forms used in tests.\n"
        )
    if s == "traceback_root_cause":
        return (
            "- Strategy: traceback_root_cause.\n"
            "- Fix exactly the first traceback root cause (file/line/exception) before broader cleanup.\n"
        )
    return ""


def _verification_supports_current_task(task: dict[str, Any], verification_text: str) -> bool:
    title = str(task.get("title", "")).lower()
    text = (verification_text or "").lower()
    if "endpoint: get /api/projects" in title and "tests\\test_projects_api.py" in text:
        return True
    if "endpoint: get /api/services" in title and "tests\\test_services_api.py" in text:
        return True
    if "endpoint: get /api/services/:slug" in title and "tests\\test_service_detail_api.py" in text:
        return True
    if "endpoint: get /api/pages/:slug" in title and "tests\\test_page_content_api.py" in text:
        return True
    return False


def _focused_check_passed(verify: VerificationResult) -> bool:
    return "pytest (focused)" in verify.checks_run and "pytest (focused)" not in verify.failures


def _entity_task_pytest_pass_overrules_alignment(
    task: dict[str, Any], verify: VerificationResult
) -> bool:
    """For ``Entity: …`` schema tasks, passing pytest is authoritative over alignment LLM nitpicks."""
    if not verify.success:
        return False
    if not re.search(r"entity:\s*", str(task.get("title", "")), re.I):
        return False
    joined = " ".join(verify.checks_run).lower()
    return "pytest" in joined


def _allow_nonblocking_alignment(
    *,
    task: dict[str, Any],
    verify: VerificationResult,
    verdict: dict[str, Any] | None,
) -> bool:
    text = f"{task.get('title', '')}\n{task.get('description', '')}".lower()
    if "quote" not in text and "enquir" not in text:
        return False
    if not _focused_check_passed(verify):
        return False
    if _has_task_relevant_failures(task, verify.output):
        return False
    notes = str((verdict or {}).get("notes", "")).lower()
    if (
        "insufficient for full alignment" in notes
        or "significant regressions across other api routes" in notes
        or "not aligned" in notes
    ):
        return True
    return False


def _task_related_test_markers(task: dict[str, Any]) -> list[str]:
    title = str(task.get("title", "")).lower()
    desc = str(task.get("description", "")).lower()
    text = f"{title}\n{desc}"
    markers: list[str] = []
    is_schema_entity_task = bool(re.search(r"entity:\s*[^\n]+", title, flags=re.I))
    if not is_schema_entity_task:
        if "/api/projects" in text or "project" in text:
            markers.extend(["test_projects_api", "test_project_detail_endpoint"])
        if "/api/services" in text or "service" in text:
            markers.extend(["test_services_api", "test_service_detail_api"])
        if "/api/pages" in text or "homepage" in text or "page" in text:
            markers.extend(["test_page_content_api"])
        if "quote" in text or "enquiry" in text:
            markers.extend(["test_quote_enquiries", "test_quote_enquiries_api"])
        if "service area" in text:
            markers.extend(["test_service_areas_api"])
    # Schema entity tasks: "Entity: ThemeSettings" — map name keywords to test stems
    m = re.search(r"entity:\s*([^\n]+)", title, flags=re.I)
    if m:
        ent = re.sub(r"[^a-z0-9]+", "", m.group(1).strip().lower())
        skip_service = "servicearea" in ent or "service_area" in ent.replace("_", "")
        for key, stems in _ENTITY_NAME_MARKERS:
            if key == "service" and skip_service:
                continue
            if key == "profile" and ent == "businessprofile":
                continue
            if key in ent:
                markers.extend(stems)
    # Dedupe preserving order
    out: list[str] = []
    for mkr in markers:
        if mkr not in out:
            out.append(mkr)
    return out


def _has_task_relevant_failures(task: dict[str, Any], verification_text: str) -> bool:
    failing_tests, _ = _extract_verification_focus(verification_text)
    if not failing_tests:
        return False
    markers = _task_related_test_markers(task)
    if not markers:
        # Cannot tie this task to specific tests; do not treat whole-suite noise as blocking.
        return False
    lowered_tests = [t.lower() for t in failing_tests]
    return any(any(marker in test_id for marker in markers) for test_id in lowered_tests)


def _run_agent(
    *,
    settings: Settings,
    state: dict[str, Any],
    prompt: str,
    project_root: Path,
    logs_dir: Path,
) -> AgentRunResult:
    runner = str(state.get("runner") or settings.autonomous_runner)
    if runner == "patch_executor":
        return run_with_patch_executor(
            settings=settings,
            prompt=prompt,
            project_root=str(project_root),
            logs_dir=logs_dir,
        )
    if runner == "openai":
        return run_with_openai(settings=settings, prompt=prompt, logs_dir=logs_dir)
    if runner == "cursor":
        return run_with_cursor(
            settings=settings,
            prompt=prompt,
            project_root=str(project_root),
            logs_dir=logs_dir,
        )
    # auto: prefer cursor, optionally fallback to openai
    try:
        return run_with_cursor(
            settings=settings,
            prompt=prompt,
            project_root=str(project_root),
            logs_dir=logs_dir,
        )
    except Exception:
        if not settings.autonomous_fallback_to_openai:
            raise
        state["last_error"] = "Cursor runner unavailable; falling back to patch executor."
        state["runner"] = "patch_executor"
        return run_with_patch_executor(
            settings=settings,
            prompt=prompt,
            project_root=str(project_root),
            logs_dir=logs_dir,
        )


def _safe_run_agent(
    *,
    settings: Settings,
    state: dict[str, Any],
    prompt: str,
    project_root: Path,
    logs_dir: Path,
) -> AgentRunResult:
    """Never raise — runner/API crashes mid-step otherwise leave tasks stuck ``running``."""
    try:
        return _run_agent(
            settings=settings,
            state=state,
            prompt=prompt,
            project_root=project_root,
            logs_dir=logs_dir,
        )
    except Exception as exc:
        now = datetime.now(timezone.utc).isoformat()
        msg = f"Runner crashed before completing: {exc}"
        return AgentRunResult(
            provider="error",
            command="",
            stdout="",
            stderr=msg,
            exit_code=1,
            timed_out=False,
            started_at_utc=now,
            ended_at_utc=now,
            duration_seconds=0.0,
            log_path="",
        )


def _autonomous_vertical_guard(settings: Settings) -> str:
    domain = getattr(settings, "autonomous_workspace_domain", "generic") or "generic"
    if domain == "pool":
        return (
            "\n\nVertical scope (mandatory):\n"
            "- Target: **swimming pool** marketing site under `app/pool/` only.\n"
        )
    return ""


def _protected_paths_prompt_addon(settings: Settings, project_root: Path) -> str:
    paths = effective_autonomous_protected_paths(settings, project_root)
    if not paths:
        return ""
    lines = "\n".join(f"- {p}" for p in paths[:32])
    return (
        "\n\nRepository guardrails (honor even if the task text mentions these areas):\n"
        "- Do not reference these paths in patch `edits` or `commands`; add new modules/files instead.\n"
        + lines
    )


def _entity_schema_task_prompt_addon(task: dict[str, Any]) -> str:
    """Extra instructions for schema steps titled ``Entity: …`` to avoid NameError / duplicate classes."""
    if not re.search(r"entity:\s*", str(task.get("title", "")), re.I):
        return ""
    return (
        "\n\nEntity / test hygiene (mandatory for this task):\n"
        "- Any test file under tests/ that uses `BusinessProfile` or another app entity must import it "
        "explicitly, e.g. `from app.entities import BusinessProfile`, at the top (after any "
        "`from __future__` import). Do not reference entity classes without imports.\n"
        "- In app/entities.py keep exactly one class definition per entity name. To change fields or "
        "methods, use replace_in_file on the existing class body — do not stack multiple "
        "`class BusinessProfile` blocks (later definitions override earlier ones and break tests).\n"
        "- Do not use write_file on app/entities.py; the executor blocks it — use replace_in_file or "
        "append_file.\n"
    )


def _hit_protected_path_blocker(agent_output: str) -> bool:
    t = (agent_output or "").lower()
    return (
        "blocked edit to protected path:" in t
        or "blocked command referencing protected path:" in t
    )


def run_next_step(settings: Settings, repair_mode: bool = False) -> dict[str, Any]:
    state = load_agent_state(settings)
    if _recover_stale_running_state(state):
        save_agent_state(settings, state)
    if state.get("paused"):
        return state
    if not state.get("schema_path"):
        if str(state.get("status", "")).lower() == "starting":
            return state
        raise ValueError("No schema configured. Start autonomous run first.")

    _assert_locked_schema_unchanged(state)

    project_root = _state_project_root(settings, state)
    if repair_mode:
        idx = _repair_focus_task_index(state)
    else:
        idx = _next_runnable_task_index(state)
    if idx is None:
        if repair_mode:
            state["status"] = "blocked"
            if not str(state.get("last_error", "")).strip():
                state["last_error"] = "Repair mode could not resolve a focused task."
            save_agent_state(settings, state)
            return state
        if _all_tasks_complete(state):
            state["status"] = "complete"
            state["current_task_id"] = ""
        else:
            state["status"] = "blocked"
            nr = next(
                (
                    t
                    for t in state.get("tasks", [])
                    if isinstance(t, dict)
                    and str(t.get("status", "")).lower() == "needs_review"
                ),
                {},
            )
            if nr.get("id"):
                state["current_task_id"] = str(nr["id"])
            if not str(state.get("last_error", "")).strip():
                state["last_error"] = "All remaining tasks require manual review."
        save_agent_state(settings, state)
        return state

    align_feature_loop_with_autonomous_task(state["schema_path"], idx)

    loop = generate_next_cursor_prompts(schema_path=state["schema_path"], iterations=1)
    prompts = loop.get("prompts", [])
    p0 = prompts[0] if prompts else {}
    task = state["tasks"][idx]
    base_prompt = str(p0.get("prompt", "")).strip()
    if not base_prompt:
        base_prompt = (
            "Implement and validate the current feature step.\n\n"
            f"Current step:\n- {task.get('title', 'Untitled task')}\n"
            f"- {task.get('description', '')}\n\n"
            "Required behavior:\n"
            "- Make focused code changes for this step only.\n"
            "- Run relevant verification and report pass/fail evidence.\n"
            "- Return changed files and concise rationale.\n"
        )
    base_prompt += (
        "\n\nExecution anchor:\n"
        f"- Work ONLY on task `{task.get('id', '')}`: {task.get('title', '')}\n"
        f"- Task description: {task.get('description', '')}\n"
        "- If any generated loop text conflicts with this anchor, follow this anchor.\n"
    )

    _set_task_status(state, idx, "running")
    previous_blocker = str(state.get("last_error", "")).strip()
    # Clear stale errors when a new step attempt starts.
    state["last_error"] = ""
    state["current_task_id"] = state["tasks"][idx]["id"]
    prompt = base_prompt + (
        "\n\nSafety constraints:\n"
        "- Do not delete files or folders outside PROJECT_ROOT.\n"
        "- Require human approval before destructive commands: deleting folders, "
        "git reset, force push, modifying environment files.\n"
    )
    prompt += _protected_paths_prompt_addon(settings, project_root)
    prompt += _autonomous_vertical_guard(settings)
    prompt += _entity_schema_task_prompt_addon(task)
    prompt += _run_topic_lock_prompt_addon(state)
    if repair_mode:
        repair_envelope = state.pop("repair_prompt_envelope", None)
        failing_tests, failure_snippet = _extract_verification_focus(
            str(state.get("last_verification_output", ""))
        )
        failure_details = _extract_failure_details(str(state.get("last_verification_output", "")))
        signature = _current_failure_signature(state)
        general_signature = _general_failure_signature(state)
        memory_tips = _memory_tips_for_signatures(settings, [signature, general_signature])
        heuristic_tips = _heuristic_repair_tips(
            str(state.get("last_verification_output", "")),
            previous_blocker,
        )
        merged_tips: list[str] = []
        for tip in memory_tips + heuristic_tips:
            if tip not in merged_tips:
                merged_tips.append(tip)
        tips_block = "\n".join(f"- {tip}" for tip in merged_tips[:8])
        blocker_type = _classify_blocker(
            previous_blocker,
            str(state.get("last_verification_output", "")),
            str(state.get("last_cursor_output", "")),
        )
        playbook = _playbook_type(
            task,
            str(state.get("last_verification_output", "")),
            blocker_type,
            last_error=previous_blocker,
            agent_output=str(state.get("last_cursor_output", "")),
        )
        fail_list = "\n".join(f"- {t}" for t in failing_tests) or "- (no explicit failing test ids parsed)"
        failure_detail_block = (
            f"- First failing test: {failure_details.get('test_id') or 'unknown'}\n"
            f"- Exception: {failure_details.get('exception_type') or 'unknown'}\n"
            f"- File: {failure_details.get('file_path') or 'unknown'}:{failure_details.get('line') or '?'}\n"
            f"- Assertion hint: {failure_details.get('assertion_hint') or 'n/a'}\n"
        )
        prompt += (
            "\n\nBlocked-task repair context:\n"
            f"- Previous blocker: {previous_blocker or 'unknown'}\n"
            f"- Blocker type: {blocker_type}\n"
            f"- Playbook: {playbook}\n"
            "- Focus only on fixing this current step and failing tests.\n"
            "- Keep changes minimal and scoped.\n"
            "- Re-run verification and report concrete pass/fail evidence.\n"
            "- Preserve existing API contract/response shape unless failing tests explicitly require a shape change.\n"
            "- Do not remove or rename existing keys that passing tests depend on.\n"
            + "\nRepair directives:\n"
            + _repair_directives_for(blocker_type)
            + _playbook_directives(playbook)
            + _strategy_directives(str(state.get("autofix_strategy", "")))
            + "\nLearned repair tips:\n"
            + tips_block
            + "\nStructured failure details:\n"
            + failure_detail_block
            + "\nFailing tests from latest verification:\n"
            + fail_list
            + "\nRecent verification output:\n"
            + failure_snippet
            + "\n\nRecent agent output:\n"
            + str(state.get("last_cursor_output", ""))[:4000]
        )
        if repair_envelope:
            # Evidence-based repair envelope (diagnosis + plan + targeted files) comes first.
            prompt = str(repair_envelope) + prompt
    state["tasks"][idx]["last_prompt"] = prompt
    save_agent_state(settings, state)

    run_result = _safe_run_agent(
        settings=settings,
        state=state,
        prompt=prompt,
        project_root=project_root,
        logs_dir=_cursor_runs_dir(settings),
    )
    combined_output = f"[stdout]\n{run_result.stdout}\n\n[stderr]\n{run_result.stderr}".strip()
    state["tasks"][idx]["last_cursor_output"] = combined_output
    state["last_cursor_output"] = combined_output

    if getattr(run_result, "provider", "") == "error" or (
        "runner crashed before completing" in combined_output.lower()
    ):
        state["tasks"][idx]["attempts"] = int(state["tasks"][idx].get("attempts", 0)) + 1
        _mark_needs_review(settings, state, idx, (combined_output or "")[:1800])
        save_agent_state(settings, state)
        return state

    if _hit_protected_path_blocker(combined_output):
        state["tasks"][idx]["attempts"] = int(state["tasks"][idx].get("attempts", 0)) + 1
        _mark_needs_review(
            settings,
            state,
            idx,
            "Patch targeted a protected infrastructure path (see stderr). "
            "Implement this step in NEW files under app/ and wire imports from allowed modules — "
            "do not edit paths listed in AUTONOMOUS_PROTECTED_PATHS.",
            escalation_trigger="needs_review:protected_path_patch",
        )
        save_agent_state(settings, state)
        return state

    state["tasks"][idx]["attempts"] = int(state["tasks"][idx].get("attempts", 0)) + 1
    current_attempts = int(state["tasks"][idx].get("attempts", 0))

    if run_result.timed_out:
        _mark_needs_review(settings, state, idx, "Cursor run timed out; manual review required.")
        save_agent_state(settings, state)
        return state
    if _contains_phrase(combined_output, BLOCK_PHRASES):
        _mark_needs_review(settings, state, idx, "Cursor output indicates manual/blocking condition.")
        save_agent_state(settings, state)
        return state
    if _contains_phrase(combined_output, CLI_UNSUPPORTED_PHRASES):
        if (state.get("runner") == "auto" or state.get("runner") == "cursor") and settings.autonomous_fallback_to_openai:
            state["last_error"] = "Cursor CLI returned non-agent output; retrying this step with patch executor runner."
            state["runner"] = "patch_executor"
            save_agent_state(settings, state)
            return run_next_step(settings)
        _mark_needs_review(
            settings,
            state,
            idx,
            "Installed Cursor CLI does not return headless agent output in this mode. "
            "Use a Cursor CLI build with terminal agent output support (e.g. cursor-agent) "
            "or configure AUTONOMOUS_RUNNER=openai.",
            escalation_trigger="needs_review:cursor_cli_no_agent_output",
        )
        save_agent_state(settings, state)
        return state
    if _contains_phrase(combined_output, DESTRUCTIVE_HINTS):
        _mark_needs_review(settings, state, idx, "Potential destructive action detected; waiting for approval.")
        save_agent_state(settings, state)
        return state

    full_verify = (current_attempts % settings.autonomous_full_verification_every) == 0
    verify = run_project_verification(
        project_root,
        task=task,
        run_full_suite=full_verify,
        parallel_workers=settings.autonomous_parallel_workers,
    )
    state["last_verification_output"] = verify.output
    state["tasks"][idx]["verification_notes"] = verify.output
    task = state["tasks"][idx]
    verification_blocks_progress = verify.success
    if verify.success:
        state["tests_failed_streak"] = 0
    else:
        relevant_failures = _has_task_relevant_failures(task, verify.output)
        if relevant_failures:
            state["tests_failed_streak"] = int(state.get("tests_failed_streak", 0)) + 1
            if state["tests_failed_streak"] >= 2:
                _mark_needs_review(settings, state, idx, "Verification failed twice in a row.")
                save_agent_state(settings, state)
                return state
        else:
            # Do not trap on unrelated suite failures while this task is otherwise valid.
            verification_blocks_progress = True
            state["tests_failed_streak"] = 0
            if maybe_flag_trigger_once(task, "unrelated_suite_failure"):
                record_escalation_for_task(
                    settings,
                    state,
                    idx,
                    "unrelated_suite_failure",
                    force=False,
                )

    alignment_input = (
        f"{combined_output}\n\n[verification]\n{verify.output}\n"
        f"\n[cursor_exit_code]\n{run_result.exit_code}"
    )
    skip_alignment = not verify.success and _has_task_relevant_failures(task, verify.output)
    if skip_alignment:
        adv = _synthetic_alignment_failure(
            "Skipped schema alignment LLM: task-relevant verification failures are present "
            "(no extra model call; flow continues as not aligned)."
        )
    else:
        adv = evaluate_and_advance_feature_loop(
            settings=settings,
            schema_path=state["schema_path"],
            generated_output=alignment_input,
            trust_verification=_entity_task_pytest_pass_overrules_alignment(task, verify),
            trust_notes="Entity task with passing pytest; schema alignment LLM skipped.",
        )

    aligned = bool((adv.get("verdict") or {}).get("aligned"))
    if not aligned and state["tasks"][idx]["attempts"] <= 1:
        corrective_prompt = (
            prompt
            + "\n\nCorrective pass required:\n"
            + f"- Prior output was not aligned: {(adv.get('verdict') or {}).get('notes', '')}\n"
            + "- Fix missing requirements, rerun tests/build, report concise evidence."
        )
        state["tasks"][idx]["last_prompt"] = corrective_prompt
        save_agent_state(settings, state)
        retry_run = _safe_run_agent(
            settings=settings,
            state=state,
            prompt=corrective_prompt,
            project_root=project_root,
            logs_dir=_cursor_runs_dir(settings),
        )
        retry_output = f"[stdout]\n{retry_run.stdout}\n\n[stderr]\n{retry_run.stderr}".strip()
        state["tasks"][idx]["last_cursor_output"] = retry_output
        state["last_cursor_output"] = retry_output

        if getattr(retry_run, "provider", "") == "error" or (
            "runner crashed before completing" in retry_output.lower()
        ):
            state["tasks"][idx]["attempts"] = int(state["tasks"][idx].get("attempts", 0)) + 1
            _mark_needs_review(settings, state, idx, (retry_output or "")[:1800])
            save_agent_state(settings, state)
            return state

        if _hit_protected_path_blocker(retry_output):
            state["tasks"][idx]["attempts"] = int(state["tasks"][idx].get("attempts", 0)) + 1
            _mark_needs_review(
                settings,
                state,
                idx,
                "Corrective patch targeted a protected infrastructure path (see stderr). "
                "Use new modules under app/ instead.",
                escalation_trigger="needs_review:protected_path_corrective",
            )
            save_agent_state(settings, state)
            return state

        state["tasks"][idx]["attempts"] = int(state["tasks"][idx].get("attempts", 0)) + 1
        attempts_after_retry = int(state["tasks"][idx].get("attempts", 0))
        full_verify2 = (attempts_after_retry % settings.autonomous_full_verification_every) == 0
        verify2 = run_project_verification(
            project_root,
            task=state["tasks"][idx],
            run_full_suite=full_verify2,
            parallel_workers=settings.autonomous_parallel_workers,
        )
        state["last_verification_output"] = verify2.output
        state["tasks"][idx]["verification_notes"] = verify2.output
        retry_task = state["tasks"][idx]
        skip_alignment2 = not verify2.success and _has_task_relevant_failures(
            retry_task, verify2.output
        )
        if skip_alignment2:
            adv = _synthetic_alignment_failure(
                "Skipped schema alignment LLM after corrective run: task-relevant verification failures."
            )
        else:
            adv = evaluate_and_advance_feature_loop(
                settings=settings,
                schema_path=state["schema_path"],
                generated_output=f"{retry_output}\n\n[verification]\n{verify2.output}",
                trust_verification=_entity_task_pytest_pass_overrules_alignment(retry_task, verify2),
                trust_notes="Entity task with passing pytest after corrective; schema alignment LLM skipped.",
            )
        aligned = bool((adv.get("verdict") or {}).get("aligned"))
        if not aligned:
            if verify2.success and (
                "validate step for feature" in prompt.lower()
                or _verification_supports_current_task(state["tasks"][idx], verify2.output)
                or current_attempts >= settings.autonomous_force_advance_attempts
                or _allow_nonblocking_alignment(
                    task=state["tasks"][idx],
                    verify=verify2,
                    verdict=adv.get("verdict"),
                )
                or _entity_task_pytest_pass_overrules_alignment(state["tasks"][idx], verify2)
            ):
                _set_task_status(state, idx, "complete")
                state["status"] = "running"
                state["last_error"] = ""
                save_agent_state(settings, state)
                return state
            _mark_needs_review(
                settings,
                state,
                idx,
                _verdict_reason(
                    adv.get("verdict"),
                    "Alignment failed after one corrective retry.",
                ),
                escalation_trigger="needs_review:alignment_failed_after_corrective",
            )
            save_agent_state(settings, state)
            return state

    if aligned:
        if bool(adv.get("done")):
            _set_task_status(state, idx, "complete")
            state["status"] = "complete"
            state["last_error"] = ""
        else:
            # complete only after a validate pass moves to next step implement.
            next_action = str(adv.get("next_action", "implement"))
            if next_action == "implement":
                _set_task_status(state, idx, "complete")
            state["status"] = "running"
            state["last_error"] = ""
    else:
        # Guardrail: validation steps with passing verification can still be marked
        # "not aligned" when the model output focuses on evidence instead of edits.
        if verification_blocks_progress and (
            "validate step for feature" in prompt.lower()
            or _verification_supports_current_task(state["tasks"][idx], verify.output)
            or current_attempts >= settings.autonomous_force_advance_attempts
            or _allow_nonblocking_alignment(
                task=state["tasks"][idx],
                verify=verify,
                verdict=adv.get("verdict"),
            )
            or _entity_task_pytest_pass_overrules_alignment(state["tasks"][idx], verify)
        ):
            _set_task_status(state, idx, "complete")
            state["status"] = "running"
            state["last_error"] = ""
        else:
            _mark_needs_review(
                settings,
                state,
                idx,
                _verdict_reason(adv.get("verdict"), "Alignment failed."),
                escalation_trigger="needs_review:alignment_failed",
            )

    save_agent_state(settings, state)
    return state


def run_until_blocked(settings: Settings, max_iterations: int | None = None) -> dict[str, Any]:
    state = load_agent_state(settings)
    if state.get("paused"):
        return state
    if str(state.get("status", "")).lower() == "starting":
        return state
    # Do not stack another step while a task is already mid-turn (avoids duplicate agent calls
    # and confusing HTTP 400/500 from overlapping state updates).
    if str(state.get("status", "")).lower() == "running" and any(
        isinstance(t, dict) and str(t.get("status", "")).lower() == "running"
        for t in (state.get("tasks") or [])
    ):
        out = dict(state)
        out["run_until_blocked_noop"] = True
        out["run_until_blocked_noop_reason"] = (
            "A task is already running; wait for the current step to finish, then try again."
        )
        return out
    if str(state.get("schema_path") or "").strip():
        _assert_locked_schema_unchanged(state)
    limit = max_iterations or settings.autonomous_max_iterations
    auto_fix_budget = settings.autonomous_auto_fix_max_attempts
    for _ in range(limit):
        state = run_next_step(settings)
        if state.get("paused") or state.get("status") in {"complete", "failed"}:
            break
        if state.get("status") == "blocked":
            if settings.autonomous_auto_fix_blocked and auto_fix_budget > 0:
                auto_fix_budget -= 1
                state = fix_blocked_task(settings)
                # If repair still blocks, continue loop while budget remains.
                if state.get("status") == "blocked" and auto_fix_budget <= 0:
                    state["last_error"] = (
                        (state.get("last_error") or "")
                        + " Auto-fix budget exhausted for this run."
                    ).strip()
                    tid = str(state.get("current_task_id") or "")
                    for i, t in enumerate(state.get("tasks") or []):
                        if isinstance(t, dict) and str(t.get("id")) == tid:
                            record_escalation_for_task(
                                settings,
                                state,
                                i,
                                "autonomous_auto_fix_budget_exhausted",
                                force=True,
                            )
                            state["last_escalation_event"] = (
                                str(state.get("last_escalation_event") or "")
                                + " Auto-fix budget exhausted; escalation written."
                            ).strip()
                            break
                    save_agent_state(settings, state)
                    break
                continue
            break
    return state


def fix_blocked_task(settings: Settings) -> dict[str, Any]:
    """Retry blocked task using diagnosis-first, evidence-based repair."""
    max_attempts = max(1, settings.autonomous_auto_fix_max_attempts)
    state = load_agent_state(settings)
    if state.get("paused"):
        state["paused"] = False
    if str(state.get("schema_path") or "").strip():
        _assert_locked_schema_unchanged(state)

    st = str(state.get("status", "")).lower()
    if st != "blocked":
        tasks_list = state.get("tasks") or []
        has_needs_review = any(
            isinstance(t, dict) and str(t.get("status", "")).lower() == "needs_review"
            for t in tasks_list
        )
        if has_needs_review and st in {"running", "idle", "paused"}:
            state["status"] = "blocked"
            tid_c = str(state.get("current_task_id") or "").strip()
            cur = next(
                (t for t in tasks_list if isinstance(t, dict) and str(t.get("id")) == tid_c),
                None,
            )
            if not cur or str(cur.get("status", "")).lower() != "needs_review":
                for t in tasks_list:
                    if isinstance(t, dict) and str(t.get("status", "")).lower() == "needs_review":
                        state["current_task_id"] = str(t.get("id", ""))
                        break
            save_agent_state(settings, state)
        else:
            raise ValueError(
                f"Autonomy is not blocked (status={state.get('status')!r}); "
                "fix-blocked applies when autonomy is blocked or when at least one task is in needs_review "
                "after a recoverable stop. If a normal step is still executing, wait for it to finish."
            )
    state["tests_failed_streak"] = 0
    state.pop("repair_stop_reason", None)
    save_agent_state(settings, state)

    for round_i in range(max_attempts):
        state = load_agent_state(settings)
        if state.get("status") != "blocked":
            return state

        tasks = state.get("tasks") or []
        try:
            idx = next(
                i
                for i, t in enumerate(tasks)
                if isinstance(t, dict) and str(t.get("id")) == str(state.get("current_task_id"))
            )
        except StopIteration:
            try:
                idx = next(
                    i
                    for i, t in enumerate(tasks)
                    if isinstance(t, dict) and str(t.get("status", "")).lower() == "needs_review"
                )
            except StopIteration:
                idx = 0
        task = tasks[idx]
        ensure_task_repair_fields(task)

        signature = _current_failure_signature(state)
        general_signature = _general_failure_signature(state)
        all_signatures = [signature, general_signature]
        strategy_scores = _memory_strategy_scores(settings, all_signatures)
        drift_text = "\n".join(
            [
                str(state.get("last_error", "")),
                str(state.get("last_verification_output", "")),
                str(state.get("last_cursor_output", "")),
            ]
        )
        default_strategies = ["contract_preserving", "schema_normalizing", "traceback_root_cause"]
        if _looks_like_alignment_step_mismatch(drift_text):
            default_strategies.insert(0, "task_anchor_first")
        strategies = sorted(
            default_strategies,
            key=lambda s: strategy_scores.get(s, 0.0),
            reverse=True,
        )
        strategy = strategies[round_i % len(strategies)] if strategies else "contract_preserving"

        prev_norm = str(task.get("last_normalized_error_excerpt") or "").strip() or normalized_failure_blob(
            state
        )

        diagnosis = build_diagnosis(
            last_error=str(state.get("last_error", "")),
            verification_output=str(state.get("last_verification_output", "")),
            agent_output=str(state.get("last_cursor_output", "")),
            strategy_name=strategy,
        )
        task["latest_diagnosis"] = diagnosis

        if diagnosis.get("needs_human_review") and maybe_flag_trigger_once(task, "needs_human_clarification"):
            record_escalation_for_task(
                settings,
                state,
                idx,
                "needs_human_clarification",
                force=False,
            )

        if (
            str(diagnosis.get("failure_type") or "") == "json_parse_error"
            and round_i >= 1
            and maybe_flag_trigger_once(task, "json_repair_repeated")
        ):
            record_escalation_for_task(
                settings,
                state,
                idx,
                "json_repair_repeated",
                force=False,
            )

        if int(task.get("repair_unchanged_streak") or 0) >= 2:
            state["repair_stop_reason"] = "unchanged_twice"
            _mark_needs_review(
                settings,
                state,
                idx,
                "Repair stopped: normalized failure signal unchanged across two attempts.",
                escalation_trigger="repair_unchanged_twice",
            )
            save_agent_state(settings, state)
            return state

        project_root = Path(_state_project_root(settings, state)).resolve()

        evidence = merge_evidence(
            str(state.get("last_verification_output", "")),
            str(state.get("last_error", "")),
            str(state.get("last_cursor_output", "")),
        )
        evidence_compact = compact_evidence_for_model(evidence)
        prior_digest = prior_attempts_digest(task)
        repeated_strategies = [
            str(h.get("repair_strategy_snapshot") or "")
            for h in (task.get("repair_history") or [])[-6:]
            if isinstance(h, dict)
        ]

        plan_obj, raw_plan_log = request_repair_plan_json(
            settings,
            diagnosis_compact=json.dumps(diagnosis, ensure_ascii=True)[:8000],
            evidence_compact=evidence_compact,
            prior_attempts_digest=prior_digest,
            strategy_name=strategy,
        )

        use_fallback_only = plan_obj is None
        if plan_obj is None:
            plan_obj = RepairPlanStrict(
                diagnosis_summary="Planner unavailable",
                repair_strategy=strategy,
                files_to_modify=[],
                commands_to_run_after_patch=["python", "-m", "pytest", "-q", "--tb=line"],
                risk_level="medium",
                requires_human_review=False,
            )

        protected_paths = effective_autonomous_protected_paths(settings, project_root)
        plan_obj, stripped_protected = filter_protection_violations_from_plan(
            plan_obj, protected_paths
        )
        focused_py = _focused_pytest_targets(project_root, task)
        plan_obj = plan_obj.model_copy(
            update={
                "commands_to_run_after_patch": merge_verification_commands(
                    plan_obj.commands_to_run_after_patch,
                    focused_py,
                )
            }
        )
        adjustment_notes: list[str] = []
        if stripped_protected:
            adjustment_notes.append(
                "Removed planner targets/commands that violate autonomous protected paths: "
                + "; ".join(stripped_protected[:20])
                + (" …" if len(stripped_protected) > 20 else "")
            )

        score, _sr = score_repair_plan(
            plan_obj,
            diagnosis_failure_type=str(diagnosis.get("failure_type") or "unknown"),
            repeated_strategies=repeated_strategies,
        )

        anti = anti_cheat_flags(plan_obj, raw_plan_log or "", protected_paths=protected_paths)
        if anti:
            diagnosis["needs_human_review"] = True

        if len(plan_obj.files_to_modify) > 5:
            state["repair_stop_reason"] = "too_many_files"
            _mark_needs_review(settings, state, idx, "Repair stopped: plan targeted more than five files.")
            save_agent_state(settings, state)
            return state

        if score < 70:
            task["repair_low_quality_streak"] = int(task.get("repair_low_quality_streak") or 0) + 1
        else:
            task["repair_low_quality_streak"] = 0

        if int(task.get("repair_low_quality_streak") or 0) >= 2 and score < 70:
            state["repair_stop_reason"] = "low_quality_twice"
            _mark_needs_review(
                settings,
                state,
                idx,
                "Repair stopped: repair plan quality below threshold twice consecutively.",
                escalation_trigger="repair_low_quality_twice",
            )
            save_agent_state(settings, state)
            return state

        targeted = load_targeted_sources(
            project_root,
            diagnosis,
            extra_relative_paths=focused_py[:4],
        )

        excerpt_for_fallback = str(diagnosis.get("relevant_error_excerpt") or "")[:4000]
        envelope = build_repair_envelope_text(
            diagnosis=diagnosis,
            plan=plan_obj,
            targeted_sources=targeted,
            prior_digest=prior_digest,
            anti_flags=anti,
            strategy_name=strategy,
            use_fallback_only=use_fallback_only or score < 70,
            failure_excerpt=excerpt_for_fallback,
            protected_relative_paths=list(protected_paths) if protected_paths else None,
            task_title=str(task.get("title", "") or ""),
            system_adjustment_notes=adjustment_notes or None,
        )

        playbook = _playbook_type(
            task,
            str(state.get("last_verification_output", "")),
            _classify_blocker(
                str(state.get("last_error", "")),
                str(state.get("last_verification_output", "")),
                str(state.get("last_cursor_output", "")),
            ),
            last_error=str(state.get("last_error", "")),
            agent_output=str(state.get("last_cursor_output", "")),
        )
        state["autofix_strategy"] = strategy
        state["autofix_playbook"] = playbook
        task["latest_repair_quality_score"] = score
        task["latest_repair_strategy"] = strategy
        state["repair_prompt_envelope"] = envelope
        state["status"] = "running"
        state["tests_failed_streak"] = 0
        tasks[idx] = task
        state["tasks"] = tasks
        save_agent_state(settings, state)

        tips = _memory_tips_for_signatures(settings, all_signatures) + _heuristic_repair_tips(
            str(state.get("last_verification_output", "")),
            str(state.get("last_error", "")),
        )
        deduped_tips: list[str] = []
        for tip in tips:
            if tip not in deduped_tips:
                deduped_tips.append(tip)

        result = run_next_step(settings, repair_mode=True)
        success = result.get("status") != "blocked"

        state_after = load_agent_state(settings)
        tasks_after = state_after.get("tasks") or []
        task_after = tasks_after[idx] if idx < len(tasks_after) else dict(task)
        ensure_task_repair_fields(task_after)

        new_norm = normalized_failure_blob(state_after)
        delta = classify_failure_delta(prev_norm, new_norm)
        task_after["last_normalized_error_excerpt"] = new_norm
        if delta == "unchanged":
            task_after["repair_unchanged_streak"] = int(task_after.get("repair_unchanged_streak") or 0) + 1
        else:
            task_after["repair_unchanged_streak"] = 0

        vo = str(state_after.get("last_verification_output", ""))
        validation_ok = (
            "FAILED" not in vo and "ERROR collecting" not in vo and "exit_code=2" not in vo.lower()
            if vo
            else None
        )

        append_repair_history(
            task_after,
            attempt_number=round_i + 1,
            diagnosis=diagnosis,
            plan=plan_obj,
            patch_summary=str(state_after.get("last_cursor_output", "")),
            files_modified_guess=extract_patch_files_from_stdout(str(state_after.get("last_cursor_output", ""))),
            validation_ok=validation_ok,
            excerpt_after=new_norm[:4000],
            failure_delta=delta,
            quality_score=score,
            strategy=strategy,
        )
        tasks_after[idx] = task_after
        state_after["tasks"] = tasks_after
        save_agent_state(settings, state_after)

        _update_autofix_memory_for_signatures(
            settings,
            signatures=all_signatures,
            used_tips=deduped_tips + [f"strategy:{strategy}", f"playbook:{playbook}", f"delta:{delta}"],
            success=success,
            note=str(result.get("last_error", "")) or "repair attempt completed",
        )
        if success:
            result.pop("autofix_strategy", None)
            result.pop("autofix_playbook", None)
            save_agent_state(settings, result)
            return result

    final_state = load_agent_state(settings)
    final_state.pop("autofix_strategy", None)
    final_state.pop("autofix_playbook", None)
    if final_state.get("status") == "blocked":
        final_state["last_error"] = (
            (str(final_state.get("last_error", "")).strip() + " ")
            + "Auto-fix learning loop exhausted; memory updated for next retry."
        ).strip()
        save_agent_state(settings, final_state)
    return final_state


def pause_autonomous(settings: Settings) -> dict[str, Any]:
    state = load_agent_state(settings)
    state["paused"] = True
    state["status"] = "paused"
    save_agent_state(settings, state)
    return state


def resume_autonomous(settings: Settings) -> dict[str, Any]:
    """Clear pause flag and restore status so Run Next / run-until can proceed."""
    state = load_agent_state(settings)
    if not state.get("paused"):
        return state
    state["paused"] = False
    tasks = state.get("tasks") or []
    if any(str(t.get("status", "")).lower() == "needs_review" for t in tasks):
        state["status"] = "blocked"
        blk = next(
            (t for t in tasks if str(t.get("status", "")).lower() == "needs_review"),
            {},
        )
        if blk.get("id"):
            state["current_task_id"] = str(blk["id"])
    elif _next_incomplete_task_index(state) is None:
        state["status"] = "complete"
        state["current_task_id"] = ""
    elif any(str(t.get("status", "")).lower() == "running" for t in tasks):
        state["status"] = "running"
        rt = next(t for t in tasks if str(t.get("status", "")).lower() == "running")
        state["current_task_id"] = str(rt.get("id", ""))
    else:
        state["status"] = "running"
    save_agent_state(settings, state)
    return state


def reset_autonomous_state(settings: Settings) -> dict[str, Any]:
    state = _new_state(settings)
    save_agent_state(settings, state)
    return state


def _task_progress_counts(state: dict[str, Any]) -> dict[str, int]:
    tasks = state.get("tasks") or []
    pending = running = complete = needs_review = 0
    for raw in tasks:
        if not isinstance(raw, dict):
            pending += 1
            continue
        s = str(raw.get("status", "pending") or "pending").lower()
        if s == "complete":
            complete += 1
        elif s == "running":
            running += 1
        elif s == "needs_review":
            needs_review += 1
        else:
            pending += 1
    return {
        "tasks_total": len(tasks),
        "tasks_pending": pending,
        "tasks_running": running,
        "tasks_complete": complete,
        "tasks_needs_review": needs_review,
    }


def _repair_inspector_from_state(state: dict[str, Any]) -> dict[str, Any]:
    tid = str(state.get("current_task_id") or "")
    task_cur = next(
        (t for t in state.get("tasks") or [] if isinstance(t, dict) and str(t.get("id")) == tid),
        {},
    )
    if not isinstance(task_cur, dict) or not tid:
        return {}
    ld = task_cur.get("latest_diagnosis")
    ft = ld.get("failure_type") if isinstance(ld, dict) else None
    return {
        "failure_type": ft,
        "repair_attempt_count": len(task_cur.get("repair_history") or [])
        if isinstance(task_cur.get("repair_history"), list)
        else 0,
        "latest_repair_strategy": task_cur.get("latest_repair_strategy"),
        "latest_quality_score": task_cur.get("latest_repair_quality_score"),
        "repair_stop_reason": state.get("repair_stop_reason"),
        "repair_unchanged_streak": int(task_cur.get("repair_unchanged_streak") or 0),
        "repair_low_quality_streak": int(task_cur.get("repair_low_quality_streak") or 0),
    }


def status_payload(settings: Settings) -> dict[str, Any]:
    state = load_agent_state(settings)
    if _recover_stale_patch_executor_running_on_status(settings, state):
        save_agent_state(settings, state)
    cmd = ""
    cmd_error = ""
    runner = str(state.get("runner") or settings.autonomous_runner)
    if runner in {"cursor", "auto"}:
        try:
            cmd = resolve_cursor_command(settings.cursor_cli_command or state.get("cursor_cli_command", ""))
        except Exception as exc:
            cmd_error = str(exc)
    state["resolved_cursor_cli"] = cmd
    state["cursor_cli_error"] = cmd_error
    state["runner"] = runner
    state["project_root"] = str(_state_project_root(settings, state))
    state.update(_task_progress_counts(state))
    state["repair_inspector"] = _repair_inspector_from_state(state)
    tid = str(state.get("current_task_id") or "")
    task_esc = next(
        (t for t in state.get("tasks") or [] if isinstance(t, dict) and str(t.get("id")) == tid),
        {},
    )
    state["escalation_inspector"] = {
        "current_task_escalation_status": task_esc.get("escalation_status"),
        "latest_escalation_summary": task_esc.get("latest_escalation_summary")
        or state.get("last_escalation_summary"),
        "latest_escalation_path": task_esc.get("latest_escalation_path")
        or state.get("last_escalation_path"),
        "last_escalated_at": task_esc.get("last_escalated_at"),
        "escalation_count": task_esc.get("escalation_count", 0),
        "total_escalations": state.get("total_escalations", 0),
        "active_escalation": state.get("active_escalation"),
        "last_escalation_event": state.get("last_escalation_event"),
        "blocked_or_review": state.get("status") == "blocked"
        or str(task_esc.get("status") or "").lower() == "needs_review",
    }
    state["pending_chat_inject"] = read_pending_cursor_chat_inject_status(settings)
    state["run_topic_lock_active"] = autonomous_run_topic_lock_active(state)
    state["env_anthropic_configured"] = bool((settings.anthropic_api_key or "").strip())
    state["env_openai_for_schema_configured"] = bool(
        (settings.feature_schema_openai_api_key or settings.openai_api_key or "").strip()
    )
    return state


def _tail_text(text: str, max_chars: int) -> str:
    t = text or ""
    if len(t) <= max_chars:
        return t
    omitted = len(t) - max_chars
    return f"... ({omitted} earlier characters omitted)\n\n" + t[-max_chars:]


def live_code_payload(settings: Settings) -> dict[str, Any]:
    """Text views of the latest agent step for a terminal-style UI.

    The runners batch work (Cursor CLI, OpenAI patch planner, etc.); new text
    generally appears after each step completes, not token-by-token.
    """
    state = load_agent_state(settings)
    task_id = str(state.get("current_task_id") or "")
    task: dict[str, Any] = {}
    for raw in state.get("tasks") or []:
        if isinstance(raw, dict) and str(raw.get("id")) == task_id:
            task = raw
            break

    agent_global = str(state.get("last_cursor_output") or "")
    agent_task = str(task.get("last_cursor_output") or "")
    display_agent = agent_task if (task_id and agent_task.strip()) else agent_global

    verify_global = str(state.get("last_verification_output") or "")
    verify_task = str(task.get("verification_notes") or "")
    display_verify = verify_task if (task_id and verify_task.strip()) else verify_global

    prompt = str(task.get("last_prompt") or "")
    rev_raw = f"{task_id}|{state.get('last_updated_utc')}|{len(display_agent)}|{len(display_verify)}|{len(prompt)}"
    revision = hashlib.sha256(rev_raw.encode("utf-8")).hexdigest()[:16]

    counts = _task_progress_counts(state)
    guardrail_in_output = _hit_protected_path_blocker(display_agent)
    autonomy_st = str(state.get("status", "") or "").lower()
    task_st = str(task.get("status", "") or "").lower()
    runner = str(state.get("runner") or "")
    waiting_for_step_output = (
        not guardrail_in_output
        and autonomy_st == "running"
        and not (display_agent or "").strip()
        and (
            task_st == "running"
            or int(counts.get("tasks_running") or 0) > 0
        )
    )
    last_up = state.get("last_updated_utc")
    last_up_note = f"\nLast state save (UTC): {last_up}" if last_up else ""
    waiting_callout = ""
    if waiting_for_step_output:
        waiting_callout = (
            f"Step is in flight ({runner or 'runner'} · {task_id or 'task'}). "
            "Agent output, verification, and the prompt panel refresh only after this step finishes and state is saved—"
            "there is no token stream here.\n\n"
            "If this message stays up for many minutes: confirm the LLM (e.g. Ollama) is running, "
            "watch the server terminal for errors, and consider Pause / Reset if the process is stuck."
            + last_up_note
        )

    return {
        "revision": revision,
        "status": state.get("status"),
        "paused": bool(state.get("paused")),
        **counts,
        "guardrail_block_in_output": guardrail_in_output,
        "autonomy_halted": bool(guardrail_in_output)
        or str(state.get("status", "")).lower() == "blocked"
        or str(task.get("status", "")).lower() == "needs_review",
        "runner": state.get("runner"),
        "current_task_id": task_id or None,
        "task_title": task.get("title"),
        "task_status": task.get("status"),
        "waiting_for_step_output": waiting_for_step_output,
        "state_last_updated_utc": last_up,
        "waiting_callout": waiting_callout,
        "last_error_excerpt": _tail_text(str(state.get("last_error") or ""), 4000),
        "agent_output": _tail_text(display_agent, 24000),
        "verification": _tail_text(display_verify, 16000),
        "prompt": _tail_text(prompt, 8000),
        "stream_note": (
            "Updates when each autonomy step finishes (model + patches + verification). "
            "During a long step, text stays on the last completed step—like a batched agent run, not live tokens."
        ),
        "effective_openai_compatible_model": resolve_openai_compatible_chat_model(settings),
        "configured_openai_chat_model": settings.openai_chat_model,
        "openai_chat_base_url_configured": bool((settings.openai_chat_base_url or "").strip()),
        "ollama_style_chat_model": settings.chat_model,
        "repair_inspector": _repair_inspector_from_state(state),
    }


def failure_debug_payload(settings: Settings) -> dict[str, Any]:
    """Return parsed failure/debug context for observability."""
    state = load_agent_state(settings)
    verification_text = str(state.get("last_verification_output", ""))
    details = _extract_failure_details(verification_text)
    task = next(
        (t for t in state.get("tasks", []) if str(t.get("id")) == str(state.get("current_task_id"))),
        {},
    )
    blocker_type = _classify_blocker(
        str(state.get("last_error", "")),
        verification_text,
        str(state.get("last_cursor_output", "")),
    )
    playbook = _playbook_type(
        task if isinstance(task, dict) else {},
        verification_text,
        blocker_type,
        last_error=str(state.get("last_error", "")),
        agent_output=str(state.get("last_cursor_output", "")),
    )
    current_signature = _current_failure_signature(state)
    general_signature = _general_failure_signature(state)
    strategy_scores = _memory_strategy_scores(settings, [current_signature, general_signature])
    return {
        "status": state.get("status"),
        "current_task_id": state.get("current_task_id"),
        "task_title": (task or {}).get("title"),
        "blocker_type": blocker_type,
        "playbook": playbook,
        "failure_fingerprint": _failure_fingerprint_from_text(verification_text),
        "failure_details": details,
        "current_signature": current_signature,
        "general_signature": general_signature,
        "strategy_scores": strategy_scores,
        "last_error": state.get("last_error", ""),
        "last_updated_utc": state.get("last_updated_utc"),
    }
