---
priority: medium
effort: medium
depends: [t1747_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1747_1, 1747_2, 1747_3, 1747_4, 1747_5, 1747_6]
anchor: 1733
followup_kind: manual_verification
created_at: 2026-09-09 11:29
updated_at: 2026-09-09 11:29
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1747_1] Open aidocs/framework/failopen_git_probes.md and spot-check five cited file:line references against the current tree — each must resolve to the code it claims. (The parent audit had to correct three stale references from the task body, so this is a real failure mode.)
- [ ] [t1747_1] Confirm the doc's Group A table assigns every row to a child, and that the child set matches the six tasks that actually exist.
- [ ] [t1747_1] Confirm the doc is reachable from a pointer CLAUDE.md already routes through (normally the shell_conventions.md pointer), not only by knowing its path.
- [ ] [t1747_2] On this repo, run a real `ait sync` while another session holds work, and confirm a normal pull/rebase still completes — the automerge path is reached by every pick and push, so a fail-closed regression here blocks all work.
- [ ] [t1747_2] Confirm no task-data commit went missing after a sync that resolved conflicts: compare `./ait git log --oneline` before and after, and check the remote commit is present in local history.
- [ ] [t1747_3] Run `ait sync` on a clean tree and confirm it reports normally (not a new UNVERIFIED/deferral path) — A3, A4, A5 and A10 all added refusals to this one command.
- [ ] [t1747_3] With a quarantined path present, confirm a genuinely settled entry still releases and is published — the A4 fix must not turn every quarantine into a permanent hold.
- [ ] [t1747_4] Run `ait setup` in this repo while another session has uncommitted work under framework paths, and confirm setup commits only its own files and reports the foreign ones as left alone.
- [ ] [t1747_4] Run `ait setup` in a freshly installed scratch project (untracked VERSION) and confirm the bootstrap commit-all path still fires with its blast-radius warning — the A9b fix must not turn every fresh install into a refusal.
- [ ] [t1747_5] Perform a fold or PR-import that uses --commit-mode amend on a checkout with no upstream configured, and confirm the amend still succeeds — this is the case the A6/A7 fix is most likely to regress.
- [ ] [t1747_6] Pick a task normally (`/aitask-pick <id>`) and confirm the lock is acquired; then attempt to pick the same task from a second session and confirm you get LOCK_LIVE_HOLDER, not a silent second claim.
- [ ] [t1747_6] Run a real `ait merge` begin/abort cycle and confirm the reservation is released; then check `force-release --dry-run` prints a correct remedy flag on a genuine merge residue.
- [ ] [cross-cutting] Complete one full pick -> plan -> implement -> commit -> merge -> archive cycle on a throwaway task, end to end, with all six children landed. This is the check no fixture can make: every child moved code from "proceed on an unread probe" to "refuse", so the risk being verified is that the framework now refuses something it should permit.
- [ ] [cross-cutting] Confirm every new refusal message names a recovery route (re-run, --commit-mode fresh, force-release, manual commit). A refusal with no way out is a dead end, not a fix.
