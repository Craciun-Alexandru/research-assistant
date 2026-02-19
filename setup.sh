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

# ── 2. LLM provider ─────────────────────────────────────────────────

echo "── Step 2: LLM provider ──"

CURRENT_PROVIDER="gemini"
if [ -f "$PREFS" ]; then
    CURRENT_PROVIDER=$("$VENV_PYTHON" -c "
import json
with open('$PREFS') as f:
    p = json.load(f)
print(p.get('llm', {}).get('provider', 'gemini'))
" 2>/dev/null || echo "gemini")
fi

echo "  1. gemini  (Google Gemini)"
echo "  2. claude  (Anthropic Claude)"
echo "  Current: $CURRENT_PROVIDER"
printf "  Pick provider (Enter to keep current): "
read -r PROVIDER_CHOICE || true
case "$PROVIDER_CHOICE" in
    1) PROVIDER="gemini" ;;
    2) PROVIDER="claude" ;;
    *) PROVIDER="$CURRENT_PROVIDER" ;;
esac
echo "  Using: $PROVIDER"

# Save provider; clear stale model selections if it changed
"$VENV_PYTHON" -c "
import json, os
prefs_path = '$PREFS'
if os.path.exists(prefs_path):
    with open(prefs_path) as f:
        p = json.load(f)
else:
    p = {}
llm = p.setdefault('llm', {})
if llm.get('provider') != '$PROVIDER':
    llm.pop('scorer_model', None)
    llm.pop('reviewer_model', None)
llm['provider'] = '$PROVIDER'
with open(prefs_path, 'w') as f:
    json.dump(p, f, indent=2)
"
echo

# ── 2a. Active provider API key ────────────────────────────────────

if [ "$PROVIDER" = "gemini" ]; then
    echo "── Step 2a: Gemini API key ──"
    _KEY_FIELD="api_key"
    _KEY_SENTINEL="YOUR_GEMINI_API_KEY_HERE"
    _KEY_LABEL="Gemini"
    _KEY_VERIFY_PY="from google import genai; c = genai.Client(api_key='__KEY__'); c.models.get(model='gemini-2.0-flash'); print('OK — connected to Gemini API')"
else
    echo "── Step 2a: Anthropic API key ──"
    _KEY_FIELD="claude_api_key"
    _KEY_SENTINEL="YOUR_ANTHROPIC_API_KEY_HERE"
    _KEY_LABEL="Anthropic"
    _KEY_VERIFY_PY="import anthropic; c = anthropic.Anthropic(api_key='__KEY__'); c.models.retrieve('claude-haiku-4-5-20251001'); print('OK — connected to Anthropic API')"
fi

