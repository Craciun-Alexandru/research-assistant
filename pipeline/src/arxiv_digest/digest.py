#!/usr/bin/env python3
"""
Format digest JSON into Markdown and HTML for email delivery.

Usage:
    python -m arxiv_digest.digest                    # Auto-detect digest_*.json in current/
    python -m arxiv_digest.digest --input digest_2026-02-04.json
    python -m arxiv_digest.digest --input digest_2026-02-04.json --output digest_2026-02-04.md
"""

import argparse
import html as html_lib
import json
import sys
from datetime import datetime

from arxiv_digest.config import CURRENT_RUN_DIR

# ── Markdown ──────────────────────────────────────────────────────────────────

MARKDOWN_TEMPLATE = """# 📚 arXiv Research Digest

**Date:** {date}

{summary_section}

{stats_section}

---
{papers_markdown}
"""

PAPER_TEMPLATE = """
## {number}. {title}

**Authors:** {authors}
**Categories:** {categories}
**Score:** {score}/10
**arXiv:** [{arxiv_id}](<{pdf_url}>)

### Summary

{summary}

### Key Insight

{key_insight}

### Relevance to Your Research

{relevance}
---
"""


def format_authors(authors: list, max_authors: int = 3) -> str:
    """Format author list with truncation."""
    if not authors:
        return "Unknown"
    if len(authors) <= max_authors:
        return ", ".join(authors)
    return ", ".join(authors[0 : max_authors - 1]) + f", et al. ({len(authors)} total)"


def format_categories(categories: list) -> str:
    """Format category list."""
    if not categories:
        return "N/A"
    return ", ".join(categories)


def generate_markdown(digest: dict) -> str:
    """Generate Markdown from digest JSON."""
    date = digest.get("digest_date", datetime.now().strftime("%Y-%m-%d"))
    summary = digest.get("summary", "")
    papers = digest.get("papers", [])
    total_reviewed = digest.get("total_reviewed", 0)
    selected_count = len(papers)

    summary_section = f"**Today's Highlights:**\n\n{summary}\n" if summary else ""
    stats_section = (
        f"**Papers in this digest:** {selected_count} selected from {total_reviewed} top candidates"
    )

    papers_markdown = ""
    for i, paper in enumerate(papers, 1):
        papers_markdown += PAPER_TEMPLATE.format(
            number=i,
            title=paper.get("title", "Untitled"),
            arxiv_id=paper.get("arxiv_id", "unknown"),
            pdf_url=paper.get("pdf_url", "#"),
            authors=format_authors(paper.get("authors", [])),
            categories=format_categories(paper.get("categories", [])),
            score=paper.get("score", 0),
            summary=paper.get("summary", "No summary available."),
            key_insight=paper.get("key_insight", "No key insight provided."),
            relevance=paper.get("relevance", "Relevance not specified."),
        )

    return MARKDOWN_TEMPLATE.format(
        date=date,
        summary_section=summary_section,
        stats_section=stats_section,
        papers_markdown=papers_markdown,
    )


# ── HTML ──────────────────────────────────────────────────────────────────────


def _css_styles() -> str:
    """Return inline CSS styles for the HTML digest."""
    return """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                         Helvetica, Arial, sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
            color: #333;
            line-height: 1.6;
        }
        .container {
            max-width: 640px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            color: #ffffff;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            margin: 0 0 8px 0;
            font-size: 24px;
        }
        .header .date {
            opacity: 0.85;
            font-size: 14px;
        }
        .summary {
            padding: 20px 30px;
            background-color: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
            font-size: 14px;
        }
        .stats {
            padding: 12px 30px;
            font-size: 13px;
            color: #666;
            border-bottom: 1px solid #e9ecef;
        }
        .paper-card {
            padding: 24px 30px;
            border-bottom: 1px solid #e9ecef;
        }
        .paper-card:last-child {
            border-bottom: none;
        }
        .paper-number {
            font-size: 12px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 6px;
        }
        .paper-title {
            font-size: 18px;
            font-weight: 600;
            margin: 0 0 10px 0;
        }
        .paper-title a {
            color: #1a73e8;
            text-decoration: none;
        }
        .paper-title a:hover {
            text-decoration: underline;
        }
        .paper-meta {
            font-size: 13px;
            color: #555;
            margin-bottom: 12px;
        }
        .category-pill {
            display: inline-block;
            background-color: #e8eaf6;
            color: #3949ab;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            margin-right: 4px;
        }
        .score-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 13px;
            font-weight: 600;
            color: #ffffff;
        }
        .section-label {
            font-size: 12px;
            font-weight: 600;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin: 14px 0 4px 0;
        }
        .section-text {
            font-size: 14px;
            margin: 0 0 4px 0;
        }
        .footer {
            padding: 20px 30px;
            text-align: center;
            font-size: 12px;
            color: #999;
            background-color: #f8f9fa;
        }
    """


def _score_color(score: float) -> str:
    """Return a hex color for a score value (0-10 scale)."""
    if score >= 9:
        return "#1b5e20"
    if score >= 7:
        return "#2e7d32"
    if score >= 5:
        return "#f57f17"
    return "#c62828"


