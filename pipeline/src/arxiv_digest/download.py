r"""
download.py — Download arXiv LaTeX source and extract body text.

Downloads the same e-print source archive used by extract_latex.py, expands
\input directives, strips the preamble and appendices, then converts the body
to structured Markdown via pandoc (falls back to plain-text stripping if
pandoc is unavailable or fails for a given paper).

Papers with no LaTeX source (PDF-only) are skipped silently; reviewer.py
handles missing .txt files gracefully.

Output: resources/papers/{arxiv_id}.txt
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from arxiv_digest.config import (
    ARXIV_REQUEST_DELAY,
    DOWNLOAD_METADATA_PATH,
    PAPERS_DIR,
    SCORED_PAPERS_PATH,
)
from arxiv_digest.extract_latex import LaTeXMetadataExtractor, LaTeXParser

# Path to the pandoc binary, or None if not installed.
_PANDOC: str | None = shutil.which("pandoc")

# Compiled once: marks where the body ends (appendix / bibliography / document end)
APPENDIX_PATTERN = re.compile(
    r"\\appendix\b"
    r"|\\begin\{appendix\}"
    r"|\\section\*?\{(?:appendix|appendices)(?:\s|[}\[])"
    r"|\\bibliography\{"
    r"|\\bibliographystyle\{"
    r"|\\end\{document\}",
    re.IGNORECASE,
)


def extract_body(content: str) -> str:
    r"""Return the document body: after \begin{document}, before the first appendix boundary.

    Args:
        content: Full LaTeX source (comments already stripped).

    Returns:
        Body text, or empty string if \begin{document} is not found.
    """
    doc_start = content.find(r"\begin{document}")
    if doc_start == -1:
        return ""
    body = content[doc_start + len(r"\begin{document}") :]
    m = APPENDIX_PATTERN.search(body)
    return body[: m.start()].strip() if m else body.strip()


def _latex_to_markdown(body: str) -> str:
    """Convert a LaTeX body fragment to structured Markdown using pandoc.

    Runs ``pandoc -f latex -t markdown --wrap=none`` via subprocess.
    Falls back to ``LaTeXParser.clean_latex()`` if pandoc is not installed or
    returns a non-zero exit code for the given input.

    Args:
        body: LaTeX source after ``\\begin{document}`` and before appendix markers.

    Returns:
        Structured Markdown string, or cleaned plain text on fallback.
    """
    if _PANDOC is not None:
        try:
            result = subprocess.run(
                [_PANDOC, "-f", "latex", "-t", "markdown", "--wrap=none"],
                input=body,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            print(
                f"    Warning: pandoc failed (exit {result.returncode}), falling back to plain-text extraction"
            )
        except subprocess.TimeoutExpired:
            print("    Warning: pandoc timed out, falling back to plain-text extraction")
        except OSError as e:
            print(f"    Warning: pandoc error ({e}), falling back to plain-text extraction")
    return LaTeXParser.clean_latex(body)


class LaTeXDownloader:
    """Download arXiv LaTeX source and extract body text for each paper."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._extractor = LaTeXMetadataExtractor()
        self.stats: dict[str, int] = {
            "total": 0,
            "success": 0,
            "skipped": 0,
            "no_source": 0,
            "extract_failed": 0,
            "no_main_tex": 0,
            "empty_body": 0,
        }
        self.download_metadata: list[dict] = []

    def download_paper(self, paper: dict) -> dict:
        """Download and extract body text for a single paper.

        Args:
            paper: Dict with at least ``arxiv_id``, ``title``, and ``score`` keys.

        Returns:
            Metadata dict describing the outcome.
        """
        arxiv_id = paper["arxiv_id"]
        self.stats["total"] += 1

        txt_path = self.output_dir / f"{arxiv_id}.txt"
        if txt_path.exists():
            self.stats["skipped"] += 1
            print("    Already exists, skipping")
            return self._create_metadata(paper, "skipped", 0)

        tmp_dir = tempfile.mkdtemp(prefix="arxiv_dl_")
        try:
            result = self._fetch_and_extract(arxiv_id, Path(tmp_dir))
            if result != "ok":
                return self._create_metadata(paper, result, 0)

            body_text = self._build_body_text(Path(tmp_dir))
            if body_text is None:
                return self._create_metadata(paper, "no_main_tex", 0)
            if not body_text:
                self.stats["empty_body"] += 1
                print("    Empty body after extraction")
                return self._create_metadata(paper, "empty_body", 0)

            txt_path.write_text(body_text, encoding="utf-8")
            size = len(body_text)
            self.stats["success"] += 1
            print(f"    Extracted {size / 1024:.1f} KB body text")
            return self._create_metadata(paper, "success", size)

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _fetch_and_extract(self, arxiv_id: str, tmp_dir: Path) -> str:
        """Download and unpack the source archive.

        Returns:
            ``"ok"`` on success, or a status string on failure.
        """
        data = self._extractor.download_source(arxiv_id)
        if data is None:
            self.stats["no_source"] += 1
            print("    No source available")
            return "no_source"

        if not self._extractor.extract_source(data, tmp_dir):
            self.stats["extract_failed"] += 1
            print("    Could not extract source archive")
            return "extract_failed"

        return "ok"

    def _build_body_text(self, tmp_dir: Path) -> str | None:
        """Find the main .tex file, expand inputs, extract and clean the body.

        Returns:
            Cleaned body text, empty string if body is empty, or None if no
            main .tex file was found.
        """
        main_tex = LaTeXParser.find_main_tex_file(tmp_dir)
        if main_tex is None:
            self.stats["no_main_tex"] += 1
            print("    No main .tex file found")
            return None

        content = main_tex.read_text(encoding="utf-8", errors="replace")
        content = LaTeXParser.strip_comments(content)
        content = LaTeXParser.expand_inputs(content, main_tex.parent)
        body = extract_body(content)
        if not body:
            return ""
        return _latex_to_markdown(body)

    def _create_metadata(self, paper: dict, status: str, txt_size: int) -> dict:
        """Build a metadata record for one paper."""
        arxiv_id = paper["arxiv_id"]
        record: dict = {
            "arxiv_id": arxiv_id,
            "title": paper.get("title", ""),
            "score": paper.get("score", 0.0),
            "status": status,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "size_bytes": txt_size,
        }
        if status == "success":
            record["path"] = f"papers/{arxiv_id}.txt"
        return record

    def save_metadata(self) -> None:
        """Persist download metadata to JSON."""
        output = {
            "download_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "statistics": self.stats,
            "papers": self.download_metadata,
        }
        DOWNLOAD_METADATA_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
        print(f"\nMetadata saved to: {DOWNLOAD_METADATA_PATH}")

    def print_summary(self) -> None:
        """Print download statistics."""
        total = max(self.stats["total"], 1)
        print("\n" + "=" * 60)
        print("DOWNLOAD SUMMARY")
        print("=" * 60)
        print(f"Total papers:      {self.stats['total']}")
        print(
            f"Success:           {self.stats['success']} ({self.stats['success'] / total * 100:.1f}%)"
        )
        print(f"Skipped (exists):  {self.stats['skipped']}")
        print(f"No source:         {self.stats['no_source']}")
        print(f"Extract failed:    {self.stats['extract_failed']}")
        print(f"No main .tex:      {self.stats['no_main_tex']}")
        print(f"Empty body:        {self.stats['empty_body']}")
        print("=" * 60)
        print(f"\nPaper texts saved to: {self.output_dir}")


