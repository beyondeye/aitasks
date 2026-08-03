---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: refactor
status: Done
labels: [aitask_monitor, shadow, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1111
implemented_with: claudecode/opus5
created_at: 2026-07-28 11:53
updated_at: 2026-08-03 11:19
completed_at: 2026-08-03 11:19
boardidx: 360
---

## Origin

Risk-mitigation ("after") follow-up for t1216_1, created at Step 8d after
implementation landed.

## Risk addressed

From t1216_1's `## Risk` section (code-health):

- "The transitional delegating seams left on `MiniMonitorApp` mean two names for
  one implementation until t1216_2/_3 land — structure debt that will quietly
  become permanent if nobody removes it."

## Goal

Remove the transitional delegating seams from `MiniMonitorApp` and point the
remaining callers and tests at the shared `monitor_core` functions directly.

### Why they exist

t1216_1 lifted the shadow helpers into `monitor_core.py` but deliberately left
one-line delegators behind on `MiniMonitorApp`:

- `_find_shadow_pane_for_sync`  -> `monitor_core.find_shadow_pane`
- `_find_shadow_pane_for`       -> `monitor_core.find_shadow_pane_async`
- `_capture_shadow_text`        -> `monitor_core.capture_shadow_text`
- `_format_stale_duration`      -> `monitor_shared.format_stale_duration`

They were kept for one reason: the existing shadow test suite binds to those
private names (stubbing `app._capture_shadow_text`, calling
`mm.MiniMonitorApp._format_stale_duration`, and using a `_FakeMon` that exposes
only `tmux_run` / `tmux_run_async`). Keeping the seams let the whole
characterization net pass **byte-unmodified**, which was that task's proof that
the lift changed no behaviour. That proof has now served its purpose.

### Scope

- **Do not start until t1216_2 and t1216_3 have landed** — the seams should only
  come out once the shared functions have a second real consumer in
  `monitor_app.py`, so removing them cannot quietly regress the one caller left.
- Delete the four delegators; update minimonitor's internal call sites to call
  the shared functions directly.
- Migrate the affected tests off the private names and onto the shared seam:
  - `tests/test_minimonitor_concern_action.py` (`CaptureArgvTests`,
    `ActionPickConcernsTests`, `AutoOfferTests`, `ShadowFreshnessTests`,
    `LaunchShadowGuardTests`)
  - `tests/test_minimonitor_concern_smoke.py` (live-tmux; drives the REAL
    capture through `app._capture_shadow_text` — needs the most care, since its
    whole point is that the production path is not stubbed)
  - `tests/test_minimonitor_shadow_pick.py`
  - `tests/test_shadow_seam.py` (already targets the shared functions; should
    need no change)
- Keep the module-level `match_shadow_pane` re-export in `minimonitor_app` or
  migrate `mm.match_shadow_pane` references in the same pass — decide one way and
  do it consistently.

### Acceptance

- No `MiniMonitorApp` method whose body is solely a call to a `monitor_core` /
  `monitor_shared` function.
- The full Python suite plus `tests/test_no_raw_tmux.sh` pass.
- Behaviour is unchanged: this is a pure de-duplication, so any test that has to
  change should change only in *which name it calls*, never in what it asserts.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-03T07:33:28Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-03T08:12:24Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-03T08:19:29Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:799fbfbe0426be79

> **✅ gate:risk_evaluated** run=2026-08-03T08:19:29Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1289/risk_evaluated_2026-08-03T08:19:29Z-risk_evaluated-a1.log`
