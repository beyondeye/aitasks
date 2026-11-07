---
Task: t2037_3_monitor_minimonitor_subscribe.md
Parent Task: aitasks/t2037_python_monitor_status_server.md
Sibling Tasks: aitasks/t2037/t2037_4_applink_subscribe_status_server.md
Archived Sibling Plans: aiplans/archived/p2037/p2037_*_*.md
Base branch: main
Output branch: main
---

# t2037_3 — `ait monitor` and `ait minimonitor` subscribe through `MonitorClient`

## Context

t2037_1 shipped the shared status server (`monitor/status_server.py`), and
t2037_2 shipped `MonitorClient` (`monitor/status_client.py`). That client wraps
the app's own `TmuxMonitor` and serves the read surface from the subscription
(server mode), from the local instance (fallback), or from a recording (replay).
No app constructs it yet, so every monitor and minimonitor still runs its own
scan. t2034_1 measured that the tmux server's cost is dominated by these
duplicated scans: about 42 scanners making about 490 `capture-pane` calls per
second.

This task swaps the two apps onto the client. In server mode one producer scans
for every client. The apps keep all actions, raw-tail captures and the switcher
local, and fall back to today's in-process code whenever the server is
unreachable.

Advisory inputs (inbox notes, acknowledged): t2037_2's wiring checklist (wrap
the local instance, pins via `set_capture_pins`, `request_refresh` at keypress
sites, `cycle_compare_mode_async`, CLI overrides are not honoured by the server,
the surface test) and t2183's note (the minimonitor diffs rendered card text, so
it needs no delta plumbing; keep its list block after the snapshot assignment).

## Design decisions

- **One construction seam**: `build_monitor_client(local, *, kind, own_pane, session, project_root, pins, enabled, log)`
  in `monitor_shared.py`, returning a `MonitorClient`. Both apps call it right
  after building the local `TmuxMonitor`, which is built exactly as today. It is
  also the single place tests patch.
- **CLI overrides keep the app in-process.** The server applies each session's
  `project_config.yaml` and cannot honour `--lines` or `--interval`. So when
  `main()` sees an explicit override it passes `monitor_server=False` to the app.
  The client then stays permanently in fallback, never calls `ensure`, and the
  app logs one line saying why. `AITASKS_MONITOR_SERVER=0` keeps working as the
  user-wide opt-out (the client reads it when `enabled` is `None`).
