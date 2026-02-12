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
│           ├── config.py           # Paths, constants, setup_daily_run()
│           ├── fetch.py            # arXiv API fetch (calls setup_daily_run)
│           ├── prefilter.py        # Keyword/category pre-filter
│           ├── download.py         # HTML-first paper downloader
│           ├── digest.py           # JSON → Markdown formatter
│           └── deliver.py          # Discord delivery
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
├── scripts                         # Thin wrappers (call python -m arxiv_digest.*)
│   ├── deliver_digest_markdown.py
│   ├── download_full_papers.py
│   ├── fetch_papers.py
│   ├── fetch_prefilter.sh
│   ├── make_digest_markdown.py
│   ├── prefilter_papers.py
│   └── process_deliver.sh
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

The pipeline runs daily as a sequence of Python steps and OpenClaw agent tasks. Each step reads from and writes to the current day's run directory (`resources/current/`), except for downloaded paper texts which accumulate in `resources/papers/`.

```
┌──────────────────────────────────────────────────────────────────┐
│  6:00 AM — Python scripts (cron)                                │
│                                                                  │
│  fetch.py                                                        │
│    • Calls setup_daily_run(): creates resources/YYYY-MM-DD/,     │
│      updates resources/current symlink                           │
│    • Queries arXiv API per category, deduplicates results        │
│    → resources/current/daily_papers.json  (~150–1000 papers)     │
│                                                                  │
│  prefilter.py                                                    │
│    • Reads daily_papers.json + user_preferences.json             │
│    • Scores by category overlap and keyword match                │
│    • Applies avoidance filters (benchmarks, engineering-only)    │
│    → resources/current/filtered_papers.json  (~50 papers)        │
├──────────────────────────────────────────────────────────────────┤
│  6:30 AM — OpenClaw agent: quick-scorer (Gemini Flash)           │
│                                                                  │
│    • Reads filtered_papers.json                                  │
│    • LLM-based relevance scoring against user preferences        │
│    → resources/current/scored_papers_summary.json  (~25 papers)  │
├──────────────────────────────────────────────────────────────────┤
│  Between scoring steps — Python script                           │
│                                                                  │
│  download.py                                                     │
│    • Reads scored_papers_summary.json                             │
│    • Downloads each paper: tries HTML first, falls back to PDF   │
│    • Extracts text to .txt, deletes intermediate HTML/PDF        │
│    → resources/papers/{arxiv_id}.txt                             │
│    → resources/papers/download_metadata.json                     │
├──────────────────────────────────────────────────────────────────┤
│  7:00 AM — OpenClaw agent: deep-reviewer (Gemini Pro)            │
│                                                                  │
│    • Reads scored_papers_summary.json + paper full texts          │
│    • Deep scholarly analysis, selects final 5–6 papers           │
│    → resources/current/digest_YYYY-MM-DD.json                    │
├──────────────────────────────────────────────────────────────────┤
│  7:30 AM — Python scripts (cron)                                 │
│                                                                  │
│  digest.py                                                       │
│    • Reads digest JSON, renders Markdown from templates          │
│    → resources/current/digest_YYYY-MM-DD.md                      │
│                                                                  │
│  deliver.py                                                      │
│    • Reads digest Markdown                                       │
│    • Splits into ≤1900-char chunks on --- delimiters             │
│    • Sends via `openclaw message send` to Discord DM             │
└──────────────────────────────────────────────────────────────────┘
```

### Intermediate JSON formats

| File | Producer | Consumer | Schema (top-level keys) |
|------|----------|----------|------------------------|
| `daily_papers.json` | fetch | prefilter | `[{arxiv_id, title, authors, abstract, categories, published, pdf_url}]` |
| `filtered_papers.json` | prefilter | quick-scorer | Same schema, fewer papers |
| `scored_papers_summary.json` | quick-scorer | download, deep-reviewer | `{scored_papers_summary: [{arxiv_id, title, score, ...}]}` |
| `digest_YYYY-MM-DD.json` | deep-reviewer | digest | `{digest_date, summary, total_reviewed, papers: [{title, arxiv_id, score, summary, relevance, ...}]}` |
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

