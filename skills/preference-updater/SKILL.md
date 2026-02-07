---
name: preference-updater
description: Update research preferences based on user feedback on papers. Use when user provides feedback on paper relevance, marks papers as interesting/not interesting, or asks to adjust their research interests. Triggers include feedback on papers, requests to update preferences, or learning from user reactions.
---

# Preference Updater

Intelligently update user research preferences based on feedback on paper relevance.

## When to Use

Trigger this skill when the user:
- Provides feedback on papers from the digest ("this was great", "not relevant", "more like this")
- Explicitly marks papers as relevant/not relevant
- Says they want to adjust their preferences based on what they've been seeing
- Mentions that certain topics should be weighted higher/lower

## Workflow

### Phase 1: Collect Feedback

**Ask for feedback naturally**:
```
How was today's digest? Were these papers useful?
```

**Accept various formats**:
- Structured: "Paper 1 was great, paper 3 not relevant, paper 5 excellent"
- Casual: "Loved the transformer paper, the benchmark one was useless"
- Binary: "👍 on papers 1, 2, 5 and 👎 on papers 3, 4"
- Explicit IDs: "arxiv:2501.12345 was relevant"

**Follow-up questions**:
- If they liked a paper: "What specifically made that paper interesting?"
- If they disliked a paper: "What was wrong with it—wrong topic, too applied, not novel enough?"

### Phase 2: Parse Feedback

Extract structured feedback:
```python
{
  "paper_id": "2501.12345",
  "title": "Transformers Meet Algebraic Geometry",
  "categories": ["cs.LG", "math.AG"],
  "keywords_present": ["transformers", "algebraic geometry"],
  "relevance": "relevant",  # or "not_relevant"
  "reason": "Exactly the kind of cross-field connection I'm looking for",
  "date": "2026-02-04"
}
```

### Phase 3: Analyze Patterns

Look for patterns in the feedback:

**Category patterns**:
- If user consistently likes papers in math.CT → Increase math.CT weight
- If user consistently dislikes cs.CV papers → Lower cs.CV weight or remove

**Keyword patterns**:
- If user likes papers with "sheaves" → Add "sheaves" to keywords
- If user dislikes papers with "benchmark" → Add to avoidance criteria

**Interest patterns**:
- If user likes cross-field papers → Emphasize "connections between fields"
- If user prefers theory over applications → Strengthen avoidance of applied papers

**Thematic patterns**:
- User feedback: "Love papers on category theory in ML"
- Action: Add "category-theoretic approaches to learning" to interests
- Action: Suggest adding math.CT if not already tracked

### Phase 4: Propose Updates

**Summarize proposed changes**:
```
Based on your feedback, I'd like to update your preferences:

Changes:
- Increase math.AG weight: 0.8 → 0.9 (you liked 3/4 math.AG papers)
- Add keyword: "sheaves" (appeared in papers you liked)
- Add to interests: "Sheaf-theoretic approaches to learning"
- Strengthen avoidance: "Benchmark papers" (you disliked 2 benchmark papers)

Sound good?
```

**Wait for confirmation** before applying changes.

### Phase 5: Apply Updates

Call the `update_preferences.py` script:
```bash
python3 scripts/update_preferences.py \
  --preferences user_preferences.json \
  --feedback-json '{...}' \
  --apply
```

The script will:
1. Load current preferences
2. Analyze feedback patterns
3. Calculate weight adjustments
4. Add/remove keywords and interests
5. Update feedback history
6. Save updated preferences
7. Report changes made

### Phase 6: Confirm and Learn

**Confirm changes**:
```
✓ Updated preferences saved!

Your new weights:
- cs.LG: 1.0 (unchanged)
- stat.ML: 0.9 (unchanged)
- math.AG: 0.9 (increased from 0.8)
- math.AC: 0.8 (unchanged)

New keywords added: sheaves, cohomology
New interests: Sheaf-theoretic approaches to learning

These changes will affect tomorrow's digest.
```

**Learning opportunity**:
- Log the feedback for future analysis
- Track which updates improve user satisfaction
- Identify emerging research interests over time

---

## Feedback Format

### Structured Feedback (Preferred)
```json
{
  "feedback": [
    {
      "paper_id": "2501.12345",
      "title": "Transformers Meet Algebraic Geometry",
      "relevance": "relevant",
      "reason": "Exactly my research focus",
      "categories": ["cs.LG", "math.AG"],
      "keywords_present": ["transformers", "algebraic geometry", "attention"]
    },
    {
      "paper_id": "2501.12346",
      "title": "Benchmark on ImageNet",
      "relevance": "not_relevant",
      "reason": "Pure benchmarking, no theory",
      "categories": ["cs.CV"],
      "keywords_present": ["benchmark"]
    }
  ],
  "date": "2026-02-04"
}
```

### Casual Feedback (Parse into Structured)

User says:
```
"The transformer/geometry paper was perfect! But that ImageNet benchmark was useless."
```

Parse to:
```json
{
  "feedback": [
    {
      "paper_match": "transformer.*geometry",
      "relevance": "relevant",
      "reason": "User called it perfect"
    },
    {
      "paper_match": "ImageNet.*benchmark",
      "relevance": "not_relevant",
      "reason": "User said useless"
    }
  ]
}
```

---

## Update Algorithms

### Weight Adjustment

