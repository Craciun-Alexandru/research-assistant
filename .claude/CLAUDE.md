# arXiv Digest Pipeline

Automated daily arXiv paper curation system. Fetches papers, pre-filters by keywords, scores and reviews via LLM, downloads full texts, generates digest, delivers via email.

For internal design details, see [ARCHITECTURE.md](../ARCHITECTURE.md).

## Stack

- Python 3.10+, no frameworks
- Dependencies: requests, google-genai, anthropic
- Linting/formatting: ruff
- Package: `src/arxiv_digest/` (PEP 621, pyproject.toml)
- Install for dev: `pip install -e ".[dev]" --break-system-packages`

## Key Commands

```
make lint          # ruff check + format
make test          # pytest tests/
make pipeline      # full daily pipeline (fetch → deliver)
make install       # pip install -e ".[dev]"
```

## Project Layout

```
pipeline/
  src/arxiv_digest/     # Python package — all pipeline logic lives here
    config.py           # ALL paths and constants. Never hardcode workspace paths elsewhere.
    llm/                # LLM client abstraction (Gemini + Claude backends)
    onboard.py          # Interactive preference wizard (python -m arxiv_digest.onboard)
  tests/                # pytest
scripts/              # Thin shell wrappers for cron jobs (call python -m arxiv_digest.*)
resources/            # Data directory (papers, digests, JSON intermediates)
```

## Code Conventions

- All filesystem paths go through `arxiv_digest.config` — no `Path.home()` or hardcoded paths in modules
- Scripts in `scripts/` are thin wrappers: set up env, call `python -m arxiv_digest.<module>`
- Type hints on all function signatures
- Docstrings on public functions (Google style)
- f-strings for formatting, pathlib for paths
- Error handling: log and continue for per-paper failures, exit nonzero for pipeline-level failures

## Pipeline Flow

```
fetch_papers (arXiv API) → prefilter (keyword/category match)
  → extract_latex (LaTeX metadata)
  → scorer (LLM — configurable: Gemini Flash or Claude Haiku)
  → download (LaTeX source → body TXT, appendices stripped)
  → reviewer (LLM — configurable: Gemini Pro or Claude Sonnet)
  → digest (JSON→Markdown+HTML) → deliver (email)

Run entire pipeline: python -m arxiv_digest
```

## Workspace Path

`config.py` resolves `WORKSPACE_ROOT` relative to the project root directory (via `Path(__file__)`). Override with the `ARXIV_DIGEST_WORKSPACE` env var for alternate deployments. All other paths derive from it.
