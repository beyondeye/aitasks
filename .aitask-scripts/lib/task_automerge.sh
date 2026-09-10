#!/usr/bin/env bash
# task_automerge.sh - Auto-merge conflicted task/plan files during a rebase.
# Source this file from aitask scripts; do not execute directly.
#
# THE one conflict-resolution engine for the task-data branch. It was extracted
# from aitask_sync.sh (t1727) so the framework's TWO `pull --rebase` paths share
# it instead of only one being able to resolve anything:
#
#   ait sync        -> aitask_sync.sh::do_pull_rebase       (sources this at startup)
#   every pick/push -> lib/task_utils.sh::_task_pull_rebase (sources this LAZILY)
#
# CONTRACT — stdout is NEVER a data channel here. Every diagnostic goes to
# stderr and every result comes back in a global, because _task_pull_rebase's
# callers capture it with `$( … 2>&1 )` and a stray stdout line would be parsed
# as git output. (The pre-extraction try_auto_merge returned its unresolved list
# ON stdout, which is exactly how the driver's own "RESOLVED" once surfaced as a
# conflicted filename — `CONFLICT:RESOLVED`.)
#
# It runs git through _ait_data_git (lib/task_utils.sh), the raw task-data
# runner: same worktree as task_git, but without assert_data_worktree_clean,
# which rejects mutating verbs while the worktree is mid-rebase — precisely when
# conflict resolution runs. That replaces the scoped AIT_GIT_SKIP_STATE_CHECK=1
# bypass the sync-side code used to carry. Both callers source task_utils.sh, so
# the seam is always present.
#
# It needs no dirty-worktree defence: `git pull --rebase` refuses BEFORE it
# fetches whenever a tracked file is modified, so reaching a conflict at all
# proves the shared worktree held no other session's uncommitted edit.

# --- Guard against double-sourcing ---
[[ -n "${_AIT_TASK_AUTOMERGE_LOADED:-}" ]] && return 0
_AIT_TASK_AUTOMERGE_LOADED=1

# Self-anchored, like pid_anchor.sh: never inherit the caller's SCRIPT_DIR. The
# lazy loader in task_utils.sh may source this from any cwd.
_AIT_AUTOMERGE_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Results (the return values; read them after each call) ---
# shellcheck disable=SC2034  # these globals ARE the return values; they are read by callers in other files (aitask_sync.sh, task_utils.sh)
AIT_AUTOMERGE_REMAINING=""   # newline-separated files that did NOT resolve
AIT_AUTOMERGE_RESOLVED=0     # files auto-merged: this call for ait_automerge_files,
                             # the running total when set by ait_automerge_rebase_loop

# --- Progress channel ---------------------------------------------------------
# NON-failure progress goes through this indirection; real failures always go
# through warn() and are never suppressible. The default is SILENT because the
# workflow pull runs on every single pick and must not narrate. aitask_sync.sh
# points it at iinfo_err, so interactive `ait sync` keeps its per-file progress
# and `--batch` stays quiet, exactly as before the extraction.
AIT_AUTOMERGE_PROGRESS_FN="${AIT_AUTOMERGE_PROGRESS_FN:-_ait_automerge_progress_noop}"

_ait_automerge_progress_noop() { :; }

_ait_automerge_progress() {
    "$AIT_AUTOMERGE_PROGRESS_FN" "$1"
}

# --- Round cap (t1727 risk mitigation: bound_automerge_loop_iterations) -------
# The pre-extraction loop in aitask_sync.sh was an unbounded `while true`. The
# new caller holds the data-worktree pull mutex for the WHOLE loop, so an
# unbounded loop would block every other session on the host indefinitely.
#
# AIT_AUTOMERGE_MAX_ROUNDS is a documented env seam (the AITASKS_LOCK_DIR shape)
# so a test can actually reach the cap. It FAILS CLOSED to the default: a typo
# must never disable or zero the cap. 50 is well above the largest replay
# observed on this project's data branch (21 commits).
_AIT_AUTOMERGE_DEFAULT_MAX_ROUNDS=50

