"""Curated repair lessons for the autonomous \"block fixer\" (diagnosis + repair envelope).

Human maintainers and coding agents add entries here after debugging a failure class so the
next blocked run gets the same hints without rediscovering the root cause.

See: data/docs/autonomous-repair-lessons.md
"""

from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple

# (lesson_id, match(blob)->bool, hint_lines)
class _Lesson(NamedTuple):
    lesson_id: str
    matches: Callable[[str], bool]
    hints: tuple[str, ...]


def _all_substrings(*needles: str) -> Callable[[str], bool]:
    """Case-insensitive: every needle must appear somewhere in the blob."""

    lowered_needles = tuple(n.lower() for n in needles)

    def _ok(blob: str) -> bool:
        low = blob.lower()
        return all(n in low for n in lowered_needles)

    return _ok


def _any_match(*predicates: Callable[[str], bool]) -> Callable[[str], bool]:
    """True if any predicate passes."""

    def _ok(blob: str) -> bool:
        return any(p(blob) for p in predicates)

    return _ok


def _pytest_collection_with_json_noise(blob: str) -> bool:
    """Pytest collection failure plus stale planner JSON errors in the same trace."""
    low = blob.lower()
    coll = "error collecting" in low or "errors during collection" in low
    if not coll:
        return False
    noise = (
        "expecting value" in low
        or "jsondecode" in low
        or "not valid json" in low
        or "patch_executor" in low
    )
    return noise


LESSONS: tuple[_Lesson, ...] = (
    _Lesson(
        "model_json_schema_missing",
        _any_match(
            _all_substrings("model_json_schema", "attributeerror"),
            _all_substrings("model_json_schema", "has no attribute"),
        ),
        (
            "AttributeError on model_json_schema: types imported by app.feature_schema (and similar "
            "callers) must expose Pydantic v2's model_json_schema — plain @dataclass types break at "
            "import/collection time.",
            "Restore the entity as a Pydantic BaseModel (or keep a parallel Pydantic model used only "
            "for schema export). If the project defines _TASK5_INQUIRY_FEATURE_SCHEMA, it must stay "
            "consistent with Inquiry.model_json_schema().",
            "Re-run the same focused pytest line after fixing imports; the failure often appears "
            "only during collection, not in assertions.",
        ),
    ),
    _Lesson(
        "entity_fields_stub_import",
        _all_substrings("importerror", "entity_fields", "cannot import name"),
        (
            "ImportError from app.entity_fields: do not invent placeholder types (String/Integer) on "
            "the module unless tests expect them. Either restore real helpers or remove the import "
            "from app/entities.py and keep entities self-contained.",
            "If app/entities.py was replaced by a minimal stub, rebuild it from the test contracts "
            "for that workspace (grep tests for from app.entities import …).",
        ),
    ),
    _Lesson(
        "pytest_import_file_mismatch",
        _all_substrings("import file mismatch", "not the same as the test file we want to collect"),
        (
            "Pytest import file mismatch: two test files share the same module name (e.g. "
            "tests/test_foo.py and app/tests/test_foo.py). Rename one file so basenames differ, or "
            "relocate helper tests outside pytest's discovery path.",
        ),
    ),
    _Lesson(
        "pydantic_model_validator_return_value",
        _all_substrings("custom validator is returning a value other than `self`", "model_validator"),
        (
            "Pydantic v2 model_validator(mode='after') must return self after mutating fields in place. "
            "Returning model_copy(...) is ignored during __init__; assign to self.field_name inside "
            "the validator instead, or switch to a pattern that does not replace the instance.",
        ),
    ),
    _Lesson(
        "pytest_collection_over_json_noise",
        _pytest_collection_with_json_noise,
        (
            "If pytest shows ERROR collecting, treat it as an import/collection failure first — fix "
            "the first traceback frame into app code before chasing stale patch_executor JSON errors "
            "in last_error.",
        ),
    ),
)


def collect_lesson_hints(blob: str, *, max_hints: int = 16) -> list[str]:
    """Return ordered, de-duplicated hint strings for everything that matches ``blob``."""
    seen: set[str] = set()
    out: list[str] = []
    if not (blob or "").strip():
        return out
    for lesson in LESSONS:
        if not lesson.matches(blob):
            continue
        for h in lesson.hints:
            h = h.strip()
            if not h or h in seen:
                continue
            seen.add(h)
            out.append(h)
            if len(out) >= max_hints:
                return out
    return out
