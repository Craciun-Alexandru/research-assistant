"""Tests for arxiv_digest.extract_latex — LaTeX parsing and metadata extraction."""

import gzip
import io
import tarfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from arxiv_digest.extract_latex import LaTeXMetadataExtractor, LaTeXParser

# ── Fixtures: sample LaTeX documents ────────────────────────────────

BASIC_DOC = r"""
\documentclass{article}
\title{On the Convergence of Gradient Descent}
\author{Alice Smith \and Bob Jones}
\begin{document}
\begin{abstract}
We study the convergence properties of gradient descent
for non-convex optimization problems.
\end{abstract}
\section{Introduction}
Gradient descent is a fundamental optimization algorithm.
It has been widely used in machine learning and deep learning.
We provide new convergence guarantees under mild assumptions.
\section{Methods}
Some methods here.
\end{document}
"""

NESTED_BRACES_DOC = r"""
\documentclass{article}
\title{Groups {$G$} and Their {Representations}}
\author{Carol Williams}
\begin{document}
\begin{abstract}
We study groups and representations.
\end{abstract}
\end{document}
"""

KEYWORDS_COMMAND_DOC = r"""
\documentclass{article}
\title{A Paper}
\keywords{machine learning, optimization, convergence theory}
\begin{document}
\begin{abstract}Abstract text.\end{abstract}
\end{document}
"""

KEYWORDS_ENV_DOC = r"""
\documentclass{article}
\title{Another Paper}
\begin{document}
\begin{abstract}Abstract text.\end{abstract}
\begin{keywords}
deep learning; neural networks; generalization
\end{keywords}
\end{document}
"""

COMPLEX_AUTHORS_DOC = r"""
\documentclass{article}
\author{Alice Smith\thanks{Supported by NSF}\affiliation{MIT} \and
Bob Jones\email{bob@example.com}\affiliation{Stanford} \and
Carol Williams}
\begin{document}
\end{document}
"""

NUMBERED_INTRO_DOC = r"""
\documentclass{article}
\begin{document}
\section{1. Introduction}
This is the numbered introduction section.
It discusses background and motivation.
\section{2. Methods}
Some methods here.
\end{document}
"""

IEEE_KEYWORDS_DOC = r"""
\documentclass{article}
\begin{document}
\begin{IEEEkeywords}
signal processing, wavelet transform, compression
\end{IEEEkeywords}
\end{document}
"""

TITLE_SHORT_DOC = r"""
\documentclass{article}
\title[Short Title]{Full Title With More Detail}
\begin{document}
\end{document}
"""


# ── LaTeXParser: title extraction ────────────────────────────────────


def test_extract_title_basic():
    title = LaTeXParser.extract_title(BASIC_DOC)
    assert title == "On the Convergence of Gradient Descent"


def test_extract_title_nested_braces():
    title = LaTeXParser.extract_title(NESTED_BRACES_DOC)
    assert "Groups" in title
    assert "Representations" in title


def test_extract_title_short_form():
    title = LaTeXParser.extract_title(TITLE_SHORT_DOC)
    assert title == "Full Title With More Detail"


def test_extract_title_not_found():
    assert LaTeXParser.extract_title(r"\begin{document} No title here \end{document}") == ""


# ── LaTeXParser: author extraction ───────────────────────────────────


def test_extract_authors_basic():
    authors = LaTeXParser.extract_authors(BASIC_DOC)
    assert len(authors) == 2
    assert "Alice Smith" in authors
    assert "Bob Jones" in authors


def test_extract_authors_complex():
    authors = LaTeXParser.extract_authors(COMPLEX_AUTHORS_DOC)
    assert "Alice Smith" in authors
    assert "Bob Jones" in authors
    assert "Carol Williams" in authors


def test_extract_authors_empty():
    authors = LaTeXParser.extract_authors(r"\documentclass{article}\begin{document}\end{document}")
    assert authors == []


# ── LaTeXParser: keyword extraction ──────────────────────────────────


def test_extract_keywords_command():
    keywords = LaTeXParser.extract_keywords(KEYWORDS_COMMAND_DOC)
    assert len(keywords) == 3
    assert "machine learning" in keywords
    assert "optimization" in keywords
    assert "convergence theory" in keywords


def test_extract_keywords_environment():
    keywords = LaTeXParser.extract_keywords(KEYWORDS_ENV_DOC)
    assert len(keywords) == 3
    assert "deep learning" in keywords
    assert "neural networks" in keywords


def test_extract_keywords_ieee():
    keywords = LaTeXParser.extract_keywords(IEEE_KEYWORDS_DOC)
    assert len(keywords) == 3
    assert "signal processing" in keywords


def test_extract_keywords_not_found():
    keywords = LaTeXParser.extract_keywords(BASIC_DOC)
    assert keywords == []


# ── LaTeXParser: abstract extraction ─────────────────────────────────


def test_extract_abstract():
    abstract = LaTeXParser.extract_abstract(BASIC_DOC)
    assert "convergence" in abstract
    assert "gradient descent" in abstract


