"""Tests for arxiv_digest.config paths and setup functions."""

import importlib
from pathlib import Path


def test_workspace_root_default(monkeypatch):
    monkeypatch.delenv("ARXIV_DIGEST_WORKSPACE", raising=False)
    import arxiv_digest.config as cfg

    importlib.reload(cfg)
    expected = Path.home() / ".openclaw/workspaces/research-assistant"
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
