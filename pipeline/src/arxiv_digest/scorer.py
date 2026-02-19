"""
Quick-scorer: deterministic + LLM hybrid scoring of pre-filtered papers.

Replaces the OpenClaw quick-scorer agent. Scores ~150 papers and selects
the top 25-30 (score >= 7) for downstream deep review.

Usage:
    python -m arxiv_digest.scorer
"""

import argparse
import json

from arxiv_digest.config import (
    FILTERED_PAPERS_PATH,
    SCORED_PAPERS_PATH,
    USER_PREFERENCES_PATH,
    load_llm_config,
)
from arxiv_digest.llm import LLMError, create_client
from arxiv_digest.llm.base import LLMClient
from arxiv_digest.utils import get_all_keywords

# ── Deterministic scoring functions ──────────────────────────────────


def calculate_category_score(paper: dict, user_areas: dict) -> float:
    """Category relevance score (0-5).

    Primary category match gets ``5 * weight``, secondary gets ``2.5 * weight``.
    """
    score = 0.0
    categories = paper.get("categories", [])
    for i, cat in enumerate(categories):
        if cat in user_areas:
            weight = user_areas[cat].get("weight", 1.0)
            if i == 0:
                score += 5 * weight
            else:
                score += 2.5 * weight
    return min(score, 5.0)


def calculate_keyword_score(paper: dict, all_keywords: set[str]) -> float:
    """Keyword presence score (0-3).

    Title match +2, abstract match +0.5 per keyword.
    """
    title_lower = paper.get("title", "").lower()
    abstract_lower = paper.get("abstract", "").lower()

    score = 0.0
    for kw in all_keywords:
        if kw in title_lower:
            score += 2
        elif kw in abstract_lower:
            score += 0.5
    return min(score, 3.0)


def calculate_novelty_bonus(paper: dict) -> int:
    """Novelty bonus (0 or 1). Awards 1 point when >= 2 indicator words match."""
    indicators = [
        "novel",
        "new approach",
        "first time",
        "theorem",
        "proof",
        "we prove",
        "breakthrough",
        "significant advance",
    ]
    text = (paper.get("title", "") + " " + paper.get("abstract", "")).lower()
    matches = sum(1 for ind in indicators if ind in text)
    return 1 if matches >= 2 else 0


def calculate_avoidance_penalty(paper: dict, avoid_criteria: list[str]) -> float:
    """Avoidance penalty (0-3). Penalises benchmark / engineering papers lacking theory."""
    penalty = 0.0
    title_lower = paper.get("title", "").lower()
    abstract_lower = paper.get("abstract", "").lower()

    for criterion in avoid_criteria:
        criterion_lower = criterion.lower()

        if "empirical" in criterion_lower:
            benchmark_terms = ["benchmark", "evaluation", "survey", "comparison"]
            theory_terms = ["theorem", "proof", "theory", "theoretical"]
            has_benchmark = any(t in title_lower for t in benchmark_terms)
            has_theory = any(t in abstract_lower for t in theory_terms)
            if has_benchmark and not has_theory:
                penalty += 2

        if "engineering" in criterion_lower:
            engineering_terms = ["implementation", "system", "framework", "tool"]
            theory_terms_eng = ["theorem"]
            has_engineering = any(t in title_lower for t in engineering_terms)
            has_theory_eng = any(t in abstract_lower for t in theory_terms_eng)
            if has_engineering and not has_theory_eng:
                penalty += 1

    return min(penalty, 3.0)


# ── LLM-based interest scoring ──────────────────────────────────────

_INTEREST_SCHEMA = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "arxiv_id": {"type": "string"},
                    "score": {"type": "integer"},
                },
                "required": ["arxiv_id", "score"],
            },
        },
    },
    "required": ["scores"],
}


def _build_interest_prompt(batch: list[dict], interests: list[str]) -> str:
    """Build the prompt for batched interest scoring."""
    interests_text = "\n".join(f"- {i}" for i in interests)

    papers_text = ""
    for p in batch:
        abstract_snippet = p.get("abstract", "")[:500]
        papers_text += (
            f"\n---\narxiv_id: {p['arxiv_id']}\nTitle: {p['title']}\nAbstract: {abstract_snippet}\n"
        )

    return (
        "You are an academic paper relevance scorer.\n\n"
        "User research interests:\n"
        f"{interests_text}\n\n"
        "Papers to score:\n"
        f"{papers_text}\n\n"
        "For each paper, score how well it aligns with the user's research interests.\n"
        "Score: 0 (no match), 1 (partial match), or 2 (strong match).\n"
        "Return JSON with a 'scores' array containing objects with 'arxiv_id' and 'score' fields."
    )


def calculate_interest_scores(
    papers: list[dict],
    interests: list[str],
    llm_client: LLMClient,
    *,
    model: str | None = None,
    batch_size: int = 15,
) -> dict[str, int]:
    """Score papers for interest alignment via batched LLM calls.

    Returns:
        Mapping of arxiv_id -> interest score (0, 1, or 2).
    """
    result: dict[str, int] = {}

    for i in range(0, len(papers), batch_size):
        batch = papers[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(papers) + batch_size - 1) // batch_size
        print(f"  Interest scoring batch {batch_num}/{total_batches} ({len(batch)} papers)...")

        prompt = _build_interest_prompt(batch, interests)
        try:
            resp = llm_client.complete_json(prompt, _INTEREST_SCHEMA, model=model)
            for item in resp.get("scores", []):
                aid = item.get("arxiv_id", "")
                score = max(0, min(2, item.get("score", 0)))
                result[aid] = score
        except LLMError as exc:
            print(f"  Warning: LLM call failed for batch {batch_num}: {exc}")
            # Default to 0 for papers in this batch
            for p in batch:
                result.setdefault(p["arxiv_id"], 0)

    return result


