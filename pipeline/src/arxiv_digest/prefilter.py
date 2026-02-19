#!/usr/bin/env python3
"""
Pre-filter papers using keyword/category matching before LLM scoring.

Usage:
    python3 prefilter_papers.py \\
        --input daily_papers.json \\
        --output filtered_papers.json \\
        --preferences user_preferences.json \\
        --target-count 50
"""

import argparse

from arxiv_digest.config import DAILY_PAPERS_PATH, FILTERED_PAPERS_PATH, USER_PREFERENCES_PATH
from arxiv_digest.utils import get_all_keywords, load_json, save_json


def prefilter_score(paper: dict, user_categories: set[str], user_keywords: set[str]) -> float:
    """
    Calculate a simple pre-filter score for a paper.

    Returns:
        Score from 0-10 based on category match and keyword presence
    """
    score = 0.0

    # Category match (up to 6 points)
    paper_categories = set(paper.get("categories", []))
    category_overlap = paper_categories & user_categories

    if category_overlap:
        score += min(len(category_overlap) * 3, 6)  # 3 points per matching category, max 6
    else:
        # No category match - likely to be filtered out
        return score

    # Keyword match (up to 4 points)
    title_lower = paper.get("title", "").lower()
    abstract_lower = paper.get("abstract", "").lower()

    keyword_matches = 0
    for keyword in user_keywords:
        if keyword in title_lower:
            keyword_matches += 2  # Title match worth more
        elif keyword in abstract_lower:
            keyword_matches += 1  # Abstract match

    score += min(keyword_matches, 4)  # Cap at 4 points

    return score


def apply_avoidance_filters(paper: dict, avoid_criteria: list[str]) -> bool:
    """
    Check if paper should be avoided based on criteria.

    Returns:
        True if paper should be KEPT, False if should be FILTERED OUT
    """
    title_lower = paper.get("title", "").lower()
    abstract_lower = paper.get("abstract", "").lower()

    for criterion in avoid_criteria:
        criterion_lower = criterion.lower()

        # Check for benchmark papers
        if "benchmark" in criterion_lower or "empirical" in criterion_lower:
            benchmark_terms = ["benchmark", "evaluation", "comparison", "survey"]
            has_benchmark = any(term in title_lower for term in benchmark_terms)

            # Check if it has theoretical content
            theory_terms = ["theorem", "proof", "theory", "theoretical", "analysis"]
            has_theory = any(term in abstract_lower for term in theory_terms)

            if has_benchmark and not has_theory:
                return False  # Filter out pure benchmark papers

        # Check for engineering-only papers
        if "engineering" in criterion_lower or "implementation" in criterion_lower:
            engineering_terms = ["implementation", "system", "framework", "tool", "library"]
            has_engineering = any(term in title_lower for term in engineering_terms)

            theory_terms = ["theorem", "proof", "theory", "theoretical"]
            has_theory = any(term in abstract_lower for term in theory_terms)

            if has_engineering and not has_theory:
                return False  # Filter out implementation-only papers

    return True  # Keep the paper


def prefilter_papers(papers: list[dict], preferences: dict, target_count: int = 50) -> list[dict]:
    """
    Pre-filter papers to reduce count before LLM scoring.

    Args:
        papers: List of all fetched papers
        preferences: User preferences dict
        target_count: Target number of papers to keep

    Returns:
        Filtered list of papers
    """
    user_categories = set(preferences["research_areas"].keys())
    user_keywords = get_all_keywords(preferences)
    avoid_criteria = preferences.get("avoid", [])

    print(f"User categories: {', '.join(user_categories)}")
    print(f"User keywords: {len(user_keywords)} total")
    print(f"Avoidance criteria: {len(avoid_criteria)}")
    print()

    # Score all papers
    scored_papers = []
    for paper in papers:
        # Apply avoidance filters first
        if not apply_avoidance_filters(paper, avoid_criteria):
            continue  # Skip this paper

        # Calculate pre-filter score
        score = prefilter_score(paper, user_categories, user_keywords)

        if score > 0:  # Only keep papers with some relevance
            paper["prefilter_score"] = score
            scored_papers.append(paper)

    # Sort by score (highest first)
    scored_papers.sort(key=lambda x: x["prefilter_score"], reverse=True)

    # Take top N papers
    filtered = scored_papers[:target_count]

    # Remove prefilter_score from output (not needed by LLM scorer)
    for paper in filtered:
        del paper["prefilter_score"]

    return filtered


def main():
    parser = argparse.ArgumentParser(description="Pre-filter papers before LLM scoring")
    parser.add_argument(
        "--target-count", type=int, default=50, help="Target number of papers to keep (default: 50)"
    )

    args = parser.parse_args()

    # Resolve paths
    input_path = DAILY_PAPERS_PATH
    output_path = FILTERED_PAPERS_PATH
    prefs_path = USER_PREFERENCES_PATH

    # Load data
    print(f"Loading papers from {input_path}...")
    papers = load_json(input_path)

    print(f"Loading preferences from {prefs_path}...")
    preferences = load_json(prefs_path)

    print(f"\nPre-filtering {len(papers)} papers to ~{args.target_count}...")
    print()

    # Filter papers
    filtered = prefilter_papers(papers, preferences, args.target_count)

    # Save output
    save_json(filtered, output_path)

    print()
    print(f"✓ Input papers: {len(papers)}")
    print(f"✓ Filtered papers: {len(filtered)}")
    print(f"✓ Reduction: {100 * (1 - len(filtered) / len(papers)):.1f}%")
    print(f"✓ Saved to {output_path}")

    # Category breakdown
    print("\nFiltered papers by category:")
    category_counts = {}
    for paper in filtered:
        for cat in paper.get("categories", []):
            category_counts[cat] = category_counts.get(cat, 0) + 1

    for cat in sorted(category_counts.keys()):
        print(f"  {cat}: {category_counts[cat]}")


if __name__ == "__main__":
    main()
