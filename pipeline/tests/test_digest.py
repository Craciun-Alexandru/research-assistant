"""Tests for arxiv_digest.digest formatting functions."""

from arxiv_digest.digest import format_authors, format_categories, generate_markdown


def test_generate_markdown_structure(sample_digest):
    md = generate_markdown(sample_digest)
    assert "# 📚 arXiv Research Digest" in md
    assert "2026-02-19" in md
    assert "Diffusion Models with Neural Network Architectures" in md


def test_generate_markdown_paper_count(sample_digest):
    md = generate_markdown(sample_digest)
    assert "1 selected from 25 top candidates" in md


def test_generate_markdown_key_insight(sample_digest):
    md = generate_markdown(sample_digest)
    assert "The key theoretical contribution is a new convergence bound." in md
    assert "### Key Insight" in md


# ── format_authors ────────────────────────────────────────────────────


def test_format_authors_under_limit():
    result = format_authors(["Alice Smith", "Bob Jones", "Carol Williams"])
    assert result == "Alice Smith, Bob Jones, Carol Williams"


def test_format_authors_truncation():
    authors = ["Alice Smith", "Bob Jones", "Carol Williams", "David Brown"]
    result = format_authors(authors, max_authors=3)
    assert result == "Alice Smith, Bob Jones, et al. (4 total)"


def test_format_authors_empty():
    result = format_authors([])
    assert result == "Unknown"


# ── format_categories ─────────────────────────────────────────────────


def test_format_categories_normal():
    result = format_categories(["cs.LG", "stat.ML"])
    assert result == "cs.LG, stat.ML"


def test_format_categories_empty():
    result = format_categories([])
    assert result == "N/A"
