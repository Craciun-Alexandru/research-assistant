---
description: Run the full arXiv digest pipeline (fetch → prefilter → download → format → deliver)
allowed-tools: Bash(python:*), Bash(make:*)
---

# /run-pipeline

Run the complete daily arXiv digest pipeline step by step.

## Steps

1. Fetch papers from arXiv API
2. Pre-filter by keywords and categories
3. Score filtered papers (deterministic + LLM)
4. Download full paper texts
5. Deep-review selected papers (LLM)
6. Generate markdown digest
7. Deliver via email

## Usage

Run all steps in sequence:
```bash
python -m arxiv_digest
```

Or individually:
```bash
python -m arxiv_digest.fetch
python -m arxiv_digest.prefilter
python -m arxiv_digest.scorer
python -m arxiv_digest.download
python -m arxiv_digest.reviewer
python -m arxiv_digest.digest
python -m arxiv_digest.deliver
```

If a step fails, report the error and stop — do not continue to the next step.
