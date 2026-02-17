#!/bin/sh
# setup.sh — one-time setup after cloning the repository.
#
# Creates the Python venv, installs dependencies, configures the Gemini API
# key, and installs cron jobs for the daily pipeline.
#
# Usage:
#   chmod +x setup.sh && ./setup.sh

set -e

WORKSPACE="$(cd "$(dirname "$0")" && pwd)"
PIPELINE="$WORKSPACE/pipeline"
PREFS="$WORKSPACE/user_preferences.json"
SCRIPTS="$WORKSPACE/scripts"
LOG="\$HOME/cron_digest.log"

echo "========================================"
echo "  arXiv Digest Pipeline — Setup"
echo "========================================"
echo
echo "Workspace: $WORKSPACE"
echo

# ── 1. Python venv ──────────────────────────────────────────────────

echo "── Step 1: Python environment ──"
if [ -d "$PIPELINE/.venv" ]; then
    echo "Venv already exists at $PIPELINE/.venv"
else
    echo "Creating venv..."
    python3 -m venv "$PIPELINE/.venv"
    echo "Venv created."
fi

echo "Installing dependencies..."
"$PIPELINE/.venv/bin/pip" install --upgrade pip -q
"$PIPELINE/.venv/bin/pip" install -e "$PIPELINE[dev]" -q
echo "Dependencies installed."
echo

# ── 2. Gemini API key ──────────────────────────────────────────────

echo "── Step 2: Gemini API key ──"

# Check if key is already set in preferences
EXISTING_KEY=""
if [ -f "$PREFS" ]; then
    EXISTING_KEY=$(python3 -c "
import json
with open('$PREFS') as f:
    p = json.load(f)
k = p.get('llm', {}).get('api_key', '')
if k and k != 'YOUR_GEMINI_API_KEY_HERE':
    print(k)
" 2>/dev/null || true)
fi

if [ -n "$EXISTING_KEY" ]; then
    echo "API key already configured (starts with ${EXISTING_KEY%"${EXISTING_KEY#????}"}...)."
    printf "Keep existing key? [Y/n] "
    read -r KEEP_KEY
    case "$KEEP_KEY" in
        [nN]*) EXISTING_KEY="" ;;
    esac
fi

if [ -z "$EXISTING_KEY" ]; then
    printf "Enter your Gemini API key: "
    read -r API_KEY
    if [ -z "$API_KEY" ]; then
        echo "Warning: No API key provided. You can set it later in user_preferences.json."
    else
        # Write key into user_preferences.json
        python3 -c "
import json
with open('$PREFS') as f:
    p = json.load(f)
p.setdefault('llm', {})['api_key'] = '$API_KEY'
with open('$PREFS', 'w') as f:
    json.dump(p, f, indent=2)
"
        echo "API key saved to user_preferences.json."

        # Quick verification
        echo "Verifying API key..."
        if "$PIPELINE/.venv/bin/python" -c "
from arxiv_digest.config import load_llm_config
from arxiv_digest.llm import create_client
cfg = load_llm_config()
c = create_client(cfg['provider'], api_key=cfg['api_key'])
r = c._client.models.get(model='gemini-2.0-flash')
print('OK — connected to Gemini API')
" 2>/dev/null; then
            true
        else
            echo "Warning: Could not verify API key. Check it in user_preferences.json."
        fi
    fi
fi
echo

# ── 3. Create resource directories ─────────────────────────────────

echo "── Step 3: Resource directories ──"
mkdir -p "$WORKSPACE/resources/papers"
mkdir -p "$WORKSPACE/resources/digests"
echo "Directories ready."
echo

# ── 4. Cron jobs ────────────────────────────────────────────────────

echo "── Step 4: Cron jobs ──"
echo
echo "The daily pipeline runs via cron at these times:"
echo "  07:00  fetch + prefilter"
echo "  07:05  score papers (Gemini Flash)"
echo "  07:10  download full texts"
echo "  07:20  deep review (Gemini Pro)"
echo "  07:59  digest + deliver"
echo

printf "Install cron jobs? [y/N] "
read -r INSTALL_CRON
case "$INSTALL_CRON" in
    [yY]*)
        # Build cron block
        CRON_BLOCK="# ── arXiv Digest Pipeline ──
00 07 * * * \"$SCRIPTS/fetch_prefilter.sh\" >> $LOG 2>&1
05 07 * * * \"$SCRIPTS/score_papers.sh\" >> $LOG 2>&1
10 07 * * * \"$SCRIPTS/download_papers.sh\" >> $LOG 2>&1
20 07 * * * \"$SCRIPTS/review_papers.sh\" >> $LOG 2>&1
59 07 * * * \"$SCRIPTS/digest_deliver.sh\" >> $LOG 2>&1
# ── End arXiv Digest Pipeline ──"

        # Remove any existing arXiv digest entries, then append
        EXISTING_CRON=$(crontab -l 2>/dev/null || true)
        CLEANED_CRON=$(echo "$EXISTING_CRON" | sed '/# ── arXiv Digest Pipeline/,/# ── End arXiv Digest Pipeline/d' | sed '/arxiv_digest\|fetch_prefilter\|score_papers\|download_papers\|review_papers\|digest_deliver/d')

        # Write new crontab
        echo "$CLEANED_CRON
$CRON_BLOCK" | crontab -
        echo "Cron jobs installed."
        ;;
    *)
        echo "Skipped. You can install them later by running:"
        echo "  crontab -e"
        ;;
esac
echo

# ── Done ────────────────────────────────────────────────────────────

echo "========================================"
echo "  Setup complete!"
echo "========================================"
echo
echo "To run the pipeline manually:"
echo "  cd $PIPELINE"
echo "  . .venv/bin/activate"
echo "  python -m arxiv_digest.fetch"
echo "  python -m arxiv_digest.prefilter"
echo "  python -m arxiv_digest.scorer"
echo "  python -m arxiv_digest.download"
echo "  python -m arxiv_digest.reviewer --delay 5"
echo "  python -m arxiv_digest.digest"
echo "  python -m arxiv_digest.deliver"
echo
echo "Or use the shell scripts in scripts/."
