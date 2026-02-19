# arXiv Research Digest

Automated daily pipeline that fetches papers from arXiv, scores them against your research interests, and delivers a curated digest to Discord.

## Quick Start

```bash
git clone https://github.com/Craciun-Alexandru/research-assistant.git
cd research-assistant
./setup.sh
```

The setup script handles everything: creates a virtual environment, installs dependencies, prompts for your API key(s), creates resource directories, and optionally installs cron jobs.

### Prerequisites

- Python 3.10+
- A [Gemini API key](https://aistudio.google.com/apikey) (free tier works) and/or an [Anthropic API key](https://console.anthropic.com/)
- [OpenClaw CLI](https://github.com/openclaw) *(optional — only needed for Discord delivery)*
- For email delivery: an SMTP-capable email account (Gmail with [App Password](https://myaccount.google.com/apppasswords), Outlook, etc.)

## Manual Pipeline Run

After setup, run the full pipeline manually:

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

Or run all steps at once:

```bash
python -m arxiv_digest
```

Shell wrapper scripts are also available for cron use:

```bash
scripts/fetch_prefilter.sh
scripts/score_papers.sh
scripts/download_papers.sh
scripts/review_papers.sh
scripts/digest_deliver.sh
```

## Cron Schedule

When installed via `setup.sh`, the pipeline runs daily:

| Time  | Script                 | Step                              |
|-------|------------------------|-----------------------------------|
| 07:00 | `fetch_prefilter.sh`   | Fetch from arXiv + keyword filter |
| 07:05 | `score_papers.sh`      | LLM hybrid scoring                |
| 07:10 | `download_papers.sh`   | Download full paper texts         |
| 07:20 | `review_papers.sh`     | Deep review via LLM               |
| 07:59 | `digest_deliver.sh`    | Format Markdown/HTML + deliver (Discord/email) |

Logs are appended to `~/cron_digest.log`.

## Configuration

All user configuration lives in `user_preferences.json` (created by `setup.sh` — you shouldn't need to edit it by hand).

### Research Areas

```json
{
  "research_areas": {
    "cs.LG": { "weight": 1.0, "keywords": ["algebraic geometry in deep learning"] },
    "math.AG": { "weight": 0.95, "keywords": ["neuroalgebraic geometry"] }
  }
}
```

- **Keys** are arXiv category codes — these are the categories fetched daily
- **weight** (0–1) controls scoring priority
- **keywords** are matched against paper titles and abstracts

### Interests and Avoidances

```json
{
  "interests": ["invariant and equivariant neural networks", "edge of stability"],
  "avoid": ["Purely empirical benchmarks without theory"]
}
```

- **interests** are sent to the LLM for semantic scoring
- **avoid** criteria trigger deterministic penalty scores

### LLM Settings

```json
{
  "llm": {
    "provider": "gemini",
    "scorer_model": "gemini-2.0-flash",
    "reviewer_model": "gemini-2.5-pro",
    "api_key": "..."
  }
}
```

Supported providers: `gemini` (default) and `claude`. The scorer uses a fast model for bulk scoring; the reviewer uses a stronger model for deep analysis. `setup.sh` configures these automatically.

### Delivery Settings

```json
{
  "delivery": {
    "method": "both",
    "discord": { "user_id": "1103007117671157760" },
    "email": {
      "smtp_host": "smtp.gmail.com",
      "smtp_port": 587,
      "smtp_user": "you@gmail.com",
      "smtp_password": "your-app-password",
      "from_address": "you@gmail.com",
      "to_address": "you@gmail.com"
    }
  }
}
```

- **method**: `"discord"` (default), `"email"`, or `"both"`
- Email uses SMTP with STARTTLS (no extra dependencies — stdlib only)

## Project Structure

```
pipeline/src/arxiv_digest/   # Python package — all pipeline logic
scripts/                     # Thin shell wrappers for cron
resources/                   # Data directory (created at runtime, gitignored)
user_preferences.json        # Your research profile + LLM config (gitignored)
setup.sh                     # One-time setup script
```

For the full module map and internal design, see [ARCHITECTURE.md](ARCHITECTURE.md).

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
