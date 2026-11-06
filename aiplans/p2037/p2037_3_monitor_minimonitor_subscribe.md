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
- timing: after | name: apps_timer_shared_scan_live | type: test | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: an app timer that requests a full server scan per client would pass every in-plan check below the app | desc: live test that mounts several real monitor/minimonitor apps on an isolated tmux server sharing one real status server and counts that server's full scans over several intervals (needs a scan counter the server exposes, e.g. in the welcome or a stats request), excluding startup and intentional refresh actions
- timing: after | name: monitor_render_on_push | type: enhancement | priority: low | effort: medium | inline_risk: medium | added_complexity: medium | addresses: up to one server tick of extra staleness in server mode | desc: re-render monitor/minimonitor on subscription updates via add_update_listener (Applied.changed) instead of only on the timer

## Step 9 (Post-Implementation)

This runs on the current branch (fast profile, no worktree). After the review,
commit the code with
`feature: Subscribe monitor and minimonitor to the status server (t2037_3)`
(only the named paths). Commit the plan via `aitask_task_commit.sh`, then run
the standard Step 9 archival of the child. t2037_4 (applink) stays pending, so
the parent is not archived and its cross-repo handoff note to aitasks_go#47 is
not due yet.
