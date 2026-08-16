#!/usr/bin/env bash
# aitask_change_surface.sh - Per-task attribution of a repository's change surface
#
# Answers "which files did task t<id> change?" on a checkout that may hold
# several tasks' work at once. Replaces the raw `git diff --name-only HEAD` a
# consumer would otherwise run, which returns the ENTIRE dirty tree with no way
# to tell whose work it is (t1263).
#
# ---------------------------------------------------------------------------
# OWNERSHIP SIGNALS
#
#   P1  commit tag     proven positive   path is in a commit tagged (t<id>)
#   P2  plan scope     declared positive the task's own plan file names the path
#   N1  claim baseline proven negative   path was already dirty at claim time
#
# Nothing else attributes. A path with no positive signal is UNKNOWN and is the
# caller's to escalate -- never silently in scope.
#
# WHY N1 ALONE IS NOT ATTRIBUTION. A claim-time snapshot answers exactly one
# question: was this path already dirty before the task started? "Yes" is a
# proven negative. It cannot produce a positive:
#
#   t1 claims -> baseline = {}        # nothing dirty yet
#   t1 edits a.md
#   t2 claims -> baseline = {a.md}
#   t2 edits b.md                     # concurrent session, AFTER t1's claim
#   list 1    -> dirty = {a.md, b.md}, baseline(t1) = {} => BOTH look "new"
#
# b.md is indistinguishable from a.md by baseline alone, so the positive must
# come from P1 or P2 and everything else lands in UNKNOWN.
#
# RESIDUAL LIMITS (documented, not papered over):
#   - P2 is DECLARED, not proven. A concurrent edit to a file the plan happens
#     to name by exact path is classified TASK. Narrower than "any dirty file",
#     but real -- consumers should show the attributed set, not just UNKNOWN.
#   - Work the plan never named by exact path lands in UNKNOWN and needs
#     confirmation. Over-escalation is recoverable; false attribution is not.
#   - Worktree isolation is deliberately NOT a signal. That a tree is a linked
#     worktree on an aitask/* branch is an INFERENCE about how it was created,
#     not a proof: a reused or hand-made worktree can hold foreign dirt, and
#     trusting it would bypass the UNKNOWN escalation entirely. Proving it needs
#     framework-created-worktree metadata written at `git worktree add` time.
# ---------------------------------------------------------------------------
#
# All subcommands exit 0. Use output lines (not exit codes) for status.
#
# Usage:
#   ./.aitask-scripts/aitask_change_surface.sh capture <task-id>
#   ./.aitask-scripts/aitask_change_surface.sh list <task-id>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/atomic_write.sh
source "$SCRIPT_DIR/lib/atomic_write.sh"

# Task/plan data paths are never part of a CODE change surface. Canonical site
# for this value set is `_DIGEST_EXCLUDES` in lib/gate_ledger.py (the code-state
# digest uses the same three); tests/test_change_surface.sh pins the two lists
# against each other so they cannot silently diverge.
EXCLUDES=(':(exclude)aitasks/**' ':(exclude)aiplans/**' ':(exclude).aitask-data/**')

BASELINE_ROOT="${AIT_CHANGE_SURFACE_DIR:-.aitask-gates}"

# Our own ephemeral state (baselines, gate sidecar logs). Separate from
# EXCLUDES above -- that array mirrors gate_ledger's canonical set and is
# drift-guarded against it; this one is this script's own bookkeeping. Normally
# redundant (`ait setup` gitignores .aitask-gates/, so --exclude-standard drops
# it), but a project that has not been through that step would otherwise see the
# baseline file reported as part of its own change surface.
SELF_EXCLUDES=(":(exclude)${BASELINE_ROOT}/**")

# --- Help ---
show_help() {
    cat <<'EOF'
Usage: aitask_change_surface.sh <subcommand> <task-id>

Classify a repository's change surface by which task each path belongs to.

Subcommands:
  capture <task-id>   Snapshot the working tree's dirty set as this task's
                      claim-time baseline (signal N1). Call once, at claim.
  list <task-id>      Print the task's classified change surface.

`capture` output:
  CAPTURED:<n>              baseline written, <n> paths recorded
  CAPTURE_SKIPPED:<reason>  no baseline written (not_a_repo | no_commits)

`list` output -- two header lines, then one line per path:
  BASELINE:ok|missing|foreign     was signal N1 available?
  PLANSCOPE:ok|missing            was signal P2 available?
  COMMITTED:<path>   proven this task's (in a commit tagged (t<id>))
  TASK:<path>        declared this task's (named by the task's own plan)
  OTHER:<path>       proven other work (already dirty when this task claimed)
  UNKNOWN:<path>     no positive signal, or signals conflict -- ESCALATE

Both headers are always printed: a missing signal is its own state, not a
silent negative. Do NOT read PLANSCOPE:missing as "nothing is this task's".
EOF
}

# --- Baseline path -----------------------------------------------------------
baseline_file() {
    printf '%s/%s/change_baseline\n' "$BASELINE_ROOT" "$1"
}

