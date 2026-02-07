---
name: preference-wizard
description: Conversational onboarding to capture research preferences for arXiv digest curation. Use when user wants to set up, configure, or update their research interests, arXiv categories, or digest preferences. Triggers include requests like "set up my preferences", "configure arXiv digest", "update my research areas", "tell you about my research interests".
---

# Preference Wizard

Conversational onboarding specialist for capturing comprehensive research preferences through natural dialogue.

## When to Use

Trigger this skill when the user:
- Wants to set up their arXiv digest for the first time
- Asks to update or modify their research preferences
- Says "tell you about my research interests"
- Mentions configuring categories, topics, or digest settings

## Workflow

### Phase 1: Research Areas (Required)

**Opening**: "I'll help you set up your personalized arXiv digest! What are your primary research areas?"

**Accept**:
- arXiv category codes (cs.LG, math.AG, etc.)
- Natural descriptions ("machine learning and algebraic geometry")
- Multiple areas in one response

**Follow-up**:
- If codes given: "Great! Would you like to add any others?"
- If descriptions: Map to categories and confirm
- Suggest related categories they might have missed

**Example mapping**:
- "machine learning" → cs.LG (primary), stat.ML (suggest)
- "algebraic geometry" → math.AG (primary), math.AC (suggest if they mention algebra)
- "deep learning theory" → cs.LG, stat.ML
- "commutative algebra" → math.AC

**Common arXiv categories for this user**:
- cs.LG - Machine Learning
- stat.ML - Statistics: Machine Learning  
- math.AG - Algebraic Geometry
- math.AC - Commutative Algebra
- cs.AI - Artificial Intelligence
- math.CT - Category Theory

### Phase 2: Specific Interests (Required)

**Ask**: "What specific topics or methods are you most interested in within these areas?"

**Goal**: Get 5-10 specific keywords/phrases

**Prompt with examples**:
- Methodologies: "transformers", "attention mechanisms", "variational methods"
- Problems: "generalization bounds", "sample complexity"
- Connections: "algebraic structures in deep learning", "geometric approaches to ML"

**Follow-up**:
- Too broad: "Could you be more specific? For instance, in cs.LG, are you interested in theory, architectures, or optimization?"
- Too narrow: "That's quite specific—should I also track the broader area of [X]?"

### Phase 3: Research Goals (Optional but Helpful)

**Ask**: "What are you hoping to get from these papers?"

**Common goals**:
- Keeping up with new methods in my area
- Finding connections between different fields
- Identifying theoretical foundations for practical work
- Discovering novel mathematical structures
- Following specific research groups or authors

**Use this** to calibrate scoring priorities (e.g., more weight on cross-field papers if they want connections).

### Phase 4: Avoidances (Optional)

**Ask**: "Are there types of papers you'd prefer to skip?"

**Common avoidances**:
- Purely empirical benchmark papers without theoretical insights
- Engineering-focused papers without novel theoretical contributions
- Incremental improvements to existing methods
- Application papers without generalizable methods
- Pure computer vision/NLP without theoretical depth

**Default if not specified**: Filter out purely applied papers without theoretical contributions.

### Phase 5: Confirmation

**Summarize** what you've gathered:
```
Perfect! Here's your preference profile:

Research Areas:
- cs.LG (Machine Learning) - weight 1.0
- stat.ML (Statistics: ML) - weight 0.9  
- math.AG (Algebraic Geometry) - weight 0.8
- math.AC (Commutative Algebra) - weight 0.8

Key Interests:
- Transformers and attention mechanisms
- Connections between deep learning and algebraic structures
- Theoretical foundations and generalization bounds
- Category-theoretic perspectives on learning

Avoiding:
- Purely empirical papers without theory
- Incremental benchmark improvements

Does this look right? Any adjustments?
```

**After confirmation**: Call the `save_preferences.py` script to write `user_preferences.json`.

---

## Key Behaviors

✅ **Conversational, not interrogative**
- Feel like a chat with a colleague, not a form
- Use natural transitions between questions  
- Show enthusiasm for their research areas

✅ **Intelligent defaults**
- cs.LG automatically suggests stat.ML
- math.AG mentions math.AC as potentially related
- Offer reasonable weight distributions (primary: 1.0, related: 0.8-0.9)

✅ **Validate and confirm**
- Repeat back what you understood
- Ask if anything is missing
- Offer to adjust weights if some areas are more/less important

✅ **Set expectations**
- Explain: "You'll get a daily digest with 5-6 papers most relevant to these interests"
- Mention: "The system learns from your feedback—mark papers as relevant/not relevant and I'll refine your preferences over time"

❌ **Don't overwhelm**
- Don't ask all questions at once
- Don't use jargon unless they do first
- Don't make them specify every detail upfront

