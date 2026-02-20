"""
Extract structured metadata from arXiv LaTeX sources.

Downloads LaTeX source tarballs from arXiv, parses them for title, authors,
keywords, abstract, and introduction text. Enriches ``filtered_papers.json``
with a ``latex_metadata`` dict per paper.

Runs between prefilter and scorer in the pipeline.

Usage:
    python -m arxiv_digest.extract_latex
"""

import gzip
import io
import re
import shutil
import tarfile
import tempfile
import time
from pathlib import Path

import requests

from arxiv_digest.config import (
    ARXIV_HEADERS,
    ARXIV_REQUEST_DELAY,
    FILTERED_PAPERS_PATH,
)
from arxiv_digest.utils import load_json, save_json


class LaTeXParser:
    """Pure LaTeX parsing logic — no I/O, independently testable."""

    # Common main tex filenames, checked first
    _COMMON_NAMES = ("main.tex", "paper.tex", "ms.tex", "article.tex")

    @staticmethod
    def find_main_tex_file(tex_dir: Path) -> Path | None:
        """Find the main ``.tex`` file containing ``\\documentclass``.

        Priority: common names (main.tex, paper.tex, etc.), then largest file
        with ``\\documentclass``.
        """
        tex_files = list(tex_dir.rglob("*.tex"))
        if not tex_files:
            return None

        # Check common names first
        for name in LaTeXParser._COMMON_NAMES:
            for tf in tex_files:
                if tf.name == name:
                    try:
                        content = tf.read_text(encoding="utf-8", errors="replace")
                        if r"\documentclass" in content:
                            return tf
                    except OSError:
                        continue

        # Fall back to largest file with \documentclass
        candidates: list[tuple[int, Path]] = []
        for tf in tex_files:
            try:
                content = tf.read_text(encoding="utf-8", errors="replace")
                if r"\documentclass" in content:
                    candidates.append((len(content), tf))
            except OSError:
                continue

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]

        return None

    @staticmethod
    def expand_inputs(content: str, base_dir: Path, depth: int = 0) -> str:
        r"""Recursively expand ``\input{}`` and ``\include{}`` directives.

        Args:
            content: LaTeX source text.
            base_dir: Directory to resolve relative paths against.
            depth: Current recursion depth (max 10).

        Returns:
            Content with input/include directives replaced by file contents.
        """
        if depth > 10:
            return content

        def _replace(match: re.Match) -> str:
            filename = match.group(1)
            # Try with and without .tex extension
            for candidate in [base_dir / filename, base_dir / f"{filename}.tex"]:
                if candidate.is_file():
                    try:
                        sub_content = candidate.read_text(encoding="utf-8", errors="replace")
                        return LaTeXParser.expand_inputs(sub_content, candidate.parent, depth + 1)
                    except OSError:
                        return match.group(0)
            return match.group(0)

        return re.sub(r"\\(?:input|include)\{([^}]+)\}", _replace, content)

    @staticmethod
    def strip_comments(content: str) -> str:
        r"""Remove LaTeX comments (``%`` to end of line), respecting ``\%``."""
        return re.sub(r"(?<!\\)%.*", "", content)

    @staticmethod
    def extract_braced_content(content: str, start_pos: int) -> str:
        """Extract content within matched braces starting at ``start_pos``.

        Args:
            content: Full text.
            start_pos: Position of the opening ``{``.

        Returns:
            The text between the outermost braces (exclusive).
        """
        if start_pos >= len(content) or content[start_pos] != "{":
            return ""

        depth = 0
        i = start_pos
        while i < len(content):
            if content[i] == "{" and (i == 0 or content[i - 1] != "\\"):
                depth += 1
            elif content[i] == "}" and (i == 0 or content[i - 1] != "\\"):
                depth -= 1
                if depth == 0:
                    return content[start_pos + 1 : i]
            i += 1
        return ""

    @staticmethod
    def clean_latex(text: str) -> str:
        r"""Strip common LaTeX commands and math markup from text.

        Removes ``\emph{}``, ``\textbf{}``, ``\cite{}``, ``\ref{}``,
        inline math ``$...$``, display math ``\[...\]``, and remaining
        commands. Normalizes whitespace.
        """
        # Remove \cite{...}, \ref{...}, \label{...}
        text = re.sub(r"\\(?:cite|ref|label|eqref|cref|Cref)\{[^}]*\}", "", text)
        # Unwrap \emph{...}, \textbf{...}, \textit{...}, \text{...}
        text = re.sub(r"\\(?:emph|textbf|textit|text|textrm|textsc)\{([^}]*)\}", r"\1", text)
        # Remove display math \[...\] and \(...\)
        text = re.sub(r"\\\[.*?\\\]", "", text, flags=re.DOTALL)
        text = re.sub(r"\\\(.*?\\\)", "", text, flags=re.DOTALL)
        # Remove inline math $...$  (non-greedy, single-line)
        text = re.sub(r"(?<!\$)\$(?!\$).*?(?<!\$)\$(?!\$)", "", text)
        # Remove display math $$...$$
        text = re.sub(r"\$\$.*?\$\$", "", text, flags=re.DOTALL)
        # Remove remaining commands like \foo but keep the text after
        text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^}]*\})*", "", text)
        # Remove stray braces
        text = re.sub(r"[{}]", "", text)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def extract_title(content: str) -> str:
        r"""Extract paper title from ``\title{...}``."""
        # Handle \title[short]{Full Title}
        match = re.search(r"\\title\s*(?:\[[^\]]*\])?\s*\{", content)
        if not match:
            return ""
        brace_start = match.end() - 1
        raw = LaTeXParser.extract_braced_content(content, brace_start)
        return LaTeXParser.clean_latex(raw)

    @staticmethod
    def extract_authors(content: str) -> list[str]:
        r"""Extract author names from ``\author{...}``.

        Strips ``\affiliation{}``, ``\thanks{}``, ``\email{}``. Splits on
        ``\and``, ``\\``, or commas.
        """
        match = re.search(r"\\author\s*(?:\[[^\]]*\])?\s*\{", content)
        if not match:
            return []
        brace_start = match.end() - 1
        raw = LaTeXParser.extract_braced_content(content, brace_start)
        if not raw:
            return []

        # Remove sub-commands
        raw = re.sub(r"\\(?:affiliation|thanks|email|inst|orcid|fnmark)\{[^}]*\}", "", raw)
        raw = re.sub(r"\\(?:affiliationmark|thanksmark)\s*(?:\[[^\]]*\])?", "", raw)

        # Split on \and, \\, or 'and' surrounded by whitespace
        parts = re.split(r"\\and\b|\\\\|\band\b", raw)
        authors: list[str] = []
        for part in parts:
            # Further split by commas if multiple names remain
            for sub in part.split(","):
                cleaned = LaTeXParser.clean_latex(sub).strip()
                # Filter out empty strings and things that look like affiliations
                if cleaned and len(cleaned) > 1 and not cleaned.startswith("("):
                    authors.append(cleaned)
        return authors

    @staticmethod
    def extract_keywords(content: str) -> list[str]:
        r"""Extract keywords from ``\keywords{...}`` or keyword environments."""
        raw = ""

        # Try \keywords{...} command
        match = re.search(r"\\keywords\s*\{", content)
        if match:
            brace_start = match.end() - 1
            raw = LaTeXParser.extract_braced_content(content, brace_start)

        # Try \begin{keywords}...\end{keywords}
        if not raw:
            match = re.search(r"\\begin\{keywords\}(.*?)\\end\{keywords\}", content, re.DOTALL)
            if match:
                raw = match.group(1)

        # Try \begin{IEEEkeywords}...\end{IEEEkeywords}
        if not raw:
            match = re.search(
                r"\\begin\{IEEEkeywords\}(.*?)\\end\{IEEEkeywords\}", content, re.DOTALL
            )
            if match:
                raw = match.group(1)

        if not raw:
            return []

        # Split on comma, semicolon, or \sep
        parts = re.split(r"[,;]|\\sep\b", raw)
        keywords: list[str] = []
        for part in parts:
            cleaned = LaTeXParser.clean_latex(part).strip()
            if cleaned:
                keywords.append(cleaned)
        return keywords

    @staticmethod
    def extract_abstract(content: str) -> str:
        r"""Extract abstract from ``\begin{abstract}...\end{abstract}``."""
        match = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", content, re.DOTALL)
        if not match:
            return ""
        return LaTeXParser.clean_latex(match.group(1))

    @staticmethod
    def extract_introduction(content: str) -> str:
        r"""Extract introduction section text.

        Matches ``\section{Introduction}``, ``\section{1. Introduction}``, etc.
        Ends at next ``\section``, ``\bibliography``, ``\appendix``, or
        ``\end{document}``. Truncated to 2000 characters.
        """
        # Match various intro heading formats
        match = re.search(
            r"\\section\*?\{(?:\d+\.?\s*)?[Ii]ntroduction\}",
            content,
        )
        if not match:
            return ""

        start = match.end()
        # Find the end boundary
        end_match = re.search(
            r"\\(?:section|bibliography|appendix|end\{document\})",
            content[start:],
        )
        end = start + end_match.start() if end_match else len(content)
        raw = content[start:end]
        cleaned = LaTeXParser.clean_latex(raw)
        return cleaned[:2000]

    @staticmethod
    def parse(content: str, base_dir: Path) -> dict:
        """Parse LaTeX source and extract all metadata fields.

        Args:
            content: Raw LaTeX source text.
            base_dir: Directory for resolving ``\\input``/``\\include`` paths.

        Returns:
            Dict with keys: title, authors, keywords, abstract, introduction.
        """
        content = LaTeXParser.strip_comments(content)
        content = LaTeXParser.expand_inputs(content, base_dir)
        return {
            "title": LaTeXParser.extract_title(content),
            "authors": LaTeXParser.extract_authors(content),
            "keywords": LaTeXParser.extract_keywords(content),
            "abstract": LaTeXParser.extract_abstract(content),
            "introduction": LaTeXParser.extract_introduction(content),
        }


