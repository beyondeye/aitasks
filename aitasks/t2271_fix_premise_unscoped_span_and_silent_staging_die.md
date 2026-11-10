---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2261
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-10 11:46
updated_at: 2026-11-10 17:51
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2261_2** id=2026-11-10T16:31:38Z.d95631983b9679ef48c4017b from=t2261_2 from_verified=yes at=2026-11-10T16:31:38Z base=9b54f33d862389402747cae9cc7c5ce492661cef base_branch=main dirty=yes host=omg16
>
> | Advisory context from t2261_2 (release-notify consumer, committed as 37ddf2fe6), not an instruction.
> | 
> | A new caller of `ait_commit_paths_staging_untracked` (lib/task_utils.sh) landed: `_ril_commit_move` in `.aitask-scripts/lib/release_issue_ledger.sh`. It commits a release-ledger move as ONE path-scoped commit of two paths: an UNTRACKED new file (`released/<tag>/<name>.rec`, staged by the helper) plus a TRACKED path deleted from the worktree (`pending/<name>.rec`), relying on the helper's documented `commit -o` behaviour for a tracked deletion (no staging of that path; `ls-files --error-unmatch` still matches it in the index). It never trusts the helper's rc: `_ril_move_landed` re-reads git state afterwards (`_ril_hit_state` committed + `diff --quiet HEAD` for the released path; pending absent from HEAD and worktree).
> | 
> | It runs inside subshell bodies (`ril_move_released`, `ril_resume_move`) whose EXIT trap calls `( ait_unstage_staged_by_us )` then releases a ledger lock, so a die inside the helper is contained to that subshell.
> | 
> | If your change alters the helper's add/commit sequence or its die/stderr behaviour, these exercise the new caller (all passed with your uncommitted task_utils.sh edit present in the working tree, as of this note's writing — a moment-relative observation):
> | - bash tests/test_release_notify.sh  — cases (b), (p), (q), (u)
> | - bash tests/test_release_notify_branch_mode.sh — cases (1), (6) (real .aitask-data worktree)
> | - bash tests/test_issue_update_ledger.sh — the t2261_1 writer (`_ril_commit_record`), cases (r), (s), (t)

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-10T15:51:42Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-10T16:56:56Z status=pass attempt=1 type=human
