"""
Shared configuration: paths, constants, and environment.

Every module imports paths from here. No hardcoded workspace paths elsewhere.
"""

import json
import os
from datetime import date
from pathlib import Path

# ── Workspace root ──
# Override with ARXIV_DIGEST_WORKSPACE env var for testing or alternate deployments.
WORKSPACE_ROOT = Path(
    os.environ.get(
        "ARXIV_DIGEST_WORKSPACE",
        str(Path(__file__).resolve().parent.parent.parent.parent),
    )
)

# ── Data paths ──
RESOURCES_DIR = WORKSPACE_ROOT / "resources"
CURRENT_RUN_DIR = RESOURCES_DIR / "current"
DAILY_PAPERS_PATH = CURRENT_RUN_DIR / "daily_papers.json"
FILTERED_PAPERS_PATH = CURRENT_RUN_DIR / "filtered_papers.json"
SCORED_PAPERS_PATH = CURRENT_RUN_DIR / "scored_papers_summary.json"
PAPERS_DIR = RESOURCES_DIR / "papers"
DIGESTS_DIR = RESOURCES_DIR / "digests"
DOWNLOAD_METADATA_PATH = PAPERS_DIR / "download_metadata.json"

# ── Config files ──
USER_PREFERENCES_PATH = WORKSPACE_ROOT / "user_preferences.json"

# ── Defaults ──
DEFAULT_CATEGORIES = ["cs.LG", "stat.ML", "math.AG", "math.AC", "math.DG", "math.DS", "math.CT"]
DEFAULT_TARGET_COUNT = 150
DEFAULT_DAYS_BACK = 1
DEFAULT_MAX_RESULTS_PER_CATEGORY = 1000

# ── arXiv API ──
ARXIV_REQUEST_DELAY = 3.0  # seconds between requests (arXiv policy)
ARXIV_USER_AGENT = "arXiv-Curator-Bot/1.0 (Academic Research; mailto:researcher@example.com)"
ARXIV_HEADERS = {"User-Agent": ARXIV_USER_AGENT}

# ── Discord ──
DISCORD_USER_ID = os.environ.get("DISCORD_USER_ID", "1103007117671157760")
DISCORD_MAX_MESSAGE_LENGTH = 1900  # Discord limit is 2000, leave margin


def setup_daily_run() -> Path:
    """Create a resources/YYYY-MM-DD/ directory for today and update the current symlink.

    Returns:
        The path to today's daily run directory.
    """
    today = date.today().isoformat()
    daily_dir = RESOURCES_DIR / today
    daily_dir.mkdir(parents=True, exist_ok=True)

    # Atomically update the "current" symlink
    current_link = RESOURCES_DIR / "current"
    tmp_link = RESOURCES_DIR / ".current_tmp"
    tmp_link.unlink(missing_ok=True)
    tmp_link.symlink_to(daily_dir)
    tmp_link.rename(current_link)

    return daily_dir


def load_llm_config() -> dict:
    """Load LLM configuration from user preferences.

    Returns:
        Dict with keys: provider, scorer_model, reviewer_model, api_key.
        ``api_key`` is automatically selected for the active provider
        (``llm.api_key`` for Gemini, ``llm.claude_api_key`` for Claude).
    """
    with USER_PREFERENCES_PATH.open() as f:
        prefs = json.load(f)
    llm = prefs.get("llm", {})
    provider = llm.get("provider", "gemini")

    if provider == "claude":
        api_key = llm.get("claude_api_key", "")
        scorer_default = "claude-haiku-4-5-20251001"
        reviewer_default = "claude-sonnet-4-6"
    else:  # gemini
        api_key = llm.get("api_key", "")
        scorer_default = "gemini-2.0-flash"
        reviewer_default = "gemini-2.5-pro"

    return {
        "provider": provider,
        "scorer_model": llm.get("scorer_model", scorer_default),
        "reviewer_model": llm.get("reviewer_model", reviewer_default),
        "api_key": api_key,
    }


def load_delivery_config() -> dict:
    """Load delivery configuration from user preferences.

    Returns:
        Dict with keys: method ("discord", "email", or "both"),
        discord (dict with user_id), email (dict with SMTP settings).
        Defaults to discord-only delivery for backward compatibility.
    """
    default_email = {
        "smtp_host": "",
        "smtp_port": 587,
        "smtp_user": "",
        "smtp_password": "",
        "from_address": "",
        "to_address": "",
    }
    default_config = {
        "method": "discord",
        "discord": {"user_id": DISCORD_USER_ID},
        "email": default_email,
    }

    try:
        with USER_PREFERENCES_PATH.open() as f:
            prefs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default_config

    delivery = prefs.get("delivery", {})
    if not delivery:
        return default_config

    return {
        "method": delivery.get("method", "discord"),
        "discord": {
            "user_id": delivery.get("discord", {}).get("user_id", DISCORD_USER_ID),
        },
        "email": {
            "smtp_host": delivery.get("email", {}).get("smtp_host", ""),
            "smtp_port": delivery.get("email", {}).get("smtp_port", 587),
            "smtp_user": delivery.get("email", {}).get("smtp_user", ""),
            "smtp_password": delivery.get("email", {}).get("smtp_password", ""),
            "from_address": delivery.get("email", {}).get("from_address", ""),
            "to_address": delivery.get("email", {}).get("to_address", ""),
        },
    }


def ensure_directories() -> None:
    """Create data directories if they don't exist."""
    RESOURCES_DIR.mkdir(parents=True, exist_ok=True)
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