EXISTING_KEY=""
if [ -f "$PREFS" ]; then
    EXISTING_KEY=$("$VENV_PYTHON" -c "
import json
with open('$PREFS') as f:
    p = json.load(f)
k = p.get('llm', {}).get('$_KEY_FIELD', '')
if k and k != '$_KEY_SENTINEL':
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

ACTIVE_API_KEY="$EXISTING_KEY"
if [ -z "$EXISTING_KEY" ]; then
    printf "Enter your $_KEY_LABEL API key: "
    read -r ACTIVE_API_KEY || true
    if [ -z "$ACTIVE_API_KEY" ]; then
        echo "Warning: No API key provided. You can set it later in user_preferences.json."
    fi
fi

if [ -n "$ACTIVE_API_KEY" ]; then
    "$VENV_PYTHON" -c "
import json, os
prefs_path = '$PREFS'
if os.path.exists(prefs_path):
    with open(prefs_path) as f:
        p = json.load(f)
else:
    p = {}
p.setdefault('llm', {})['$_KEY_FIELD'] = '$ACTIVE_API_KEY'
with open(prefs_path, 'w') as f:
    json.dump(p, f, indent=2)
"
    echo "API key saved."
    echo "Verifying API key..."
    _VERIFY=$(echo "$_KEY_VERIFY_PY" | sed "s|__KEY__|$ACTIVE_API_KEY|g")
    if "$VENV_PYTHON" -c "$_VERIFY" 2>/dev/null; then
        true
    else
        echo "Warning: Could not verify API key. Check it in user_preferences.json."
    fi
fi
echo

# ── 2b. Other provider API key (optional) ─────────────────────────

if [ "$PROVIDER" = "gemini" ]; then
    echo "── Step 2b: Anthropic API key (optional) ──"
    _OTHER_FIELD="claude_api_key"
    _OTHER_SENTINEL="YOUR_ANTHROPIC_API_KEY_HERE"
    _OTHER_LABEL="Anthropic"
    _OTHER_VERIFY_PY="import anthropic; c = anthropic.Anthropic(api_key='__KEY__'); c.models.retrieve('claude-haiku-4-5-20251001'); print('OK — connected to Anthropic API')"
else
    echo "── Step 2b: Gemini API key (optional) ──"
    _OTHER_FIELD="api_key"
    _OTHER_SENTINEL="YOUR_GEMINI_API_KEY_HERE"
    _OTHER_LABEL="Gemini"
    _OTHER_VERIFY_PY="from google import genai; c = genai.Client(api_key='__KEY__'); c.models.get(model='gemini-2.0-flash'); print('OK — connected to Gemini API')"
fi

EXISTING_OTHER_KEY=""
if [ -f "$PREFS" ]; then
    EXISTING_OTHER_KEY=$("$VENV_PYTHON" -c "
import json
with open('$PREFS') as f:
    p = json.load(f)
k = p.get('llm', {}).get('$_OTHER_FIELD', '')
if k and k != '$_OTHER_SENTINEL':
    print(k)
" 2>/dev/null || true)
fi

if [ -n "$EXISTING_OTHER_KEY" ]; then
    echo "$_OTHER_LABEL API key already configured (starts with ${EXISTING_OTHER_KEY%"${EXISTING_OTHER_KEY#????}"}...)."
    printf "Keep existing key? [Y/n] "
    read -r KEEP_OTHER || true
    case "$KEEP_OTHER" in
        [nN]*) EXISTING_OTHER_KEY="" ;;
    esac
fi

OTHER_API_KEY="$EXISTING_OTHER_KEY"
if [ -z "$EXISTING_OTHER_KEY" ]; then
    printf "Enter your $_OTHER_LABEL API key (Enter to skip): "
    read -r OTHER_API_KEY || true
fi

if [ -n "$OTHER_API_KEY" ]; then
    "$VENV_PYTHON" -c "
import json
prefs_path = '$PREFS'
with open(prefs_path) as f:
    p = json.load(f)
p['llm']['$_OTHER_FIELD'] = '$OTHER_API_KEY'
with open(prefs_path, 'w') as f:
    json.dump(p, f, indent=2)
"
    echo "$_OTHER_LABEL API key saved."
    echo "Verifying..."
    _OTHER_VERIFY=$(echo "$_OTHER_VERIFY_PY" | sed "s|__KEY__|$OTHER_API_KEY|g")
    if "$VENV_PYTHON" -c "$_OTHER_VERIFY" 2>/dev/null; then
        true
    else
        echo "Warning: Could not verify $_OTHER_LABEL API key."
    fi
else
    echo "Skipped. You can add it later as llm.$_OTHER_FIELD in user_preferences.json."
fi
echo

# ── 2c. Model selection ───────────────────────────────────────────

echo "── Step 2c: Model selection ──"

if [ -n "$ACTIVE_API_KEY" ]; then
    # Write model selection script to a temp file so stdin stays on the terminal
    _MODEL_SCRIPT=$(mktemp)
    trap 'rm -f "$_MODEL_SCRIPT"' EXIT
    cat > "$_MODEL_SCRIPT" << 'PYEOF'
import json
import sys

prefs_path = sys.argv[1]

with open(prefs_path) as f:
    prefs = json.load(f)

llm = prefs.setdefault("llm", {})
provider = llm.get("provider", "gemini")
gemini_key = llm.get("api_key", "")
claude_key = llm.get("claude_api_key", "")


def _pick(label, models, current):
    """Print a numbered list and return the user's choice."""
    print(f"\n{label}:")
    for i, m in enumerate(models, 1):
        print(f"  {i}. {m}")
    if current:
        print(f"\n  Current: {current}")
        choice = input("  Pick a number (Enter to keep current): ").strip()
    else:
        choice = input("  Pick a number: ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(models):
        selected = models[int(choice) - 1]
        print(f"  Selected: {selected}")
        return selected
    if not choice and current:
        print(f"  Keeping: {current}")
        return current
    default = models[0] if models else None
    if default:
        print(f"  Using default: {default}")
    return default


if provider == "gemini":
    if not gemini_key:
        print("No Gemini API key configured, skipping model selection.")
        sys.exit(0)
    from google import genai
    client = genai.Client(api_key=gemini_key)
    try:
        all_models = [
            m.name for m in client.models.list()
            if "generateContent" in (m.supported_actions or [])
        ]
    except Exception as e:
        print(f"Could not list Gemini models: {e}")
        llm.setdefault("scorer_model", "gemini-2.0-flash")
        llm.setdefault("reviewer_model", "gemini-2.5-pro")
        with open(prefs_path, "w") as f:
            json.dump(prefs, f, indent=2)
        sys.exit(0)

    flash = [m.replace("models/", "") for m in all_models if "flash" in m.lower()]
    pro   = [m.replace("models/", "") for m in all_models if "pro"   in m.lower()]

    scorer   = _pick("Available flash-class models (for scoring)",   flash, llm.get("scorer_model", ""))
    reviewer = _pick("Available pro-class models (for deep review)", pro,   llm.get("reviewer_model", ""))
    llm["scorer_model"]   = scorer   or "gemini-2.0-flash"
    llm["reviewer_model"] = reviewer or "gemini-2.5-pro"

elif provider == "claude":
    if not claude_key:
        print("No Claude API key configured, skipping model selection.")
        sys.exit(0)
    import anthropic
    client = anthropic.Anthropic(api_key=claude_key)
    try:
        all_ids = [m.id for m in client.models.list()]
    except Exception as e:
        print(f"Could not list Claude models: {e}")
        llm.setdefault("scorer_model", "claude-haiku-4-5-20251001")
        llm.setdefault("reviewer_model", "claude-sonnet-4-6")
        with open(prefs_path, "w") as f:
            json.dump(prefs, f, indent=2)
        sys.exit(0)

    fast     = [m for m in all_ids if "haiku"  in m.lower() or "sonnet" in m.lower()]
    powerful = [m for m in all_ids if "sonnet" in m.lower() or "opus"   in m.lower()]

    scorer   = _pick("Available fast models (for scoring)",          fast,     llm.get("scorer_model", ""))
    reviewer = _pick("Available powerful models (for deep review)",  powerful, llm.get("reviewer_model", ""))
    llm["scorer_model"]   = scorer   or "claude-haiku-4-5-20251001"
    llm["reviewer_model"] = reviewer or "claude-sonnet-4-6"

with open(prefs_path, "w") as f:
    json.dump(prefs, f, indent=2)
print("\nModel selections saved.")
PYEOF
    "$VENV_PYTHON" "$_MODEL_SCRIPT" "$PREFS"
    rm -f "$_MODEL_SCRIPT"
else
    echo "Skipped (no active API key configured)."
fi
echo

# ── 3. Onboarding wizard ─────────────────────────────────────────

echo "── Step 3: Research preferences ──"

if [ -n "$ACTIVE_API_KEY" ]; then
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
    echo "Skipped (no API key configured). Run the wizard later with:"
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
echo "  07:05  score papers (LLM scorer)"
echo "  07:10  download full texts"
echo "  07:20  deep review (LLM reviewer)"
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
