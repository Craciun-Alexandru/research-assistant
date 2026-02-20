"""Tests for arxiv_digest.config paths and setup functions."""

import importlib
import json
from pathlib import Path


def test_workspace_root_default(monkeypatch):
    monkeypatch.delenv("ARXIV_DIGEST_WORKSPACE", raising=False)
    import arxiv_digest.config as cfg

    importlib.reload(cfg)
    # Default: project root, resolved from config.py's location
    config_file = Path(cfg.__file__).resolve()
    expected = config_file.parent.parent.parent.parent
    assert expected == cfg.WORKSPACE_ROOT


def test_workspace_root_override(monkeypatch, tmp_path):
    monkeypatch.setenv("ARXIV_DIGEST_WORKSPACE", str(tmp_path))
    import arxiv_digest.config as cfg

    importlib.reload(cfg)
    assert tmp_path == cfg.WORKSPACE_ROOT


def test_ensure_directories(monkeypatch, tmp_path):
    monkeypatch.setenv("ARXIV_DIGEST_WORKSPACE", str(tmp_path))
    import arxiv_digest.config as cfg

    importlib.reload(cfg)
    cfg.ensure_directories()
    assert cfg.RESOURCES_DIR.exists()
    assert cfg.PAPERS_DIR.exists()
    assert cfg.DIGESTS_DIR.exists()


def test_setup_daily_run(monkeypatch, tmp_path):
    monkeypatch.setenv("ARXIV_DIGEST_WORKSPACE", str(tmp_path))
    import arxiv_digest.config as cfg

    importlib.reload(cfg)
    daily_dir = cfg.setup_daily_run()
    assert daily_dir.exists()
    assert daily_dir.is_dir()

    current_link = cfg.RESOURCES_DIR / "current"
    assert current_link.exists()
    assert current_link.is_symlink()
    assert current_link.resolve() == daily_dir.resolve()


# ── load_delivery_config ─────────────────────────────────────────────


def test_load_delivery_config_default_no_key(monkeypatch, tmp_path):
    """No delivery key in prefs → defaults to discord with DISCORD_USER_ID."""
    monkeypatch.setenv("ARXIV_DIGEST_WORKSPACE", str(tmp_path))
    import arxiv_digest.config as cfg

    importlib.reload(cfg)

    prefs = {"llm": {"provider": "gemini"}}
    cfg.USER_PREFERENCES_PATH.write_text(json.dumps(prefs))

    config = cfg.load_delivery_config()
    assert config["method"] == "discord"
    assert config["discord"]["user_id"] == cfg.DISCORD_USER_ID
    assert config["email"]["smtp_host"] == ""


def test_load_delivery_config_email(monkeypatch, tmp_path):
    """Email config loaded correctly from preferences."""
    monkeypatch.setenv("ARXIV_DIGEST_WORKSPACE", str(tmp_path))
    import arxiv_digest.config as cfg

    importlib.reload(cfg)

    prefs = {
        "delivery": {
            "method": "email",
            "email": {
                "smtp_host": "smtp.gmail.com",
                "smtp_port": 587,
                "smtp_user": "me@gmail.com",
                "smtp_password": "secret",
                "from_address": "me@gmail.com",
                "to_address": "me@gmail.com",
            },
        }
    }
    cfg.USER_PREFERENCES_PATH.write_text(json.dumps(prefs))

    config = cfg.load_delivery_config()
    assert config["method"] == "email"
    assert config["email"]["smtp_host"] == "smtp.gmail.com"
    assert config["email"]["to_address"] == "me@gmail.com"


def test_load_delivery_config_missing_prefs(monkeypatch, tmp_path):
    """Missing prefs file returns defaults."""
    monkeypatch.setenv("ARXIV_DIGEST_WORKSPACE", str(tmp_path))
    import arxiv_digest.config as cfg

    importlib.reload(cfg)

    # Ensure file does not exist
    cfg.USER_PREFERENCES_PATH.unlink(missing_ok=True)

    config = cfg.load_delivery_config()
    assert config["method"] == "discord"
    assert config["email"]["smtp_port"] == 587
