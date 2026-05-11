# Regression: patch planner output may include // comments; JSON must still parse.

from __future__ import annotations

from app.agent_runner import _parse_json_block, _strip_line_comments_outside_strings


def test_strip_line_comments_outside_strings_keeps_url_in_string():
    raw = '{"commands": ["curl https://example.com/x", "y"]}'
    assert _strip_line_comments_outside_strings(raw) == raw


def test_strip_removes_slash_slash_after_json_string():
    raw = (
        '{\n  "commands": [\n'
        '    "pytest a.py", // note here\n'
        '    "pytest b.py"\n  ]\n}'
    )
    stripped = _strip_line_comments_outside_strings(raw)
    data = _parse_json_block(stripped)
    assert data["commands"] == ["pytest a.py", "pytest b.py"]


def test_parse_json_block_skips_leading_prose_before_brace():
    block = """Sure — here is the patch plan.

{"summary": "fix thing", "edits": [], "commands": ["pytest -q"]} trailing junk ignored"""
    data = _parse_json_block(block)
    assert data["summary"] == "fix thing"
    assert data["commands"] == ["pytest -q"]


def test_parse_json_block_handles_code_fence_and_comments():
    block = """```json
{
  "summary": "x",
  "edits": [],
  "commands": ["pytest t.py", // oops
  "pytest u.py"]
}
```"""
    data = _parse_json_block(block)
    assert data["summary"] == "x"
    assert data["commands"] == ["pytest t.py", "pytest u.py"]
