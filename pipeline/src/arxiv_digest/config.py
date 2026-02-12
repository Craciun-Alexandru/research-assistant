"""
Shared configuration: paths, constants, and environment.

Every module imports paths from here. No hardcoded workspace paths elsewhere.
"""

import os
from datetime import date
from pathlib import Path

# ── Workspace root ──
# Override with ARXIV_DIGEST_WORKSPACE env var for testing or alternate deployments.
WORKSPACE_ROOT = Path(
    os.environ.get(
        "ARXIV_DIGEST_WORKSPACE",
        Path.home() / ".openclaw/workspaces/research-assistant",
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


def ensure_directories() -> None:
    """Create data directories if they don't exist."""
    RESOURCES_DIR.mkdir(parents=True, exist_ok=True)
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
