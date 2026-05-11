"""Unit tests for repair extraction, diagnosis, quality, and JSON helpers."""

from __future__ import annotations

from app.repair_diagnose import build_diagnosis
from app.repair_extract import extract_pytest_signals, merge_evidence
from app.repair_quality import (
    RepairPlanStrict,
    anti_cheat_flags,
    classify_failure_delta,
    filter_protection_violations_from_plan,
    parse_repair_plan_json,
    score_repair_plan,
)
from app.repair_flow import merge_verification_commands


def test_pytest_error_extraction_collects_failed_lines():
    out = """
============================= test session starts =============================
FAILED tests/test_x.py::test_a - AssertionError: assert 1 == 2
FAILED tests/test_y.py::test_b - RuntimeError: boom
"""
    sig = extract_pytest_signals(out)
    assert "tests/test_x.py::test_a" in sig["failing_tests"]


def test_merge_evidence_has_pytest_key():
    blob = merge_evidence("FAILED tests/foo.py::t\n", "", "")
    assert blob["pytest"]["failing_tests"]


def test_failure_delta_unchanged_vs_changed():
    assert classify_failure_delta("hello world", "hello world") == "unchanged"
    assert classify_failure_delta("a", "b") == "changed"


def test_parse_repair_plan_json_strips_double_slash_comments():
    raw = """{
  "diagnosis_summary":"x",
  "repair_strategy":"y",
  "files_to_modify":[],
  "commands_to_run_after_patch":["pytest -q"], // note
  "risk_level":"low",
  "requires_human_review":false
}"""
    p = parse_repair_plan_json(raw)
    assert p is not None
    assert p.commands_to_run_after_patch == ["pytest -q"]


def test_parse_repair_plan_json_accepts_fence():
    raw = """```json
{"diagnosis_summary":"x","repair_strategy":"y","files_to_modify":[],"commands_to_run_after_patch":[],"risk_level":"low","requires_human_review":false}
```"""
    p = parse_repair_plan_json(raw)
    assert p is not None
    assert p.diagnosis_summary == "x"


def test_repair_quality_scores_high_for_focused_plan():
    plan = RepairPlanStrict(
        diagnosis_summary="d",
        repair_strategy="fix import",
        files_to_modify=[],
        commands_to_run_after_patch=["pytest -q"],
        risk_level="low",
        requires_human_review=False,
    )
    score, _ = score_repair_plan(
        plan,
        diagnosis_failure_type="test_failure",
        repeated_strategies=[],
    )
    assert score >= 70


def test_repair_quality_penalizes_many_files():
    files = [
        {"path": f"f{i}.py", "reason": "r", "change_summary": "c"}
        for i in range(6)
    ]
    plan = RepairPlanStrict(
        diagnosis_summary="d",
        repair_strategy="big bang",
        files_to_modify=files,
        commands_to_run_after_patch=[],
        risk_level="high",
        requires_human_review=False,
    )
    score, reasons = score_repair_plan(
        plan,
        diagnosis_failure_type="test_failure",
        repeated_strategies=[],
    )
    assert score < 70
    assert "too_many_files" in reasons


def test_anti_cheat_detects_skip_pattern():
    plan = RepairPlanStrict(
        diagnosis_summary="",
        repair_strategy="pytest.skip all",
        files_to_modify=[],
        commands_to_run_after_patch=[],
        risk_level="low",
        requires_human_review=False,
    )
    flags = anti_cheat_flags(plan, "we should pytest.skip this")
    assert "pytest_skip" in flags


def test_filter_protection_violations_from_plan_drops_entities():
    plan = RepairPlanStrict(
        diagnosis_summary="d",
        repair_strategy="touch core",
        files_to_modify=[
            {"path": "app/entities.py", "reason": "bad", "change_summary": "x"},
            {"path": "app/foo.py", "reason": "ok", "change_summary": "y"},
        ],
        commands_to_run_after_patch=["python -m pytest app/entities.py", "python -m pytest tests/test_a.py"],
        risk_level="low",
        requires_human_review=False,
    )
    sanitized, removed = filter_protection_violations_from_plan(
        plan, ["app/entities.py"]
    )
    assert len(sanitized.files_to_modify) == 1
    assert sanitized.files_to_modify[0].path == "app/foo.py"
    assert "entities.py" in removed[0]
    assert len(sanitized.commands_to_run_after_patch) == 1
    assert "test_a.py" in sanitized.commands_to_run_after_patch[0]


def test_merge_verification_commands_prepends_focused():
    cmds = merge_verification_commands(
        ["python -m pytest -q"],
        ["tests/a.py", "tests/b.py"],
    )
    assert cmds[0].startswith("python -m pytest -q --tb=line")
    assert "tests/a.py" in cmds[0]
    assert "tests/b.py" in cmds[0]
    assert "python -m pytest -q" in cmds[1:]


def test_build_diagnosis_json_parse_failure_type():
    d = build_diagnosis(
        last_error="Expecting value: line 1 column 1",
        verification_output="",
        agent_output="",
        strategy_name="contract_preserving",
    )
    assert d["failure_type"] == "json_parse_error"


def test_build_diagnosis_pytest_collection_beats_stale_json_error():
    """Stale patch_executor JSON errors must not hide pytest collection failures."""
    d = build_diagnosis(
        last_error="Expecting value: line 1 column 1",
        verification_output=(
            "ERROR collecting tests/test_x.py\n"
            "AttributeError: type object 'Inquiry' has no attribute 'model_json_schema'"
        ),
        agent_output="",
        strategy_name="contract_preserving",
    )
    assert d["failure_type"] == "test_failure"
    hints = d.get("repair_hints") or []
    assert hints
    assert "model_json_schema" in hints[0]


def test_build_diagnosis_model_json_schema_hints_without_collection_banner():
    d = build_diagnosis(
        last_error="",
        verification_output=(
            "FAILED tests/test_a.py::t - AssertionError\n"
            "ERROR at setup of test_a: AttributeError: type object 'Inquiry' has no attribute "
            "'model_json_schema'"
        ),
        agent_output="",
        strategy_name="contract_preserving",
    )
    assert d["failure_type"] == "test_failure"
    assert d.get("repair_hints")


def test_playbook_lesson_entity_fields_import():
    """Curated lessons (repair_playbook_lessons) surface via repair_hints."""
    d = build_diagnosis(
        last_error="",
        verification_output=(
            "ImportError while importing test module.\n"
            "cannot import name 'String' from 'app.entity_fields'"
        ),
        agent_output="",
        strategy_name="retry",
    )
    hints = d.get("repair_hints") or []
    blob = " ".join(hints).lower()
    assert "entity_fields" in blob
    assert "placeholder" in blob or "stub" in blob or "restore" in blob

