from __future__ import annotations

from dataclasses import dataclass

from chromadb.api.models.Collection import Collection
from openai import OpenAI

from app.config import Settings, rag_answer_model


SYSTEM_PROMPT = """You are an expert assistant focused on modern coding tools, AI-assisted development, autonomous code generation, and production LLM/RAG practices.

Use the CONTEXT snippets below when they are relevant. If context is thin or missing, still answer from general best practices and say when something may be environment-specific.

When you rely on a snippet, mention its bracketed source tag (e.g. [filename.md]) briefly so the user can trace it.

When giving code, prefer complete minimal examples and mention language/version if it matters."""


@dataclass
class RagResult:
    answer: str
    sources: list[str]
    retrieved_excerpt: str


def retrieve_context(
    settings: Settings,
    embed_client: OpenAI | None,
    collection: Collection,
    query: str,
) -> tuple[str, list[str]]:
    if collection.count() == 0:
        return "", []
    if embed_client is None or not (settings.openai_api_key or "").strip():
        return "", []

    q_emb = embed_client.embeddings.create(
        model=settings.openai_embed_model,
        input=[query],
    ).data[0].embedding

    fetch_k = min(
        settings.rag_top_k * max(1, settings.rag_fetch_multiplier),
        max(1, collection.count()),
    )

    result = collection.query(
        query_embeddings=[q_emb],
        n_results=fetch_k,
        include=["documents", "metadatas", "distances"],
    )

    docs = result["documents"][0] if result["documents"] else []
    metas = result["metadatas"][0] if result["metadatas"] else []
    sources: list[str] = []
    blocks: list[str] = []
    seen_pairs: set[tuple[str, str]] = set()
    for doc, meta in zip(docs, metas):
        src = meta.get("source", "unknown") if meta else "unknown"
        pair = (src, doc[:120])
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        if src not in sources:
            sources.append(src)
        blocks.append(f"[{src}]\n{doc}")
        if len(blocks) >= settings.rag_top_k:
            break

    context = "\n\n---\n\n".join(blocks)
    max_chars = max(2000, settings.rag_max_context_chars)
    if len(context) > max_chars:
        context = context[:max_chars] + "\n\n…[context truncated for length]"
    return context, sources


def generate_answer(
    settings: Settings,
    embed_client: OpenAI | None,
    chat_client: OpenAI,
    collection: Collection,
    user_message: str,
    conversation: list[dict[str, str]] | None = None,
) -> RagResult:
    context, sources = retrieve_context(
        settings, embed_client, collection, user_message
    )
    conv = conversation or []

    user_block = user_message
    if context:
        user_block = (
            f"CONTEXT (from internal docs):\n{context}\n\n"
            f"USER QUESTION:\n{user_message}"
        )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *conv,
        {"role": "user", "content": user_block},
    ]

    completion = chat_client.chat.completions.create(
        model=rag_answer_model(settings),
        messages=messages,
        temperature=0.35,
    )
    answer = completion.choices[0].message.content or ""
    excerpt = context[:4000] + ("…" if len(context) > 4000 else "")
    return RagResult(answer=answer, sources=sources, retrieved_excerpt=excerpt)
