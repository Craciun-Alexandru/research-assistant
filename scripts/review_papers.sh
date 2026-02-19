#!/bin/sh
# Thin wrapper: deep-review scored papers.
set -e
WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"
export ARXIV_DIGEST_WORKSPACE="$WORKSPACE"
cd "$WORKSPACE/pipeline"

. .venv/bin/activate

python -m arxiv_digest.reviewer "$@"
