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
created_at: 2026-11-10 11:46
updated_at: 2026-11-10 12:42
---

## Origin

Spawned from t2261_1 during Step 8b review.

## Upstream defect

Two unrelated pre-existing defects, both surfaced while verifying t2261_1:

- `.claude/skills/task-workflow/premise-staleness.md:213` — `tests/test_no_unscoped_task_commit.sh` reports an unscoped task-data commit instruction here (`UNSCOPED: … AIT_UNPARSEABLE_SPAN`, just before `## Advance after an approved replan`). The same failure (102 passed / 1 failed) reproduces on a clean detached-HEAD worktree at 79416f14c, so it predates t2261_1.
- `.aitask-scripts/lib/task_utils.sh:1101` — `ait_commit_paths_staging_untracked` runs `task_git add -- "$p" >/dev/null 2>&1`. When `task_git`'s `assert_data_worktree_clean` dies there (data worktree mid-rebase/merge/…), its die message goes to `/dev/null`: the process exits 1 with no cause printed. This affects every caller of the helper.

## Diagnostic context

From t2261_1's Final Implementation Notes (`aiplans/archived/p2261/p2261_1_issue_backends_and_ledger_writer.md` once archived):

- The release-ledger test (s) plants `MERGE_HEAD` in the data worktree's git dir right after the helper's `ls-files --error-unmatch` probe. The helper's next `task_git add` then hits the guard and dies. The test expected the guard's "Data worktree (.aitask-data) is stuck mid-MERGE_HEAD" message on stderr and got nothing: the `add` redirect swallowed it. t2261_1 worked around it on its own side by reading the wedge back with `ait_data_inprogress_state` in its recovery hint, but every other caller still gets a silent exit.
- `test_no_unscoped_task_commit.sh` failed during t2261_1's verification. A run on a clean HEAD worktree showed the identical failure on `premise-staleness.md:213`, so it was not caused by t2261_1's procedure edits.

## Suggested fix

- task_utils.sh: run `assert_data_worktree_clean add -- "$p"` (current shell, terminal stderr) before the silenced `task_git add`, or capture the add's stderr to a file and re-emit it on failure, the way `task_git_commit_scoped` already does with `_ait_cs_errf`. Add a regression test with a planted `MERGE_HEAD` asserting the message reaches stderr.
- premise-staleness.md:213: find which span the scanner cannot parse (it reports `AIT_UNPARSEABLE_SPAN`), make the instruction scoped (or the span parseable), regenerate any affected goldens/prerenders, and re-run `tests/test_no_unscoped_task_commit.sh`.
