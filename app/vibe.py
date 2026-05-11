"""Vibe-coding prompts for Code Llama: style contracts and message assembly."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


VIBE_SYSTEM_PROMPT = """You are Code Llama acting as a vibe-coding pair programmer.

"Vibe coding" means staying in flow: small iterations, matching the human's taste in naming and structure, and shipping working code without unnecessary ceremony—unless the user asked for ceremony.

You MUST follow the STYLE CONTRACT in the user message exactly when writing code. If something is ambiguous, pick the option that best matches that contract (not generic best practices that contradict it).

Output rules:
- Prefer the programming language the user implies; default to Python if none is stated.
- Place code in fenced markdown blocks when you include explanation; if the user asked for code only, output only the code.
- Do not invent libraries that do not exist; use standard library when possible if the contract says minimal dependencies.
- On the **first** reply to a task, give the solution directly (no separate changelog) unless the task explicitly asks for a plan or changelog first."""


def guide_intro() -> str:
    return """
What is vibe coding (with Code Llama)?
  Flow over perfection—you steer with rough prompts, tighten later. Code Llama does best when you give it a *style contract* up front (how chatty, how strict, how modular)
  and a *concrete next step* (one function, one file, one behavior).

How to prompt:
  - Anchor the vibe in constraints: "few comments", "split files when >120 lines", "strict types", "scrappy script OK".
  - Name the shape of the answer: "only the function", "module + one usage example", "CLI first".
  - Iterate: run output, paste errors back, say "keep the same style".

This guide will ask a few style questions, generate code, then let you refine in a loop. Optional **self-documentation**: on each refinement you can ask Code Llama to explain what it changed (numbered steps) before the updated code.
"""


def guide_prompting_cheatsheet() -> str:
    return """
Prompt patterns that work well with Code Llama:
  • "Match this style: [bullet list]. Implement: [task]."
  • "Start minimal; no deps beyond stdlib. Expand only if I ask."
  • "Use my variable tone: short names / descriptive names / mixed—pick one and stick to it."
  • "If unsure, choose the simpler branch and leave a one-line TODO in my comment style."

Anti-patterns:
  • Huge multi-feature asks with no style hints—split the task.
  • Contradictions ("enterprise patterns" + "no abstractions")—pick one lane.
