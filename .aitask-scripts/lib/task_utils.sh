#!/usr/bin/env bash
# task_utils.sh - Shared task/plan resolution and extraction utilities
# Source this file from aitask scripts; do not execute directly.

# --- Guard against double-sourcing ---
[[ -n "${_AIT_TASK_UTILS_LOADED:-}" ]] && return 0
_AIT_TASK_UTILS_LOADED=1

# Ensure terminal_compat.sh is loaded (for die/warn helpers)
SCRIPT_DIR="${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# shellcheck source=terminal_compat.sh
source "${SCRIPT_DIR}/lib/terminal_compat.sh"
# shellcheck source=archive_utils.sh
source "${SCRIPT_DIR}/lib/archive_utils.sh"
# shellcheck source=yaml_utils.sh
source "${SCRIPT_DIR}/lib/yaml_utils.sh"
# shellcheck source=python_resolve.sh
source "${SCRIPT_DIR}/lib/python_resolve.sh"
# data_symlinks.sh provides ait_main_worktree_root(), rung 3 of the data-worktree
# resolution ladder below. It sources only terminal_compat.sh (self-anchored via
# its own BASH_SOURCE, so no cwd dependency) and guards against double-sourcing,
# so there is no cycle with aitask_setup.sh / aitask_init_data.sh, which source
# it too.
# shellcheck source=data_symlinks.sh
source "${SCRIPT_DIR}/lib/data_symlinks.sh"

# --- Default directory variables (override before sourcing if needed) ---
TASK_DIR="${TASK_DIR:-aitasks}"
ARCHIVED_DIR="${ARCHIVED_DIR:-aitasks/archived}"
PLAN_DIR="${PLAN_DIR:-aiplans}"
ARCHIVED_PLAN_DIR="${ARCHIVED_PLAN_DIR:-aiplans/archived}"

# --- Task Data Worktree Detection ---
# Detects if task data lives in a separate worktree (.aitask-data/)
# or on the current branch (legacy mode). All scripts use task_git()
# for git operations on task/plan files.

_AIT_DATA_WORKTREE=""

# Detect whether task data lives in a separate worktree.
# Sets _AIT_DATA_WORKTREE to the data worktree (branch mode) or "." (legacy).
#
# A FOUR-RUNG ladder, first hit wins. It used to be a single cwd-relative probe,
# which silently answered "." — indistinguishable from a genuine legacy project —
# for every caller whose cwd was not the repo root. None of the 15 scripts that
# perform data-branch git ops cd to the root, so from `website/` the seam
# operated on `main` and from an unlinked crew worktree on that worktree's own
# branch, both reporting success while the data branch was never reconciled
# (t1658_2).
#
#   1. ./.aitask-data/.git          -> ".aitask-data"          (the repo root)
#   2. <toplevel>/.aitask-data/.git -> <toplevel>/.aitask-data  (a subdirectory)
#   3. <main>/.aitask-data/.git     -> <main>/.aitask-data      (a linked worktree
#                                      that was never --link-worktree'd)
#   4. otherwise                    -> "."                      (legacy mode)
#
# Rung 1 stays a PURE FILESYSTEM PROBE and is byte-identical to the pre-ladder
# behaviour at the repo root — which is every ./ait-dispatched invocation.
#
# The <root>/.aitask-data spelling is deliberately UNCANONICALIZED (not `pwd -P`)
# so a task worktree's symlinked data dir keeps its friendly path in messages;
# git follows the symlink either way.
#
# BOUNDARY: a submodule, or any nested repository, resolves to its OWN root and
# therefore to legacy mode — never to the parent repo's data branch. That is
# ait_main_worktree_root()'s same-repo property and it is the correct answer, not
# an oversight; do not "fix" it by walking up past a repository boundary.
_ait_detect_data_worktree() {
    if [[ -n "$_AIT_DATA_WORKTREE" ]]; then return; fi
    local root=""

    # Rung 1 — today's fast path.
    if [[ -d ".aitask-data/.git" || -f ".aitask-data/.git" ]]; then
        _AIT_DATA_WORKTREE=".aitask-data"
        return
    fi

    # Rung 2 — this checkout's toplevel. The `|| root=""` is load-bearing: a bare
    # assignment from a command substitution that fails exits 128 under
    # `set -euo pipefail` and kills the caller with no message at all, and every
    # framework script runs with those options.
    root="$(git rev-parse --show-toplevel 2>/dev/null)" || root=""
    if [[ -n "$root" && ( -d "$root/.aitask-data/.git" || -f "$root/.aitask-data/.git" ) ]]; then
        _AIT_DATA_WORKTREE="$root/.aitask-data"
        return
    fi

    # Rung 3 — the MAIN worktree, for a linked worktree that was never
    # --link-worktree'd (the crew case). ait_main_worktree_root has THREE states
    # and they must not be conflated — that is the whole point of this rung:
    #
    #   0  resolved      -> probe <main>/.aitask-data
    #   1  not a git repository at all -> legacy is a PROVEN answer
    #   2  inside a repository, but the topology did not resolve
    #
    # State 2 is NOT a licence to answer legacy. `git init --separate-git-dir`
    # is a documented layout that answers 2 (see the KNOWN LAYOUT BOUNDARY note
    # in data_symlinks.sh), and an unlinked linked worktree of such a
    # BRANCH-MODE primary would otherwise fall straight through to "." and
    # operate on its own code branch — reinstating, in a different layout,
    # exactly the silent legacy fallback this ladder exists to remove.
    #
    # It must be called in an `if`/`|| rc=$?` for the same set -e reason as
    # rung 2.
    local main_rc=0
    ait_main_worktree_root "." || main_rc=$?
    case "$main_rc" in
        0)
            if [[ -d "$AIT_WT_MAIN_ROOT/.aitask-data/.git" || -f "$AIT_WT_MAIN_ROOT/.aitask-data/.git" ]]; then
                _AIT_DATA_WORKTREE="$AIT_WT_MAIN_ROOT/.aitask-data"
                return
            fi
            ;;
        1)
            : # Not a repository — rung 4's legacy answer is correct.
            ;;
        *)
            # Indeterminate. Legacy is only safe if we can PROVE this checkout
            # owns its repository, i.e. it is the primary (or a plain
            # subdirectory of it) — rung 2 already established that primary has
            # no .aitask-data, so "." is then a proven answer rather than a
            # guess. ait_linked_worktree_roots decides that on the
            # git-dir-vs-git-common-dir predicate, which still works when the
            # main root does not resolve: it returns 1 for "definitively NOT
            # linked". (It cannot return 0 here — it calls
            # ait_main_worktree_root itself and propagates this same failure —
            # so 1 is the only safe state.)
            local linked_rc=0
            ait_linked_worktree_roots "." || linked_rc=$?
            if [[ "$linked_rc" -ne 1 ]]; then
                die "Cannot determine where task data lives: this is a git worktree whose main checkout could not be resolved (an unsupported layout such as 'git init --separate-git-dir'). Refusing rather than defaulting to legacy mode, which would commit task data to this worktree's own branch. Give this worktree its own .aitask-data (./ait setup, or aitask_init_data.sh --link-worktree <dir>), or run the command from the main checkout."
            fi
            ;;
    esac

    # Rung 4 — a genuine legacy-mode project.
    _AIT_DATA_WORKTREE="."
}

# Anchor the process to the repository root — the same rule `ait` applies
# (`cd "$AIT_DIR"`, ait:9) so relative paths like aitasks/metadata/... and ./ait
# resolve. Call it ONCE, early, from an ENTRY-POINT script only; never from a
# library, and never from a sourced helper.
#
# Deliberately does NOT honour AITASK_REPO_ROOT: that is a single-script test
# hook read only by aitask_add_model.sh, and promoting it to a framework-wide
# override here would silently broaden its blast radius.
ait_cd_repo_root() {
    local script_dir="${1:?ait_cd_repo_root: script dir required}" root
    root="$(cd "$script_dir/.." && pwd)" || die "Cannot resolve repo root from $script_dir"
    cd "$root" || die "Cannot cd to repo root $root"
}

# Resolve the data worktree's git-dir. Empty when in legacy mode or when the
# git-dir cannot be resolved.
#
# ALWAYS returns 0: every caller does `gitdir="$(_ait_data_gitdir)"` under
# `set -e`, so a non-zero status here aborts the caller with no message. An
# unresolvable git-dir is an empty answer, not a failure (t1616).
_ait_data_gitdir() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" == "." ]]; then
        printf ''
        return 0
    fi
    # Fast path: the relative admin dir, correct from the primary checkout.
    local gd=".git/worktrees/-aitask-data"
    if [[ -d "$gd" ]]; then
        printf '%s' "$gd"
        return 0
    fi
    # From a linked worktree `.git` is a FILE, so the path above does not exist
    # even though the data worktree is perfectly reachable through the
    # .aitask-data symlink. Ask git, which resolves it from anywhere.
    git -C "$_AIT_DATA_WORKTREE" rev-parse --absolute-git-dir 2>/dev/null || printf ''
    return 0
}

# Internal: run git against the task-data worktree (branch mode) or the current
# repo (legacy mode). Unlike task_git() it skips the wedged-worktree assertion,
# so it is safe for the read-only probes and for task_push, which asserts once
# up front. LC_ALL=C keeps git's messages parseable by _task_push_classify.
_ait_data_git() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        LC_ALL=C git -C "$_AIT_DATA_WORKTREE" "$@"
    else
        LC_ALL=C git "$@"
    fi
}

# Read-only git subcommands — the guard treats them as safe.
_ait_git_subcmd_is_readonly() {
    case "${1:-}" in
        status|log|show|diff|rev-parse|ls-files|blame|grep|reflog) return 0 ;;
        branch)
            local a
            for a in "${@:2}"; do
                case "$a" in -d|-D|-m|-M|--delete|--move) return 1 ;; esac
            done
            return 0 ;;
        tag)
            local a
            for a in "${@:2}"; do
                case "$a" in -l|--list) return 0 ;; esac
            done
            return 1 ;;
        stash)
            [[ "${2:-}" == "list" || "${2:-}" == "show" ]] && return 0 || return 1 ;;
    esac
    return 1
}

