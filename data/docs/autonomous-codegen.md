# Autonomous Code Generation and Agent Safety

## Planning before coding

Successful autonomous coding agents: (1) read relevant files, (2) outline a short plan, (3) implement in small commits or steps, (4) run linters/tests when available. Avoid giant single-shot patches without verification loops.

## Verification

Prefer generated code that includes tests or type hints. In CI, run formatters, linters, unit tests, and security scanners (dependency audit, secret detection).

## Human-in-the-loop

Gate destructive commands (`rm`, `git reset`, production deploys) behind confirmation. Log prompts and outputs for audit in regulated environments.

## Vector stores for codebases

Code RAG often indexes symbols, paths, and docstrings—sometimes with AST-aware chunking. Hybrid search (BM25 + vectors) improves exact identifier lookup versus pure semantic search.
