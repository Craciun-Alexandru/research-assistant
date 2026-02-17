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
from arxiv_digest.llm import LLMError, create_client

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


def main() -> None:
    """Run the interactive onboarding wizard."""
    print("=" * 48)
    print("  arXiv Digest — Research Preference Setup")
    print("=" * 48)
    print()

    # Load existing prefs for LLM config
    existing_prefs = _load_existing_prefs()
    llm_config = existing_prefs.get("llm")
    if not llm_config:
        try:
            llm_config = load_llm_config()
        except Exception:
            print("Error: No LLM configuration found.")
            print("Run setup.sh first to configure your API key.")
            sys.exit(1)

    api_key = llm_config.get("api_key", "")
    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
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
        extraction_response = chat.send(_EXTRACTION_PROMPT)
        # Strip markdown code fences if present
        text = extraction_response.strip()
        if text.startswith("```"):
            # Remove first line (```json or ```) and last line (```)
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
        research_prefs = json.loads(text)
    except (json.JSONDecodeError, LLMError) as exc:
        print(f"Error extracting preferences: {exc}")
        print("Your conversation was completed but preferences could not be saved automatically.")
        print("You can re-run this wizard with: python -m arxiv_digest.onboard")
        sys.exit(1)

    # Merge with existing prefs: keep llm config, replace research data
    merged = dict(existing_prefs)
    merged["research_areas"] = research_prefs.get("research_areas", {})
    merged["interests"] = research_prefs.get("interests", [])
    merged["avoid"] = research_prefs.get("avoid", [])
    merged["feedback_history"] = existing_prefs.get("feedback_history", [])
    merged["last_updated"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017
    merged["update_count"] = existing_prefs.get("update_count", 0)

    _save_prefs(merged)

    print("\nYou're all set! Your first digest will use these preferences.")
    print("The system learns from feedback — mark papers as relevant/not relevant")
    print("and preferences will be refined over time.")


if __name__ == "__main__":
    main()
