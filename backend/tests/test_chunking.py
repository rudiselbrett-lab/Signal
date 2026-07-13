import itertools

from forge.domain.knowledge.chunking import OVERLAP_CHARS, TARGET_CHARS, chunk_text, contextualize


def para(word: str, words: int = 80) -> str:
    return " ".join([word] * words)


def test_short_text_is_single_chunk():
    chunks = chunk_text("one paragraph only")
    assert len(chunks) == 1
    assert chunks[0].index == 0


def test_empty_text_yields_no_chunks():
    assert chunk_text("   \n\n  ") == []


def test_long_text_splits_with_overlap():
    text = "\n\n".join(para(f"w{i}") for i in range(30))
    chunks = chunk_text(text)
    assert len(chunks) > 1
    # Every chunk after the first starts with overlap from its predecessor.
    for prev, cur in itertools.pairwise(chunks):
        overlap_head = cur.text.split("\n\n")[0]
        assert overlap_head in prev.text
        assert len(overlap_head) <= OVERLAP_CHARS
    # Chunks stay near the target size (plus overlap slack).
    assert all(len(c.text) < TARGET_CHARS * 2 for c in chunks)


def test_oversized_paragraph_is_hard_split():
    text = "x" * (TARGET_CHARS * 4)
    chunks = chunk_text(text)
    assert len(chunks) >= 3


def test_tiny_tail_merges_into_previous():
    text = "\n\n".join([para("body") for _ in range(10)] + ["tiny tail"])
    chunks = chunk_text(text)
    assert "tiny tail" in chunks[-1].text
    assert chunks[-1].text != "tiny tail"


def test_contextualize_prefixes_title():
    chunks = chunk_text("some body text")
    assert contextualize("My Title", chunks[0]).startswith("My Title\n\n")
