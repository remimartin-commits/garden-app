"""Topic / schema guardrails for autonomous runs."""

import hashlib
from pathlib import Path

import pytest

from app.autonomous_loop import (
    _assert_locked_schema_unchanged,
    autonomous_run_topic_lock_active,
)


def test_topic_lock_active_when_status_starting():
    st = {"status": "starting", "schema_path": "", "tasks": []}
    assert autonomous_run_topic_lock_active(st) is True


def test_topic_lock_active_when_schema_and_incomplete_tasks():
    st = {
        "schema_path": "/tmp/schema.json",
        "status": "running",
        "tasks": [{"id": "1", "status": "pending"}],
    }
    assert autonomous_run_topic_lock_active(st) is True


def test_topic_lock_inactive_when_run_complete():
    st = {
        "schema_path": "/tmp/schema.json",
        "status": "complete",
        "tasks": [{"id": "1", "status": "complete"}],
    }
    assert autonomous_run_topic_lock_active(st) is False


def test_topic_lock_active_when_schema_but_no_tasks():
    st = {"schema_path": "/x/schema.json", "status": "idle", "tasks": []}
    assert autonomous_run_topic_lock_active(st) is True


def test_assert_locked_schema_unchanged_skips_when_no_hash():
    st = {"locked_run_schema_sha256": "", "schema_path": "/nonexistent/path.json"}
    _assert_locked_schema_unchanged(st)


def test_assert_locked_schema_unchanged_detects_mutation(tmp_path: Path):
    p = tmp_path / "schema.json"
    p.write_text('{"schema": {"name": "A"}}', encoding="utf-8")
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    st = {"locked_run_schema_sha256": digest, "schema_path": str(p)}
    _assert_locked_schema_unchanged(st)
    p.write_text('{"schema": {"name": "B"}}', encoding="utf-8")
    with pytest.raises(ValueError, match="changed on disk"):
        _assert_locked_schema_unchanged(st)
