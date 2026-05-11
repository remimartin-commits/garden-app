# RAG, Embeddings, and Production LLM APIs

## Retrieval-augmented generation

RAG grounds answers in retrieved documents: chunk source material, embed queries and chunks with the same model family, retrieve top-k by cosine similarity, inject snippets into the system or user message. Reduces hallucination for facts that change often (docs, APIs). Tune chunk size (256–1024 tokens), overlap (10–20%), and top-k (4–12).

## OpenAI API patterns (chat completions)

Use `chat.completions` with `messages` array (system, user, assistant). Strong models: **gpt-4o**, **gpt-4.1**, **o3-mini** (reasoning). Set `temperature` low (0.2–0.5) for code generation; higher for brainstorming.

## Embeddings

**text-embedding-3-small** and **text-embedding-3-large** map text to vectors for semantic search. Normalize vectors if comparing cosine similarity manually; many stores handle this internally.

## Tool use and function calling

Modern APIs support **tools/functions**: the model returns structured JSON to call HTTP APIs, DBs, or code runners. Combine with RAG: retrieve context first, then let the model decide whether to emit code or call a tool.
