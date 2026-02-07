# Tool Usage Guidelines

## Available Tools for Research Agents

### File Operations
- `read`: Read JSON files (preferences, paper data)
- `write`: Write scored papers and digest outputs
- `bash_tool`: Execute Python scripts for data processing

### Restrictions
- **No web access**: Papers are pre-fetched by system scripts
- **No user interaction**: These are batch jobs, not conversational
- **No file creation outside workspace**: Stay in research-assistant directory

## Tool Usage Patterns

### quick-scorer
```python
# Read filtered papers
papers = json.load(open('resources/filtered_papers.json'))

# Score in batches (15-20 papers per API call)
# ... scoring logic ...

# Write results
json.dump(scored_papers, open('resources/scored_papers.json', 'w'))
```

### deep-reviewer
```python
# Read scored papers
papers = json.load(open('resources/scored_papers.json'))

# Analyze each paper deeply
# ... analysis logic ...

# Write digest
json.dump(digest, open(f'resources/digests/digest_{date}.json', 'w'))
```

## Error Handling
- Log errors but continue processing remaining papers
- If preferences file missing, use default weights
- If input file malformed, skip invalid entries
```
