#!/usr/bin/env python3
"""
Format digest JSON into Markdown for delivery.

Usage:
    python3 format_digest_markdown.py \\
        --input digest_2026-02-04.json \\
        --output digest_2026-02-04.md
"""

import argparse
import json
import sys
from datetime import datetime

from arxiv_digest.config import CURRENT_RUN_DIR

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
    else:
        return ", ".join(authors[0 : max_authors - 1]) + f", et al. ({len(authors)} total)"


def format_categories(categories: list) -> str:
    """Format category list."""
    if not categories:
        return "N/A"
    return ", ".join(categories)


def generate_markdown(digest: dict) -> str:
    """Generate Markdown from digest JSON."""

    # Extract metadata
    date = digest.get("digest_date", datetime.now().strftime("%Y-%m-%d"))
    summary = digest.get("summary", "")
    papers = digest.get("papers", [])
    total_reviewed = digest.get("total_reviewed", 0)
    selected_count = len(papers)

    # Generate summary section
    summary_section = f"**Today's Highlights:**\n\n{summary}\n" if summary else ""

    # Generate stats section
    stats_section = (
        f"**Papers in this digest:** {selected_count} selected from {total_reviewed} top candidates"
    )

    # Generate paper markdown
    papers_markdown = ""
    for i, paper in enumerate(papers, 1):
        paper_md = PAPER_TEMPLATE.format(
            number=i,
            title=paper.get("title", "Untitled"),
            arxiv_id=paper.get("arxiv_id", "unknown"),
            pdf_url=paper.get("pdf_url", "#"),
            authors=format_authors(paper.get("authors", [])),
            categories=format_categories(paper.get("categories", [])),
            score=paper.get("score", 0),
            summary=paper.get("summary", "No summary available."),
            relevance=paper.get("relevance", "Relevance not specified."),
            # key_insight=paper.get('key_insight', 'No key insight provided.')
        )
        papers_markdown += paper_md

    # Fill template
    markdown = MARKDOWN_TEMPLATE.format(
        date=date,
        summary_section=summary_section,
        stats_section=stats_section,
        papers_markdown=papers_markdown,
    )

    return markdown


def main():
    parser = argparse.ArgumentParser(description="Format digest JSON to Markdown")
    parser.add_argument(
        "--input", required=True, help="Input digest JSON file (e.g., digest_2026-02-04.json)"
    )
    parser.add_argument("--output", help="Output Markdown file (default: replaces .json with .md)")

    args = parser.parse_args()

    # Resolve paths — read/write inside today's daily run directory
    input_path = CURRENT_RUN_DIR / args.input

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

    # Save output
    with output_path.open("w") as f:
        f.write(markdown)

    print("\n✓ Markdown digest created")
    print(f"✓ {len(digest.get('papers', []))} papers formatted")
    print(f"✓ Saved to {output_path}")

    # Show file size
    size = output_path.stat().st_size
    print(f"✓ File size: {size:,} bytes")

    # Check if it's too large for Discord (8000 char limit per message)
    if size > 7000:
        print("\n⚠️  Warning: File may be too large for a single Discord message")
        print("   Consider splitting or using file attachment")


if __name__ == "__main__":
    main()
