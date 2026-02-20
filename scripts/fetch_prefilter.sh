#!/bin/sh
# Fetch papers from arXiv and pre-filter by keyword/category.
# Cron entry example (runs daily at 7:00 AM):
# 0 7 * * * /path/to/fetch_prefilter.sh
set -e
WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"
export ARXIV_DIGEST_WORKSPACE="$WORKSPACE"
exec >> "$WORKSPACE/cron_digest.log" 2>&1
cd "$WORKSPACE/pipeline"

# Activate the project environment
. .venv/bin/activate

python -m arxiv_digest.fetch
python -m arxiv_digest.prefilter
