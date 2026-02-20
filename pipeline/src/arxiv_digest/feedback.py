"""
Feedback wizard for iterative preference tuning.

Review past digest papers, rate them, and let an LLM propose targeted
preference adjustments as a delta (not a full replacement).

Usage:
    python -m arxiv_digest.feedback
    python -m arxiv_digest.feedback --dates 2026-02-19,2026-02-18
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from arxiv_digest.config import RESOURCES_DIR, USER_PREFERENCES_PATH, load_llm_config
from arxiv_digest.llm import LLMError, create_client

# ── Delta schema ──────────────────────────────────────────────────────────────

_DELTA_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "weight_adjustments": {
            "type": "object",
            "description": "Map of arxiv category code to new weight (0.0–1.0).",
        },
        "add_keywords": {
            "type": "object",
            "description": "Map of arxiv category code to list of keywords to add.",
        },
        "remove_keywords": {
            "type": "object",
            "description": "Map of arxiv category code to list of keywords to remove.",
        },
        "add_interests": {
            "type": "array",
            "items": {"type": "string"},
            "description": "New interest strings to add.",
        },
        "remove_interests": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Existing interest strings to remove.",
        },
        "add_avoid": {
            "type": "array",
            "items": {"type": "string"},
            "description": "New avoidance strings to add.",
        },
        "remove_avoid": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Existing avoidance strings to remove.",
        },
        "reasoning": {
            "type": "string",
            "description": "Explanation of why these changes are proposed.",
        },
    },
    "required": ["reasoning"],
}

# ── Date discovery ────────────────────────────────────────────────────────────

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def find_digest_dates(resources_dir: Path) -> list[str]:
    """Scan resources_dir for YYYY-MM-DD subdirs containing a digest_*.json.

    Args:
        resources_dir: Root directory to scan.

    Returns:
        Date strings sorted newest first.
    """
    dates = []
    if not resources_dir.is_dir():
        return dates
    for entry in resources_dir.iterdir():
        if not entry.is_dir():
            continue
        if not _DATE_RE.match(entry.name):
            continue
        # Must contain at least one digest_*.json
        if any(entry.glob("digest_*.json")):
            dates.append(entry.name)
    dates.sort(reverse=True)
    return dates


get_available_digest_dates = find_digest_dates


def load_digest_for_date(date_str: str, resources_dir: Path) -> dict:
    """Load and return the digest JSON for the given date string.

    Args:
        date_str: Date string in YYYY-MM-DD format.
        resources_dir: Root directory containing dated subdirs.

    Returns:
        Parsed digest JSON as a dict.

    Raises:
        FileNotFoundError: If no digest file exists for the date.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    date_dir = resources_dir / date_str
    candidates = list(date_dir.glob("digest_*.json"))
    if not candidates:
        raise FileNotFoundError(f"No digest_*.json found in {date_dir}")
    digest_path = sorted(candidates)[-1]
    with digest_path.open() as f:
        return json.load(f)


# ── Feedback entry ────────────────────────────────────────────────────────────


def build_feedback_entry(paper: dict, feedback_type: str, feedback_text: str) -> dict:
    """Build a feedback dict from a paper and user feedback.

    Args:
        paper: Paper dict from the digest JSON.
        feedback_type: One of "good", "bad", or "verbal".
        feedback_text: Free-text note from the user (may be empty string).

    Returns:
        Dict with keys: arxiv_id, title, categories, score, feedback_type, feedback_text.
    """
    return {
        "arxiv_id": paper.get("arxiv_id", ""),
        "title": paper.get("title", ""),
        "categories": paper.get("categories", []),
        "score": paper.get("score", 0.0),
        "feedback_type": feedback_type,
        "feedback_text": feedback_text,
    }


# ── Delta application ─────────────────────────────────────────────────────────


