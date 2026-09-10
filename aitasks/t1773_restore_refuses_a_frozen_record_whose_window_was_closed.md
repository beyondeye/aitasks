---
priority: high
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [tmux, codeagent, session_persistence]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: review_finding
implemented_with: claudecode/opus5
created_at: 2026-09-09 19:53
updated_at: 2026-09-10 14:45
---

## Symptom

Freeze an agent, close its window (or restart the tmux server), then Restore:

```
RESTORE_FAILED:<id>|respawn:respawn-pane refused for %21
```

The record stays `frozen` and the capture survives (so nothing is lost), but
that record can never be restored again through this path. Found by the
composed acceptance suite `tests/test_frozen_agents_acceptance.sh` (t1705_8),
case 6b — which is exactly the cross-child-drift class the suite exists for:
each child is self-consistent, and the join between them is not.

## Cause

`agent_restore._restore` (`.aitask-scripts/lib/agent_restore.py:334,391`) binds
`pane_id = rec.get("pane_id", "")` and then branches on `if pane_id:` — the
**recorded** id, never whether that pane still exists. A retained frozen record
keeps its old `%N` forever, so the branch takes `frozen_ops.respawn()` on a dead
pane instead of `_launch_into_new_window()`.

## Why this is a contradiction, not a missing feature

Two shipped sites already state the opposite contract:

- `agent_freeze.drop_record()`'s docstring: *"The record's `pane_id` is durable
  but NOT authoritative: `_reconcile_frozen` returns `KEEP:<id>|pane_gone` and
  writes nothing, so after a tmux restart every retained record still names a
  `%N` that no longer exists. Keying 'nothing to kill' on an empty `pane_id`
  would make exactly those records undroppable."* `drop` therefore preflights
  the live pane inventory. `restore` does not.
- The same docstring: *"The record stays restorable into a fresh window
  (`_reconcile_frozen`'s `KEEP:<id>|pane_gone`)."* That is the promise this
  defect breaks.

So `_launch_into_new_window` is currently reachable **only** via the
`freezing` + pane-gone reconcile row (`agent_freeze.py:696`), which commits
`--pane "" --pane-pid 0`. A record frozen normally and later orphaned never
gets there.

## Suggested fix

In `_restore`, treat a recorded `pane_id` as a hint and verify it against the
server before choosing the branch — `frozen_ops.pane_facts(pane_id)` is already
used at `:541` and returns `{}` for a gone pane, so the shape exists. Empty
facts should fall through to `_launch_into_new_window`, exactly as `drop`
preflights its target.

## Verification

`tests/test_frozen_agents_acceptance.sh` case 6b currently asserts only the
fail-safe half (record still `frozen`, capture intact) and names this task.
When this is fixed, 6b should assert `RESTORED:<id>` into a new window with the
recorded name, matching case 6a.

Case 6a already covers the reachable gone-pane path end to end, so the
`_launch_into_new_window` branch itself is proven to work — only the routing
into it is wrong.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-10T09:39:21Z status=pass attempt=1 type=human