# Recovery subcommands — must be allowed through even when the worktree is wedged.
_ait_git_subcmd_is_recovery() {
    case "${1:-}" in
        rebase|merge|cherry-pick|revert)
            local a
            for a in "${@:2}"; do
                case "$a" in --abort|--continue|--skip|--edit-todo|--quit) return 0 ;; esac
            done
            return 1 ;;
        bisect)
            [[ "${2:-}" == "reset" ]] && return 0 || return 1 ;;
    esac
    return 1
}

# Pre-flight: reject mutating ops while the data worktree is mid-rebase/merge/etc.
# No-op in legacy mode and when the data worktree git-dir is missing.
assert_data_worktree_clean() {
    [[ "${AIT_GIT_SKIP_STATE_CHECK:-}" == "1" ]] && return 0
    _ait_git_subcmd_is_recovery "$@" && return 0
    _ait_git_subcmd_is_readonly "$@" && return 0

    local gitdir
    gitdir="$(_ait_data_gitdir)"
    [[ -z "$gitdir" ]] && return 0

    local state hit=""
    for state in rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD BISECT_LOG; do
        if [[ -e "$gitdir/$state" ]]; then hit="$state"; break; fi
    done
    [[ -z "$hit" ]] && return 0

    die "$(cat <<EOF
Data worktree (.aitask-data) is stuck mid-${hit}.
Recover with one of:
  ./ait git rebase --abort        (discard the in-progress rebase)
  ./ait git rebase --continue     (resume if you were editing)
  ./ait git merge --abort
  ./ait git cherry-pick --abort
  ./ait git revert --abort
  ./ait git bisect reset
Set AIT_GIT_SKIP_STATE_CHECK=1 to bypass this check.
Run './ait git-health' for a full diagnostic.
EOF
)"
}

# Print human-readable health of the .aitask-data worktree. Informational only.
task_git_health() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" == "." ]]; then
        info "Mode: legacy (no separate .aitask-data worktree) — nothing to check."
        return 0
    fi

    local gitdir branch head_ref state
    local hits=()
    gitdir="$(_ait_data_gitdir)"
    branch="$(git -C .aitask-data rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
    head_ref="$(git -C .aitask-data rev-parse --short HEAD 2>/dev/null || echo '?')"

    info "Mode: branch (.aitask-data worktree present)"
    info "Worktree path: .aitask-data"
    info "Git-dir: ${gitdir:-<missing>}"
    info "Branch (rev-parse --abbrev-ref HEAD): $branch"
    info "HEAD commit: $head_ref"

    if [[ -z "$gitdir" || ! -d "$gitdir" ]]; then
        warn "Git-dir not found at expected path — worktree may be misregistered."
        return 0
    fi

    for state in rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD BISECT_LOG; do
        [[ -e "$gitdir/$state" ]] && hits+=("$state")
    done

    if [[ "$branch" == "HEAD" ]]; then
        warn "Detached HEAD."
    fi
    if (( ${#hits[@]} > 0 )); then
        warn "In-progress operations: ${hits[*]}"
        info "Recover with: ./ait git <rebase|merge|cherry-pick|revert> --abort  (or --continue)"
    elif [[ "$branch" != "HEAD" ]]; then
        success "Clean — no in-progress rebase/merge/cherry-pick/revert/bisect."
    fi
}

# Run git commands targeting the task data worktree
# In branch mode: git -C .aitask-data <args>
# In legacy mode: git <args>
task_git() {
    _ait_detect_data_worktree
    assert_data_worktree_clean "$@"
    if [[ "$_AIT_DATA_WORKTREE" != "." ]]; then
        git -C "$_AIT_DATA_WORKTREE" "$@"
    else
        git "$@"
    fi
}

# --- Path-scoped commit (shared) ---

# task_git_commit_scoped [--no-stage] <msg> <path>... — stage and commit ONLY
# these paths.
# Returns 0 = committed, 2 = verified nothing to commit, 1 = commit failed.
#
# `git commit -- <paths>` is a PARTIAL commit: it takes those paths' WORKTREE
# content and ignores their index entry (verified: a staged-then-modified path
# commits the on-disk version). That is deliberate for its callers — a claim's
# own aitask_update.sh write is on disk — but it is a real change from an
# index-wide commit, so it is stated rather than assumed.
#
# `--no-stage` (opt-in; default is unchanged) skips the `add` entirely, for a
# caller that has already staged whatever needed staging and must not touch the
# index for anything else. The `.aitask-data` index is SHARED by every session
# on the machine, so an unconditional `add` of a tracked path can replace an
# index entry another session staged and has not yet committed (t1599_3). A
# caller in that position stages only the untracked paths itself — so it also
# knows exactly which entries to unstage if the commit fails — and passes this
# flag. `commit -o` needs no staging for a tracked path, so nothing is lost.
#
# Lives here rather than in one script because BOTH writers of the shared
# contributor list commit through it (t1626): aitask_pick_own.sh (via its
# _commit_scoped alias) and aitask_create.sh::add_email_to_file.
task_git_commit_scoped() {
    # Matched literally, so a message is never mistaken for the flag.
    local do_stage=1
    if [[ "${1:-}" == "--no-stage" ]]; then
        do_stage=0; shift
    fi
    local msg="$1"; shift
    # Load-bearing: `git commit --` with no pathspec commits the WHOLE index,
    # silently re-creating the cross-session swallow this exists to stop.
    # `-o` below makes that case fatal rather than silent; this guard means it
    # is never reached.
    (( $# )) || return 2

    # `add` is needed ONLY so an untracked path can be named by the pathspec;
    # a pathspec cannot match a file git does not know about. Verified: a
    # two-path `commit -o -- <new> <orig>` rename fails outright with
    # "pathspec did not match any file(s) known to git" when <new> is untracked,
    # while a pure deletion needs no staging at all.
    if (( do_stage )); then
        task_git add -- "$@" >/dev/null 2>&1 || true
    fi

    # Capture the status exit separately: a failing status with empty stdout
    # must read as "unverified", never as "clean" (same shape as the guard in
    # aitask_gate.sh's materialize-active).
    local st st_rc=0
    st="$(task_git status --porcelain -- "$@" 2>/dev/null)" || st_rc=$?
    if [[ $st_rc -eq 0 && -z "$st" ]]; then
        return 2
    fi
    [[ $st_rc -ne 0 ]] && warn "git status failed for $* — committing anyway"

    # stdout to /dev/null: --quiet already silences the summary, but
    # aitask_create.sh's stdout is a DATA channel (it prints the created task
    # file path), so this helper must never be able to contaminate it.
    task_git commit -o -m "$msg" --quiet -- "$@" >/dev/null || return 1
}

# --- Contributor list (shared by both of its writers) ---

# The one canonical path. aitask_pick_own.sh and aitask_create.sh each keep a
# local EMAILS_FILE name, assigned from this, so their call sites are unchanged.
AIT_EMAILS_FILE="aitasks/metadata/emails.txt"

# ait_email_is_committed <email>
# 0 = the address is in the COMMITTED contributor list.
# 1 = it is not — INCLUDING when the answer cannot be established (no HEAD, the
#     file untracked, a git failure).
#
# The failure direction is deliberate and is the whole point of t1626. Both
# writers short-circuit on membership, and an address appended by a write whose
# commit never happened is invisible to every later call: the short-circuit
# returns before the "this call owes the file a commit" flag can be set, so the
# one path that would commit it never runs again. Answering "not committed" when
# unsure costs at most one task_git_commit_scoped call that returns 2 (verified
# nothing to commit); answering "committed" when unsure is permanent.
ait_email_is_committed() {
    local email="$1" head_list="" rc=0
    head_list="$(task_git show "HEAD:$AIT_EMAILS_FILE" 2>/dev/null)" || rc=$?
    [[ $rc -eq 0 ]] || return 1
    grep -qxF -- "$email" <<<"$head_list"
}

# --- Task data sync (best-effort, but never silent) ---
#
# Outcome of the most recent task_sync call. task_sync always returns 0 (the
# best-effort contract: a failed sync must never abort a pick), so read these
# when the outcome matters.
#
# BOTH counts are sampled AFTER the pull cycle and are read against the LOCAL
# upstream ref. TASK_SYNC_UNPUSHED is authoritative (HEAD is local).
# TASK_SYNC_UNPULLED is NOT: `git pull --rebase` refuses before it fetches when
# the worktree is dirty, and an unreachable remote never updates the ref either,
# so on a failed sync it reports the remote side as of the LAST SUCCESSFUL FETCH
# and can read 0 while the remote has in fact moved. Never present it as a
# current reading of the remote.
TASK_SYNC_STATUS=""     # synced | up-to-date | no-remote | failed
TASK_SYNC_REASON=""     # classifier code when failed (see _task_push_classify)
TASK_SYNC_UNPUSHED=""   # local commits not on upstream; "" when undeterminable
TASK_SYNC_UNPULLED=""   # cached upstream commits not merged; "" when undeterminable

# Sync task data from remote (independent of code sync in branch mode)
# Uses --rebase instead of --ff-only so sync succeeds even when local has
# unpushed commits (e.g. from a previous failed push cycle).
#
# Deliberately does NOT call assert_data_worktree_clean: task_sync runs at the
# top of every pick from aitask_pick_own.sh, which runs `set -euo pipefail`, so
# a die() here would abort the pick. A wedged worktree instead surfaces as
# reason=rebase_conflict with its recovery hint — loud, but still non-fatal.
# shellcheck disable=SC2034  # the TASK_SYNC_* globals ARE the return value; they are read by callers in other files (aitask_pick_own.sh)
task_sync() {
    TASK_SYNC_STATUS=""
    TASK_SYNC_REASON=""
    TASK_SYNC_UNPUSHED=""
    TASK_SYNC_UNPULLED=""

    # No remote at all (solo / offline-only repo): nothing to reconcile.
    if ! _task_push_has_remote; then
        TASK_SYNC_STATUS="no-remote"
        return 0
    fi

    local before_head after_head pull_err="" detail=""
    before_head="$(_task_sync_head)"

    if pull_err="$(_task_pull_rebase 2>&1)"; then
        after_head="$(_task_sync_head)"
        if [[ "$before_head" == "$after_head" ]]; then
            TASK_SYNC_STATUS="up-to-date"
        else
            TASK_SYNC_STATUS="synced"
        fi
        TASK_SYNC_UNPUSHED="$(_task_push_unpushed_count)"
        TASK_SYNC_UNPULLED="$(_task_sync_unpulled_count)"
        return 0
    fi

    TASK_SYNC_STATUS="failed"
    TASK_SYNC_REASON="$(_task_push_classify "" "$pull_err")"
    TASK_SYNC_UNPUSHED="$(_task_push_unpushed_count)"
    TASK_SYNC_UNPULLED="$(_task_sync_unpulled_count)"
    if [[ "$TASK_SYNC_REASON" == "unknown" ]]; then
        detail="$(_task_push_first_line "$pull_err")"
        if [[ -n "$detail" ]]; then
            detail=" (git: ${detail})"
        fi
    fi
    _task_sync_warn "$detail"
    return 0
}

# Internal: current HEAD commit; empty when undeterminable. Returns 0 (see the
# task_push probe note below).
_task_sync_head() {
    _ait_data_git rev-parse HEAD 2>/dev/null || true
}

# Internal: commits the upstream has that HEAD does not. Prints nothing when
# the branch has no upstream.
_task_sync_unpulled_count() {
    _ait_data_git rev-list --count 'HEAD..@{upstream}' 2>/dev/null || true
}

# Internal: emit the user-facing warning for a failed sync cycle. Mirrors
# _task_push_warn's policy — warn only when something is actually at risk, so
# an offline or single-machine user does not get a warning on every pick.
_task_sync_warn() {
    local detail="${1:-}" upstream hint
    upstream="$(_task_push_upstream)"
    if [[ -n "$upstream" ]]; then
        upstream=" with ${upstream}"
    fi
    hint="$(_task_push_reason_hint "$TASK_SYNC_REASON" "./ait sync")"

    if [[ -z "$TASK_SYNC_UNPUSHED" && -z "$TASK_SYNC_UNPULLED" ]]; then
        warn "task data sync failed (unreconciled commit counts unavailable) — ${hint}${detail}"
        return 0
    fi
    if [[ "${TASK_SYNC_UNPUSHED:-0}" != "0" || "${TASK_SYNC_UNPULLED:-0}" != "0" ]]; then
        # The remote count comes from the local upstream ref, which a failed
        # sync may never have refreshed — say so rather than implying it is a
        # current reading of the remote.
        warn "task data not reconciled${upstream}: ${TASK_SYNC_UNPUSHED:-0} local unpushed, ${TASK_SYNC_UNPULLED:-0} remote unpulled (remote side as of the last successful fetch — this sync may not have refreshed it) — ${hint}${detail}"
        return 0
    fi
    # Nothing is pending, but a local-state blocker keeps every future sync AND
    # push failing, so it is still worth reporting.
    case "$TASK_SYNC_REASON" in
        dirty_worktree|rebase_conflict)
            warn "task data sync failed — ${hint}${detail}" ;;
    esac
    return 0
}

# --- Task data push (best-effort, but never silent) ---
#
# task_push() returns 0 for EVERY push outcome — the best-effort contract the
# workflow relies on. The single exception is the pre-flight
# assert_data_worktree_clean guard, which die()s when the data worktree is
# wedged mid-rebase/merge: that is a broken-worktree error rather than a push
# outcome, and it is loud (bypass with AIT_GIT_SKIP_STATE_CHECK=1).
#
# The outcome is reported on three surfaces:
#   in-process — the TASK_PUSH_* globals below
#   human      — a warn() line on stderr; silent on success
#   machine    — task_push_report(), one line (`ait git push --batch`)
#
# TASK_PUSH_UNPUSHED is sampled AFTER the push cycle, so it is a CURRENT count
# ("how many commits are unpushed now"), not an atomic snapshot of the failure:
# on a shared checkout another session can move refs in between.
TASK_PUSH_STATUS=""     # pushed | up-to-date | no-remote | failed
TASK_PUSH_REASON=""     # classifier code when failed (see _task_push_classify)
TASK_PUSH_UNPUSHED=""   # unpushed commit count; "" when undeterminable

# Push task data to remote with automatic pull-rebase on conflict.
# Retries up to 3 times. Failures are non-fatal, but they are reported: a
# failed push used to be indistinguishable from a successful one (no output,
# exit 0), silently stranding archival and gate-ledger commits.
task_push() {
    TASK_PUSH_STATUS=""
    TASK_PUSH_REASON=""
    TASK_PUSH_UNPUSHED=""
    assert_data_worktree_clean push

    # No remote at all (solo / offline-only repo): nothing to push to and
    # nothing at risk — stay silent.
    if ! _task_push_has_remote; then
        TASK_PUSH_STATUS="no-remote"
        return 0
    fi

    local before_count push_err="" rebase_err="" out="" detail=""
    before_count="$(_task_push_unpushed_count)"

    local max_attempts=3
    local attempt
    for (( attempt=1; attempt<=max_attempts; attempt++ )); do
        if push_err="$(_task_push_once 2>&1)"; then
            if [[ "$before_count" == "0" ]]; then
                TASK_PUSH_STATUS="up-to-date"
            else
                TASK_PUSH_STATUS="pushed"
            fi
            TASK_PUSH_UNPUSHED="$(_task_push_unpushed_count)"
            return 0
        fi
        # Pull with rebase to incorporate remote changes, then retry.
        # Accumulate every attempt's output: attempt 1 carries the real
        # blocker, later attempts only echo the state it left behind.
        if [[ $attempt -lt $max_attempts ]]; then
            out="$(_task_pull_rebase 2>&1)" || true
            rebase_err+="${out}"$'\n'
        fi
    done

    # All attempts exhausted — best-effort, so don't fail the workflow, but
    # don't report silent success either.
    TASK_PUSH_STATUS="failed"
    TASK_PUSH_REASON="$(_task_push_classify "$push_err" "$rebase_err")"
    TASK_PUSH_UNPUSHED="$(_task_push_unpushed_count)"
    if [[ "$TASK_PUSH_REASON" == "unknown" ]]; then
        detail="$(_task_push_first_line "${push_err}"$'\n'"${rebase_err}")"
        if [[ -n "$detail" ]]; then
            detail=" (git: ${detail})"
        fi
    fi
    _task_push_warn "$detail"
    return 0
}

# Print the structured one-line outcome of the last task_push call.
# This is the cross-process surface (`ait git push --batch`): in-process callers
# read the TASK_PUSH_* globals directly. Tokens reuse the vocabulary documented
# for `ait sync --batch`.
task_push_report() {
    case "$TASK_PUSH_STATUS" in
        pushed)     echo "PUSHED" ;;
        up-to-date) echo "NOTHING" ;;
        no-remote)  echo "NO_REMOTE" ;;
        failed)     echo "FAILED:${TASK_PUSH_REASON}:${TASK_PUSH_UNPUSHED:-unknown}" ;;
        *)          echo "ERROR:no-push-run" ;;
    esac
}

