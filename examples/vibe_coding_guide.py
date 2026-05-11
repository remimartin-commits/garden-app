"""
Interactive vibe-coding guide (terminal).

Prefer the unified launcher:  python -m app.cli  → choose Terminal.

Requires Ollama with the configured model (e.g. ollama pull codellama).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.interactive_vibe import run_terminal_session

if __name__ == "__main__":
    run_terminal_session()
