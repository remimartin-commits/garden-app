# Autonomous repair playbook lessons

The block fixer (repair diagnosis, escalation envelopes, and heuristic tips in `autonomous_loop`) consumes **curated hints** from `app/repair_playbook_lessons.py`.

When you debug a new failure class and fix it in code or tests, add a lesson so the next blocked run gets the same guidance without rediscovering the cause.

## How to add a lesson

1. Open `app/repair_playbook_lessons.py`.
2. Append a `_Lesson(...)` entry to the `LESSONS` tuple:
   - **`lesson_id`**: short snake_case identifier (used in logs and future tooling).
   - **`matches`**: a predicate `blob: str -> bool`. Prefer `_all_substrings("needle", ...)` or `_any_match(...)` for combinations. Keep matchers **specific** enough to avoid noisy hints on unrelated traces.
   - **`hints`**: one or more complete sentences; first hint should state the fix priority clearly.
3. Add or extend a unit test in `tests/test_repair_toolkit.py` that calls `build_diagnosis(...)` with a **minimal synthetic** traceback string and asserts a substring of the expected lesson appears in `repair_hints`.

## Wiring

- **Diagnosis**: `app/repair_diagnose.py` merges playbook output into `repair_hints`.
- **Learned tips**: `app/autonomous_loop.py` prepends up to three playbook hints into `_heuristic_repair_tips` (deduplicated with existing heuristics).

## Optional overlays

For environment-specific rules, you can later load a JSON file from the task workspace and merge strings into `collect_lesson_hints`; the playbook module is the single source of truth for shared, versioned lessons.
