"""
Deep reviewer: full-text analysis of top-scored papers via LLM.

Replaces the OpenClaw deep-reviewer agent. Reads full paper texts, generates
scholarly analyses, then selects a diverse final set of 5-6 papers for the
daily digest.

Usage:
    python -m arxiv_digest.reviewer
"""

import argparse
import json
import sys
import time
from datetime import date

from arxiv_digest.config import (
    CURRENT_RUN_DIR,
    PAPERS_DIR,
    SCORED_PAPERS_PATH,
    USER_PREFERENCES_PATH,
    load_llm_config,
)
from arxiv_digest.llm import LLMError, create_client
from arxiv_digest.llm.base import LLMClient

# ── Schemas ──────────────────────────────────────────────────────────

_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "relevance": {"type": "string"},
        "key_insight": {"type": "string"},
        "score": {"type": "number"},
    },
    "required": ["summary", "relevance", "key_insight", "score"],
}

_SELECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "selected_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "digest_summary": {"type": "string"},
    },
    "required": ["selected_ids", "digest_summary"],
}

# ── Per-paper analysis ───────────────────────────────────────────────


def _build_analysis_prompt(paper: dict, full_text: str, interests: list[str]) -> str:
    """Build the deep-review prompt for a single paper."""
    interests_text = "\n".join(f"- {i}" for i in interests)
    # Truncate very long papers to stay within context limits
    max_text_len = 80_000
    if len(full_text) > max_text_len:
        full_text = full_text[:max_text_len] + "\n\n[Text truncated for length]"

    return (
        "You are a scholarly research paper reviewer.\n\n"
        f"Paper: {paper['title']}\n"
        f"Authors: {', '.join(paper.get('authors', []))}\n"
        f"Categories: {', '.join(paper.get('categories', []))}\n\n"
        f"Full text:\n{full_text}\n\n"
        "User's research interests:\n"
        f"{interests_text}\n\n"
        "Provide a deep analysis of this paper:\n"
        "1. **summary**: 2-3 paragraphs covering the problem addressed, "
        "methodology/approach, and key results/contributions.\n"
        "2. **relevance**: 1 paragraph explaining how this connects to the "
        "user's research interests and why they should read it now.\n"
        "3. **key_insight**: 2-3 sentences on the most important takeaway "
        "and what makes this paper stand out.\n"
        "4. **score**: A float from 0-10 rating overall quality and relevance.\n"
    )


def analyze_paper(
    paper: dict,
    full_text: str,
    interests: list[str],
    llm_client: LLMClient,
    *,
    model: str | None = None,
) -> dict:
    """Run deep analysis on a single paper.

    Returns:
        Dict with summary, relevance, key_insight, score.
    """
    prompt = _build_analysis_prompt(paper, full_text, interests)
    return llm_client.complete_json(prompt, _ANALYSIS_SCHEMA, model=model)


# ── Selection ────────────────────────────────────────────────────────


def _build_selection_prompt(
    analyses: list[dict],
    interests: list[str],
    target_count: int,
) -> str:
    """Build the final selection prompt."""
    interests_text = "\n".join(f"- {i}" for i in interests)

    papers_text = ""
    for a in analyses:
        papers_text += (
            f"\n---\narxiv_id: {a['arxiv_id']}\n"
            f"Title: {a['title']}\n"
            f"Score: {a['analysis']['score']}\n"
            f"Key insight: {a['analysis']['key_insight']}\n"
        )

    return (
        "You are curating a daily research digest.\n\n"
        "User's research interests:\n"
        f"{interests_text}\n\n"
        f"The following papers have been deeply analyzed:\n{papers_text}\n\n"
        f"Select the best {target_count} papers for today's digest. "
        "Choose papers that:\n"
        "- Represent significant contributions\n"
        "- Span different aspects of the user's research interests\n"
        "- Offer actionable insights\n\n"
        "Return:\n"
        "- 'selected_ids': list of arxiv_id strings for the chosen papers\n"
        "- 'digest_summary': 2-3 sentence overview of today's digest themes\n"
    )


def select_papers(
    analyses: list[dict],
    interests: list[str],
    llm_client: LLMClient,
    *,
    model: str | None = None,
    target_count: int = 6,
) -> tuple[list[str], str]:
    """Ask the LLM to pick the final diverse set of papers.

    Returns:
        Tuple of (selected arxiv_ids, digest summary string).
    """
    prompt = _build_selection_prompt(analyses, interests, target_count)
    resp = llm_client.complete_json(prompt, _SELECTION_SCHEMA, model=model)
    return resp.get("selected_ids", []), resp.get("digest_summary", "")


# ── Main pipeline ────────────────────────────────────────────────────