def apply_delta(prefs: dict, delta: dict) -> dict:
    """Apply an LLM-proposed delta to preferences dict.

    Does not mutate the input. Returns an updated copy.

    Args:
        prefs: Current user preferences dict.
        delta: Delta dict from the LLM (see _DELTA_SCHEMA).

    Returns:
        Updated preferences dict.
    """
    import copy

    updated = copy.deepcopy(prefs)
    research_areas = updated.setdefault("research_areas", {})

    # Weight adjustments
    for cat, new_weight in delta.get("weight_adjustments", {}).items():
        if cat in research_areas:
            research_areas[cat]["weight"] = new_weight

    # Add keywords
    for cat, kws in delta.get("add_keywords", {}).items():
        area = research_areas.setdefault(cat, {"weight": 0.8, "keywords": []})
        existing = set(area.setdefault("keywords", []))
        for kw in kws:
            if kw not in existing:
                area["keywords"].append(kw)
                existing.add(kw)

    # Remove keywords
    for cat, kws in delta.get("remove_keywords", {}).items():
        if cat in research_areas:
            to_remove = set(kws)
            research_areas[cat]["keywords"] = [
                k for k in research_areas[cat].get("keywords", []) if k not in to_remove
            ]

    # Interests
    interests = updated.setdefault("interests", [])
    for item in delta.get("add_interests", []):
        if item not in interests:
            interests.append(item)
    to_remove_interests = set(delta.get("remove_interests", []))
    updated["interests"] = [i for i in interests if i not in to_remove_interests]

    # Avoid
    avoid = updated.setdefault("avoid", [])
    for item in delta.get("add_avoid", []):
        if item not in avoid:
            avoid.append(item)
    to_remove_avoid = set(delta.get("remove_avoid", []))
    updated["avoid"] = [a for a in avoid if a not in to_remove_avoid]

    return updated


apply_preference_delta = apply_delta


# ── LLM prompt ───────────────────────────────────────────────────────────────


def _build_llm_prompt(prefs: dict, feedback_list: list[dict]) -> str:
    """Build the prompt for the LLM preference update call.

    Args:
        prefs: Current user preferences dict.
        feedback_list: List of feedback entry dicts.

    Returns:
        Prompt string.
    """
    prefs_json = json.dumps(
        {
            "research_areas": prefs.get("research_areas", {}),
            "interests": prefs.get("interests", []),
            "avoid": prefs.get("avoid", []),
        },
        indent=2,
    )
    feedback_json = json.dumps(feedback_list, indent=2)

    return f"""\
You are a research preference optimizer for a personalized arXiv digest system.

## Current Preferences

```json
{prefs_json}
```

## User Feedback on Recent Papers

The user has reviewed papers from their digest and provided feedback:
- "good": paper was relevant and interesting
- "bad": paper was not relevant or not interesting
- "verbal": user's own words describing what they liked or disliked

```json
{feedback_json}
```

## Task

Analyze the feedback patterns and propose targeted adjustments to the user's preferences.
Focus on changes that would have meaningfully improved the selection of papers shown.

Guidelines:
- Only propose changes supported by clear patterns in the feedback
- Prefer small, targeted adjustments over sweeping changes
- Weight adjustments should stay in the range [0.5, 1.0]
- When adding keywords, use specific terms from paper titles/categories that were rated good
- When removing keywords, only remove ones clearly associated with bad papers
- Interests and avoid lists should remain concise (under 15 items each)
- The "reasoning" field must explain the rationale for each proposed change

Respond with a JSON object matching the delta schema. Omit any field where no change is needed.
"""


def build_feedback_prompt(current_prefs: dict, feedback_entries: list[dict]) -> tuple[str, dict]:
    """Build the LLM prompt and return it with the delta schema.

    Args:
        current_prefs: Current user preferences dict.
        feedback_entries: List of feedback entry dicts.

    Returns:
        Tuple of (prompt_string, delta_schema_dict).
    """
    return (_build_llm_prompt(current_prefs, feedback_entries), _DELTA_SCHEMA)


# ── Reviewed-history helpers ──────────────────────────────────────────────────