# Internal: single push attempt
_task_push_once() {
    _ait_data_git push --quiet
}

# Internal: pull with rebase to catch up with remote
_task_pull_rebase() {
    _ait_data_git pull --rebase --quiet
}

# --- task_push probes (each returns 0: they are consumed via "$(...)" inside
# --- scripts running `set -euo pipefail`, where a leaked non-zero status would
# --- abort the caller with no visible error) ---

# Internal: commits on HEAD that the upstream does not have. Prints nothing
# when the branch has no upstream.
_task_push_unpushed_count() {
    _ait_data_git rev-list --count '@{upstream}..HEAD' 2>/dev/null || true
}

# Internal: upstream ref name (e.g. origin/aitask-data); empty when unset.
_task_push_upstream() {
    _ait_data_git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true
}

# Internal: true when at least one git remote is configured.
_task_push_has_remote() {
    [[ -n "$(_ait_data_git remote 2>/dev/null || true)" ]]
}

# Internal: first non-blank line of a captured git output blob.
_task_push_first_line() {
    local line
    while IFS= read -r line; do
        if [[ -n "${line//[[:space:]]/}" ]]; then
            printf '%s' "$line"
            return 0
        fi
    done <<< "$1"
    return 0
}

# Internal: classify a failed push cycle from the captured git output.
# Pure (no git calls, no I/O) so every reason is unit-testable from fixtures.
#   $1 = push stderr, $2 = accumulated `pull --rebase` stderr
# Prints one reason code. The rebase blocker is matched BEFORE the push
# rejection: the rejection is only the symptom, the blocker is why the
# automatic recovery could not clear it.
_task_push_classify() {
    local push_err="$1" rebase_err="$2"
    local blob="${push_err}"$'\n'"${rebase_err}"

    case "$rebase_err" in
        *"cannot pull with rebase"*|*"unstaged changes"*|*"uncommitted changes"*|*"local changes"*"would be overwritten"*)
            echo "dirty_worktree"; return 0 ;;
    esac
    case "$rebase_err" in
        *CONFLICT*|*"could not apply"*|*"Resolve all conflicts"*|*"rebase-merge directory"*|*"rebase-apply"*)
            echo "rebase_conflict"; return 0 ;;
    esac
    # A configured remote but no upstream for the current branch: `git push`
    # says "has no upstream branch", `git pull` says "no tracking information".
    # Neither substring overlaps another arm, so the position is not
    # load-bearing.
    case "$blob" in
        *"no upstream branch"*|*"no tracking information"*)
            echo "no_upstream"; return 0 ;;
    esac
    case "$blob" in
        *"Could not read from remote repository"*|*"does not appear to be a git repository"*|\
        *"Could not resolve host"*|*"Connection refused"*|*"Authentication failed"*|\
        *"Permission denied"*|*"unable to access"*|*"No configured push destination"*|*"timed out"*)
            echo "remote_unreachable"; return 0 ;;
    esac
    case "$push_err" in
        *"non-fast-forward"*|*"fetch first"*|*"rejected"*|*"behind its remote"*)
            echo "diverged"; return 0 ;;
    esac
    echo "unknown"
}

