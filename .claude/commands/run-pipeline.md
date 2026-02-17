---
description: Run the full arXiv digest pipeline (fetch → prefilter → download → format → deliver)
allowed-tools: Bash(python:*), Bash(make:*)
---

# /run-pipeline

Run the complete daily arXiv digest pipeline step by step.

**NOTE**: This runs only the Python-managed steps. The Gemini agent steps (quick-scorer, deep-reviewer) are triggered separately via OpenClaw cron.

## Steps

1. Fetch papers from arXiv API
2. Pre-filter by keywords and categories
3. Download full paper texts (after quick-scorer has run)
4. Generate markdown digest (after deep-reviewer has run)
5. Deliver via Discord

## Usage

Run all Python steps in sequence:
```bash
make pipeline
```

Or run individual steps:
```bash
python -m arxiv_digest.fetch
python -m arxiv_digest.prefilter
python -m arxiv_digest.download
python -m arxiv_digest.digest
python -m arxiv_digest.deliver
```

If a step fails, report the error and stop — do not continue to the next step.
