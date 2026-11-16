---
priority: medium
effort: medium
depends: []
issue_type: performance
status: Ready
labels: [sitrep, tui, tmux]
gates: [risk_evaluated]
anchor: 2175
followup_kind: risk_mitigation
created_at: 2026-11-16 09:39
updated_at: 2026-11-16 09:39
---

## Origin

Risk-mitigation ("after") follow-up for t2309, created at Step 8d after implementation landed.

## Risk addressed

code-health — synchronous guarded Enter can block the minimonitor event loop ~15–20s on a tmux stall

- The guarded dispatch runs synchronously on the Textual event loop. That is deliberate: it keeps the no-await checkpoint→key and dispatch→outcome invariants. But it makes 3 blocking `tmux_run` calls (plus a 4th on a skip), each with the 5s default timeout, and the cleanup still runs after a failed ack. A tmux stall can freeze the minimonitor for about 15–20s, up from about 5s with today's single `send_keys`. This plan has no responsiveness acceptance criterion. · severity: medium · → mitigation: bounded_guarded_dispatch_budget

## Goal

Since t2309, `minimonitor_app._submit_shadow_prompt`'s `send_enter` calls
`monitor_core.guarded_send_key` **synchronously** on the Textual event loop. That is
deliberate: the shared loop (`monitor/agent_submit.submit_typed_text`) needs no await
between the supersession checkpoint and the key. It also needs no await between the
dispatch and the fatal `"failed"` returns, which `_service_review_loop` disarms on with
no lifecycle check (t2001 / t2009).

`_guarded_dispatch` makes blocking `TmuxMonitor.tmux_run` calls, each with
`timeout=5.0`: `if-shell`, the ack read-back, the ack unset, and the skip-reason read
on a skip. It still runs the cleanup after a failed ack. A stalled tmux therefore
freezes the minimonitor for about 15–20s.

Bound it, preserving both invariants:

- **Option A:** give `guarded_send_key` / `_guarded_dispatch` an overall budget, e.g.
  per-call timeouts derived from a deadline, with any overrun classified `unknown`,
  never `sent`. Then check the sitrep caller (`agent_request_delivery`, which already
  uses `asyncio.to_thread`) for the same budget.
- **Option B:** keep only the `if-shell` on the loop and move the ack read-back and
  cleanup to a thread. Re-validate the delivery token after that await and before
  applying any outcome, so a stale fatal code can never disarm a fresh lifecycle.
- Add a responsiveness acceptance test: a fake `tmux_run` that stalls must not hold the
  loop past the budget, and the outcome must be `unknown` / `DISARM_ENTER_UNACKNOWLEDGED`.
- Keep `tests/test_submit_labels_pinned.py` and the supersession tests in
  `tests/test_minimonitor_concern_action.py` (`SupersessionDuringDeliveryAwaitsTests`)
  green.
- Update `aidocs/framework/shadow_agent.md` item 9 (the synchronous-dispatch sentence).
