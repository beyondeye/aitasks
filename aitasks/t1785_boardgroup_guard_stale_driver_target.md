---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
anchor: 1733
followup_kind: upstream_defect
created_at: 2026-09-10 15:17
updated_at: 2026-09-10 15:17
---

## Origin

Spawned from t1747_2 during Step 8b review. The `anchor:` this task carries is the
topic root, not the exact origin — the origin is t1747_2.

## Upstream defect

- `tests/test_aitask_merge_boardgroup.sh:197-203` — Test 3's "every driver invocation
  passes --base-file" guard greps `aitask_sync.sh` for `"$_MERGE_PYTHON" "$_MERGE_SCRIPT"`,
  which t1727 (`66da94134`) moved to `lib/task_automerge.sh` as
  `"$_AIT_AUTOMERGE_PYTHON" "$_AIT_AUTOMERGE_SCRIPT"`; it finds 0 invocations and fails
  1/18 at HEAD `dc755d85c` independent of t1747_2 (replayed in a clean worktree). The
  moved invocation does pass `base_args`, so only the guard's target is stale.

## Diagnostic context

- Surfaced while running the regression suites for t1747_2 (every other automerge-path
  suite green). `bash tests/test_aitask_merge_boardgroup.sh` →
  `FAIL: At least one driver invocation exists (guard is not vacuous) (expected '1', got '0')`,
  17/18 passing.
- Replayed at the literal SHA `dc755d85c` in a detached worktree with no working-tree
  changes: identical failure, so it predates t1747_2.
- It is the guard's own anti-vacuity assertion that fires — it is doing its job. The
  guarded property (every merge-driver invocation passes `--base-file`) still holds at
  `lib/task_automerge.sh::ait_automerge_files` (`${base_args[@]+"${base_args[@]}"}`), but
  nothing checks it any more.

## Suggested fix

Retarget Test 3 at `lib/task_automerge.sh` and the current
`"$_AIT_AUTOMERGE_PYTHON" "$_AIT_AUTOMERGE_SCRIPT"` shape, keeping the anti-vacuity count.
Consider scanning every `.sh` under `.aitask-scripts/` for driver invocations instead of
one named file, so the next move cannot silently empty it again.
