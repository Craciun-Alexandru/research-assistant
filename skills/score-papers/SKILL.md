---
name: score-papers
description: Score arXiv papers for relevance based on user research preferences. Use when processing paper lists for curation, filtering, or recommendation. Triggers include scoring tasks, relevance assessment, paper filtering, or digest generation workflows.
---

# Score Papers

Score arXiv papers for relevance based on user research preferences and interests.

## When to Use

This skill is used by:
- **quick-scorer**: Bulk scoring of ~150 papers to identify top 25 candidates
- **deep-reviewer**: Deep analysis of top 25 papers to select final 5-6 for digest

## Agent-Specific Behavior

### Quick Scorer Mode - used by quick-scorer

**Goal**: High-throughput filtering with good recall

**Input**: `resources/current/filtered_papers.json` (~150 papers)

**Process**:
1. Load user preferences from `user_preferences.json`
2. **Batch process papers** (15-20 at a time, never one-by-one)
3. Assign scores 0-10 based on relevance
4. Use terse justifications (1 sentence max)
5. Select top 25-30 papers with scores ≥ 7

**Scoring criteria** (fast heuristics):
- **Category match** (5 points max): Paper in user's research areas
- **Keyword match** (3 points max): Title/abstract contains user keywords
- **Interest alignment** (2 points max): Relates to stated research interests

**Output**: `resources/current/scored_papers_summary.json` with scores and brief reasons

**Example output**:
```json
{
  "scored_papers_summary": [
    {
      "arxiv_id": "2501.12345",
      "title": "Transformers Meet Algebraic Geometry",
      "authors": ["Smith, J.", "Jones, A."],
      "categories": ["cs.LG", "math.AG"],
      "abstract": "We establish connections between...",
      "score": 9,
      "reason": "Directly combines transformers with algebraic geometry—core interest."
    },
    ...
  ],
  "total_processed": 147,
  "selected_count": 25,
  "scoring_mode": "quick"
}
```

---

### Deep Reviewer Mode - used by deep-reviewer

**Goal**: Scholarly analysis with precision

**Input**: `resources/papers/` (folder containing the full text papers in `TXT` format)

**Process**:
1. Load user preferences from `user_preferences.json`
2. Deeply analyze each paper's contribution
3. Assess methodology, novelty, and relevance
4. Consider diversity across user's interests
5. Select 5-6 papers that:
   - Represent significant contributions
   - Span different aspects of user's research
   - Offer actionable insights

**Analysis structure** (per paper):

**Summary** (2-3 paragraphs):
- What problem does the paper address?
- What methodology/approach do they use?
- What are the key results and contributions?

**Relevance** (1 paragraph):
- How does this connect to the user's research interests?
- Why should they read this paper now? What specific value does it offer?

**Key Insight** (2-3 sentences):
- The most important takeaway
- What makes this paper stand out
- Potential impact or application

**Output**: `resources/current/digest_YYYY-MM-DD.json` with detailed analyses

**Example output**:
```json
{
  "digest_date": "2026-02-04",
  "summary": "Today's digest features advances in transformer theory, algebraic methods in learning, and geometric perspectives on neural architectures.",
  "papers": [
    {
      "arxiv_id": "2501.12345",
      "title": "Transformers Meet Algebraic Geometry",
      "authors": ["Smith, J.", "Jones, A."],
      "categories": ["cs.LG", "math.AG"],
      "abstract": "We establish connections between...",
      "summary": "This paper establishes a novel connection between transformer architectures and algebraic varieties...",
      "relevance": "This work directly addresses your interest in connections between deep learning and algebraic structures...",
      "key_insight": "The key insight is that attention mechanisms can be understood as morphisms between algebraic varieties...",
      "score": 9.5,
      "pdf_url": "https://arxiv.org/pdf/2501.12345"
    },
    ...
  ],
  "total_reviewed": 25,
  "selected_count": 6,
  "scoring_mode": "deep"
}
```

---

## Scoring Guidelines

### Research Area Weights