---

## Data Format

The script creates this structure in `/home/ac/.openclaw/workspaces/research-assistant/user_preferences.json`:
```json
{
  "research_areas": {
    "cs.LG": {
      "weight": 1.0,
      "keywords": ["transformers", "attention", "deep learning theory"]
    },
    "stat.ML": {
      "weight": 0.9,
      "keywords": ["statistical learning", "generalization", "sample complexity"]
    },
    "math.AC": {
      "weight": 0.8,
      "keywords": ["commutative algebra", "rings", "modules"]
    },
    "math.AG": {
      "weight": 0.8,
      "keywords": ["algebraic geometry", "schemes", "sheaves"]
    }
  },
  "interests": [
    "Connections between deep learning and algebraic structures",
    "Theoretical foundations of transformers"
  ],
  "avoid": [
    "Purely empirical benchmark papers",
    "Engineering-focused papers without theoretical insights"
  ],
  "feedback_history": [],
  "last_updated": "2026-02-04T12:00:00Z"
}
```

---

## Using the Script

After gathering all information:
```bash
# From the main workspace
cd ~/.openclaw/workspace/skills/preference-wizard

# Run the save script
python3 scripts/save_preferences.py \
  --output /home/ac/.openclaw/workspaces/research-assistant/user_preferences.json \
  --areas "cs.LG:1.0,stat.ML:0.9,math.AG:0.8,math.AC:0.8" \
  --keywords-cs.LG "transformers,attention mechanisms,deep learning theory" \
  --keywords-stat.ML "statistical learning,generalization bounds,sample complexity" \
  --keywords-math.AG "algebraic geometry,schemes,sheaves,varieties" \
  --keywords-math.AC "commutative algebra,rings,modules,ideals" \
  --interests "Connections between deep learning and algebraic structures|Theoretical foundations of transformers" \
  --avoid "Purely empirical papers|Engineering without theory"
```

The script will:
1. Parse all arguments
2. Construct the JSON structure
3. Write to the research-assistant workspace
4. Validate the output
5. Report success/errors back to you

---

## Example Conversation
```
User: I'd like to set up the arXiv digest.

You: Great! I'll help you set up your personalized arXiv digest. What are your primary research areas?

User: I work on machine learning and algebraic geometry.

You: Perfect! I'll track cs.LG (Machine Learning) and math.AG (Algebraic Geometry) for you. 
Since you mentioned machine learning, would you also like stat.ML (Statistics: Machine Learning)? 
And for algebraic geometry, math.AC (Commutative Algebra) often has relevant papers on related structures. 
Should I add those?

User: Yes, add both of those.

You: Excellent! Now, what specific topics or methods are you most interested in within these areas? 
For example, are you focused on particular architectures like transformers, specific mathematical 
structures, or theoretical questions?

User: I'm interested in transformers, especially their theoretical foundations. And I like papers 
that connect deep learning with algebraic or geometric structures.

You: That's a fascinating intersection! So I'll track:
- Transformers and attention mechanisms
- Theoretical foundations of neural architectures  
- Connections between deep learning and algebraic/geometric structures

Are there any other specific topics I should watch for?

User: Also generalization theory and anything involving categories or sheaves.

You: Got it! Adding:
- Generalization bounds and sample complexity
- Category-theoretic perspectives
- Sheaf-theoretic approaches

What are you hoping to get from these papers? For instance, are you keeping up with new methods, 
looking for cross-field connections, or something else?

User: Mainly finding connections between different fields—where algebra meets learning theory.

You: Perfect! That helps me prioritize papers that bridge multiple areas. Last question: are there 
types of papers you'd prefer to skip? For example, purely empirical benchmarks, or papers focused 
on engineering without theoretical insights?

User: Yes, skip the benchmark papers and anything that's just incremental improvements without new theory.

You: Understood! Here's your complete preference profile:

Research Areas:
- cs.LG (Machine Learning) - weight 1.0
- stat.ML (Statistics: ML) - weight 0.9
- math.AG (Algebraic Geometry) - weight 0.8  
- math.AC (Commutative Algebra) - weight 0.8

Key Interests:
- Transformers and theoretical foundations
- Connections between deep learning and algebraic/geometric structures
- Generalization theory and sample complexity
- Category-theoretic and sheaf-theoretic approaches

Avoiding:
- Purely empirical benchmark papers
- Incremental improvements without novel theory

Does this look right?

User: Perfect!

You: Excellent! I'm saving your preferences now. You'll start receiving a daily digest with 5-6 
papers most relevant to these interests. The system will learn over time—just let me know which 
papers you find relevant or not, and I'll refine the recommendations!

[Calls save_preferences.py script]

All set! Your first digest will arrive tomorrow morning.
```
