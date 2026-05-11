# AI Coding Assistants and IDE Integration (2025–2026)

## Cursor and agentic IDE features

Cursor is a fork of VS Code with native AI: inline edits (Cmd/Ctrl+K), Composer for multi-file changes, and Agent mode for autonomous exploration of the repo. Best practices: write concise `.cursor/rules` or `AGENTS.md` for project conventions; keep context focused by @-mentioning files; use Composer for refactors spanning multiple modules.

## GitHub Copilot ecosystem

Copilot provides completions in the editor, Copilot Chat for Q&A, and Copilot Workspace/agents for larger tasks in GitHub. Enterprise setups often combine org policies, audit logs, and secret scanning with AI suggestions.

## CLI and cloud agents

Tools like Anthropic Claude Code, OpenAI Codex CLI, and Cursor CLI run agents in terminals or CI. Typical pattern: sandboxed commands, explicit approval for destructive ops, and structured output (diffs, tests) rather than silent edits.

## Choosing a workflow

Use **inline completion** for local syntax and boilerplate. Use **chat** for explanation and design tradeoffs. Use **agents** when the task needs searching the codebase, running tests, or multi-step edits with verification.
