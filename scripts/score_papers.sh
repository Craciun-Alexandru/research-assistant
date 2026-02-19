#!/bin/sh
# Thin wrapper: score filtered papers.
set -e
WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"
export ARXIV_DIGEST_WORKSPACE="$WORKSPACE"
cd "$WORKSPACE/pipeline"

. .venv/bin/activate

python -m arxiv_digest.scorer "$@"