def test_extract_abstract_not_found():
    doc = r"\documentclass{article}\begin{document}No abstract.\end{document}"
    assert LaTeXParser.extract_abstract(doc) == ""


# ── LaTeXParser: introduction extraction ─────────────────────────────


def test_extract_introduction_basic():
    intro = LaTeXParser.extract_introduction(BASIC_DOC)
    assert "fundamental optimization algorithm" in intro
    assert "convergence guarantees" in intro
    # Should not contain content from Methods section
    assert "Some methods here" not in intro


def test_extract_introduction_numbered():
    intro = LaTeXParser.extract_introduction(NUMBERED_INTRO_DOC)
    assert "numbered introduction section" in intro
    assert "background and motivation" in intro


def test_extract_introduction_not_found():
    doc = r"\documentclass{article}\begin{document}\section{Background}Stuff\end{document}"
    assert LaTeXParser.extract_introduction(doc) == ""


def test_extract_introduction_no_truncation():
    long_intro = r"\section{Introduction}" + "word " * 1000 + r"\section{Methods}"
    intro = LaTeXParser.extract_introduction(long_intro)
    assert len(intro) > 2000


# ── LaTeXParser: utility methods ─────────────────────────────────────


def test_strip_comments():
    content = "Real text % this is a comment\nMore text"
    result = LaTeXParser.strip_comments(content)
    assert "Real text" in result
    assert "this is a comment" not in result


def test_strip_comments_escaped_percent():
    content = r"The rate is 50\% of the total"
    result = LaTeXParser.strip_comments(content)
    assert r"50\%" in result


def test_clean_latex_emph():
    assert "important" in LaTeXParser.clean_latex(r"\emph{important}")


def test_clean_latex_textbf():
    assert "bold text" in LaTeXParser.clean_latex(r"\textbf{bold text}")


def test_clean_latex_cite():
    result = LaTeXParser.clean_latex(r"as shown in \cite{smith2024}")
    assert "smith2024" not in result
    assert "as shown in" in result


def test_clean_latex_math():
    result = LaTeXParser.clean_latex(r"The value $x^2 + y^2$ is positive")
    assert "$" not in result
    assert "positive" in result


def test_extract_braced_content_nested():
    content = r"{outer {inner} text}"
    result = LaTeXParser.extract_braced_content(content, 0)
    assert result == "outer {inner} text"


def test_extract_braced_content_empty():
    content = r"{}"
    result = LaTeXParser.extract_braced_content(content, 0)
    assert result == ""


def test_extract_braced_content_no_brace():
    result = LaTeXParser.extract_braced_content("no braces here", 0)
    assert result == ""


# ── LaTeXParser: find_main_tex_file ──────────────────────────────────


def test_find_main_tex_file(tmp_path: Path):
    (tmp_path / "main.tex").write_text(r"\documentclass{article}\begin{document}\end{document}")
    (tmp_path / "other.tex").write_text(r"\section{Something}")
    result = LaTeXParser.find_main_tex_file(tmp_path)
    assert result is not None
    assert result.name == "main.tex"


def test_find_main_tex_file_prefers_main(tmp_path: Path):
    """main.tex should be preferred over a larger file."""
    (tmp_path / "main.tex").write_text(r"\documentclass{article}\begin{document}\end{document}")
    (tmp_path / "big.tex").write_text(
        r"\documentclass{article}\begin{document}" + "x" * 10000 + r"\end{document}"
    )
    result = LaTeXParser.find_main_tex_file(tmp_path)
    assert result is not None
    assert result.name == "main.tex"


def test_find_main_tex_file_fallback(tmp_path: Path):
    """Falls back to largest file with \\documentclass when no common name."""
    (tmp_path / "my_paper.tex").write_text(
        r"\documentclass{article}\begin{document}" + "x" * 100 + r"\end{document}"
    )
    (tmp_path / "small.tex").write_text(r"\documentclass{article}")
    result = LaTeXParser.find_main_tex_file(tmp_path)
    assert result is not None
    assert result.name == "my_paper.tex"


def test_find_main_tex_file_none(tmp_path: Path):
    (tmp_path / "notes.txt").write_text("just notes")
    assert LaTeXParser.find_main_tex_file(tmp_path) is None


# ── LaTeXParser: expand_inputs ───────────────────────────────────────


def test_expand_inputs(tmp_path: Path):
    main_content = r"""
\documentclass{article}
\begin{document}
\input{section1}
\end{document}
"""
    section_content = r"This is the content of section one."

    (tmp_path / "main.tex").write_text(main_content)
    (tmp_path / "section1.tex").write_text(section_content)

    result = LaTeXParser.expand_inputs(main_content, tmp_path)
    assert "content of section one" in result


def test_expand_inputs_without_extension(tmp_path: Path):
    """Input without .tex extension should still resolve."""
    main_content = r"\input{intro}"
    (tmp_path / "intro.tex").write_text("Introduction text here.")

    result = LaTeXParser.expand_inputs(main_content, tmp_path)
    assert "Introduction text here" in result


