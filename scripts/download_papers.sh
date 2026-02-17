#!/bin/sh
# Thin wrapper: download full papers for scored papers.
set -e
WORKSPACE="$HOME/.openclaw/workspaces/research-assistant"
cd "$WORKSPACE/pipeline"

. .venv/bin/activate

python -m arxiv_digest.download "$@"
