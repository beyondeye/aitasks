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

## Final Implementation Notes

- **Actual work done:** Added two missing initializer assignments to the Tier 1c
  scaffold in `tests/test_multi_session_minimonitor.sh` (`app._refresh_timer = None`,
  `app._monitor = None`) so `_teardown_prior_monitoring` — newly invoked from
  `_start_monitoring` since t733 — sees both attributes. Also patched the Tier 1f
  scaffold: imported `TmuxControlState` and gave the `_monitor` SimpleNamespace a
  `control_state=lambda: TmuxControlState.STOPPED` shim so `_rebuild_session_bar`
  (which queries `self._monitor.control_state()` for the new control-channel
  badge added in t733) does not raise.

- **Deviations from plan:** Plan only enumerated the Tier 1c fix. After landing
  it, re-running the test surfaced a second t733-induced regression in Tier 1f
  (`_rebuild_session_bar` calling `self._monitor.control_state()`). Same root
  cause (scaffold predates t733's production additions), same class of fix
  (scaffold catches up). Both fixes shipped under this task per the original
  pivot mandate.

- **Issues encountered:** Tier 1c failure was the easy reveal. Tier 1f was
  masked by it — only became visible once Tier 1c stopped raising. No other
  Tier scaffolds (1b, 1d, 1e) hit a t733-related path.

- **Key decisions:** Kept the fixes scoped to test scaffolds rather than adding
  defensive `getattr` to production. Production has no path that violates the
  "instance has run `__init__`" contract, and `_monitor` is a real `TmuxMonitor`
  in production (always has `control_state`). Defensive code in production
  would muddle the contract just to accommodate `__new__` test scaffolds.

- **Upstream defects identified:**
  - `.aitask-scripts/monitor/minimonitor_app.py:194-219` — `_teardown_prior_monitoring`
    references `self._refresh_timer` / `self._monitor` without initializer
    fallback. Production-safe (always called post-`__init__`), but t733 added
    this helper and its new test-impact wasn't covered. Already fixed at the
    scaffold layer here; recording for sibling-task awareness.
  - `.aitask-scripts/monitor/minimonitor_app.py:386` — `_rebuild_session_bar`
    similarly assumes `self._monitor` exposes `control_state()`. Fine in
    production; surfaced through the scaffold.
  - **Original t735 premise (`test_multi_session_monitor.sh` 6/43 failing) does
    not reproduce.** Verified at HEAD (f55d0dcb) and at cited baseline
    (32957a2d) — 43/43 passes in both. No upstream defect under the
    originally-named test; t735's diagnostic context is incorrect (likely
    transient environmental state when filed).

- **Notes for sibling tasks:** This is not a child task. But the broader
  pattern — t733's monitor changes shipped with two test-scaffold drift bugs
  (Tier 1c + Tier 1f in `test_multi_session_minimonitor.sh`) — suggests the
  t733 plan should have run the full `tests/test_*monitor*.sh` sweep before
  archival. No follow-up task created here; the regression is now closed.

## Verification (executed)

- `bash tests/test_multi_session_minimonitor.sh` → **24/24 passed, 0 failed**
- `bash tests/test_multi_session_monitor.sh` → **43/43 passed, 0 failed** (unchanged)
- `bash tests/test_tui_switcher_multi_session.sh` → **45/45 passed**
- `bash tests/test_setup_git_tui.sh` → **ALL TESTS PASSED**
- `git diff --stat`: 1 file changed, 7 insertions, 1 deletion (only `tests/test_multi_session_minimonitor.sh`).
