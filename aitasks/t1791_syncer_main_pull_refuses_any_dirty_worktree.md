---
priority: medium
effort: low
depends: []
issue_type: bug
status: Folded
labels: [syncer, git]
gates: [risk_evaluated]
folded_into: 2126
anchor: 1599
followup_kind: upstream_defect
created_at: 2026-09-10 15:54
updated_at: 2026-10-22 12:48
---

## Problem

The syncer's code-branch pull refuses whenever the worktree is dirty at all, although the command it guards refuses only when it would actually overwrite something.

`_main_pull_worker` (`.aitask-scripts/syncer/syncer_app.py` ~2326-2334 at base e7bcb66c — re-derive, the file moves) checks `git status --porcelain`. Any output makes it refuse with "Working tree dirty — stash or commit before pulling", before it ever runs `git pull --ff-only`. A fast-forward-only pull refuses only when it would **overwrite** a dirty or untracked file, which is a strictly weaker precondition.

The user runs several code agents at once in the same checkout, so the working tree is dirty almost all the time. The syncer's main-branch pull therefore almost never runs.

## Origin

Raised as point 4 of an inbox note on t1731, sent from a t1725 explore session. The user had reported "syncer fails because of dirty worktree", and this refusal message matches that report. It is unconfirmed which message they actually saw. Filed as a follow-up of t1731, whose data-branch fix has the same shape: an over-strong precondition in front of a git command that already guards itself. This is a separate, code-branch surface.

## Goal

Let git decide. Drop the blanket dirty-worktree refusal and run `git pull --ff-only`. When it refuses, surface git's own message, which names the files that would be overwritten, not a generic line.

Keep refusing up front when the checkout is mid-rebase or mid-merge. Consider `--no-autostash`, and whether `--no-overwrite-ignore` is appropriate here: git's default silently overwrites ignored files.

## Acceptance criteria

- An unrelated dirty file, with the remote ahead on other files: the pull fast-forwards, and the dirty file is byte-identical afterwards.
- The remote changes the dirty file: the pull is refused, and the message names that file.
- A diverged branch, where no fast-forward is possible: refused, as today.
- The checkout is mid-rebase: refused before any pull runs.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1792** id=2026-10-14T15:34:56Z.51ee8eadce7fc3ad26c6b2b3 from=t1792 from_verified=yes at=2026-10-14T15:34:56Z base=7f1d0614a333c14f0130789c8a22e2233e6d9db0 base_branch=main dirty=no host=omg16
>
> | Advisory context from t1792. These are probe results on git 2.55.0 in scratch repos, valid as of commit 02e4a1bad. They bear on this task's "consider --no-autostash / --no-overwrite-ignore" question.
> | 
> | - **Autostash on a fast-forward.** `merge --ff-only` with `merge.autoStash=true` stashes and re-applies an unrelated dirty tracked file. The file's inode and ctime change even though its bytes come back. With `--no-autostash` the file is left untouched.
> | - **Ignored files on a fast-forward.** `merge --ff-only` (git's default `--overwrite-ignore`) and a behind-only `pull --rebase` both silently overwrite an ignored local file that an incoming commit writes. With `--no-overwrite-ignore`, git refuses at write time and leaves HEAD, the index and the worktree unchanged. That holds for the exact path, for an ignored file where an incoming directory goes, and for an ignored directory where an incoming file goes.
> | - **Git's refusal message** names the files raw, with control characters replaced by '?'. If you print it, avoid `echo -e` / `warn()`, which would decode any literal backslash sequence in a filename.
> | - **What `ait sync` now does** (aitask_sync.sh `do_pull_rebase`): it fast-forwards only to a pinned upstream SHA, using `--ff-only --no-autostash --no-overwrite-ignore`. A refusal is reported and never retried as a rebase.
> | 
> | Whether the same flags fit the syncer's `pull --ff-only` on main is this task's decision.
