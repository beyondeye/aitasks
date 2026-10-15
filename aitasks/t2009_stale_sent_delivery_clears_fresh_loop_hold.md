---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [shadow, aitask_monitormini, review_loop]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2001
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-15 21:34
updated_at: 2026-10-15 23:08
---

## Origin
Spawned from t2001 during Step 8b review.

## Upstream defect
- `.aitask-scripts/monitor/minimonitor_app.py:4653-4656` (as of commit 159437cd1) — the `"sent"` branch of `_service_review_loop` calls `_clear_loop_hold()` unconditionally, even when `ctrl.confirm_fire(token, …)` returns `False` because the delivery was superseded (a disarm + re-arm during the post-Enter drain/capture, which `_submit_shadow_prompt` does not re-check before returning `"sent"`). A stale delivery can therefore clear a hold reason the fresh lifecycle set. Low impact (no key is sent, no disarm; the next hold re-records), out of scope for t2001.

## Diagnostic context
t2001 established that the delivery methods must re-check the delivery token after their last await and before deciding ANY outcome, because `_service_review_loop` acts on every outcome without a lifecycle check: a stale `"failed"` used to disarm a freshly re-armed loop (fixed in t2001 for the pre-Enter READY/WORKING dispatch and the budget-exhausted `submit_unconfirmed` return — see `SupersessionDuringDeliveryAwaitsTests` in `tests/test_minimonitor_concern_action.py`).

The `"sent"` route is the one outcome t2001 left alone: after the post-Enter drain + capture, `_submit_shadow_prompt` returns `"sent"` with no token check. The caller then runs `ctrl.confirm_fire(token, …)` — a no-op returning `False` for a stale token — and `_clear_loop_hold()` regardless, mutating the live (fresh) lifecycle's `_loop_hold_reason`. Effects: a hold banner the fresh lifecycle is showing can vanish for a tick, and the edge-triggered hold toast/record fires again on the next occurrence.

## Suggested fix
Gate the clear on the confirmation: `if ctrl.confirm_fire(token, time.monotonic()): self._clear_loop_hold()`. A test in the style of `SupersessionDuringDeliveryAwaitsTests`: re-arm at the post-Enter capture with a submitting composer, set a hold reason on the fresh lifecycle in the hook, assert it survives the stale "sent".

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T20:08:37Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-15T20:53:00Z status=pass attempt=1 type=human
