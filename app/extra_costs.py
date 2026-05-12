"""Shared normalization for job / recurring-rule extra cost line items."""

from __future__ import annotations

from typing import Any

_PRESET_EXTRA_COST_CATEGORIES = frozenset({"materials", "fuel", "labor", "equipment", "travel", "custom", "other"})


def canonical_extra_cost_category(raw: Any) -> str:
    s = str(raw or "").strip()
    if not s:
        return "materials"
    sl = s.lower()
    if sl in _PRESET_EXTRA_COST_CATEGORIES:
        return sl
    return s[:48]


def normalize_extra_costs_lines(raw: Any) -> list[dict[str, Any]]:
    """Normalize lines: category, label, amount (non-negative)."""
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        cat = canonical_extra_cost_category(item.get("category"))
        label = str(item.get("label") or "").strip()
        if not label and cat == "materials":
            label = "Material"
        try:
            amt = float(item.get("amount", 0) or 0)
        except (TypeError, ValueError):
            amt = 0.0
        if amt < 0:
            amt = 0.0
        out.append({"category": cat, "label": label, "amount": round(amt, 2)})
    return out
