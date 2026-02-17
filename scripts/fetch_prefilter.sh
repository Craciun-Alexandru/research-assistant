#!/bin/sh
# This script is designed to be run as a cron job to fetch and prefilter research papers from arXiv on a daily basis. It will execute the following steps: 
# 1. Change to the appropriate directory where the Python scripts are located.
# 2. Run the `fetch_papers.py` script to retrieve papers from specified categories
# 3. Run the `prefilter_papers.py` script to filter the fetched papers down to a target count
#
# Cron entry example (runs daily at 7:00 AM):
# 0 7 * * * /path/to/fetch_prefilter.sh >> "$HOME/cron_digest.log" 2>&1
# Make sure to replace "/path/to/fetch_prefilter.sh" with the actual path to this script on your system.
set -e
WORKSPACE="$HOME/.openclaw/workspaces/research-assistant"
cd "$WORKSPACE/pipeline"

# Activate the project environment
. .venv/bin/activate

python -m arxiv_digest.fetch
python -m arxiv_digest.prefilter
