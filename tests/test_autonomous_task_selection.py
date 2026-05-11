"""Task selection and stale-running recovery helpers."""

from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.autonomous_loop import (
    _all_tasks_complete,
    _entity_schema_task_prompt_addon,
    _next_runnable_task_index,
    _recover_stale_patch_executor_running_on_status,
    _repair_focus_task_index,
)


def test_entity_schema_prompt_addon_for_entity_titles():
    text = _entity_schema_task_prompt_addon({"title": "Entity: BusinessProfile"})
    assert "from app.entities import" in text
    assert "exactly one class" in text.lower()


def test_entity_schema_prompt_addon_empty_for_non_entity():
    assert _entity_schema_task_prompt_addon({"title": "API: GET /foo"}) == ""


def test_next_runnable_skips_needs_review():
    state = {
        "tasks": [
            {"id": "a", "status": "needs_review"},
            {"id": "b", "status": "pending"},
        ]
    }
    assert _next_runnable_task_index(state) == 1


def test_next_runnable_none_when_only_needs_review():
    state = {
        "tasks": [
            {"id": "a", "status": "needs_review"},
        ]
    }
    assert _next_runnable_task_index(state) is None
    assert _all_tasks_complete(state) is False


def test_all_tasks_complete():
    state = {
        "tasks": [
            {"id": "a", "status": "complete"},
            {"id": "b", "status": "complete"},
        ]
    }
    assert _all_tasks_complete(state) is True


def test_repair_focus_prefers_current_task_id():
    state = {
        "current_task_id": "b",
        "tasks": [
            {"id": "a", "status": "needs_review"},
            {"id": "b", "status": "needs_review"},
        ],
    }
    assert _repair_focus_task_index(state) == 1


def test_repair_focus_falls_back_to_first_needs_review():
    state = {
        "current_task_id": "",
        "tasks": [
            {"id": "a", "status": "needs_review"},
            {"id": "b", "status": "pending"},
        ],
    }
    assert _repair_focus_task_index(state) == 0


def test_stale_patch_executor_running_is_blocked_on_status_poll():
    stale_sec = 400
    settings = Settings(patch_executor_stale_step_seconds=stale_sec)
    old = datetime.now(timezone.utc) - timedelta(seconds=stale_sec + 120)
    state = {
        "status": "running",
        "paused": False,
        "runner": "patch_executor",
        "last_updated_utc": old.isoformat(),
        "tasks": [{"id": "task-1", "status": "running"}],
        "last_error": "",
    }
    changed = _recover_stale_patch_executor_running_on_status(settings, state)
    assert changed is True
    assert state["status"] == "blocked"
    assert state["tasks"][0]["status"] == "needs_review"
    assert "Recovered stale running state automatically" in state["last_error"]


def test_recent_patch_executor_running_is_not_touched():
    settings = Settings()
    fresh = datetime.now(timezone.utc) - timedelta(seconds=10)
    state = {
        "status": "running",
        "paused": False,
        "runner": "patch_executor",
        "last_updated_utc": fresh.isoformat(),
        "tasks": [{"id": "task-1", "status": "running"}],
    }
    changed = _recover_stale_patch_executor_running_on_status(settings, state)
    assert changed is False
    assert state["status"] == "running"


def test_focused_pytest_includes_test_entities_for_schema_entity_tasks(tmp_path):
    from app.autonomous_loop import _focused_pytest_targets, _task_related_test_markers

    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "tests" / "test_entities.py").write_text("# stub\n", encoding="utf-8")
    (tmp_path / "tests" / "test_page_entity.py").write_text("# stub\n", encoding="utf-8")
    task = {"title": "Entity: BusinessProfile", "description": "Implement entity BusinessProfile."}
    targets = _focused_pytest_targets(tmp_path, task)
    assert "tests/test_entities.py" in targets
    assert "tests/test_page_entity.py" not in targets
    markers = _task_related_test_markers(task)
    assert "test_entities" in markers
    assert "test_page_entity" not in markers


def test_entity_task_pytest_pass_overrules_alignment_guard():
    from app.autonomous_loop import VerificationResult, _entity_task_pytest_pass_overrules_alignment

    task = {"title": "Entity: BusinessProfile", "description": "x"}
    ok = VerificationResult(
        checks_run=["pytest (focused)"],
        output="1 passed",
        success=True,
        failures=[],
    )
    assert _entity_task_pytest_pass_overrules_alignment(task, ok) is True
    bad = VerificationResult(
        checks_run=["pytest (focused)"],
        output="FAILED",
        success=False,
        failures=["pytest (focused)"],
    )
    assert _entity_task_pytest_pass_overrules_alignment(task, bad) is False
    non_entity = {"title": "Endpoint: GET /api/foo", "description": ""}
    assert _entity_task_pytest_pass_overrules_alignment(non_entity, ok) is False
