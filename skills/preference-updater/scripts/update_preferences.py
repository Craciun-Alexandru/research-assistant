#!/usr/bin/env python3
"""
Update user research preferences based on feedback.

Usage:
    # Add keywords to a category
    python3 update_preferences.py \\
        --preferences user_preferences.json \\
        --action add-keywords \\
        --category cs.LG \\
        --keywords "keyword1,keyword2" \\
        --reason "User feedback reason"

    # Adjust category weight
    python3 update_preferences.py \\
        --preferences user_preferences.json \\
        --action adjust-weight \\
        --category math.AG \\
        --weight-delta 0.1 \\
        --reason "User wants more papers"

    # Add avoidance criterion
    python3 update_preferences.py \\
        --preferences user_preferences.json \\
        --action add-avoidance \\
        --criterion "Description of what to avoid" \\
        --reason "User disliked certain papers"

    # Add new research area
    python3 update_preferences.py \\
        --preferences user_preferences.json \\
        --action add-area \\
        --category math.CT \\
        --weight 0.75 \\
        --keywords "category theory,functors" \\
        --reason "User wants to track this area"
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def load_preferences(filepath):
    """Load preferences JSON file."""
    with open(filepath) as f:
        return json.load(f)


def save_preferences(preferences, filepath):
    """Save preferences JSON file."""
    preferences["last_updated"] = datetime.utcnow().isoformat() + "Z"
    preferences["update_count"] = preferences.get("update_count", 0) + 1
    
    with open(filepath, "w") as f:
        json.dump(preferences, f, indent=2)


def record_feedback(preferences, action_summary, reason, paper_id=None):
    """Record feedback in history."""
    if "feedback_history" not in preferences:
        preferences["feedback_history"] = []
    
    feedback_entry = {
        "date": datetime.utcnow().isoformat() + "Z",
        "action": action_summary,
        "reason": reason
    }
    
    if paper_id:
        feedback_entry["paper_id"] = paper_id
    
    preferences["feedback_history"].append(feedback_entry)
    
    # Keep last 50 entries
    preferences["feedback_history"] = preferences["feedback_history"][-50:]


def add_keywords(preferences, category, keywords_str):
    """Add keywords to a category."""
    if category not in preferences["research_areas"]:
        print(f"Warning: Category {category} not in research areas")
        return False
    
    new_keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    existing_keywords = preferences["research_areas"][category].get("keywords", [])
    
    # Add new keywords, avoiding duplicates
    added = []
    for kw in new_keywords:
        if kw not in existing_keywords:
            existing_keywords.append(kw)
            added.append(kw)
    
    # Limit to 10 keywords per category
    if len(existing_keywords) > 10:
        print(f"Warning: Too many keywords for {category}, keeping most recent 10")
        existing_keywords = existing_keywords[-10:]
    
    preferences["research_areas"][category]["keywords"] = existing_keywords
    
    return added


def adjust_weight(preferences, category, delta):
    """Adjust weight for a category."""
    if category not in preferences["research_areas"]:
        print(f"Warning: Category {category} not in research areas")
        return False
    
    current_weight = preferences["research_areas"][category]["weight"]
    new_weight = max(0.5, min(1.0, current_weight + delta))
    
    preferences["research_areas"][category]["weight"] = new_weight
    
    return {
        "old_weight": current_weight,
        "new_weight": new_weight,
        "delta": delta
    }


def add_avoidance(preferences, criterion):
    """Add avoidance criterion."""
    if "avoid" not in preferences:
        preferences["avoid"] = []
    
    # Avoid duplicates
    if criterion in preferences["avoid"]:
        print(f"Criterion already exists: {criterion}")
        return False
    
    preferences["avoid"].append(criterion)
    
    # Limit to 5 criteria
    if len(preferences["avoid"]) > 5:
        print("Warning: Too many avoidance criteria, removing oldest")
        preferences["avoid"] = preferences["avoid"][-5:]
    
    return True


def add_research_area(preferences, category, weight, keywords_str):
    """Add a new research area."""
    if category in preferences["research_areas"]:
        print(f"Warning: Category {category} already exists, updating instead")
        return adjust_weight(preferences, category, 0)  # No-op adjustment
    
    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    
    preferences["research_areas"][category] = {
        "weight": weight,
        "keywords": keywords
    }
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Update research preferences")
    parser.add_argument(
        "--preferences",
        default="user_preferences.json",
        help="Preferences file path"
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=["add-keywords", "adjust-weight", "add-avoidance", "add-area"],
        help="Action to perform"
    )
    parser.add_argument("--category", help="Research area category (e.g., cs.LG)")
    parser.add_argument("--keywords", help="Comma-separated keywords")
    parser.add_argument("--weight-delta", type=float, help="Weight adjustment (-1.0 to 1.0)")
    parser.add_argument("--weight", type=float, help="Initial weight for new area (0.5-1.0)")
    parser.add_argument("--criterion", help="Avoidance criterion text")
    parser.add_argument("--reason", required=True, help="Reason for this update")
    parser.add_argument("--paper-id", help="Optional paper ID related to feedback")
    
    args = parser.parse_args()
    
    # Resolve path
    workspace = Path.home() / ".openclaw/workspaces/research-assistant"
    prefs_path = workspace / args.preferences
    
    # Load preferences
    print(f"Loading preferences from {prefs_path}...")
    preferences = load_preferences(prefs_path)
    
    # Perform action
    action_summary = ""
    success = False
    
    if args.action == "add-keywords":
        if not args.category or not args.keywords:
            print("Error: --category and --keywords required for add-keywords")
            sys.exit(1)
        
        added = add_keywords(preferences, args.category, args.keywords)
        if added:
            action_summary = f"Added keywords to {args.category}: {', '.join(added)}"
            success = True
    
    elif args.action == "adjust-weight":
        if not args.category or args.weight_delta is None:
            print("Error: --category and --weight-delta required for adjust-weight")
            sys.exit(1)
        
        result = adjust_weight(preferences, args.category, args.weight_delta)
        if result:
            action_summary = f"Adjusted {args.category} weight: {result['old_weight']:.2f} → {result['new_weight']:.2f}"
            success = True
    
    elif args.action == "add-avoidance":
        if not args.criterion:
            print("Error: --criterion required for add-avoidance")
            sys.exit(1)
        
        if add_avoidance(preferences, args.criterion):
            action_summary = f"Added avoidance criterion: {args.criterion}"
            success = True
    
    elif args.action == "add-area":
        if not args.category or args.weight is None or not args.keywords:
            print("Error: --category, --weight, and --keywords required for add-area")
            sys.exit(1)
        
        if add_research_area(preferences, args.category, args.weight, args.keywords):
            action_summary = f"Added research area {args.category} (weight: {args.weight})"
            success = True
    
    if not success:
        print("Update failed")
        sys.exit(1)
    
    # Record feedback
    record_feedback(preferences, action_summary, args.reason, args.paper_id)
    
    # Save preferences
    save_preferences(preferences, prefs_path)
    
    print(f"\n✓ {action_summary}")
    print(f"✓ Reason: {args.reason}")
    print(f"✓ Preferences saved to {prefs_path}")
    print(f"✓ Total updates: {preferences['update_count']}")


if __name__ == "__main__":
    main()