"""


class VibeStyleProfile(BaseModel):
    pace: Literal["fast_loose", "steady_pragmatic", "careful"] = Field(
        description="How rushed vs deliberate the code should feel",
    )
    verbosity: Literal["code_only", "brief_notes", "teach_along"] = Field(
        description="How much prose vs code",
    )
    structure: Literal["one_file", "split_when_helpful"] = Field(
        description="File / module boundaries",
    )
    types: Literal["full", "some", "none"] = Field(
        description="Type hints density (Python-ish; adapt if another language)",
    )
    naming: Literal["short", "balanced", "explicit"] = Field(
        description="Identifier length and descriptiveness",
    )
    errors: Literal["minimal", "practical", "defensive"] = Field(
        description="Error handling depth",
    )
    deps: Literal["stdlib_only", "common_libs_ok"] = Field(
        description="Dependency appetite",
    )
    extras: str = Field(
        default="",
        description="Free-form vibe notes (optional)",
    )
    change_documentation: Literal["off", "step_by_step"] = Field(
        default="step_by_step",
        description="On refinement: explain each edit step-by-step before the updated code.",
    )


def build_style_contract(profile: VibeStyleProfile) -> str:
    pace_line = {
        "fast_loose": "Bias to shipping quickly; acceptable to leave small rough edges if noted.",
        "steady_pragmatic": "Balance clarity and speed; avoid cleverness.",
        "careful": "Prefer readability and edge-case checks over brevity.",
    }[profile.pace]
    verbosity_line = {
        "code_only": "Output mostly code; avoid narration unless necessary.",
        "brief_notes": "Short comments at non-obvious spots only.",
        "teach_along": "Brief explanations before/after code blocks are OK.",
    }[profile.verbosity]
    structure_line = {
        "one_file": "Keep everything in a single file unless impossible.",
        "split_when_helpful": "Split into multiple files when it genuinely helps navigation.",
    }[profile.structure]
    types_line = {
        "full": "Use thorough type hints where they help.",
        "some": "Type hints on public surfaces and tricky spots.",
        "none": "Skip type hints unless the language forces them.",
    }[profile.types]
    naming_line = {
        "short": "Terse names where context is obvious.",
        "balanced": "Readable names; avoid extreme abbreviation.",
        "explicit": "Longer, descriptive names even if verbose.",
    }[profile.naming]
    errors_line = {
        "minimal": "Minimal error handling—fail naturally or simple checks.",
        "practical": "Handle likely failures with clear messages.",
        "defensive": "Guard inputs and spell out failure modes.",
    }[profile.errors]
    deps_line = {
        "stdlib_only": "Standard library only unless the user explicitly required a library.",
        "common_libs_ok": "Well-known ecosystem libs are fine if they reduce boilerplate.",
    }[profile.deps]
    extra = profile.extras.strip()
    extra_block = f"\n- Extra notes: {extra}" if extra else ""
    if profile.change_documentation == "step_by_step":
        doc_line = (
            "- Refinements: self-document step-by-step—see the refinement message format "
            "(## Changes then ## Updated solution)."
        )
    else:
        doc_line = (
            "- Refinements: return the updated solution only unless the user asks for narration."
        )
    return (
        "STYLE CONTRACT (follow strictly):\n"
        f"- Pace: {pace_line}\n"
        f"- Verbosity: {verbosity_line}\n"
        f"- Structure: {structure_line}\n"
        f"- Types: {types_line}\n"
        f"- Naming: {naming_line}\n"
        f"- Errors: {errors_line}\n"
        f"- Dependencies: {deps_line}\n"
        f"{doc_line}"
        f"{extra_block}"
    )


def build_vibe_messages(profile: VibeStyleProfile, task: str) -> list[dict[str, str]]:
    contract = build_style_contract(profile)
    user_msg = (
        f"{contract}\n\nTASK:\n{task.strip()}\n\n"
        "Deliver the initial solution for this task (no separate ## Changes section "
        "unless the task itself asks for one)."
    )
    return [
        {"role": "system", "content": VIBE_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]


REFINEMENT_INSTRUCTION = """FEEDBACK ON YOUR LAST OUTPUT

Apply the feedback below while keeping the original STYLE CONTRACT and TASK from the conversation start—unless the feedback explicitly asks to change scope or style.

Reply with the complete updated solution (full code or full answer). Do not use a patch/diff format unless the feedback asks for a diff."""

STEP_BY_STEP_SELF_DOC = """
Self-documentation for this refinement (required):
- Start with a section whose heading is exactly: ## Changes
- Use a numbered list. Each step states: (1) what you changed, (2) which part of the feedback it satisfies, (3) one short rationale.
- Order steps in a logical edit sequence (e.g. structure first, then behavior, then polish).
- If you intentionally left something unchanged, add a step explaining why.
- After that, use a section whose heading is exactly: ## Updated solution
- Put the full revised program or answer there (use fenced code blocks for code).
"""


def format_refinement_user_message(
    feedback: str,
    *,
    change_documentation: Literal["off", "step_by_step"] = "step_by_step",
) -> str:
    body = f"{REFINEMENT_INSTRUCTION}\n\n---\n{feedback.strip()}"
    if change_documentation == "off":
        return body
    return f"{body}\n{STEP_BY_STEP_SELF_DOC}"


def append_refinement_turn(
    messages: list[dict[str, str]],
    assistant_reply: str,
    feedback: str,
    *,
    change_documentation: Literal["off", "step_by_step"] = "step_by_step",
) -> list[dict[str, str]]:
    """Extend a vibe thread with the model's last reply and the user's refinement feedback."""
    out = [dict(m) for m in messages]
    out.append({"role": "assistant", "content": assistant_reply})
    out.append(
        {
            "role": "user",
            "content": format_refinement_user_message(
                feedback, change_documentation=change_documentation
            ),
        }
    )
    return out


def build_refinement_messages(
    profile: VibeStyleProfile,
    task: str,
    previous_assistant_output: str,
    feedback: str,
) -> list[dict[str, str]]:
    """Single refinement step when only the last model output and feedback are stored."""
    base = build_vibe_messages(profile, task)
    return append_refinement_turn(
        base,
        previous_assistant_output,
        feedback,
        change_documentation=profile.change_documentation,
    )
