"""Tests for arxiv_digest.prefilter pure functions."""

from arxiv_digest.prefilter import apply_avoidance_filters, prefilter_score
from arxiv_digest.utils import get_all_keywords


def test_prefilter_score_category_match(sample_paper, sample_preferences):
    user_categories = set(sample_preferences["research_areas"].keys())
    keywords = get_all_keywords(sample_preferences)
    score = prefilter_score(sample_paper, user_categories, keywords)
    assert score > 0


def test_prefilter_score_no_category_match(sample_paper, sample_preferences):
    user_categories = {"math.AG", "math.AC"}  # no overlap with cs.LG / stat.ML
    keywords = get_all_keywords(sample_preferences)
    score = prefilter_score(sample_paper, user_categories, keywords)
    assert score == 0.0


def test_prefilter_score_title_beats_abstract(sample_preferences):
    user_categories = {"cs.LG"}
    keywords = {"diffusion"}

    paper_title_match = {
        "title": "Diffusion Models Are Great",
        "abstract": "We study generative approaches without mentioning the key term.",
        "categories": ["cs.LG"],
    }
    paper_abstract_match = {
        "title": "On Generative Models",
        "abstract": "We study diffusion as a core mechanism here.",
        "categories": ["cs.LG"],
    }

    score_title = prefilter_score(paper_title_match, user_categories, keywords)
    score_abstract = prefilter_score(paper_abstract_match, user_categories, keywords)
    assert score_title > score_abstract


def test_apply_avoidance_filters_benchmark_no_theory():
    paper = {
        "title": "A Large-Scale Benchmark and Evaluation of Language Models",
        "abstract": "We compare 50 models across 20 tasks using standard metrics.",
    }
    result = apply_avoidance_filters(paper, ["benchmark studies"])
    assert result is False


def test_apply_avoidance_filters_benchmark_with_theory():
    paper = {
        "title": "Benchmark Analysis of Diffusion Models",
        "abstract": "We prove a theorem showing that under certain conditions the evaluation error converges.",
    }
    result = apply_avoidance_filters(paper, ["benchmark studies"])
    assert result is True


def test_apply_avoidance_filters_no_criteria(sample_paper):
    result = apply_avoidance_filters(sample_paper, [])
    assert result is True
