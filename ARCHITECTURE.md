# ARCHITECTURE.md - Project ARCHITECTURE
The purpose of this document is to provide an overview of the architecture of the project, including its components, their interactions, and the overall design principles. It is structured as follows:
1. File Structure
2. Data Flow
3. Key Design Decisions
4. Extension Points
5. Conventions

## 1. File structure
The project is organized into the following directories and files:
```
.
├── AGENTS.md
├── ARCHITECTURE.md
├── HEARTBEAT.md
├── IDENTITY.md
├── memory
├── pipeline
│   ├── pyproject.toml
│   └── src
│       └── arxiv_digest            # Python package — all pipeline logic
│           ├── __init__.py
│           ├── config.py           # Paths, constants, setup_daily_run(), load_llm_config()
│           ├── fetch.py            # arXiv API fetch (calls setup_daily_run)
│           ├── prefilter.py        # Keyword/category pre-filter
│           ├── scorer.py           # Quick-scorer: deterministic + LLM hybrid scoring
│           ├── download.py         # HTML-first paper downloader
│           ├── reviewer.py         # Deep reviewer: full-text LLM analysis
│           ├── digest.py           # JSON → Markdown formatter
│           ├── deliver.py          # Discord delivery
│           └── llm/                # LLM client abstraction
│               ├── __init__.py     # create_client() factory
│               ├── base.py         # Abstract LLMClient, exceptions
│               └── gemini.py       # GeminiClient (google-genai SDK)
├── resources
│   ├── YYYY-MM-DD                  # Per-day run directory (created by setup_daily_run)
│   │   ├── daily_papers.json
│   │   ├── filtered_papers.json
│   │   ├── scored_papers_summary.json
│   │   ├── digest_YYYY-MM-DD.json
│   │   └── digest_YYYY-MM-DD.md
│   ├── current -> YYYY-MM-DD      # Symlink to today's run
│   ├── digests
│   └── papers
│       ├── YYMM.XXXXXv1.txt
│       └── download_metadata.json
├── scripts                         # Thin shell wrappers (call python -m arxiv_digest.*)
│   ├── fetch_prefilter.sh
│   ├── score_papers.sh
│   ├── review_papers.sh
│   └── digest_deliver.sh
├── skills
│   ├── preference-updater
│   │   ├── scripts
│   │   │   └── update_preferences.py
│   │   └── SKILL.md
│   ├── preference-wizard
│   │   ├── scripts
│   │   │   └── save_preferences.py
│   │   └── SKILL.md
│   └── score-papers
│       ├── references
│       │   └── scoring_algorithm.md
│       └── SKILL.md
├── SOUL.md
├── SPEC.md
├── TOOLS.md
├── USER.md
└── user_preferences.json
```

## 2. Data Flow

The pipeline runs daily as a sequence of Python steps. Each step reads from and writes to the current day's run directory (`resources/current/`), except for downloaded paper texts which accumulate in `resources/papers/`.