Load from `user_preferences.json`:
```json
{
  "research_areas": {
    "cs.LG": {"weight": 1.0, "keywords": [...]},
    "stat.ML": {"weight": 0.9, "keywords": [...]},
    "math.AG": {"weight": 0.8, "keywords": [...]},
    "math.AC": {"weight": 0.8, "keywords": [...]}
  }
}
```

**Category scoring**:
- Primary category in user's areas: Base score × weight
- Secondary categories: 50% of base score × weight
- Multiple category matches: Sum scores (capped at 10)

### Keyword Matching

**Title match** (higher weight):
- Keyword in title: +2 points per keyword (max 4)

**Abstract match** (lower weight):
- Keyword in abstract: +0.5 points per keyword (max 2)

**Fuzzy matching**:
- "transformer" matches "transformers", "attention" matches "self-attention"
- Use stemming for keyword variants

### Interest Alignment

Check paper themes against stated interests:
```json
"interests": [
  "Connections between deep learning and algebraic structures",
  "Theoretical foundations of transformers"
]
```

**Scoring**:
- Strong thematic match: +2 points
- Partial match: +1 point
- No clear match: 0 points

### Avoidance Filters

Check paper against avoidance criteria:
```json
"avoid": [
  "Purely empirical benchmark papers",
  "Engineering-focused papers without theoretical insights"
]
```

**Penalties**:
- Strong avoidance match: -3 points (or skip entirely)
- Partial match: -1 point

**Detection heuristics**:
- "Purely empirical": Title contains only dataset names, "benchmark", "evaluation", "survey"
- "No theory": Abstract lacks math notation, theorems, proofs, or theoretical analysis

### Novelty Indicators

Look for signals of significant contribution:
- "Novel", "new approach", "first time"
- Mathematical theorems or proofs mentioned
- Cross-field connections
- Solving open problems

**Bonus**: +1 point for strong novelty signals

---

## Data Files

### Input Files

**resources/current/filtered_papers.json** (quick-scorer input):
```json
[
  {
    "arxiv_id": "2501.12345",
    "title": "Paper Title",
    "authors": ["Author 1", "Author 2"],
    "categories": ["cs.LG", "stat.ML"],
    "abstract": "Full abstract text...",
    "published": "2026-02-03",
    "pdf_url": "https://arxiv.org/pdf/2501.12345"
  },
  ...
]
```

**resources/papers/** (deep-reviewer input):
Full text papers in `TXT` format.


### Output Files

**resources/current/scored_papers_summary.json** (quick-scorer output):
- Top 25-30 papers with scores
- Brief reasons (1 sentence)

**resources/current/digest_YYYY-MM-DD.json** (deep-reviewer output):
- Final 5-6 papers with deep analysis
- Summaries, relevance, key insights

---

## Workflow Examples

### Quick Scorer Workflow
1. Load preferences and papers
2. Process in batches
3. Filter top papers
4. Save results

### Deep Reviewer Workflow
1. Load preferences
2. Deep analysis 
 * Read one paper at a time. **WAIT 1 minute before proceeding to the next one**
 * Do a deep analysis of the paper
 * See how it relates to the users' interests
 * If necessary, take notes in `memory/deep-reviewer-notes.txt`
3. Select the best top papers by how well they align with users' interests
4. Save digest

---

## Quality Checks

### Quick Scorer

✓ Processed all input papers
✓ Selected 20-30 papers (not too narrow or broad)
✓ Scores are distributed (not all 9-10)
✓ Brief reasons provided for each
✓ Completed in <5 minutes

### Deep Reviewer

✓ Analyzed all top 25 papers
✓ Selected 5-6 diverse papers
✓ Summaries are substantive (2-3 paragraphs)
✓ Relevance connects to user's specific interests
✓ Key insights are actionable
✓ Papers span different themes (not all on same narrow topic)
✓ Completed in <15 minutes

---

## Error Handling

**Missing preferences file**:
Write the following message in the file `error.txt`: "Warning: No preferences file found, using defaults".

---

## References

For detailed scoring algorithms and helper functions, see:
- `skills/score-papers/references/scoring_algorithm.md` - Detailed scoring formulas, to be used as references *only*.

---