**Rule**: Adjust category weights based on relevance ratio.
```python
def adjust_weight(current_weight, relevant_count, total_count):
    """
    Adjust weight based on feedback ratio.
    
    Increase if >75% relevant
    Decrease if <25% relevant
    """
    ratio = relevant_count / total_count if total_count > 0 else 0.5
    
    if ratio >= 0.75:
        # Strong positive signal - increase weight
        new_weight = min(current_weight + 0.1, 1.0)
    elif ratio <= 0.25:
        # Strong negative signal - decrease weight
        new_weight = max(current_weight - 0.1, 0.3)
    else:
        # Mixed signal - no change
        new_weight = current_weight
    
    return round(new_weight, 1)
```

### Keyword Learning

**Rule**: Add keywords that appear in relevant papers.
```python
def learn_keywords(feedback, existing_keywords):
    """
    Extract keywords from relevant papers.
    """
    relevant_papers = [f for f in feedback if f["relevance"] == "relevant"]
    
    # Count keyword frequencies
    keyword_counts = {}
    for paper in relevant_papers:
        for kw in paper.get("keywords_present", []):
            keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
    
    # Add keywords that appear in 2+ relevant papers
    new_keywords = []
    for kw, count in keyword_counts.items():
        if count >= 2 and kw not in existing_keywords:
            new_keywords.append(kw)
    
    return new_keywords
```

### Avoidance Learning

**Rule**: Add patterns from not-relevant papers.
```python
def learn_avoidances(feedback, existing_avoidances):
    """
    Learn what to avoid from negative feedback.
    """
    not_relevant_papers = [f for f in feedback if f["relevance"] == "not_relevant"]
    
    # Extract common patterns
    patterns = {}
    for paper in not_relevant_papers:
        reason = paper.get("reason", "").lower()
        
        if "benchmark" in reason:
            patterns["benchmark"] = patterns.get("benchmark", 0) + 1
        if "applied" in reason or "engineering" in reason:
            patterns["applied"] = patterns.get("applied", 0) + 1
        if "incremental" in reason:
            patterns["incremental"] = patterns.get("incremental", 0) + 1
    
    # Add to avoidances if pattern appears 2+ times
    new_avoidances = []
    for pattern, count in patterns.items():
        if count >= 2:
            avoid_text = f"Papers focused on {pattern} without theoretical insights"
            if avoid_text not in existing_avoidances:
                new_avoidances.append(avoid_text)
    
    return new_avoidances
```

---

## Conversation Examples

### Example 1: Simple Feedback
```
User: Today's digest was great! I loved papers 1, 3, and 5. Paper 2 was too applied.

You: Glad you found them useful! Let me update your preferences.

[Analyzing feedback...]
- Papers 1, 3, 5: All had strong theory + math connections
- Paper 2: Was implementation-focused

I'd like to make these updates:
- Strengthen avoidance: "Implementation-focused papers without theory"
- Papers you liked were all cs.LG + math.AG → keep current weights

Should I apply these changes?

User: Yes

You: ✓ Updated! You'll see fewer applied papers and more theory-focused ones tomorrow.
```

### Example 2: Discovering New Interest
```
User: The paper on category theory and neural networks was fascinating! I want more like that.

You: That's a great direction! That paper combined math.CT (Category Theory) with cs.LG. 

Should I:
1. Add math.CT to your tracked areas (weight 0.7)?
2. Add "category-theoretic approaches" to your interests?
3. Add keywords: "category theory", "functors", "natural transformations"?

User: Yes to all three!

You: Perfect! I'm updating your preferences now.

[Updates applied]

✓ Added math.CT (Category Theory) - weight 0.7
✓ Added interest: "Category-theoretic approaches to learning"
✓ Added 3 new keywords

Tomorrow's digest will include relevant category theory papers!
```

### Example 3: Negative Feedback
```
User: These benchmark papers keep showing up and I don't care about them.

You: Got it—let me strengthen the filtering. Looking at recent digests, I see:
- Last 3 days: 4 benchmark papers delivered
- Your feedback: 0/4 were relevant

I'll update to:
- Strengthen avoidance: "Benchmark and evaluation papers"
- Lower threshold for papers with "benchmark" in title

This should mostly eliminate them. Sound good?

User: Yes please.

You: ✓ Updated! Benchmark papers should be rare or absent from now on.
```

---

## Key Behaviors

✅ **Always confirm before updating**
- Never silently change preferences
- Show exactly what will change
- Get user approval

✅ **Be specific about changes**
- Don't just say "updated preferences"
- List each change (weights, keywords, interests)
- Explain why each change was made

✅ **Learn gradually**
- Don't make huge weight swings from one day's feedback
- Build confidence over multiple feedback sessions
- Prefer adding keywords over removing them

✅ **Preserve user intent**
- Don't remove areas user explicitly set up
- Don't change avoidances user explicitly stated
- Respect the original preference structure

❌ **Don't be overeager**
- Don't suggest changes after 1 day of feedback
- Don't add new areas without asking
- Don't dramatically change weights (max ±0.1 per update)

---

## Script Usage

After gathering and parsing feedback:
```bash
cd ~/.openclaw/workspaces/research-assistant/skills/preference-updater

python3 scripts/update_preferences.py \
  --preferences ~/.openclaw/workspaces/research-assistant/user_preferences.json \
  --feedback-file feedback_2026-02-04.json \
  --apply
```

Or with inline JSON:
```bash
python3 scripts/update_preferences.py \
  --preferences ~/.openclaw/workspaces/research-assistant/user_preferences.json \
  --feedback-json '{"feedback": [...], "date": "2026-02-04"}' \
  --apply
```

The script outputs:
- Changes made
- New vs old values
- Success confirmation

---

## References

For detailed update algorithms and pattern detection, see:
- `references/update_algorithm.md` - Detailed update formulas
