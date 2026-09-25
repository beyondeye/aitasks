---
Task: t1880_fix_multi_session_monitor_snapshot_frozen_attr.md
Base branch: main
Output branch: main
---

# t1880 — Give the multi-session monitor test snapshots the `frozen` field

## Context

`tests/test_multi_session_monitor.sh` exits 1 on HEAD. The failure is
`AttributeError: 'types.SimpleNamespace' object has no attribute 'frozen'`.
Since t1705_7 (fcf144025), `MonitorApp._format_agent_card_text`
(`.aitask-scripts/monitor/monitor_app.py:1756`) reads `snap.frozen`. The test
builds its snapshot by hand as a `SimpleNamespace` that was never given that
field.

Exploration found the **same crash in `tests/test_multi_session_minimonitor.sh`**.
Its five `mk_snap` doubles hit the minimonitor renderer's `a.frozen` /
`snap.frozen` reads (`minimonitor_app.py:2222-2325`). The Python tests that also
use SimpleNamespace snapshot doubles already pass (175 passed), so they stay out
of scope.

## Approach

Build the snapshot from the **real `PaneSnapshot` dataclass**
(`monitor_core.py:1272`), not by adding `frozen=False` to each double. This is
the task's suggested "build from the real type" option: any future defaulted
field (`parked`, `frozen`, `awaiting_input`, …) then defaults instead of
crashing a stale double. The *pane* double stays a `SimpleNamespace`: the
renderers read only the fields it already sets, and the reported defect is
about the snapshot. `PaneSnapshot` is re-exported by both `monitor_app` (`ma`)
and `minimonitor_app` (`mm`), so no new import path is needed.

Pattern for each `mk_snap`:

```python
return ma.PaneSnapshot(pane=pane, content="", timestamp=0.0,
                       idle_seconds=0.0, is_idle=False)
```

(Use `mm.PaneSnapshot` in the minimonitor file, and keep `is_idle=idle` where
the builder takes it.) The explicit `parked=False` goes, because it is now the
dataclass default. Replace the "`parked` is a real PaneSnapshot field" comment
with a one-line note that this is the real type, so new defaulted fields cannot
break the double.

## Files

- `tests/test_multi_session_monitor.sh`: `mk_snap` at ~line 717.
- `tests/test_multi_session_minimonitor.sh`: the five `mk_snap` builders at
  ~lines 220, 291, 335, 452 and 513.

## Verification

- `bash tests/test_multi_session_monitor.sh` → exits 0, all PASS.
- `bash tests/test_multi_session_minimonitor.sh` → exits 0, all PASS.
- `shellcheck` is unaffected (only the embedded Python changes).

## Step 9

Post-implementation: commit with `test: … (t1880)`, then archive through the
standard Step 9 flow (current-branch mode, nothing to merge).

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
