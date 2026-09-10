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

## Implementation Notes

All steps landed as planned; no deviations.

- `.aitask-scripts/frozenagent/frozenagent_app.py` — added `import agent_frozen_ops`,
  the single `_settle_timeout_for(rec)` derivation site, the dispatch-time compute
  in `_start_restore`, and the `settle_timeout: float | None = None` parameter on
  `_poll_restore` (the constant `DISPATCH_GRACE + 30.0` is gone).
- `tests/test_frozenagent_app.py` — new `RestorePollDeadlineTests(_AppCase)` with
  all five planned tests, plus a local `_FakeTimer` and `from unittest.mock import patch`.
  `_project(grace)` builds the temp root; `_mount_on(root, **over)` rewrites the
  fixture record under it.

**Pre-fix control (run):** with only `frozenagent_app.py` stashed, 4 of the 5 new
tests fail — `40.0 not greater than 60.0` / `not greater than 90.0`, the
three-argument fallback reporting `restore still restoring after the grace — run
reconcile` at 41s, and the behavioural pin the same way. The fifth,
`test_the_default_grace_keeps_the_value_the_viewer_shipped`, passes pre-fix by
design: it is the compatibility pin.

**Results:** `test_frozenagent_app.py` 56 passed;
`test_frozenagent_restore_poll_characterization.py` 16 passed **and unedited**
(`git status` clean for that path); `test_frozen_restore_verdict.py` 26 passed;
`test_monitor_frozen_filter.py` 69 passed.

## Final Implementation Notes

- **Actual work done:** Exactly the approved plan. `_poll_restore`'s hardcoded
  `settle_timeout=DISPATCH_GRACE + 30.0` is replaced by a deadline derived from the
  polled record's own root through the shared `agent_frozen_ops.restore_settle_timeout()`
  (the helper t1705_7 added). One derivation site, `FrozenAgentApp._settle_timeout_for(rec)`;
  `_start_restore` computes it once at dispatch and binds it into the poll timer;
  `_poll_restore` takes it as `settle_timeout: float | None = None` and derives it
  itself when a caller supplies none. `tests/test_frozenagent_app.py` gained
  `RestorePollDeadlineTests` (5 tests) plus a local `_FakeTimer` and
  `from unittest.mock import patch`.
- **Deviations from plan:** None.
- **Issues encountered:** None in the change itself. The full Python suite ends
  `FAILED (failures=3)` out of 7307 — all three are **pre-existing** failures in
  `tests/test_concern_parser.py` (2) and `tests/test_prompt_detection.py` (1),
  already tracked by **t1763**. Proven unrelated: both modules fail identically with
  this task's two files stashed. A note was sent to t1763 reporting that its third
  listed failure (`tests/test_desync_state.py`) no longer reproduces, so its standing
  red is 3 failures across 2 modules, not 3.
- **Key decisions:**
  - *Compute once at dispatch, not per tick.* Mirrors the monitor twin
    (`monitor_shared._poll_frozen_outcome`) and avoids re-reading the project YAML at
    1 Hz. It is also more correct: `rec` is known non-None at dispatch, while
    mid-restore the record can be transiently unreadable — deriving then would fall
    back to the cwd and produce a different deadline for some ticks.
  - *`settle_timeout` defaults to `None`, not to a required parameter.* A required
    parameter would have forced an edit to the t1705_7 characterization control
    (`tests/test_frozenagent_restore_poll_characterization.py`), which calls
    `_poll_restore` with three positional arguments and must stay green **unedited**.
    Editing a control to accommodate the change it controls for weakens it. Both
    branches route through the single `_settle_timeout_for` derivation, so the two
    entry points cannot diverge.
  - *The fallback is tested at a non-default grace* (`test_the_three_argument_fallback_is_root_aware_too`).
    Raised in review of the plan: every other new test enters through `_start_restore`,
    so without this one a future change that left the fallback hardcoded at 40.0 — or
    reading the cwd instead of the record — would keep them all green.
  - *Pre-fix control run, not assumed.* With only `frozenagent_app.py` stashed, 4 of
    the 5 new tests fail (`40.0 not greater than 60.0` / `not greater than 90.0`; the
    fallback reporting `restore still restoring after the grace — run reconcile` at
    41s). The fifth, the 40.0 compatibility pin, passes pre-fix by design.
- **Upstream defects identified:** None

## Step 9 (Post-Implementation)

Cleanup, archival of `aitasks/t1766_*.md` + this plan, and the merge back to the
output branch follow the shared workflow's Step 9.