def get_reviewed_info(feedback_history: list[dict]) -> tuple[set[str], set[str]]:
    """Extract reviewed dates and paper IDs from feedback history.

    Args:
        feedback_history: List of history entries from user_preferences.json.

    Returns:
        Tuple of (reviewed_dates, reviewed_paper_ids) as sets of strings.
    """
    reviewed_dates: set[str] = set()
    reviewed_paper_ids: set[str] = set()
    for entry in feedback_history:
        for d in entry.get("dates_reviewed", []):
            reviewed_dates.add(d)
        for pid in entry.get("reviewed_paper_ids", []):
            reviewed_paper_ids.add(pid)
    return reviewed_dates, reviewed_paper_ids


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """Run the interactive feedback wizard."""
    parser = argparse.ArgumentParser(
        description="Review past digest papers and tune preferences via feedback."
    )
    parser.add_argument(
        "--dates",
        metavar="YYYY-MM-DD,...",
        help="Comma-separated digest dates to review (default: interactive selection).",
    )
    args = parser.parse_args()

    print("=" * 52)
    print("  arXiv Digest — Feedback & Preference Tuning")
    print("=" * 52)
    print()

    # ── Load prefs early to get reviewed history ──
    try:
        with USER_PREFERENCES_PATH.open() as f:
            existing_prefs = json.load(f)
    except FileNotFoundError:
        print(f"Error: {USER_PREFERENCES_PATH} not found. Run onboarding first.")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"Error: Could not parse {USER_PREFERENCES_PATH}: {exc}")
        sys.exit(1)

    reviewed_dates, reviewed_paper_ids = get_reviewed_info(
        existing_prefs.get("feedback_history", [])
    )

    # ── Resolve dates to review ──
    if args.dates:
        requested = [d.strip() for d in args.dates.split(",") if d.strip()]
        selected_dates = []
        for d in requested:
            if d in reviewed_dates:
                print(f"Note: {d} has already been reviewed — skipping.")
            else:
                selected_dates.append(d)
        if not selected_dates:
            print("All specified dates have already been reviewed.")
            sys.exit(0)
    else:
        all_dates = find_digest_dates(RESOURCES_DIR)
        if not all_dates:
            print("Error: No digest directories found in resources/.")
            print("Run the pipeline first to generate a digest.")
            sys.exit(1)

        unreviewed = [d for d in all_dates if d not in reviewed_dates]
        if not unreviewed:
            print("All available digests have already been reviewed.")
            sys.exit(0)

        recent = unreviewed[:7]
        skipped_count = len(all_dates) - len(unreviewed)
        if skipped_count:
            print(f"(Hiding {skipped_count} already-reviewed date(s).)\n")
        print("Available digest dates:")
        for i, d in enumerate(recent, 1):
            print(f"  {i}. {d}")
        print()

        try:
            raw = input(
                "Enter numbers to review (e.g. 1,2) or press Enter for most recent: "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(0)

        if not raw:
            selected_dates = [recent[0]]
        else:
            selected_dates = []
            for token in raw.split(","):
                token = token.strip()
                if token.isdigit():
                    idx = int(token) - 1
                    if 0 <= idx < len(recent):
                        selected_dates.append(recent[idx])
                    else:
                        print(f"Warning: index {token} out of range, skipping.")
                else:
                    print(f"Warning: '{token}' is not a valid number, skipping.")

        if not selected_dates:
            print("No valid dates selected. Exiting.")
            sys.exit(1)

    # ── Collect feedback ──
    feedback_list: list[dict] = []

    for date_str in selected_dates:
        print(f"\n── Reviewing digest: {date_str} ──\n")
        try:
            digest = load_digest_for_date(date_str, RESOURCES_DIR)
        except FileNotFoundError as exc:
            print(f"Warning: {exc} — skipping.")
            continue
        except json.JSONDecodeError as exc:
            print(f"Warning: Could not parse digest for {date_str}: {exc} — skipping.")
            continue

        papers = digest.get("papers", [])
        if not papers:
            print("  No papers in this digest.")
            continue

        # Filter out already-reviewed papers
        pending = [p for p in papers if p.get("arxiv_id") not in reviewed_paper_ids]
        already_reviewed = len(papers) - len(pending)
        if already_reviewed:
            print(f"  (Skipping {already_reviewed} already-reviewed paper(s).)\n")
        if not pending:
            print("  All papers in this digest have already been reviewed.")
            continue

        for i, paper in enumerate(pending, 1):
            title = paper.get("title", "(no title)")
            cats = ", ".join(paper.get("categories", []))
            score = paper.get("score", "?")
            summary = paper.get("summary", "")
            print(f"[{i}/{len(pending)}] {title}")
            print(f"  Categories: {cats}  |  Score: {score}")
            if summary:
                # Show first 200 chars
                preview = summary[:200].rstrip()
                if len(summary) > 200:
                    preview += "…"
                print(f"  {preview}")
            print()

            try:
                raw = (
                    input("  Feedback — [g]ood / [b]ad / [v]erbal / [s]kip (default): ")
                    .strip()
                    .lower()
                )
            except (EOFError, KeyboardInterrupt):
                print("\nCancelled.")
                sys.exit(0)

            if raw in ("g", "good"):
                feedback_list.append(build_feedback_entry(paper, "good", ""))
                print("  ✓ Marked as good.\n")
            elif raw in ("b", "bad"):
                feedback_list.append(build_feedback_entry(paper, "bad", ""))
                print("  ✓ Marked as bad.\n")
            elif raw in ("v", "verbal"):
                try:
                    text = input("  Your note: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nCancelled.")
                    sys.exit(0)
                feedback_list.append(build_feedback_entry(paper, "verbal", text))
                print("  ✓ Feedback recorded.\n")
            else:
                print("  Skipped.\n")

    if not feedback_list:
        print("No feedback given, nothing to do.")
        sys.exit(0)

    print(
        f"\nCollected {len(feedback_list)} feedback item(s). Consulting LLM for preference update…\n"
    )

    # ── Load LLM config + create client ──
    try:
        llm_config = load_llm_config()
    except Exception as exc:
        print(f"Error loading LLM config: {exc}")
        sys.exit(1)

    try:
        client = create_client(llm_config["provider"], api_key=llm_config["api_key"])
    except LLMError as exc:
        print(f"Error creating LLM client: {exc}")
        sys.exit(1)

    prompt = _build_llm_prompt(existing_prefs, feedback_list)

    try:
        delta = client.complete_json(prompt, _DELTA_SCHEMA, model=llm_config["scorer_model"])
    except LLMError as exc:
        print(f"Error calling LLM: {exc}")
        sys.exit(1)

    # ── Display reasoning + summary ──
    reasoning = delta.get("reasoning", "")
    if reasoning:
        print("── LLM Reasoning ──")
        print(reasoning)
        print()

    print("── Proposed Changes ──")
    any_changes = False

    weight_adj = delta.get("weight_adjustments", {})
    if weight_adj:
        any_changes = True
        print("Weight adjustments:")
        for cat, w in weight_adj.items():
            print(f"  {cat}: → {w}")

    add_kws = delta.get("add_keywords", {})
    if add_kws:
        any_changes = True
        print("Add keywords:")
        for cat, kws in add_kws.items():
            print(f"  {cat}: {', '.join(kws)}")

    rm_kws = delta.get("remove_keywords", {})
    if rm_kws:
        any_changes = True
        print("Remove keywords:")
        for cat, kws in rm_kws.items():
            print(f"  {cat}: {', '.join(kws)}")

    add_int = delta.get("add_interests", [])
    if add_int:
        any_changes = True
        print("Add interests:")
        for item in add_int:
            print(f"  + {item}")

    rm_int = delta.get("remove_interests", [])
    if rm_int:
        any_changes = True
        print("Remove interests:")
        for item in rm_int:
            print(f"  - {item}")

    add_av = delta.get("add_avoid", [])
    if add_av:
        any_changes = True
        print("Add avoid:")
        for item in add_av:
            print(f"  + {item}")

    rm_av = delta.get("remove_avoid", [])
    if rm_av:
        any_changes = True
        print("Remove avoid:")
        for item in rm_av:
            print(f"  - {item}")

    if not any_changes:
        print("No preference changes proposed.")
        sys.exit(0)

    print()

    # ── Confirm and apply ──
    try:
        answer = input("Apply these changes? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled — no changes saved.")
        sys.exit(0)

    if answer not in ("", "y", "yes"):
        print("Changes discarded.")
        sys.exit(0)

    updated_prefs = apply_delta(existing_prefs, delta)

    # Append to feedback_history, increment update_count
    history_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        "feedback_count": len(feedback_list),
        "dates_reviewed": selected_dates,
        "reviewed_paper_ids": [e["arxiv_id"] for e in feedback_list],
        "reasoning": reasoning,
    }
    updated_prefs.setdefault("feedback_history", []).append(history_entry)
    updated_prefs["update_count"] = existing_prefs.get("update_count", 0) + 1
    updated_prefs["last_updated"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017

    with USER_PREFERENCES_PATH.open("w") as f:
        json.dump(updated_prefs, f, indent=2)

    print(f"\nPreferences updated and saved to {USER_PREFERENCES_PATH}")
    print(f"Update #{updated_prefs['update_count']} complete.")


if __name__ == "__main__":
    main()
