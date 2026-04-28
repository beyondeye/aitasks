#!/usr/bin/env bash
# aitask_remote_drift_check.sh - Detect remote-branch drift after planning.
#
# Compares local <base-branch> against origin/<base-branch> and reports
# whether any remote-only commits touch files referenced in the plan.
# Best-effort: never fails the workflow. Outputs structured lines on stdout
# that the calling skill (.claude/skills/task-workflow/remote-drift-check.md)
# parses.
#
# Output protocol (one line per item, in order):
#   LEGACY_MODE_SKIP            Task data is on the same branch as code; task_sync()
#                               already pulled it. No drift to detect.
#   NO_REMOTE                   No 'origin' remote configured.
#   FETCH_FAILED                git fetch failed (timeout, auth, network, etc.).
#   UP_TO_DATE                  Remote has zero commits ahead of local.
#   AHEAD:<n>                   Remote is <n> commits ahead. Followed by either:
#     OVERLAP:<file>            (zero or more) one per remote-changed file
#                               that is also referenced in the plan.
#     NO_OVERLAP                emitted exactly once when no OVERLAP lines.
#
# Exit code: always 0 unless invalid CLI args.
#
# Used by:
#   .claude/skills/task-workflow/remote-drift-check.md (post-plan checkpoint)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

# --- Defaults ---
NETWORK_TIMEOUT=10
DEBUG=false
BASE_BRANCH=""
PLAN_FILE=""

show_help() {
    cat <<'EOF'
Usage: aitask_remote_drift_check.sh [--debug] [--timeout <sec>] <base-branch> <plan-file>

Detects whether origin/<base-branch> has commits not yet on local
<base-branch>, with emphasis on commits that touch files referenced in
the supplied plan file.

Arguments:
  <base-branch>     Code-branch name (e.g., main).
  <plan-file>       Path to the externalized plan markdown file.

Options:
  --timeout <sec>   Network operation timeout. Default: 10.
  --debug           Print debug info to stderr.
  --help, -h        Show this help.

Output (always exit 0; structured stdout):
  LEGACY_MODE_SKIP
  NO_REMOTE
  FETCH_FAILED
  UP_TO_DATE
  AHEAD:<n>
  OVERLAP:<file>     (zero or more, after AHEAD)
  NO_OVERLAP         (after AHEAD, when no OVERLAP lines)
EOF
}

debug() {
    if [[ "$DEBUG" == true ]]; then
        echo "[debug] $*" >&2
    fi
}

# --- Argument parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --debug)   DEBUG=true; shift ;;
        --timeout) NETWORK_TIMEOUT="${2:?--timeout requires a value}"; shift 2 ;;
        --help|-h) show_help; exit 0 ;;
        --*)       die "Unknown option: $1. Use --help for usage." ;;
        *)
            if [[ -z "$BASE_BRANCH" ]]; then
                BASE_BRANCH="$1"
            elif [[ -z "$PLAN_FILE" ]]; then
                PLAN_FILE="$1"
            else
                die "Unexpected positional arg: $1. Use --help for usage."
            fi
            shift
            ;;
    esac
done

[[ -z "$BASE_BRANCH" ]] && die "<base-branch> is required. Use --help for usage."
[[ -z "$PLAN_FILE" ]] && die "<plan-file> is required. Use --help for usage."

# --- Legacy-mode short-circuit ---
_ait_detect_data_worktree
if [[ "$_AIT_DATA_WORKTREE" == "." ]]; then
    debug "legacy mode: task data on same branch as code, task_sync() already pulled"
    echo "LEGACY_MODE_SKIP"
    exit 0
fi

# --- Remote check ---
if ! git remote get-url origin &>/dev/null; then
    debug "no 'origin' remote configured"
    echo "NO_REMOTE"
    exit 0
fi

