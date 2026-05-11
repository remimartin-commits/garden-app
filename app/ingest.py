from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection
from openai import OpenAI

from app.chunking import chunk_markdown_sections, chunk_text
from app.config import Settings

logger = logging.getLogger(__name__)


def _doc_id(source: str, chunk_index: int, text: str) -> str:
    h = hashlib.sha256(f"{source}:{chunk_index}:{text}".encode()).hexdigest()[:24]
    return f"{Path(source).stem}_{chunk_index}_{h}"


def _embed_batches(client: OpenAI, model: str, texts: list[str], batch_size: int = 64):
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        embed_response = client.embeddings.create(model=model, input=batch)
        out.extend([e.embedding for e in embed_response.data])
    return out


def ingest_docs(settings: Settings, client: OpenAI | None) -> Collection:
    settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
    chroma = chromadb.PersistentClient(path=str(settings.chroma_persist_dir))

    if settings.force_reingest:
        try:
            chroma.delete_collection("coding_docs")
        except Exception:
            pass

    collection = chroma.get_or_create_collection(
        name="coding_docs",
        metadata={"description": "Curated coding tools and codegen docs"},
    )

    md_files = sorted(settings.docs_dir.glob("*.md"))
    if not md_files:
        return collection

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for path in md_files:
        raw = path.read_text(encoding="utf-8")
        if settings.rag_chunk_strategy == "markdown":
            parts = chunk_markdown_sections(
                raw,
                max_tokens=settings.chunk_tokens,
                overlap_tokens=settings.chunk_overlap_tokens,
            )
        else:
            parts = chunk_text(
                raw,
                max_tokens=settings.chunk_tokens,
                overlap_tokens=settings.chunk_overlap_tokens,
            )
        for i, chunk in enumerate(parts):
            ids.append(_doc_id(str(path), i, chunk))
            documents.append(chunk)
            metadatas.append({"source": path.name, "chunk_index": i})

    if not documents:
        return collection

    if client is None or not (settings.openai_api_key or "").strip():
        logger.warning(
            "OPENAI_API_KEY not set; skipping embedding ingest (RAG retrieval disabled until configured)."
        )
        return collection

    embeddings = _embed_batches(
        client, settings.openai_embed_model, documents
    )

    existing = collection.get(ids=ids)
    existing_ids = set(existing["ids"] or [])
    new_ids = [i for i in ids if i not in existing_ids]
    if not new_ids:
        return collection

    idx_map = {id_: j for j, id_ in enumerate(ids)}
    to_add = [idx_map[i] for i in new_ids]
    collection.add(
        ids=[ids[j] for j in to_add],
        embeddings=[embeddings[j] for j in to_add],
        documents=[documents[j] for j in to_add],
        metadatas=[metadatas[j] for j in to_add],
    )
    return collection


def get_collection(settings: Settings) -> Collection:
    chroma = chromadb.PersistentClient(path=str(settings.chroma_persist_dir))
    return chroma.get_or_create_collection(name="coding_docs")
