"""Tests for arxiv_digest.download — body extraction and LaTeXDownloader."""

import io
import tarfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from arxiv_digest.download import LaTeXDownloader, _latex_to_markdown, extract_body

# ── Fixtures: LaTeX documents ────────────────────────────────────────

FULL_DOC = r"""
\documentclass{article}
\usepackage{amsmath}
\begin{document}
\begin{abstract}
We study an important problem.
\end{abstract}
\section{Introduction}
This is the introduction with key ideas.
\section{Methods}
These are the methods.
\section{Conclusion}
We conclude.
\appendix
\section{Proofs}
Long proof here.
\end{document}
"""

DOC_APPENDIX_ENV = r"""
\documentclass{article}
\begin{document}
\section{Introduction}
Intro text.
\section{Conclusion}
Conclusion text.
\begin{appendix}
\section{Extra}
Appendix content.
\end{appendix}
\end{document}
"""

DOC_APPENDIX_SECTION = r"""
\documentclass{article}
\begin{document}
\section{Introduction}
Intro text.
\section{Appendix}
Appendix content.
\end{document}
"""

DOC_APPENDIX_SECTION_STAR = r"""
\documentclass{article}
\begin{document}
\section{Introduction}
Intro text.
\section*{Appendix A}
More appendix content.
\end{document}
"""

DOC_BIBLIOGRAPHY = r"""
\documentclass{article}
\begin{document}
\section{Introduction}
Intro text.
\section{Conclusion}
Conclusion text.
\bibliography{refs}
\end{document}
"""

DOC_END_DOCUMENT_ONLY = r"""
\documentclass{article}
\begin{document}
\section{Introduction}
All the content is here.
\section{Conclusion}
Final words.
\end{document}
"""

DOC_NO_BEGIN_DOCUMENT = r"""
\documentclass{article}
\usepackage{amsmath}
\section{Introduction}
Orphaned content with no begin document.
"""


# ── extract_body ─────────────────────────────────────────────────────


def test_extract_body_basic():
    """Intro and conclusion included; \\appendix command truncates."""
    body = extract_body(FULL_DOC)
    assert "introduction with key ideas" in body
    assert "These are the methods" in body
    assert "We conclude" in body
    # Everything after \appendix must be absent
    assert r"\appendix" not in body
    assert "Long proof here" not in body


def test_extract_body_appendix_command():
    r"""Bare \appendix\n acts as the truncation boundary."""
    content = r"""
\begin{document}
\section{Introduction}
Intro here.
\appendix
\section{A. Extra Proofs}
Should be cut.
\end{document}
"""
    body = extract_body(content)
    assert "Intro here" in body
    assert "Should be cut" not in body


def test_extract_body_appendix_environment():
    r"""\\begin{appendix} is the truncation boundary."""
    body = extract_body(DOC_APPENDIX_ENV)
    assert "Intro text" in body
    assert "Conclusion text" in body
    assert "Appendix content" not in body


def test_extract_body_appendix_section():
    r"""\\section{Appendix} is the truncation boundary."""
    body = extract_body(DOC_APPENDIX_SECTION)
    assert "Intro text" in body
    assert "Appendix content" not in body


def test_extract_body_appendix_section_star():
    r"""\\section*{Appendix A} is the truncation boundary."""
    body = extract_body(DOC_APPENDIX_SECTION_STAR)
    assert "Intro text" in body
    assert "More appendix content" not in body


def test_extract_body_bibliography():
    r"""\\bibliography{refs} acts as a boundary when no \\appendix is present."""
    body = extract_body(DOC_BIBLIOGRAPHY)
    assert "Intro text" in body
    assert "Conclusion text" in body
    assert r"\bibliography" not in body


def test_extract_body_end_document_only():
    r"""When no appendix markers exist, full body up to \\end{document} is returned."""
    body = extract_body(DOC_END_DOCUMENT_ONLY)
    assert "All the content is here" in body
    assert "Final words" in body
    assert r"\end{document}" not in body


def test_extract_body_no_begin_document():
    r"""Malformed source without \\begin{document} returns empty string."""
    assert extract_body(DOC_NO_BEGIN_DOCUMENT) == ""


# ── LaTeXDownloader integration ──────────────────────────────────────


def _make_tar_gz(tex_content: str) -> bytes:
    """Build a gzip-compressed tar archive containing main.tex."""
    encoded = tex_content.encode("utf-8")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="main.tex")
        info.size = len(encoded)
        tar.addfile(info, io.BytesIO(encoded))
    return buf.getvalue()


@pytest.fixture()
def downloader(tmp_path: Path) -> LaTeXDownloader:
    return LaTeXDownloader(tmp_path)


PAPER = {
    "arxiv_id": "2602.99999",
    "title": "Test Paper on Important Topics",
    "score": 8.5,
}


def test_download_paper_integration(downloader: LaTeXDownloader, tmp_path: Path):
    """Mock network → gzip'd tarball → verify .txt written, appendix absent."""
    tar_data = _make_tar_gz(FULL_DOC)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = tar_data
    mock_resp.raise_for_status = MagicMock()

    with patch("arxiv_digest.extract_latex.requests.get", return_value=mock_resp):
        result = downloader.download_paper(PAPER)

    assert result["status"] == "success"
    txt_path = tmp_path / "2602.99999.txt"
    assert txt_path.exists()
    body = txt_path.read_text()
    assert "introduction with key ideas" in body
    assert "We conclude" in body
    # Appendix section content must not appear
    assert "Long proof here" not in body
    assert downloader.stats["success"] == 1


def test_download_paper_skip_existing(downloader: LaTeXDownloader, tmp_path: Path):
    """Pre-existing .txt is not overwritten; status is 'skipped'."""
    txt_path = tmp_path / "2602.99999.txt"
    txt_path.write_text("original content", encoding="utf-8")

    result = downloader.download_paper(PAPER)

    assert result["status"] == "skipped"
    assert txt_path.read_text() == "original content"
    assert downloader.stats["skipped"] == 1


def test_download_paper_source_unavailable(downloader: LaTeXDownloader, tmp_path: Path):
    """When download_source returns None, status is 'no_source' and no file is created."""
    with patch.object(downloader._extractor, "download_source", return_value=None):
        result = downloader.download_paper(PAPER)

    assert result["status"] == "no_source"
    assert not (tmp_path / "2602.99999.txt").exists()
    assert downloader.stats["no_source"] == 1


# ── _latex_to_markdown ────────────────────────────────────────────────

SIMPLE_BODY = r"""
\section{Introduction}
Gradient descent \textbf{converges} quickly.
\subsection{Background}
Prior work is relevant.
\begin{itemize}
\item Fast
\item Reliable
\end{itemize}
"""


def test_latex_to_markdown_produces_structure():
    """pandoc converts sections to headings and preserves prose."""
    md = _latex_to_markdown(SIMPLE_BODY)
    # Section heading present in some form
    assert "Introduction" in md
    # Prose preserved
    assert "converges" in md
    assert "Prior work" in md
    # List items present
    assert "Fast" in md
    assert "Reliable" in md


def test_latex_to_markdown_fallback_when_pandoc_absent():
    """When pandoc is not found, falls back to clean_latex output."""
    with patch("arxiv_digest.download._PANDOC", None):
        result = _latex_to_markdown(SIMPLE_BODY)
    # clean_latex output still contains the prose
    assert "converges" in result
    assert "Prior work" in result
