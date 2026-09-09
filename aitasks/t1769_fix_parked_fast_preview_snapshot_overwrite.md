---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [minimonitor, aitask_monitor, aitask_monitormini, tui, textual, python, testing]
anchor: 1705
followup_kind: upstream_defect
created_at: 2026-09-09 16:28
updated_at: 2026-09-09 16:28
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
