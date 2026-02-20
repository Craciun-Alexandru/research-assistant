# LaTeX Metadata Extraction

Enriches `filtered_papers.json` with structured metadata parsed from arXiv LaTeX sources. Runs between prefilter and scorer in the pipeline.

## What It Does

For each paper in `filtered_papers.json`:

1. Downloads the LaTeX source bundle from `https://arxiv.org/e-print/{arxiv_id}`
2. Extracts the archive (tar.gz, gzip, or plain text)
3. Finds the main `.tex` file (looks for `\documentclass`)
4. Parses structured fields: title, authors, keywords, abstract, introduction
5. Adds a `latex_metadata` dict to the paper entry

The scorer then uses the extracted keywords and introduction text for improved keyword matching (+1.0 for LaTeX keyword matches, +0.25 for introduction matches).

## Usage

### As part of the full pipeline

```bash
python -m arxiv_digest   # runs all 8 steps including extract_latex
```

### Standalone

```bash
python -m arxiv_digest.extract_latex
```

Requires `filtered_papers.json` to exist in `resources/current/`.

## Example Output

Each paper gets a `latex_metadata` field added:

```json
{
  "arxiv_id": "2602.12345",
  "title": "On Diffusion Models",
  "latex_metadata": {
    "title": "On Diffusion Models for Non-Convex Optimization",
    "authors": ["Alice Smith", "Bob Jones"],
    "keywords": ["diffusion models", "non-convex optimization", "convergence"],
    "abstract": "We study convergence properties...",
    "introduction": "Diffusion models have recently emerged as a powerful framework..."
  }
}
```

## Edge Cases

- **No LaTeX source available** (e.g., PDF-only submissions): paper is skipped, no `latex_metadata` added
- **Single-file submissions**: handled as plain gzip or plain text
- **Multi-file projects with `\input{}`/`\include{}`**: recursively expanded up to depth 10
- **No keywords in source**: `keywords` list will be empty; the scorer gracefully handles this
- **Very long introductions**: truncated to 2000 characters
- **Path traversal in tar archives**: members with `..` or absolute paths are filtered out

## Dependencies

No new dependencies — uses only stdlib (`tarfile`, `gzip`, `tempfile`, `io`, `re`, `shutil`) plus `requests` (already installed).
