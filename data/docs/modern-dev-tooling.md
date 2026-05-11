# Modern Developer Tooling Stack

## Package and repo hygiene

Use lockfiles (`package-lock.json`, `poetry.lock`, `uv.lock`). Prefer reproducible builds in Docker or devcontainers. Document minimal versions in README or CI.

## API design for AI backends

Expose **streaming** optional endpoints (`text/event-stream`) for long responses. Always validate inputs with Pydantic or JSON Schema. Rate-limit and authenticate production endpoints.

## Observability

Instrument LLM apps with traces (latency, token usage, retrieval scores). Store retrieval snippets for debugging “wrong answer” reports.

## Evaluation

Track answer quality with human review and automated checks (contains citation markers, passes syntax check for emitted code). Refresh the doc corpus when frameworks release breaking changes.
