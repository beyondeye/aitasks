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
#   AHEAD:<n>                   Remote is <n> commits ahead. Followed by, in order:
#     OVERLAP:<file>            (zero or more) a remote-changed file the plan
#                               references by its full path (strong).
#     WEAK_OVERLAP:<file>       (zero or more) a remote-changed file the plan
#                               references only weakly: an extensionless
#                               root-level name (`ait`, `Makefile` -- the same
#                               word is ordinary prose), or a module-relative
#                               trailing sub-path. Evidence, never a verdict.
#     NO_OVERLAP                emitted exactly once when there is no OVERLAP
#                               line (WEAK_OVERLAP lines do not suppress it, so a
#                               parser that ignores them sees the same verdict).
#   EXTRACT_FAILED              The plan reference scan could not run
#                               (lib/plan_paths.py unreachable, or the plan file
#                               unreadable). Emitted INSTEAD of any
#                               OVERLAP/NO_OVERLAP verdict, with a non-zero exit,
#                               because "references nothing" and "could not scan"
#                               are the same shape -- an empty set -- and
#                               reporting the latter as NO_OVERLAP is a false
#                               all-clear on the pick hot path. A failure to LIST
#                               the remote-changed files (the `git diff`) is
#                               different: it keeps its best-effort meaning and
#                               reports NO_OVERLAP with exit 0.
#
# Exit code: 0 unless invalid CLI args (2) or scan failure (3).
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
  OVERLAP:<file>       (zero or more, after AHEAD) full-path plan reference
  WEAK_OVERLAP:<file>  (zero or more, after OVERLAP) bare-name or
                       module-relative plan reference; evidence only
  NO_OVERLAP           (after AHEAD, when no OVERLAP lines)
  EXTRACT_FAILED       (exit 3) the plan reference scan could not run
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
# THREE dots, deliberately. In `git diff` (unlike `git log`) `A..B` is plain
# `git diff A B` -- an endpoint-to-endpoint comparison that also reports files
# changed only by the user's OWN local commits. `A...B` diffs from the merge
# base, which is what "files the remote changed" actually means. Inflating
# OVERLAP -- the strong half of this check -- with the user's landed work is the
# cry-wolf failure that trains the user to click past a real hit (t1724).
# (The AHEAD count above uses `git rev-list`, where two dots ARE a commit range
# and are correct.)
#
# `-z` into a file: the list reaches the reference scan NUL-delimited, so a path
# containing a newline cannot split a record (bash cannot hold NUL in a
# variable). A failed diff keeps its best-effort meaning -- no remote file list,
# so NO_OVERLAP with exit 0 -- and is deliberately NOT the fail-closed
# EXTRACT_FAILED below, which is about the PLAN scan. `|| diff_rc=$?` keeps the
# failure away from errexit, which would otherwise end the script right after
# AHEAD with no verdict at all.
remote_tmp=$(mktemp "${TMPDIR:-/tmp}/aitask_drift_remote_XXXXXX") || {
    debug "mktemp failed: cannot list remote file changes"
    echo "NO_OVERLAP"
    exit 0
}
trap 'rm -f "$remote_tmp"' EXIT
diff_rc=0
git diff --name-only -z "${BASE_BRANCH}...origin/${BASE_BRANCH}" > "$remote_tmp" 2>/dev/null || diff_rc=$?
if [[ $diff_rc -ne 0 ]]; then
    debug "git diff failed ($diff_rc): treating as no remote file changes"
    echo "NO_OVERLAP"
    exit 0
fi
if [[ ! -s "$remote_tmp" ]]; then
    debug "no remote-only file changes found"
    echo "NO_OVERLAP"
    exit 0
fi

# --- Plan references to the remote-changed files ---
# The inverted search (t1877): each remote-changed path, byte for byte as git
# named it, is tested for a reference in the plan -- plan_paths.reference_kinds()
# through the lazy bridge sourced above. There is no filename grammar and no
# extension list, so a Go/Rust/TS source or an extensionless `src/Makefile` is
# found, and `x/SKILL.md.j2` no longer yields a false `x/SKILL.md`. Delimiters,
# NFC normalization and undecodable bytes follow
# aidocs/framework/plan_path_reference_extraction_findings.md sections 3-5; the
# measured impact of switching is its section 7.
#
# Tiers: `full` -> OVERLAP (strong). `bare` (an extensionless root-level name)
# and `suffix` (a module-relative sub-path) -> WEAK_OVERLAP, evidence only: the
# measurement showed the bare word `ait` in prose alone would otherwise raise the
# strong-overlap rate by ~11 points in this repository.
refs=""
# `-e || -L` rather than `-r`: a plan that EXISTS but cannot be read (mode 000,
# a broken symlink, another user's file) must reach the scan and fail closed.
# A `-r` test would skip the block and print NO_OVERLAP with exit 0 -- the false
# all-clear this path exists to prevent. A plan file that is genuinely ABSENT
# keeps the pre-existing behaviour: no references, no overlap claim of its own.
if [[ -e "$PLAN_FILE" || -L "$PLAN_FILE" ]]; then
    scan_rc=0
    refs=$(plan_paths_references "$PLAN_FILE" < "$remote_tmp") || scan_rc=$?
    if [[ $scan_rc -ne 0 ]]; then
        # FAIL CLOSED. Falling through with an empty set would print NO_OVERLAP,
        # which is indistinguishable from a genuine all-clear.
        echo "EXTRACT_FAILED"
        exit 3
    fi
fi

debug "plan references (kind<TAB>path):"
debug "$refs"

# --- Verdict ---
strong=()
weak=()
while IFS=$'\t' read -r kind path; do
    [[ -z "$path" ]] && continue
    case "$kind" in
        full) strong+=("$path") ;;
        *)    weak+=("$path") ;;
    esac
done <<< "$refs"

for path in ${strong[@]+"${strong[@]}"}; do
    echo "OVERLAP:$path"
done
for path in ${weak[@]+"${weak[@]}"}; do
    echo "WEAK_OVERLAP:$path"
done
if [[ ${#strong[@]} -eq 0 ]]; then
    echo "NO_OVERLAP"
fi

exit 0