# Internal: actionable recovery hint for a reason code.
#   $1 = reason code
#   $2 = command to suggest retrying (default './ait git push'); task_sync
#        passes './ait sync' so a failed pull is not sent to the push recovery.
_task_push_reason_hint() {
    local retry_cmd="${2:-./ait git push}"
    case "$1" in
        dirty_worktree)
            echo "data worktree has unstaged changes blocking rebase; reconcile with 'ait syncer'" ;;
        # The two converge-only codes below name './ait sync' — the
        # non-interactive converger the recovery tests actually drive — rather
        # than the 'ait syncer' TUI the older arms suggest.
        ff_blocked)
            echo "local edits to the same file(s) block the fast-forward; commit them or reconcile with './ait sync'" ;;
        local_diverged)
            echo "local data branch has both unpushed and unpulled commits; reconcile with './ait sync'" ;;
        rebase_conflict)
            echo "rebase stopped on conflicts; recover with './ait git rebase --abort' (or resolve and './ait git rebase --continue')" ;;
        no_upstream)
            # MUST be the './ait git' gateway form: in branch mode the branch
            # needing an upstream is aitask-data inside .aitask-data, and a bare
            # 'git branch' run at the repo root would retarget the CODE branch
            # instead, leaving every later sync failing.
            echo "task-data branch has no upstream; set one with './ait git branch --set-upstream-to=origin/<branch>' (or run 'ait setup' to repair the data branch)" ;;
        remote_unreachable)
            echo "remote unreachable (network, auth, or no configured destination); retry '${retry_cmd}' once connectivity is restored" ;;
        diverged)
            echo "remote has diverged (non-fast-forward) and the rebase retries did not resolve it; reconcile with 'ait syncer'" ;;
        *)
            echo "reason unknown; run './ait git-health' and inspect the data worktree manually" ;;
    esac
}

# Internal: emit the user-facing warning for a failed push cycle. Warns only
# when commits are actually stranded — an offline repo with nothing pending
# stays as quiet as it was before this reporting existed.
_task_push_warn() {
    local detail="${1:-}" upstream hint
    upstream="$(_task_push_upstream)"
    if [[ -n "$upstream" ]]; then
        upstream=" to ${upstream}"
    fi
    hint="$(_task_push_reason_hint "$TASK_PUSH_REASON")"

    if [[ -z "$TASK_PUSH_UNPUSHED" ]]; then
        warn "task data push failed (unpushed commit count unavailable) — ${hint}${detail}"
    elif [[ "$TASK_PUSH_UNPUSHED" != "0" ]]; then
        warn "${TASK_PUSH_UNPUSHED} commit(s) not pushed${upstream} — ${hint}${detail}"
    fi
}

# --- Task data convergence (best-effort, but never silent) ---
#
# task_data_converge() reconciles the LOCAL data branch with its upstream in
# both directions, without ever stashing or committing. It exists because the
# metadata updaters push straight to origin from a throwaway clone, leaving the
# local ref behind: the compensating `pull --rebase` refuses (exit 128) BEFORE
# it fetches whenever the shared .aitask-data worktree is dirty, so nothing
# converges and the next local commit creates real divergence.
#
# The reconcile seam is `fetch` + `merge --ff-only`, NOT `pull --rebase`
# (measured on git 2.55.0 with the worktree dirty): the rebase refuses in every
# dirty case, while the fast-forward succeeds when the dirty paths do not
# overlap and fails closed ("would be overwritten by merge ... Aborting") when
# they do. `--autostash` and a wholesale auto-commit are both rejected: each
# would touch OTHER live sessions' uncommitted aitasks/ / aiplans/ edits in the
# shared worktree. This function never stashes and never commits anything.
#
# Same contract as task_push(): always returns 0, outcome in globals, one
# warn() on stderr, silent on success. It calls _ait_data_git / _task_push_once
# directly rather than task_push(), so it inherits no die() pre-flight.
TASK_CONVERGE_STATUS=""   # converged|fast-forwarded|pushed|diverged|blocked|no-remote|failed
TASK_CONVERGE_REASON=""   # classifier code when blocked/diverged/failed
TASK_CONVERGE_AHEAD=""    # local commits not on upstream (post-cycle)
TASK_CONVERGE_BEHIND=""   # upstream commits not on HEAD (post-cycle)

# A race can turn ahead-only into ahead-and-behind between our fetch and our
# push. Two passes bound the retry; see the push arm below for the single
# trigger that consumes the second one.
_AIT_CONVERGE_MAX_PASSES=2

task_data_converge() {
    local context="${1:-}"
    TASK_CONVERGE_STATUS=""
    TASK_CONVERGE_REASON=""
    TASK_CONVERGE_AHEAD=""
    TASK_CONVERGE_BEHIND=""

    # No remote at all (solo / offline-only repo): nothing to reconcile.
    if ! _task_push_has_remote; then
        TASK_CONVERGE_STATUS="no-remote"
        return 0
    fi

    local upstream
    upstream="$(_task_push_upstream)"
    if [[ -z "$upstream" ]]; then
        TASK_CONVERGE_STATUS="failed"
        TASK_CONVERGE_REASON="no_upstream"
        _task_converge_warn "$context"
        return 0
    fi

    local pass fetch_err ahead behind ff_err push_err reason
    for (( pass=1; pass<=_AIT_CONVERGE_MAX_PASSES; pass++ )); do
        # A plain fetch never touches the worktree. This is the step the old
        # `pull --rebase` never reached, because it refused first.
        if ! fetch_err="$(_ait_data_git fetch --quiet 2>&1)"; then
            TASK_CONVERGE_STATUS="failed"
            TASK_CONVERGE_REASON="$(_task_push_classify "$fetch_err" "")"
            TASK_CONVERGE_AHEAD="$(_task_push_unpushed_count)"
            TASK_CONVERGE_BEHIND="$(_task_sync_unpulled_count)"
            _task_converge_warn "$context"
            return 0
        fi

        ahead="$(_task_push_unpushed_count)"
        behind="$(_task_sync_unpulled_count)"
        TASK_CONVERGE_AHEAD="$ahead"
        TASK_CONVERGE_BEHIND="$behind"

        # Both counts diverged: resolving needs a rebase, and a rebase needs the
        # shared worktree. Report it and hand ownership to './ait sync'.
        if [[ "${ahead:-0}" != "0" && "${behind:-0}" != "0" ]]; then
            TASK_CONVERGE_STATUS="diverged"
            TASK_CONVERGE_REASON="local_diverged"
            _task_converge_warn "$context"
            return 0
        fi

        if [[ "${behind:-0}" != "0" ]]; then
            if ff_err="$(_ait_data_git merge --ff-only --quiet "$upstream" 2>&1)"; then
                TASK_CONVERGE_STATUS="fast-forwarded"
                TASK_CONVERGE_AHEAD="$(_task_push_unpushed_count)"
                TASK_CONVERGE_BEHIND="$(_task_sync_unpulled_count)"
                return 0
            fi
            # Terminal and fails closed: the worktree is still dirty, so another
            # pass cannot change the answer. The classifier already maps git's
            # "local changes ... would be overwritten by merge" to
            # dirty_worktree; remap it so the hint names a merge, not a rebase.
            reason="$(_task_push_classify "" "$ff_err")"
            [[ "$reason" == "dirty_worktree" ]] && reason="ff_blocked"
            TASK_CONVERGE_STATUS="blocked"
            TASK_CONVERGE_REASON="$reason"
            _task_converge_warn "$context"
            return 0
        fi

        if [[ "${ahead:-0}" != "0" ]]; then
            if push_err="$(_task_push_once 2>&1)"; then
                TASK_CONVERGE_STATUS="pushed"
                TASK_CONVERGE_AHEAD="$(_task_push_unpushed_count)"
                TASK_CONVERGE_BEHIND="$(_task_sync_unpulled_count)"
                return 0
            fi
            reason="$(_task_push_classify "$push_err" "")"
            # A non-fast-forward rejection here means another writer advanced
            # origin between our fetch and our push. That is a LOST RACE, not a
            # failure: the true state is now ahead-and-behind. Re-fetch and
            # re-sample so it gets classified from the COUNTS as
            # diverged/local_diverged. This `continue` is the ONLY thing that
            # consumes a second pass — every other arm returns.
            if [[ "$reason" == "diverged" ]]; then
                continue
            fi
            # Not a race (remote_unreachable / no_upstream / unknown): another
            # pass buys nothing.
            TASK_CONVERGE_STATUS="failed"
            TASK_CONVERGE_REASON="$reason"
            _task_converge_warn "$context"
            return 0
        fi

        TASK_CONVERGE_STATUS="converged"
        return 0
    done

    # Passes exhausted: reached only when the last pass's push also lost the
    # race. The final counts are the truth, not the push's error string — the
    # same rule the ahead-and-behind arm above follows.
    TASK_CONVERGE_AHEAD="$(_task_push_unpushed_count)"
    TASK_CONVERGE_BEHIND="$(_task_sync_unpulled_count)"
    if [[ "${TASK_CONVERGE_AHEAD:-0}" != "0" && "${TASK_CONVERGE_BEHIND:-0}" != "0" ]]; then
        TASK_CONVERGE_STATUS="diverged"
        TASK_CONVERGE_REASON="local_diverged"
    else
        TASK_CONVERGE_STATUS="failed"
        TASK_CONVERGE_REASON="diverged"
    fi
    _task_converge_warn "$context"
    return 0
}

# Internal: emit the user-facing warning for a non-success converge cycle.
# Mirrors _task_sync_warn (:354). Success statuses emit nothing.
_task_converge_warn() {
    local context="${1:-}" upstream hint
    upstream="$(_task_push_upstream)"
    if [[ -n "$upstream" ]]; then
        upstream=" with ${upstream}"
    fi
    hint="$(_task_push_reason_hint "$TASK_CONVERGE_REASON" "./ait sync")"
    if [[ -n "$context" ]]; then
        context=" (${context})"
    fi

    # Both probes print nothing when the branch has no upstream, so a default of
    # 0 would report "0 unpushed, 0 remote unpulled" — a concrete, false claim
    # about a state where the counts are simply UNKNOWN. Say so instead, exactly
    # as _task_sync_warn does.
    if [[ -z "$TASK_CONVERGE_AHEAD" && -z "$TASK_CONVERGE_BEHIND" ]]; then
        warn "task data not converged [${TASK_CONVERGE_STATUS}]${upstream} (unreconciled commit counts unavailable) — ${hint}${context}"
        return 0
    fi

    # Name the status: unlike _task_sync_warn, which only ever reports "failed",
    # this one line carries three distinct non-success outcomes (blocked /
    # diverged / failed) and the hint alone does not separate them.
    warn "task data not converged [${TASK_CONVERGE_STATUS}]${upstream}: ${TASK_CONVERGE_AHEAD:-0} local unpushed, ${TASK_CONVERGE_BEHIND:-0} remote unpulled — ${hint}${context}"
}

