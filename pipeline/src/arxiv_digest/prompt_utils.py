"""Shared prompt-building utilities for the arXiv digest pipeline."""


def build_persona(interests: list[str], research_areas: dict) -> str:
    """Derive a domain-specific LLM persona from the user's preferences.

    Combines the arXiv category codes from research_areas (sorted by weight
    descending) with the free-text interests list to produce a persona sentence
    like:

      "You are an expert researcher working in cs.LG, math.AG, stat.ML whose
       research focuses on: theoretical foundations of deep learning;
       connections between algebra and neural networks."

    Args:
        interests: From preferences["interests"].
        research_areas: From preferences["research_areas"]; keys are arXiv
            category codes, values are dicts with at least a "weight" key.

    Returns:
        A single-sentence persona string, no trailing newline.
    """
    sorted_cats = sorted(
        research_areas.keys(),
        key=lambda c: research_areas[c].get("weight", 0),
        reverse=True,
    )

    base = "You are an expert researcher"

    if sorted_cats and interests:
        cats_str = ", ".join(sorted_cats)
        interests_str = "; ".join(interests)
        return f"{base} working in {cats_str} whose research focuses on: {interests_str}."
    elif sorted_cats:
        cats_str = ", ".join(sorted_cats)
        return f"{base} working in {cats_str}."
    elif interests:
        interests_str = "; ".join(interests)
        return f"{base} whose research focuses on: {interests_str}."
    else:
        return f"{base}."
