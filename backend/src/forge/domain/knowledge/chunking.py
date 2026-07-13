"""Paragraph-aware chunking for retrieval.

Targets ~400-700 tokens per chunk (approximated at 4 chars/token) with a
tail overlap so ideas spanning a boundary stay retrievable. Pure function —
the embedding service handles I/O.
"""

from dataclasses import dataclass

TARGET_CHARS = 2400  # ≈600 tokens
MIN_CHARS = 800  # merge tiny trailing chunks into the previous one
OVERLAP_CHARS = 360  # ≈15%


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str


def chunk_text(text: str) -> list[Chunk]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    pieces: list[str] = []
    current: list[str] = []
    current_len = 0
    for para in paragraphs:
        # Oversized single paragraphs are split hard at the target size.
        while len(para) > TARGET_CHARS * 1.5:
            head, para = para[:TARGET_CHARS], para[TARGET_CHARS:]
            if current:
                pieces.append("\n\n".join(current))
                current, current_len = [], 0
            pieces.append(head)
        if current_len + len(para) > TARGET_CHARS and current:
            pieces.append("\n\n".join(current))
            current, current_len = [], 0
        current.append(para)
        current_len += len(para) + 2
    if current:
        tail = "\n\n".join(current)
        if pieces and len(tail) < MIN_CHARS:
            pieces[-1] = pieces[-1] + "\n\n" + tail
        else:
            pieces.append(tail)

    chunks: list[Chunk] = []
    for i, piece in enumerate(pieces):
        if i > 0:
            overlap = pieces[i - 1][-OVERLAP_CHARS:]
            # Snap the overlap to a word boundary.
            overlap = overlap.split(" ", 1)[-1] if " " in overlap else overlap
            piece = f"{overlap}\n\n{piece}"
        chunks.append(Chunk(index=i, text=piece))
    return chunks


def contextualize(title: str, chunk: Chunk) -> str:
    """Prefix used at embed time — improves retrieval vs. bare chunks."""
    return f"{title}\n\n{chunk.text}"