# --- YAML List Parsing ---

# Parse a YAML inline list value to comma-separated string.
# Strips brackets, quotes, and spaces: "['38', t85_2]" -> "38,t85_2"
parse_yaml_list() {
    local value="$1"
    echo "$value" | tr -d "[]'\"" | tr -d ' '
}

# --- YAML List Formatting ---

# Format a comma-separated string as a YAML inline list.
# "1,3,5" -> "[1, 3, 5]"; empty input -> "[]".
# Inverse of parse_yaml_list.
format_yaml_list() {
    local input="$1"
    if [[ -z "$input" ]]; then
        echo "[]"
    else
        echo "[$(echo "$input" | sed 's/,/, /g')]"
    fi
}

# --- Label Vocabulary Management ---
#
# Canonical implementation of the label vocabulary seam (aitasks/metadata/
# labels.txt). aitask_create.sh, aitask_update.sh, aitask_pr_import.sh,
# aitask_issue_import.sh and aitask_labels.sh all call these — do NOT re-define
# any of them in a caller: a later definition shadows the lib and the shared
# behaviour silently disappears (tests/test_label_vocabulary_lib.sh pins this).

# Resolve the vocabulary file path, honoring a caller-set LABELS_FILE.
# Lazy on purpose: aitask_create.sh sets TASK_DIR *after* sourcing this lib, and
# tests export a temp TASK_DIR before sourcing.
labels_file_path() {
    if [[ -n "${LABELS_FILE:-}" ]]; then
        printf '%s' "$LABELS_FILE"
    else
        printf '%s' "${TASK_DIR:-aitasks}/metadata/labels.txt"
    fi
}

# Canonicalize a single label: lowercase, non-[a-z0-9_-] -> "_", collapse runs
# of "_", trim leading/trailing "_". "UI Stuff" -> "ui_stuff"; "!!!" -> "".
# Matches github_map_labels() in aitask_pr_import.sh so imported and
# locally-minted labels agree.
#
# Control characters are folded FIRST, before the line-oriented stages. `sed`
# processes one line at a time, so an embedded newline would otherwise survive
# the whole pipeline: `--add-label $'alpha\nbeta'` then wrote a two-line
# `labels: [...]` inline list (which YAML folds to the space-bearing label
# "alpha beta") while the CSV registration saw only the first line — the
# frontmatter and the vocabulary disagreed, and labels.txt is itself
# line-delimited. Folding to "_" rather than deleting keeps the two halves
# distinguishable ("alpha_beta", not "alphabeta").
sanitize_label() {
    local label="$1"
    printf '%s' "$label" | tr '[:cntrl:]' '_' | tr '[:upper:]' '[:lower:]' \
        | sed -e 's/[^a-z0-9_-]/_/g' -e 's/__*/_/g' -e 's/^_//' -e 's/_$//'
}

ensure_labels_file() {
    local file dir
    file=$(labels_file_path)
    dir=$(dirname "$file")
    mkdir -p "$dir"
    touch "$file"
}

# Print the vocabulary, sorted. Always returns 0 — a bare `[[ -s ]] && sort`
# returns 1 on an empty file and would abort `set -e` callers.
get_existing_labels() {
    local file
    ensure_labels_file
    file=$(labels_file_path)
    if [[ -s "$file" ]]; then
        LC_ALL=C sort -u "$file"
    fi
    return 0
}

# --- Rich-return globals (see add_labels_csv_to_file) ---
# NEVER call the label helpers via $( ) — command substitution runs them in a
# subshell and these globals evaporate with it. Read them after a direct call.
AIT_LABELS_NORMALIZED=""   # normalized CSV, safe for frontmatter
AIT_LABELS_ADDED=()        # labels newly appended to the vocabulary this call
AIT_LABELS_DROPPED=()      # input tokens that sanitized to nothing

# Append a label to the vocabulary if absent. Appends to AIT_LABELS_ADDED when
# it actually wrote. Always returns 0 (callers invoke it bare under `set -e`).
add_label_to_file() {
    local label="$1"
    local file tmp
    [[ -z "$label" ]] && return 0
    # Write-site guard for a line-delimited file: a control character (newline
    # above all) would inject extra vocabulary entries that no reader can tell
    # apart from real ones. Undecidable on read, so neutralize on write. Every
    # in-tree caller passes a sanitize_label output, so this never fires in
    # practice — it exists so a future caller cannot corrupt the file.
    # Matched in-shell on purpose: grep is line-oriented and can never see the
    # newline it is meant to catch (it splits the input on exactly that byte).
    if [[ "$label" == *[[:cntrl:]]* ]]; then
        warn "refusing to register a label containing a control character"
        return 0
    fi
    ensure_labels_file
    file=$(labels_file_path)
    # -F/-x: labels may legitimately start with "-" or contain regex chars.
    if grep -qFx -- "$label" "$file" 2>/dev/null; then
        return 0
    fi
    # temp-file + mv so concurrent readers never see a torn file.
    # LC_ALL=C pins collation: the committed file must not reorder by locale.
    tmp="${file}.tmp.$$"
    { cat "$file"; echo "$label"; } | LC_ALL=C sort -u > "$tmp" && mv "$tmp" "$file"
    AIT_LABELS_ADDED+=("$label")
    return 0
}