# --- git helpers -------------------------------------------------------------

# Dirty ∪ untracked, repo-relative, excluding task/plan data. Prints nothing
# when git is unavailable or the tree is clean.
#
# The trailing `|| true` is load-bearing: on a clean tree `grep -v '^$'` finds
# no lines and exits 1, and under `set -o pipefail` that failure propagates out
# of the command substitution and kills the caller with no message at all
# (shell_conventions.md, "silent set -e aborts via $(...) capture").
current_dirty_set() {
    {
        git diff --name-only HEAD -- . "${EXCLUDES[@]}" "${SELF_EXCLUDES[@]}" 2>/dev/null || true
        git ls-files --others --exclude-standard -- . "${EXCLUDES[@]}" "${SELF_EXCLUDES[@]}" 2>/dev/null || true
    } | sed 's|^\./||' | grep -v '^$' | sort -u || true
}

# --- capture -----------------------------------------------------------------
cmd_capture() {
    local task_id="${1:-}"
    [[ -n "$task_id" ]] || die "Usage: aitask_change_surface.sh capture <task-id>"

    local toplevel head
    toplevel="$(git rev-parse --show-toplevel 2>/dev/null || true)"
    if [[ -z "$toplevel" ]]; then
        echo "CAPTURE_SKIPPED:not_a_repo"
        return 0
    fi
    head="$(git rev-parse HEAD 2>/dev/null || true)"
    if [[ -z "$head" ]]; then
        # An unborn HEAD has no diff base; the baseline would be meaningless.
        echo "CAPTURE_SKIPPED:no_commits"
        return 0
    fi

    local paths count content
    paths="$(current_dirty_set)"
    count=0
    [[ -n "$paths" ]] && count="$(printf '%s\n' "$paths" | wc -l | tr -d ' ')"

    local dest
    dest="$(baseline_file "$task_id")"
    mkdir -p "$(dirname "$dest")"

    content="version=1
task=${task_id}
toplevel=${toplevel}
head=${head}
captured_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
paths:
${paths}"

    ait_atomic_write_text "$dest" "$content" || {
        warn "change-surface: could not write baseline $dest" >&2
        echo "CAPTURE_SKIPPED:write_failed"
        return 0
    }
    echo "CAPTURED:${count}"
}

# --- baseline read -----------------------------------------------------------
# Sets BASELINE_STATE (ok|missing|foreign) and BASELINE_PATHS (newline list).
read_baseline() {
    local task_id="$1" file recorded_top current_top
    BASELINE_STATE="missing"
    BASELINE_PATHS=""

    file="$(baseline_file "$task_id")"
    [[ -f "$file" ]] || return 0

    recorded_top="$(sed -n 's/^toplevel=//p' "$file" | head -n1)"
    current_top="$(git rev-parse --show-toplevel 2>/dev/null || true)"
    # A baseline taken in a different tree describes a different working set;
    # applying it here could exclude a path this task legitimately changed.
    if [[ -n "$recorded_top" && -n "$current_top" && "$recorded_top" != "$current_top" ]]; then
        BASELINE_STATE="foreign"
        return 0
    fi

    BASELINE_STATE="ok"
    BASELINE_PATHS="$(sed -n '/^paths:$/,$p' "$file" | tail -n +2 | grep -v '^$' || true)"
}

# --- plan scope (P2) ---------------------------------------------------------
# Sets PLANSCOPE_STATE (ok|missing) and PLANSCOPE_PATHS (newline list).
#
# EXACT FILE MATCHES ONLY. Directory tokens are discarded: a plan legitimately
# names broad directories in prose (.aitask-scripts/, tests/, seed/ ...), and
# treating them as recursive scope prefixes would attribute nearly the whole
# repo -- reopening the very failure this script exists to close. Recursive
# ownership is not inferable from prose, so it is not inferred.
#
# Tokens are only ever COMPARED as fixed strings, never used as patterns and
# never evaluated: plan text is agent/user-authored and may contain `.*` or
# `$(id)`.
read_plan_scope() {
    local task_id="$1" plan_file="" dirty="$2"
    PLANSCOPE_STATE="missing"
    PLANSCOPE_PATHS=""

    plan_file="$(resolve_plan_file "$task_id" 2>/dev/null || true)"
    if [[ -z "$plan_file" || ! -f "$plan_file" ]]; then
        return 0
    fi
    PLANSCOPE_STATE="ok"

    local tokens
    # Portable ERE (no grep -P: unavailable on macOS). Candidate = a token made
    # of path-safe characters that contains at least one `/` or a dot-extension.
    #
    # The leading `.` in the character class is load-bearing: without it a token
    # may not START with a dot, so `.aitask-scripts/foo.sh` is captured as
    # `aitask-scripts/foo.sh`, which resolves to nothing and is discarded. Every
    # dot-directory path (.claude/, .codex/, .opencode/, .agents/, .github/ ...)
    # would then be permanently unattributable — a large share of this framework
    # and of most repositories.
    tokens="$(grep -oE '[A-Za-z0-9_.][A-Za-z0-9_./-]*' "$plan_file" 2>/dev/null \
        | sed -e 's|^\./||' -e 's|[.,:;)]*$||' \
        | grep -E '/|\.[A-Za-z0-9]+$' \
        | sort -u || true)"
    [[ -n "$tokens" ]] || return 0

    local tok keep=""
    while IFS= read -r tok; do
        [[ -n "$tok" ]] || continue
        # Discard directory tokens outright -- they never attribute.
        [[ -d "$tok" ]] && continue
        # Keep a token that names an existing regular file, or a path that is
        # currently dirty/untracked (a file the plan CREATES does not exist
        # until it does). Fixed-string membership test, never a pattern.
        if [[ -f "$tok" ]] || printf '%s\n' "$dirty" | grep -qxF -- "$tok"; then
            keep+="${tok}"$'\n'
        fi
    done <<< "$tokens"

    PLANSCOPE_PATHS="$(printf '%s' "$keep" | grep -v '^$' | sort -u || true)"
}