# --- Portable timeout wrapper for git fetch ---
# Uses coreutils `timeout` if available; falls back to a background watchdog
# (macOS BSD does not ship timeout). Returns 124 on timeout, mirroring
# aitask_sync.sh:_git_with_timeout.
_git_fetch_with_timeout() {
    if command -v timeout &>/dev/null; then
        timeout "$NETWORK_TIMEOUT" git fetch --quiet origin "$BASE_BRANCH"
    else
        git fetch --quiet origin "$BASE_BRANCH" &
        local pid=$!
        local i=0
        while kill -0 "$pid" 2>/dev/null && [[ $i -lt $NETWORK_TIMEOUT ]]; do
            sleep 1
            i=$((i + 1))
        done
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
            return 124
        fi
        wait "$pid"
    fi
}

debug "fetching origin/$BASE_BRANCH (timeout ${NETWORK_TIMEOUT}s)"
fetch_exit=0
_git_fetch_with_timeout 2>/dev/null || fetch_exit=$?
if [[ $fetch_exit -ne 0 ]]; then
    debug "fetch failed with exit code $fetch_exit"
    echo "FETCH_FAILED"
    exit 0
fi

# --- Compute remote-ahead count ---
ahead=""
ahead=$(git rev-list --count "${BASE_BRANCH}..origin/${BASE_BRANCH}" 2>/dev/null) || ahead=""

if [[ -z "$ahead" ]]; then
    debug "rev-list failed (local '$BASE_BRANCH' likely missing)"
    echo "FETCH_FAILED"
    exit 0
fi

if [[ "$ahead" -eq 0 ]]; then
    debug "local $BASE_BRANCH is up to date with origin"
    echo "UP_TO_DATE"
    exit 0
fi

echo "AHEAD:$ahead"

# --- Files touched by remote-only commits ---
remote_files=""
remote_files=$(git diff --name-only "${BASE_BRANCH}..origin/${BASE_BRANCH}" 2>/dev/null) || remote_files=""

if [[ -z "$remote_files" ]]; then
    debug "no remote-only file changes found"
    echo "NO_OVERLAP"
    exit 0
fi

# --- Plan-referenced paths ---
# Step 1: pull every token shaped like a relative path with a known extension.
# Step 2: keep only those rooted in one of our project subdirectories.
# Step 3: strip leading './' and dedupe.
plan_paths=""
if [[ -r "$PLAN_FILE" ]]; then
    plan_paths=$(grep -oE '[A-Za-z0-9_./-]+\.(sh|py|md|yaml|yml|json|toml)' "$PLAN_FILE" 2>/dev/null \
        | grep -E '^(\.?/)?\.?(aitask-scripts|aitasks|aiplans|claude/skills|opencode/skills|gemini/skills|agents/skills|website|seed|tests)/' \
        | sed 's|^\./||' \
        | sort -u || true)
fi

debug "plan-referenced paths:"
debug "$plan_paths"

# --- Intersect ---
overlap_count=0
if [[ -n "$plan_paths" ]]; then
    plan_tmp=$(mktemp "${TMPDIR:-/tmp}/aitask_drift_plan_XXXXXX")
    remote_tmp=$(mktemp "${TMPDIR:-/tmp}/aitask_drift_remote_XXXXXX")
    trap 'rm -f "$plan_tmp" "$remote_tmp"' EXIT
    printf '%s\n' "$plan_paths" > "$plan_tmp"
    printf '%s\n' "$remote_files" | sed 's|^\./||' | sort -u > "$remote_tmp"

    # grep -F -x -f: fixed-string, full-line, patterns from file. Empty lines
    # in either input are filtered out via the `-v ^$` filter on the result.
    while IFS= read -r overlap; do
        [[ -z "$overlap" ]] && continue
        echo "OVERLAP:$overlap"
        overlap_count=$((overlap_count + 1))
    done < <(grep -Fxf "$plan_tmp" "$remote_tmp" 2>/dev/null || true)
fi

if [[ $overlap_count -eq 0 ]]; then
    echo "NO_OVERLAP"
fi

exit 0