# Pure: split a CSV on ",", trim, sanitize, drop empties, order-preserving
# dedupe. stdout = normalized CSV. stderr = "DROPPED:<tok1>,<tok2>" when any
# input token sanitized to nothing. Writes no files.
normalize_labels_csv() {
    local csv="$1"
    local -a parts=() kept=() dropped=()
    local raw trimmed clean k found
    [[ -z "$csv" ]] && { printf ''; return 0; }
    # `read` consumes ONE line: an embedded newline would silently truncate the
    # token list (",a\nb,c" yielded just "a"). Fold control characters first so
    # every token survives the split, then sanitize_label canonicalizes each.
    csv=$(printf '%s' "$csv" | tr '[:cntrl:]' '_')
    IFS=',' read -ra parts <<< "$csv"
    for raw in "${parts[@]}"; do
        trimmed="${raw#"${raw%%[![:space:]]*}"}"
        trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
        [[ -z "$trimmed" ]] && continue
        clean=$(sanitize_label "$trimmed")
        if [[ -z "$clean" ]]; then
            dropped+=("$trimmed")
            continue
        fi
        found=false
        for k in ${kept[@]+"${kept[@]}"}; do
            [[ "$k" == "$clean" ]] && { found=true; break; }
        done
        [[ "$found" == false ]] && kept+=("$clean")
    done
    if (( ${#dropped[@]} > 0 )); then
        echo "DROPPED:$(IFS=','; printf '%s' "${dropped[*]}")" >&2
    fi
    if (( ${#kept[@]} > 0 )); then
        printf '%s' "$(IFS=','; printf '%s' "${kept[*]}")"
    fi
    return 0
}

# Normalize a CSV and register every resulting label in the vocabulary.
# Sets AIT_LABELS_NORMALIZED / AIT_LABELS_ADDED / AIT_LABELS_DROPPED.
# Call directly (never via $( )) — the results are the globals, not stdout.
# shellcheck disable=SC2034  # the AIT_LABELS_* globals ARE the return value; they are read by callers in other files
add_labels_csv_to_file() {
    local csv="$1"
    local normalized dropped_line
    AIT_LABELS_NORMALIZED=""
    AIT_LABELS_ADDED=()
    AIT_LABELS_DROPPED=()
    [[ -z "$csv" ]] && return 0
    # Two-call stdout/stderr split (same idiom as filter_gates_for_issue_type).
    dropped_line=$(normalize_labels_csv "$csv" 2>&1 >/dev/null)
    normalized=$(normalize_labels_csv "$csv" 2>/dev/null)
    if [[ -n "$dropped_line" ]]; then
        IFS=',' read -ra AIT_LABELS_DROPPED <<< "${dropped_line#DROPPED:}"
    fi
    AIT_LABELS_NORMALIZED="$normalized"
    [[ -z "$normalized" ]] && return 0
    local -a tokens=()
    IFS=',' read -ra tokens <<< "$normalized"
    local t
    for t in "${tokens[@]}"; do
        add_label_to_file "$t"
    done
    return 0
}

# Gates a `manual_verification` task can actually REACH: the machine gates
# recorded in task-workflow Step 9. Manual verification skips Steps 6-8
# (plan / risk / review), so any gate whose checkpoint lives there is
# unreachable and must not be declared on such a task (it would block archival
# forever — see t1156). This is an ALLOWLIST (not a denylist) on purpose: an
# unknown/new gate is stripped by default, so a future planning gate added to a
# profile's default_gates can never silently make a manual_verification task
# unarchivable. See .claude/skills/task-workflow/manual-verification.md
# (Steps 6-8 skipped) and aitasks/metadata/gates.yaml. `merge_approved` is
# intentionally excluded (profile-conditional human gate, never auto-injected).
MANUAL_VERIFICATION_REACHABLE_GATES="build_verified tests_pass lint"

# filter_gates_for_issue_type <issue_type> <csv-gates>
#   Echoes the kept gates as a CSV on stdout. Echoes "STRIPPED:<csv>" on stderr
#   iff any unreachable gate was removed. Only `manual_verification` filters;
#   every other issue_type passes its gates through unchanged.
filter_gates_for_issue_type() {
    local issue_type="$1" csv="$2"
    if [[ "$issue_type" != "manual_verification" || -z "$csv" ]]; then
        printf '%s' "$csv"
        return 0
    fi
    local kept=() stripped=() g
    local _gates
    IFS=',' read -ra _gates <<< "$csv"
    for g in "${_gates[@]}"; do
        g="${g// /}"
        [[ -z "$g" ]] && continue
        if [[ " $MANUAL_VERIFICATION_REACHABLE_GATES " == *" $g "* ]]; then
            kept+=("$g")
        else
            stripped+=("$g")
        fi
    done
    local IFS=','
    printf '%s' "${kept[*]}"
    [[ ${#stripped[@]} -gt 0 ]] && printf 'STRIPPED:%s\n' "${stripped[*]}" >&2
    return 0
}

# join_yaml_flow_lists and read_yaml_field are defined in yaml_utils.sh
# (sourced above) — a shared lib so agentcrew_utils.sh can reuse the same
# canonical readers without a copy of its own.

# --- Issue-type vocabulary (shell-side reader) ---

# read_valid_task_types [file]
# Pure reader for the issue-type vocabulary — prints one type per line, sorted.
# Unlike the callers' get_valid_task_types wrappers it does NOT call
# ensure_task_types_file: a read-only lister (aitask_ls.sh) must never create
# files in the user's repo. Callers that legitimately need the file to exist
# keep their own ensure_task_types_file call around this one.
#
# Folding the whole vocabulary onto one seam across the 32+ duplication sites is
# t720's job (issue_type_list_single_source_of_truth); this is only the
# shell-side reader, a down-payment on it and not a substitute.
read_valid_task_types() {
    local f="${1:-${TASK_TYPES_FILE:-aitasks/metadata/task_types.txt}}"
    if [[ -s "$f" ]]; then
        sort -u "$f"
    else
        printf '%s\n' "bug" "feature" "refactor"
    fi
}

# --- Task level enum (single source of truth) ---

# Canonical task level enum (high/medium/low), shared by priority, effort, and
# the two risk fields (risk_code_health, risk_goal_achievement). Single bash
# source of truth — Python mirror: .aitask-scripts/lib/task_levels.py.
TASK_LEVELS="high medium low"   # canonical, severity-descending

# Return 0 if $1 is a valid task level, non-zero otherwise (empty => invalid).
is_valid_task_level() {
    local val="$1" level
    for level in $TASK_LEVELS; do
        [[ "$val" == "$level" ]] && return 0
    done
    return 1
}

# Emit the levels one-per-line for interactive pickers (e.g. fzf).
task_levels_lines()     { printf '%s\n' high medium low; }   # canonical (desc)
task_levels_lines_asc() { printf '%s\n' low medium high; }   # ascending

# --- Helper: read status of a folded task ---
read_task_status() {
    local file_path="$1"
    read_yaml_field "$file_path" "status"
}

# --- Cross-repo dependency field readers ---

# Read the xdeps list as a normalized comma-separated string (e.g. "1,t42_3").
# Empty when the field is absent.
read_xdeps() {
    local file_path="$1"
    local raw
    raw=$(read_yaml_field "$file_path" "xdeps")
    [[ -z "$raw" ]] && return 0
    local parsed
    parsed=$(parse_yaml_list "$raw")
    normalize_task_ids "$parsed"
}

# Read the xdeprepo scalar (cross-repo project name). Empty when absent.
read_xdeprepo() {
    local file_path="$1"
    read_yaml_field "$file_path" "xdeprepo"
}

# Validate the cross-repo dep pair.
#
# As of t832_10:
#   - Neither set                 → no-op (most tasks).
#   - Both set                    → BATCH_XDEPREPO must resolve cleanly;
#                                   every id in BATCH_XDEPS must exist in
#                                   the cross-repo project.
#   - BATCH_XDEPREPO alone        → OK (intent-only; the new task declares
#                                   cross-repo coordination without any
#                                   concrete deps yet). The xdeprepo
#                                   registry resolution still runs.
#   - BATCH_XDEPS alone           → die (xdeps cannot exist without a
#                                   project context to resolve them in).
#
# Reads globals: BATCH_XDEPS, BATCH_XDEPREPO, SCRIPT_DIR. Callers
# (create.sh, update.sh) populate these before invoking.
validate_xdeps_pair() {
    if [[ -z "${BATCH_XDEPS:-}" && -z "${BATCH_XDEPREPO:-}" ]]; then
        return 0
    fi
    if [[ -n "${BATCH_XDEPS:-}" && -z "${BATCH_XDEPREPO:-}" ]]; then
        die "--xdeps requires --xdeprepo (xdeps without a project context cannot be resolved)."
    fi

    local resolved
    resolved=$("$SCRIPT_DIR/aitask_project_resolve.sh" "$BATCH_XDEPREPO" 2>/dev/null || true)
    case "$resolved" in
        RESOLVED:*) ;;
        STALE:*)
            die "Project '$BATCH_XDEPREPO' is registered but its path is stale: ${resolved#STALE:}"
            ;;
        NOT_FOUND:*|"")
            die "Project '$BATCH_XDEPREPO' is not registered. Run \`cd /path/to/$BATCH_XDEPREPO && ait projects add\`."
            ;;
        *)
            die "Project resolver returned unexpected output for '$BATCH_XDEPREPO': $resolved"
            ;;
    esac

    local IFS=','
    local id
    for id in $BATCH_XDEPS; do
        id="${id#t}"
        [[ -z "$id" ]] && continue
        local result
        result=$("$SCRIPT_DIR/aitask_query_files.sh" --project "$BATCH_XDEPREPO" task-status "$id" 2>/dev/null || true)
        case "$result" in
            STATUS:NOT_FOUND|"")
                die "--xdeps id $id not found in cross-repo project '$BATCH_XDEPREPO'."
                ;;
            STATUS:*) ;;
            *)
                die "Unexpected task-status output for xdeps id $id in '$BATCH_XDEPREPO': $result"
                ;;
        esac
    done
}

# --- Anchor field helper ---

# Normalize and validate an anchor task id (intra-repo, archived-inclusive).
#
# Accepts a raw id with an optional single leading "t" (e.g. t42, 42, t42_1,
# 42_1), strips it, asserts the id shape (N or N_M), and verifies the task
# exists (any status, including Done/archived, is valid — anchoring to a
# completed topic root is allowed). Echoes the BARE id so callers store/resolve
# the canonical form (so `--anchor t42` and `--anchor 42` are identical, and the
# stored `anchor:` value equals a root's bare own-id group key).
#
# Dies on a malformed id or a non-existent target. Mirrors the local
# strip_prefix in aitask_query_files.sh, but t-only and shared.
#
# Reads global: SCRIPT_DIR.
normalize_anchor_id() {
    local raw="$1"
    local id="${raw#t}"
    if [[ ! "$id" =~ ^[0-9]+(_[0-9]+)?$ ]]; then
        die "anchor target '$raw' is not a valid task id (expected N or N_M)."
    fi
    local status
    status=$("$SCRIPT_DIR/aitask_query_files.sh" task-status "$id" 2>/dev/null || true)
    case "$status" in
        STATUS:NOT_FOUND|"")
            die "anchor target '$id' not found."
            ;;
        STATUS:*)
            echo "$id"
            ;;
        *)
            die "anchor target '$id': unexpected status result '$status'."
            ;;
    esac
}

# Validate a board column id against this project's configured columns (t1377_1).
# Echoes the id unchanged when valid; dies naming the valid ids otherwise.
#
# Before this existed, `ait update --boardcol <bad-id>` wrote the value verbatim
# and produced a task that rendered in NO column at all — not even `unordered` —
# and that the work-report gatherer could not name either.
#
# The synthetic `unordered` is a legal target, so the listing is requested with
# --include-unordered. The probe reads only board_config.json; deliberately NOT
# `aitask_work_report_gather.sh --list-columns`, which globs and parses every
# task file just to decide whether to prepend `unordered` (O(all tasks) per
# `ait update` call).
#
# `$TASK_DIR` is forwarded so a repo using a non-default layout validates against
# its own columns instead of the stock defaults.
#
# Reads globals: SCRIPT_DIR, TASK_DIR.
normalize_board_column() {
    local raw="$1"
    local listing valid_ids
    if ! listing=$("$SCRIPT_DIR/aitask_board_column.sh" list-columns \
            --root . --task-dir "${TASK_DIR:-aitasks}" --include-unordered 2>/dev/null); then
        die "board column '$raw': could not read the configured column list."
    fi
    # Column ids never contain '|' (load_columns rejects that), so cutting at the
    # first separator is exact.
    valid_ids=$(printf '%s\n' "$listing" | sed -n 's/^COLUMN:\([^|]*\)|.*/\1/p')
    if [[ -z "$valid_ids" ]]; then
        die "board column '$raw': no board columns are configured."
    fi
    local cid
    while IFS= read -r cid; do
        if [[ "$cid" == "$raw" ]]; then
            echo "$raw"
            return 0
        fi
    done <<< "$valid_ids"
    die "board column '$raw' is not configured. Valid ids: $(printf '%s' "$valid_ids" | tr '\n' ' ')"
}

# Normalize child task IDs: ensure entries with underscore have 't' prefix.
# e.g. "85_2,t85_3,16" -> "t85_2,t85_3,16"
normalize_task_ids() {
    local input="$1"
    [[ -z "$input" ]] && return
    local result=""
    IFS=',' read -ra ids <<< "$input"
    for id in "${ids[@]}"; do
        if [[ "$id" =~ ^[0-9]+_[0-9]+$ ]]; then
            id="t${id}"
        fi
        [[ -n "$result" ]] && result="${result},"
        result="${result}${id}"
    done
    echo "$result"
}

# --- Per-user Config ---

# Read the current user's email from the local (gitignored) userconfig.yaml
# Output: email string, or empty if file missing / field not found
get_user_email() {
    local config="${TASK_DIR:-aitasks}/metadata/userconfig.yaml"
    if [[ -f "$config" ]]; then
        grep '^email:' "$config" | sed 's/^email: *//'
    fi
}

# Read the last-used labels list from userconfig.yaml (per-user).
# Output: CSV string (e.g. "ui,backend"), empty when field or file is absent.
# Delegates to the yaml-aware userconfig_persist.py so both flow- and
# block-style values are read correctly; falls back to a flow-only grep read
# when no Python interpreter is available (read-only, never corrupts).
get_last_used_labels() {
    local config="${TASK_DIR:-aitasks}/metadata/userconfig.yaml"
    [[ -f "$config" ]] || return 0

    local py out
    py="$(resolve_python 2>/dev/null || true)"
    if [[ -n "$py" ]]; then
        if out="$(TASK_DIR="${TASK_DIR:-aitasks}" "$py" \
            "${SCRIPT_DIR}/lib/userconfig_persist.py" get-labels 2>/dev/null)"; then
            printf '%s' "$out"
            return 0
        fi
    fi

    # Fallback (no Python): flow-style single-line read only.
    local line
    line=$(grep '^last_used_labels:' "$config" 2>/dev/null) || true
    [[ -z "$line" ]] && return 0
    echo "$line" | sed -e 's/^last_used_labels:[[:space:]]*//' \
                       -e 's/^\[//' \
                       -e 's/\][[:space:]]*$//' \
                       -e 's/[[:space:]]//g'
}

