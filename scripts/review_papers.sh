#!/bin/sh
# Thin wrapper: deep-review scored papers.
set -e
WORKSPACE="$HOME/.openclaw/workspaces/research-assistant"
cd "$WORKSPACE/pipeline"

. .venv/bin/activate

python -m arxiv_digest.reviewer "$@"
