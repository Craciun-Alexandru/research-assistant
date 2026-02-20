"""
Interactive onboarding wizard for research preferences.

Conducts a multi-turn conversation via the Gemini API to capture
research areas, interests, and avoidances, then writes the results
to user_preferences.json.

Usage:
    python -m arxiv_digest.onboard
"""

import json
import sys
from datetime import datetime, timezone

from arxiv_digest.config import USER_PREFERENCES_PATH, load_llm_config
from arxiv_digest.llm import ChatSession, LLMError, create_client

_SYSTEM_PROMPT = """\
You are a friendly, conversational research preference interviewer helping \
a researcher set up their personalized arXiv digest.

## Your Goal

Guide the user through 5 phases to capture their research preferences. \
Be conversational—like chatting with a colleague, not filling out a form.

## Phases

### Phase 1: Research Areas (Required)
Ask about primary research areas. Accept arXiv category codes (cs.LG, math.AG) \
or natural descriptions ("machine learning"). Map descriptions to categories and confirm. \
Suggest related categories they might have missed.

### Phase 2: Specific Interests (Required)
Ask about specific topics, methods, or problems within their areas. \
Aim for 5-10 keywords/phrases. Prompt with examples if needed.

### Phase 3: Research Goals (Optional but Helpful)
Ask what they hope to get from the papers (keeping up with methods, finding \
cross-field connections, theoretical foundations, etc.). Use this to calibrate priorities.

### Phase 4: Avoidances (Optional)
Ask about paper types to skip (purely empirical benchmarks, engineering-focused, \
incremental improvements, etc.). Offer reasonable defaults if they have no preference.

### Phase 5: Confirmation
Summarize everything gathered with a clear profile showing:
- Research areas with arXiv codes and suggested weights (primary: 1.0, related: 0.8-0.9)
- Key interests
- Avoidances
Ask "Does this look right? Any adjustments?"

## arXiv Category Reference

Common categories:
- cs.LG - Machine Learning
- cs.AI - Artificial Intelligence
- cs.CL - Computation and Language (NLP)
- cs.CV - Computer Vision
- cs.NE - Neural and Evolutionary Computing
- cs.IT - Information Theory
- stat.ML - Statistics: Machine Learning
- stat.TH - Statistics Theory
- math.AG - Algebraic Geometry
- math.AC - Commutative Algebra
- math.AT - Algebraic Topology
- math.CT - Category Theory
- math.DG - Differential Geometry
- math.DS - Dynamical Systems
- math.OC - Optimization and Control
- math.PR - Probability
- math.ST - Statistics Theory
- physics.comp-ph - Computational Physics
- quant-ph - Quantum Physics
- eess.SP - Signal Processing
- q-bio.QM - Quantitative Methods (Biology)

## Behaviors

- Be conversational and enthusiastic about their research
- Use natural transitions between phases
- Suggest related categories (cs.LG → stat.ML, math.AG → math.AC)
- Use smart defaults for weights (primary: 1.0, closely related: 0.9, secondary: 0.8)
- Don't ask all questions at once
- Don't overwhelm with jargon unless they use it first

## Completion Signal

After the user confirms the summary (says something like "yes", "looks good", \
"perfect", etc.), respond with your final message AND include the word DONE \
on its own line at the very end of your response.

Do NOT say DONE until the user has confirmed the summary.
"""

ONBOARD_SYSTEM_PROMPT = _SYSTEM_PROMPT

_EXTRACTION_PROMPT = """\
Based on the conversation above, extract the user's research preferences \
as a JSON object with exactly this structure:

{{
  "research_areas": {{
    "<arxiv_category_code>": {{
      "weight": <float between 0.0 and 1.0>,
      "keywords": ["keyword1", "keyword2", ...]
    }}
  }},
  "interests": ["interest1", "interest2", ...],
  "avoid": ["avoidance1", "avoidance2", ...]
}}

Rules:
- Use actual arXiv category codes (e.g., "cs.LG", "math.AG")
- Weights: primary areas get 1.0, closely related 0.9, secondary 0.8, tangential 0.7
- Keywords: specific terms relevant to that category for this user
- Interests: broader research themes and goals (5-10 items)
- Avoid: types of papers to skip (keep it concise)

Respond with ONLY the JSON object, no other text.
"""


