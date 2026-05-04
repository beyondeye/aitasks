---
Task: t735_fix_multi_session_monitor_pane_aggregation.md
Base branch: main
plan_verified: []
---

# Plan: Fix MiniMonitorApp test scaffold AttributeError after t733

## Context

t735 was filed claiming `tests/test_multi_session_monitor.sh` had 6/43 failing
assertions on `main`. Verified that this test passes 43/43 on current `main`
(f55d0dcb) AND at the cited baseline 32957a2d — the task's premise does not
reproduce.

However, an adjacent test, `tests/test_multi_session_minimonitor.sh`, IS failing
today with a different root cause. The user agreed to pivot t735's scope to fix
that test instead.

**Failure:**

```
File "/home/ddt/Work/aitasks/.aitask-scripts/monitor/minimonitor_app.py", line 202, in _teardown_prior_monitoring
    if self._refresh_timer is not None:
       ^^^^^^^^^^^^^^^^^^^
AttributeError: 'MiniMonitorApp' object has no attribute '_refresh_timer'
```

**Root cause:** t733 (`e5ebcb9c`, "Add reconnect supervisor + re-entry leak fix
to monitor") added a call to `self._teardown_prior_monitoring()` at the start
of `MiniMonitorApp._start_monitoring()` (`.aitask-scripts/monitor/minimonitor_app.py:223`).
That helper reads `self._refresh_timer` and `self._monitor`, both initialized
in `__init__` at lines 142–143.

The Tier 1c test scaffold in `tests/test_multi_session_minimonitor.sh:120-132`
constructs the app via `MiniMonitorApp.__new__(MiniMonitorApp)`, manually sets
the attributes the *prior* `_start_monitoring` body referenced
(`_session`, `_capture_lines`, `_idle_threshold`, `_agent_prefixes`, `_tui_names`,
`_refresh_seconds`, `_compare_mode_default`, plus stub callables), then calls
`app._start_monitoring()`. Since `__init__` was bypassed, `_refresh_timer` and
`_monitor` are never set — and t733's new teardown call now crashes on first
attribute access.

The production code is correct: `__init__` always runs before `on_mount` →
`_start_monitoring`. Only the test scaffold needs catch-up. This is the same
"scaffold catches up to production" pattern as the recent t732_5 commit
(`312fe99a`, "Restore aitask_path/python_resolve copies in 4 test scaffolds").

## Fix

Add two missing initializer assignments to the Tier 1c scaffold in
`tests/test_multi_session_minimonitor.sh`, mirroring `__init__`'s defaults
at `minimonitor_app.py:142-143`:

```python
app._refresh_timer = None
app._monitor = None
```

Insert after `app._compare_mode_default = "stripped"` (current line 127), before
the stub-callable block. Keeps the scaffold's "set what the method needs"
discipline — no defensive `getattr` in production code.

**Why not make `_teardown_prior_monitoring` defensive (`getattr(self, "_refresh_timer", None)`)?**
The contract is "instance has run `__init__`". Production has no path that
violates this contract. Adding `getattr` muddles the contract and accumulates
defensive code purely to accommodate a test scaffold pattern. The scaffold is
the right place to fix.

**Other Tier scaffolds (1b, 1d, 1e, 1f) reviewed:** none call `_start_monitoring`,
so none are affected.

## Critical Files

- `tests/test_multi_session_minimonitor.sh` — Tier 1c scaffold around line 120-132 (only edit)

## Reference

- `.aitask-scripts/monitor/minimonitor_app.py:142-143` — `__init__` defaults for
  `_refresh_timer` and `_monitor` (the values to mirror).
- `.aitask-scripts/monitor/minimonitor_app.py:194-219` — `_teardown_prior_monitoring`
  body, which reads both attributes.
- `.aitask-scripts/monitor/minimonitor_app.py:221-223` — `_start_monitoring`
  entry point that now calls the teardown helper.

## Verification

1. **Targeted test:**
   ```bash
   bash tests/test_multi_session_minimonitor.sh
   ```
   Expect: clean PASS summary, no AttributeError.

2. **Adjacent regression sweep:** the same sweep cited in t735 origin context.
   ```bash
   for t in tests/test_*tui*.sh tests/test_*monitor*.sh; do
       echo "=== $t ==="; bash "$t" 2>&1 | tail -3
   done
   ```
   Expect: no new failures introduced. `test_multi_session_monitor.sh` (the
   originally-cited-but-actually-passing test) remains 43/43.

3. **Sanity:** confirm `git diff` only touches
   `tests/test_multi_session_minimonitor.sh` and the addition is exactly 2
   `app._<attr> = None` lines mirroring `__init__`.

## Note on t735's task file

The original task file (`aitasks/t735_fix_multi_session_monitor_pane_aggregation.md`)
describes the wrong test. The Final Implementation Notes will record the
pivot: "no-repro on `test_multi_session_monitor.sh`; pivoted to fixing
`test_multi_session_minimonitor.sh` per user decision." The task filename will
remain as-is to preserve git history; the plan file (this doc) is the
authoritative record of what was actually done. Reference to Step 9
(Post-Implementation) for the cleanup, archival, and merge steps.
