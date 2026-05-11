"""LLM calls for structured repair plans only (no code edits here)."""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from app.agent_runner import _openai_chat_client, resolve_openai_compatible_chat_model
from app.config import Settings
from app.repair_quality import RepairPlanStrict, parse_repair_plan_json


JSON_REPAIR_HINT = (
    "The previous output was invalid JSON. Reply with ONE JSON object only, keys: "
    "diagnosis_summary, repair_strategy, files_to_modify (array of {path, reason, change_summary}), "
    "commands_to_run_after_patch (string array), risk_level (low|medium|high), requires_human_review (boolean)."
)


def request_repair_plan_json(
    settings: Settings,
    *,
    diagnosis_compact: str,
    evidence_compact: str,
    prior_attempts_digest: str,
    strategy_name: str,
) -> tuple[RepairPlanStrict | None, str]:
    """Returns validated plan or None; raw response text for logging."""
    api_key = (settings.openai_chat_api_key or settings.openai_api_key or "").strip()
    base_url = (settings.openai_chat_base_url or "").strip()
    if not api_key and not base_url:
        return None, "no_llm_config"

    client = _openai_chat_client(settings)
    model_id = resolve_openai_compatible_chat_model(settings)
    sys_msg = (
        "You output strict JSON only for a repair PLAN (no code). "
        "Follow the user's schema exactly. Do not include markdown fences."
    )
    user_msg = (
        f"Strategy hint: {strategy_name}\n\n"
        f"Diagnosis:\n{diagnosis_compact}\n\n"
        f"Evidence (compact):\n{evidence_compact}\n\n"
        f"Prior attempts (avoid repeating failed approaches):\n{prior_attempts_digest}\n\n"
        "Return JSON with keys: diagnosis_summary, repair_strategy, files_to_modify "
        "(array of objects path, reason, change_summary), commands_to_run_after_patch, "
        "risk_level (low|medium|high), requires_human_review."
    )
    raw = _chat(client, model_id, sys_msg, user_msg)
    plan = parse_repair_plan_json(raw)
    if plan:
        return plan, raw

    raw2 = _chat(client, model_id, sys_msg, JSON_REPAIR_HINT + "\n\n" + user_msg)
    plan2 = parse_repair_plan_json(raw2)
    if plan2:
        return plan2, raw2

    fallback_sys = (
        "Reply with minimal JSON only: "
        '{"diagnosis_summary":"","repair_strategy":"minimal_fix","files_to_modify":[],"'
        '"commands_to_run_after_patch":["python -m pytest -q --tb=line"],"risk_level":"low","requires_human_review":false}'
    )
    raw3 = _chat(client, model_id, fallback_sys, user_msg[:6000])
    plan3 = parse_repair_plan_json(raw3)
    return plan3, raw3


def _chat(client: OpenAI, model_id: str, system: str, user: str) -> str:
    completion = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (completion.choices[0].message.content or "").strip()


def fallback_minimal_prompt_block(failure_excerpt: str) -> str:
    return (
        "\n\n## Fallback repair mode (narrow)\n"
        "Fix ONLY the specific failing test/build error shown below. "
        "Do not refactor. Do not change unrelated files. Do not add features. "
        "Make the smallest change that resolves this exact failure.\n\n"
        f"Failure excerpt:\n{failure_excerpt[:3500]}\n"
    )

