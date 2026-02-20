"""Tests for arxiv_digest.onboard extracted functions."""

import copy
import json
from unittest.mock import MagicMock

import pytest

from arxiv_digest.onboard import extract_preferences_from_chat, merge_research_preferences

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_research_prefs() -> dict:
    return {
        "research_areas": {
            "cs.LG": {"weight": 1.0, "keywords": ["diffusion", "score matching"]},
            "stat.ML": {"weight": 0.8, "keywords": ["bayesian"]},
        },
        "interests": ["theoretical foundations", "generative models"],
        "avoid": ["benchmark studies"],
    }


@pytest.fixture
def existing_prefs() -> dict:
    return {
        "research_areas": {"cs.AI": {"weight": 0.9, "keywords": ["planning"]}},
        "interests": ["old interest"],
        "avoid": ["old avoidance"],
        "llm": {"provider": "gemini", "api_key": "test-key"},
        "delivery": {"email": {"to_address": "user@example.com"}},
        "feedback_history": [{"timestamp": "2026-01-01T00:00:00"}],
        "update_count": 3,
    }


# ── extract_preferences_from_chat ────────────────────────────────────────────


def test_extract_parses_clean_json(sample_research_prefs):
    chat = MagicMock()
    chat.send.return_value = json.dumps(sample_research_prefs)

    result = extract_preferences_from_chat(chat)
    assert result == sample_research_prefs
    chat.send.assert_called_once()


def test_extract_strips_markdown_fences(sample_research_prefs):
    chat = MagicMock()
    wrapped = "```json\n" + json.dumps(sample_research_prefs) + "\n```"
    chat.send.return_value = wrapped

    result = extract_preferences_from_chat(chat)
    assert result == sample_research_prefs


def test_extract_raises_on_invalid_json():
    chat = MagicMock()
    chat.send.return_value = "This is not JSON at all."

    with pytest.raises(json.JSONDecodeError):
        extract_preferences_from_chat(chat)


# ── merge_research_preferences ───────────────────────────────────────────────


def test_merge_replaces_research_keeps_llm(existing_prefs, sample_research_prefs):
    merged = merge_research_preferences(existing_prefs, sample_research_prefs)

    # Research fields replaced
    assert merged["research_areas"] == sample_research_prefs["research_areas"]
    assert merged["interests"] == sample_research_prefs["interests"]
    assert merged["avoid"] == sample_research_prefs["avoid"]

    # LLM, delivery, feedback_history preserved
    assert merged["llm"] == existing_prefs["llm"]
    assert merged["delivery"] == existing_prefs["delivery"]
    assert merged["feedback_history"] == existing_prefs["feedback_history"]
    assert merged["update_count"] == existing_prefs["update_count"]
    assert "last_updated" in merged


def test_merge_does_not_mutate_input(existing_prefs, sample_research_prefs):
    original = copy.deepcopy(existing_prefs)
    merge_research_preferences(existing_prefs, sample_research_prefs)
    assert existing_prefs == original
