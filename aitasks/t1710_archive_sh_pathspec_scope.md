---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [git, task_metadata, robustness]
gates: [risk_evaluated]
anchor: 1599
followup_kind: risk_mitigation
created_at: 2026-09-04 15:53
updated_at: 2026-09-04 15:53
---

## Origin

Risk-mitigation ("after") follow-up for t1702, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — the same defect remains in `aitask_archive.sh`.

From t1702's `## Risk`: "The same defect remains in `aitask_archive.sh` (3
sites), so 'the board never swallows a bystander' is true only for these three
paths — the board's archive gesture still routes through that script · severity:
medium".

## Goal

t1702 gave the board's delete / rename / commit-dialog sites a pathspec and
removed their staging. The **archive** gesture was deliberately left out of
scope, so the swallow is still reachable from the board — by the one path a user
is most likely to take after finishing a task.

Two halves, and they must land together: fixing the script alone would leave its
caller staging deletions with nothing to consume them.

1. `.aitask-scripts/aitask_archive.sh:283,565,645` — three pathspec-less
   `task_git commit` calls. Route them through the scoped seam
   (`lib/task_utils.sh::ait_commit_paths_staging_untracked`, or
   `task_git_commit_scoped` directly), naming every path the archive wrote —
   the moved task/plan files, the parent's `children_to_implement`, and any
   carry-over checklist it seeded.
2. `.aitask-scripts/board/aitask_board.py:13718` (`_do_archive`) — `git rm -f`
   parks staged deletions in the shared `.aitask-data` index and currently
   *depends* on the archive script's index-wide commit to consume them. Once (1)
   is scoped, that dependency breaks: switch to a worktree unlink and let
   `commit -o` record the deletion, exactly as `_do_delete` now does.

Re-derive both line numbers before starting; do not trust these.

## Verification

- a bystander control per site: a file staged by a simulated concurrent session
  must not appear in the archive's commit
- negative control: each assertion must fail against today's pathspec-less
  `task_git commit`
- the archive must still commit everything it wrote — verify by measurement, as
  t1702 did, not by reading the source. t1702's characterization found the
  board's delete leaving the parent and revived-folded writes dirty and
  ownerless; check whether the archive path has the same omission before
  assuming its current pathspec is complete.

## References

- `tests/test_task_commit_scoped.sh` — the helper-level contract and its
  measured mutation matrix
- `tests/test_board_scoped_task_commit.py` — the board-level pattern (real
  worker bodies via `__wrapped__` over a `board_fixture` tree)
- `aidocs/framework/tui_conventions.md` — "Task and plan files: commit them
  path-scoped, and stage nothing you need not"