def _render_header(digest: dict) -> str:
    """Render the HTML header section."""
    date_str = html_lib.escape(digest.get("digest_date", datetime.now().strftime("%Y-%m-%d")))
    return f"""
    <div class="header">
        <h1>arXiv Research Digest</h1>
        <div class="date">{date_str}</div>
    </div>"""


def _render_paper_card(paper: dict, index: int) -> str:
    """Render a single paper card as HTML."""
    title = html_lib.escape(paper.get("title", "Untitled"))
    arxiv_id = html_lib.escape(paper.get("arxiv_id", "unknown"))
    pdf_url = html_lib.escape(paper.get("pdf_url", "#"))
    authors = html_lib.escape(format_authors(paper.get("authors", [])))
    score = paper.get("score", 0)
    summary = html_lib.escape(paper.get("summary", "No summary available."))
    key_insight = html_lib.escape(paper.get("key_insight", "No key insight provided."))
    relevance = html_lib.escape(paper.get("relevance", "Relevance not specified."))
    color = _score_color(score)

    categories_html = ""
    for cat in paper.get("categories", []):
        categories_html += f'<span class="category-pill">{html_lib.escape(cat)}</span>'

    return f"""
    <div class="paper-card">
        <div class="paper-number">Paper {index}</div>
        <div class="paper-title"><a href="{pdf_url}">{title}</a></div>
        <div class="paper-meta">
            {authors} &middot; {arxiv_id}<br>
            {categories_html}
            <span class="score-badge" style="background-color: {color};">{score}/10</span>
        </div>
        <div class="section-label">Summary</div>
        <p class="section-text">{summary}</p>
        <div class="section-label">Key Insight</div>
        <p class="section-text">{key_insight}</p>
        <div class="section-label">Relevance to Your Research</div>
        <p class="section-text">{relevance}</p>
    </div>"""


def generate_html(digest: dict) -> str:
    """Generate a complete HTML document from digest JSON.

    Args:
        digest: Digest dict with keys digest_date, summary, total_reviewed, papers.

    Returns:
        Complete HTML document string.
    """
    date_str = html_lib.escape(digest.get("digest_date", datetime.now().strftime("%Y-%m-%d")))
    summary = digest.get("summary", "")
    papers = digest.get("papers", [])
    total_reviewed = digest.get("total_reviewed", 0)

    header_html = _render_header(digest)

    summary_html = ""
    if summary:
        summary_html = f"""
    <div class="summary">{html_lib.escape(summary)}</div>"""

    stats_html = f"""
    <div class="stats">{len(papers)} papers selected from {total_reviewed} top candidates</div>"""

    papers_html = ""
    for i, paper in enumerate(papers, 1):
        papers_html += _render_paper_card(paper, i)

    footer_html = """
    <div class="footer">
        Generated by arXiv Research Digest
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>arXiv Research Digest — {date_str}</title>
    <style>{_css_styles()}
    </style>
</head>
<body>
    <div class="container">
        {header_html}
        {summary_html}
        {stats_html}
        {papers_html}
        {footer_html}
    </div>
</body>
</html>
"""


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Format digest JSON to Markdown and HTML")
    parser.add_argument(
        "--input",
        help="Input digest JSON file (default: auto-detect digest_*.json in current/)",
    )
    parser.add_argument("--output", help="Output Markdown file (default: replaces .json with .md)")

    args = parser.parse_args()

    # Resolve input path — auto-detect if not specified
    if args.input:
        input_path = CURRENT_RUN_DIR / args.input
    else:
        digest_files = list(CURRENT_RUN_DIR.glob("digest_*.json"))
        if not digest_files:
            print(f"Error: No digest_*.json files found in {CURRENT_RUN_DIR}")
            sys.exit(1)
        if len(digest_files) > 1:
            print(f"Warning: Multiple digest files found, using {digest_files[0].name}")
        input_path = digest_files[0]
        print(f"Auto-detected input: {input_path.name}")

    output_path = CURRENT_RUN_DIR / args.output if args.output else input_path.with_suffix(".md")

    # Load digest
    print(f"Loading digest from {input_path}...")
    try:
        with input_path.open() as f:
            digest = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found: {input_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}")
        sys.exit(1)

    # Generate Markdown
    print("Generating Markdown...")
    markdown = generate_markdown(digest)
    with output_path.open("w") as f:
        f.write(markdown)
    print(f"\n✓ Markdown digest saved to {output_path}")
    print(f"✓ {len(digest.get('papers', []))} papers formatted")
    print(f"✓ File size: {output_path.stat().st_size:,} bytes")

    # Generate HTML
    print("\nGenerating HTML...")
    html_output_path = output_path.with_suffix(".html")
    html_content = generate_html(digest)
    with html_output_path.open("w") as f:
        f.write(html_content)
    print(f"✓ HTML digest saved to {html_output_path}")
    print(f"✓ File size: {html_output_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
