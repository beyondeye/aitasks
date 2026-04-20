---
priority: medium
effort: low
depends: []
issue_type: chore
status: Implementing
labels: [git-integration, bash_scripts, ait_dispatcher]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-20 08:56
updated_at: 2026-04-20 09:16
---

## Context

During implementation of t597_3, the `.aitask-data` worktree was discovered stuck mid-rebase, left over from an earlier session's `./ait git push` where the internal `git pull --rebase --quiet` never finished. While in that wedged state:

- `./ait git commit` kept succeeding but landed commits on the detached rebase HEAD, orphaning them from the `aitask-data` branch pointer.
- `./ait git push` kept failing opaquely.
- `aitask_verified_update.sh` failed with `Remote branch HEAD not found in upstream origin` because `./ait git rev-parse --abbrev-ref HEAD` returns the literal string `HEAD` on a detached HEAD, and the script fed that to `git clone --branch <name>`.

The damage silently persists across sessions — the rebase state sits in `.git/worktrees/-aitask-data/rebase-merge/` until someone manually aborts it. This task adds two layers of detection so the situation is caught at the first wrapper call instead of spreading corruption.

## Key Files to Modify

- `ait` (dispatcher) or `.aitask-scripts/ait_git.sh` (wherever `./ait git` is routed) — add a pre-flight check that fails fast on in-progress rebase/merge/cherry-pick states in the data worktree.
- `.aitask-scripts/aitask_verified_update.sh` — reject a literal `HEAD` return from `current_task_branch()` with a specific error message.

## Implementation Plan

### 1. Pre-flight in `./ait git` dispatcher

Before delegating the user's git command, resolve the data worktree's git-dir (via `git rev-parse --git-dir` inside the worktree, or by path `$REPO_ROOT/.git/worktrees/-aitask-data`) and check for in-progress operation markers:

```bash
check_data_worktree_clean_state() {
  local gitdir="$1"
  local state
  for state in rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD BISECT_LOG; do
    if [ -e "$gitdir/$state" ]; then
      die "Data worktree is stuck mid-$state. Recover with './ait git <rebase|merge|cherry-pick|revert|bisect> --abort' (or '--continue' if resuming intentionally), then retry."
    fi
  done
}
```

Call this at the top of every `./ait git` invocation (or just for the mutating subcommands: commit, push, pull, rebase, merge, cherry-pick). The `die` helper already exists in `lib/terminal_compat.sh`.

**Required: override paths.** The guard MUST have both of these escape paths, because without them the user gets locked out of their own recovery:

1. **Auto-bypass for recovery subcommands.** When the user runs `./ait git rebase --abort|--continue|--skip|--edit-todo`, `./ait git merge --abort|--continue`, `./ait git cherry-pick --abort|--continue|--skip`, `./ait git revert --abort|--continue|--skip`, or `./ait git bisect reset` — the guard must skip entirely. These are the commands that release the broken state, and refusing to run them would be self-defeating. Detect by inspecting the positional args.

2. **Auto-bypass for read-only subcommands.** `status`, `log`, `show`, `diff`, `rev-parse`, `branch` (without `-d`/`-D`/`-m`), `ls-files`, `blame`, `grep`, `tag -l`, `stash list`, `reflog`. Users should be able to inspect a wedged worktree without the guard getting in the way.

3. **Env-var escape hatch as final fallback.** Honor `AIT_GIT_SKIP_STATE_CHECK=1` to skip the check entirely. Used for (a) scripts that need to run in odd states (diagnostics), and (b) coverage gaps not matched by paths 1–2.

Document all three in the error message itself so the user can recover without reading source:
```
Data worktree is stuck mid-rebase. Recover with:
  ./ait git rebase --abort      (discard the in-progress rebase)
  ./ait git rebase --continue   (resume if you were editing)
Or set AIT_GIT_SKIP_STATE_CHECK=1 to bypass this check.
```

### 2. Defense-in-depth in `aitask_verified_update.sh`

In `has_remote_tracking()` (or the caller), after resolving the branch name, reject the literal string `HEAD`:

```bash
current_task_branch() {
  local branch
  branch="$(./ait git rev-parse --abbrev-ref HEAD)"
  if [ "$branch" = "HEAD" ]; then
    die "Data worktree is on a detached HEAD (possibly mid-rebase). Resolve the branch state before retrying."
  fi
  printf '%s\n' "$branch"
}
```

This catches any future detached-HEAD cause that slips past the pre-flight (e.g. manual checkout of a commit).

### 3. Grep for other callers of `rev-parse --abbrev-ref HEAD`

Audit other scripts that resolve the data-branch name the same way and add the `HEAD` check inline or factor it into `task_utils.sh`:

```bash
grep -rn "rev-parse --abbrev-ref HEAD" .aitask-scripts/
```

Any hit whose result is used as a branch name in a `git push`/`clone`/`fetch` argument should be guarded.

### 4. Optional: data-worktree health sub-command

Add `./ait git-health` (or similar) that prints the detected state: "clean" / "mid-rebase" / "detached" / etc. Makes diagnosis trivial next time something weird happens.

## Verification Steps

```bash
# Manually induce the stuck state to validate the pre-flight catches it:
git -C .aitask-data rebase -i HEAD~2   # stop, type 'edit' for one commit, close editor
./ait git status                        # should fail fast with recovery hint
./.aitask-scripts/aitask_verified_update.sh --agent-string foo/bar --skill pick --score 5   # should fail fast with clear message
git -C .aitask-data rebase --abort      # recover
./ait git status                        # works again

shellcheck .aitask-scripts/ait_git.sh .aitask-scripts/aitask_verified_update.sh
bash tests/test_ait_git.sh   # if a test file exists or is added
```

## Out of Scope

- Auto-recovery (automatically running `--abort`) — too destructive without user confirmation.
- Changing the `pull --rebase --quiet` to non-quiet — separate concern; the pre-flight makes it less urgent since stuck states are now caught.