def _load_existing_prefs() -> dict:
    """Load existing user_preferences.json if it exists."""
    if USER_PREFERENCES_PATH.exists():
        with USER_PREFERENCES_PATH.open() as f:
            return json.load(f)
    return {}


def _save_prefs(prefs: dict) -> None:
    """Write user_preferences.json."""
    with USER_PREFERENCES_PATH.open("w") as f:
        json.dump(prefs, f, indent=2)
    print(f"\nPreferences saved to {USER_PREFERENCES_PATH}")


def extract_preferences_from_chat(chat: ChatSession) -> dict:
    """Send the extraction prompt and parse the JSON response.

    Args:
        chat: An active ChatSession with completed onboarding conversation.

    Returns:
        Dict with research_areas, interests, and avoid keys.

    Raises:
        json.JSONDecodeError: If the response is not valid JSON.
        LLMError: If the LLM call fails.
    """
    extraction_response = chat.send(_EXTRACTION_PROMPT)
    text = extraction_response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return json.loads(text)


def merge_research_preferences(existing: dict, new_research: dict) -> dict:
    """Merge extracted research preferences into an existing preferences dict.

    Replaces research_areas/interests/avoid from new_research while preserving
    llm config, delivery settings, feedback_history, and update_count.

    Args:
        existing: Current full preferences dict.
        new_research: Dict with research_areas, interests, and avoid keys.

    Returns:
        Merged preferences dict (does not mutate input).
    """
    merged = dict(existing)
    merged["research_areas"] = new_research.get("research_areas", {})
    merged["interests"] = new_research.get("interests", [])
    merged["avoid"] = new_research.get("avoid", [])
    merged["feedback_history"] = existing.get("feedback_history", [])
    merged["last_updated"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
    merged["update_count"] = existing.get("update_count", 0)
    return merged


def main() -> None:
    """Run the interactive onboarding wizard."""
    print("=" * 48)
    print("  arXiv Digest — Research Preference Setup")
    print("=" * 48)
    print()

    # Load existing prefs for merging later; load LLM config via the
    # provider-aware helper so the api_key field is always correct.
    existing_prefs = _load_existing_prefs()
    try:
        llm_config = load_llm_config()
    except Exception:
        print(f"Error: No LLM configuration found in {USER_PREFERENCES_PATH}")
        print("Run setup.sh first to configure your API key.")
        sys.exit(1)

    api_key = llm_config.get("api_key", "")
    if not api_key:
        print("Error: No valid API key found.")
        print("Run setup.sh first to configure your API key.")
        sys.exit(1)

    provider = llm_config.get("provider", "gemini")
    # Use scorer model (flash-class) for the conversational wizard
    model = llm_config.get("scorer_model")

    try:
        client = create_client(provider, api_key=api_key)
    except LLMError as exc:
        print(f"Error creating LLM client: {exc}")
        sys.exit(1)

    # Start chat session
    chat = client.chat(_SYSTEM_PROMPT, model=model)

    # Get the first message from the LLM
    try:
        greeting = chat.send("Hello! I'd like to set up my arXiv digest.")
    except LLMError as exc:
        print(f"Error starting conversation: {exc}")
        sys.exit(1)

    print(f"\n{greeting}\n")

    # Conversation loop
    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nOnboarding cancelled.")
            sys.exit(0)

        if not user_input:
            continue

        try:
            response = chat.send(user_input)
        except LLMError as exc:
            print(f"\nError: {exc}")
            print("Let's try that again.")
            continue

        print(f"\n{response}\n")

        # Check if the wizard signaled completion
        if "DONE" in response.split("\n"):
            break

    # Extract structured preferences from the conversation
    print("Extracting your preferences...")
    try:
        research_prefs = extract_preferences_from_chat(chat)
    except (json.JSONDecodeError, LLMError) as exc:
        print(f"Error extracting preferences: {exc}")
        print("Your conversation was completed but preferences could not be saved automatically.")
        print("You can re-run this wizard with: python -m arxiv_digest.onboard")
        sys.exit(1)

    merged = merge_research_preferences(existing_prefs, research_prefs)

    _save_prefs(merged)

    print("\nYou're all set! Your first digest will use these preferences.")
    print("The system learns from feedback — mark papers as relevant/not relevant")
    print("and preferences will be refined over time.")


if __name__ == "__main__":
    main()
