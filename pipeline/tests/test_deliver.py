"""Tests for arxiv_digest.deliver split_markdown function."""

from arxiv_digest.deliver import split_markdown

MAX = 100


def test_split_markdown_short_content():
    content = "Short content"
    chunks = split_markdown(content, max_length=MAX)
    assert len(chunks) == 1
    assert chunks[0] == "Short content"


def test_split_markdown_splits_on_delimiter():
    content = "Section one\n---\nSection two\n---\nSection three"
    chunks = split_markdown(content, max_length=MAX)
    assert len(chunks) >= 2


def test_split_markdown_each_chunk_within_limit():
    # Build content with sections that individually fit
    sections = [f"Section {i}: some text here." for i in range(10)]
    content = "\n---\n".join(sections)
    chunks = split_markdown(content, max_length=MAX)
    for chunk in chunks:
        assert len(chunk) <= MAX


def test_split_markdown_long_chunk_subdivided():
    # A single section longer than max_length should be split further
    long_section = "A" * 60 + "\n\n" + "B" * 60
    content = long_section  # no --- delimiter, single section > MAX
    chunks = split_markdown(content, max_length=MAX)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk) <= MAX


def test_split_markdown_empty_sections_removed():
    content = "Section one\n---\n\n---\nSection two"
    chunks = split_markdown(content, max_length=MAX)
    # Empty sections between consecutive --- should not produce empty chunks
    assert all(chunk.strip() for chunk in chunks)
