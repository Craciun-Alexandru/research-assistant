# arXiv Research Digest

Automated daily pipeline that fetches papers from arXiv, scores them against your research interests, and delivers a curated digest via email.

## Quick Start

```bash
git clone https://github.com/Craciun-Alexandru/research-assistant.git
cd research-assistant
./setup.sh
```

`setup.sh` handles everything: creates a virtual environment, installs dependencies, prompts for your API key(s), runs the onboarding wizard, and optionally installs a cron job.

### Prerequisites

- Python 3.10+
- A [Gemini API key](https://aistudio.google.com/apikey) (free tier works) and/or an [Anthropic API key](https://console.anthropic.com/)
- An SMTP-capable email account (Gmail with [App Password](https://myaccount.google.com/apppasswords), Outlook, etc.)

## Running the Pipeline

Run the full pipeline manually:

```bash
scripts/run_pipeline.sh
```

Or directly from the package:

```bash
cd pipeline && . .venv/bin/activate
python -m arxiv_digest
```

Per-stage scripts are also available in `scripts/` for debugging individual steps.

## Cron Schedule

When installed via `setup.sh`, a single cron job runs the full pipeline daily:

```
00 07 * * * /path/to/scripts/run_pipeline.sh
```

Logs are appended to `cron_digest.log` in the project root.

## Configuration

All user configuration lives in `user_preferences.json` (created by `setup.sh`).

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

- **interests** are sent to the LLM for semantic scoring and persona generation
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

Delivery is via email only, using SMTP with STARTTLS (stdlib — no extra dependencies).

## Project Structure

```
pipeline/src/arxiv_digest/   # Python package — all pipeline logic
scripts/                     # Shell wrappers (run_pipeline.sh + per-stage scripts)
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