```
┌──────────────────────────────────────────────────────────────────┐
│  Step 1 — fetch.py                                               │
│    • Calls setup_daily_run(): creates resources/YYYY-MM-DD/,     │
│      updates resources/current symlink                           │
│    • Reads categories from user_preferences.json (or --categories)│
│    • Queries arXiv API per category, deduplicates results        │
│    → resources/current/daily_papers.json  (~150–1000 papers)     │
│                                                                  │
│  Step 2 — prefilter.py                                           │
│    • Reads daily_papers.json + user_preferences.json             │
│    • Scores by category overlap and keyword match                │
│    • Applies avoidance filters (benchmarks, engineering-only)    │
│    → resources/current/filtered_papers.json  (~50 papers)        │
│                                                                  │
│  Step 3 — scorer.py  (Gemini Flash)                              │
│    • Reads filtered_papers.json + user_preferences.json          │
│    • Deterministic scoring: category, keyword, novelty, avoidance│
│    • LLM-based interest scoring (batched, 15–20 papers per call) │
│    • Combines scores, selects top 25–30 (score ≥ 7)             │
│    → resources/current/scored_papers_summary.json  (~25 papers)  │
│                                                                  │
│  Step 4 — download.py                                            │
│    • Reads scored_papers_summary.json                             │
│    • Downloads each paper: tries HTML first, falls back to PDF   │
│    • Extracts text to .txt, deletes intermediate HTML/PDF        │
│    → resources/papers/{arxiv_id}.txt                             │
│    → resources/papers/download_metadata.json                     │
│                                                                  │
│  Step 5 — reviewer.py  (Gemini Pro)                              │
│    • Reads scored_papers_summary.json + paper full texts          │
│    • Deep scholarly analysis per paper (60s delay between calls)  │
│    • LLM selects final 5–6 diverse papers for digest             │
│    → resources/current/digest_YYYY-MM-DD.json                    │
│                                                                  │
│  Step 6 — digest.py                                              │
│    • Reads digest JSON, renders Markdown from templates          │
│    → resources/current/digest_YYYY-MM-DD.md                      │
│                                                                  │
│  Step 7 — deliver.py                                             │
│    • Reads digest Markdown                                       │
│    • Splits into ≤1900-char chunks on --- delimiters             │
│    • Sends via `openclaw message send` to Discord DM             │
└──────────────────────────────────────────────────────────────────┘
```

### Intermediate JSON formats

| File | Producer | Consumer | Schema (top-level keys) |
|------|----------|----------|------------------------|
| `daily_papers.json` | fetch | prefilter | `[{arxiv_id, title, authors, abstract, categories, published, pdf_url}]` |
| `filtered_papers.json` | prefilter | scorer | Same schema, fewer papers |
| `scored_papers_summary.json` | scorer | download, reviewer | `{scored_papers_summary: [{arxiv_id, title, score, reason, ...}], total_processed, selected_count, scoring_mode}` |
| `digest_YYYY-MM-DD.json` | reviewer | digest | `{digest_date, summary, total_reviewed, selected_count, scoring_mode, papers: [{title, arxiv_id, score, summary, relevance, key_insight, ...}]}` |
| `digest_YYYY-MM-DD.md` | digest | deliver | Markdown text |
| `download_metadata.json` | download | (diagnostics) | `{download_date, statistics, papers: [{arxiv_id, status, format, ...}]}` |

## 3. Key Design Decisions

### Daily run isolation
Each pipeline run writes to its own `resources/YYYY-MM-DD/` directory. A `resources/current` symlink always points to today's directory. This means:
- Previous days' results are preserved for debugging and comparison.
- All modules resolve data paths through `config.CURRENT_RUN_DIR`, so they always read/write the active run without hardcoded dates.
- The symlink is updated atomically (create temp symlink, then `rename`) to avoid races if a module reads while fetch is starting.

### Centralized configuration
`config.py` is the single source of truth for all filesystem paths, API constants, and default values. No module constructs workspace paths on its own. This makes it possible to relocate the workspace (via the `ARXIV_DIGEST_WORKSPACE` env var) or change file layouts without editing multiple modules.

### LLM client abstraction
The `llm/` package provides an abstract `LLMClient` base class with a `complete_json()` method for structured output. `GeminiClient` is the current implementation using the `google-genai` SDK. The factory function `create_client(provider, ...)` allows swapping providers without touching scorer or reviewer code. LLM configuration (provider, models, API key) is stored in `user_preferences.json` under the `llm` key and loaded via `config.load_llm_config()`.

### Thin wrapper scripts
Scripts in `scripts/` are shell wrappers that activate the venv and call `python -m arxiv_digest.<module>`, forwarding CLI arguments. All logic lives in the `arxiv_digest` package. This keeps the scripts trivially maintainable and ensures the package is the canonical code.

