"""Escalation / Personality AI layer tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import Settings
from app.escalation_flow import (
    hydrate_escalation_state,
    mark_escalation_resolved,
    record_escalation_for_task,
    resume_after_manual_fix,
)
from app.escalation_models import default_constraints
from app.escalation_writer import generate_escalation_message
from app.autonomous_loop import VerificationResult


def _minimal_state(tmp: Path) -> dict:
    return {
        "status": "blocked",
        "paused": False,
        "schema_path": "",
        "project_root": str(tmp),
        "current_task_id": "task-1",
        "tasks": [
            {
                "id": "task-1",
                "title": "Entity: Inquiry",
                "description": "Implement entity Inquiry and required fields.",
                "status": "needs_review",
                "repair_history": [
                    {
                        "attempt_number": 1,
                        "failure_delta": "unchanged",
                        "quality_score": 65,
                        "repair_strategy_snapshot": "contract_preserving",
                        "validation_result": "fail",
                    },
                    {
                        "attempt_number": 2,
                        "failure_delta": "unchanged",
                        "quality_score": 62,
                        "repair_strategy_snapshot": "schema_normalizing",
                        "validation_result": "fail",
                    },
                ],
                "latest_diagnosis": {
                    "failure_type": "test_failure",
                    "failing_command": "pytest tests/test_quote_enquiries.py::test_submit -q",
                    "relevant_error_excerpt": "AssertionError: assert response.status_code == 422",
                    "affected_files": ["app/quote_enquiries.py", "tests/test_quote_enquiries.py"],
                    "suspected_root_cause": "Endpoint returns 404 instead of validation error.",
                },
                "verification_notes": "FAILED tests/test_quote_enquiries.py::test_submit\nAssertionError",
            }
        ],
        "last_error": "blocked",
        "last_verification_output": "FAILED tests/test_quote_enquiries.py::test_submit",
        "last_cursor_output": "[stderr]\nblocked edit\n",
    }


def test_escalation_message_fields_and_constraints():
    task = _minimal_state(Path("."))["tasks"][0]
    msg = generate_escalation_message(
        task=task,
        schema={"entities": [{"name": "Inquiry"}], "api_endpoints": [{}, {}, {}]},
        repair_history=task["repair_history"],
        latest_diagnosis=task["latest_diagnosis"],
        latest_error_excerpt="AssertionError: assert 404 == 422",
        project_context="/tmp/project",
        run_logs="FAILED test_x\n" * 50,
        trigger="repair_unchanged_twice",
    )
    assert "Inquiry" in msg.current_task
    assert msg.expected_behavior
    assert msg.actual_behavior
    assert msg.failure_type == "test_failure"
    assert "AssertionError" in msg.key_error_excerpt or "422" in msg.key_error_excerpt
    assert len(msg.attempted_fixes) >= 2
    assert msg.constraints == default_constraints()
    assert msg.suggested_next_steps
    assert "pytest" in msg.handoff_prompt or "inspect" in msg.handoff_prompt.lower()
    assert "Hi, I'm the autonomous codebot" in msg.handoff_prompt


def test_escalation_prepends_repair_hints():
    task = _minimal_state(Path("."))["tasks"][0]
    diag = dict(task["latest_diagnosis"])
    diag["repair_hints"] = [
        "Hint A: restore Pydantic model_json_schema contract for entities imported by feature_schema."
    ]
    msg = generate_escalation_message(
        task=task,
        schema=None,
        repair_history=[],
        latest_diagnosis=diag,
        latest_error_excerpt="",
        project_context=".",
        run_logs="",
        trigger="test",
    )
    assert msg.suggested_next_steps
    assert msg.suggested_next_steps[0].startswith("Hint A:")


def test_handoff_inline_not_huge():
    huge = "x\n" * 50000
    msg = generate_escalation_message(
        task={"id": "t", "title": "T", "description": "D"},
        schema=None,
        repair_history=[],
        latest_diagnosis={"relevant_error_excerpt": huge[:100000]},
        latest_error_excerpt=huge,
        project_context=".",
        run_logs=huge,
        trigger="test",
    )
    assert len(msg.key_error_excerpt) <= 2600
    assert len(msg.handoff_prompt) < 20000


def test_record_escalation_updates_task_paths(tmp_path: Path):
    settings = Settings(user_data_dir=tmp_path)
    state = _minimal_state(tmp_path)
    hydrate_escalation_state(state)
    out = record_escalation_for_task(
        settings,
        state,
        0,
        "autonomous_auto_fix_budget_exhausted",
        force=True,
    )
    assert out and out.get("ok")
    path = Path(out["path"])
    assert path.is_file()
    assert state["tasks"][0]["latest_escalation_path"]
    assert state["tasks"][0]["escalation_status"] == "generated"
    assert state["total_escalations"] >= 1
    pending = tmp_path / "escalations" / "pending_chat_inject.json"
    assert pending.is_file()
    pend_j = json.loads(pending.read_text(encoding="utf-8"))
    assert "Hi, I'm the autonomous codebot" in pend_j.get("handoff_markdown", "")
    raw = path.read_text(encoding="utf-8")
    assert "autonomous codebot" in raw.lower()
    assert len(raw) < 500_000


def test_mark_escalation_resolved(tmp_path: Path):
    agent_path = tmp_path / "agent_state.json"
    state = _minimal_state(tmp_path)
    hydrate_escalation_state(state)
    agent_path.write_text(json.dumps(state), encoding="utf-8")
    settings = Settings(user_data_dir=tmp_path)
    st2 = mark_escalation_resolved(settings, "task-1", resolution_summary="done")
    task = next(t for t in st2["tasks"] if t["id"] == "task-1")
    assert task["escalation_status"] == "resolved"
    assert task.get("escalation_resolution")


def test_resume_after_manual_fix_passing(monkeypatch, tmp_path: Path):
    agent_path = tmp_path / "agent_state.json"
    state = _minimal_state(tmp_path)
    state["tasks"][0]["escalation_failure_signature_at_generation"] = "oldsig"
    hydrate_escalation_state(state)
    agent_path.write_text(json.dumps(state), encoding="utf-8")
    settings = Settings(user_data_dir=tmp_path)

    def fake_verify(*_a, **_k):
        return VerificationResult(
            checks_run=["pytest"],
            output="3 passed in 0.1s",
            success=True,
            failures=[],
        )

    monkeypatch.setattr(
        "app.autonomous_loop.run_project_verification",
        fake_verify,
    )
    st = resume_after_manual_fix(settings, "task-1")
    task = next(t for t in st["tasks"] if t["id"] == "task-1")
    assert task["escalation_status"] == "resolved"
    assert st["status"] == "running"


def test_resume_after_manual_fix_still_failing(monkeypatch, tmp_path: Path):
    agent_path = tmp_path / "agent_state.json"
    state = _minimal_state(tmp_path)
    state["tasks"][0]["escalation_failure_signature_at_generation"] = "AAA"
    hydrate_escalation_state(state)
    agent_path.write_text(json.dumps(state), encoding="utf-8")
    settings = Settings(user_data_dir=tmp_path)

    def fake_verify(*_a, **_k):
        return VerificationResult(
            checks_run=["pytest"],
            output="FAILED tests/test_x.py::t\nAssertionError",
            success=False,
            failures=["pytest"],
        )

    monkeypatch.setattr(
        "app.autonomous_loop.run_project_verification",
        fake_verify,
    )
    monkeypatch.setattr(
        "app.repair_flow.normalized_failure_blob",
        lambda _s: "AAA",
    )
    st = resume_after_manual_fix(settings, "task-1")
    assert st.get("last_escalation_path")


def test_generate_after_unrelated_trigger_once(tmp_path: Path):
    settings = Settings(user_data_dir=tmp_path)
    state = _minimal_state(tmp_path)
    hydrate_escalation_state(state)
    from app.escalation_flow import maybe_flag_trigger_once

    assert maybe_flag_trigger_once(state["tasks"][0], "unrelated_suite_failure") is True
    assert maybe_flag_trigger_once(state["tasks"][0], "unrelated_suite_failure") is False
