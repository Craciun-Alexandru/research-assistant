"""Tests for arxiv_digest.feedback pure functions."""

import json

import pytest

from arxiv_digest.feedback import (
    apply_delta,
    build_feedback_entry,
    find_digest_dates,
    get_reviewed_info,
    load_digest_for_date,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_paper() -> dict:
    return {
        "arxiv_id": "2602.99001",
        "title": "Test Paper on Diffusion",
        "authors": ["Alice"],
        "categories": ["cs.LG", "stat.ML"],
        "score": 8.5,
        "summary": "A short summary.",
        "key_insight": "Key insight here.",
        "relevance": "Very relevant.",
    }


@pytest.fixture
def base_prefs() -> dict:
    return {
        "research_areas": {
            "cs.LG": {"weight": 1.0, "keywords": ["diffusion", "neural network"]},
            "stat.ML": {"weight": 0.8, "keywords": ["bayesian", "variational"]},
        },
        "interests": ["theoretical foundations", "generative models"],
        "avoid": ["benchmark studies", "engineering implementations"],
        "llm": {"provider": "gemini", "api_key": "test-key"},
        "delivery": {"email": {}},
    }


# ── Date discovery ────────────────────────────────────────────────────────────


def _make_digest_dir(base: object, date_str: str) -> None:
    """Helper: create a dated dir with a digest JSON inside."""
    from pathlib import Path

    d = Path(str(base)) / date_str
    d.mkdir(parents=True)
    (d / f"digest_{date_str}.json").write_text(json.dumps({"papers": []}))


def test_find_digest_dates_returns_newest_first(tmp_path):
    for d in ("2026-02-17", "2026-02-19", "2026-02-18"):
        _make_digest_dir(tmp_path, d)

    result = find_digest_dates(tmp_path)
    assert result == ["2026-02-19", "2026-02-18", "2026-02-17"]


def test_find_digest_dates_ignores_non_date_dirs(tmp_path):
    _make_digest_dir(tmp_path, "2026-02-19")
    for name in ("current", "papers", "digests", "some_other_dir"):
        d = tmp_path / name
        d.mkdir()
        (d / "digest_whatever.json").write_text("{}")

    result = find_digest_dates(tmp_path)
    assert result == ["2026-02-19"]


def test_find_digest_dates_requires_digest_json(tmp_path):
    # Date dir without a digest_*.json
    (tmp_path / "2026-02-19").mkdir()
    # Date dir with a differently-named file
    (tmp_path / "2026-02-18").mkdir()
    (tmp_path / "2026-02-18" / "summary.json").write_text("{}")
    # Date dir WITH a digest
    _make_digest_dir(tmp_path, "2026-02-17")

    result = find_digest_dates(tmp_path)
    assert result == ["2026-02-17"]


def test_find_digest_dates_empty(tmp_path):
    result = find_digest_dates(tmp_path)
    assert result == []


# ── load_digest_for_date ──────────────────────────────────────────────────────


def test_load_digest_for_date_success(tmp_path):
    payload = {"digest_date": "2026-02-19", "papers": [{"arxiv_id": "1234"}]}
    _make_digest_dir(tmp_path, "2026-02-19")
    (tmp_path / "2026-02-19" / "digest_2026-02-19.json").write_text(json.dumps(payload))

    result = load_digest_for_date("2026-02-19", tmp_path)
    assert result["digest_date"] == "2026-02-19"
    assert result["papers"][0]["arxiv_id"] == "1234"


def test_load_digest_for_date_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_digest_for_date("2026-02-19", tmp_path)


# ── build_feedback_entry ──────────────────────────────────────────────────────


def test_build_feedback_entry_good(sample_paper):
    entry = build_feedback_entry(sample_paper, "good", "")
    assert entry["feedback_type"] == "good"
    assert entry["feedback_text"] == ""


def test_build_feedback_entry_bad(sample_paper):
    entry = build_feedback_entry(sample_paper, "bad", "")
    assert entry["feedback_type"] == "bad"
    assert entry["feedback_text"] == ""


def test_build_feedback_entry_verbal(sample_paper):
    entry = build_feedback_entry(sample_paper, "verbal", "Too applied, not theoretical enough.")
    assert entry["feedback_type"] == "verbal"
    assert entry["feedback_text"] == "Too applied, not theoretical enough."


def test_build_feedback_entry_fields(sample_paper):
    entry = build_feedback_entry(sample_paper, "good", "")
    required_keys = {"arxiv_id", "title", "categories", "score", "feedback_type", "feedback_text"}
    assert required_keys.issubset(entry.keys())
    assert entry["arxiv_id"] == sample_paper["arxiv_id"]
    assert entry["title"] == sample_paper["title"]
    assert entry["categories"] == sample_paper["categories"]
    assert entry["score"] == sample_paper["score"]


# ── apply_delta ───────────────────────────────────────────────────────────────


def test_apply_delta_weight_adjustments(base_prefs):
    delta = {"weight_adjustments": {"cs.LG": 0.9}, "reasoning": "test"}
    result = apply_delta(base_prefs, delta)
    assert result["research_areas"]["cs.LG"]["weight"] == 0.9
    # stat.ML unchanged
    assert result["research_areas"]["stat.ML"]["weight"] == 0.8


def test_apply_delta_weight_adjustments_unknown_category(base_prefs):
    # Adjusting a category not in prefs should not create it (no-op for weights)
    delta = {"weight_adjustments": {"cs.CV": 0.7}, "reasoning": "test"}
    result = apply_delta(base_prefs, delta)
    assert "cs.CV" not in result["research_areas"]


def test_apply_delta_add_keywords_existing_category(base_prefs):
    delta = {"add_keywords": {"cs.LG": ["score matching", "flow matching"]}, "reasoning": "test"}
    result = apply_delta(base_prefs, delta)
    kws = result["research_areas"]["cs.LG"]["keywords"]
    assert "score matching" in kws
    assert "flow matching" in kws
    # original keywords still present
    assert "diffusion" in kws


def test_apply_delta_add_keywords_new_category(base_prefs):
    delta = {"add_keywords": {"math.AG": ["sheaves", "schemes"]}, "reasoning": "test"}
    result = apply_delta(base_prefs, delta)
    assert "math.AG" in result["research_areas"]
    assert "sheaves" in result["research_areas"]["math.AG"]["keywords"]


def test_apply_delta_add_keywords_no_duplicates(base_prefs):
    # "diffusion" already exists in cs.LG
    delta = {"add_keywords": {"cs.LG": ["diffusion", "new_keyword"]}, "reasoning": "test"}
    result = apply_delta(base_prefs, delta)
    kws = result["research_areas"]["cs.LG"]["keywords"]
    assert kws.count("diffusion") == 1


def test_apply_delta_remove_keywords(base_prefs):
    delta = {"remove_keywords": {"cs.LG": ["diffusion"]}, "reasoning": "test"}
    result = apply_delta(base_prefs, delta)
    assert "diffusion" not in result["research_areas"]["cs.LG"]["keywords"]
    assert "neural network" in result["research_areas"]["cs.LG"]["keywords"]


def test_apply_delta_remove_keywords_missing_silently_ignored(base_prefs):
    delta = {"remove_keywords": {"cs.LG": ["nonexistent_keyword"]}, "reasoning": "test"}
    result = apply_delta(base_prefs, delta)
    # Original keywords unchanged
    assert result["research_areas"]["cs.LG"]["keywords"] == ["diffusion", "neural network"]


def test_apply_delta_add_remove_interests(base_prefs):
    delta = {
        "add_interests": ["categorical structures", "sheaf theory"],
        "remove_interests": ["generative models"],
        "reasoning": "test",
    }
    result = apply_delta(base_prefs, delta)
    assert "categorical structures" in result["interests"]
    assert "sheaf theory" in result["interests"]
    assert "generative models" not in result["interests"]
    assert "theoretical foundations" in result["interests"]


def test_apply_delta_add_interests_no_duplicates(base_prefs):
    delta = {"add_interests": ["theoretical foundations"], "reasoning": "test"}
    result = apply_delta(base_prefs, delta)
    assert result["interests"].count("theoretical foundations") == 1


def test_apply_delta_add_remove_avoid(base_prefs):
    delta = {
        "add_avoid": ["survey papers", "tutorial-style papers"],
        "remove_avoid": ["engineering implementations"],
        "reasoning": "test",
    }
    result = apply_delta(base_prefs, delta)
    assert "survey papers" in result["avoid"]
    assert "tutorial-style papers" in result["avoid"]
    assert "engineering implementations" not in result["avoid"]
    assert "benchmark studies" in result["avoid"]


def test_apply_delta_empty_delta(base_prefs):
    delta = {"reasoning": "no changes needed"}
    result = apply_delta(base_prefs, delta)
    assert result["research_areas"] == base_prefs["research_areas"]
    assert result["interests"] == base_prefs["interests"]
    assert result["avoid"] == base_prefs["avoid"]


def test_apply_delta_does_not_mutate_input(base_prefs):
    import copy

    original = copy.deepcopy(base_prefs)
    delta = {
        "weight_adjustments": {"cs.LG": 0.5},
        "add_keywords": {"cs.LG": ["new_kw"]},
        "remove_keywords": {"stat.ML": ["bayesian"]},
        "add_interests": ["new interest"],
        "remove_interests": ["theoretical foundations"],
        "add_avoid": ["new avoidance"],
        "remove_avoid": ["benchmark studies"],
        "reasoning": "mutation test",
    }
    apply_delta(base_prefs, delta)
    assert base_prefs == original


# ── get_reviewed_info ─────────────────────────────────────────────────────────


def test_get_reviewed_info_empty():
    reviewed_dates, reviewed_ids = get_reviewed_info([])
    assert reviewed_dates == set()
    assert reviewed_ids == set()


def test_get_reviewed_info_collects_dates():
    history = [
        {"dates_reviewed": ["2026-02-17", "2026-02-18"], "reviewed_paper_ids": []},
        {"dates_reviewed": ["2026-02-19"], "reviewed_paper_ids": []},
    ]
    reviewed_dates, _ = get_reviewed_info(history)
    assert reviewed_dates == {"2026-02-17", "2026-02-18", "2026-02-19"}


def test_get_reviewed_info_collects_paper_ids():
    history = [
        {"dates_reviewed": [], "reviewed_paper_ids": ["2602.00001", "2602.00002"]},
        {"dates_reviewed": [], "reviewed_paper_ids": ["2602.00003"]},
    ]
    _, reviewed_ids = get_reviewed_info(history)
    assert reviewed_ids == {"2602.00001", "2602.00002", "2602.00003"}


def test_get_reviewed_info_deduplicates():
    history = [
        {"dates_reviewed": ["2026-02-19"], "reviewed_paper_ids": ["2602.00001"]},
        {"dates_reviewed": ["2026-02-19"], "reviewed_paper_ids": ["2602.00001"]},
    ]
    reviewed_dates, reviewed_ids = get_reviewed_info(history)
    assert reviewed_dates == {"2026-02-19"}
    assert reviewed_ids == {"2602.00001"}


def test_get_reviewed_info_missing_keys_ignored():
    # Older history entries may not have reviewed_paper_ids
    history = [
        {"dates_reviewed": ["2026-02-18"]},
        {"reviewed_paper_ids": ["2602.00001"]},
        {},
    ]
    reviewed_dates, reviewed_ids = get_reviewed_info(history)
    assert reviewed_dates == {"2026-02-18"}
    assert reviewed_ids == {"2602.00001"}
