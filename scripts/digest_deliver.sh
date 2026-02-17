#!/bin/sh
# This script is designed to be run as a cron job to process and deliver the daily research digest. It will execute the following steps:
# 1. Create a markdown digest from a JSON file.
# 2. Deliver the markdown digest to a specified Discord user.
# Cron entry example (runs daily at 8:00 AM):
# 0 8 * * * * /path/to/process_deliver.sh >> "$HOME/cron_digest.log" 2>&1
# Make sure to replace "/path/to/process_deliver.sh" with the actual path to this script on your system.
set -e
WORKSPACE="$HOME/.openclaw/workspaces/research-assistant"
cd "$WORKSPACE/pipeline"

# Activate the project environment (one line)
. .venv/bin/activate

python -m arxiv_digest.digest
python -m arxiv_digest.deliver
