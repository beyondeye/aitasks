---
Task: t599_detect_stuck_data_worktree_rebase.md
Base branch: main
plan_verified: []
---

# Plan: t599 — Detect stuck `.aitask-data` worktree state

## Context

During t597_3 the `.aitask-data` worktree was found stuck mid-rebase, left over from a prior `./ait git push` whose internal `git pull --rebase --quiet` never finished. While wedged:

- `./ait git commit` kept landing commits on the detached rebase HEAD (orphaned from the branch pointer).
- `./ait git push` failed opaquely.
- `aitask_verified_update.sh` died with `Remote branch HEAD not found in upstream origin` because `./ait git rev-parse --abbrev-ref HEAD` returns the literal string `HEAD` on a detached HEAD, and the script fed that to `git clone --branch <name>`.

The rebase state persists across sessions in `.git/worktrees/-aitask-data/rebase-merge/` until manually aborted. This plan adds a fail-fast pre-flight in the `./ait git` wrapper, hardens `aitask_verified_update.sh` against the literal `HEAD` value, and adds a small diagnostic subcommand.

## Files to Modify

- `/home/ddt/Work/aitasks/.aitask-scripts/lib/task_utils.sh` — add `assert_data_worktree_clean()` and `task_git_health()`; call the assert from `task_git()` and `task_push()`.
- `/home/ddt/Work/aitasks/.aitask-scripts/aitask_verified_update.sh` — make `current_task_branch()` reject the literal `HEAD`.
- `/home/ddt/Work/aitasks/ait` — register a new top-level `git-health` subcommand.

## Implementation

### 1. Pre-flight guard in `lib/task_utils.sh`

Add immediately after `_ait_detect_data_worktree()` (after current line 38):

```bash
# Resolve the data worktree's git-dir. Empty when in legacy mode.
_ait_data_gitdir() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" == "." ]]; then
        printf ''
        return
    fi
    # In branch mode the gitdir lives at .git/worktrees/-aitask-data/
    local gd=".git/worktrees/-aitask-data"
    [[ -d "$gd" ]] && printf '%s' "$gd"
}

# Read-only git subcommands — the guard treats them as safe.
_ait_git_subcmd_is_readonly() {
    case "${1:-}" in
        status|log|show|diff|rev-parse|ls-files|blame|grep|reflog) return 0 ;;
        branch)
            # branch is read-only without -d/-D/-m/-M and without a positional name+start
            for a in "${@:2}"; do
                case "$a" in -d|-D|-m|-M|--delete|--move) return 1 ;; esac
            done
            return 0 ;;
        tag)
            # `tag -l` is read-only; bare `tag <name>` mutates
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
```

Wire it into the existing entry points:

- `task_git()` (current lines 43-50): add `assert_data_worktree_clean "$@"` as the first line of the function body, after `_ait_detect_data_worktree`.
- `task_push()` (current lines 66-80): add `assert_data_worktree_clean push` at the top (before the retry loop). `task_push()` is invoked with no args from the dispatcher, so we synthesize `push` for the read-only/recovery classifier.

### 2. Reject literal `HEAD` in `aitask_verified_update.sh`

Replace the body of `current_task_branch()` (current lines 275-277):

```bash
current_task_branch() {
    local branch
    branch="$(./ait git rev-parse --abbrev-ref HEAD)"
    if [[ "$branch" == "HEAD" ]]; then
        die "Data worktree is on a detached HEAD (possibly mid-rebase). Run './ait git-health' for diagnosis, then './ait git rebase --abort' or '--continue' to recover."
    fi
    printf '%s\n' "$branch"
}
```

`has_remote_tracking()` (lines 270-273) discards the value via `>/dev/null 2>&1 || return 1`, so it does not need the same guard — it only reports presence/absence. The pre-flight in §1 catches the upstream cause anyway.

### 3. Audit verdict for other `rev-parse --abbrev-ref HEAD` callers

Two callers found beyond `aitask_verified_update.sh`:

- `aitask_lock_diag.sh:175` — diagnostic-only, already pipes through `2>/dev/null || echo "unknown"`. Leave as-is (it intentionally tolerates wedged states because it is the diagnostic).
- `aitask_plan_externalize.sh` — uses the safer `git symbolic-ref --short HEAD 2>/dev/null || echo ""` pattern, which returns empty on detached HEAD. Leave as-is.

No new helper or refactor needed — only the one call site in §2 is fed into `git clone --branch` and therefore vulnerable.

### 4. `./ait git-health` diagnostic subcommand

Add to `lib/task_utils.sh` (next to `task_git()`):

```bash
# Print human-readable health of the .aitask-data worktree.
# Exits 0 always — informational only.
task_git_health() {
    _ait_detect_data_worktree
    if [[ "$_AIT_DATA_WORKTREE" == "." ]]; then
        info "Mode: legacy (no separate .aitask-data worktree) — nothing to check."
        return 0
    fi

    local gitdir branch head_ref state hits=()
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
```

Add a new dispatcher case in `/home/ddt/Work/aitasks/ait`. Insert immediately after the existing `git)` case (after current line 251):

```bash
    git-health)   shift; source "$SCRIPTS_DIR/lib/task_utils.sh"
                  task_git_health "$@"
                  ;;
```

Add a one-line entry to `show_usage()` under "Task Management" (around current line 37), e.g.:

```
  git-health     Diagnose the .aitask-data worktree state
```

## Verification

```bash
# Lint
shellcheck .aitask-scripts/lib/task_utils.sh .aitask-scripts/aitask_verified_update.sh

# Health on a clean worktree
./ait git-health         # expect "Clean — no in-progress..."

# Induce stuck rebase, confirm fail-fast
git -C .aitask-data rebase -i HEAD~2
#   in the editor: change one 'pick' to 'edit', save & quit
./ait git status         # PASSES (read-only auto-bypass)
./ait git commit -m x    # FAILS with recovery hint
./ait git push           # FAILS with recovery hint
./ait git-health         # shows "In-progress operations: rebase-merge"

# Recovery path is allowed through
./ait git rebase --abort
./ait git-health         # shows "Clean"
./ait git status         # works again

# Defense-in-depth: simulate detached HEAD by hand
git -C .aitask-data checkout --detach HEAD
./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_7 --skill pick --score 5
#   expect: "Data worktree is on a detached HEAD..." (NOT the old "Remote branch HEAD not found...")
git -C .aitask-data checkout aitask-data   # or whatever the data branch is named

# Escape hatch
AIT_GIT_SKIP_STATE_CHECK=1 ./ait git status   # always allowed
```

Run the existing test suite to confirm no regressions:

```bash
bash tests/test_task_git.sh
bash tests/test_task_push.sh
bash tests/test_verified_update.sh
bash tests/test_data_branch_setup.sh
bash tests/test_data_branch_migration.sh
```

## Out of Scope

- Auto-recovery (running `--abort` for the user) — too destructive without explicit consent.
- Changing `pull --rebase --quiet` to non-quiet — separate concern; the pre-flight reduces urgency.
- New tests — existing suite covers happy path; the stuck-state scenarios are awkward to exercise hermetically and are validated manually per the verification block above.

## Step 9 — Post-Implementation

After review approval: commit code with `bug: Detect stuck .aitask-data worktree state (t599)`, then `./ait git add aiplans/p599_detect_stuck_data_worktree_rebase.md` + `./ait git commit -m "ait: Update plan for t599"`. Run `./.aitask-scripts/aitask_archive.sh 599`. Push with `./ait git push`.
