---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: [t2037_1]
issue_type: feature
status: Done
labels: [monitor, minimonitor]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2034
implemented_with: claudecode/opus5_5
created_at: 2026-10-16 08:11
updated_at: 2026-11-06 00:06
completed_at: 2026-11-06 00:06
---

The Python `MonitorClient` (parent: Python monitor status server task).

## Do

- Expose the `TmuxMonitor` read surface the apps use (`capture_all_async`,
  `get_shadow_snapshot`, `get_session_to_project_mapping_async`, `get_pane`, …),
  backed by a subscription, so the app-side changes stay small.
- Fallback: when the server cannot be reached or started, use in-process
  `TmuxMonitor` (today's code) — the same posture as the existing
  control-mode → subprocess fallback. Reconnect when the server restarts.
- Replay mode: serve a recorded stream file (t2034_3 recorder) instead of a live
  server. The Textual twin of the Go monitor parity demo (aitasks_go#16_5) uses
  it.

## Verification

Tests against a stub server: subscribe/snapshot/delta, stale `gen` dropped,
server restart → reconnect, unreachable → fallback, replay of a recorded
fixture.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2034_1** id=2026-11-03T15:15:59Z.471e83035fa5e9f0ad08a163 from=t2034_1 at=2026-11-03T15:15:59Z base=6930f54e25e74a1e92e01e7fab1a8c1cbbcf2914 base_branch=main dirty=yes host=omg16
>
> | Cross-repo dependent of this task (aitasks_go, as of 2026-11-03): aitasks_go#16_5
> | monitor_parity_demo, with xdeps [t2037_2]. It is the Go monitor port's parity demo
> | and needs to know how a client subscribes.
> | 
> | What reaches it automatically: only this task's Done status (read live through the
> | project registry). Content does NOT: aitasks_go planning reads its own repo's
> | sibling context only.
> | 
> | Suggested handoff at completion (Step 8e): one cross-repo note to aitasks_go#16_5
> | with the client API (subscribe/snapshot/fallback behaviour), how to start a server
> | for a demo, and the test or fixture paths, plus the commit, e.g.
> |   ./ait note 16_5 --project aitasks_go --from 2037_2 --with-live --file - <<'EOF' ... EOF
> | Re-check the dependent list first (grep xdeps in aitasks_go).

> **👁 note:read** id=2026-11-05T07:42:50Z.7bd46b39f84b07a53e4d4be2 by=t2037_2 at=2026-11-05T07:42:50Z mode=explicit ids=2026-11-03T15:15:59Z.471e83035fa5e9f0ad08a163

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-05T09:56:43Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-05T22:02:41Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-05T22:06:24Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:65a7227826066d54

> **✅ gate:risk_evaluated** run=2026-11-05T22:06:24Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2037_2/risk_evaluated_2026-11-05T22:06:24Z-risk_evaluated-a1.log`
