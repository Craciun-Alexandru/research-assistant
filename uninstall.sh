#!/bin/sh
# uninstall.sh — remove the arXiv digest pipeline.
#
# Removes cron jobs and deletes the workspace directory.
#
# Usage:
#   ./uninstall.sh

set -e

WORKSPACE="$(cd "$(dirname "$0")" && pwd)"

echo "========================================"
echo "  arXiv Digest Pipeline — Uninstall"
echo "========================================"
echo
echo "This will:"
echo "  1. Remove arXiv digest cron jobs"
echo "  2. Delete the entire workspace at:"
echo "     $WORKSPACE"
echo
printf "Are you sure? [y/N] "
read -r CONFIRM
case "$CONFIRM" in
    [yY]*) ;;
    *)
        echo "Cancelled."
        exit 0
        ;;
esac
echo

# ── 1. Remove cron jobs ───────────────────────────────────────────

echo "Removing cron jobs..."
EXISTING_CRON=$(crontab -l 2>/dev/null || true)
if echo "$EXISTING_CRON" | grep -q "arXiv Digest Pipeline"; then
    CLEANED_CRON=$(echo "$EXISTING_CRON" \
        | sed '/# ── arXiv Digest Pipeline/,/# ── End arXiv Digest Pipeline/d' \
        | sed '/arxiv_digest\|fetch_prefilter\|score_papers\|download_papers\|review_papers\|digest_deliver/d')
    echo "$CLEANED_CRON" | crontab -
    echo "Cron jobs removed."
else
    echo "No cron jobs found."
fi
echo

# ── 2. Delete workspace ──────────────────────────────────────────

echo "Deleting workspace..."
rm -rf "$WORKSPACE"
echo "Done. Workspace deleted."
