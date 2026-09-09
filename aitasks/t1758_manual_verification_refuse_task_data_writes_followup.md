---
priority: medium
effort: medium
depends: [1725_2]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1725_2]
anchor: 1599
followup_kind: manual_verification
created_at: 2026-09-09 09:59
updated_at: 2026-09-09 09:59
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1725_2

## Verification Checklist

- [ ] Wedge the data worktree for real: `git -C .aitask-data rev-parse --absolute-git-dir` then `mkdir -p "$(that)/rebase-merge"`. Run `ait update 10 --priority low` (batch) and confirm the refusal names the state, offers both retry and abort, and that the task file is byte-identical afterwards.
- [ ] With the same wedge in place, run `ait update` with NO arguments so the real interactive/fzf flow starts. Confirm it refuses IMMEDIATELY, before offering a task picker or any field prompt — the guard is the first statement of run_interactive_mode precisely so the user is not asked to fill in an edit that cannot land.
- [ ] Read the refusal message as a user who does not know this codebase. Confirm it says which state the worktree is in, that retrying may be enough if a sync is running, and gives a recovery command that actually applies to that state (a MERGE_HEAD must not be handed `rebase --abort`).
- [ ] Repeat the refusal with a non-rebase state: `: > "$(gitdir)/MERGE_HEAD"`. Confirm the message says mid-MERGE_HEAD, not mid-rebase.
- [ ] Clear the wedge (`rm -rf <gitdir>/rebase-merge`, `rm -f <gitdir>/MERGE_HEAD`) and confirm normal `ait update` / `ait create --batch --commit` work again with no residue.
- [ ] Force a create commit failure on a CLEAN worktree: `: > "$(gitdir)/index.lock"`, then `ait create --batch --commit --name probe --desc d`. Confirm it exits 0, prints the path, and the stderr warning names the real cause (the index lock) rather than an empty parenthetical.
- [ ] Remove the index.lock and run `ait sync`. Confirm the abandoned file is swept in under its own task id and that no second create was needed (the id counter advanced by exactly one across the whole exercise).
- [ ] Confirm `ait git-health` still describes the worktree accurately at each stage above — it is the diagnostic the refusal message points the user at.
