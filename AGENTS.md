# Research Assistant System - Agent Coordination

This folder is home. Treat it that way.

## System Overview

This workspace supports an automated arXiv paper curation system with two specialized agents that work together to deliver a personalized daily research digest.

## Agents in This System

### quick-scorer (Gemini Flash)
- **Role**: High-throughput relevance filter
- **Task**: Process ~150 papers/day, identify top 25
- **Trigger**: Cron job at 6:30 AM daily
- **Input**: `resources/current/filtered_papers.json`
- **Output**: `resources/current/scored_papers_summary.json`
- **Session**: `cron:quick-score`

### deep-reviewer (Gemini Pro)  
- **Role**: Expert scholarly analyst
- **Task**: Deep analysis of top 25, select final 5-6
- **Trigger**: Cron job at 7:00 AM daily (after quick-scorer)
- **Input**: `resources/current/scored_papers_summary.json` + `resources/papers`
- **Output**: `resources/current/digest_YYYY-MM-DD.json`
- **Session**: `cron:deep-review`

## Workflow Sequence
```
[6:00 AM] System scripts fetch and prefilter papers
    ↓
[6:30 AM] quick-scorer: Bulk scoring (150 → 25 papers)
    ↓
[7:00 AM] deep-reviewer: Deep analysis (25 → 5-6 papers)
    ↓
[7:30 AM] System formats and delivers digest via Discord
```

## Shared Resources

Both agents access:
- `user_preferences.json` - Research interests and scoring criteria
- `skills/score-papers/` - Shared scoring methodology
- Session data stored separately per agent

## Coordination Principles

1. **Sequential execution**: deep-reviewer waits for quick-scorer completion
2. **Shared preferences**: Both read from same `user_preferences.json`
3. **Isolated sessions**: Each agent maintains separate conversation history
4. **No direct communication**: Agents coordinate via JSON files, not messages
