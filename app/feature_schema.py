"""Generate and persist feature schemas from a topic."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import BadRequestError, OpenAI

from app.agent_runner import _openai_chat_client, resolve_openai_compatible_chat_model
from app.config import Settings

logger = logging.getLogger(__name__)


def feature_schemas_dir(settings: Settings) -> Path:
    settings.user_data_dir.mkdir(parents=True, exist_ok=True)
    root = settings.user_data_dir / "feature_schemas"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _topic_slug(topic: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", topic.strip().lower()).strip("-")
    return cleaned or "feature"


def _feature_schema_prompt(topic: str) -> str:
    return (
        "Generate a practical software feature schema as strict JSON only.\n"
        "Topic: "
        f"{topic}\n\n"
        "Return an object with keys:\n"
        "- name: string\n"
        "- summary: string\n"
        "- goals: string[]\n"
        "- non_goals: string[]\n"
        "- entities: [{name: string, fields: [{name: string, type: string, required: bool, description: string}]}]\n"
        "- api_endpoints: [{method: string, path: string, purpose: string, request: object, response: object}]\n"
        "- acceptance_criteria: string[]\n"
        "- implementation_notes: string[]\n"
        "Do not include markdown, comments, or extra text."
    )


def _parse_model_json(content: str) -> dict[str, Any]:
    raw = (content or "").strip()
    if not raw:
        raise ValueError("Model output is empty")
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Model output must be a JSON object")
    return data


def _feature_schema_openai_client(settings: Settings) -> OpenAI:
    # Prefer cloud OPENAI_API_KEY over OPENAI_CHAT_API_KEY so Ollama-style chat keys (e.g. "ollama") do not
    # override the real key used for official-api gpt-5.5 draft/finalize.
    key = (
        settings.feature_schema_openai_api_key
        or settings.openai_api_key
        or settings.openai_chat_api_key
        or ""
    ).strip()
    if not key:
        raise ValueError(
            "Configure OPENAI_API_KEY (or FEATURE_SCHEMA_OPENAI_API_KEY) for feature schema generation. "
            "OPENAI_CHAT_API_KEY alone may point at Ollama; the schema pipeline uses the official OpenAI API "
            "unless FEATURE_SCHEMA_OPENAI_BASE_URL is set."
        )
    base = (settings.feature_schema_openai_base_url or "").strip().rstrip("/")
    if base:
        return OpenAI(api_key=key, base_url=base)
    return OpenAI(api_key=key)


def _openai_schema_json_completion(
    *,
    client: OpenAI,
    model: str,
    system: str,
    user: str,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    try:
        completion = client.chat.completions.create(
            **kwargs,
            response_format={"type": "json_object"},
        )
    except BadRequestError:
        completion = client.chat.completions.create(**kwargs)
    content = completion.choices[0].message.content or "{}"
    return _parse_model_json(content)


def _anthropic_audit_schema(
    *,
    topic: str,
    draft_schema: dict[str, Any],
    settings: Settings,
) -> dict[str, Any]:
    try:
        from anthropic import Anthropic
    except ImportError as exc:  # pragma: no cover - exercised when dependency missing
        raise RuntimeError(
            "The anthropic package is required for the schema audit step. "
            "Install dependencies (pip install -r requirements.txt)."
        ) from exc

    key = (settings.anthropic_api_key or "").strip()
    if not key:
        raise ValueError(
            "Configure ANTHROPIC_API_KEY for the feature-schema audit step (Claude Opus)."
        )
    client = Anthropic(api_key=key)
    model = (settings.feature_schema_audit_anthropic_model or "").strip() or "claude-opus-4-7"
    user = (
        f"Topic:\n{topic}\n\n"
        "Draft feature schema JSON (to audit):\n"
        f"{json.dumps(draft_schema, indent=2, ensure_ascii=True)}\n\n"
        "Return ONLY valid JSON (no markdown fences) with keys:\n"
        "- critical_issues: string[]\n"
        "- improvements: string[]\n"
        "- risk_notes: string[]\n"
        "- author_instructions_for_revision: string (numbered, concrete edits for the model that will revise the schema)\n"
        "- overall_verdict: string (one of pass|needs_revision)\n"
    )
    msg = client.messages.create(
        model=model,
        max_tokens=16384,
        system=(
            "You are a strict principal engineer reviewing a feature schema before autonomous "
            "implementation. Be specific, testable, and actionable. Output JSON only."
        ),
        messages=[{"role": "user", "content": user}],
    )
    parts: list[str] = []
    for block in msg.content:
        if hasattr(block, "text") and block.text:
            parts.append(str(block.text))
    text = "\n".join(parts).strip()
    return _parse_model_json(text)


def _schema_audit_stub_pass() -> dict[str, Any]:
    """Audit-shaped object used when Claude audit is skipped (no key or optional package missing)."""
    return {
        "critical_issues": [],
        "improvements": [],
        "risk_notes": [],
        "author_instructions_for_revision": "",
        "overall_verdict": "pass",
    }


def _finalize_schema_with_openai(
    *,
    topic: str,
    draft_schema: dict[str, Any],
    audit: dict[str, Any],
    client: OpenAI,
    model: str,
) -> dict[str, Any]:
    system = (
        "You are a senior product engineer. You receive a topic, a draft feature schema, and an audit. "
        "Return valid JSON only: a single object with exactly these keys: "
        "name, summary, goals, non_goals, entities, api_endpoints, acceptance_criteria, implementation_notes. "
        "Incorporate the audit (especially author_instructions_for_revision). "
        "Refine the draft; keep scope aligned with the topic; do not invent unrelated products."
    )
    user = (
        f"Topic:\n{topic}\n\n"
        "Draft schema JSON:\n"
        f"{json.dumps(draft_schema, ensure_ascii=True)}\n\n"
        "Audit JSON:\n"
        f"{json.dumps(audit, ensure_ascii=True)}\n"
    )
    return _openai_schema_json_completion(client=client, model=model, system=system, user=user)


def generate_and_store_feature_schema(topic: str, settings: Settings) -> dict[str, Any]:
    """Generate a feature schema: OpenAI draft, optional Anthropic audit, OpenAI finalize, then store.

    When ``ANTHROPIC_API_KEY`` is unset (and ``feature_schema_require_anthropic_audit`` is False),
    the Claude audit step is skipped so a valid ``OPENAI_API_KEY`` alone can produce a schema and
    unblock the autonomous coding loop.
    """
    if not topic.strip():
        raise ValueError("topic must not be empty")

    anthropic_key = (settings.anthropic_api_key or "").strip()
    if settings.feature_schema_require_anthropic_audit and not anthropic_key:
        raise ValueError(
            "feature_schema_require_anthropic_audit is enabled but ANTHROPIC_API_KEY is empty. "
            "Set the key or disable FEATURE_SCHEMA_REQUIRE_ANTHROPIC_AUDIT."
        )

    client = _feature_schema_openai_client(settings)
    model = (settings.feature_schema_openai_model or "").strip() or "gpt-5.5"

    draft_system = (
        "You are a senior product engineer. Return valid JSON only, following the user schema exactly."
    )
    draft_user = _feature_schema_prompt(topic)
    draft_schema = _openai_schema_json_completion(
        client=client, model=model, system=draft_system, user=draft_user
    )

    audited_at = datetime.now(timezone.utc)
    audit: dict[str, Any]
    audit_model_label: str
    if anthropic_key:
        try:
            audit = _anthropic_audit_schema(topic=topic, draft_schema=draft_schema, settings=settings)
            audit_model_label = (settings.feature_schema_audit_anthropic_model or "").strip() or "claude-opus-4-7"
        except RuntimeError as exc:
            if "anthropic package" in str(exc).lower():
                logger.warning(
                    "Anthropic audit skipped (package unavailable: %s); continuing with OpenAI finalize only.",
                    exc,
                )
                audit = _schema_audit_stub_pass()
                audit_model_label = "skipped_unavailable"
            else:
                raise
    else:
        logger.info(
            "Anthropic audit skipped (ANTHROPIC_API_KEY not set); schema uses OpenAI draft → finalize only."
        )
        audit = _schema_audit_stub_pass()
        audit_model_label = "skipped_no_api_key"

    final_schema = _finalize_schema_with_openai(
        topic=topic,
        draft_schema=draft_schema,
        audit=audit,
        client=client,
        model=model,
    )

    now = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    slug = _topic_slug(topic)
    out_path = feature_schemas_dir(settings) / f"{now}-{slug}.json"
    payload = {
        "topic": topic,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "schema": final_schema,
        "schema_pipeline": {
            "draft_model": model,
            "audit_model": audit_model_label,
            "finalize_model": model,
            "audited_at_utc": audited_at.isoformat(),
            "finalized_at_utc": datetime.now(timezone.utc).isoformat(),
            "audit": audit,
            "draft_schema": draft_schema,
        },
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"path": str(out_path), "schema": final_schema}


def _load_schema_file(schema_path: str) -> dict[str, Any]:
    path = Path(schema_path)
    if not path.is_file():
        raise ValueError(f"schema file not found: {schema_path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "schema" not in raw:
        raise ValueError("schema file must contain a top-level 'schema' object")
    return raw


def _state_path_for_schema(schema_path: Path) -> Path:
    return schema_path.with_suffix(".state.json")


def _load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.is_file():
        return {"next_step_index": 0, "next_action": "implement", "history": []}
    data = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"next_step_index": 0, "next_action": "implement", "history": []}
    data.setdefault("next_step_index", 0)
    data.setdefault("next_action", "implement")
    data.setdefault("history", [])
    return data


def _build_plan_steps(schema_payload: dict[str, Any]) -> list[str]:
    schema = schema_payload.get("schema", {})
    steps: list[str] = []
    for entity in schema.get("entities", []) or []:
        name = (entity or {}).get("name")
        if name:
            steps.append(f"Implement entity '{name}' and its required fields.")
    for endpoint in schema.get("api_endpoints", []) or []:
        method = (endpoint or {}).get("method", "GET")
        path = (endpoint or {}).get("path", "/")
        purpose = (endpoint or {}).get("purpose", "Fulfill endpoint behavior.")
        steps.append(f"Implement API endpoint {method} {path}. Purpose: {purpose}")
    for criterion in schema.get("acceptance_criteria", []) or []:
        if isinstance(criterion, str) and criterion.strip():
            steps.append(f"Validate acceptance criterion: {criterion.strip()}")
    for note in schema.get("implementation_notes", []) or []:
        if isinstance(note, str) and note.strip():
            steps.append(f"Apply implementation note: {note.strip()}")
    if not steps:
        steps.append("Implement a minimal vertical slice based on goals and summary.")
    return steps


def align_feature_loop_with_autonomous_task(schema_path: str, task_index: int) -> dict[str, Any]:
    """Point the schema feature-loop cursor at the same step as the autonomous task list.

    Autonomous tasks are built in the same order as the first segment of ``plan_steps``:
    entities, then ``api_endpoints``, then ``acceptance_criteria``. Remaining ``plan_steps``
    (e.g. ``implementation_notes``) have no matching tasks and are not targeted until the
    loop advances past all tasks.

    If the saved loop's ``next_step_index`` differs from ``task_index`` (drift), reset this
    step to ``implement`` so prompts and alignment both reference one coherent step.
    """
    schema_file = Path(schema_path)
    schema_payload = _load_schema_file(str(schema_file))
    plan_steps = _build_plan_steps(schema_payload)
    if not plan_steps:
        return {"adjusted": False, "reason": "no_plan_steps"}
    state_path = _state_path_for_schema(schema_file)
    state = _load_state(state_path)
    clamped = max(0, min(int(task_index), len(plan_steps) - 1))
    previous_step = int(state["next_step_index"])
    if previous_step != clamped:
        state["next_step_index"] = clamped
        state["next_action"] = "implement"
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        return {
            "adjusted": True,
            "previous_step_index": previous_step,
            "next_step_index": clamped,
            "next_action": str(state["next_action"]),
            "state_path": str(state_path),
        }
    return {
        "adjusted": False,
        "next_step_index": clamped,
        "next_action": str(state["next_action"]),
        "state_path": str(state_path),
    }


def _build_cursor_prompt(
    schema_payload: dict[str, Any],
    step_text: str,
    action: str,
    iteration: int,
) -> str:
    schema = schema_payload.get("schema", {})
    feature_name = schema.get("name", schema_payload.get("topic", "Feature"))
    summary = schema.get("summary", "")
    goals = schema.get("goals", []) or []
    goals_text = "\n".join(f"- {g}" for g in goals[:5] if isinstance(g, str))
    action_title = "Implement step" if action == "implement" else "Validate step"
    return (
        f"{action_title} for feature: {feature_name}\n"
        f"Iteration: {iteration}\n"
        f"Feature summary: {summary}\n"
        f"Top goals:\n{goals_text if goals_text else '- (no goals listed)'}\n\n"
        f"Current step:\n- {step_text}\n\n"
        "Required behavior:\n"
        "- Reference the existing codebase and make only focused changes for this step.\n"
        "- If implementing: add/modify code and tests for this step only.\n"
        "- If validating: run checks/tests and report pass/fail with evidence.\n"
        "- Return: (1) files changed, (2) brief rationale, (3) verification status."
    )


def _preview_next_prompts(
    *,
    schema_payload: dict[str, Any],
    state: dict[str, Any],
    plan_steps: list[str],
    iterations: int,
) -> list[dict[str, Any]]:
    prompts: list[dict[str, Any]] = []
    step_index = int(state["next_step_index"])
    action = str(state["next_action"])
    base_iteration = len(state.get("history", []))
    for i in range(iterations):
        if step_index >= len(plan_steps):
            break
        step_text = plan_steps[step_index]
        iteration_no = base_iteration + i + 1
        prompts.append(
            {
                "iteration": iteration_no,
                "step_index": step_index,
                "action": action,
                "step": step_text,
                "prompt": _build_cursor_prompt(
                    schema_payload=schema_payload,
                    step_text=step_text,
                    action=action,
                    iteration=iteration_no,
                ),
            }
        )
        if action == "implement":
            action = "validate"
        else:
            action = "implement"
            step_index += 1
    return prompts


def generate_next_cursor_prompts(
    schema_path: str,
    iterations: int = 1,
) -> dict[str, Any]:
    """Emit the next Cursor prompt for the schema loop.

    `next_action` is the kind of output we are waiting on from Cursor
    after this prompt—only `evaluate_and_advance_feature_loop` should flip
    it after a passing alignment check."""
    if iterations != 1:
        raise ValueError("iterations must be 1; fetch the next prompt after each advance.")

    schema_file = Path(schema_path)
    schema_payload = _load_schema_file(schema_path)
    plan_steps = _build_plan_steps(schema_payload)
    state_path = _state_path_for_schema(schema_file)
    state = _load_state(state_path)

    prompts = _preview_next_prompts(
        schema_payload=schema_payload,
        state=state,
        plan_steps=plan_steps,
        iterations=iterations,
    )
    for entry in prompts:
        step_index = int(entry["step_index"])
        action = str(entry["action"])
        iteration_no = int(entry["iteration"])
        state["history"].append(
            {
                "iteration": iteration_no,
                "step_index": step_index,
                "action": action,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "phase": "prompt_issued",
            }
        )

    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    done = int(state["next_step_index"]) >= len(plan_steps)
    return {
        "schema_path": str(schema_file),
        "state_path": str(state_path),
        "total_steps": len(plan_steps),
        "next_step_index": int(state["next_step_index"]),
        "next_action": str(state["next_action"]),
        "done": done,
        "prompts": prompts,
    }


def check_generated_output_alignment(
    *,
    settings: Settings,
    schema_path: str,
    step_text: str,
    action: str,
    generated_output: str,
) -> dict[str, Any]:
    """Judge whether generated output aligns with the schema step."""
    if not generated_output.strip():
        raise ValueError("generated_output must not be empty")
    if action not in {"implement", "validate"}:
        raise ValueError("action must be 'implement' or 'validate'")

    api_key = (settings.openai_chat_api_key or settings.openai_api_key or "").strip()
    base_url = (settings.openai_chat_base_url or "").strip()
    if not api_key and not base_url:
        raise ValueError(
            "Configure OPENAI_API_KEY for cloud alignment, or OPENAI_CHAT_BASE_URL for an "
            "OpenAI-compatible server (e.g. Ollama)."
        )

    schema_payload = _load_schema_file(schema_path)
    schema_json = json.dumps(schema_payload.get("schema", {}), ensure_ascii=True)
    prompt = (
        "Assess alignment of generated output against a feature schema step.\n"
        f"Action: {action}\n"
        f"Step: {step_text}\n"
        "Return strict JSON with keys:\n"
        "- aligned: boolean\n"
        "- confidence: number (0..1)\n"
        "- missing_requirements: string[]\n"
        "- notes: string\n\n"
        f"Feature schema JSON:\n{schema_json}\n\n"
        f"Generated output to evaluate:\n{generated_output}\n"
    )
    client = _openai_chat_client(settings)
    model_id = resolve_openai_compatible_chat_model(settings)
    completion = client.chat.completions.create(
        model=model_id,
        messages=[
            {
                "role": "system",
                "content": "You are a strict reviewer. Return valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    content = (completion.choices[0].message.content or "").strip() or "{}"
    try:
        verdict = _parse_model_json(content)
    except (json.JSONDecodeError, ValueError) as exc:
        preview = (content or "")[:400]
        verdict = {
            "aligned": False,
            "confidence": 0.0,
            "missing_requirements": [],
            "notes": (
                "Alignment model output was not usable JSON "
                f"({type(exc).__name__}: {exc}). Preview: {preview!r}"
            ),
        }
    verdict.setdefault("aligned", False)
    verdict.setdefault("confidence", 0)
    verdict.setdefault("missing_requirements", [])
    verdict.setdefault("notes", "")
    return verdict


def evaluate_and_advance_feature_loop(
    *,
    settings: Settings,
    schema_path: str,
    generated_output: str,
    trust_verification: bool = False,
    trust_notes: str = "",
) -> dict[str, Any]:
    """Evaluate current step output and advance loop state when aligned."""
    schema_file = Path(schema_path)
    schema_payload = _load_schema_file(schema_path)
    plan_steps = _build_plan_steps(schema_payload)
    state_path = _state_path_for_schema(schema_file)
    state = _load_state(state_path)
    step_index = int(state["next_step_index"])

    if step_index >= len(plan_steps):
        return {
            "done": True,
            "advanced": False,
            "reason": "All features are already complete.",
            "verdict": {
                "aligned": True,
                "confidence": 1,
                "missing_requirements": [],
                "notes": "Loop finished; nothing left to evaluate.",
            },
            "next_prompts": [],
            "next_step_index": step_index,
            "next_action": str(state["next_action"]),
            "total_steps": len(plan_steps),
            "state_path": str(state_path),
        }

    action = str(state["next_action"])
    step_text = plan_steps[step_index]
    if trust_verification:
        verdict = {
            "aligned": True,
            "confidence": 1.0,
            "missing_requirements": [],
            "notes": (trust_notes or "Autonomy trusted verification for this step.").strip(),
        }
    else:
        verdict = check_generated_output_alignment(
            settings=settings,
            schema_path=schema_path,
            step_text=step_text,
            action=action,
            generated_output=generated_output,
        )
    aligned = bool(verdict.get("aligned"))
    iteration_no = len(state["history"]) + 1
    state["history"].append(
        {
            "iteration": iteration_no,
            "step_index": step_index,
            "action": action,
            "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
            "aligned": aligned,
            "verdict": verdict,
        }
    )

    advanced = False
    if aligned:
        advanced = True
        if action == "implement":
            state["next_action"] = "validate"
        else:
            state["next_action"] = "implement"
            state["next_step_index"] = step_index + 1

    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    done = int(state["next_step_index"]) >= len(plan_steps)
    next_prompts = _preview_next_prompts(
        schema_payload=schema_payload,
        state=state,
        plan_steps=plan_steps,
        iterations=1,
    )
    return {
        "done": done,
        "advanced": advanced,
        "verdict": verdict,
        "total_steps": len(plan_steps),
        "next_step_index": int(state["next_step_index"]),
        "next_action": str(state["next_action"]),
        "next_prompts": next_prompts,
        "state_path": str(state_path),
    }


def reset_feature_loop_state(schema_path: str) -> dict[str, Any]:
    """Delete saved loop state so a schema file can restart from step 0."""
    path = Path(schema_path)
    if not path.is_file():
        raise ValueError(f"schema file not found: {schema_path}")
    state_path = _state_path_for_schema(path)
    removed = False
    if state_path.is_file():
        state_path.unlink()
        removed = True
    return {"schema_path": str(path), "state_path": str(state_path), "reset": removed}