_ait_automerge_max_rounds() {
    local v="${AIT_AUTOMERGE_MAX_ROUNDS:-}"
    # Rejects empty, non-numeric, "0", and octal-looking "010" alike.
    if [[ -n "$v" && "$v" != *[!0-9]* && "$v" != 0* ]]; then
        printf '%s' "$v"
        return 0
    fi
    printf '%s' "$_AIT_AUTOMERGE_DEFAULT_MAX_ROUNDS"
}

# --- Path resolution ----------------------------------------------------------
# ait_automerge_conflict_path <repo-relative path> -> filesystem path
# The merge driver takes a filesystem path, but a conflicted-file listing is
# repo-relative; in branch mode those differ.
ait_automerge_conflict_path() {
    local file="$1"
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        printf '%s\n' "$_AIT_DATA_WORKTREE/$file"
    else
        printf '%s\n' "$file"
    fi
}

# --- Driver resolution (lazy) -------------------------------------------------
# Resolved on first use, not at source time: task_utils.sh sources this library
# lazily and must not pay for a python probe on a pull that never conflicts.
_AIT_AUTOMERGE_PYTHON=""
_AIT_AUTOMERGE_SCRIPT=""
_AIT_AUTOMERGE_DRIVER_PROBED=""

# 0 = the driver is usable; 1 = it is not (no python, or no merge script).
_ait_automerge_driver_ready() {
    if [[ -z "$_AIT_AUTOMERGE_DRIVER_PROBED" ]]; then
        _AIT_AUTOMERGE_DRIVER_PROBED=1
        # resolve_python may print nothing in a fully-stripped environment.
        _AIT_AUTOMERGE_PYTHON="$(resolve_python)"
        _AIT_AUTOMERGE_SCRIPT="$_AIT_AUTOMERGE_LIB_DIR/../board/aitask_merge.py"
    fi
    [[ -n "$_AIT_AUTOMERGE_PYTHON" && -f "$_AIT_AUTOMERGE_SCRIPT" ]]
}