- **Scan only on demand, never on the App message pump.**
  `_refresh_data(self, *, scan: bool = True)`.
  - The interval timer and the first refresh run with `scan=False`: they only
    read the subscription, so N clients never cause N scans.
  - Every `call_later(self._refresh_data)` site is user-driven (refresh key,
    kill, pick, mark, `M`, the filter re-tick, `d`'s follow-up, and so on).
    Those sites keep their exact text and get the default `scan=True`.
  - **Why the wait cannot stay inline.** `call_later` awaits its callback
    *inline on the App pump*, the same queue that dispatches keys (t1598; see
    the comment in `minimonitor_app._start_monitoring`). Awaiting
    `request_refresh()` there would let a connected but stalled server block
    input for the client's 10 s request timeout. So on the `scan=True` route,
    when the monitor is a `MonitorClient` not in `FALLBACK`, `_refresh_data`
    awaits nothing. It calls `self._dispatch_scan_refresh()` and returns.
  - **`_dispatch_scan_refresh()`** is in `monitor_shared` and shared by both
    apps.
    - It coalesces: if a scan worker is already running, it sets
      `_scan_again = True` and returns.
    - Otherwise it runs a worker with
      `run_worker(self._scan_refresh_worker(), group="scan-refresh", exclusive=False, exit_on_error=False)`
      (`asyncio.create_task`, so it is off every pump).
  - **The worker runs ONE guarded refresh round, in this order: publish
    first, then flush the pins, then request the scan, then read.** The order
    is load-bearing. The minimonitor's `_capture_pins()` depends on this
    round's identity check (`_update_own_window_info`), and t2034_2 requires
    that the followed parked agent is captured live and that an unconfirmed
    identity fails safe (`CAPTURE_PIN_ALL`). A scan requested before the new
    pins reach the server runs under the old pin. It then produces a parked
    placeholder for a newly followed parked window, and
    `client_view_snapshots` cannot turn a placeholder back into live content.
    - `_refresh_data` gains a private kwarg, `_request_scan: bool = False`. The
      worker calls `await self._refresh_data(scan=False, _request_scan=True)`.
      That is a normal guarded round (the `_refresh_inflight` guard, the
      `finally` and the early returns are unchanged). After the
      capture-policy preparation, which is the existing pre-capture block,
      and before the capture, it does
      `await monitor.flush_pins(); await monitor.request_refresh()`.
      - The pre-capture block is: mapping → `_set_session_root_map` → marks →
        (minimonitor) identity reset and `_update_own_window_info` →
        `_publish_parked_agents()`, which also calls `set_capture_pins`.
      - Then the capture reads the state the request produced. Every wait runs
        in the worker task, never on the pump.
    - **`MonitorClient.flush_pins()`** is new and additive in
      `status_client.py`. `set_capture_pins` keeps its fire-and-forget send but
      retains that task as `self._pins_send`. `flush_pins()` awaits it. The
      wait is shielded, bounded by `request_timeout`, swallows failures like
      `_quiet_request`, and is a no-op when no send is pending or the client
      is not subscribed.
      - The server applies `set_pins` before answering `result`, and handles
        one connection's requests in order. Verified in the code:
        - `_Connection`'s read loop awaits `_handle(msg)` for each line in
          turn (`status_server.py` ~L630–640);
        - `_set_pins` assigns `conn.pins` and calls `_publish_skip_set()` under
          the producer lock, and only then calls `send_result` (~L1072–1076);
        - a full `refresh` runs `_tick_locked`, and `_publish_skip_set`'s own
          docstring says it runs before every capture route. So once `flush_pins()` returns,
        the next `refresh` scans under the new pins, and its skip set is
        computed from them.
      - If identity is unconfirmed, `CAPTURE_PIN_ALL` is what gets flushed, so
        the requested scan is fail-safe.
    - **Coalescing.** `_dispatch_scan_refresh()` sets `_scan_again` when a scan
      worker is running. The worker repeats its round while `_scan_again` was
      set during the previous round.
    - **Teardown.** After each await the worker checks
      `self._monitor is monitor` and ends the round early if the monitor was
      replaced. Textual cancels the worker at unmount.
  - **Guard turn-away.** A worker round turned away by `_refresh_inflight` (a
    timer tick is mid-flight) sets `_scan_rerun = True`. That tick's `finally`
    (`_maybe_rerun_refresh()`) then dispatches the scan worker once more. It
    does not dispatch a plain re-tick, because the user action still needs its
    scan. That is one re-dispatch per turn-away, never a loop, and it runs
    beside the minimonitor's existing `_maybe_retick_for_filter`.
  - **In `FALLBACK`, and with any non-client fake**, `scan=True` runs inline
    exactly as today. `request_refresh` would be a no-op there, and nothing new
    waits on the pump.
  - The client check is `isinstance(self._monitor, MonitorClient)`, with
    `MonitorClient` imported from `monitor.status_client` (the package path
    that `monitor_shared` and the tests also use, so there is one class object).
    This way test fakes
    (SimpleNamespace or MagicMock) never meet an un-awaitable attribute. In
    fallback the call returns `None` immediately.
  - The timer is wired through a new method, `_tick_refresh()`, which calls
    `await self._refresh_data(scan=False)`, because `set_interval` passes no
    kwargs.
- **Pins.** `AgentMarksMixin._publish_parked_agents` also calls
  `set_capture_pins(self._capture_pins())`, probed with `getattr` like
  `set_parked_agents`. The initial `pins=` passed to the client is
  `self._capture_pins()` at construction: `CAPTURE_PIN_ALL` for a minimonitor
  whose identity is not yet confirmed (fail-safe), `frozenset()` for the monitor.
- **Compare mode (`d`).** Both `action_cycle_compare_mode` handlers keep their
  validation, then branch:
  - **Client present** (`getattr(monitor, "cycle_compare_mode_async", None)`):
    `run_worker(self._cycle_compare_mode_async(pane_id), group="compare-mode", exclusive=False)`.
    The worker awaits the authoritative `(mode, following_default)`, notifies,
    and then calls `self._dispatch_scan_refresh()` directly. It does not use
    `call_later`, which would put a refresh back on the pump.
  - **Failure** (`RequestFailed`, `ConnectionLost`, `asyncio.TimeoutError`):
    notify a warning, "Idle detect: request failed".
  - **No client** (sync fakes): today's code path, unchanged.
  - It is not awaited on the message pump, because a hung server would freeze
    input for the request timeout.
- **Lifecycle.** Unchanged call shape. The existing
  `_connect_control_client` worker calls `start_control_client()`, which is the
  client's `start()`. `on_unmount` and `_teardown_prior_monitoring` call
  `close_control_client()`, which is `close()`. The session-rename re-entry in
  the monitor builds a fresh client, and the old one closes in the teardown
  worker.
- **Unchanged, client-side** (all already in `GATEWAY_NAMES`): the review loop's
  raw-tail captures (`capture_pane_content_async`), send-keys, kill, pick,
  shadow spawn, `tmux_run*` and the switcher. The fast preview
  (`capture_pane_classified_async`) and `refresh_shadow_snapshot` are served by
  the client: `refresh{panes|shadows}` in server mode, local in fallback.
- **Projection** stays in `_project_snapshots`, which already wraps every write
  (t2034_2).
- **Not in scope.** Render on push via `add_update_listener` is optional. It is
  proposed below as an "after" follow-up, because the timer read adds at most
  one server tick of staleness.

## Implementation

0. **`status_client.py`, additive.**
   - `set_capture_pins` stores its spawned send task as `self._pins_send`.
   - New `async def flush_pins(self) -> None` awaits it as described in the
     design.
   - Add the name to `READ_SURFACE_NAMES`. Do this only if the surface test's
     own definition requires listed names; otherwise a class member suffices.
     Check `tests/test_monitor_client_surface.py`.
   - Add cases to `tests/test_monitor_status_client.py`. Both are
     deterministic.
     - **Ordering, on `ScriptedServer`.** Hold back the `result` for
       `set_pins`, then run `set_capture_pins(new)`, then
       `flush_pins()` followed by `request_refresh()` in one task. Assert the
       server has received no `refresh` while the `set_pins` result is held.
       After the result is released, the `refresh` arrives. If `set_pins` is
       never answered, `flush_pins` returns within `request_timeout` and does
       not raise.
     - **Effect, on the real-server fixture.** Run
       `set_capture_pins(new)` → `flush_pins()` → `request_refresh()`. The
       `("skip", …)` entry in `FakeProducer.calls` right before that refresh's
       `"capture"` equals `parked_capture_skip(global, [new])`.
   - Add one sentence to the spec's "Python client" section.
   - Before editing, check the file is clean: `git diff --quiet HEAD`.

1. **`monitor_shared.py`**
   - Import `MonitorClient` with the same dual import used for the other
     `monitor.*` imports in this file. Check the file's existing pattern first.
   - Add `build_monitor_client(...)`. The docstring states the `enabled` rule:
     `None` reads `AITASKS_MONITOR_SERVER`, and `False` means permanent
     in-process.
   - Extend `_publish_parked_agents` with the `set_capture_pins` probe, in the
     same `try/except` as the parked setter (advisory data never breaks a tick).
   - Add to `AgentMarksMixin`:
     - `_wants_offpump_scan()`: client and not `FALLBACK`;
     - `_dispatch_scan_refresh()` and `_scan_refresh_worker()`;
     - `_maybe_rerun_refresh()`, called from each app's `_refresh_data`
       `finally`;
     - the class defaults `_scan_inflight = False`, `_scan_again = False` and
       `_refresh_rerun = False`, so test doubles built without `__init__` still
       work.
2. **`monitor_app.py`**
   - `__init__` gains `monitor_server: bool | None = None`, stored as
     `self._monitor_server`.
   - In `_start_monitoring`, `self._monitor = build_monitor_client(TmuxMonitor(...as today...), kind="monitor", own_pane=self._own_pane_id, session=self._session or "", project_root=self._project_root, pins=self._capture_pins(), enabled=self._monitor_server, log=self.log)`.
     The first refresh worker calls `self._refresh_data(scan=False)`. The timer
     uses `self._tick_refresh`.
   - `_refresh_data(self, *, scan=True, _request_scan=False)`.
     - First, before the guard:
       `if scan and self._wants_offpump_scan(): self._dispatch_scan_refresh(); return`.
       It awaits nothing on this route.
     - The guard's early return sets `_scan_rerun` when `_request_scan`.
     - Right after `self._publish_parked_agents()` and before
       `capture_all_classified_async()`:
       `if _request_scan: await self._monitor.flush_pins(); await self._monitor.request_refresh()`,
       followed by the `_monitor` identity check.
     - The `finally` calls `self._maybe_rerun_refresh()`.
   - `action_cycle_compare_mode`: the async branch described above, plus a new
     `_cycle_compare_mode_async(pane_id)` coroutine.
   - `main()`: `monitor_server=False if (args.lines is not None or args.interval is not None) else None`.
   - Update the `self._monitor: TmuxMonitor | None` annotation to
     `TmuxMonitor | MonitorClient | None`, with a comment.
3. **`minimonitor_app.py`**: the same changes.
   - `kind="minimonitor"`.
   - `own_pane=self._own_pane_id`, or `os.environ.get("TMUX_PANE")` if the
     attribute differs. Check what `_project_snapshots` reads.
   - `main()` handles `--interval` only, since the minimonitor has no `--lines`.
   - The same off-pump dispatch at the top of `_refresh_data` and the same
     turn-away flag.
   - The `flush_pins` + `request_refresh` hook goes after the identity
     confirmation and `_publish_parked_agents()`, and before
     `capture_all_async()`.
   - `_maybe_rerun_refresh()` goes in the `finally` next to
     `_maybe_retick_for_filter()`.
   - Keep the t2183 list block exactly after the snapshot assignment.
   - The `_maybe_retick_for_filter` `call_later` stays `scan=True`. It is a
     keypress follow-up, and one extra scan is harmless.
4. **`tests/test_minimonitor_startup_input_latency.py`**: it swaps
   `mm.TmuxMonitor` for a blocking fake and calls the real `_start_monitoring`.
   That is the only unit test that reaches construction, which a grep of
   `_start_monitoring()` call sites confirmed. Wrap its `_start_monitoring`
   calls in `mock.patch.dict(os.environ, {"AITASKS_MONITOR_SERVER": "0"})` so it
   never runs `ensure_server` against whatever tmux the developer runs. Then
   assert, inside the test, that `app._monitor` is a `MonitorClient` in
   `FALLBACK` delegating to the fake. That keeps the test's dispatch assertion
   meaningful and also pins the wrap. Check the test's references to
   `_refresh_data` and the first-refresh worker name (`first_refresh`); the
   name stays.

   **New test in the same file: `test_a_keypress_is_dispatched_while_a_server_refresh_request_is_stalled`.**
   - Mount the minimonitor as the sibling tests do. Set `app._monitor` to a
     `MonitorClient` in server mode on a `cx.ScriptedServer`. The script
     answers `hello` / `subscribe` with a snapshot, answers any `set_pins` with
     a `result` (the worker round flushes pins first), then **never answers
     `refresh`**. The test records the `refresh` it received so it can await
     that point.
   - Trigger a keypress-driven `call_later(self._refresh_data)` through a real
     binding, for example the multi-session toggle; confirm its key while
     implementing. Wait until the server has received the `refresh`.
   - Then `_press_and_observe(app, "j", handled)` must see the `j` dispatched
     while the request is still pending.
   - Afterwards, have the script answer the `refresh` (a `result` after a
     delta). Assert that the worker ran `_refresh_data(scan=False)`:
     `_refresh_inflight` is cleared, and the snapshot reflects the delta.
   - Also assert that `_scan_inflight` is cleared afterwards.
   - **Positive control (run by hand, recorded in the docstring table):**
     replace the off-pump dispatch with an inline
     `await self._monitor.request_refresh()`. The test must then fail by turn
     exhaustion.
   - A second case covers `d`. The compare-mode worker's follow-up refresh is
     also off-pump: `j` is dispatched while that follow-up's `refresh` is
     stalled.
5. **Spec, `aidocs/framework/monitor_status_protocol.md`, "Python client"**: add
   a short "Consumers" subsection in current-state prose:
   - monitor and minimonitor subscribe through `build_monitor_client`;
   - the timer only reads the subscription. A user action calls
     `request_refresh` from a coalesced worker, never on the App message
     pump;
   - pins are published every tick;
   - `d` uses the async cycle;
   - explicit `--lines` / `--interval` keep the app in-process;
   - the opt-out is `AITASKS_MONITOR_SERVER=0`.
6. **Website, `website/content/docs/tuis/monitor/reference.md`**:
   - In "Environment Variables", add an `AITASKS_MONITOR_SERVER` row:
     `0` makes monitor and minimonitor scan in-process instead of sharing the
     per-tmux-server status server.
   - Add one line under "Command-line Options": passing `--interval` or
     `--lines` runs that instance in-process.
   - Add the same env-var mention to `website/content/docs/tuis/minimonitor/_index.md`
     only if it has a reference table. Otherwise the monitor page covers both.
   - Then run `cd website && python3 check_links.py --build`.

### Tests — new `tests/test_monitor_apps_subscribe.py` (unittest)

It reuses the client fixtures through module aliases only
(`import test_monitor_status_client as cx`, `import test_monitor_status_server as fx`),
so pytest collects no foreign `TestCase` classes. It reaches no real tmux: the
ensure is injected through a patched `build_monitor_client`, or with
`enabled=False`.

- **Wiring, both apps.** Patch `TmuxMonitor` in the app module with a recording
  fake and patch `ensure`, then run `_start_monitoring()`.
  - `app._monitor` is a `MonitorClient` with the right `kind`, `own_pane`,
    `session`, `project_root` and initial pins: `CAPTURE_PIN_ALL` for an
    unconfirmed minimonitor, empty for the monitor.
  - With `monitor_server=False`, the mode is `FALLBACK` and `ensure` was never
    called.
  - `main()` override mapping: with `MonitorApp` / `MiniMonitorApp` patched to
    capture kwargs and `app.run` stubbed, `--lines 50` / `--interval 1` →
    `monitor_server=False`, and no flags → `None`.
- **Both modes, same view.** The monitor and the minimonitor each run inside
  `run_test`, with TMUX scrubbed as the sibling tests do. `app._monitor` is
  either:
  - (a) a server-mode client on a real `StatusServer` over `fx.FakeProducer`
    (the `ClientCase.real_server` pattern), or
  - (b) `MonitorClient(cx.FakeLocal-equivalent, enabled=False)` producing the
    same snapshots.

  After `await app._refresh_data(scan=False)`, both legs give the same
  `app._snapshots` keys and categories, and the same rendered list card ids.
  This is the "both modes" leg for the shared refresh path. Existing app tests
  inject their own fakes directly and stay as they are.
- **Scan policy.** With a server-mode client whose `request_refresh` is
  wrapped:
  - `_refresh_data()` returns without awaiting the request. Exactly one guarded
    `scan-refresh` worker round follows, and its recorded call order is:
    mapping, `_publish_parked_agents` (`set_parked_agents`,
    `set_capture_pins`), `flush_pins`, `request_refresh`, the capture.
  - `_refresh_data(scan=False)` and `_tick_refresh()` → no `request_refresh`.
  - Coalescing: three `_refresh_data()` calls while the first request is held
    → one worker, and exactly two `request_refresh` rounds (the first plus one
    `_scan_again` round), never three concurrent ones.
  - Guard turn-away: the worker's round starts while a timer tick holds
    `_refresh_inflight` → the scan worker is dispatched exactly once after that
    tick, and exactly one `request_refresh` results.
  - Teardown: `app._monitor` is replaced while the request is held → the worker
    stops without a refresh.
  - Fallback → `scan=True` runs inline as today: no worker, and the capture
    goes through the local instance.
  - A SimpleNamespace fake monitor → no `request_refresh` access, no worker,
    no error.
- **App timer: the real interval issues no full server scans.** This is the
  concern-2 check at unit level.
  - Mount the monitor and the minimonitor. Both run in one test with nested
    `run_test` contexts if Textual allows two apps on one loop. Otherwise they
    run sequentially against the same server, and the test docstring says so.
  - Each goes through its **real `_start_monitoring`**, with
    `build_monitor_client` patched to inject `ensure` = a real `StatusServer`
    over `fx.FakeProducer`. The server's tick interval is set long (≥ 60 s), so
    it makes no scans of its own during the test. The app is built with
    `refresh_seconds=0.05`.
  - After the first refresh and the initial subscribe have settled, record
    the baseline count of `fake.calls.count("capture")` (full scans). Then
    wait ≥ 5 intervals, which is witnessed by counting `_tick_refresh` calls
    (≥ 5 per app).
  - Assert the producer's full-scan count is unchanged.
  - Then press the refresh key once in one app → the count rises by exactly
    1. That shows the counter sees app-requested scans, and that a user action
      costs one scan.
  - **Positive control (by hand, recorded in the docstring):** wire the timer
    back to `self._refresh_data` (the default `scan=True`). The test must fail
    with a count that grows with the ticks.
- **Publish before scan: the followed identity moves to a parked window.**
  This is the round-3 regression check.
  - Mount a minimonitor whose `app._monitor` is a server-mode client over a
    real `StatusServer` with `fx.FakeProducer` and `fx.FakeMarks`. Window
    `agent-b` (pane `%2`) is parked in the marks. The local gateway's
    `tmux_run_async` is stubbed to answer `display-message` with the app's own
    window info.
  - Tick 1, via `_refresh_data(scan=False)`: the own window is `agent-a`.
  - Between ticks, the stub starts answering `agent-b`, and `fake.snaps` gets a
    fresh content marker for `%2`.
  - Then trigger a user refresh (`app._refresh_data()`, `scan=True`) and await
    the scan worker.
  - Assert:
    - the `("skip", …)` entry right before the requested scan's `"capture"`
      excludes `(session, "agent-b")`;
    - `app._snapshots["%2"]` is live (not `parked`) and carries the fresh
      marker;
    - `_find_own_agent_snapshot()` returns it.
  - **Fail-safe variant:** the identity query fails on the scan round
    (`rc != 0`). The skip set published before the requested scan is computed
    under `CAPTURE_PIN_ALL`, so it is empty.
  - **Positive control (by hand, recorded in the docstring):** move the
    `flush_pins` + `request_refresh` hook above the identity / publish block.
    The first assertion must then fail, with `agent-b` in the skip set and a
    parked placeholder for `%2`.
- **Pins.** A recording monitor exposing both setters: one
  `_publish_parked_agents()` passes the skip set to `set_parked_agents` and
  `_capture_pins()` to `set_capture_pins`. The minimonitor test is in two
  steps: unconfirmed → `CAPTURE_PIN_ALL`; then confirmed with name `agent-x` →
  `{(session, "agent-x")}`.
- **Compare mode.**
  - Client present, server mode: `d` sends `cycle_compare_mode` and notifies
    the server's answer, not the prediction. In the fixture the server replies
    a mode different from what the prediction would give, for example a pane
    already overridden server-side.
  - `RequestFailed` → warning notification.
  - The existing `test_minimonitor_other_section` sync fakes still take the
    sync path.
- **Surface.** Run `tests/test_monitor_client_surface.py` unchanged. It must
  stay green with the new attribute uses (`request_refresh`,
  `set_capture_pins`, `cycle_compare_mode_async` are class members).

### Live test — new `tests/test_monitor_apps_subscribe_live.py`

This test covers the task's "one capture pass per tick with N clients" and
"idle seconds agree" checks.

- **Setup.** It reuses `test_monitor_status_server_live.LiveCase`'s isolation:
  `-L ait_t2037_3_<pid>_<n>` plus scratch `TMUX_TMPDIR`, `XDG_RUNTIME_DIR`,
  `HOME` and `AITASKS_AGENT_MARKS_FILE`, applied with `patch.dict(os.environ)`.
  It skips only when tmux is missing.
- **Fixture.** One session in a temporary project, with 2 agent windows running
  printer loops.
- **Counting.** Build K=3 `build_monitor_client(TmuxMonitor(), kind="minimonitor", ...)`
  clients in-process. Wrap each local instance's tmux exec seam
  (`_tmux_async`, and the control backend's capture if one is ever started) to
  count `capture-pane`.
- **Server mode.** Over ≥3 server ticks:
  - the local instances perform 0 `capture-pane` calls;
  - all 3 clients see both agent panes;
  - for each pane, `get_last_change_wall()` is identical across the clients.
    That is the "idle seconds agree" check, read from the same server record.
- **Control.** The same with `AITASKS_MONITOR_SERVER=0`: each local instance
  makes ≥1 `capture-pane` per tick. This is the "before" count, and it proves
  the counter actually sees captures.
- **Cleanup.** Close the clients. Signal only the server pids from
  `server_info`, after the `/proc/<pid>/cmdline` scratch-path check. Kill the
  tmux server by its `-L` name only.
- If it flakes under the xdist lane, add it to the runner's serial carve-out and
  to the CLAUDE.md list in the same commit.
- **What it does not prove.** It does not count the shared producer's
  captures, because the server is another process, and it does not mount the
  apps. The unit-level "App timer" check above covers the apps' interval
  wiring against the producer's full-scan count. A live check of several
  mounted apps against a real server's scan count is the follow-up
  `apps_timer_shared_scan_live` (see `## Risk`).

### Post-phase (risk mitigations)

1. [suite_spawns_no_status_server] Run this after all tests pass.
   - Record
     `pgrep -af 'monitor/status_server.py'` (pid + cmdline) and
     `ls -la "$(~/.aitask/venv/bin/python -c 'import sys; sys.path[:0]=[".aitask-scripts",".aitask-scripts/lib"]; from monitor import status_server as s; print(s.runtime_dir())')"`
     into the scratchpad.
   - Run `bash tests/run_all_python_tests.sh` once, then record both again.
   - Pass when every pid present afterwards was either present before or has
     a scratch path (`/tmp`, `ait_t2037_*`) in its cmdline, and the runtime
     dir gained no new socket.
   - On failure, find the test that reached `ensure_server` (it booted an app
     with `TMUX` set). Fix it the way step 4 fixes the latency test, then
     re-run.
   - Record the before/after listings in Final Implementation Notes.

### Measurement — re-run t2034_1 (recorded, not a test)

- Re-run t2034_1's controlled server-cost comparison verbatim from its archived
  plan appendix (`aiplans/archived/p2034/p2034_1_measure_monitor_scan_cost.md`:
  `scale.sh servercost`, `cpurate.sh`, `tickcount.py`, `fakeagent.sh`). It runs
  on an isolated tmux server with N=12 fake agents and K ∈ {0, 1, 4} companion
  minimonitors.
- Do two runs: one with the new code (server mode), and one with
  `AITASKS_MONITOR_SERVER=0` (the in-process baseline, same host, same moment).
- Also record the status-server process's own CPU (`cpurate` on its pid) in
  server mode.
- Record the table (K → tmux server CPU %, status-server CPU %, per-minimonitor
  CPU %) and the difference in this plan's Final Implementation Notes, with the
  same caveats t2034_1 used (one host, one moment).
- Scripts live in the scratchpad. The scratch-socket guards from the appendix
  apply; never `kill-server` on `ait`.

## Verification

- `bash tests/run_all_python_tests.sh`: read the last line,
  `PYTHON SUITE: PASSED`.
- Targeted:
  `bash tests/run_all_python_tests.sh --test-dir <dir with the new/changed modules>`,
  or direct `python -m pytest tests/test_monitor_apps_subscribe.py tests/test_monitor_apps_subscribe_live.py tests/test_monitor_client_surface.py tests/test_minimonitor_startup_input_latency.py tests/test_minimonitor_other_section.py`.
- `cd website && python3 check_links.py --build`.
- The measurement table is in Final Implementation Notes.

## Risk

### Code-health risk: medium
- A server-refresh wait on the App message pump would block key input for the
  client's request timeout (`call_later` awaits inline, t1598). The design
  keeps every server wait in a `scan-refresh` worker. The extended
  input-dispatch test, with a stalled `refresh` and its positive control, pins
  this · severity: low (residual) · → mitigation: none (in-plan design + test)
- Requesting a scan before this round's identity check and pin publish would
  scan under a stale pin, and a newly followed parked agent would then be
  captured as a placeholder. The design keeps publish → `flush_pins` → request
  → read inside one guarded round, and the identity-moves-to-parked regression
  test, with its positive control, pins this · severity: low (residual) ·
  → mitigation: none (in-plan design + test)
- Both large TUIs change their refresh path: the `scan` kwarg, a new
  `_tick_refresh`, the scan worker with its coalescing and re-tick flags, and
  `d` moved to a worker. Starting either app now also
  spawns a background status-server process. This is bounded by fallback,
  `isinstance` gating and the unchanged `call_later` sites, but it is a
  load-bearing path · severity: medium · → mitigation: none (covered by the
  plan's scan-policy, wiring and both-modes tests)
- A unit test that boots an app through `_start_monitoring` with real `TMUX` in
  its environment would run `ensure_server` against the developer's live tmux
  and leave a server process scanning real sessions. Only one such test is known
  today (the startup-latency test, handled in step 4), but a future one would do
  the same silently · severity: low (residual: addressed by inline post-phase
  suite_spawns_no_status_server) · → mitigation: inline post-phase
  suite_spawns_no_status_server

### Goal-achievement risk: medium
- "Existing tests pass in both modes" is delivered as the full suite plus new
  seam-level both-modes tests. It is not delivered by re-wrapping the ~50
  existing app test files, which inject fakes below the seam. A behaviour
  difference that only shows through one of those files' specific fakes in
  server mode would not be caught · severity: medium · → mitigation: none
  (judgement recorded here)
- Checks below the app could pass even if the real app interval asked for a
  full server scan per client, which would quietly defeat the resource savings.
  The unit-level "App timer" test covers one mounted app (or two) against a
  producer's full-scan count. A live check of several mounted apps over real
  intervals against the real server's scan count is deferred as a follow-up ·
  severity: medium (residual: low after the unit-level app-timer check) ·
  → mitigation: apps_timer_shared_scan_live
- In server mode the timer reads the subscription, so a card can be up to one
  server tick staler than with an in-process scan. Render on push would close
  this, but it is out of scope · severity: low · → mitigation: monitor_render_on_push
- The re-measurement depends on re-running t2034_1's archived scripts on this
  host. The numbers are one host at one moment and are not a gate ·
  severity: low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: suite_spawns_no_status_server | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: unit test reaching ensure_server against the live tmux | desc: snapshot status-server pids/sockets around one full Python suite run and confirm none was left outside a scratch path
- timing: after | name: apps_timer_shared_scan_live | type: test | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: an app timer that requests a full server scan per client would pass every in-plan check below the app | desc: live test that mounts several real monitor/minimonitor apps on an isolated tmux server sharing one real status server and counts that server's full scans over several intervals (needs a scan counter the server exposes, e.g. in the welcome or a stats request), excluding startup and intentional refresh actions | created: t2223
- timing: after | name: monitor_render_on_push | type: enhancement | priority: low | effort: medium | inline_risk: medium | added_complexity: medium | addresses: up to one server tick of extra staleness in server mode | desc: re-render monitor/minimonitor on subscription updates via add_update_listener (Applied.changed) instead of only on the timer

## Step 9 (Post-Implementation)

This runs on the current branch (fast profile, no worktree). After the review,
commit the code with
`feature: Subscribe monitor and minimonitor to the status server (t2037_3)`
(only the named paths). Commit the plan via `aitask_task_commit.sh`, then run
the standard Step 9 archival of the child. t2037_4 (applink) stays pending, so
the parent is not archived and its cross-repo handoff note to aitasks_go#47 is
not due yet.

## Post-Review Changes

### Change Request 1 (2026-11-07)
- **Requested by user:** the full monitor's fast-preview callbacks
  (`_fast_preview_refresh` / `_fast_shadow_refresh`) now wait for a server
  `refresh` reply, but `_forward_key_to_tmux`, the scroll re-attach in
  `_record_scroll_for` and `action_scroll_preview_tail` still scheduled them with
  `call_later`, which runs them on the App message pump. A held reply stopped the
  next key from dispatching. The user confirmed this with a ScriptedServer probe.
  Move those waits off the pump, preserving the target and generation guards,
  and add full-monitor input-dispatch coverage.
- **Changes made:**
  - **`MonitorApp._dispatch_fast_refresh(refresh)`.** Under a client that is
    not in `FALLBACK`, it runs the same refresh method in a `fast-refresh`
    worker, coalesced per column: one round in flight, plus at most one more
    round for requests made after that round sent its request. In fallback, and
    with test doubles, it is the old `call_later`. The three `call_later`
    sites now call it.
  - **Guards preserved.** The pinned-pane, generation and focus-identity guards
    live inside the refresh methods, which are unchanged.
  - **Audit.** An `ast` audit of both apps found no other pump-reachable await
    on a server-backed client call. The 0.3 s zone timer runs in its own timer
    task. **Correction (Change Request 2):** this audit originally said the
    delayed refresh does too. It does not: Textual's `set_timer` wraps its
    callback in `call_next`, which runs it on the App pump; only `set_interval`
    passes its callback unwrapped.
  - **Tests.**
    - New `MonitorFastRefreshDispatchTests` in
      `tests/test_minimonitor_startup_input_latency.py`. Four cases cover:
      forwarding a key to the preview; forwarding a key to the shadow; `t`; and
      a scroll re-attach. Each held request is checked for the right
      `panes` / `shadows` target, then the next key must dispatch.
    - One more case tests coalescing.
    - **Positive controls.** A plain `call_later` dispatcher fails all four
      dispatch cases by turn exhaustion. An uncoalesced worker-per-call fails
      the coalescing case.
    - The shared fixture moved to `_ServerDispatchBase`.
  - The spec's "Consumers" bullet now names the fast-refresh path.
- **Files affected:** `.aitask-scripts/monitor/monitor_app.py`,
  `tests/test_minimonitor_startup_input_latency.py`,
  `aidocs/framework/monitor_status_protocol.md`.
- **Verification:**
  - all `tests/test_monitor*.py` / `tests/test_minimonitor*.py` non-live modules:
    1982 passed;
  - the three status-server live modules: 10 passed;
  - no status server was left behind.

### Change Request 2 (2026-11-07)
- **Requested by user:** Enter in the pane-list zone calls
  `_schedule_delayed_refresh()`, which is `set_timer(0.3, _fire_delayed_refresh)`.
  That callback awaited `_fast_preview_refresh()` directly. Installed Textual's
  `MessagePump.set_timer` wraps the callback in `partial(self.call_next, callback)`,
  which returns it to the App pump. The user confirmed with a probe that a held
  `refresh` reply blocked the next key. Route the callback through the
  dispatcher, add a stalled-reply test through the Enter / delayed-timer path,
  and correct the audit statement.
- **Changes made:**
  - **The fix.** `MonitorApp._fire_delayed_refresh` is now a sync callback that
    calls `self._dispatch_fast_refresh(self._fast_preview_refresh)`. It never
    awaits.
  - **Checked against the installed source.** `set_timer` wraps its callback in
    `call_next`; `set_interval` does not.
  - **Other `set_timer` callbacks.** The only others in either app are the two
    synchronous minimonitor scroll-lock releases.
  - **New test, `test_enter_in_the_pane_list_never_holds_input`.** It sends a
    real `enter` Key event through the driver. Once the server holds the
    delayed refresh's `refresh`, the next key must dispatch.
  - **Test fixture fix.** `_stalled_refresh_then_key` now clears the key spy
    after the held request arrives. A trigger that is itself a key would
    otherwise satisfy the dispatch observation on its own.
  - **Positive controls.**
    - Reverting `_fire_delayed_refresh` to `await self._fast_preview_refresh()`
      fails the Enter test by turn exhaustion.
    - The plain `call_later` dispatcher still fails all five dispatch cases.
  - The audit statement in Change Request 1 is corrected above.
- **Files affected:** `.aitask-scripts/monitor/monitor_app.py`,
  `tests/test_minimonitor_startup_input_latency.py`.

### Change Request 3 (2026-11-07)
- **Requested by user:** `_dispatch_fast_refresh` chose the route when it
  scheduled the refresh. In `FALLBACK` it queued `call_later(refresh)`, but the
  client can reconnect to `SERVER` before that callback runs. The queued
  refresh then waited for the server's reply on the App pump. The user
  confirmed this with a probe: real fallback, a fast refresh queued behind a
  held App callback, the actual `_attempt` / subscription transition, then
  release. Recheck at execution time, or keep client fast refreshes off the
  pump in both modes, and add a fallback-to-server queued-callback regression
  test.
- **Changes made:**
  - **The fix.** `_dispatch_fast_refresh` now sends ANY `MonitorClient` fast
    refresh to the coalesced worker, whatever its mode. In fallback the worker
    runs the in-process capture off the pump. Only a non-client monitor (test
    doubles) keeps `call_later`. No route decision is made at scheduling time,
    so none can go stale.
  - **Other route decisions, re-checked for the same race:**
    - `_refresh_data` decides when the callback itself runs, and its inline
      fallback path never waits on the server: after a mid-refresh reconnect
      it only reads state.
    - `d`'s follow-up `call_later(self._refresh_data)` re-decides in
      `_refresh_data`.
    - `d` itself and the scan worker are always workers.
  - **New test,
    `test_a_refresh_queued_in_fallback_never_holds_input_after_a_reconnect`.**
    It follows the user's probe:
    1. a real `FALLBACK` start (`ensure` answers `UNAVAILABLE`);
    2. the App pump held by a queued callback;
    3. a fast refresh scheduled;
    4. the real `client._attempt()` and subscription, to `SERVER`;
    5. release.

    The next key must dispatch, and the scheduled refresh must actually have
    run.
  - **Positive control.** Gating the dispatcher on the current mode fails the
    test by turn exhaustion.
  - The spec bullet says the route is chosen for any client.
- **Files affected:** `.aitask-scripts/monitor/monitor_app.py`,
  `tests/test_minimonitor_startup_input_latency.py`,
  `aidocs/framework/monitor_status_protocol.md`.

### Change Request 4 (2026-11-07)
- **Requested by user:** the reconnect regression test held the App pump on
  `gate.wait()`, but released the gate only after the subscribe exchange and
  the reconnect assertions. A failed or timed-out exchange left `run_test`'s
  teardown waiting on the held pump. The user's injected subscription
  disconnect hung past a 6 s timeout. Release the gate unconditionally in a
  `finally`. This is test-harness hardening only.
- **Changes made:**
  - **The fix.** Everything after the hold is queued now runs inside
    `try/finally`. The `finally` sets the gate and cancels a still-pending
    `_attempt()` task.
  - **Re-checked with the user's injection.** A scripted disconnect on the
    subscribe reply now fails the test in 0.1 s instead of hanging.
  - **Same treatment for three app-test events.** In
    `tests/test_monitor_apps_subscribe.py` the held-request events of
    `test_a_user_refresh_returns_at_once_and_scans_in_order`, the coalescing
    test and the replaced-monitor test are released in `finally` as well. They
    never hung, because their drain is bounded, but a failure no longer leaves
    a worker blocked until the bound.
- **Files affected:** `tests/test_minimonitor_startup_input_latency.py`,
  `tests/test_monitor_apps_subscribe.py`.
- **Verification:** monitor and minimonitor non-live modules: 1984 passed.

## Final Implementation Notes

- **Actual work done:**
  - **`status_client.py`, additive.** `set_capture_pins` keeps its send task.
    New `flush_pins()` waits for it, bounded by the request timeout, and never
    raises for the send's outcome.
  - **`monitor_shared.py`.**
    - `build_monitor_client(...)` is the one construction seam.
    - `_publish_parked_agents` also calls `set_capture_pins(self._capture_pins())`.
    - The off-pump user-refresh machinery: `_wants_offpump_scan`,
      `_dispatch_scan_refresh`, `_scan_refresh_worker`, `_request_server_scan`
      and `_maybe_rerun_refresh`, plus class-level flags.
    - `_cycle_compare_mode_async`, the `d` worker.
  - **Both apps.**
    - They build their `TmuxMonitor` as before and wrap it.
    - The first refresh and the interval (`_tick_refresh`) pass `scan=False`.
    - `_refresh_data(scan=True)` under a client not in `FALLBACK` dispatches
      the worker and returns. The worker runs one ordinary guarded round
      (`_request_scan=True`):
      1. publish (after this tick's identity check in the minimonitor);
      2. `flush_pins`;
      3. `request_refresh`;
      4. read.
    - `main()` passes `monitor_server=False` for an explicit `--interval`
      (both) or `--lines` (monitor).
  - **Monitor only.** `_dispatch_fast_refresh` routes every fast
    preview/shadow refresh of any `MonitorClient` through a coalesced worker.
    That covers forwarded keys, scroll re-attach, `t` and Enter's
    `set_timer` delayed refresh.
  - **Docs.** The spec's "Python client" section gets a `flush_pins` sentence
    and a "Consumers: monitor and minimonitor" subsection. The website monitor
    reference gets the `AITASKS_MONITOR_SERVER` row and the
    `--interval`/`--lines` note.
- **Deviations from plan:**
  - **Fast preview path.** The plan covered only full refreshes. Review rounds
    1–3 extended the off-pump rule to the monitor's fast preview path: the
    `call_later` sites, the `set_timer` delayed refresh, and the route
    decided by object type rather than by mode at scheduling time. See
    Post-Review Changes.
  - `READ_SURFACE_NAMES` was not extended. The surface test only needs class
    members.
  - The live test runs its clients in a driver subprocess, as
    `test_monitor_status_client_live` does.
  - App-timer checks run monitor and minimonitor sequentially against one
    server: one Textual app per `run_test`.
- **Issues encountered:**
  - **A wrong pump audit.** My first audit cleared the `set_timer` callback.
    Installed Textual wraps `set_timer` callbacks in `call_next`, so they run
    on the pump; only `set_interval` doesn't (Change Request 2).
  - **The coalescing test's first version** expected a second round for
    keystrokes that landed before the first round had sent its request. Those
    are correctly covered by that round.
  - **A wrong delta generation** in a scripted test caused a stream gap. Fixed
    with consecutive generations.
  - **Live use from the shared checkout.** A real minimonitor spawned in this
    repo at 2026-11-06 11:14 ran the uncommitted code and started a real status
    server, pid 3870908. That is production use, not a test leak. It was the
    only server present both before and after the full suite.
- **Key decisions:**
  - Route by type, never by mode, for anything queued (Change Request 3).
  - Keep fallback inline behaviour for full refreshes, decided at callback
    execution, where the inline path never waits on the server.
  - `_request_server_scan` treats a non-client monitor as a plain read.
- **Verification:**
  - **Full suite:** `PYTHON SUITE: PASSED (runner=pytest, exit=0)`, with 11175
    passed and 6 skipped, plus 15 serial, before the review rounds. After the
    rounds, every `tests/test_monitor*.py` / `tests/test_minimonitor*.py`
    non-live module passed (1984), and the three status-server live modules
    passed (10).
  - **Positive controls,** each failing its test:
    - the inline server wait;
    - request before publish;
    - the timer back to `scan=True`;
    - publish without pins;
    - notifying the prediction;
    - no off-pump dispatch;
    - a no-op `flush_pins`;
    - `call_later` fast dispatch;
    - uncoalesced fast dispatch;
    - mode-gated fast dispatch;
    - the delayed refresh awaiting.
  - **Post-phase `suite_spawns_no_status_server`: PASS.**
    - Before the suite: one server, pid 3870908 on `/tmp/tmux-1000/ait`, from
      the live minimonitor above, with the runtime dir
      `/run/user/1000/aitasks/monitor-2d0b888256e321e6-0.40.1.{lock,log,sock}`.
    - After: the identical pid and files. No new server and no new socket.
- **Measurement — t2034_1's controlled server-cost comparison re-run.**
  - Setup: N = 12 fake agents on an isolated `-L ait_t2034_1_scale` server.
    Each row is two 60 s `cpurate` windows after a 20 s warm-up, on omg16 at
    2026-11-06 11:27–11:42. The 1-min load was 12.7 at the start, falling to
    2.4; other agents were running. Scripts are t2034_1's appendix copies.
  - **Script changes (deviations, all additive):**
    - `cpurate.sh` classifies `status_server.py` before `*tmux*`, so the
      server's `--tmux-socket-path` argument does not count it as the tmux
      server.
    - `scale.sh` passes `AITASKS_MONITOR_SERVER=${MS:-1}` to the companion
      minimonitors, includes the scratch socket's status-server pid in
      `cpurate`, and on teardown SIGTERMs only status servers whose cmdline
      names the scratch socket.
    - Every teardown left no status server behind.

  | K minimonitors | mode | tmux server % of a core | status server % | minimonitors total % |
  |---|---|---|---|---|
  | 0 | — | 0.03 / 0.03 | — | — |
  | 1 | shared server | 0.65 / 0.55 | 0.37 / 0.33 | 0.3 / 0.2 |
  | 4 | shared server | 0.68 / 0.65 | 0.33 / 0.35 | 1.0 / 1.0 |
  | 1 | in-process (`AITASKS_MONITOR_SERVER=0`) | 0.57 / 0.50 | — | 0.4 / 0.4 |
  | 4 | in-process | 2.22 / 2.13 | — | 1.8 / 1.6 |

  - **The difference.** With the shared server, tmux-server CPU no longer
    grows with K: 0.6 → 0.67 % from K = 1 to 4, against 0.54 → 2.18 %
    in-process. At K = 4 that is about −70 %; one shared scanner predicts
    (K − 1)/K = 75 %.
  - **System total at K = 4:** about 3.9 % in-process, against about 2.0 %
    shared (tmux 0.67 + status server 0.34 + minimonitors 1.0).
  - **Minimonitor CPU.** Per-minimonitor CPU is also lower in server mode, at
    about 0.25 % against 0.43 % each at K = 4, because the producer moved out.
  - **Against t2034_1.** Its K = 4 in-process figure was 2.62–2.73 %; this run
    measured 2.13–2.22 % on the same harness, after t2183's render diff. The
    numbers are one host and one moment, and not a gate.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - **t2037_4 (applink).**
    - Construct through `monitor_shared.build_monitor_client` (`kind="applink"`),
      or `MonitorClient` directly if pulling in Textual is unwanted.
      `monitor_shared` imports Textual widgets.
    - **Before any requested scan,** call `flush_pins()` between
      `set_capture_pins` and `request_refresh`.
    - **Never await a server-backed call** (`capture_pane_classified_async`,
      `refresh_shadow_snapshot`, `request_refresh`, `capture`, `set_content`,
      the `*_async` compare calls) on a serialized dispatch path.
    - **Decide routes by type, not by `mode`.** The mode can change between
      scheduling and execution.
    - The server applies project config. An instance override needs
      `enabled=False`.
  - **Follow-ups.** `apps_timer_shared_scan_live` and `monitor_render_on_push`
    are spawned at Step 8d.