class LaTeXMetadataExtractor:
    """Download and extract metadata from arXiv LaTeX sources.

    Follows the ``PaperDownloader`` pattern from ``download.py``.
    """

    def __init__(self) -> None:
        self.parser = LaTeXParser()
        self.stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}

    def download_source(self, arxiv_id: str) -> bytes | None:
        """Download LaTeX source bundle from arXiv.

        Args:
            arxiv_id: The arXiv paper identifier.

        Returns:
            Raw bytes of the source bundle, or None on failure.
        """
        url = f"https://arxiv.org/e-print/{arxiv_id}"
        try:
            resp = requests.get(url, headers=ARXIV_HEADERS, timeout=30)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            print(f"    Warning: source download failed: {exc}")
            return None

    def extract_source(self, data: bytes, extract_dir: Path) -> bool:
        """Extract LaTeX source archive to a directory.

        Tries tar.gz, then gzip (single file), then plain text.
        Filters tar members for path traversal safety.

        Args:
            data: Raw bytes of the source bundle.
            extract_dir: Directory to extract into.

        Returns:
            True if extraction succeeded.
        """
        # Try tar.gz
        try:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
                # Filter unsafe members
                safe_members = []
                for member in tar.getmembers():
                    if member.name.startswith("/") or ".." in member.name:
                        continue
                    safe_members.append(member)
                tar.extractall(path=extract_dir, members=safe_members, filter="data")
                return True
        except (tarfile.TarError, gzip.BadGzipFile, EOFError):
            pass

        # Try plain gzip (single .tex file)
        try:
            decompressed = gzip.decompress(data)
            (extract_dir / "main.tex").write_bytes(decompressed)
            return True
        except (gzip.BadGzipFile, OSError):
            pass

        # Try plain text
        try:
            text = data.decode("utf-8")
            if r"\documentclass" in text or r"\begin{document}" in text:
                (extract_dir / "main.tex").write_text(text, encoding="utf-8")
                return True
        except (UnicodeDecodeError, OSError):
            pass

        return False

    def process_paper(self, paper: dict, index: int, total: int) -> dict | None:
        """Download, extract, and parse LaTeX metadata for a single paper.

        Args:
            paper: Paper dict (must contain ``arxiv_id``).
            index: 1-based index for progress display.
            total: Total number of papers being processed.

        Returns:
            Parsed metadata dict, or None on failure.
        """
        arxiv_id = paper["arxiv_id"]
        self.stats["total"] += 1

        print(f"  [{index}/{total}] {arxiv_id}: {paper.get('title', '')[:60]}...")

        tmp_dir = tempfile.mkdtemp(prefix="arxiv_latex_")
        try:
            data = self.download_source(arxiv_id)
            if data is None:
                print("    Warning: no source available")
                self.stats["failed"] += 1
                return None

            extract_dir = Path(tmp_dir)
            if not self.extract_source(data, extract_dir):
                print("    Warning: could not extract source")
                self.stats["failed"] += 1
                return None

            main_tex = LaTeXParser.find_main_tex_file(extract_dir)
            if main_tex is None:
                print("    Warning: no main .tex file found")
                self.stats["failed"] += 1
                return None

            content = main_tex.read_text(encoding="utf-8", errors="replace")
            metadata = LaTeXParser.parse(content, main_tex.parent)

            # Check if we got anything useful
            has_content = any(
                [
                    metadata["keywords"],
                    metadata["introduction"],
                ]
            )
            if has_content:
                self.stats["success"] += 1
                kw_count = len(metadata["keywords"])
                intro_len = len(metadata["introduction"])
                print(f"    Extracted: {kw_count} keywords, {intro_len} chars intro")
            else:
                self.stats["skipped"] += 1
                print("    No keywords or introduction found")

            return metadata

        except Exception as exc:
            print(f"    Error processing {arxiv_id}: {exc}")
            self.stats["failed"] += 1
            return None
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def print_summary(self) -> None:
        """Print extraction summary statistics."""
        total = max(self.stats["total"], 1)
        print("\n" + "=" * 60)
        print("LATEX EXTRACTION SUMMARY")
        print("=" * 60)
        print(f"Total papers:      {self.stats['total']}")
        print(
            f"Enriched:          {self.stats['success']} "
            f"({self.stats['success'] / total * 100:.1f}%)"
        )
        print(f"No useful data:    {self.stats['skipped']}")
        print(f"Failed:            {self.stats['failed']}")
        print("=" * 60)


def main() -> None:
    """Extract LaTeX metadata and enrich ``filtered_papers.json``."""
    print("=" * 60)
    print("LaTeX Metadata Extractor")
    print("=" * 60)

    if not FILTERED_PAPERS_PATH.exists():
        print(f"Error: {FILTERED_PAPERS_PATH} not found")
        raise SystemExit(1)

    papers = load_json(FILTERED_PAPERS_PATH)
    print(f"Loaded {len(papers)} papers from {FILTERED_PAPERS_PATH}\n")

    extractor = LaTeXMetadataExtractor()

    for i, paper in enumerate(papers):
        if i > 0:
            time.sleep(ARXIV_REQUEST_DELAY)

        metadata = extractor.process_paper(paper, i + 1, len(papers))
        if metadata is not None:
            paper["latex_metadata"] = metadata

    save_json(papers, FILTERED_PAPERS_PATH)
    print(f"\nSaved enriched papers to {FILTERED_PAPERS_PATH}")

    extractor.print_summary()


if __name__ == "__main__":
    main()