def review_papers(
    scored: dict,
    preferences: dict,
    llm_client: LLMClient,
    *,
    model: str | None = None,
    delay: int = 60,
    target_selected: int = 6,
) -> dict:
    """Deep-review scored papers and produce the digest JSON.

    Args:
        scored: Parsed ``scored_papers_summary.json``.
        preferences: Parsed ``user_preferences.json``.
        llm_client: LLM backend.
        model: Model name override.
        delay: Seconds to wait between per-paper LLM calls.
        target_selected: Number of papers to select for the final digest.

    Returns:
        Dict in the ``digest_YYYY-MM-DD.json`` format.
    """
    papers = scored.get("scored_papers_summary", [])
    interests = preferences.get("interests", [])

    print(f"Deep-reviewing {len(papers)} papers...")
    print(f"  Delay between papers: {delay}s")
    print()

    # 1. Analyze each paper sequentially
    analyses: list[dict] = []
    for idx, paper in enumerate(papers):
        aid = paper["arxiv_id"]
        txt_path = PAPERS_DIR / f"{aid}.txt"

        if not txt_path.exists():
            print(f"  [{idx + 1}/{len(papers)}] Skipping {aid} (no full text)")
            continue

        print(f"  [{idx + 1}/{len(papers)}] Analyzing {aid}: {paper['title'][:60]}...")
        full_text = txt_path.read_text(encoding="utf-8", errors="replace")

        try:
            analysis = analyze_paper(paper, full_text, interests, llm_client, model=model)
        except LLMError as exc:
            print(f"    Warning: analysis failed: {exc}")
            continue

        analyses.append(
            {
                "arxiv_id": aid,
                "title": paper["title"],
                "authors": paper.get("authors", []),
                "categories": paper.get("categories", []),
                "abstract": paper.get("abstract", ""),
                "pdf_url": paper.get("pdf_url", ""),
                "analysis": analysis,
            }
        )

        # Wait between papers (skip delay after the last one)
        if idx < len(papers) - 1 and delay > 0:
            print(f"    Waiting {delay}s before next paper...")
            time.sleep(delay)

    if not analyses:
        print("Error: No papers could be analyzed.")
        sys.exit(1)

    # 2. Select final papers
    print(f"\nSelecting top {target_selected} papers from {len(analyses)} analyses...")
    selected_ids, digest_summary = select_papers(
        analyses, interests, llm_client, model=model, target_count=target_selected
    )

    # Build final paper list
    analyses_by_id = {a["arxiv_id"]: a for a in analyses}
    selected_papers: list[dict] = []
    for aid in selected_ids:
        if aid in analyses_by_id:
            a = analyses_by_id[aid]
            selected_papers.append(
                {
                    "arxiv_id": a["arxiv_id"],
                    "title": a["title"],
                    "authors": a["authors"],
                    "categories": a["categories"],
                    "abstract": a["abstract"],
                    "pdf_url": a["pdf_url"],
                    "summary": a["analysis"]["summary"],
                    "relevance": a["analysis"]["relevance"],
                    "key_insight": a["analysis"]["key_insight"],
                    "score": a["analysis"]["score"],
                }
            )

    return {
        "digest_date": date.today().isoformat(),
        "summary": digest_summary,
        "papers": selected_papers,
        "total_reviewed": len(analyses),
        "selected_count": len(selected_papers),
        "scoring_mode": "deep",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Deep-review scored papers")
    parser.add_argument(
        "--delay",
        type=int,
        default=60,
        help="Seconds between per-paper LLM calls (default: 60)",
    )
    parser.add_argument(
        "--target-selected",
        type=int,
        default=6,
        help="Number of papers to select for digest (default: 6)",
    )
    args = parser.parse_args()

    # Load inputs
    print(f"Loading scored papers from {SCORED_PAPERS_PATH}...")
    with SCORED_PAPERS_PATH.open() as f:
        scored = json.load(f)

    print(f"Loading preferences from {USER_PREFERENCES_PATH}...")
    with USER_PREFERENCES_PATH.open() as f:
        preferences = json.load(f)

    # Create LLM client
    llm_cfg = load_llm_config()
    client = create_client(llm_cfg["provider"], api_key=llm_cfg["api_key"])

    # Review
    digest = review_papers(
        scored,
        preferences,
        client,
        model=llm_cfg["reviewer_model"],
        delay=args.delay,
        target_selected=args.target_selected,
    )

    # Write output
    output_path = CURRENT_RUN_DIR / f"digest_{date.today().isoformat()}.json"
    with output_path.open("w") as f:
        json.dump(digest, f, indent=2)

    print("\n--- Results ---")
    print(f"Total reviewed: {digest['total_reviewed']}")
    print(f"Selected: {digest['selected_count']}")
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