# Write the last-used labels list to userconfig.yaml (per-user).
# Input: CSV string (e.g. "ui,backend") — empty is valid and writes "[]".
# Delegates to the yaml-aware userconfig_persist.py, which round-trips the whole
# file safely so it can never orphan a prior block-style value into invalid
# YAML. Falls back to a block-safe bash writer when no Python is available.
set_last_used_labels() {
    local csv="${1:-}"
    local config="${TASK_DIR:-aitasks}/metadata/userconfig.yaml"
    mkdir -p "$(dirname "$config")"

    local py
    py="$(resolve_python 2>/dev/null || true)"
    if [[ -n "$py" ]]; then
        if TASK_DIR="${TASK_DIR:-aitasks}" "$py" \
            "${SCRIPT_DIR}/lib/userconfig_persist.py" set-labels "$csv" 2>/dev/null; then
            return 0
        fi
    fi

    _set_last_used_labels_fallback "$csv" "$config"
}

# Block-safe bash writer, used only when no Python interpreter is available.
# Writes flow style ([a, b]) and, when replacing an existing value, also removes
# any block-style continuation lines ("- item") that followed the header — so a
# value previously written in block style cannot orphan list items into invalid
# YAML. Deletion stops at the first non-list line, so a following block such as
# "shortcuts:" is never touched.
_set_last_used_labels_fallback() {
    local csv="$1" config="$2"
    local yaml_list
    if [[ -z "$csv" ]]; then
        yaml_list="[]"
    else
        yaml_list="[$(echo "$csv" | sed 's/,/, /g')]"
    fi

    if [[ ! -f "$config" ]]; then
        {
            echo "# Local user configuration (gitignored, not shared)"
            echo "last_used_labels: $yaml_list"
        } > "$config"
        return 0
    fi

    if grep -q '^last_used_labels:' "$config" 2>/dev/null; then
        local tmp
        tmp="$(mktemp)"
        awk -v repl="last_used_labels: ${yaml_list}" '
            drop && /^[[:space:]]*-[[:space:]]/ { next }
            drop { drop=0 }
            /^last_used_labels:/ { print repl; drop=1; next }
            { print }
        ' "$config" > "$tmp" && mv "$tmp" "$config"
    else
        echo "last_used_labels: $yaml_list" >> "$config"
    fi
}

# --- Platform Detection ---

# Detect git remote platform from origin URL
# Output: "github", "gitlab", "bitbucket", or "" (unknown)
detect_platform() {
    local remote_url
    remote_url=$(git remote get-url origin 2>/dev/null || echo "")
    if [[ "$remote_url" == *"gitlab"* ]]; then
        echo "gitlab"
    elif [[ "$remote_url" == *"bitbucket"* ]]; then
        echo "bitbucket"
    elif [[ "$remote_url" == *"github"* ]]; then
        echo "github"
    else
        echo ""
    fi
}

# Detect platform from an issue/web URL
# Input: URL string
# Output: "github", "gitlab", "bitbucket", or "" (unknown)
detect_platform_from_url() {
    local url="$1"
    if [[ "$url" == *"gitlab"* ]]; then
        echo "gitlab"
    elif [[ "$url" == *"bitbucket"* ]]; then
        echo "bitbucket"
    elif [[ "$url" == *"github"* ]]; then
        echo "github"
    else
        echo ""
    fi
}

# --- Task and Plan Resolution ---
# Archive search/extract primitives provided by archive_utils.sh:
#   _search_archive(), _extract_from_archive(), _find_archive_for_task()
# Temp directory cleanup handled by _AIT_ARCHIVE_TMPDIR in archive_utils.sh

# Resolve task number to file path, checking both active and archived directories
# Input: task_id (e.g., "53" or "53_6")
# Output: file path
resolve_task_file() {
    local task_id="$1"
    local files=""

    if [[ "$task_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent_num="${BASH_REMATCH[1]}"
        local child_num="${BASH_REMATCH[2]}"

        # Check active directory first
        files=$(ls "$TASK_DIR"/t${parent_num}/t${parent_num}_${child_num}_*.md 2>/dev/null || true)

        # Check archived directory
        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_DIR"/t${parent_num}/t${parent_num}_${child_num}_*.md 2>/dev/null || true)
        fi

        # Tier 3: numbered archives (computed path, then legacy fallback)
        if [[ -z "$files" ]]; then
            local archive_path="" tar_match=""
            archive_path=$(_find_archive_for_task "$parent_num" "$ARCHIVED_DIR")
            if [[ -n "$archive_path" ]]; then
                tar_match=$(_search_archive "$archive_path" "(^|/)t${parent_num}/t${parent_num}_${child_num}_.*\.md$")
            fi
            if [[ -z "$tar_match" ]]; then
                local legacy
                for legacy in "$ARCHIVED_DIR/old.tar.zst" "$ARCHIVED_DIR/old.tar.gz"; do
                    [[ -f "$legacy" ]] || continue
                    archive_path="$legacy"
                    tar_match=$(_search_archive "$archive_path" "(^|/)t${parent_num}/t${parent_num}_${child_num}_.*\.md$")
                    [[ -n "$tar_match" ]] && break
                done
            fi
            if [[ -n "$tar_match" ]]; then
                _extract_from_archive "$archive_path" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi

        if [[ -z "$files" ]]; then
            die "No task file found for t${parent_num}_${child_num} (checked active, archived, and numbered archives)"
        fi
    else
        # Parent task
        files=$(ls "$TASK_DIR"/t${task_id}_*.md 2>/dev/null || true)

        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_DIR"/t${task_id}_*.md 2>/dev/null || true)
        fi

        # Tier 3: numbered archives (computed path, then legacy fallback)
        if [[ -z "$files" ]]; then
            local archive_path="" tar_match=""
            archive_path=$(_find_archive_for_task "$task_id" "$ARCHIVED_DIR")
            if [[ -n "$archive_path" ]]; then
                tar_match=$(_search_archive "$archive_path" "(^|/)t${task_id}_.*\.md$")
            fi
            if [[ -z "$tar_match" ]]; then
                local legacy
                for legacy in "$ARCHIVED_DIR/old.tar.zst" "$ARCHIVED_DIR/old.tar.gz"; do
                    [[ -f "$legacy" ]] || continue
                    archive_path="$legacy"
                    tar_match=$(_search_archive "$archive_path" "(^|/)t${task_id}_.*\.md$")
                    [[ -n "$tar_match" ]] && break
                done
            fi
            if [[ -n "$tar_match" ]]; then
                _extract_from_archive "$archive_path" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi

        if [[ -z "$files" ]]; then
            die "No task file found for task number $task_id (checked active, archived, and numbered archives)"
        fi
    fi

    local count
    count=$(echo "$files" | wc -l)

    if [[ "$count" -gt 1 ]]; then
        die "Multiple task files found for task $task_id"
    fi

    echo "$files"
}

# Resolve plan file from task number, checking both active and archived
# Plan naming convention:
#   Parent task t53_name.md -> plan p53_name.md
#   Child task t53/t53_1_name.md -> plan p53/p53_1_name.md
# Input: task_id (e.g., "53" or "53_6")
# Output: file path or empty string if not found
resolve_plan_file() {
    local task_id="$1"
    local files=""

    if [[ "$task_id" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        local parent_num="${BASH_REMATCH[1]}"
        local child_num="${BASH_REMATCH[2]}"

        # Check active plan directory
        files=$(ls "$PLAN_DIR"/p${parent_num}/p${parent_num}_${child_num}_*.md 2>/dev/null || true)

        # Check archived plan directory
        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_PLAN_DIR"/p${parent_num}/p${parent_num}_${child_num}_*.md 2>/dev/null || true)
        fi

        # Tier 3: numbered archives (computed path, then legacy fallback)
        if [[ -z "$files" ]]; then
            local archive_path="" tar_match=""
            archive_path=$(_find_archive_for_task "$parent_num" "$ARCHIVED_PLAN_DIR")
            if [[ -n "$archive_path" ]]; then
                tar_match=$(_search_archive "$archive_path" "(^|/)p${parent_num}/p${parent_num}_${child_num}_.*\.md$")
            fi
            if [[ -z "$tar_match" ]]; then
                local legacy
                for legacy in "$ARCHIVED_PLAN_DIR/old.tar.zst" "$ARCHIVED_PLAN_DIR/old.tar.gz"; do
                    [[ -f "$legacy" ]] || continue
                    archive_path="$legacy"
                    tar_match=$(_search_archive "$archive_path" "(^|/)p${parent_num}/p${parent_num}_${child_num}_.*\.md$")
                    [[ -n "$tar_match" ]] && break
                done
            fi
            if [[ -n "$tar_match" ]]; then
                _extract_from_archive "$archive_path" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi
    else
        # Parent plan
        files=$(ls "$PLAN_DIR"/p${task_id}_*.md 2>/dev/null || true)

        if [[ -z "$files" ]]; then
            files=$(ls "$ARCHIVED_PLAN_DIR"/p${task_id}_*.md 2>/dev/null || true)
        fi

        # Tier 3: numbered archives (computed path, then legacy fallback)
        if [[ -z "$files" ]]; then
            local archive_path="" tar_match=""
            archive_path=$(_find_archive_for_task "$task_id" "$ARCHIVED_PLAN_DIR")
            if [[ -n "$archive_path" ]]; then
                tar_match=$(_search_archive "$archive_path" "(^|/)p${task_id}_.*\.md$")
            fi
            if [[ -z "$tar_match" ]]; then
                local legacy
                for legacy in "$ARCHIVED_PLAN_DIR/old.tar.zst" "$ARCHIVED_PLAN_DIR/old.tar.gz"; do
                    [[ -f "$legacy" ]] || continue
                    archive_path="$legacy"
                    tar_match=$(_search_archive "$archive_path" "(^|/)p${task_id}_.*\.md$")
                    [[ -n "$tar_match" ]] && break
                done
            fi
            if [[ -n "$tar_match" ]]; then
                _extract_from_archive "$archive_path" "$tar_match"
                files="$_AIT_EXTRACT_RESULT"
            fi
        fi
    fi

    if [[ -z "$files" ]]; then
        echo ""
        return
    fi

    local count
    count=$(echo "$files" | wc -l)
    if [[ "$count" -gt 1 ]]; then
        echo "$files" | head -1
    else
        echo "$files"
    fi
}

# Extract the issue URL from a task file's YAML frontmatter
# Input: task file path
# Output: issue URL or empty string
extract_issue_url() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then
                break
            else
                in_yaml=true
                continue
            fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^issue:[[:space:]]*(.*) ]]; then
            local url="${BASH_REMATCH[1]}"
            url=$(echo "$url" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$url"
            return
        fi
    done < "$file_path"

    echo ""
}

# Extract the pull request URL from a task file's YAML frontmatter
# Input: task file path
# Output: pull request URL or empty string
extract_pr_url() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then
                break
            else
                in_yaml=true
                continue
            fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^pull_request:[[:space:]]*(.*) ]]; then
            local url="${BASH_REMATCH[1]}"
            url=$(echo "$url" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$url"
            return
        fi
    done < "$file_path"

    echo ""
}

