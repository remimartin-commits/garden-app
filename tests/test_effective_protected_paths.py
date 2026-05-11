"""Regression: isolated project roots must not inherit host protected-path rules."""

from pathlib import Path

from app.config import Settings, effective_autonomous_protected_paths, effective_autonomous_write_file_denylist
from app.patch_executor import execute_patch_plan


def test_same_root_keeps_blocklist():
    s = Settings()
    root = s.project_root.resolve()
    paths = effective_autonomous_protected_paths(s, root)
    assert "app/entities.py" in paths
    assert "app/main.py" in paths


def test_different_root_allows_all_edits_when_vertical_generic():
    s = Settings(autonomous_workspace_domain="generic")
    isolated = Path("./outputs/fake-run").resolve()
    paths = effective_autonomous_protected_paths(s, isolated)
    assert paths == []


def test_different_root_allows_all_edits_when_vertical_pool():
    s = Settings(autonomous_workspace_domain="pool")
    isolated = Path("./outputs/fake-run").resolve()
    paths = effective_autonomous_protected_paths(s, isolated)
    assert paths == []


def test_write_file_denylist_always_includes_entities():
    s = Settings()
    deny = effective_autonomous_write_file_denylist(s)
    assert "app/entities.py" in deny
    assert "app/main.py" in deny


def test_write_file_blocked_on_denylist_even_when_not_protected(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "entities.py").write_text("x = 1\n", encoding="utf-8")
    res = execute_patch_plan(
        project_root=tmp_path,
        plan={
            "summary": "bad",
            "edits": [
                {"action": "write_file", "path": "app/entities.py", "content": "gone"},
                {"action": "replace_in_file", "path": "app/entities.py", "old": "x = 1", "new": "x = 2"},
            ],
            "commands": [],
        },
        command_timeout_seconds=30,
        protected_paths=[],
        write_file_denylist=["app/entities.py"],
    )
    assert "blocked write_file" in res.errors[0]
    assert any("replace_in_file:app/entities.py" in e for e in res.applied_edits)