# ── Main pipeline ────────────────────────────────────────────────────


def score_papers(
    papers: list[dict],
    preferences: dict,
    llm_client: LLMClient,
    *,
    model: str | None = None,
    min_score: float = 7.0,
    max_selected: int = 30,
) -> dict:
    """Score all papers and return the top candidates.

    Returns:
        Dict in the ``scored_papers_summary`` output format.
    """
    user_areas = preferences.get("research_areas", {})
    all_keywords = get_all_keywords(preferences)
    avoid = preferences.get("avoid", [])
    interests = preferences.get("interests", [])

    print(f"Scoring {len(papers)} papers...")
    print(f"  Categories: {len(user_areas)}")
    print(f"  Keywords: {len(all_keywords)}")
    print(f"  Interests: {len(interests)}")
    print()

    # 1. Deterministic scores
    det_scores: dict[str, dict[str, float]] = {}
    for paper in papers:
        aid = paper["arxiv_id"]
        det_scores[aid] = {
            "category": calculate_category_score(paper, user_areas),
            "keyword": calculate_keyword_score(paper, all_keywords),
            "novelty": calculate_novelty_bonus(paper),
            "avoidance": calculate_avoidance_penalty(paper, avoid),
        }

    # 2. LLM interest scores
    print("Computing interest scores via LLM...")
    interest_scores = calculate_interest_scores(papers, interests, llm_client, model=model)

    # 3. Combine and rank
    scored: list[dict] = []
    for paper in papers:
        aid = paper["arxiv_id"]
        ds = det_scores[aid]
        interest = interest_scores.get(aid, 0)
        total = ds["category"] + ds["keyword"] + interest + ds["novelty"] - ds["avoidance"]

        scored.append(
            {
                "arxiv_id": aid,
                "title": paper["title"],
                "authors": paper.get("authors", []),
                "categories": paper.get("categories", []),
                "abstract": paper.get("abstract", ""),
                "pdf_url": paper.get("pdf_url", ""),
                "score": round(total, 2),
                "reason": _brief_reason(ds, interest),
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)

    # 4. Select top papers
    selected = [p for p in scored if p["score"] >= min_score][:max_selected]
    # If too few, relax threshold
    if len(selected) < 20:
        selected = scored[:max_selected]

    print(
        f"\nSelected {len(selected)}/{len(papers)} papers (min score in selection: "
        f"{selected[-1]['score'] if selected else 'N/A'})"
    )

    return {
        "scored_papers_summary": selected,
        "total_processed": len(papers),
        "selected_count": len(selected),
        "scoring_mode": "quick",
    }


def _brief_reason(det: dict[str, float], interest: int) -> str:
    """Generate a terse 1-sentence scoring reason."""
    parts: list[str] = []
    if det["category"] >= 4:
        parts.append("strong category match")
    elif det["category"] >= 2:
        parts.append("category match")
    if det["keyword"] >= 2:
        parts.append("keyword hits")
    if interest == 2:
        parts.append("high interest alignment")
    elif interest == 1:
        parts.append("partial interest match")
    if det["novelty"]:
        parts.append("novelty signals")
    if det["avoidance"] >= 2:
        parts.append("avoidance penalty applied")
    return "; ".join(parts).capitalize() + "." if parts else "Low overall relevance."


def main() -> None:
    parser = argparse.ArgumentParser(description="Quick-score filtered papers")
    parser.add_argument(
        "--min-score",
        type=float,
        default=7.0,
        help="Minimum score for selection (default: 7.0)",
    )
    parser.add_argument(
        "--max-selected",
        type=int,
        default=30,
        help="Maximum papers to select (default: 30)",
    )
    args = parser.parse_args()

    # Load inputs
    print(f"Loading papers from {FILTERED_PAPERS_PATH}...")
    with FILTERED_PAPERS_PATH.open() as f:
        papers = json.load(f)

    print(f"Loading preferences from {USER_PREFERENCES_PATH}...")
    with USER_PREFERENCES_PATH.open() as f:
        preferences = json.load(f)

    # Create LLM client
    llm_cfg = load_llm_config()
    client = create_client(llm_cfg["provider"], api_key=llm_cfg["api_key"])

    # Score
    result = score_papers(
        papers,
        preferences,
        client,
        model=llm_cfg["scorer_model"],
        min_score=args.min_score,
        max_selected=args.max_selected,
    )

    # Write output
    with SCORED_PAPERS_PATH.open("w") as f:
        json.dump(result, f, indent=2)

    print("\n--- Results ---")
    print(f"Total processed: {result['total_processed']}")
    print(f"Selected: {result['selected_count']}")
    print(f"Saved to {SCORED_PAPERS_PATH}")


if __name__ == "__main__":
    main()
