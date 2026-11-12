---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [bash_scripts]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2261
followup_kind: upstream_defect
created_at: 2026-11-12 15:40
updated_at: 2026-11-12 19:38
---

## Origin

Spawned from t2277 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/task_utils.sh:assert_data_worktree_clean` and
  `assert_task_data_writable`: their die messages claim "'--abort' below
  discards only the partially replayed remote commits; your own committed work
  stays on the branch". The claim is incomplete when the shared `.aitask-data`
  index holds staged entries that the in-progress operation does not own.
  Measured on git 2.56: `merge --abort` removed a new file staged into a
  stopped merge from both the index and the worktree.

## Diagnostic context

t2277 (staged entries left by a wedged cleanup) measured with real merges
(`tests/test_staged_entry_ownership.sh`, cases R2c / R2a) that both ways out of
an in-progress operation act on staged entries of uncertain ownership:

- continuing (`--continue`, or committing a resolved merge) commits every
  staged entry along with the operation;
- `merge --abort` deletes a new file staged into the stopped merge from both
  the index and the worktree.

t2277 qualified this only in `ait_unstage_staged_by_us`'s warning, which prints
right after the guard's message. It also added it to `ait git-health`'s
in-progress line ("Before you continue OR abort it, inspect them … copy aside
…"). The guard messages themselves still advertise `--abort` as discarding only
the remote commits. A user who reads only the guard's list can lose an
unrelated session's new file.

The guard text is shared by the two guards and pinned verbatim: the
`'--abort' …` clause "must not drift". Tests assert on it, e.g. "stuck
mid-MERGE_HEAD" in `tests/test_task_commit_scoped.sh`,
`tests/test_issue_update_ledger.sh` and `tests/test_task_push.sh`, and the
two-guard first-sentence distinction. Rewording it means updating those pins
together.

## Suggested fix

Reword the shared `'--abort'` clause in both guards. Say that continuing
commits, and aborting can discard, entries staged in the shared index that the
operation does not own. Point at `./ait git-health`, which lists them, before
the recovery list, so the user inspects first. Keep the two guards' clauses
identical, and update the pinned assertions.
