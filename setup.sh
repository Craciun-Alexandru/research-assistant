#!/bin/sh
# setup.sh — one-time setup after cloning the repository.
#
# Creates the Python venv, installs dependencies, configures the Gemini API
# key, selects models, runs the onboarding wizard, and installs cron jobs.
#
# Usage:
#   chmod +x setup.sh && ./setup.sh

set -e

WORKSPACE="$(cd "$(dirname "$0")" && pwd)"
export ARXIV_DIGEST_WORKSPACE="$WORKSPACE"
PIPELINE="$WORKSPACE/pipeline"
PREFS="$WORKSPACE/user_preferences.json"
SCRIPTS="$WORKSPACE/scripts"
VENV_PYTHON="$PIPELINE/.venv/bin/python"
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
    EXISTING_KEY=$("$VENV_PYTHON" -c "
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
    read -r KEEP_KEY || true
    case "$KEEP_KEY" in
        [nN]*) EXISTING_KEY="" ;;
    esac
fi

API_KEY="$EXISTING_KEY"
if [ -z "$EXISTING_KEY" ]; then
    printf "Enter your Gemini API key: "
    read -r API_KEY || true
    if [ -z "$API_KEY" ]; then
        echo "Warning: No API key provided. You can set it later in user_preferences.json."
    fi
fi

if [ -n "$API_KEY" ]; then
    # Write minimal prefs file with API key
    "$VENV_PYTHON" -c "
import json, os
prefs_path = '$PREFS'
if os.path.exists(prefs_path):
    with open(prefs_path) as f:
        p = json.load(f)
else:
    p = {}
p.setdefault('llm', {})['api_key'] = '$API_KEY'
p['llm'].setdefault('provider', 'gemini')
with open(prefs_path, 'w') as f:
    json.dump(p, f, indent=2)
"
    echo "API key saved."

    # Quick verification
    echo "Verifying API key..."
    if "$VENV_PYTHON" -c "
from google import genai
c = genai.Client(api_key='$API_KEY')
r = c.models.get(model='gemini-2.0-flash')
print('OK — connected to Gemini API')
" 2>/dev/null; then
        true
    else
        echo "Warning: Could not verify API key. Check it in user_preferences.json."
    fi
fi
echo

# ── 2c. Claude API key (optional) ────────────────────────────────

echo "── Step 2c: Claude API key (optional) ──"

