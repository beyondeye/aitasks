---
title: "Sync"
linkTitle: "Sync"
weight: 35
description: "ait sync command for bidirectional task data synchronization"
depth: [intermediate]
---

## ait sync

Sync task data with a remote repository: auto-commit local changes, fetch, pull with rebase, and push. Designed for multi-machine workflows where task files may be edited on different PCs.

```bash
ait sync                    # Interactive mode with colored progress
ait sync --batch            # Structured output for scripting/automation
```

| Option | Description |
|--------|-------------|
| `--batch` | Structured single-line output for scripting (no colors, no interactive prompts) |
| `--help, -h` | Show usage help |

### Interactive Mode

In interactive mode, `ait sync` displays colored progress messages as it works through each step:

1. Checks for uncommitted task file changes and auto-commits them
2. Fetches from the remote with a 10-second timeout
3. Pulls new commits using rebase (to keep history linear)
4. Pushes local commits to the remote

If merge conflicts occur during rebase, the script opens each conflicted file in `$EDITOR` (default: `nano`) for manual resolution. After editing, the file is staged and the rebase continues. You can abort the rebase at any point by exiting the editor without saving.

### Batch Output Protocol

In batch mode (`--batch`), the script outputs a single structured line on stdout:

| Output | Meaning |
|--------|---------|
| `SYNCED` | Both push and pull completed successfully |
| `PUSHED` | Local changes pushed, nothing to pull |
| `PULLED` | Remote changes pulled, nothing to push |
| `NOTHING` | Already up-to-date, no action needed |
| `AUTOMERGED` | Merge conflicts detected and auto-resolved by merge rules |
| `CONFLICT:<file1>,<file2>` | Unresolvable merge conflicts detected (rebase aborted) |
| `NO_NETWORK` | Fetch or push timed out or failed (no connectivity) |
| `NO_REMOTE` | No git remote configured for the repository |
| `DEFERRED:<reason>[:<detail>]` | Sync deliberately did less than a full cycle — **not** an error (see [Auto-commit policy](#auto-commit-policy)) |
| `ERROR:<message>` | Unexpected error with details |

A `DEFERRED:` line splits on its **first** colon only; `<detail>` is free text and may contain colons. The reasons are a closed set:

| Reason | Meaning |
|--------|---------|
| `publication_blocked` | A commit whose content could not be vouched for is being withheld from the remote |
| `protected_dirty` | Files another session owns are still dirty, which blocks the rebase |
| `worktree_wedged` | The data worktree is stuck mid-rebase or mid-merge |

Per-file skip reasons — an unreadable lock branch, a contended data-index lock, an ownerless file — are reported on stderr rather than in this token; when they block the rebase they surface here as `protected_dirty`.

This protocol is used by the [board TUI](../../tuis/board/) for background sync integration.

### Auto-commit policy

Several sessions can share one working copy of the task data, so the pre-sync sweep never commits a file it cannot attribute. It groups the dirty task and plan files by their **owning task** and commits each group path-scoped, under a message naming that task — so a commit never carries an unrelated task's file.

Anything it cannot vouch for is **skipped and reported on stderr**, and simply stays dirty, which is safe:

- the task is locked by a session that is still running, or by one whose liveness cannot be established (including any lock held by another machine);
- the file has no derivable task id — for example `aitasks/metadata/*`;
- the entry is a rename whose two paths belong to different tasks;
- another session has already staged the file;
- the file changed after it was classified;
- the lock branch could not be read at all, in which case nothing is committed.

Skipped files can block the later rebase, since `git pull --rebase` refuses to run with a dirty worktree. When that happens the run reports `DEFERRED:protected_dirty` and exits **successfully** — the deferral clears by itself once the owning session commits its work.

An ownerless file is different: nothing else will ever commit it, so it stays dirty until you do. The report names the file and the exact command that clears it.

Three flags trade safety for availability, and each is deliberately never automatic:

| Flag | Effect |
|------|--------|
| `--commit-unowned` | Also commit files with no derivable task id, under a message that names no task |
| `--assume-unlocked` | Treat an unreadable lock branch as "nothing is locked". An outage can coincide with a live editor, so this is a decision you make, not one a network failure makes for you |
| `--release-quarantine` | Publish commits withheld by `publication_blocked` (see below) |

#### Withheld commits

If a file is rewritten in the instant between being checked and being committed, the resulting commit holds content that was never classified. That commit is kept **local** — the run reports `DEFERRED:publication_blocked` and pushes nothing — and the state persists across runs, so a later sync cannot publish it either.

It clears on its own once a later commit supersedes the content, or once the owning task's session has ended and the file has settled. Age alone never releases it: expiring the hold would publish exactly the content it exists to withhold. Past 24 hours (`AIT_SYNC_QUARANTINE_WARN_AGE`) the report escalates and names `--release-quarantine`, which is the only way to publish deliberately.

While a commit is withheld, the run publishes nothing at all — not just that commit.

### How It Works

The sync flow follows these steps:

1. **Mode detection** — Determines whether task data lives on a separate `aitask-data` branch (via `.aitask-data/` worktree) or on the current branch (legacy mode)
2. **Remote check** — Verifies a git remote exists; outputs `NO_REMOTE` if not
3. **Auto-commit** — If there are uncommitted changes to `aitasks/` or `aiplans/`, commits them **grouped by owning task** (see [Auto-commit policy](#auto-commit-policy))
4. **Fetch** — Fetches from the remote with a 10-second network timeout; outputs `NO_NETWORK` on failure
5. **Pull with rebase** — If the remote has new commits, pulls them using `git pull --rebase` to maintain linear history. If conflicts occur in task files, the auto-merge system attempts to resolve them automatically (see below)
6. **Push** — If there are local commits to push, pushes them to the remote (retries once on rejection, in case the remote advanced during rebase)
7. **Output result** — Reports the final status

### Auto-Merge Conflict Resolution

When `git pull --rebase` encounters conflicts in task files, `ait sync` automatically invokes a Python merge script (`aitask_merge.py`) to resolve frontmatter conflicts using deterministic rules. This avoids manual resolution for the most common multi-machine editing scenarios (e.g., one PC moves a task on the board while another changes labels).

#### Merge Rules

| Field | Rule | Details |
|-------|------|---------|
| `boardcol`, `boardidx` | Keep LOCAL | Your local board position is always preserved |
| `updated_at` | Keep newer | Compares timestamps, keeps the more recent value |
| `labels` | Union | Merges both lists, deduplicates, and sorts alphabetically |
| `depends` | Union | Merges both lists, deduplicates, and sorts |
| `priority`, `effort` | Keep REMOTE (batch) | In batch/automated mode, the remote value wins. In interactive mode, prompts the user |
| `status` | Implementing wins | If either side has `Implementing`, result is `Implementing`. If both differ and neither is `Implementing`, the conflict is unresolved |
| Other fields | Same = keep; different = unresolved | Fields with identical values on both sides are kept. Different values cannot be auto-resolved |

#### What Happens When Auto-Merge Can't Fully Resolve

If some fields (or the task body) cannot be auto-resolved, the merge script resolves what it can and leaves conflict markers for the rest. In interactive mode, the remaining conflicted file opens in `$EDITOR` for manual resolution. In batch mode, the status is reported as `CONFLICT:<files>`.

#### Exit Codes (for scripting)

The merge script (`aitask_merge.py`) uses these exit codes:

| Code | Stdout | Meaning |
|------|--------|---------|
| 0 | `RESOLVED` | All conflicts auto-resolved |
| 1 | `SKIPPED` | Not a task file or no conflict markers found |
| 2 | `PARTIAL:<fields>` | Some fields auto-resolved, others need manual attention |

### Network Handling

All network operations use a 10-second timeout to prevent the script from hanging when there is no connectivity. On systems with the `timeout` command (standard on Linux), it is used directly. On systems without it (e.g., macOS without coreutils), a portable bash-based watchdog fallback is used.

If any network operation times out, the script outputs `NO_NETWORK` and exits cleanly — no partial state is left behind.

### Data Branch Mode

When the repository uses a separate `aitask-data` branch for task files (set up via `ait setup`), all git operations target the data branch worktree automatically. In legacy mode (tasks on the main branch), sync operates on the current branch. The behavior is transparent — the same `ait sync` command works in both modes.

### See also

- [Syncer TUI]({{< relref "/docs/tuis/syncer" >}}) — interactive surface for remote desync state across `main` and `aitask-data` with one-keystroke pull/push/sync actions and an agent escape hatch on failure. The syncer's `s` action invokes `ait sync --batch` under the hood. Git state is only its first tab: the same TUI also tracks each discovered repo's installed framework version (with an upgrade action) and compares shared settings across repos.

## ait git push

`ait git` runs git commands against task data, routing them to the data branch
worktree in [data-branch mode](#data-branch-mode) and to the current branch in
legacy mode. `push` is special-cased: it is **best-effort**, so a network
outage or a diverged remote never aborts a task workflow mid-flight.

```bash
ait git push                  # best-effort push; warns if commits are stranded
ait git push --batch          # same, plus one structured status line on stdout
```

Best-effort does not mean silent. The push is attempted up to three times, with
a `pull --rebase` between attempts to absorb a remote that has moved. If every
attempt fails, the command **still exits 0** but prints a warning naming how
many commits are stranded and why:

```
Warning: 3 commit(s) not pushed to origin/aitask-data — data worktree has
unstaged changes blocking rebase; reconcile with 'ait syncer'
```

Recognised failure reasons, each with its own recovery hint: a dirty data
worktree blocking the rebase fallback, a rebase stopped on conflicts, an
unreachable remote, and a remote that has diverged. An unrecognised failure
still warns and quotes git's own first line.

Two cases stay deliberately quiet, because nothing is at risk: the repository
has no git remote configured, or the push failed while there were no local
commits to send.

### Batch Output Protocol

With `--batch`, one structured line is printed on stdout (exit status is still 0
in all cases):

| Output | Meaning |
|--------|---------|
| `PUSHED` | Local commits reached the remote |
| `NOTHING` | Already up to date, nothing to push |
| `NO_REMOTE` | No git remote configured |
| `FAILED:<reason>:<count>` | Push failed; `<reason>` is one of `dirty_worktree`, `rebase_conflict`, `no_upstream`, `remote_unreachable`, `diverged`, `unknown`, and `<count>` is the unpushed commit count (`unknown` when it cannot be determined) |

The commit count is read *after* the push attempts finish, so it reports how
many commits are unpushed **now** — on a shared checkout another session can
move refs in between, so treat it as a current reading rather than a snapshot of
the moment the push failed.

### Task-data pull before task selection

Picking a task pulls the task data first, so the local task list reflects what
other machines have already claimed. That pull is best-effort in the same way,
and reports itself with the same failure reasons and recovery hints as the push
above — a warning on stderr naming what is left unreconciled, while the pick
continues:

```
Warning: task data not reconciled with origin/aitask-data: 2 local unpushed,
0 remote unpulled (remote side as of the last successful fetch — this sync may
not have refreshed it) — data worktree has unstaged changes blocking rebase;
reconcile with 'ait syncer'
```

The remote count is read from the local copy of the remote branch. A pull that
failed before it could fetch never refreshed that copy, so the number describes
the remote as of the last successful fetch, not as of now — the message says so
rather than implying otherwise. The local count carries no such caveat.

Two cases stay quiet here as well: no remote configured, or a failed pull with
nothing unreconciled in either direction. A blocked local worktree (a dirty data
worktree or a stopped rebase) always warns, because it keeps every later sync
and push failing until it is cleared.

The one case where `ait git push` does **not** exit 0 is a data worktree left
stuck mid-rebase, merge, cherry-pick, revert, or bisect. That is a broken
worktree rather than a push outcome, so the command stops with the recovery
hints described under [`ait git-health`](#ait-git-health) (bypass with
`AIT_GIT_SKIP_STATE_CHECK=1`).

## ait git-health

Diagnose the state of the `.aitask-data` worktree that backs task and plan
storage in [data-branch mode](#data-branch-mode).

```bash
ait git-health
```

In **legacy mode** (no separate `aitask-data` branch) it reports that there is
nothing to check. In **branch mode** it prints the worktree path, git-dir,
current branch, and HEAD commit, then flags anything that would leave `ait git`
operations stuck:

- A detached HEAD on the worktree.
- An in-progress `rebase`, `merge`, `cherry-pick`, `revert`, or `bisect`, with a
  recovery hint (`./ait git <op> --abort` or `--continue`).

A clean worktree reports no in-progress operations. Reach for `git-health` when
a fresh clone or a moved checkout looks like it is missing tasks — see the
[installation troubleshooting notes]({{< relref "/docs/installation#what-gets-installed" >}})
and the [Repository Maintenance]({{< relref "/docs/workflows/repo-maintenance" >}})
workflow.

---

**Next:** [Lock]({{< relref "/docs/commands/lock" >}})
