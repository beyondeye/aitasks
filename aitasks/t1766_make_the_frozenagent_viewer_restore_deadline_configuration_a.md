---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [frozen]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: upstream_defect
created_at: 2026-09-09 15:31
updated_at: 2026-09-10 08:50
---

`frozenagent_app._poll_restore` passes `settle_timeout=DISPATCH_GRACE + 30.0`
(40s) to `agent_sessions.restore_verdict`, ignoring the target project's
`frozen.restore_ack_grace`.

`agent_restore` gives a `restoring` record up to that grace to be acknowledged
by its replacement agent's SessionStart hook before it may be liveness-confirmed
instead. With a valid grace above ~30s, the viewer therefore warns and stops its
timer while the restore is still legitimately in flight: every successful
restore is reported as a stall, and the eventual success is never shown.

This is the twin of a defect fixed in `monitor_shared._poll_frozen_outcome`
under t1705_7. That fix added the shared helper this one needs:

    agent_frozen_ops.restore_settle_timeout(root, *, dispatch_grace)

which returns `dispatch_grace + restore_ack_grace(root) + slack` and is pinned by
`tests/test_frozen_restore_verdict.py::SettleTimeoutTests`. At the DEFAULT grace
it returns exactly the 40.0 the viewer hardcodes, so the change is behaviour-
identical under default config — which is also why
`tests/test_frozenagent_restore_poll_characterization.py` should stay green
across it. Read the root from the record being polled, not from the cwd.

Not folded into t1705_7: that task's scope was the monitor TUIs, and this is
shipped t1705_6 code with its own characterization control. Found by review of
t1705_7.