# --- Auto-merge one conflict set ---------------------------------------------
# ait_automerge_files <conflicted_files_newline_separated>
#
# Attempts an auto-merge of each task/plan file and stages what resolved.
# Returns 0 if ALL resolved, 1 if any remain. Sets AIT_AUTOMERGE_REMAINING and
# AIT_AUTOMERGE_RESOLVED (this call's count).
ait_automerge_files() {
    local conflicted="$1"
    local unresolved=""
    local resolved_count=0

    AIT_AUTOMERGE_REMAINING=""
    AIT_AUTOMERGE_RESOLVED=0

    if ! _ait_automerge_driver_ready; then
        AIT_AUTOMERGE_REMAINING="$conflicted"
        return 1
    fi

    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        case "$f" in
            aitasks/*.md|aiplans/*.md)
                local file_path merge_exit=0
                file_path="$(ait_automerge_conflict_path "$f")"
                # Supply the MERGE BASE from git's conflicted index (stage 1 =
                # base, 2 = ours, 3 = theirs). The diff3 marker base is not an
                # option: `merge.conflictStyle` is configured nowhere, so git
                # emits 2-way markers and the parser has no ancestor to read.
                # `$f` (repo-relative), never `$file_path` — a `:1:` pathspec is
                # resolved against the repo, not the filesystem. An add/add
                # conflict has no stage 1; the extraction fails, no flag is
                # passed, and base-aware fields fail closed to PARTIAL.
                local base_tmp base_args=()
                base_tmp="$(mktemp)"
                if _ait_data_git show ":1:$f" > "$base_tmp" 2>/dev/null; then
                    base_args=(--base-file "$base_tmp")
                else
                    rm -f "$base_tmp"
                    base_tmp=""
                fi
                # The driver's own stdout ("RESOLVED" / "PARTIAL:...") is
                # discarded; only its exit status matters here.
                PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$_AIT_AUTOMERGE_LIB_DIR/../board" \
                    "$_AIT_AUTOMERGE_PYTHON" "$_AIT_AUTOMERGE_SCRIPT" "$file_path" \
                    --batch --rebase ${base_args[@]+"${base_args[@]}"} >/dev/null 2>&1 || merge_exit=$?
                if [[ -n "$base_tmp" ]]; then rm -f "$base_tmp"; fi
                if [[ $merge_exit -eq 0 ]]; then
                    local add_err add_rc=0
                    add_err="$(_ait_data_git add "$f" 2>&1)" || add_rc=$?
                    if [[ $add_rc -eq 0 ]]; then
                        resolved_count=$((resolved_count + 1))
                        _ait_automerge_progress "Auto-merged: $f"
                    else
                        # A file we could not stage is an UNRESOLVED merge, not a
                        # resolved one: `rebase --continue` would fail later with
                        # the diagnostic already discarded. warn() -> stderr.
                        warn "auto-merge could not stage $f (git add rc=$add_rc): ${add_err:-<no output>}"
                        unresolved="${unresolved}${unresolved:+$'\n'}$f"
                    fi
                else
                    unresolved="${unresolved}${unresolved:+$'\n'}$f"
                fi
                ;;
            *)
                unresolved="${unresolved}${unresolved:+$'\n'}$f"
                ;;
        esac
    done <<< "$conflicted"

    AIT_AUTOMERGE_RESOLVED=$resolved_count
    AIT_AUTOMERGE_REMAINING="$unresolved"

    if [[ -z "$unresolved" ]]; then
        _ait_automerge_progress "Auto-merged $resolved_count file(s)"
        return 0
    fi
    [[ $resolved_count -gt 0 ]] && \
        _ait_automerge_progress "Auto-merged $resolved_count file(s), remaining conflicts need manual resolution"
    return 1
}

# --- Rebase advancement -------------------------------------------------------
# Try rebase --continue, and fall back to --skip only for a patch VERIFIED to be
# empty. Current git (>= 2.26) drops an empty replayed commit during --continue
# itself, so the fallback serves older git -- and --continue also fails for
# reasons unrelated to emptiness (a hook, a locked index), where skipping would
# DISCARD a commit with real content.
#
# Returns 0 when the rebase advanced, 1 when it did not; the caller aborts.
# Probe rule and dispositions: aidocs/framework/failopen_git_probes.md (A1)
ait_automerge_advance() {
    if GIT_EDITOR=true _ait_data_git rebase --continue &>/dev/null; then
        return 0
    fi
    # An unreadable probe is not "nothing unresolved": it never authorises --skip.
    local unresolved="" u_rc=0
    unresolved="$(_ait_data_git diff --name-only --diff-filter=U 2>/dev/null)" || u_rc=$?
    (( u_rc == 0 )) || return 1
    [[ -z "$unresolved" ]] || return 1

    # ...and "nothing unresolved" is not "empty patch". The staged-tree check
    # exits 0 = identical to HEAD, 1 = a real patch, >= 2 = could not tell, and
    # "could not tell" is not "empty".
    local e_rc=0
    _ait_data_git diff --cached --quiet HEAD >/dev/null 2>&1 || e_rc=$?
    (( e_rc == 0 )) || return 1

    if _ait_data_git rebase --skip &>/dev/null; then
        return 0
    fi
    return 1
}

# Internal: the files git currently reports as unresolved.
#   0 -- the list was read; empty output means "none unresolved"
#   2 -- the probe could not be read, and its empty output means NOTHING
# Every consumer runs under `set -euo pipefail` and must ABSORB the status: a
# bare `x="$(...)"` would exit the shell mid-rebase. Each call site records its
# disposition in an `# unverified:` comment directly above it, and
# tests/test_sync_branch_mode_automerge.sh (Test 13) pins the set. (A2)
_ait_automerge_conflicted_now() {
    local out="" rc=0
    out="$(_ait_data_git diff --name-only --diff-filter=U 2>/dev/null)" || rc=$?
    (( rc == 0 )) || return 2
    printf '%s' "$out"
}

# --- The full resolve-and-advance loop ----------------------------------------
# ait_automerge_rebase_loop
#
# Call when a `pull --rebase` has stopped on a conflict THE CALLER OWNS. Merges
# the current conflict set, advances the rebase, and repeats for each further
# replayed commit that conflicts.
#
#   0 — the rebase completed; AIT_AUTOMERGE_RESOLVED = files merged across all rounds
#   1 — stuck: AIT_AUTOMERGE_REMAINING lists what could not be merged (this also
#       covers round-cap exhaustion, which is reported on stderr first)
#   2 — the rebase could not be advanced for a NON-conflict reason: nothing left
#       unresolved yet neither --continue nor --skip worked, OR the unresolved-file
#       probe could not be read (nothing was merged or advanced on that probe)
#
# Every caller MUST absorb the status (`rc=0; ait_automerge_rebase_loop || rc=$?`):
# both callers run under `set -euo pipefail`, where a bare call would exit the
# shell on rc 1 / 2 — bypassing the abort and the CONFLICT: token exactly when
# they are needed.
ait_automerge_rebase_loop() {
    local total=0 round=0 max_rounds conflicted c_rc=0
    max_rounds="$(_ait_automerge_max_rounds)"

    AIT_AUTOMERGE_REMAINING=""
    AIT_AUTOMERGE_RESOLVED=0

    # unverified: return 2 before any merge or advance, so the caller aborts.
    conflicted="$(_ait_automerge_conflicted_now)" || c_rc=$?
    (( c_rc == 0 )) || return 2

    while :; do
        round=$((round + 1))
        if (( round > max_rounds )); then
            # Fail closed and let the caller abort: a resolver that will not stop
            # is worse than one that gives up, because it holds the pull mutex.
            # Sentinel text owned by task_utils.sh — see AIT_AUTOMERGE_GAVE_UP_SENTINEL
            # there for why the matcher's side declares it.
            printf 'aitask: %s %d rounds\n' "$AIT_AUTOMERGE_GAVE_UP_SENTINEL" "$max_rounds" >&2
            AIT_AUTOMERGE_REMAINING="$conflicted"
            AIT_AUTOMERGE_RESOLVED=$total
            return 1
        fi

        local files_rc=0
        ait_automerge_files "$conflicted" || files_rc=$?
        total=$((total + AIT_AUTOMERGE_RESOLVED))
        if [[ $files_rc -ne 0 ]]; then
            [[ $total -gt 0 ]] && _ait_automerge_progress \
                "Auto-merged earlier commits, but conflicts remain that need manual resolution"
            AIT_AUTOMERGE_RESOLVED=$total
            return 1        # AIT_AUTOMERGE_REMAINING already set by ait_automerge_files
        fi

        # unverified: rc 1 -- it never skips on an unread probe or an unverified
        # empty patch; the re-probe below then tells a new conflict from a failure.
        if ait_automerge_advance; then
            AIT_AUTOMERGE_RESOLVED=$total
            # shellcheck disable=SC2034  # a result global, read by callers in other files
            AIT_AUTOMERGE_REMAINING=""
            return 0        # rebase complete
        fi

        # The advance failed. A new conflict from the next replayed commit is
        # the expected case; anything else is a real failure the caller must
        # distinguish, because its remedy is an abort, not a manual merge.
        c_rc=0
        # unverified: return 2 -- an unread probe is not "no new conflict".
        conflicted="$(_ait_automerge_conflicted_now)" || c_rc=$?
        if (( c_rc != 0 )) || [[ -z "$conflicted" ]]; then
            AIT_AUTOMERGE_RESOLVED=$total
            # shellcheck disable=SC2034  # a result global, read by callers in other files
            AIT_AUTOMERGE_REMAINING=""
            return 2
        fi
    done
}
