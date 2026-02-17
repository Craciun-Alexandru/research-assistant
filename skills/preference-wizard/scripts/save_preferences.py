#!/usr/bin/env python3
"""
Save user research preferences for arXiv digest system.

Usage:
    python3 save_preferences.py \\
        --output /path/to/user_preferences.json \\
        --areas "cs.LG:1.0,stat.ML:0.9" \\
        --keywords-cs.LG "transformers,attention" \\
        --interests "Interest 1|Interest 2" \\
        --avoid "Avoid 1|Avoid 2"
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Save user research preferences")
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for user_preferences.json",
    )
    parser.add_argument(
        "--areas",
        required=True,
        help="Comma-separated area:weight pairs (e.g., 'cs.LG:1.0,stat.ML:0.9')",
    )
    parser.add_argument(
        "--interests",
        default="",
        help="Pipe-separated list of research interests",
    )
    parser.add_argument(
        "--avoid",
        default="",
        help="Pipe-separated list of things to avoid",
    )

    # Dynamic keyword arguments for each area
    args, unknown = parser.parse_known_args()

    # Parse area-specific keywords
    keywords_args = {}
    for arg in unknown:
        if arg.startswith("--keywords-"):
            area = arg.replace("--keywords-", "")
            # Get the value (next arg)
            idx = unknown.index(arg)
            if idx + 1 < len(unknown):
                keywords_args[area] = unknown[idx + 1]

    return args, keywords_args


def parse_areas(areas_str):
    """Parse 'cs.LG:1.0,stat.ML:0.9' into dict."""
    areas = {}
    for pair in areas_str.split(","):
        if ":" not in pair:
            print(
                f"Warning: Skipping malformed area '{pair}' (expected format: 'area:weight')"
            )
            continue
        area, weight = pair.split(":", 1)
        try:
            areas[area.strip()] = float(weight.strip())
        except ValueError:
            print(f"Warning: Invalid weight for {area}, using 1.0")
            areas[area.strip()] = 1.0
    return areas


def parse_keywords(keywords_str):
    """Parse 'keyword1,keyword2,keyword3' into list."""
    if not keywords_str:
        return []
    return [k.strip() for k in keywords_str.split(",") if k.strip()]


def parse_list(list_str):
    """Parse pipe-separated list."""
    if not list_str:
        return []
    return [item.strip() for item in list_str.split("|") if item.strip()]


def build_preferences(areas_dict, keywords_dict, interests, avoid):
    """Build the user_preferences.json structure."""
    research_areas = {}

    for area, weight in areas_dict.items():
        research_areas[area] = {
            "weight": weight,
            "keywords": keywords_dict.get(area, []),
        }

    return {
        "research_areas": research_areas,
        "interests": interests,
        "avoid": avoid,
        "feedback_history": [],
        "last_updated": datetime.utcnow().isoformat() + "Z",
    }


def main():
    args, keywords_args = parse_args()

    # Parse areas
    areas_dict = parse_areas(args.areas)
    if not areas_dict:
        print("Error: No valid research areas provided")
        sys.exit(1)

    # Parse keywords for each area
    keywords_dict = {}
    for area in areas_dict.keys():
        if area in keywords_args:
            keywords_dict[area] = parse_keywords(keywords_args[area])

    # Parse interests and avoid lists
    interests = parse_list(args.interests)
    avoid = parse_list(args.avoid)

    # Build preferences structure
    preferences = build_preferences(areas_dict, keywords_dict, interests, avoid)

    # Write to output file
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(preferences, f, indent=2)

    print(f"✓ Preferences saved to {output_path}")
    print(f"✓ Tracking {len(areas_dict)} research areas")
    print(f"✓ {sum(len(kws) for kws in keywords_dict.values())} total keywords")
    print(f"✓ {len(interests)} research interests")
    print(f"✓ {len(avoid)} avoidance criteria")


if __name__ == "__main__":
    main()
