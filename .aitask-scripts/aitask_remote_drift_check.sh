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
#                               Suppressed by --unsynced.
#   LOCAL_BRANCH_MISSING        refs/heads/<branch> does not exist locally. Checked
#                               before any network access, so this never conflates
#                               with a fetch failure. For the Step 9 output branch
#                               this means the merge is guaranteed to fail.
#   NO_REMOTE                   No 'origin' remote configured.
#   FETCH_FAILED                git fetch failed (timeout, auth, network, etc.).
#                               Means only "could not reach the remote" — it is
#                               NOT evidence about the local branch.
#   UP_TO_DATE                  Remote has zero commits ahead of local.
#   AHEAD:<n>                   Remote is <n> commits ahead. Followed by either:
#     OVERLAP:<file>            (zero or more) one per remote-changed file
#                               that is also referenced in the plan.
#     NO_OVERLAP                emitted exactly once when no OVERLAP lines.
#   EXTRACT_FAILED              Plan-path extraction could not run (lib/plan_paths.py
#                               unreachable, or the plan file unreadable). Emitted
#                               INSTEAD of any OVERLAP/NO_OVERLAP verdict, with a
#                               non-zero exit, because "extracted nothing" and
#                               "could not extract" are the same shape -- an empty
#                               set -- and reporting the latter as NO_OVERLAP is a
#                               false all-clear on the pick hot path.
#
# Exit code: 0 unless invalid CLI args (2) or extraction failure (3).
#
# Used by:
#   .claude/skills/task-workflow/remote-drift-check.md (post-plan checkpoint)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/plan_paths_sh.sh
source "$SCRIPT_DIR/lib/plan_paths_sh.sh"

# --- Defaults ---
NETWORK_TIMEOUT=10
DEBUG=false
BASE_BRANCH=""
PLAN_FILE=""
UNSYNCED=false

show_help() {
    cat <<'EOF'
Usage: aitask_remote_drift_check.sh [--debug] [--timeout <sec>] [--unsynced]
                                    <base-branch> <plan-file>

Detects whether origin/<base-branch> has commits not yet on local
<base-branch>, with emphasis on commits that touch files referenced in
the supplied plan file.

Arguments:
  <base-branch>     Code-branch name (e.g., main).
  <plan-file>       Path to the externalized plan markdown file.
  --unsynced        Skip the legacy-mode short-circuit. Pass this for a branch
                    the workflow has not pulled (the task-workflow Step 9 output
                    branch is never checked out during implementation), where
                    the shortcut's premise -- task_sync() already refreshed this
                    branch -- does not hold. In legacy mode task_sync() runs a
                    bare `git pull --rebase`, refreshing only the CURRENT branch.

Options:
  --timeout <sec>   Network operation timeout. Default: 10.
  --debug           Print debug info to stderr.
  --help, -h        Show this help.

Output (always exit 0; structured stdout):
  LEGACY_MODE_SKIP
  LOCAL_BRANCH_MISSING   refs/heads/<branch> absent; checked before any network
                         access, so it never conflates with a fetch failure
  NO_REMOTE
  FETCH_FAILED           could not reach the remote; NOT evidence about the
                         local branch
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
        --debug)    DEBUG=true; shift ;;
        --unsynced) UNSYNCED=true; shift ;;
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
# Premise: in legacy mode task_sync() already pulled this branch. That holds for
# the branch being worked on, but NOT for a branch the workflow never checks out
# (task_sync() runs a bare `git pull --rebase`, i.e. the current branch only) --
# hence --unsynced.
_ait_detect_data_worktree
if [[ "$_AIT_DATA_WORKTREE" == "." && "$UNSYNCED" != true ]]; then
    debug "legacy mode: task data on same branch as code, task_sync() already pulled"
    echo "LEGACY_MODE_SKIP"
    exit 0
fi

# --- Local branch existence (network-independent) ---
# Deliberately BEFORE the origin/fetch checks: a repo with no remote and no local
# branch is still a guaranteed merge failure, and letting NO_REMOTE/FETCH_FAILED
# win there would return silently and lose the signal. Fully-qualified so a tag
# of the same name cannot satisfy it (gitrevisions ranks refs/tags above
# refs/heads).
if ! git rev-parse --verify --quiet "refs/heads/${BASE_BRANCH}" >/dev/null 2>&1; then
    debug "local branch refs/heads/$BASE_BRANCH does not exist"
    echo "LOCAL_BRANCH_MISSING"
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
    # Local-branch absence is caught earlier by LOCAL_BRANCH_MISSING, so this is
    # the defensive case: origin/<branch> absent after an apparently OK fetch.
    debug "rev-list failed (origin/'$BASE_BRANCH' missing after fetch)"
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
# Step 2: strip leading './' and dedupe.
#
# There is deliberately NO allowlist of directory roots. OVERLAP is produced by
# an exact full-line intersection with the remote-changed file list below, so a
# token that is not a real remote-changed path is discarded there anyway: a root
# filter can only remove TRUE positives, never false ones. The list removed here
# was this repository's own top-level directories, which made the overlap signal
# -- the strong half of the drift check -- unreachable in every consumer project,
# and missed aidocs/ even here (t1275).
#
# The extension list is a KNOWN remaining narrowing, deliberately left in place:
# a plan referencing internal/pkg/server.go still yields zero tokens. See
# aidocs/framework/plan_path_reference_extraction_findings.md.
#
# The grammar itself lives in lib/plan_paths.py and is reached through the
# lazy bridge sourced above -- it has three other consumers (lib/trail_gather.py
# and t1569_3's admission checker among them) and forking it would guarantee
# divergence on exactly the edges that document records. The extractor sorts in
# codepoint order where this pipeline used locale-collated `sort -u`; the
# intersect below is `grep -Fxf`, which is order-independent, so the emitted
# OVERLAP order can differ while no verdict does (t1569_1).
plan_paths=""
# `-e || -L` rather than `-r`: a plan that EXISTS but cannot be read (mode 000,
# a broken symlink, another user's file) must reach the extractor and fail
# closed. The former `-r` test intercepted precisely the case the header names,
# skipping the block and printing NO_OVERLAP with exit 0 -- the false all-clear
# this path exists to prevent. A plan file that is genuinely ABSENT keeps the
# pre-existing behaviour: no paths, no overlap claim of its own.
if [[ -e "$PLAN_FILE" || -L "$PLAN_FILE" ]]; then
    extract_rc=0
    plan_paths=$(plan_paths_extract "$PLAN_FILE") || extract_rc=$?
    if [[ $extract_rc -ne 0 ]]; then
        # FAIL CLOSED. Falling through with an empty set would print NO_OVERLAP,
        # which is indistinguishable from a genuine all-clear.
        echo "EXTRACT_FAILED"
        exit 3
    fi
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
