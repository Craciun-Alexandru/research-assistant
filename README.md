# arXiv Research Digest

Automated daily pipeline that fetches papers from arXiv, scores them against your research interests using a mix of deterministic heuristics and Gemini LLM calls, downloads full texts, produces deep scholarly reviews, and delivers a curated digest of 5-6 papers to Discord.

## How It Works

Every day the pipeline runs 7 steps:

```
fetch → prefilter → score → download → review → digest → deliver
```

1. **Fetch** — Queries the arXiv API for your research categories (read from `user_preferences.json`)
2. **Prefilter** — Keyword/category matching reduces ~150 papers to ~50
3. **Score** — Hybrid scoring: deterministic (category, keyword, novelty, avoidance) + LLM-based interest alignment via Gemini Flash. Selects top ~25-30
4. **Download** — Retrieves full paper text (HTML preferred, PDF fallback) and extracts to plain text
5. **Review** — Deep scholarly analysis of each paper using Gemini Pro. Selects a diverse final set of 5-6 papers
6. **Digest** — Converts the review JSON into formatted Markdown
7. **Deliver** — Sends the digest to Discord, split into message-sized chunks

## Quick Start

```bash
git clone https://github.com/Craciun-Alexandru/research-assistant.git
cd research-assistant
./setup.sh
```

The setup script handles everything:
- Creates a Python virtual environment and installs dependencies
- Prompts for your Gemini API key and verifies it
- Creates resource directories
- Optionally installs cron jobs for daily automated runs

### Prerequisites

- Python 3.10+
- A [Gemini API key](https://aistudio.google.com/apikey) (free tier works)
- [OpenClaw CLI](https://github.com/openclaw) (only needed for Discord delivery)

## Manual Pipeline Run

After setup, you can run the full pipeline manually:

```bash
cd pipeline
. .venv/bin/activate

python -m arxiv_digest.fetch
python -m arxiv_digest.prefilter
python -m arxiv_digest.scorer
python -m arxiv_digest.download
python -m arxiv_digest.reviewer --delay 5    # use --delay 60 in production
python -m arxiv_digest.digest
python -m arxiv_digest.deliver
```

Or use the shell wrapper scripts from anywhere:

```bash
scripts/fetch_prefilter.sh
scripts/score_papers.sh
scripts/download_papers.sh
scripts/review_papers.sh
scripts/digest_deliver.sh
```

## Cron Schedule

When installed via `setup.sh`, the daily pipeline runs automatically:

| Time  | Script                 | Step                              |
|-------|------------------------|-----------------------------------|
| 07:00 | `fetch_prefilter.sh`   | Fetch from arXiv + keyword filter |
| 07:05 | `score_papers.sh`      | LLM hybrid scoring (Gemini Flash) |
| 07:10 | `download_papers.sh`   | Download full paper texts         |
| 07:20 | `review_papers.sh`     | Deep review (Gemini Pro)          |
| 07:59 | `digest_deliver.sh`    | Format Markdown + send to Discord |

Logs are appended to `~/cron_digest.log`.

## Configuration

All user configuration lives in `user_preferences.json`:

### Research Areas

```json
{
  "research_areas": {
    "cs.LG": { "weight": 1.0, "keywords": ["algebraic geometry in deep learning", ...] },
    "math.AG": { "weight": 0.95, "keywords": ["neuroalgebraic geometry", ...] }
  }
}
```

- **Keys** are arXiv category codes — these are the categories fetched daily
- **weight** (0-1) controls scoring priority
- **keywords** are matched against paper titles and abstracts

### Interests and Avoidances

```json
{
  "interests": [
    "invariant and equivariant neural networks",
    "edge of stability"
  ],
  "avoid": [
    "Purely empirical benchmarks without theory",
    "Engineering-focused architecture tweaks"
  ]
}
```

- **interests** are sent to the LLM for semantic interest-alignment scoring
- **avoid** criteria trigger deterministic penalty scores

### LLM Settings

```json
{
  "llm": {
    "provider": "gemini",
    "scorer_model": "gemini-2.0-flash",
    "reviewer_model": "gemini-2.5-pro",
    "api_key": "your-api-key"
  }
}
```

## Project Structure

```
.
├── setup.sh                          # One-time setup script
├── pipeline/
│   ├── pyproject.toml
│   └── src/arxiv_digest/             # Python package — all pipeline logic
│       ├── config.py                 # Paths, constants, load_llm_config()
│       ├── fetch.py                  # arXiv API fetch
│       ├── prefilter.py              # Keyword/category pre-filter
│       ├── scorer.py                 # Quick-scorer (deterministic + LLM)
│       ├── download.py               # HTML/PDF downloader + text extraction
│       ├── reviewer.py               # Deep reviewer (full-text LLM analysis)
│       ├── digest.py                 # JSON → Markdown formatter
│       ├── deliver.py                # Discord delivery
│       └── llm/                      # LLM client abstraction
│           ├── base.py               # Abstract LLMClient, exceptions
│           └── gemini.py             # Gemini implementation (google-genai)
├── scripts/                          # Thin shell wrappers for cron
├── resources/                        # Data directory (gitignored)
│   ├── current -> YYYY-MM-DD/        # Symlink to today's run
│   ├── YYYY-MM-DD/                   # Per-day pipeline outputs
│   └── papers/                       # Downloaded full-text files
├── skills/                           # OpenClaw agent skill definitions
└── user_preferences.json             # Your research profile + LLM config
```

### Data Flow

Each daily run creates a `resources/YYYY-MM-DD/` directory with a `current` symlink. Intermediate files:

| File | Producer | Consumer |
|------|----------|----------|
| `daily_papers.json` | fetch | prefilter |
| `filtered_papers.json` | prefilter | scorer |
| `scored_papers_summary.json` | scorer | download, reviewer |
| `digest_YYYY-MM-DD.json` | reviewer | digest |
| `digest_YYYY-MM-DD.md` | digest | deliver |

## Scoring Algorithm

The scorer uses a hybrid approach to minimize API costs:

**Deterministic (no LLM, instant):**
- **Category score** (0-5): Primary category = 5 x weight, secondary = 2.5 x weight
- **Keyword score** (0-3): Title match +2, abstract match +0.5 per keyword
- **Novelty bonus** (0-1): Awarded if 2+ indicator words found (novel, theorem, proof, etc.)
- **Avoidance penalty** (0-3): Benchmark/engineering papers without theory

**LLM-based (Gemini Flash, batched):**
- **Interest score** (0-2): Semantic alignment with user's stated research interests. Papers are sent in batches of 15-20 to minimize API calls.

**Total** = category + keyword + interest + novelty - avoidance

Papers scoring >= 7 (top 25-30) advance to download and deep review.

## Development

```bash
cd pipeline
. .venv/bin/activate

make lint       # ruff check + format
make test       # pytest
make install    # pip install -e ".[dev]"
```

## License

MIT