### HTML-first download strategy
The download module tries arXiv's HTML endpoint before falling back to PDF. HTML (available for papers submitted after Dec 2023) produces cleaner extracted text than PDF. Both intermediate formats are deleted after text extraction, keeping only `.txt` files in `resources/papers/`.

### Two-tier LLM scoring
Scoring is split into two Python modules:
- **scorer.py** (Gemini Flash): Hybrid deterministic + LLM scoring. Category, keyword, novelty, and avoidance scores are computed deterministically (fast, free). Only interest alignment uses the LLM, batched 15–20 papers per call to minimize API cost. Reduces ~50 papers to ~25.
- **reviewer.py** (Gemini Pro): Full-text deep analysis with structured JSON output per paper, followed by a diversity-aware selection prompt. 60s delay between papers to respect rate limits. Reduces ~25 papers to 5–6.

### Categories from preferences
`fetch.py` reads arXiv categories from the `research_areas` keys in `user_preferences.json` by default. This eliminates hardcoded category lists and ensures fetch, prefilter, and scorer all use the same category set. Categories can still be overridden via `--categories` CLI flag.

## 4. Extension Points

### Adding arXiv categories
Add category codes to the `research_areas` object in `user_preferences.json`. No other changes needed — fetch, prefilter, and scorer read categories from preferences at runtime.

### Swapping LLM providers
Implement a new `LLMClient` subclass in `llm/` (e.g., `openai.py`), register it in `llm/__init__.py`'s `create_client()`, and set `"provider": "openai"` in `user_preferences.json`. Scorer and reviewer need no changes.

### Adjusting scoring logic
Deterministic scoring functions are in `scorer.py` (`calculate_category_score`, `calculate_keyword_score`, `calculate_novelty_bonus`, `calculate_avoidance_penalty`). The interest scoring prompt is in `_build_interest_prompt()`. The reference algorithm is documented in `skills/score-papers/references/scoring_algorithm.md`.

### Adding delivery channels
`deliver.py` currently sends to Discord via the `openclaw message send` CLI. To add another channel (email, Slack, etc.), add a new delivery function alongside `send_discord_message` and a new `--method` choice.

### Custom prefilter rules
`prefilter.py` supports avoidance filters via `user_preferences.json`'s `avoid` list. New filter types can be added to `apply_avoidance_filters()` by matching on additional keyword patterns.

## 5. Conventions

### Code style
- Python 3.12+, no frameworks. Dependencies: `requests`, `beautifulsoup4`, `PyMuPDF`, `google-genai`.
- Linting and formatting: `ruff` (config in `pyproject.toml`). Run via `make lint`.
- Type hints on all function signatures. Google-style docstrings on public functions.
- f-strings for formatting, `pathlib.Path` for all file operations.

### Path management
- All filesystem paths are defined in `config.py` and imported by other modules.
- Per-run data (daily papers, filtered papers, scored papers, digests) goes in `resources/current/` (which symlinks to `resources/YYYY-MM-DD/`).
- Persistent data (downloaded paper texts, download metadata) goes in `resources/papers/`.
- Never use `Path.home()` or hardcoded absolute paths outside of `config.py`.

### Error handling
- Per-paper failures (download errors, parse errors, LLM errors) are logged and skipped — the pipeline continues with remaining papers.
- Pipeline-level failures (missing input files, no papers found) cause a nonzero exit.
- LLM calls retry with exponential backoff on 429/5xx errors (max 3 attempts).

### Do not touch
The following root-level files are OpenClaw agent configuration, read by Gemini agents at runtime. Do not refactor, move, rename, or restructure them:
- `SOUL.md`, `IDENTITY.md`, `AGENTS.md`, `HEARTBEAT.md`, `TOOLS.md`, `USER.md`, `SPEC.md`
- `skills/` directory (OpenClaw skills, not Claude Code skills)
- `memory/` directory
- `user_preferences.json`
