#!/bin/sh
# Thin wrapper: score filtered papers.
set -e
WORKSPACE="$HOME/.openclaw/workspaces/research-assistant"
cd "$WORKSPACE/pipeline"

. .venv/bin/activate

python -m arxiv_digest.scorer "$@"
