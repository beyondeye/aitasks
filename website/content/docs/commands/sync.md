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
| `MERGED` | Local and remote had both moved on while another session's uncommitted files blocked the rebase, so the branch was joined with a merge commit and pushed; those files are left untouched and uncommitted (see [Auto-commit policy](#auto-commit-policy)) |
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

Skipped files can block the later rebase, since `git pull --rebase` refuses to run while a tracked file is modified. Sync then tries two other ways to catch up, neither of which touches a skipped file:

- If the local branch has no commits of its own, it fast-forwards (see [Stashing and ignored files](#stashing-and-ignored-files)).
- If local and remote both have new commits, it joins them with a merge commit and pushes, and the run reports `MERGED`. This happens only when the two sides changed different files, git merges them cleanly, and the merge writes none of the skipped files and no ignored file. The skipped files stay exactly as they were, uncommitted.

Otherwise the run reports `DEFERRED:protected_dirty` and exits **successfully**. The deferral clears by itself once the owning session commits its work. Re-running `ait sync` is therefore a recovery attempt, not a guarantee: when both sides changed the same file, it keeps deferring until that session commits or you resolve the overlap yourself.

An ownerless file is different: no session is going to commit it *for* you, so it stays dirty until it is committed. The report names the file and the exact command that clears it.

Most config files do have an owner now. Every surface that writes a tracked file under `aitasks/metadata/` on an explicit save commits it itself — the [settings TUI]({{< relref "/docs/tuis/settings" >}}), board column edits, the chatlink wizard, and `ait setup`'s populate-missing passes — so those never reach the sweep as ownerless. What still can: a file you edited by hand, a config whose own commit failed, and `aitasks/metadata/gates.yaml`, which `ait gates sync-registry` deliberately leaves for you to review before committing. For any of them:

```bash
./.aitask-scripts/aitask_metadata_commit.sh aitasks/metadata/<file>
```

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

### Stashing and ignored files

Sync never stashes. It passes `--no-autostash` to every fast-forward and rebase, so a `rebase.autoStash` or `merge.autoStash` setting in your git config does not apply, and a file sync left uncommitted is never stashed and re-applied.

It also protects **ignored files**: files your ignore rules keep out of git, such as `aitasks/metadata/userconfig.yaml`.

- **No local commits.** Sync fast-forwards to exactly the commit the fetch brought in. Git refuses to write over an ignored file at that point, so sync stops and changes nothing.
- **Local commits to replay.** Sync rebases them with `git pull --rebase`, and a rebase has no such protection: it overwrites an ignored file that an incoming commit writes.

An incoming commit can write a path that your checkout ignores:

- the path was tracked before an ignore rule was added, and later commits update it with an ordinary `git add`;
- another checkout has different ignore rules (its own `.git/info/exclude` or global excludes file);
- someone force-added it with `git add -f`.

When sync refuses to fast-forward, it reports one of these:

| Output | Meaning | What to do |
|--------|---------|------------|
| `ERROR:pull_overwrites_ignored` | An incoming commit writes over an ignored file you have locally; stderr names both paths | Move your file aside, run `ait sync`, then keep the version you want (see below) |
| `ERROR:pull_ff_refused` | Git refused the fast-forward; stderr carries git's reason, such as a file in the way or a commit made in the meantime | If git names a file in the way, handle it like the row above; otherwise run `ait sync` again |
| `ERROR:pull_preflight_unverified` | Sync could not read what the fast-forward would write | Run `ait sync` again |

The TUIs show only the token. Run `ait sync` in a terminal to see the paths.

If the incoming commit shares a file that should stay local, such as a teammate's `userconfig.yaml`, stop tracking it on the branch and then restore your copy:

```bash
mv aitasks/metadata/userconfig.yaml aitasks/metadata/userconfig.yaml.mine
ait sync
./ait git rm aitasks/metadata/userconfig.yaml
./ait git commit -m "ait: Stop tracking userconfig.yaml" -- aitasks/metadata/userconfig.yaml
ait sync
mv aitasks/metadata/userconfig.yaml.mine aitasks/metadata/userconfig.yaml
```

### How It Works

The sync flow follows these steps:

1. **Mode detection** — Determines whether task data lives on a separate `aitask-data` branch (via `.aitask-data/` worktree) or on the current branch (legacy mode)
2. **Remote check** — Verifies a git remote exists; outputs `NO_REMOTE` if not
3. **Auto-commit** — If there are uncommitted changes to `aitasks/` or `aiplans/`, commits them **grouped by owning task** (see [Auto-commit policy](#auto-commit-policy))
4. **Fetch** — Fetches from the remote with a 10-second network timeout; outputs `NO_NETWORK` on failure
5. **Pull** — If the remote has new commits and the local branch has none of its own, fast-forwards to exactly the commit the fetch brought in. It does not fetch again and does not fall back to a rebase. Otherwise it pulls with `git pull --rebase` to maintain linear history. If conflicts occur in task files, the auto-merge system attempts to resolve them automatically (see below). Neither path stashes, and the fast-forward never overwrites an ignored file (see [Stashing and ignored files](#stashing-and-ignored-files))
6. **Push** — If there are local commits to push, pushes them to the remote (retries once on rejection, in case the remote advanced during rebase)
7. **Output result** — Reports the final status

### Auto-Merge Conflict Resolution

When `git pull --rebase` encounters conflicts in task files, `ait sync` automatically invokes a Python merge script (`aitask_merge.py`) to resolve frontmatter conflicts using deterministic rules. This avoids manual resolution for the most common multi-machine editing scenarios (e.g., one PC moves a task on the board while another changes labels).

The same resolver runs on the task-data pull that happens when you pick a task and on the pull `ait git push` retries with, so a frontmatter-only collision is cleared automatically wherever it appears rather than only under `ait sync` — see [Task-data pull before task selection](#task-data-pull-before-task-selection).

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

The fetch and the push each have a 10-second limit, so the script never hangs when there is no connectivity. When the limit expires, the whole git process tree is killed, including a transport such as `ssh` that ignores the polite stop signal, so nothing keeps running in the background. The behaviour is the same on Linux and macOS.

If any network operation times out, the script outputs `NO_NETWORK` and exits cleanly — no partial state is left behind.

#### Authentication prompts

By default, the fetch and the push cannot ask for credentials. No terminal prompt, no `SSH_ASKPASS` dialog, and no Git Credential Manager window appears, so a background sync from the [syncer]({{< relref "/docs/tuis/syncer" >}}) never pops up a dialog. Credentials must come from `ssh-agent` or a git credential helper that answers without asking. When they are missing, the sync reports `NO_NETWORK`.

If your setup authenticates through a graphical prompt, for example an `SSH_ASKPASS` program for a passphrase-protected key or Git Credential Manager's sign-in window, allow it for a run:

```bash
AIT_SYNC_ALLOW_PROMPT=1 ait sync
```

Only the exact value `1` enables prompts. This setting changes nothing else: the 10-second limit and the process-tree kill still apply, so the prompt has to be answered within that time. Terminal (typed) prompts stay impossible even then, because git runs without a controlling terminal.

### Data Branch Mode

When the repository uses a separate `aitask-data` branch for task files (set up via `ait setup`), all git operations target the data branch worktree automatically. In legacy mode (tasks on the main branch), sync operates on the current branch. The behavior is transparent — the same `ait sync` command works in both modes.

### See also

- [Syncer TUI]({{< relref "/docs/tuis/syncer" >}}) — interactive surface for remote desync state across `main` and `aitask-data` with one-keystroke pull/push/sync actions and an agent escape hatch on failure or conflict. The syncer's `s` action invokes `ait sync --batch` under the hood. Git state is only its first tab: the same TUI also tracks each discovered repo's installed framework version (with an upgrade action) and compares shared settings across repos.

## ait git push

`ait git` runs git commands against task data, routing them to the data branch
worktree in [data-branch mode](#data-branch-mode) and to the current branch in
legacy mode. `push` is special-cased: it is **best-effort**, so a network
outage or a diverged remote never aborts a task workflow mid-flight. `pull` is
special-cased too — see [`ait git pull`](#ait-git-pull).

Global git options in front of the subcommand are understood: `ait git -c
core.pager=cat rebase --abort` is recognised as the recovery command it is. The
options that would point git at a different repository — `-C`, `--git-dir`,
`--work-tree` and `--namespace` — are refused, since they defeat the routing;
use plain `git` for those. `-c name=value` and `--config-env` are kept.

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

That pull resolves conflicts, not just reports them. When it stops on a
frontmatter-only collision — the common two-machine case, such as one PC moving
a task on the board while another edits its labels — it runs the same
[auto-merge rules](#auto-merge-conflict-resolution) `ait sync` uses, completes
the rebase, and continues, naming what it merged on stderr:

```
auto-merged task-data conflict(s) during pull (1 file(s)) - rebase completed
```

Anything it cannot merge — a conflict in the task body, or a file that is not a
task or plan — is left to a human exactly as before: the rebase is aborted so
nothing is left in progress, and the pull reports `rebase_conflict` with its
recovery hint.

The one case where `ait git push` does **not** exit 0 is a data worktree left
stuck mid-rebase, merge, cherry-pick, revert, or bisect. That is a broken
worktree rather than a push outcome, so the command stops with the recovery
hints described under [`ait git-health`](#ait-git-health) (bypass with
`AIT_GIT_SKIP_STATE_CHECK=1`).

## ait git pull

```bash
ait git pull --rebase
ait git -c core.pager=cat pull --rebase    # global options are fine
```

`ait git pull` runs your pull with the same clean-up guarantee as the
[pull that runs when you pick a task](#task-data-pull-before-task-selection): it
never leaves the data worktree stuck mid-rebase. A frontmatter-only conflict is
auto-merged and the rebase completes. Anything it cannot merge is aborted, so
nothing is left in progress and later `ait git` commands keep working. A rebase
that some other session started is never touched. It fails with git's own exit
status and, for a recognised failure, prints one warning naming the reason
(`rebase_conflict`, `dirty_worktree`, `pull_locked`, `data_midop`, …) with its
recovery hint. git's output, including the conflict details, goes to stderr.

- **No automatic stashing.** The data worktree is shared by every session on
  the machine, so the pull never stashes: a dirty data worktree makes it refuse
  with `dirty_worktree`, whatever `rebase.autoStash` / `merge.autoStash` say.
  An explicit `--autostash` is refused. Commit or set aside the local changes
  first, or use plain `git -C .aitask-data pull --autostash` if you really mean
  it.
- **No interactive rebase.** `--rebase=interactive` (or `-ri`) is refused
  before anything is fetched, and so is an interactive mode chosen by config
  (`branch.<name>.rebase` or `pull.rebase`, including one passed with `-c`):
  the editor needs your terminal, and an `edit` stop would leave the shared data
  worktree paused mid-rebase. An explicit `--rebase` still overrides an
  interactive config, as in plain git. For an interactive pull use plain
  `git -C .aitask-data pull --rebase=interactive`.
- **No editor opens.** A merge-mode pull commits with git's default merge
  message, even where plain git would open your editor (an interactive terminal,
  or `GIT_MERGE_AUTOEDIT=yes`). An explicit `--edit` is refused before anything
  is fetched; use plain `git -C .aitask-data pull --edit` to write the message
  yourself.
- **Your `-c` settings apply throughout.** Options such as `-c user.email=…`
  reach the rebase's continue and abort steps as well as the pull. The one
  exception is the framework's own pins (`rerere.enabled=false`,
  `maintenance.auto=false`), which keep the rebase safe from background git
  work.
- **One pull at a time.** If another session is reconciling the task data right
  now, the pull is skipped with `pull_locked` and nothing changes. Retry in a
  moment.
- **A completed pull is still checked.** If git reports success but unmerged
  files remain, or the check itself cannot run, the pull fails with a message
  saying it completed but could not be verified. It names the next step and
  leaves the files as they are.
- **A stopped merge is left to you.** With `pull.rebase=false` (or
  `--no-rebase`), a merge that stops — on a conflict, or because a hook such as
  `pre-merge-commit` refused the merge commit — is left in progress, reported
  as `data_midop` with the merge recovery hint, and never aborted
  automatically. Finish it, or run `./ait git merge --abort`.
- **Resolving a rebase conflict by hand** is not possible through `ait git
  pull`, because a conflict it cannot merge is always aborted. Use plain
  `git -C .aitask-data pull --rebase` for that.

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
