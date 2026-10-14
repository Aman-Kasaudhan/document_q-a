import pytest

from src.chunking import chunk_text, normalise

TEXT = (
    "First paragraph about leave. It has two sentences.\n\n"
    "Second paragraph about security. It also has two sentences.\n\n"
    "Third paragraph about travel and expenses with a few more words in it."
)


def test_offsets_point_back_into_the_text():
    chunks = chunk_text(TEXT, size=120, overlap=20)
    assert len(chunks) > 1
    for ch in chunks:
        assert TEXT[ch.start:ch.end].strip() == ch.text


def test_chunks_cover_the_whole_document_in_order():
    chunks = chunk_text(TEXT, size=120, overlap=20)
    assert chunks[0].start == 0
    assert chunks[-1].end == len(TEXT)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert all(a.start < b.start for a, b in zip(chunks, chunks[1:]))


def test_long_paragraph_is_split_to_respect_size():
    long_text = "This is a sentence about policy. " * 40
    chunks = chunk_text(normalise(long_text), size=200, overlap=0)
    assert len(chunks) > 3
    assert all(len(c.text) <= 200 for c in chunks)


def test_overlap_repeats_text_between_neighbours():
    long_text = "word " * 200
    chunks = chunk_text(normalise(long_text), size=100, overlap=30)
    assert chunks[1].start < chunks[0].end   # neighbours overlap


def test_empty_text_gives_no_chunks():
    assert chunk_text("", 100, 10) == []


@pytest.mark.parametrize("size,overlap", [(0, 0), (100, 100), (100, -1)])
def test_invalid_parameters_are_rejected(size, overlap):
    with pytest.raises(ValueError):
        chunk_text("hello world", size, overlap)
