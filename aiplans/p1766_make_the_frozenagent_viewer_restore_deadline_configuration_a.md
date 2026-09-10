---
Task: t1766_make_the_frozenagent_viewer_restore_deadline_configuration_a.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1766 — Make the frozenagent viewer's restore deadline configuration-aware

## Context

`FrozenAgentApp._poll_restore` (`.aitask-scripts/frozenagent/frozenagent_app.py:877`)
hands `agent_sessions.restore_verdict` a hardcoded `settle_timeout=DISPATCH_GRACE + 30.0`
(40s), ignoring the target project's `frozen.restore_ack_grace`.

`agent_restore` gives a `restoring` record up to that grace to be acknowledged by
its replacement agent's SessionStart hook before it may be liveness-confirmed
instead. On a project whose grace is above ~30s the viewer therefore warns and
stops its timer while the restore is still legitimately in flight: **every**
successful restore is reported as a stall, and the eventual success is never
shown.

This is the twin of the defect fixed in `monitor_shared._poll_frozen_outcome`
under t1705_7 (`.aitask-scripts/monitor/monitor_shared.py:1019-1029`). That fix
added the shared helper this one reuses:

```python
agent_frozen_ops.restore_settle_timeout(root, *, dispatch_grace)
# → dispatch_grace + restore_ack_grace(root) + RESTORE_SETTLE_SLACK
```

pinned by `tests/test_frozen_restore_verdict.py::SettleTimeoutTests`. At the
DEFAULT grace it returns exactly the 40.0 the viewer hardcodes, so the change is
behaviour-identical under default config — which is why
`tests/test_frozenagent_restore_poll_characterization.py` (the t1705_7 control)
must stay green across it, **unedited**.

Outcome: the viewer's deadline is derived from the **polled record's own root**
(not the app's cwd — a stand-in pane's cwd is wherever the frozen agent started),
and always outlasts the coordinator's ack window.

## Implementation

### 1. `.aitask-scripts/frozenagent/frozenagent_app.py`

**a. Import the shared ops module** — next to the existing `import agent_sessions`
(line 68), mirroring `monitor_shared.py:31`:

```python
import agent_frozen_ops  # noqa: E402
```

**b. Add one derivation site** — a small method on `FrozenAgentApp`, placed just
above `_poll_restore` in the "coordinator actions" section:

```python
    def _settle_timeout_for(self, rec) -> float:
        """How long this viewer may watch a dispatched restore before crying stall.

        The deadline is the COORDINATOR's, not ours: `agent_restore` gives a
        `restoring` record up to the project's `frozen.restore_ack_grace` to be
        acknowledged by its replacement agent's SessionStart hook before it may
        be liveness-confirmed instead. A fixed 40s stops the timer mid-restore on
        any project that raised that grace, turning every successful restore into
        a spurious stall report. Read from the RECORD's root: this app's cwd is
        wherever the frozen agent's pane happened to start.
        """
        return agent_frozen_ops.restore_settle_timeout(
            (rec.root if rec is not None else "") or None,
            dispatch_grace=DISPATCH_GRACE,
        )
```

**c. Derive once at dispatch** in `_start_restore` (after the existing `rec is None`
/ `repick` guards, where `rec` is known non-None), and bind it into the timer
lambda — the same compute-once shape as the monitor twin, so the project config
is read once per operation rather than once per 1 Hz tick:

```python
        settle_timeout = self._settle_timeout_for(rec)
        ...
        self._op_timers[rid] = self.set_interval(
            POLL_INTERVAL,
            lambda: self._poll_restore(rid, snapshot, elapsed, settle_timeout),
        )
```

**d. Take the deadline as a parameter** in `_poll_restore`, replacing the constant:

```python
    def _poll_restore(self, rid: str, snapshot: tuple[int, str],
                      elapsed: dict, settle_timeout: float | None = None) -> None:
        elapsed["t"] += POLL_INTERVAL
        self._view.invalidate()
        prev_attempts, _prev_nonce = snapshot
        rec = self._view.by_id(rid)
        if settle_timeout is None:
            # A caller that dispatched nothing still gets a config-derived
            # deadline rather than a constant — never the 40s this fixed.
            settle_timeout = self._settle_timeout_for(rec)
        done, note, warn = agent_sessions.restore_verdict(
            rec, prev_attempts, elapsed["t"],
            dispatch_grace=DISPATCH_GRACE,
            settle_timeout=settle_timeout,
        )
        if done:
            self._finish(rid, note, warn=warn)
```

The `None` default is what keeps the t1705_7 characterization control green with
**no edit at all** (it calls `_poll_restore` with three positional args), and it
keeps the "never a constant" property for every caller. Both branches route
through the single `_settle_timeout_for` derivation.

`_poll_drop` is untouched: `drop_grace` is the coordinator's drop wait, unrelated
to the ack grace.

### 2. `tests/test_frozenagent_app.py` — new `RestorePollDeadlineTests(_AppCase)`

Mirrors `tests/test_monitor_frozen_filter.py::RestorePollDeadlineTests`
(lines 1247-1330): drive the **real** production path — press `R`, capture the
timer callback, run it — and spy on the `settle_timeout` the poll hands the
verdict. Needs `from unittest.mock import patch` and a local
`class _FakeTimer: def stop(self): pass`.

Helper:

