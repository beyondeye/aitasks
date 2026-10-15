---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [trails, skills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1989
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-15 22:11
updated_at: 2026-10-15 23:49
---

## Origin

Spawned from t2004 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_attach.sh:233 — cmd_add resolves its owner with resolve_task_file and writes attachments: into whatever file comes back, so 'ait attach add <archived id>' commits an attachment entry into a loose archived task file (and for a bundled id targets a temp extraction) — same shape as the cmd_create gap t2004 closed; not reproduced`

## Diagnostic context

t2004 made `ait artifact create` refuse an archived owner. `resolve_task_file`
(`lib/task_utils.sh:2324`) checks the active dir first, then loose files in
`aitasks/archived/`, then extracts from numbered or legacy `.tar.zst` bundles
into a temp file. `cmd_create` never checked which tier answered. The red
proof against pre-fix code showed a loose archived owner getting an
`artifacts:` entry committed into its file. A bundled owner died at
`txn_require_clean` ("… is outside repository") before any mutation.

`ait attach add` (`aitask_attach.sh` `cmd_add`, ~line 233) has the same
shape: it calls `resolve_task_file "$task_id"` and passes the result to
`_attach_add_txn` with no active check. Found by code reading during t2004;
not reproduced.

## Suggested fix

First decide whether attaching to an archived task is intended. If it is not,
mirror t2004: refuse in `cmd_add` when the resolved file is not the active
location. t2004's `_artifact_owner_is_active` in `aitask_artifact.sh` compares
the dirname to `$TASK_DIR` or `$TASK_DIR/t<parent>` with `-ef` (directory
identity, so a trailing slash in `TASK_DIR` cannot misclassify an active
child). If both scripts need the check, consider moving it to a shared helper.

`attach rm` / `ls` / `get` on an archived owner must keep working. Add tests
for the loose and bundled cases, an active control on the same id, and a
trailing-slash `TASK_DIR` case (see section L of `tests/test_artifact_cli.sh`).
`tests/test_attach_lock_callback_contract.sh` pins `aitask_attach.sh` line
numbers in its ALLOWLIST. Re-check those sites and renumber them if the file
shifts.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T20:49:57Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-15T21:05:17Z status=pass attempt=1 type=human
