"""Shared utilities: JSON I/O and keyword helpers."""

import json
from pathlib import Path


def load_json(filepath: Path) -> dict:
    """Load JSON file."""
    with filepath.open() as f:
        return json.load(f)


def save_json(data, filepath: Path) -> None:
    """Save JSON file."""
    with filepath.open("w") as f:
        json.dump(data, f, indent=2)


def get_all_keywords(preferences: dict) -> set[str]:
    """Extract and lowercase all keywords from user preferences."""
    keywords = set()
    for area_data in preferences["research_areas"].values():
        for keyword in area_data.get("keywords", []):
            keywords.add(keyword.lower())
    return keywords
