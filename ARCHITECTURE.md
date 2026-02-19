# Architecture

Internal design reference for contributors and Claude Code.

## Pipeline Overview

The pipeline runs 7 steps sequentially:

```
fetch → prefilter → scorer → download → reviewer → digest → deliver
```

| Step | Reads | Writes | Does |
|------|-------|--------|------|
| **fetch** | `user_preferences.json` | `daily_papers.json` | Queries arXiv API for configured categories and date range |
| **prefilter** | `daily_papers.json`, `user_preferences.json` | `filtered_papers.json` | Deterministic keyword/category/avoidance filtering (~150 → ~50 papers) |
| **scorer** | `filtered_papers.json`, `user_preferences.json` | `scored_papers_summary.json` | Hybrid deterministic + LLM scoring, selects top ~25–30 |
| **download** | `scored_papers_summary.json` | `resources/papers/<id>.txt` | Fetches full text (HTML preferred, PDF fallback) and extracts to plain text |
| **reviewer** | `scored_papers_summary.json`, paper texts | `digest_YYYY-MM-DD.json` | Deep scholarly analysis via LLM, selects final 5–6 papers |
| **digest** | `digest_YYYY-MM-DD.json` | `resources/digests/digest_YYYY-MM-DD.md` | Converts review JSON to formatted Markdown |
| **deliver** | `resources/digests/digest_YYYY-MM-DD.md` | *(Discord message)* | Sends digest to Discord via `openclaw message send` |

All intermediate JSON files live in `resources/current/` (a symlink to `resources/YYYY-MM-DD/`).

## Data Flow

Each daily run creates a `resources/YYYY-MM-DD/` directory and updates the `resources/current` symlink. Intermediate files and their producer → consumer chain:

| File | Location | Producer | Consumer |
|------|----------|----------|----------|
| `daily_papers.json` | `resources/current/` | fetch | prefilter |
| `filtered_papers.json` | `resources/current/` | prefilter | scorer |
| `scored_papers_summary.json` | `resources/current/` | scorer | download, reviewer |
| `digest_YYYY-MM-DD.json` | `resources/current/` | reviewer | digest |
| `digest_YYYY-MM-DD.md` | `resources/digests/` | digest | deliver |
| `<paper_id>.txt` | `resources/papers/` | download | reviewer |
| `download_metadata.json` | `resources/papers/` | download | download (cache) |

## Scoring Algorithm

The scorer uses a hybrid approach to minimise API costs:

**Deterministic (no LLM, instant):**
- **Category score** (0–5): Primary category = 5 × weight, secondary = 2.5 × weight
- **Keyword score** (0–3): Title match +2, abstract match +0.5 per keyword
- **Novelty bonus** (0–1): Awarded if 2+ indicator words found (novel, theorem, proof, etc.)
- **Avoidance penalty** (0–3): Benchmark/engineering papers without theory

**LLM-based (batched, fast model):**
- **Interest score** (0–2): Semantic alignment with user's stated research interests. Papers are sent in batches of 15–20 to minimise API calls.

**Total** = category + keyword + interest + novelty − avoidance

Papers scoring ≥ 7 (top 25–30) advance to download and deep review.

## LLM Abstraction Layer

The `llm/` package provides a provider-agnostic interface:

- **`LLMClient`** (abstract base in `llm/base.py`) — defines the contract
- **`GeminiClient`** (`llm/gemini.py`) — implementation using `google-genai`
- **`ClaudeClient`** (`llm/claude.py`) — implementation using `anthropic`
- **`create_client(provider, **kwargs)`** (`llm/__init__.py`) — factory function

Two abstract methods every provider must implement:

1. **`complete_json(prompt, schema, *, model=None) → dict`** — single-shot structured output. Used by scorer and reviewer for stateless batch processing.
2. **`chat(system_prompt, *, model=None) → ChatSession`** — multi-turn conversation. Used by the onboard wizard for interactive preference gathering.

`ChatSession` is also abstract, with a single `send(message) → str` method.

Both implementations include retry logic with exponential backoff for rate-limit (429) and server errors (500/503).

**Adding a new provider:** create `llm/<provider>.py` implementing `LLMClient` and `ChatSession`, then add a branch to `create_client()` in `llm/__init__.py`.

## Module Map

All pipeline logic lives in `pipeline/src/arxiv_digest/`:

