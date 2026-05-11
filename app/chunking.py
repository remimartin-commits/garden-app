from __future__ import annotations

import tiktoken


def chunk_markdown_sections(
    text: str,
    *,
    encoding_name: str = "cl100k_base",
    max_tokens: int = 450,
    overlap_tokens: int = 80,
) -> list[str]:
    """Split Markdown on headings (# …), then window each section by tokens."""
    lines = text.split("\n")
    sections: list[str] = []
    buf: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#") and buf:
            sections.append("\n".join(buf))
            buf = [line]
        else:
            buf.append(line)
    if buf:
        sections.append("\n".join(buf))

    chunks: list[str] = []
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        chunks.extend(
            chunk_text(
                sec,
                encoding_name=encoding_name,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens,
            )
        )
    return chunks


def chunk_text(
    text: str,
    *,
    encoding_name: str = "cl100k_base",
    max_tokens: int = 450,
    overlap_tokens: int = 80,
) -> list[str]:
    """Split text into overlapping token windows."""
    enc = tiktoken.get_encoding(encoding_name)
    tokens = enc.encode(text)
    if not tokens:
        return []

    chunks: list[str] = []
    start = 0
    step = max(1, max_tokens - overlap_tokens)
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        piece = enc.decode(tokens[start:end]).strip()
        if piece:
            chunks.append(piece)
        if end >= len(tokens):
            break
        start += step
    return chunks
