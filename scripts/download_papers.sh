#!/bin/sh
# Thin wrapper: download full papers for scored papers.
set -e
WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"
export ARXIV_DIGEST_WORKSPACE="$WORKSPACE"
cd "$WORKSPACE/pipeline"

. .venv/bin/activate

python -m arxiv_digest.download "$@"
