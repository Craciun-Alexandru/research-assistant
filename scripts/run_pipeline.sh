#!/bin/sh
# Run the full arXiv digest pipeline in a single invocation.
set -e
WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"
export ARXIV_DIGEST_WORKSPACE="$WORKSPACE"
exec >> "$WORKSPACE/cron_digest.log" 2>&1
cd "$WORKSPACE/pipeline"

# Activate the project environment
. .venv/bin/activate

python -m arxiv_digest
