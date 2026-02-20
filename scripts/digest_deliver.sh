#!/bin/sh
# Generate Markdown/HTML digest and deliver via email.
# Cron entry example (runs daily at 7:59 AM):
# 59 7 * * * /path/to/digest_deliver.sh
set -e
WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"
export ARXIV_DIGEST_WORKSPACE="$WORKSPACE"
exec >> "$WORKSPACE/cron_digest.log" 2>&1
cd "$WORKSPACE/pipeline"

# Activate the project environment (one line)
. .venv/bin/activate

python -m arxiv_digest.digest
python -m arxiv_digest.deliver
