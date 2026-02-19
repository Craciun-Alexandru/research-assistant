"""Shared pytest fixtures for arxiv_digest tests."""

import importlib
import os

import pytest


@pytest.fixture
def sample_paper() -> dict:
    return {
        "arxiv_id": "2602.12345",
        "title": "Diffusion Models with Neural Network Architectures: A Theoretical Analysis",
        "abstract": (
            "We present a theoretical analysis of diffusion models combined with neural network "
            "architectures. Our main theorem establishes convergence guarantees under mild "
            "assumptions. The proof relies on novel techniques from stochastic calculus and "
            "provides new insights into score-based generative models."
        ),
        "authors": ["Alice Smith", "Bob Jones", "Carol Williams", "David Brown"],
        "categories": ["cs.LG", "stat.ML"],
        "published": "2026-02-19",
        "pdf_url": "https://arxiv.org/pdf/2602.12345",
    }


@pytest.fixture
def sample_preferences() -> dict:
    return {
        "research_areas": {
            "cs.LG": {
                "weight": 1.0,
                "keywords": [
                    "diffusion",
                    "neural network",
                    "generative model",
                    "representation learning",
                ],
            },
            "stat.ML": {
                "weight": 0.8,
                "keywords": ["bayesian inference", "variational", "score matching"],
            },
        },
        "interests": [
            "Theoretical foundations of deep learning",
            "Generative models and their applications",
            "Connections between optimization and statistical learning",
        ],
        "avoid": [
            "benchmark studies",
            "engineering implementations",
        ],
    }


@pytest.fixture
def sample_digest() -> dict:
    return {
        "digest_date": "2026-02-19",
        "summary": "Today's digest highlights advances in diffusion model theory.",
        "total_reviewed": 25,
        "papers": [
            {
                "arxiv_id": "2602.12345",
                "title": "Diffusion Models with Neural Network Architectures: A Theoretical Analysis",
                "authors": ["Alice Smith", "Bob Jones", "Carol Williams", "David Brown"],
                "categories": ["cs.LG", "stat.ML"],
                "score": 9.2,
                "pdf_url": "https://arxiv.org/pdf/2602.12345",
                "summary": "This paper proves convergence guarantees for diffusion models.",
                "key_insight": "The key theoretical contribution is a new convergence bound.",
                "relevance": "Directly relevant to theoretical deep learning research.",
            }
        ],
    }


@pytest.fixture(scope="session")
def tmp_workspace(tmp_path_factory):
    """Session-scoped workspace in a temp dir; sets ARXIV_DIGEST_WORKSPACE env var."""
    workspace = tmp_path_factory.mktemp("workspace")
    os.environ["ARXIV_DIGEST_WORKSPACE"] = str(workspace)

    import arxiv_digest.config as cfg

    importlib.reload(cfg)

    yield workspace

    # Cleanup env var
    del os.environ["ARXIV_DIGEST_WORKSPACE"]
    importlib.reload(cfg)
