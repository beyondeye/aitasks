---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [syncer, git]
gates: [risk_evaluated]
anchor: 1599
followup_kind: upstream_defect
created_at: 2026-09-10 15:54
updated_at: 2026-09-10 15:54
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
