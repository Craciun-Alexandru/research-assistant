"""
Deep reviewer: full-text analysis of top-scored papers via LLM.

Reads full paper texts, generates scholarly analyses, then selects a diverse
final set of 2-3 papers for the daily digest.

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
from arxiv_digest.prompt_utils import build_persona

# ── Schemas ──────────────────────────────────────────────────────────

_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "analyses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "arxiv_id": {"type": "string"},
                    "summary": {"type": "string"},
                    "relevance": {"type": "string"},
                    "key_insight": {"type": "string"},
                    "score": {"type": "number"},
                },
                "required": ["arxiv_id", "summary", "relevance", "key_insight", "score"],
            },
        },
    },
    "required": ["analyses"],
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

# ── Per-batch analysis ───────────────────────────────────────────────

_MAX_TEXT_LEN = 40_000


def _build_batch_analysis_prompt(
    batch: list[tuple[dict, str]], interests: list[str], research_areas: dict
) -> str:
    """Build the deep-review prompt for a batch of papers."""
    interests_text = "\n".join(f"- {i}" for i in interests)

    papers_text = ""
    for paper, full_text in batch:
        if len(full_text) > _MAX_TEXT_LEN:
            full_text = full_text[:_MAX_TEXT_LEN] + "\n\n[Text truncated for length]"
        papers_text += (
            f"\n{'=' * 60}\n"
            f"arxiv_id: {paper['arxiv_id']}\n"
            f"Title: {paper['title']}\n"
            f"Authors: {', '.join(paper.get('authors', []))}\n"
            f"Categories: {', '.join(paper.get('categories', []))}\n\n"
            f"Full text:\n{full_text}\n"
        )

    return (
        f"{build_persona(interests, research_areas)}\n\n"
        "User's research interests:\n"
        f"{interests_text}\n\n"
        f"Analyze each of the following {len(batch)} papers:\n"
        f"{papers_text}\n\n"
        "For each paper provide:\n"
        "1. **arxiv_id**: the paper's arxiv_id (as given above)\n"
        "2. **summary**: 2-3 paragraphs covering the problem addressed, "
        "methodology/approach, and key results/contributions.\n"
        "3. **relevance**: 1 paragraph explaining how this connects to the "
        "user's research interests and why they should read it now.\n"
        "4. **key_insight**: 2-3 sentences on the most important takeaway "
        "and what makes this paper stand out.\n"
        "5. **score**: A float from 0-10 rating overall quality and relevance.\n"
        "Return an 'analyses' array with one object per paper.\n"
    )


def analyze_batch(
    batch: list[tuple[dict, str]],
    interests: list[str],
    llm_client: LLMClient,
    *,
    model: str | None = None,
    research_areas: dict | None = None,
) -> list[dict]:
    """Run deep analysis on a batch of papers in a single LLM call.

    Args:
        batch: List of (paper dict, full_text) pairs.
        interests: User research interests.
        llm_client: LLM backend.
        model: Model name override.
        research_areas: User's research area weights from preferences.

    Returns:
        List of analysis dicts, each with arxiv_id, summary, relevance,
        key_insight, score.
    """
    prompt = _build_batch_analysis_prompt(batch, interests, research_areas or {})
    resp = llm_client.complete_json(prompt, _ANALYSIS_SCHEMA, model=model)
    return resp.get("analyses", [])


# ── Selection ────────────────────────────────────────────────────────


def _build_selection_prompt(
    analyses: list[dict],
    interests: list[str],
    target_count: int,
    research_areas: dict | None = None,
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
        f"{build_persona(interests, research_areas or {})}\n\n"
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
    target_count: int = 3,
    research_areas: dict | None = None,
) -> tuple[list[str], str]:
    """Ask the LLM to pick the final diverse set of papers.

    Returns:
        Tuple of (selected arxiv_ids, digest summary string).
    """
    prompt = _build_selection_prompt(analyses, interests, target_count, research_areas)
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
    target_selected: int = 3,
    batch_size: int = 5,
) -> dict:
    """Deep-review scored papers and produce the digest JSON.

    Args:
        scored: Parsed ``scored_papers_summary.json``.
        preferences: Parsed ``user_preferences.json``.
        llm_client: LLM backend.
        model: Model name override.
        delay: Seconds to wait between batch LLM calls.
        target_selected: Number of papers to select for the final digest.
        batch_size: Papers per LLM call (default: 5).

    Returns:
        Dict in the ``digest_YYYY-MM-DD.json`` format.
    """
    papers = scored.get("scored_papers_summary", [])
    interests = preferences.get("interests", [])
    research_areas = preferences.get("research_areas", {})

    # Load full texts, skip papers with no downloaded text
    available: list[tuple[dict, str]] = []
    for paper in papers:
        aid = paper["arxiv_id"]
        txt_path = PAPERS_DIR / f"{aid}.txt"
        if not txt_path.exists():
            print(f"  Skipping {aid} (no full text)")
            continue
        available.append((paper, txt_path.read_text(encoding="utf-8", errors="replace")))

    total_batches = (len(available) + batch_size - 1) // batch_size
    print(f"Deep-reviewing {len(available)} papers in {total_batches} batches of {batch_size}...")
    print(f"  Delay between batches: {delay}s")
    print()

    # 1. Analyze in batches
    analyses: list[dict] = []
    for batch_idx in range(0, len(available), batch_size):
        batch = available[batch_idx : batch_idx + batch_size]
        batch_num = batch_idx // batch_size + 1
        ids = ", ".join(p["arxiv_id"] for p, _ in batch)
        print(f"  Batch {batch_num}/{total_batches}: {ids}")

        try:
            results = analyze_batch(
                batch, interests, llm_client, model=model, research_areas=research_areas
            )
        except LLMError as exc:
            print(f"    Warning: batch analysis failed: {exc}")
            continue

        # Index results by arxiv_id to join back paper metadata
        result_by_id = {r["arxiv_id"]: r for r in results}
        for paper, _ in batch:
            aid = paper["arxiv_id"]
            analysis = result_by_id.get(aid)
            if analysis is None:
                print(f"    Warning: no analysis returned for {aid}")
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

        if batch_idx + batch_size < len(available) and delay > 0:
            print(f"    Waiting {delay}s before next batch...")
            time.sleep(delay)

    if not analyses:
        print("Error: No papers could be analyzed.")
        sys.exit(1)

    # 2. Select final papers
    print(f"\nSelecting top {target_selected} papers from {len(analyses)} analyses...")
    selected_ids, digest_summary = select_papers(
        analyses,
        interests,
        llm_client,
        model=model,
        target_count=target_selected,
        research_areas=research_areas,
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
        default=3,
        help="Number of papers to select for digest (default: 3)",
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
