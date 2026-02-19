"""Tests for arxiv_digest.scorer deterministic scoring functions."""

import pytest

from arxiv_digest.scorer import (
    _brief_reason,
    calculate_avoidance_penalty,
    calculate_category_score,
    calculate_keyword_score,
    calculate_novelty_bonus,
)
from arxiv_digest.utils import get_all_keywords

# ── Category score ────────────────────────────────────────────────────


def test_calculate_category_score_primary():
    paper = {"categories": ["cs.LG", "stat.ML"]}
    user_areas = {"cs.LG": {"weight": 1.0}}
    score = calculate_category_score(paper, user_areas)
    assert score == pytest.approx(5.0)


def test_calculate_category_score_secondary():
    paper = {"categories": ["math.AG", "cs.LG"]}
    user_areas = {"cs.LG": {"weight": 1.0}}
    score = calculate_category_score(paper, user_areas)
    assert score == pytest.approx(2.5)


def test_calculate_category_score_cap():
    paper = {"categories": ["cs.LG", "stat.ML", "cs.AI"]}
    # All three with weight 1.0 would give 5 + 2.5 + 2.5 = 10, but capped at 5.0
    user_areas = {
        "cs.LG": {"weight": 1.0},
        "stat.ML": {"weight": 1.0},
        "cs.AI": {"weight": 1.0},
    }
    score = calculate_category_score(paper, user_areas)
    assert score == pytest.approx(5.0)


def test_calculate_category_score_no_match():
    paper = {"categories": ["math.AG"]}
    user_areas = {"cs.LG": {"weight": 1.0}}
    score = calculate_category_score(paper, user_areas)
    assert score == 0.0


# ── Keyword score ─────────────────────────────────────────────────────


def test_calculate_keyword_score_title_match():
    paper = {"title": "Diffusion Models for Everything", "abstract": "We study other things."}
    score = calculate_keyword_score(paper, {"diffusion"})
    assert score == pytest.approx(2.0)


def test_calculate_keyword_score_abstract_match():
    paper = {"title": "On Generative Models", "abstract": "We study diffusion in detail."}
    score = calculate_keyword_score(paper, {"diffusion"})
    assert score == pytest.approx(0.5)


def test_calculate_keyword_score_cap():
    paper = {
        "title": "alpha beta gamma delta epsilon zeta eta",
        "abstract": "alpha beta gamma delta epsilon zeta eta theta iota kappa",
    }
    keywords = {"alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta"}
    score = calculate_keyword_score(paper, keywords)
    assert score == pytest.approx(3.0)


# ── Novelty bonus ─────────────────────────────────────────────────────


def test_calculate_novelty_bonus_high():
    paper = {
        "title": "A Novel Approach to Diffusion",
        "abstract": "We prove a theorem showing breakthrough convergence.",
    }
    assert calculate_novelty_bonus(paper) == 1


def test_calculate_novelty_bonus_low():
    paper = {
        "title": "Incremental Improvements to Existing Methods",
        "abstract": "We extend prior work with marginal gains.",
    }
    assert calculate_novelty_bonus(paper) == 0


# ── Avoidance penalty ────────────────────────────────────────────────


def test_calculate_avoidance_penalty_benchmark_no_theory():
    paper = {
        "title": "A Benchmark Evaluation of Language Models",
        "abstract": "We compare 50 models using standard metrics.",
    }
    penalty = calculate_avoidance_penalty(paper, ["empirical studies"])
    assert penalty == pytest.approx(2.0)


def test_calculate_avoidance_penalty_benchmark_with_theory():
    paper = {
        "title": "A Benchmark for Proving Convergence",
        "abstract": "We provide a theorem with proof of theoretical guarantees.",
    }
    penalty = calculate_avoidance_penalty(paper, ["empirical studies"])
    assert penalty == pytest.approx(0.0)


def test_calculate_avoidance_penalty_cap():
    paper = {
        "title": "A Benchmark Implementation Framework Tool",
        "abstract": "We compare systems and evaluate performance across multiple datasets.",
    }
    penalty = calculate_avoidance_penalty(
        paper, ["empirical studies", "engineering implementations"]
    )
    assert penalty == pytest.approx(3.0)


# ── Brief reason ─────────────────────────────────────────────────────


def test_brief_reason_high_scores():
    det = {"category": 5.0, "keyword": 3.0, "novelty": 1, "avoidance": 0.0}
    reason = _brief_reason(det, interest=2)
    assert len(reason) > 0
    assert reason != "Low overall relevance."


def test_brief_reason_low_scores():
    det = {"category": 0.0, "keyword": 0.0, "novelty": 0, "avoidance": 0.0}
    reason = _brief_reason(det, interest=0)
    assert reason == "Low overall relevance."


# ── get_all_keywords ─────────────────────────────────────────────────


def test_get_all_keywords(sample_preferences):
    keywords = get_all_keywords(sample_preferences)
    assert isinstance(keywords, set)
    # All should be lowercase
    assert all(kw == kw.lower() for kw in keywords)
    # Check known keywords are present
    assert "diffusion" in keywords
    assert "neural network" in keywords
    assert "bayesian inference" in keywords
