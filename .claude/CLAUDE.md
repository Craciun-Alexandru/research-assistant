# arXiv Digest Pipeline

Automated daily arXiv paper curation system. Fetches papers, pre-filters by keywords, scores via Gemini agents (managed by OpenClaw), downloads full texts, generates digest, delivers via Discord.

## Stack

- Python 3.12+, no frameworks
- Dependencies: requests, beautifulsoup4, PyMuPDF (fitz)
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
src/arxiv_digest/     # Python package — all pipeline logic lives here
  config.py           # ALL paths and constants. Never hardcode workspace paths elsewhere.
scripts/              # Thin shell wrappers for cron jobs (call python -m arxiv_digest.*)
resources/            # Data directory (papers, digests, JSON intermediates)
skills/               # OpenClaw skills for Gemini agents — NOT Claude Code skills
tests/                # pytest
```

## CRITICAL: Do Not Touch

The following root-level files are **OpenClaw agent configuration** read by Gemini agents at runtime. Do NOT refactor, move, rename, or restructure them:
- SOUL.md, IDENTITY.md, AGENTS.md, HEARTBEAT.md, TOOLS.md, USER.md, SPEC.md, ARCHITECTURE.md
- `skills/` directory (OpenClaw skills, not Claude Code skills)
- `memory/` directory
- `user_preferences.json`

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
  → [Gemini quick-scorer via OpenClaw cron]
  → download (HTML→TXT, PDF→TXT fallback)
  → [Gemini deep-reviewer via OpenClaw cron]
  → digest (JSON→Markdown) → deliver (Discord via openclaw CLI)
```

Steps in brackets are OpenClaw agent tasks, not Python scripts.

## Workspace Path

This project lives at `~/.openclaw/workspaces/research-assistant/`. The `config.py` module resolves this as `WORKSPACE_ROOT` and all other paths derive from it.
