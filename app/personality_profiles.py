"""Escalation writer tone profiles (extensible registry)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class EscalationPersonality:
    id: str
    label: str
    description: str
    style_instructions: str


DEFAULT_PROFILE = EscalationPersonality(
    id="default",
    label="Collaborative engineer",
    description="Calm, precise, collaborative default.",
    style_instructions=(
        "Write in a calm, precise, collaborative tone. Be concise but complete. "
        "State uncertainty honestly when evidence is incomplete. "
        "List every repair attempt that was tried — never omit failures. "
        "Do not overstate confidence. Ask for specific debugging actions (inspect file X, run command Y). "
        "Never blame tools or the user. Avoid vague phrases like 'it does not work'; "
        "name the observable failure (assertion, traceback line, exit code). "
        "Include enough context that another engineer can act immediately. "
        "Do not use emotional filler or repeated apologies. "
        "Do not invent root causes; reflect diagnosis confidence. "
        "Do not include huge raw logs inline — reference paths only. "
        "Do not ask vague questions or suggest skipping tests, deleting tests, disabling validation, "
        "or broad rewrites of unrelated features."
    ),
)

TERSE_PROFILE = EscalationPersonality(
    id="terse",
    label="Terse",
    description="Minimal bullets, maximum signal.",
    style_instructions=(
        "Ultra-compact bullets. No filler. Same factual requirements as default: attempts, paths, commands."
    ),
)

TECHNICAL_PROFILE = EscalationPersonality(
    id="technical",
    label="Technical",
    description="Dense technical vocabulary, stack traces summarized.",
    style_instructions=(
        "Prefer exact symbols, file:line references, and command lines. Same guardrails as default."
    ),
)

FRIENDLY_PROFILE = EscalationPersonality(
    id="friendly",
    label="Friendly",
    description="Warm but still factual.",
    style_instructions=(
        "Warm, approachable tone while staying factual and complete. Same anti-noise rules as default."
    ),
)

SENIOR_ENGINEER_PROFILE = EscalationPersonality(
    id="senior_engineer",
    label="Senior engineer",
    description="Direct, prioritizes risk and blast radius.",
    style_instructions=(
        "Direct senior-engineer voice: risks, invariants, smallest safe change. Same constraints as default."
    ),
)

PRODUCT_MANAGER_PROFILE = EscalationPersonality(
    id="product_manager",
    label="Product manager",
    description="User-visible impact first; still lists technical next steps.",
    style_instructions=(
        "Lead with user-facing impact, then technical evidence. No vague asks; same factual completeness."
    ),
)


class PersonalityRegistry:
    _profiles: ClassVar[dict[str, EscalationPersonality]] = {
        p.id: p
        for p in (
            DEFAULT_PROFILE,
            TERSE_PROFILE,
            TECHNICAL_PROFILE,
            FRIENDLY_PROFILE,
            SENIOR_ENGINEER_PROFILE,
            PRODUCT_MANAGER_PROFILE,
        )
    }

    @classmethod
    def get(cls, profile_id: str) -> EscalationPersonality:
        return cls._profiles.get(profile_id.strip().lower(), DEFAULT_PROFILE)


def list_profile_ids() -> list[str]:
    return sorted(PersonalityRegistry._profiles.keys())
