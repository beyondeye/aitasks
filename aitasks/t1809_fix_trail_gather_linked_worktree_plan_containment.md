---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [trails, python]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1794
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-14 23:39
updated_at: 2026-09-16 10:31
---

## Origin

Spawned from t1794_3 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/trail_gather.py:1185 — _contained_plan_path realpath-confines plan refs to the project root, so in a linked worktree (aitask_init_data.sh --link-worktree) the aiplans/ symlink into the primary checkout's .aitask-data resolves outside it: drift returns ERROR:ref_outside_project (board banner "drift unavailable"), and 2 tests in tests/test_roadmap_drift_contract.py fail in any linked worktree`
- `tests/test_data_branch_setup.sh:781 — zero-byte fixture-named task files sit in the live aitasks/ (t1_alpha.md 2026-09-02, t2_beta.md and t10_gamma.md 2026-08-27, plus one more reported only as "+1 more" by the toast); the names match fixtures written by this test and tests/test_boardcol_update.sh (which run leaked them is not proven); they make every By-Trail discovery toast "Trail scan skipped 4 unreadable active task file(s)"`

## Diagnostic context

- t1794_3 ran the full Python suite and a board smoke in isolated linked
  worktrees (`git worktree add --detach` + `aitask_init_data.sh
  --link-worktree`). In BOTH the unchanged base worktree and the change
  worktree, `tests/test_roadmap_drift_contract.py` fails
  `test_a_wide_generation_over_unpublished_candidates_makes_it_STALE` and
  `test_anchor_roots_in_scope_topics_DO_raise_topic_drift` with
  `'ERROR:ref_outside_project:aitasks:aiplans/p1118/p1118_1_shadow_driving_protocol_design_doc.md' != 'STALE'`;
  the same module passes in the primary checkout.
- In `ait board` started from a linked worktree, the By-Trail banner reads
  `(drift unavailable: ref_outside_project)` for a trail that is fine in the
  primary checkout.
- Mechanism: `_contained_plan_path` compares `os.path.realpath(tree.root)` with
  `os.path.realpath(root/relpath)`. In a linked worktree `aiplans/` is a symlink
  to `<primary>/.aitask-data/aiplans`, so every plan ref's realpath leaves the
  worktree root; the caller (`trail_gather.py:1366`) then appends
  `ref_outside_project:<ref>` (`:1368`) and the whole drift run errors out.
- Worktree-mode picks (profiles with `create_worktree: true`) link their
  worktrees exactly this way, so drift and roadmap checks break for real work
  there, not only in tests.
- The stray files: `: > aitasks/t10_gamma.md` at
  `tests/test_data_branch_setup.sh:781`; `tests/test_boardcol_update.sh` also
  names `t1_alpha` / `t2_beta`. Nothing in t1794_3 created or removed them
  (their mtimes predate it by weeks).

## Suggested fix

- Containment: accept a plan path whose realpath lies under the realpath of the
  project's own `aiplans/` target (the data worktree the symlink legitimately
  points to), keeping the traversal guard for every other escape; add a test
  with a linked-worktree fixture (symlinked `aiplans/`) that is red before the
  fix.
- Stray files (may deserve its own task): find the test that writes into the
  live tree (cwd or TASK_DIR not isolated), fix it, then remove the files once
  no other session owns them.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-16T07:31:14Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-16T08:19:20Z status=pass attempt=1 type=human
