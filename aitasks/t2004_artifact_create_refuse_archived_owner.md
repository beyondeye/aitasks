---
priority: medium
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
created_at: 2026-10-15 10:12
updated_at: 2026-10-15 12:40
---

## Origin

Spawned from t1989 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_artifact.sh:241 — cmd_create resolves the owner with resolve_task_file (lib/task_utils.sh:2324), which also returns archived loose files and bundle-extracted temp files, so 'ait artifact create <archived id>' does not refuse an archived owner and would write an artifacts: entry into an archived task file (by code reading; not reproduced)`

## Diagnostic context

t1989 made `aitask_trail_gather.sh snapshot` refuse an archived owner on the
create path (`ERROR:archived_owner:<ref>`). Only refresh accepts one, via
`--allow-archived-owner`. The reason is that the snapshot's `OWNER:` line
feeds `aitask_artifact.sh create <owner_id>`, and `cmd_create`
(`aitask_artifact.sh:241`) resolves that id with `resolve_task_file`. That
function checks the active dir, then `aitasks/archived/`, then extracts from
numbered or legacy `.tar.zst` bundles into a temp file
(`_extract_from_archive`). Neither `cmd_create` nor `_artifact_create_txn`
checks whether the resolved file is active.

So the trail skill is now guarded by the gatherer, but the substrate itself
is not:
- a direct `ait artifact create <archived id> …` would append an
  `artifacts:` entry to a **loose archived** task file and commit it;
- for a **bundled** id, it would write into a temp extraction outside the
  repo. Expect `txn_require_clean` / the commit to fail; unverified.

Found by code reading during t1989 planning; not reproduced.

## Suggested fix

Have `cmd_create` refuse an owner whose resolved file is not under the active
`$TASK_DIR` (excluding `$ARCHIVED_DIR`), with a message naming the task as
archived. First check whether any intentional flow creates artifacts on
archived tasks (`ait artifact rm` / `ls` / `get` on archived owners must keep
working; trails outlive their owners). Add a test for both the loose-archived
and the bundled case.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T09:40:51Z status=pass attempt=1 type=human
