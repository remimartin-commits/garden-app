"""Extract concise failure signals from noisy tool output."""

from __future__ import annotations

import json
import re
from typing import Any


def normalize_excerpt(text: str, max_chars: int = 2400) -> str:
    t = " ".join((text or "").split())
    return t[:max_chars]


def extract_pytest_signals(output: str) -> dict[str, Any]:
    """Pull pytest-focused lines without full log."""
    lines = output.splitlines()
    failing_tests: list[str] = []
    for line in lines:
        m = re.match(r"^FAILED\s+(\S+)", line.strip())
        if m:
            failing_tests.append(m.group(1))
        m2 = re.match(r"^ERROR\s+(?:at setup of\s+)?(\S+)", line.strip())
        if m2 and m2.group(1) not in failing_tests:
            failing_tests.append(m2.group(1))

    file_refs: list[str] = []
    for pat in (
        r'File "([^"]+\.py)", line (\d+)',
        r"^(\S+\.py):\d+:",
        r"app\\[^\s]+\.py",
        r"app/[^\s]+\.py",
    ):
        for m in re.finditer(pat, output, re.MULTILINE):
            file_refs.append(m.group(1) if m.lastindex else m.group(0))

    assertion = ""
    for line in lines:
        if "AssertionError" in line or "assert " in line.lower():
            assertion = line.strip()
            break

    short_summary = ""
    idx = output.lower().find("short test summary info")
    if idx >= 0:
        short_summary = output[idx : idx + 2500]
    else:
        short_summary = "\n".join(lines[-80:])

    return {
        "kind": "pytest",
        "failing_tests": failing_tests[:24],
        "file_refs": list(dict.fromkeys(file_refs))[:24],
        "assertion_line": assertion[:800],
        "short_summary": short_summary[:4000],
        "command_hint": "pytest",
    }


def extract_npm_signals(output: str) -> dict[str, Any]:
    lines = output.splitlines()
    errs: list[str] = []
    for line in lines:
        low = line.lower()
        if "error" in low or "failed" in low or "ERR!" in line:
            errs.append(line.strip()[:500])
        if len(errs) >= 12:
            break
    return {"kind": "npm", "error_lines": errs[:12], "tail": "\n".join(lines[-40:])[:3000]}


def extract_typescript_signals(output: str) -> dict[str, Any]:
    lines = output.splitlines()
    hits: list[str] = []
    for line in lines:
        if ".ts" in line or ".tsx" in line:
            if "error TS" in line or ": error" in line.lower():
                hits.append(line.strip()[:500])
    return {"kind": "typescript", "lines": hits[:16]}


def extract_python_traceback(output: str) -> dict[str, Any]:
    blocks: list[str] = []
    current: list[str] = []
    for line in output.splitlines():
        if line.strip().startswith("Traceback"):
            if current:
                blocks.append("\n".join(current))
            current = [line]
        elif current:
            current.append(line)
            if len(current) > 60:
                blocks.append("\n".join(current))
                current = []
    if current:
        blocks.append("\n".join(current))
    root = blocks[-1][:3500] if blocks else ""
    file_line = ""
    for m in re.finditer(r'File "([^"]+)", line (\d+)', output):
        file_line = f"{m.group(1)}:{m.group(2)}"
    return {"kind": "python_tb", "last_traceback": root, "last_file_line": file_line}


def extract_json_parse_error(message: str) -> dict[str, Any]:
    raw = message or ""
    preview = raw[:1500]
    return {"kind": "json_parse", "message": preview}


def extract_subprocess_error(output: str) -> dict[str, Any]:
    head = "\n".join(output.splitlines()[:30])
    tail = "\n".join(output.splitlines()[-40:])
    return {"kind": "subprocess", "head": head[:2000], "tail": tail[:2000]}


def merge_evidence(
    verification_output: str,
    last_error: str,
    agent_output: str,
) -> dict[str, Any]:
    """Route to extractors and merge."""
    blob = "\n".join([verification_output or "", last_error or "", agent_output or ""])
    merged: dict[str, Any] = {
        "pytest": extract_pytest_signals(verification_output or blob),
        "npm": extract_npm_signals(blob),
        "typescript": extract_typescript_signals(blob),
        "traceback": extract_python_traceback(blob),
    }
    if "Expecting value" in blob or "JSONDecodeError" in blob or "not valid JSON" in blob:
        merged["json"] = extract_json_parse_error(blob)
    merged["subprocess"] = extract_subprocess_error(blob)

    failing_cmd = ""
    for line in (last_error or "").splitlines():
        if line.strip().startswith("$"):
            failing_cmd = line.strip()
            break
    merged["failing_command_guess"] = failing_cmd
    return merged


def compact_evidence_for_model(evidence: dict[str, Any], max_chars: int = 6000) -> str:
    """Human-readable compact block for LLM (not whole project output)."""
    try:
        s = json.dumps(evidence, indent=2, ensure_ascii=True)
    except Exception:
        s = str(evidence)
    return s if len(s) <= max_chars else s[:max_chars] + "\n…(truncated)"