| Module | Purpose |
|--------|---------|
| `config.py` | All paths and constants. `WORKSPACE_ROOT`, `load_llm_config()`, `setup_daily_run()`, `ensure_directories()`. No other module hardcodes paths. |
| `fetch.py` | Queries arXiv API by category and date range. Respects rate limits and deduplicates across categories. |
| `prefilter.py` | Deterministic keyword/category/avoidance filtering. No LLM calls. |
| `scorer.py` | Hybrid scoring: deterministic component + LLM interest-alignment scoring in batches. |
| `download.py` | HTML-first full-text retrieval (ar5iv) with PDF fallback (PyMuPDF). Extracts to plain text. Maintains `download_metadata.json` cache. |
| `reviewer.py` | Per-paper deep scholarly analysis via LLM. Selects a diverse final set of 5–6 papers. |
| `digest.py` | Converts review JSON into formatted Markdown. |
| `deliver.py` | Sends Markdown digest to Discord via `openclaw message send`, splitting into message-sized chunks. |
| `onboard.py` | Interactive preference wizard. Uses multi-turn LLM chat to build `user_preferences.json`. Run with `python -m arxiv_digest.onboard`. |
| `utils.py` | Shared helpers: JSON I/O (`load_json`, `save_json`), keyword extraction. |
| `llm/` | Provider abstraction — see [LLM Abstraction Layer](#llm-abstraction-layer). |
| `__main__.py` | Entry point for `python -m arxiv_digest`. Runs all 7 steps sequentially. |

## Design Decisions

**HTML-first download.** arXiv papers published after Dec 2023 have HTML versions (via ar5iv). HTML yields cleaner text extraction than PDF (no column-merging artefacts, intact math notation). PDF fallback handles older papers.

**Hybrid scoring.** Deterministic heuristics handle cheap bulk filtering (category match, keyword hits, avoidance penalties). The LLM is only called for semantic interest alignment on the already-filtered set — this minimises API costs while preserving personalisation quality.

**Timestamped daily directories with `current/` symlink.** Each day's outputs go to `resources/YYYY-MM-DD/`. The `current` symlink provides a stable path for scripts and config constants. The dated directories enable traceability and performance analysis of the recommendation system over time.

**Stateless LLM calls.** Scoring and reviewing use single-shot `complete_json()` — no conversation history. This is simpler, cheaper, and parallelisable. Multi-turn chat is only used by the onboard wizard, which genuinely needs conversational context.

## Directory Structure

```
.
├── setup.sh                          # One-time setup (venv, API keys, cron)
├── uninstall.sh                      # Remove cron jobs and venv
├── pipeline/
│   ├── pyproject.toml                # PEP 621 package config (requires-python >=3.10)
│   ├── Makefile                      # lint, test, install, pipeline targets
│   ├── src/arxiv_digest/             # Python package — all pipeline logic
│   │   ├── __init__.py
│   │   ├── __main__.py               # Entry point: python -m arxiv_digest
│   │   ├── config.py                 # Paths, constants, load_llm_config()
│   │   ├── fetch.py                  # arXiv API fetch
│   │   ├── prefilter.py              # Keyword/category pre-filter
│   │   ├── scorer.py                 # Hybrid scorer (deterministic + LLM)
│   │   ├── download.py               # HTML/PDF downloader + text extraction
│   │   ├── reviewer.py               # Deep reviewer (full-text LLM analysis)
│   │   ├── digest.py                 # JSON → Markdown formatter
│   │   ├── deliver.py                # Discord delivery via openclaw CLI
│   │   ├── onboard.py                # Interactive preference wizard
│   │   ├── utils.py                  # Shared helpers (JSON I/O, keywords)
│   │   └── llm/                      # LLM client abstraction
│   │       ├── __init__.py           # Factory: create_client()
│   │       ├── base.py               # Abstract LLMClient, ChatSession, exceptions
│   │       ├── gemini.py             # Gemini implementation (google-genai)
│   │       └── claude.py             # Claude implementation (anthropic)
│   └── tests/                        # pytest test suite
│       ├── conftest.py
│       ├── test_config.py
│       ├── test_deliver.py
│       ├── test_digest.py
│       ├── test_prefilter.py
│       └── test_scorer.py
├── scripts/                          # Thin shell wrappers for cron
│   ├── fetch_prefilter.sh
│   ├── score_papers.sh
│   ├── download_papers.sh
│   ├── review_papers.sh
│   └── digest_deliver.sh
├── resources/                        # Data directory (gitignored, created at runtime)
│   ├── current -> YYYY-MM-DD/        # Symlink to today's run
│   ├── YYYY-MM-DD/                   # Per-day pipeline outputs (JSON intermediates)
│   ├── papers/                       # Downloaded full-text files + metadata cache
│   └── digests/                      # Final Markdown digests
└── user_preferences.json             # Research profile + LLM config (gitignored)
```