```python
    async def _timeouts(self, root: str) -> list[float]:
        """Every `settle_timeout` the real dispatch → tick path hands the verdict."""
        ansi, txt = self.fx.capture(self.RECORD_ID)
        self.fx.write([_record(self.RECORD_ID, root=root,
                               capture_ansi=ansi, capture_txt=txt)])
        seen: list[float] = []

        def spy(rec, prev, elapsed, *, dispatch_grace, settle_timeout):
            seen.append(settle_timeout)
            return False, "", False

        app = self.make_app()
        async with app.run_test(size=(80, 20)) as pilot:
            ticks: list = []
            app.set_interval = lambda interval, fn: ticks.append(fn) or _FakeTimer()
            await pilot.press("R")
            await pilot.pause()
            # `agent_sessions` is the shared module object — scoped patch only.
            with patch.object(self.app_mod.agent_sessions, "restore_verdict", spy):
                ticks[0]()
        return seen
```

Tests (`_project(grace)` writes `aitasks/metadata/project_config.yaml` with
`frozen:\n  restore_ack_grace: <n>\n` into a `tempfile.TemporaryDirectory`):

1. `test_the_deadline_follows_the_projects_configured_grace` — grace 60 →
   `seen[0] > 60.0` (the defect: a 40s watcher on a 60s grace calls every
   successful restore a stall). **This is the pre-fix control** — it fails at
   40.0 against unfixed code.
2. `test_the_default_grace_keeps_the_value_the_viewer_shipped` — root with no
   config → `seen[0] == 40.0`. Compatibility pin; the reason the characterization
   control stays green.
3. `test_the_grace_is_read_from_the_records_root_not_the_cwd` — record root is a
   temp project with grace 90 while the process cwd is this repo (default 20) →
   `seen[0] > 90.0`.
4. `test_the_three_argument_fallback_is_root_aware_too` — **covers the
   `settle_timeout=None` path directly**, which no other test reaches at a
   non-default grace: every test above enters through `_start_restore`, so a
   future change that left the fallback hardcoded at 40.0 (or reading the cwd
   instead of the record) would keep them all green. Mount on a record rooted in
   a grace-60 project, press `R` (so the rid is pending and the header reads
   `dispatching…`), write the record as `state="restoring", restore_attempts=1,
   op_nonce="bbbbbbbb"`, then call `_poll_restore` with **three positional
   arguments only** — the pre-fix signature the characterization control uses:
   - `app._poll_restore(self.RECORD_ID, (0, ""), {"t": 40.0})` → elapsed becomes
     41.0, past the old constant but inside the derived 80.0: still pending,
     header still `dispatching…`, no verdict.
   - `app._poll_restore(self.RECORD_ID, (0, ""), {"t": 80.0})` → elapsed 81.0,
     past the derived deadline: finishes with the stall note (`reconcile`), so
     the fallback is pinned to *the derived* deadline rather than to "no
     deadline". Also a pre-fix control: unfixed, the first call times out at 41.
5. `test_a_restore_inside_the_configured_grace_is_not_reported_as_a_stall` — the
   end-to-end behavioural pin, real verdict, no spy: mount on a `frozen`
   attempts-0 record whose root has grace 60, press `R`, then write the record as
   `state="restoring", restore_attempts=1, op_nonce="bbbbbbbb"` (the shape
   `test_a_timeout_never_reads_as_success` uses) and call the captured tick 41
   times → the record is still in `app._pending` and no note mentions
   `reconcile`. Then keep ticking past 81 → it finishes with the stall note, so
   the test proves a deadline still exists rather than that it was removed.

## Verification

```bash
# The changed module and its t1705_7 control (must be green, control unedited)
python3 tests/test_frozenagent_app.py
python3 tests/test_frozenagent_restore_poll_characterization.py

# The shared helper's own contract and the twin fix, unaffected
python3 tests/test_frozen_restore_verdict.py
python3 tests/test_monitor_frozen_filter.py

# Pre-fix control: revert ONLY frozenagent_app.py and confirm the new tests fail
git stash push .aitask-scripts/frozenagent/frozenagent_app.py
python3 tests/test_frozenagent_app.py   # RestorePollDeadlineTests must FAIL at 40.0
                                        # (both the dispatch path and the
                                        #  three-argument fallback test)
git stash pop

# Whole Python suite (read the LAST line only; piping discards the status)
bash tests/run_all_python_tests.sh
```

## Risk

### Code-health risk: low
- The optional `settle_timeout=None` parameter adds a second entry into the
  derivation (dispatch-time vs. poll-time). Both funnel through the single
  `_settle_timeout_for` method, so the value can never diverge; the alternative
  (a required parameter) would force an edit to the t1705_7 characterization
  control, which is worse. · severity: low · → mitigation: already inline — test 4
  exercises the fallback directly at a non-default grace, so it cannot silently
  regress to a constant or to a cwd-derived deadline while the dispatch path
  stays green
- Behaviour change at non-default config only; the default-config path is pinned
  by two independent tests (the untouched characterization control and the new
  40.0 compatibility pin). · severity: low · → mitigation: already inline —
  test 2 above, plus the pre-fix control in Verification

### Goal-achievement risk: low
- None identified. The task names the exact defect, the exact shared helper, and
  the control that must stay green; the fix is a three-line rewire of one call
  site with a test that fails against unfixed code.

## Step 9 (Post-Implementation)

Cleanup, archival of `aitasks/t1766_*.md` + this plan, and the merge back to the
output branch follow the shared workflow's Step 9.
