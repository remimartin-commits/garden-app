"""
Smoke-test Code Llama via Ollama (same client as the API).

Requires: Ollama running locally with the model pulled, e.g.
  ollama pull codellama

Run from repo root:
  .\\.venv\\Scripts\\python examples\\verify_function_gen.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openai import OpenAI

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    client = OpenAI(
        base_url=settings.ollama_base_url.rstrip("/"),
        api_key=settings.ollama_api_key,
    )
    prompt = (
        "Write a Python function `merge_sorted(a: list[int], b: list[int]) -> list[int]` "
        "that merges two sorted lists into one sorted list. "
        "Use only O(n) extra space for the output list. Output only the code, no explanation."
    )
    completion = client.chat.completions.create(
        model=settings.chat_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    text = completion.choices[0].message.content or ""
    print(f"Model: {settings.chat_model}")
    print("--- generated code ---")
    print(text.strip())


if __name__ == "__main__":
    main()