def test_expand_inputs_missing_file():
    """Missing input file should leave the directive in place."""
    content = r"\input{nonexistent}"
    result = LaTeXParser.expand_inputs(content, Path("/tmp/empty"))
    assert r"\input{nonexistent}" in result


# ── LaTeXParser: full parse ──────────────────────────────────────────


def test_parse_full(tmp_path: Path):
    (tmp_path / "main.tex").write_text(BASIC_DOC)
    content = (tmp_path / "main.tex").read_text()
    result = LaTeXParser.parse(content, tmp_path)

    assert result["title"] == "On the Convergence of Gradient Descent"
    assert len(result["authors"]) == 2
    assert "convergence" in result["abstract"]
    assert "fundamental optimization algorithm" in result["introduction"]
    assert result["keywords"] == []  # BASIC_DOC has no keywords


# ── LaTeXMetadataExtractor: source extraction ────────────────────────


def test_extract_source_tar_gz(tmp_path: Path):
    """Test extraction of a tar.gz source bundle."""
    tex_content = BASIC_DOC.encode("utf-8")

    # Create tar.gz in memory
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="main.tex")
        info.size = len(tex_content)
        tar.addfile(info, io.BytesIO(tex_content))
    tar_data = buf.getvalue()

    extractor = LaTeXMetadataExtractor()
    assert extractor.extract_source(tar_data, tmp_path)
    assert (tmp_path / "main.tex").exists()
    assert r"\documentclass" in (tmp_path / "main.tex").read_text()


def test_extract_source_plain_gz(tmp_path: Path):
    """Test extraction of a gzip-compressed single file."""
    tex_content = BASIC_DOC.encode("utf-8")
    gz_data = gzip.compress(tex_content)

    extractor = LaTeXMetadataExtractor()
    assert extractor.extract_source(gz_data, tmp_path)
    assert (tmp_path / "main.tex").exists()


def test_extract_source_plain_text(tmp_path: Path):
    """Test extraction of plain-text LaTeX source."""
    tex_data = BASIC_DOC.encode("utf-8")

    extractor = LaTeXMetadataExtractor()
    assert extractor.extract_source(tex_data, tmp_path)
    assert (tmp_path / "main.tex").exists()


def test_extract_source_path_traversal(tmp_path: Path):
    """Tar members with path traversal should be filtered out."""
    tex_content = BASIC_DOC.encode("utf-8")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        # Safe member
        info = tarfile.TarInfo(name="main.tex")
        info.size = len(tex_content)
        tar.addfile(info, io.BytesIO(tex_content))
        # Unsafe member
        info_bad = tarfile.TarInfo(name="../../../etc/passwd")
        info_bad.size = 4
        tar.addfile(info_bad, io.BytesIO(b"evil"))
    tar_data = buf.getvalue()

    extractor = LaTeXMetadataExtractor()
    assert extractor.extract_source(tar_data, tmp_path)
    assert (tmp_path / "main.tex").exists()
    # The unsafe file should NOT have been extracted
    assert not (tmp_path / ".." / ".." / ".." / "etc" / "passwd").exists()


def test_extract_source_invalid_data(tmp_path: Path):
    """Invalid data should return False."""
    extractor = LaTeXMetadataExtractor()
    assert not extractor.extract_source(b"not valid data at all \x00\x01\x02", tmp_path)


# ── LaTeXMetadataExtractor: process_paper integration ────────────────


def test_process_paper_integration(tmp_path: Path):
    """Integration test: mock download, verify full pipeline."""
    tex_content = BASIC_DOC.encode("utf-8")
    gz_data = gzip.compress(tex_content)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = gz_data
    mock_response.raise_for_status = MagicMock()

    paper = {
        "arxiv_id": "2602.99999",
        "title": "On the Convergence of Gradient Descent",
    }

    extractor = LaTeXMetadataExtractor()

    with patch("arxiv_digest.extract_latex.requests.get", return_value=mock_response):
        result = extractor.process_paper(paper, 1, 1)

    assert result is not None
    assert result["title"] == "On the Convergence of Gradient Descent"
    assert len(result["authors"]) == 2
    assert "convergence" in result["abstract"]
    assert "fundamental optimization algorithm" in result["introduction"]


def test_process_paper_download_failure():
    """When download fails, process_paper returns None."""
    mock_response = MagicMock()
    mock_response.status_code = 404

    paper = {"arxiv_id": "0000.00000", "title": "Ghost Paper"}
    extractor = LaTeXMetadataExtractor()

    with patch(
        "arxiv_digest.extract_latex.requests.get",
        return_value=mock_response,
    ) as mock_get:
        mock_get.return_value.status_code = 404
        mock_get.return_value.content = None
        # Make download_source return None
        with patch.object(extractor, "download_source", return_value=None):
            result = extractor.process_paper(paper, 1, 1)

    assert result is None
    assert extractor.stats["failed"] == 1