EXISTING_CLAUDE_KEY=""
if [ -f "$PREFS" ]; then
    EXISTING_CLAUDE_KEY=$("$VENV_PYTHON" -c "
import json
with open('$PREFS') as f:
    p = json.load(f)
k = p.get('llm', {}).get('claude_api_key', '')
if k and k != 'YOUR_ANTHROPIC_API_KEY_HERE':
    print(k)
" 2>/dev/null || true)
fi

if [ -n "$EXISTING_CLAUDE_KEY" ]; then
    echo "Claude API key already configured (starts with ${EXISTING_CLAUDE_KEY%"${EXISTING_CLAUDE_KEY#????}"}...)."
    printf "Keep existing key? [Y/n] "
    read -r KEEP_CLAUDE_KEY || true
    case "$KEEP_CLAUDE_KEY" in
        [nN]*) EXISTING_CLAUDE_KEY="" ;;
    esac
fi

CLAUDE_API_KEY="$EXISTING_CLAUDE_KEY"
if [ -z "$EXISTING_CLAUDE_KEY" ]; then
    printf "Enter your Anthropic API key (Enter to skip): "
    read -r CLAUDE_API_KEY || true
fi

if [ -n "$CLAUDE_API_KEY" ]; then
    "$VENV_PYTHON" -c "
import json, os
prefs_path = '$PREFS'
if os.path.exists(prefs_path):
    with open(prefs_path) as f:
        p = json.load(f)
else:
    p = {}
p.setdefault('llm', {})['claude_api_key'] = '$CLAUDE_API_KEY'
with open(prefs_path, 'w') as f:
    json.dump(p, f, indent=2)
"
    echo "Claude API key saved."

    echo "Verifying Claude API key..."
    if "$VENV_PYTHON" -c "
import anthropic
c = anthropic.Anthropic(api_key='$CLAUDE_API_KEY')
c.models.retrieve('claude-haiku-4-5-20251001')
print('OK — connected to Anthropic API')
" 2>/dev/null; then
        true
    else
        echo "Warning: Could not verify Claude API key. Check it in user_preferences.json."
    fi
else
    echo "Skipped. You can add it later as llm.claude_api_key in user_preferences.json."
fi
echo

# ── 2b. Model selection ───────────────────────────────────────────

echo "── Step 2b: Model selection ──"

if [ -n "$API_KEY" ]; then
    # Write model selection script to a temp file so stdin stays on the terminal
    _MODEL_SCRIPT=$(mktemp)
    trap 'rm -f "$_MODEL_SCRIPT"' EXIT
    cat > "$_MODEL_SCRIPT" << 'PYEOF'
import json
import sys

from google import genai

prefs_path = sys.argv[1]

# Read current prefs
with open(prefs_path) as f:
    prefs = json.load(f)

api_key = prefs.get("llm", {}).get("api_key", "")
if not api_key:
    print("No API key found, skipping model selection.")
    sys.exit(0)

client = genai.Client(api_key=api_key)

# Fetch available models
try:
    models_response = client.models.list()
    all_models = [m.name for m in models_response if "generateContent" in (m.supported_actions or [])]
except Exception as e:
    print(f"Could not list models: {e}")
    print("Using defaults: gemini-2.0-flash (scorer), gemini-2.5-pro (reviewer)")
    prefs["llm"]["scorer_model"] = "gemini-2.0-flash"
    prefs["llm"]["reviewer_model"] = "gemini-2.5-pro"
    with open(prefs_path, "w") as f:
        json.dump(prefs, f, indent=2)
    sys.exit(0)

# Split into flash-class and pro-class
flash_models = [m for m in all_models if "flash" in m.lower()]
pro_models = [m for m in all_models if "pro" in m.lower()]

# Scorer model (flash-class)
print("\nAvailable flash-class models (for scoring):")
for i, m in enumerate(flash_models, 1):
    # Strip "models/" prefix for display
    display = m.replace("models/", "")
    print(f"  {i}. {display}")

current_scorer = prefs.get("llm", {}).get("scorer_model", "")
if current_scorer:
    print(f"\n  Current: {current_scorer}")
    choice = input("  Pick a number (Enter to keep current): ").strip()
else:
    choice = input("  Pick a number: ").strip()

if choice.isdigit() and 1 <= int(choice) <= len(flash_models):
    selected = flash_models[int(choice) - 1].replace("models/", "")
    prefs["llm"]["scorer_model"] = selected
    print(f"  Selected: {selected}")
elif not choice and current_scorer:
    print(f"  Keeping: {current_scorer}")
else:
    default = flash_models[0].replace("models/", "") if flash_models else "gemini-2.0-flash"
    prefs["llm"]["scorer_model"] = default
    print(f"  Using default: {default}")

# Reviewer model (pro-class)
print("\nAvailable pro-class models (for deep review):")
for i, m in enumerate(pro_models, 1):
    display = m.replace("models/", "")
    print(f"  {i}. {display}")

current_reviewer = prefs.get("llm", {}).get("reviewer_model", "")
if current_reviewer:
    print(f"\n  Current: {current_reviewer}")
    choice = input("  Pick a number (Enter to keep current): ").strip()
else:
    choice = input("  Pick a number: ").strip()

if choice.isdigit() and 1 <= int(choice) <= len(pro_models):
    selected = pro_models[int(choice) - 1].replace("models/", "")
    prefs["llm"]["reviewer_model"] = selected
    print(f"  Selected: {selected}")
elif not choice and current_reviewer:
    print(f"  Keeping: {current_reviewer}")
else:
    default = pro_models[0].replace("models/", "") if pro_models else "gemini-2.5-pro"
    prefs["llm"]["reviewer_model"] = default
    print(f"  Using default: {default}")

# Save
with open(prefs_path, "w") as f:
    json.dump(prefs, f, indent=2)
print("\nModel selections saved.")
PYEOF
    "$VENV_PYTHON" "$_MODEL_SCRIPT" "$PREFS"
    rm -f "$_MODEL_SCRIPT"
else
    echo "Skipped (no API key)."
fi
echo

# ── 3. Onboarding wizard ─────────────────────────────────────────

echo "── Step 3: Research preferences ──"

if [ -n "$API_KEY" ]; then
    # Check if research preferences already exist
    HAS_RESEARCH=$("$VENV_PYTHON" -c "
import json
with open('$PREFS') as f:
    p = json.load(f)
areas = p.get('research_areas', {})
if areas:
    print('yes')
" 2>/dev/null || true)

    if [ "$HAS_RESEARCH" = "yes" ]; then
        printf "Research preferences already configured. Re-run wizard? [y/N] "
        read -r RERUN_WIZARD || true
        case "$RERUN_WIZARD" in
            [yY]*)
                "$VENV_PYTHON" -m arxiv_digest.onboard
                ;;
            *)
                echo "Keeping existing preferences."
                ;;
        esac
    else
        echo "Let's set up your research preferences..."
        echo
        "$VENV_PYTHON" -m arxiv_digest.onboard
    fi
else
    echo "Skipped (no API key). Run the wizard later with:"
    echo "  $VENV_PYTHON -m arxiv_digest.onboard"
fi
echo

# ── 4. Create resource directories ─────────────────────────────────

echo "── Step 4: Resource directories ──"
mkdir -p "$WORKSPACE/resources/papers"
mkdir -p "$WORKSPACE/resources/digests"
echo "Directories ready."
echo

# ── 5. Cron jobs ────────────────────────────────────────────────────

echo "── Step 5: Cron jobs ──"
echo
echo "The daily pipeline runs via cron at these times:"
echo "  07:00  fetch + prefilter"
echo "  07:05  score papers (Gemini Flash)"
echo "  07:10  download full texts"
echo "  07:20  deep review (Gemini Pro)"
echo "  07:59  digest + deliver"
echo

printf "Install cron jobs? [y/N] "
read -r INSTALL_CRON || true
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
echo "To re-run the preference wizard:"
echo "  $VENV_PYTHON -m arxiv_digest.onboard"
echo
echo "Or use the shell scripts in scripts/."