# Extract file_references entries from a task file's YAML frontmatter
# Input: task file path
# Output: one entry per line (newline-separated), empty if missing/empty
# Each entry is returned verbatim: "path", "path:N", "path:N-M",
# or compact multi-range "path:N-M^N-M^...".
get_file_references() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then break
            else in_yaml=true; continue; fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^file_references:[[:space:]]*(.*) ]]; then
            local raw="${BASH_REMATCH[1]}"
            raw="${raw#\[}" ; raw="${raw%\]}"
            if [[ -z "$raw" ]]; then return; fi
            while IFS=',' read -ra items; do
                for item in "${items[@]}"; do
                    item=$(echo "$item" | sed 's/^[[:space:]"]*//;s/[[:space:]"]*$//')
                    [[ -n "$item" ]] && echo "$item"
                done
            done <<< "$raw"
            return
        fi
    done < "$file_path"
}

# Validate a single file_reference entry string.
# Accepted: "path" | "path:N" | "path:N-M" | "path:N-M^N-M^..."
# Line numbers are 1-indexed. Die with a clear error on malformed input.
validate_file_ref() {
    local ref="$1"
    if [[ -z "$ref" ]]; then
        die "Empty file reference"
    fi
    if [[ ! "$ref" =~ ^[^:]+(:[0-9]+(-[0-9]+)?(\^[0-9]+(-[0-9]+)?)*)?$ ]]; then
        die "Invalid file reference: '$ref' (expected PATH[:N[-M][^N[-M]]...])"
    fi
}

# union_file_references <primary_file> [<folded_file> ...]
# Reads file_references from primary first, then each folded file in
# argument order. Dedupes by first-occurrence exact-string match.
# Prints the unioned list as CSV on stdout (empty if nothing to emit).
union_file_references() {
    local primary_file="$1"
    shift
    local -a merged=()
    declare -A seen=()
    local entry f

    if [[ -n "$primary_file" && -f "$primary_file" ]]; then
        while IFS= read -r entry; do
            [[ -z "$entry" ]] && continue
            if [[ -z "${seen[$entry]:-}" ]]; then
                seen[$entry]=1
                merged+=("$entry")
            fi
        done < <(get_file_references "$primary_file")
    fi

    for f in "$@"; do
        [[ -z "$f" || ! -f "$f" ]] && continue
        while IFS= read -r entry; do
            [[ -z "$entry" ]] && continue
            if [[ -z "${seen[$entry]:-}" ]]; then
                seen[$entry]=1
                merged+=("$entry")
            fi
        done < <(get_file_references "$f")
    done

    if [[ ${#merged[@]} -eq 0 ]]; then
        return 0
    fi
    local IFS=','
    echo "${merged[*]}"
}

# Extract related issue URLs from a task file's YAML frontmatter
# Input: task file path
# Output: one URL per line (newline-separated), empty if missing/empty
extract_related_issues() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then break
            else in_yaml=true; continue; fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^related_issues:[[:space:]]*(.*) ]]; then
            local raw="${BASH_REMATCH[1]}"
            # Strip brackets, split on comma, trim quotes/spaces
            raw="${raw#\[}" ; raw="${raw%\]}"
            if [[ -z "$raw" ]]; then return; fi
            while IFS=',' read -ra items; do
                for item in "${items[@]}"; do
                    item=$(echo "$item" | sed 's/^[[:space:]"]*//;s/[[:space:]"]*$//')
                    [[ -n "$item" ]] && echo "$item"
                done
            done <<< "$raw"
            return
        fi
    done < "$file_path"
}

# Extract the contributor username from a task file's YAML frontmatter
# Input: task file path
# Output: contributor username or empty string
extract_contributor() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then
                break
            else
                in_yaml=true
                continue
            fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^contributor:[[:space:]]*(.*) ]]; then
            local val="${BASH_REMATCH[1]}"
            val=$(echo "$val" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$val"
            return
        fi
    done < "$file_path"

    echo ""
}

# Extract the contributor email from a task file's YAML frontmatter
# Input: task file path
# Output: contributor email or empty string
extract_contributor_email() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then
                break
            else
                in_yaml=true
                continue
            fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^contributor_email:[[:space:]]*(.*) ]]; then
            local val="${BASH_REMATCH[1]}"
            val=$(echo "$val" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$val"
            return
        fi
    done < "$file_path"

    echo ""
}

# Extract the implemented_with agent string from a task file's YAML frontmatter
# Input: task file path
# Output: implemented_with value or empty string
extract_implemented_with() {
    local file_path="$1"
    local in_yaml=false

    while IFS= read -r line; do
        if [[ "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then
                break
            else
                in_yaml=true
                continue
            fi
        fi
        if [[ "$in_yaml" == true && "$line" =~ ^implemented_with:[[:space:]]*(.*) ]]; then
            local val="${BASH_REMATCH[1]}"
            val=$(echo "$val" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$val"
            return
        fi
    done < "$file_path"

    echo ""
}

# Extract "Final Implementation Notes" section from a plan file
# Input: plan file path
# Output: the section content
extract_final_implementation_notes() {
    local plan_path="$1"
    local in_section=false
    local content=""

    while IFS= read -r line; do
        if [[ "$line" =~ ^##[[:space:]]+Final[[:space:]]+Implementation[[:space:]]+Notes ]]; then
            in_section=true
            continue
        fi

        if [[ "$in_section" == true ]]; then
            # Stop at next level-2 heading
            if [[ "$line" =~ ^##[[:space:]] ]]; then
                break
            fi
            if [[ -n "$content" ]]; then
                content="${content}"$'\n'"${line}"
            else
                content="$line"
            fi
        fi
    done < "$plan_path"

    # Trim leading/trailing blank lines (awk for portability — BSD sed can't handle grouped multi-line commands)
    echo "$content" | sed '/./,$!d' | awk '{lines[NR]=$0} /[^[:space:]]/{last=NR} END{for(i=1;i<=last;i++) print lines[i]}'
}

# --- Contribute Metadata Parsing ---

# Parse aitask-contribute metadata from issue body HTML comment
# Sets global: CONTRIBUTE_CONTRIBUTOR, CONTRIBUTE_EMAIL, CONTRIBUTE_FINGERPRINT_VERSION,
#              CONTRIBUTE_AREAS, CONTRIBUTE_FILE_PATHS, CONTRIBUTE_FILE_DIRS,
#              CONTRIBUTE_CHANGE_TYPE, CONTRIBUTE_AUTO_LABELS
parse_contribute_metadata() {
    local body="$1"
    CONTRIBUTE_CONTRIBUTOR=""
    CONTRIBUTE_EMAIL=""
    CONTRIBUTE_FINGERPRINT_VERSION=""
    CONTRIBUTE_AREAS=""
    CONTRIBUTE_FILE_PATHS=""
    CONTRIBUTE_FILE_DIRS=""
    CONTRIBUTE_CHANGE_TYPE=""
    CONTRIBUTE_AUTO_LABELS=""

    local in_block=false
    while IFS= read -r line; do
        if [[ "$line" == *"<!-- aitask-contribute-metadata"* ]]; then
            in_block=true
            continue
        fi
        if [[ "$in_block" == true ]]; then
            if [[ "$line" == *"-->"* ]]; then
                break
            fi
            case "$line" in
                *contributor_email:*)
                    CONTRIBUTE_EMAIL=$(echo "$line" | sed 's/.*contributor_email:[[:space:]]*//' | tr -d '[:space:]')
                    ;;
                *contributor:*)
                    CONTRIBUTE_CONTRIBUTOR=$(echo "$line" | sed 's/.*contributor:[[:space:]]*//' | tr -d '[:space:]')
                    ;;
                *fingerprint_version:*)
                    CONTRIBUTE_FINGERPRINT_VERSION=$(echo "$line" | sed 's/.*fingerprint_version:[[:space:]]*//' | tr -d '[:space:]')
                    ;;
                *file_paths:*)
                    CONTRIBUTE_FILE_PATHS=$(echo "$line" | sed 's/.*file_paths:[[:space:]]*//' | sed 's/[[:space:]]*$//')
                    ;;
                *file_dirs:*)
                    CONTRIBUTE_FILE_DIRS=$(echo "$line" | sed 's/.*file_dirs:[[:space:]]*//' | sed 's/[[:space:]]*$//')
                    ;;
                *change_type:*)
                    CONTRIBUTE_CHANGE_TYPE=$(echo "$line" | sed 's/.*change_type:[[:space:]]*//' | tr -d '[:space:]')
                    ;;
                *auto_labels:*)
                    CONTRIBUTE_AUTO_LABELS=$(echo "$line" | sed 's/.*auto_labels:[[:space:]]*//' | sed 's/[[:space:]]*$//')
                    ;;
                *areas:*)
                    CONTRIBUTE_AREAS=$(echo "$line" | sed 's/.*areas:[[:space:]]*//' | sed 's/[[:space:]]*$//')
                    ;;
            esac
        fi
    done <<< "$body"
}
