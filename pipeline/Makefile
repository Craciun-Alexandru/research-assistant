.PHONY: install lint format test pipeline fetch prefilter download digest deliver setup-cron clean

# ── Setup ──

install:
	pip install -e ".[dev]" --break-system-packages

# ── Code Quality ──

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff check --fix src/ tests/
	ruff format src/ tests/

test:
	pytest tests/ -v

# ── Pipeline Steps (Python-managed only) ──

fetch:
	python -m arxiv_digest.fetch

prefilter:
	python -m arxiv_digest.prefilter

download:
	python -m arxiv_digest.download

digest:
	python -m arxiv_digest.digest

deliver:
	python -m arxiv_digest.deliver

pipeline: fetch prefilter
	@echo "──────────────────────────────────────"
	@echo "Pipeline: fetch + prefilter complete."
	@echo "Now wait for OpenClaw quick-scorer, then run: make download"
	@echo "After OpenClaw deep-reviewer, run: make digest deliver"
	@echo "──────────────────────────────────────"

# ── Cron Setup (placeholder) ──

setup-cron:
	@echo "TODO: Install cron entries for fetch_prefilter.sh and process_deliver.sh"
	@echo "Current cron scripts are in scripts/"
	@echo "Manually add with: crontab -e"

# ── Cleanup ──

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
