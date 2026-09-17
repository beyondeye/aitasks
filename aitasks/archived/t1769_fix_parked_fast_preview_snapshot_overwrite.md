---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [minimonitor, aitask_monitor, aitask_monitormini, tui, textual, python, testing]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-09 16:28
updated_at: 2026-09-17 10:00
completed_at: 2026-09-17 10:00
---

## Origin

Spawned from t1705_7 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/monitor_core.py:2954 — commit_snapshot (singular) has no parked branch, so a focused parked pane is captured and classified on the fast-preview route and its parked=True snapshot overwritten; the parked placeholder at monitor_app.py:2024 then reverts to stale content and the session-bar term drops it. Pre-existing t1685 defect, not introduced here; the frozen guard added in t1705_7 makes the parked case a two-line addition.`

## Diagnostic context

There are **two** capture routes in `monitor_core`, and only the bulk one was
ever state-aware:

- `capture_all_classified_async` + `commit_snapshots` (plural) — splits parked
  panes out before capture and routes them to `_parked_snapshot`.
- `capture_pane_classified_async` + `commit_snapshot` (singular) — no state
  branch at all. `monitor_app._fast_preview_refresh` uses this one, then writes
  `self._snapshots[pane_id] = snap` unconditionally.

So focusing a parked card captures its pane, runs prompt/idle classification
over it, and replaces its `parked=True` snapshot with an ordinary one. The user
loses the parked preview placeholder (`monitor_app.py` reads
`snapshots[...].parked`), the row's parked rendering, and the session-bar term —
on the very pane they are looking at.

Found while verifying t1705_7's plan: the frozen state had the identical hole,
which that task fixed at the core seam so every caller inherits it. The parked
case was deliberately left out of scope — it is a behaviour change to shipped
t1685 code with its own test expectations, not something to fold into a
frozen-rows task.

## Suggested fix

Mirror what t1705_7 did for frozen, at the same two functions:

1. `capture_pane_classified_async` returns before its tmux await when the pane
   is parked, yielding `ClassifyResult(compare_value="", parked=True)`.
2. `commit_snapshot` routes a `result.parked` to `_parked_snapshot`, mirroring
   `commit_snapshots`.

Note the ordering rule t1705_7 established: frozen is checked FIRST at every
partition site, because a pane can carry the parked mark *and* be frozen, and a
parked-first split hands such a pane a `parked=True, frozen=False` snapshot that
no renderer can recover. Do not reintroduce a parked-first branch here.

Unlike frozen, parked is published down from the App (`set_parked_agents`)
rather than read off the discovery row, so confirm the parked set is populated
on the fast route before relying on `_is_parked_pane`.

Test harness to mirror: `tests/test_monitor_frozen_capture.py`
`FastPreviewRouteTests` (core-level: no capture, no classify, frozen snapshot
returned) and `FastPreviewAppRouteTests` (app-level: the snapshot survives
`_fast_preview_refresh` and the placeholder renders, with a live-pane negative
control). Both have pre-fix controls recorded — removing the core guard fails 2.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1705_7** id=2026-09-09T13:31:56Z.06bccdc278d72e2185e0deff from=t1705_7 from_verified=yes at=2026-09-09T13:31:56Z base=d822b650a2362b82356f64ff1e5292ef2556f0f4 base_branch=main dirty=no host=Darios-Mac-mini.local
>
> | Pointer to the working reference for this fix, recorded here so it does not have
> | to be rediscovered. Advisory only.
> | 
> | t1705_7 fixed the identical hole for the **frozen** state at the same two
> | functions, and its commits are the template:
> | 
> | - `cdadfdf68 feature: Add frozen snapshot plumbing and extract the restore verdict (t1705_7)`
> |   — the core guard: `capture_pane_classified_async` returns before its tmux
> |   await, and `commit_snapshot` routes the flagged result to the state snapshot.
> | - `d822b650a test: Replace the tautological filter tests, and cover the promised paths (t1705_7)`
> |   — `FastPreviewAppRouteTests` in `tests/test_monitor_frozen_capture.py`, which
> |   is the app-level half you will want to mirror.
> | 
> | Two things learned there that apply directly:
> | 
> | - **Core-level tests are not sufficient.** The first version stopped at the two
> |   `monitor_core` methods, which leaves the reachability claim unproven — the
> |   defect is a reverting preview, not a core call. Drive `_fast_preview_refresh`
> |   on a mounted app and assert both that the snapshot survives and that the
> |   placeholder renders, with a live-pane negative control.
> | - **Frozen must stay checked FIRST at every partition site.** A pane can carry
> |   the parked mark and be frozen; a parked-first split hands it
> |   `parked=True, frozen=False` and no renderer can recover the lost flag. When you
> |   add the parked branch, add it *after* the frozen one — `commit_snapshots`
> |   (plural) already has them in that order and is the shape to copy.
> | 
> | One difference from frozen: parked is published down from the App
> | (`set_parked_agents`) rather than read off the discovery row, so confirm the
> | parked set is populated before the fast route consults `_is_parked_pane`. That is
> | why frozen needed no publish-down and parked may.

> **👁 note:read** id=2026-09-17T06:27:41Z.e32cbb11510721c1ec20f037 by=t1769 at=2026-09-17T06:27:41Z mode=explicit ids=2026-09-09T13:31:56Z.06bccdc278d72e2185e0deff

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-17T06:46:07Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-17T06:55:37Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-17T07:00:30Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:ad5ab479de485e5b

> **✅ gate:risk_evaluated** run=2026-09-17T07:00:30Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1769/risk_evaluated_2026-09-17T07:00:30Z-risk_evaluated-a1.log`