def main() -> None:
    """Main entry point."""
    print("=" * 60)
    print("arXiv LaTeX Downloader")
    print("=" * 60)

    if not SCORED_PAPERS_PATH.exists():
        print(f"Error: {SCORED_PAPERS_PATH} not found")
        sys.exit(1)

    print(f"\nLoading papers from: {SCORED_PAPERS_PATH}")
    with SCORED_PAPERS_PATH.open() as f:
        data = json.load(f)

    papers = data.get("scored_papers_summary", [])
    print(f"Found {len(papers)} papers to process")

    if not papers:
        print("No papers to download")
        sys.exit(0)

    # Remove stale .txt files from previous runs
    old_txts = list(PAPERS_DIR.glob("*.txt"))
    if old_txts:
        print(f"Removing {len(old_txts)} stale .txt file(s) from previous runs...")
        for f in old_txts:
            f.unlink()

    downloader = LaTeXDownloader(PAPERS_DIR)
    print(f"Output directory: {PAPERS_DIR.absolute()}\n")

    for i, paper in enumerate(papers):
        if i > 0:
            print(f"\nWaiting {ARXIV_REQUEST_DELAY}s (rate limit)...")
            time.sleep(ARXIV_REQUEST_DELAY)

        arxiv_id = paper["arxiv_id"]
        print(f"\n[{i + 1}/{len(papers)}] {arxiv_id}: {paper.get('title', '')[:70]}")
        metadata = downloader.download_paper(paper)
        downloader.download_metadata.append(metadata)

    downloader.save_metadata()
    downloader.print_summary()
    print("\nDone.")


if __name__ == "__main__":
    main()
