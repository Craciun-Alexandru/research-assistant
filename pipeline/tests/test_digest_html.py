"""Tests for arxiv_digest.digest_html HTML formatting functions."""

from arxiv_digest.digest_html import _score_color, generate_html


def test_html_document_structure(sample_digest):
    html = generate_html(sample_digest)
    assert "<!DOCTYPE html>" in html
    assert "<html" in html
    assert "</html>" in html
    assert "2026-02-19" in html


def test_html_contains_paper_title(sample_digest):
    html = generate_html(sample_digest)
    assert "Diffusion Models with Neural Network Architectures" in html


def test_html_contains_arxiv_link(sample_digest):
    html = generate_html(sample_digest)
    assert "https://arxiv.org/pdf/2602.12345" in html
    assert "2602.12345" in html


def test_html_contains_score(sample_digest):
    html = generate_html(sample_digest)
    assert "9.2/10" in html


def test_html_escapes_special_characters():
    digest = {
        "digest_date": "2026-02-19",
        "summary": "Test <script>alert('xss')</script> & entities",
        "total_reviewed": 1,
        "papers": [
            {
                "arxiv_id": "2602.99999",
                "title": 'Paper with <b>HTML</b> & "quotes"',
                "authors": ["Author <One>"],
                "categories": ["cs.LG"],
                "score": 8.0,
                "pdf_url": "https://arxiv.org/pdf/2602.99999",
                "summary": "Summary with <tags>",
                "key_insight": "Insight & more",
                "relevance": 'Relevance "quoted"',
            }
        ],
    }
    html = generate_html(digest)
    # Raw HTML tags should be escaped
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;HTML&lt;/b&gt;" in html
    assert "&amp; &quot;quotes&quot;" in html


def test_score_color_high():
    assert _score_color(9.5) == "#1b5e20"
    assert _score_color(9.0) == "#1b5e20"


def test_score_color_medium_high():
    assert _score_color(7.5) == "#2e7d32"
    assert _score_color(7.0) == "#2e7d32"


def test_score_color_medium():
    assert _score_color(6.0) == "#f57f17"
    assert _score_color(5.0) == "#f57f17"


def test_score_color_low():
    assert _score_color(4.0) == "#c62828"
    assert _score_color(0.0) == "#c62828"


def test_html_empty_papers():
    digest = {
        "digest_date": "2026-02-19",
        "summary": "",
        "total_reviewed": 0,
        "papers": [],
    }
    html = generate_html(digest)
    assert "<!DOCTYPE html>" in html
    assert "0 papers selected from 0 top candidates" in html


def test_html_paper_count(sample_digest):
    html = generate_html(sample_digest)
    assert "1 papers selected from 25 top candidates" in html