# --- list --------------------------------------------------------------------
cmd_list() {
    local task_id="${1:-}"
    [[ -n "$task_id" ]] || die "Usage: aitask_change_surface.sh list <task-id>"

    local dirty committed
    dirty="$(current_dirty_set)"

    # Pass A input: every path in a commit tagged (t<id>). -F keeps the tag a
    # fixed string, so "(t126)" never matches "(t1263)".
    committed=""
    if git rev-parse HEAD >/dev/null 2>&1; then
        local shas sha
        shas="$(git log -F --grep="(t${task_id})" --format=%H 2>/dev/null || true)"
        if [[ -n "$shas" ]]; then
            while IFS= read -r sha; do
                [[ -n "$sha" ]] || continue
                # No `--` before the sha: that would make git read it as a
                # PATHSPEC rather than a revision, and Pass A would silently
                # return nothing for every task (t1263).
                committed+="$(git show --name-only --format= "$sha" 2>/dev/null || true)"$'\n'
            done <<< "$shas"
        fi
    fi
    # Apply the same data-path exclusion the dirty scan uses.
    committed="$(printf '%s' "$committed" | sed 's|^\./||' | grep -v '^$' \
        | grep -Ev '^(aitasks/|aiplans/|\.aitask-data/)' | sort -u || true)"

    read_baseline "$task_id"
    read_plan_scope "$task_id" "$dirty"

    echo "BASELINE:${BASELINE_STATE}"
    echo "PLANSCOPE:${PLANSCOPE_STATE}"

    # --- Pass A: the tagged-commit set, emitted UNCONDITIONALLY ---------------
    # Independent of the dirty scan: a task that committed code earlier and left
    # the file clean still contributes it to the surface. Do not fold this into
    # the dirty loop.
    local p
    if [[ -n "$committed" ]]; then
        while IFS= read -r p; do
            [[ -n "$p" ]] && echo "COMMITTED:${p}"
        done <<< "$committed"
    fi

    # --- Pass B: the dirty set, classified; Pass A paths de-duplicated out ----
    [[ -n "$dirty" ]] || return 0
    local in_plan in_base
    while IFS= read -r p; do
        [[ -n "$p" ]] || continue
        # COMMITTED is the strongest signal: report such a path once, in Pass A.
        if [[ -n "$committed" ]] && printf '%s\n' "$committed" | grep -qxF -- "$p"; then
            continue
        fi
        in_plan=0; in_base=0
        [[ "$PLANSCOPE_STATE" == "ok" && -n "$PLANSCOPE_PATHS" ]] &&
            printf '%s\n' "$PLANSCOPE_PATHS" | grep -qxF -- "$p" && in_plan=1
        [[ "$BASELINE_STATE" == "ok" && -n "$BASELINE_PATHS" ]] &&
            printf '%s\n' "$BASELINE_PATHS" | grep -qxF -- "$p" && in_base=1

        if [[ "$in_plan" -eq 1 && "$in_base" -eq 1 ]]; then
            # Signals conflict (plan names it, but it was already dirty at
            # claim). Never guess a winner.
            echo "UNKNOWN:${p}"
        elif [[ "$in_plan" -eq 1 ]]; then
            echo "TASK:${p}"
        elif [[ "$in_base" -eq 1 ]]; then
            echo "OTHER:${p}"
        else
            # Appeared after the claim and unnamed by the plan -- the
            # concurrent-session case. Escalate; do not attribute.
            echo "UNKNOWN:${p}"
        fi
    done <<< "$dirty"
}

# --- Main ---
main() {
    local cmd="${1:-}"
    [[ $# -gt 0 ]] && shift
    case "$cmd" in
        capture) cmd_capture "$@" ;;
        list)    cmd_list "$@" ;;
        -h|--help|help|"") show_help ;;
        *) die "Unknown subcommand: $cmd (try --help)" ;;
    esac
}

main "$@"