### Thin wrapper scripts
Scripts in `scripts/` are one-liner wrappers that call `python -m arxiv_digest.<module>`, forwarding CLI arguments. All logic lives in the `arxiv_digest` package. This keeps the scripts trivially maintainable and ensures the package is the canonical code.

### HTML-first download strategy
The download module tries arXiv's HTML endpoint before falling back to PDF. HTML (available for papers submitted after Dec 2023) produces cleaner extracted text than PDF. Both intermediate formats are deleted after text extraction, keeping only `.txt` files in `resources/papers/`.

### Two-tier LLM scoring
Scoring is split between a fast, cheap model (Gemini Flash for bulk scoring ~150 → ~25) and a capable model (Gemini Pro for deep review ~25 → ~6). This balances cost and quality. Both agents are managed by OpenClaw, not by this Python pipeline.

### Separation of Python pipeline and OpenClaw agents
Python handles deterministic, I/O-heavy work (API calls, parsing, downloading, formatting). LLM-powered scoring and analysis are delegated to OpenClaw agents that run on their own cron schedule. The two systems coordinate exclusively through JSON files in the daily run directory — no direct inter-process communication.

## 4. Extension Points

### Adding arXiv categories
Add category codes to `DEFAULT_CATEGORIES` in `config.py` and to the `research_areas` object in `user_preferences.json`. No other changes needed — fetch and prefilter read categories from preferences at runtime.

### Changing the scoring pipeline
The quick-scorer and deep-reviewer are OpenClaw skills defined in `skills/score-papers/`. Modify `SKILL.md` and `scoring_algorithm.md` to change prompts or scoring rubrics. The Python pipeline is unaffected as long as the JSON output schemas stay the same.

### Adding delivery channels
`deliver.py` currently sends to Discord via the `openclaw message send` CLI. To add another channel (email, Slack, etc.), add a new delivery function alongside `send_discord_message` and a new `--method` choice.

### Custom prefilter rules
`prefilter.py` supports avoidance filters via `user_preferences.json`'s `avoid` list. New filter types can be added to `apply_avoidance_filters()` by matching on additional keyword patterns.

### Adjusting daily run timing
The cron schedule is external to this codebase. Adjust the crontab entries for fetch/prefilter (6:00 AM), quick-scorer (6:30 AM), download (between scoring steps), deep-reviewer (7:00 AM), and digest/deliver (7:30 AM).

## 5. Conventions

### Code style
- Python 3.12+, no frameworks. Dependencies: `requests`, `beautifulsoup4`, `PyMuPDF`.
- Linting and formatting: `ruff` (config in `pyproject.toml`). Run via `make lint`.
- Type hints on all function signatures. Google-style docstrings on public functions.
- f-strings for formatting, `pathlib.Path` for all file operations.

### Path management
- All filesystem paths are defined in `config.py` and imported by other modules.
- Per-run data (daily papers, filtered papers, scored papers, digests) goes in `resources/current/` (which symlinks to `resources/YYYY-MM-DD/`).
- Persistent data (downloaded paper texts, download metadata) goes in `resources/papers/`.
- Never use `Path.home()` or hardcoded absolute paths outside of `config.py`.

### Error handling
- Per-paper failures (download errors, parse errors) are logged and skipped — the pipeline continues with remaining papers.
- Pipeline-level failures (missing input files, no papers found) cause a nonzero exit.

### Do not touch
The following root-level files are OpenClaw agent configuration, read by Gemini agents at runtime. Do not refactor, move, rename, or restructure them:
- `SOUL.md`, `IDENTITY.md`, `AGENTS.md`, `HEARTBEAT.md`, `TOOLS.md`, `USER.md`, `SPEC.md`
- `skills/` directory (OpenClaw skills, not Claude Code skills)
- `memory/` directory
- `user_preferences.json`
