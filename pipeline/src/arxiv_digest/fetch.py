#!/usr/bin/env python3
"""
Fetch recent papers from arXiv API for specified categories.

Usage:
    python3 fetch_papers.py \\
        --categories cs.LG,stat.ML,math.AG,math.AC \\
        --days-back 1 \\
        --output daily_papers.json
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from arxiv_digest.config import (
    DAILY_PAPERS_PATH,
    USER_PREFERENCES_PATH,
    ensure_directories,
    setup_daily_run,
)


def fetch_arxiv_papers(
    categories: list[str], start_date: str, end_date: str, max_results: int = 1000
) -> list[dict]:
    """
    Fetch papers from arXiv API for given categories and date range.

    Args:
        categories: List of arXiv category codes (e.g., ['cs.LG', 'math.AG'])
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        max_results: Maximum papers to fetch per query

    Returns:
        List of paper dictionaries
    """
    base_url = "http://export.arxiv.org/api/query?"
    papers = []

    for category in categories:
        print(f"Fetching papers from {category}...")

        # Build query
        # Format: cat:cs.LG AND submittedDate:[20260203 TO 20260204]
        query = f"cat:{category} AND submittedDate:[{start_date} TO {end_date}]"

        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        url = base_url + urllib.parse.urlencode(params)

        try:
            # ArXiv API rate limit: max 1 request per 3 seconds
            time.sleep(3)

            with urllib.request.urlopen(url) as response:
                data = response.read()

            # Parse XML response
            root = ET.fromstring(data)

            # Define namespace
            ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

            # Extract papers
            for entry in root.findall("atom:entry", ns):
                paper = {}

                # arXiv ID
                id_elem = entry.find("atom:id", ns)
                if id_elem is not None:
                    arxiv_url = id_elem.text
                    paper["arxiv_id"] = arxiv_url.split("/abs/")[-1]
                else:
                    continue

                # Title
                title_elem = entry.find("atom:title", ns)
                if title_elem is not None:
                    paper["title"] = " ".join(title_elem.text.split())  # Clean whitespace

                # Authors
                authors = []
                for author in entry.findall("atom:author", ns):
                    name_elem = author.find("atom:name", ns)
                    if name_elem is not None:
                        authors.append(name_elem.text)
                paper["authors"] = authors

                # Abstract
                summary_elem = entry.find("atom:summary", ns)
                if summary_elem is not None:
                    paper["abstract"] = " ".join(summary_elem.text.split())

                # Categories
                categories_list = []
                for cat in entry.findall("atom:category", ns):
                    cat_term = cat.get("term")
                    if cat_term:
                        categories_list.append(cat_term)
                paper["categories"] = categories_list

                # Published date
                published_elem = entry.find("atom:published", ns)
                if published_elem is not None:
                    paper["published"] = published_elem.text[:10]  # YYYY-MM-DD

                # PDF URL
                paper["pdf_url"] = f"https://arxiv.org/pdf/{paper['arxiv_id']}"

                papers.append(paper)

            print(f"  Found {len(root.findall('atom:entry', ns))} papers in {category}")

        except Exception as e:
            print(f"  Error fetching {category}: {e}")
            continue

    return papers


def deduplicate_papers(papers: list[dict]) -> list[dict]:
    """Remove duplicate papers (same arXiv ID)."""
    seen = set()
    unique_papers = []

    for paper in papers:
        arxiv_id = paper.get("arxiv_id")
        if arxiv_id and arxiv_id not in seen:
            seen.add(arxiv_id)
            unique_papers.append(paper)

    return unique_papers


def main():
    parser = argparse.ArgumentParser(description="Fetch papers from arXiv API")
    parser.add_argument(
        "--categories",
        help="Comma-separated arXiv categories (default: read from user_preferences.json)",
    )
    parser.add_argument(
        "--days-back", type=int, default=1, help="Number of days back to fetch (default: 1)"
    )
    parser.add_argument(
        "--max-results", type=int, default=1000, help="Max results per category (default: 1000)"
    )

    args = parser.parse_args()

    # Set up today's run directory and symlink
    ensure_directories()
    setup_daily_run()

    # Parse categories — from CLI arg or user_preferences.json
    if args.categories:
        categories = [cat.strip() for cat in args.categories.split(",") if cat.strip()]
    else:
        with USER_PREFERENCES_PATH.open() as f:
            prefs = json.load(f)
        categories = list(prefs.get("research_areas", {}).keys())
        if categories:
            print(f"(categories from {USER_PREFERENCES_PATH.name})")

    if not categories:
        print("Error: No valid categories provided")
        sys.exit(1)

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days_back)

    start_date_str = start_date.strftime("%Y%m%d")
    end_date_str = end_date.strftime("%Y%m%d")

    print(
        f"Fetching papers from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    )
    print(f"Categories: {', '.join(categories)}")
    print()

    # Fetch papers
    papers = fetch_arxiv_papers(categories, start_date_str, end_date_str, args.max_results)

    # Deduplicate
    papers = deduplicate_papers(papers)

    # Sort by published date (most recent first)
    papers.sort(key=lambda x: x.get("published", ""), reverse=True)

    # Save to file
    output_path = DAILY_PAPERS_PATH

    with output_path.open("w") as f:
        json.dump(papers, f, indent=2)

    print()
    print(f"✓ Fetched {len(papers)} unique papers")
    print(f"✓ Saved to {output_path}")

    # Print category breakdown
    print("\nPapers per category:")
    category_counts = {}
    for paper in papers:
        for cat in paper.get("categories", []):
            category_counts[cat] = category_counts.get(cat, 0) + 1

    for cat in sorted(category_counts.keys()):
        print(f"  {cat}: {category_counts[cat]}")


if __name__ == "__main__":
    main()
