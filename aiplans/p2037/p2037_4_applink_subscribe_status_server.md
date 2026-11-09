---
Task: t2037_4_applink_subscribe_status_server.md
Parent Task: aitasks/t2037_python_monitor_status_server.md
Sibling Tasks: (none pending)
Archived Sibling Plans: aiplans/archived/p2037/p2037_*_*.md
Base branch: main
Output branch: main
---

# t2037_4 — applink subscribes to the monitor status server

## Context

t2037_1 shipped the shared status server, t2037_2 shipped `MonitorClient`
(`monitor/status_client.py`), and t2037_3 moved `ait monitor` / `ait minimonitor`
onto it. applink is the last consumer that still runs its own scan:
`AppLinkServer` (`applink/server.py:194`) builds a `TmuxMonitor`, and every
connection's `PushScheduler` (`applink/pusher.py:158`) calls
`capture_all_async()`. That call is a **full scan of every pane** on each push
tick, which happens every 300 ms while a phone focuses a pane.

Goal: status comes from the subscription, and the per-call routing is explicit.
The mobile wire protocol (`aidocs/applink/protocol.md`) stays unchanged.

User decisions taken in this session:
- **Lifecycle:** applink holds a subscription only while at least one phone
  connection has a push loop. An idle applink costs no scans, as today.
- **Pins:** applink pins the `(session, window)` of every pane that any phone
  streams content for. Status-only parked panes get the parked placeholder.
- **`cycle_compare_mode`:** a deferred, authoritative answer. The `res` is sent
  by a background task when the server answers, never awaited in the
  per-connection read loop.

Advisory input (t2037_3's note, acknowledged):
- never await a server-backed call on a serialized dispatch path;
- `set_capture_pins` → `flush_pins()` → `request_refresh()` is the order;
- choose routes by object type, never by `client.mode`;
- `capture_all_*` only reads the subscription.

## Design

### Per-call routing (the task's "decide per call")

| Call (site) | Server mode | Why |
|---|---|---|
| `capture_all_async` (pusher) | subscription read | status for `pane_status`, content for frames |
| `get_pane`, `discover_panes`, `get_session_to_project_mapping` (router, pusher) | subscription | already on the client's read surface |
| streamed content panes whose requested cadence is due, plus forced panes (pusher) | one batched `request_refresh(panes=[…])` before the read | keeps each pane's requested cadence: the focused 300 ms, and a read-only client's fast `cadence_idle_ms` (floor 500 ms), which it uses because it cannot `focus`. The server ticks every ≥1 s, default 3 s. Status-only panes stay on the shared background ticks |
| `restart_task` idle gate (router) | new `status_snapshot(pane_id)`: subscription snapshot | the local instance never scans, so a local `capture_pane` would always say `not_idle` |
| `cycle_compare_mode` (router) | `cycle_compare_mode_async`, deferred reply | authoritative, off the read loop |
| `send_keys`, `send_enter`, `forward_key`, `switch_to_pane`, `kill_*`, `spawn_tui`, `get_pane_option_sync` | local gateway (`GATEWAY_NAMES`) | actions; local pane cache seeded by the client |
| `capture_cursor_async` (pusher) | local gateway | cursor isn't in the protocol |
| `capture_pane_content_async` (history pull) | local gateway | applink-only depth (`history_capture_lines`, up to 10000); the local cache is seeded, and it never touches the idle clock |

Nothing goes through the wire `capture{}`: the one raw read applink makes is the
deep history pull, and that read stays local, where its depth bound is enforced.

### Lifecycle (`AppLinkServer`)

- **The base local stays.** `self._monitor` is the `TmuxMonitor` built exactly as
  today. It serves the router whenever no client exists: verbs from a connection
  with no push loop, and the first `subscribe`'s roster expansion.
- **`self._use_status_server`** follows `AITASKS_MONITOR_SERVER` (`ENV_SWITCH`
  from `status_client`), read once in `__init__`. With `0` there is never a
  client, and every path is exactly today's code: `start()` starts the base
  control client as before.
- **Class defaults.** `_use_status_server = False`, `_client = None`,
  `_client_ensure = None` and `_deferred = {}` are class-level, so the
  `AppLinkServer.__new__`-built servers in `tests/test_applink_pusher.sh` and
  `tests/test_applink_server_limits.sh` keep today's path untouched.
- **`_ensure_pusher(conn, ws)`.** When enabled and `self._client is None`, it
  calls `self._client = self._build_client()` and
  `self._router.set_monitor(self._client)`. The new pusher gets
  `self._client`, plus `publish_pins=self._publish_pins`.
- **`_build_client()`** constructs a **fresh** local `TmuxMonitor` with the same
  config arguments, and returns
  `MonitorClient(local, kind="applink", own_pane=self._own_pane,
  session=DEFAULT_SESSION, project_root=<project root>, include_shadows=False,
  pins=frozenset(), ensure=self._client_ensure, log=<"applink.status" logger>.info)`.
  Construction does no I/O.
  - **Startup belongs to the client lifetime, not to a pusher.**
    - **The flaw.** `MonitorClient.start()` awaits its `_start_task` unshielded
      (`status_client.py:397`). The first caller's cancellation therefore
      cancels the shared startup, and `_start_body`'s `finally` sets `_ready`
      with the mode still `CONNECTING`: no fallback and no reconnect.
    - **How applink would hit it.** Phone A's pusher is the first reader. Phone
      B joins. A disconnects mid-startup, and `PushScheduler.stop()` cancels
      A's loop, killing the startup B depends on.
    - **The fix.** `_build_client()` calls a new, additive, sync
      `client.start_detached()`. It sets `_started` and creates `_start_task`
      itself, and no caller awaits that task. Every later `start()` /
      `_await_ready()` then takes the existing `_started` branch,
      `await self._ready.wait()`, and an `Event` waiter can be cancelled safely.
    - **Final close still cancels.** `close()` already cancels and drains
      `_start_task`.
    - `start()`'s own semantics are unchanged (the monitor apps' contract).
  - **Why a fresh local per lifetime.** A closing client releases its seeded
    pane cache and closes its local's control client. If two client lifetimes
    shared one local, an old client closing while a new one starts would wipe
    the new one's seed or close its control client. With one local per
    lifetime, the two never meet.
- **`_release_client_if_idle()`** runs in `_handle`'s `finally`, after
  `pusher.stop()`. When no pushers remain, it does three things, in this order:
  1. detach the client: `client = self._client; self._client = None`;
  2. point the router back at the base local:
     `self._router.set_monitor(self._monitor)`;
  3. `await client.close()`.

  Detaching before awaiting means a connection arriving meanwhile builds a new
  client.
- **`start()`.** When enabled, it no longer starts the base local's control
  client. The status server owns the stream parse; the client starts local
  control itself in fallback.
- **`stop()`.** It cancels deferred tasks, closes the client if any, then the
  base control client as today.
- **New `FrameRouter.set_monitor(monitor)`.**

### Pins and the parked view

- **`AppLinkServer._streamed_pins()`.** The union, over every pushed connection
  that is not paused, of `(pane.session_name, pane.window_name)` for each pane
  `p` where `sub.streams_content(p)` and `client.get_pane(p)` is known.
- **Publishing is independent of push passes.** A new server method,
  `_publish_pins()`, runs `self._client.set_capture_pins(self._streamed_pins())`
  when a client exists. `set_capture_pins` is a no-op when nothing changed, and
  it sends `set_pins` otherwise.
  - **Where it runs.**
    - In `_handle`, after **every** routed frame. That covers `subscribe`
      (including an empty accepted roster, where no pusher pass ever runs),
      `pause`, `resume`, `focus` and `request_keyframe`.
    - In `_handle`'s `finally`, after the connection is removed from `_conns` /
      `_pushers` and **before** the idle-release check. So one phone leaving
      while the other is paused still shrinks the union.
    - In each push pass, which also catches a pane moving to another window.
  - **Why the push pass alone was not enough.** It is skipped while paused,
    with an empty roster, or over the high-water mark, so a pin could stay
    stale for as long as the socket stayed open.
- **New client additions** in `status_client.py`, all additive:
  - `capture_pins`, a read-only property returning `self._pins`;
  - `parked_pairs()`, which returns the stream's `parked` set when serving and
    `frozenset()` otherwise. Fallback therefore stays exactly today's
    in-process behaviour: applink never published a skip set, so it captured
    and showed everything.
  - `status_snapshot(pane_id)`:
    - when serving: `self._snapshots_view().get(pane_id)`;
    - subscribed but not serving: `None`;
    - otherwise: `self._local.capture_pane(pane_id)`, today's live capture.
    - Added to `READ_SURFACE_NAMES`.
- **New `applink/status_view.py`** (pure, no asyncio):
  `view_snapshots(monitor, snaps, *, own_pane)` →
  `client_view_snapshots(snaps, own_pane=own_pane,
  parked_pairs=<getattr probe parked_pairs()>, pins=<getattr probe
  capture_pins>)`. A plain `TmuxMonitor` has neither attribute, so it becomes a
  pass-through apart from the own-pane drop.
  - The pusher's existing `client_view_snapshots(snaps, own_pane=…)` call is
    replaced by it.
  - The router's restart gate projects its one snapshot through it.

  Effect: a parked agent that only another subscriber pins arrives live, but
  shows as parked to applink unless a phone streams it, which is the spec's
  per-client projection rule.

### Pusher (`_run_once`)

After the existing paused / no-subscription / high-water returns, when
`isinstance(self._monitor, MonitorClient)` (routed by type), run
`await self._prepare_server_read(sub)`:
1. `await monitor.start()`. The server already started the client detached, so
   this only waits on the `_ready` event, and cancelling this pusher cannot
   cancel the startup.
2. `self._publish_pins()`, the server's publisher, when given. It is a refresh
   of the already-published union, not its only publisher.
3. `refresh_now = self._clock()`. `want` is every `p` in `sub.panes` such that:
   - `sub.streams_content(p)`, so status-only panes are never requested and
     stay on the shared background ticks;
   - `monitor.get_pane(p) is not None`, so a gone pane is never requested;
   - and either `p in sub.force`, or
     `refresh_now - st.last_refresh_t >= sub.cadence_for(p) / 1000`.

   `cadence_for` already returns the focused cadence for the focused pane and
   `cadence_idle_ms` for every other pane, so a focused pane and a read-only
   client's fast idle cadence go through the same rule. There is no focused
   special case.
   - **`PaneState.last_refresh_t`** (new, `content.py`, default `0.0`) records
     refresh **attempts**, separately from `last_send_t`. Every pane in `want`
     gets `last_refresh_t = refresh_now` when the request is sent, whatever
     comes back. So an unchanged pane is captured at most once per its own
     cadence, never once per loop pass.
   - **No new scheduler.** The push loop already wakes at `sub.next_tick_ms()`,
     which is the minimum of the focused and idle cadences, so it reaches each
     pane's cadence.
4. If `want` is non-empty: `await monitor.flush_pins()`, then **one** batched
   `await monitor.request_refresh(panes=sorted(want))`.
   - In fallback both return at once.
   - This is the pusher's own task, not the read loop. A stalled server delays
     only this connection's next push, bounded by the client's request timeout.

Then the existing `capture_all_async()` read, followed by `view_snapshots`.

**Parked content guard** in `_push_pane`, after the `pane_status` heartbeat:
`if getattr(snap, "parked", False): sub.force.discard(pane_id); return`.
- A placeholder carries `content=""`. Pushing it as a keyframe would blank the
  phone's terminal.
- `row_sigs` stays `None`, so the first live content is a keyframe.

### Deferred `cycle_compare_mode`

- **Router.** If `getattr(self._monitor, "cycle_compare_mode_async", None)` is
  callable (a client, so the route is chosen by type), it returns a
  `DeferredReply(run)`. `run` is an `async def` that awaits it and builds:
  - on success: the same `res`, `{mode, following_default}`;
  - on `RequestFailed`, `ConnectionLost`, `asyncio.TimeoutError` or
    `ReplayReadOnly`: `err INTERNAL`, `"compare mode request failed"`,
    `detail.reason` set to the exception class name.

  `DeferredReply` lives in `router.py` as a tiny holder. The router still
  imports no asyncio: the coroutine function is written in
  `status_view.py`, or the exceptions are caught generically by name. Pick at
  implementation, keeping the router asyncio-free.

  Otherwise (the base local, or stubs), the sync path is unchanged.
- **Server `_handle`.** `isinstance(reply, DeferredReply)` → `_spawn_deferred(conn, ws, reply)`:
  - a task awaits `reply.run()` and then `ws.send(json.dumps(frame))`, with
    send failures swallowed;
  - tasks are tracked in `self._deferred[conn]` and cancelled in `_handle`'s
    `finally`, before the client release.

  The read loop goes straight on to the next frame.
- **Ordering.** The `res` can now follow replies to later requests. The
  envelope pairs `res` to `req` by `id` (`protocol.md` §Message envelope), and
  the pre-phase below checks the mobile client actually does.

## Implementation

### Pre-phase (risk mitigations)

1. [mobile_res_correlation_check] Resolve the mobile repo by logical name.
   - Run `./ait projects resolve aitasks_mobile`. If it is not registered,
     record that and keep going.
   - Grep its applink client for how `res` / `err` frames reach their caller:
     a pending map keyed by `id`, or a FIFO.
   - Record the file:line evidence in the plan's Final Implementation Notes.
   - If replies are matched by arrival order, **stop** and ask the user whether
     to fall back to the sync prediction, before writing the deferred path.

### Steps

1. **`monitor/status_client.py`**, additive: `start_detached()`,
   `capture_pins`, `parked_pairs()`, `status_snapshot()`, plus the
   `READ_SURFACE_NAMES` entry for `status_snapshot`.
   - Check `git diff --quiet HEAD -- <file>` first.
   - Add `tests/test_monitor_status_client.py` cases for each, in server mode
     (real-server fixture) and in fallback.
   - **Startup cases for `start_detached()`.** Hold `ensure` on a
     `threading.Event` (the attempt runs in `to_thread`). Start two waiter
     tasks, each awaiting `start()`, then cancel the first.
     - After release, the client reaches `SERVER`, or `FALLBACK` with a
       reconnect task for an `UNAVAILABLE` ensure. The second waiter returns.
     - Positive control (recorded): without `start_detached`, letting the first
       waiter own the start leaves the mode `CONNECTING` with no reconnect task.
     - `close()` during a held detached start cancels it. The client ends
       closed, and no waiter hangs.
2. **`applink/status_view.py`** (new): `view_snapshots`, plus the async compare
   helper if it lands here.
3. **`applink/router.py`**:
   - `set_monitor`;
   - `DeferredReply`;
   - the `cycle_compare_mode` branch;
   - the restart gate: `snap = status_snapshot(pid)` via a probe, falling back
     to `capture_pane`, then projected through `view_snapshots`;
   - module docstring line on the deferred reply.
4. **`applink/pusher.py`**:
   - the `publish_pins` kwarg;
   - `_prepare_server_read`, plus `PaneState.last_refresh_t` in
     `applink/content.py`;
   - `view_snapshots`;
   - the parked guard;
   - docstring paragraph on the server-mode read.
5. **`applink/server.py`**:
   - the lifecycle members above;
   - `_streamed_pins` and `_publish_pins`, the latter called after every routed
     frame and in `_handle`'s `finally` before the idle-release check;
   - `start_detached()` from `_build_client`;
   - `_spawn_deferred`;
   - the `start` / `stop` changes;
   - module docstring.
6. **`tests/test_applink_headless_live.sh`**: export `AITASKS_MONITOR_SERVER=0`
   for the launched bridge, with a comment.
   - Reason: it runs on the developer's **real** tmux server, and must not
     start a status server there. Its scope (the TLS round-trip) stays the
     in-process path.
   - The new isolated live test below covers server mode.
7. **Docs** (current-state prose):
   - **`aidocs/framework/monitor_status_protocol.md`**:
     - a new `### Consumers: applink` subsection, covering: subscribe while
       streaming; the routing table in brief; pins = streamed panes; the
       batched per-cadence `refresh{panes}` for streamed content panes
       (status-only panes stay on background ticks); the deferred compare
       reply; the opt-out;
     - Python client section: the three new members.
   - **`aidocs/applink/`**: grep for statements that applink builds or scans
     its own `TmuxMonitor`, and correct the current-state ones. Candidates:
     `monitor_port_design.md`, `content_transport.md`. Add one sentence where
     `cycle_compare_mode` is described: its `res` may arrive after later
     replies.
   - **`website/content/docs/tuis/applink/reference.md`** "Listener": one
     paragraph. While a device streams, pane status comes from the shared
     monitor status server, and `AITASKS_MONITOR_SERVER=0` makes applink scan
     itself.
   - **`website/content/docs/tuis/monitor/reference.md`**: widen the
     `AITASKS_MONITOR_SERVER` row to "monitor, minimonitor and applink".
   - Then run `cd website && python3 check_links.py --build`.

### Tests — new `tests/test_applink_status_subscribe.py` (unittest, async)

- **Fixtures.** Reuse the fixtures through module aliases only
  (`import test_monitor_status_server as fx`, `import test_monitor_status_client as cx`).
  Skip when `websockets` or `msgpack` are missing, as the sibling applink
  Python test does. No real tmux: `_client_ensure` is injected, with a real
  `StatusServer` over `fx.FakeProducer` (tick ≥ 60 s), a `cx.ScriptedServer`,
  or `UNAVAILABLE`.
- **Lifecycle.**
  - The first pusher builds one client: `kind="applink"`, no shadows, its own
    fresh local (`is not srv._monitor`), and the router points at it.
  - A second connection reuses it.
  - Ending one connection keeps it.
  - Ending the last closes it: `_client is None` and the router is back on the
    base local.
  - The next connection gets a new client with a new local.
  - With `AITASKS_MONITOR_SERVER=0` there is no client, the pusher gets the base
    local, and `start()` starts the base control client.
  - **Startup overlap.**
    1. Hold `ensure` (a `threading.Event`).
    2. Phone A subscribes, then phone B subscribes; they share one client.
    3. A disconnects, so its pusher is stopped and its `_handle` exits, while
       startup is still held.
    4. Release `ensure`.

    Then the client reaches `SERVER`, and B's next pass gets `pane_status`
    from the subscription with no local `capture_*`. With an `UNAVAILABLE`
    ensure instead: `FALLBACK` with a reconnect task. Afterwards, B
    disconnects and the client closes.
    - Positive control (by hand, docstring): build the client without
      `start_detached()`. The test then fails, with the mode stuck at
      `CONNECTING`.
- **Status from the subscription.** Over 5 `_run_once` passes with no focus and
  no force:
  - the `pane_status` payloads match the producer snapshots;
  - the client's local saw no `capture_*` call;
  - the server received no `refresh`;
  - the producer's full-scan count is unchanged apart from the subscribe tick.
- **Requested cadence without focus.** The phone is read-only, so the router
  answers `focus` with `PERMISSION_DENIED`.
  - **Setup.** The phone subscribes through the router with
    `content_panes=[A]`, roster `[A, B]` and `cadence_idle_ms=500`. Pane `C`
    exists but is not subscribed. The real `StatusServer` ticks every ≥ 60 s,
    so it runs no background scan during the test. Use an injected pusher
    clock, and change A's producer content between passes.
  - **Assertions:**
    1. At t=0 the forced subscribe pass sends one `refresh{panes:[A]}`.
    2. At t=0.3, not due, nothing is sent.
    3. At t=0.6 one `refresh{panes:[A]}` is sent, and the phone receives a
       frame carrying A's **new** content.
    4. The producer's full-scan count stays at its post-subscribe baseline, so
       the fresh content arrived before any background scan.
    5. Every recorded partial capture targets A only: never B (status-only) and
       never C (unrelated).
  - **Unchanged output.** Leave A's content unchanged and run passes at 0.7,
    0.8 and 1.0. Exactly one refresh follows, at 1.1 (one per cadence); none is
    sent per pass.
  - **Focused pane.** A `monitor_control` phone that focuses A gets a
    `refresh{panes:[A]}` at the 300 ms focused cadence through the same rule.
  - **Batching.** Two due content panes go in **one** `refresh` request.
  - **Order.** The recorded order is `set_pins` → (pins flushed) → `refresh` →
    read.
  - **Positive controls (by hand, docstring):**
    - Restricting `want` to focused and forced panes fails assertion 3: the
      content is stale.
    - Driving due-ness from `last_send_t` instead of `last_refresh_t` fails the
      unchanged-output check, with one refresh per pass.
- **Forced panes.** The subscribe pass refreshes exactly the forced streamed
  panes that are known. The next pass refreshes none. A forced gone pane is
  never requested.
- **Pins.**
  - A streamed pane in a parked window → `set_pins` carries its pair before the
    refresh, the skip set at the refresh's capture excludes it, and the
    keyframe carries live content.
  - A status-only parked pane → placeholder `pane_status` and no binary frame.
  - A parked agent pinned only by a second `fx.Client` → shows as parked to
    applink.
  - **Positive control (by hand):** request before `set_pins`. The first
    assertion then fails.
- **Pins drop with no push pass.** Use phones A and B on a real
  `StatusServer` with `fx.FakeMarks`, and patch `PushScheduler.start`, so that
  no push pass ever runs and only `_handle` frames drive the pins. A streams a
  pane in parked window WA; B streams one in parked window WB.
  1. A sends `pause` → the server-side pins of the applink connection drop WA.
     Read them from the server's connection state, or from the `("skip", …)`
     before the next tick's capture, which then contains WA again.
  2. A sends `resume` → WA is back.
  3. B re-subscribes to an empty accepted roster → WB drops.
  4. A disconnects while B is paused → the union is empty.
  5. B disconnects → the client closes.
  - Positive control (by hand): publish only from the push pass. Steps 1, 3
    and 4 then fail.
- **Parked guard.** A ScriptedServer placeholder for a content pane sends no
  binary frame and clears force. The first live content after it is a keyframe.
- **Fallback.** With `ensure` → `UNAVAILABLE`, the capture goes through the
  local instance as today, with no requests.
- **Restart gate.**
  - A subscription snapshot with `is_idle` → `confirm_required`, carrying the
    subscription's `idle_seconds`, and the local `capture_pane` is never
    called.
  - Not idle → `not_idle`.
  - The client in fallback → local `capture_pane`.
  - **Positive control (by hand):** route to `capture_pane`. The gate then
    answers `not_idle`.
- **Deferred compare**, through the real `_handle` with a queue-fed fake ws:
  - The ScriptedServer answers a mode different from the prediction, and the
    `res` carries the server's answer.
  - With the reply held, a following `send_keys` frame's `res` is sent first.
    After release, the compare `res` arrives with its own `id`.
  - An `error` reply → `err INTERNAL`.
  - Socket closed while the reply is held → the task is cancelled, and nothing
    is sent after close.
  - The stub-monitor sync path is pinned by the existing
    `tests/test_applink_router.sh`.
- **Surface.** `tests/test_monitor_client_surface.py` runs unchanged and stays
  green.

### Live test — new `tests/test_applink_status_subscribe_live.py`

- **Isolation.** The `test_monitor_status_server_live.LiveCase` pattern: a
  scratch `-L` socket via `AITASKS_TMUX_SOCKET`, plus scratch `TMUX_TMPDIR`,
  `XDG_RUNTIME_DIR`, `HOME` and marks file. It skips only without tmux,
  `websockets` or `msgpack`.
- **Fixture.** A scratch project with `refresh_seconds: 1`, one session, and 2
  agent windows running printer loops.
- **Driver subprocess** (as `test_monitor_apps_subscribe_live.py` does):
  - Patch `applink.paths.project_root` / `sessions_dir` to the scratch project,
    so no audit log or sessions file lands in the repo.
  - Build a real `AppLinkServer` with `ssl_context=None` (no listener), a
    `SessionTable(persist=False)` and the repo's profiles.
  - Wrap each built client's local `_tmux_async` / `tmux_run` to count
    `capture-pane`.
  - Pair through the router, then run `_handle` on a queue-fed fake ws:
    1. `subscribe {panes: []}`;
    2. collect the `pane_status` pushes for both agents over ≥ 3 server ticks;
    3. `send_keys` a marker plus `send_enter` to pane A;
    4. close the socket.
  - Print the counts as JSON.
- **Asserts, server mode:**
  - both panes get `pane_status`;
  - the marker reaches pane A (`tmux capture-pane` in the test);
  - the client's local made **0** `capture-pane` calls;
  - after close, `_client is None`.
- **Control.** The same run with `AITASKS_MONITOR_SERVER=0` makes ≥ 1 local
  `capture-pane` per tick. That proves the counter sees captures.
- **Cleanup.** Signal only the status-server pids from `server_info` that pass
  the `/proc/<pid>/cmdline` scratch-path check, and kill tmux by its `-L` name
  only.
- If it flakes under xdist, add it to the runner's serial carve-out and the
  CLAUDE.md list in the same commit.

### Post-phase (risk mitigations)

1. [suite_spawns_no_status_server] Repeat t2037_3's check, with the same
   commands as that archived plan's post-phase:
   - record the status-server pids and cmdlines
     (`pgrep -af 'monitor/status_server.py'`) and the runtime-dir listing;
   - run `bash tests/run_all_python_tests.sh` and every `tests/test_applink_*.sh`;
   - record both again.
   - **Pass** when no new pid lacks a scratch path and the runtime dir gained no
     socket. Record the listings in Final Implementation Notes.

## Verification

- Each applink suite passes: `for t in tests/test_applink_*.sh; do bash "$t"; done`.
- Targeted: `python -m pytest tests/test_applink_status_subscribe.py tests/test_applink_status_subscribe_live.py tests/test_monitor_client_surface.py tests/test_monitor_status_client.py tests/test_applink_pane_status_provenance.py`.
- Full suite: `bash tests/run_all_python_tests.sh`. Read only the last line:
  `PYTHON SUITE: PASSED`.
- `shellcheck` on any edited `.sh` file.
- `cd website && python3 check_links.py --build`.

## Risk

### Code-health risk: medium
- **Lifecycle and concurrency.** `AppLinkServer` gains a client lifecycle
  (build on the first pusher, detach-then-close on the last, a fresh local per
  lifetime) and deferred reply tasks. A missed release would leave a
  subscription that keeps the status server scanning. A missed cancel would
  send on a closed socket. Bounded by the class defaults, which keep the
  `__new__`-built tests on today's path, and by the lifecycle and
  deferred-close tests · severity: medium · → mitigation: none (in-plan tests)
- **Shared startup cancellation (found in plan review).** One pusher's
  cancellation could cancel the startup that every other phone shares, and
  leave the client in `CONNECTING` for good. Startup now belongs to the client
  lifetime (`start_detached()`), and the overlap is covered by the client and
  lifecycle tests, with a positive control · severity: low (residual) ·
  → mitigation: none (in-plan design + tests)
- **Stale pins (found in plan review).** Pins published only from push passes
  could stay stale while every phone is paused or has an empty roster, so the
  shared server would keep capturing parked windows nobody watches. The pins
  are now published on every frame and on connection removal, and covered by
  the no-push-pass test · severity: low (residual) · → mitigation: none
  (in-plan design + test)
- **A stalled server in the push path.** The pusher's push loop now awaits
  `request_refresh` on the focused or forced panes. A stalled server delays
  that connection's pushes by up to the 10 s request timeout. It never delays
  the read loop or input · severity: low · → mitigation: none (by design;
  documented)
- **A test reaching the real tmux.** An applink test that builds a real server
  with real `TMUX` would start a status server on the developer's tmux. The
  headless live test is pinned to `AITASKS_MONITOR_SERVER=0`, but a future
  test could do this silently · severity: low (residual: addressed by inline
  post-phase suite_spawns_no_status_server) · → mitigation: inline post-phase
  suite_spawns_no_status_server
- **Some refresh work is duplicated.**
  - Each phone refreshes its own streamed panes. Two phones on the same pane
    each request it, which is not yet deduplicated.
  - A content pane at a cadence not faster than the server's background
    interval, such as the default 3000 ms against a 3 s tick, gets roughly one
    extra partial capture per cadence. The protocol does not advertise the
    interval.

  Both stay well below today's full scan per push pass, and attempts are
  bounded to one per pane per cadence · severity: low · → mitigation: none
  (later optimization: cross-phone dedup, interval-aware skipping)
- **Cursor captures fork.** In server mode the client's local runs no control
  client, so `capture_cursor_async` forks a `tmux display-message` for each
  changed focused-pane frame (up to ~3/s). That is still far cheaper than
  today's full scan every 300 ms · severity: low · → mitigation: none

### Goal-achievement risk: medium
- **Deferred replies can arrive out of order.** If the mobile client matches
  replies by arrival order rather than `id`, the deferred `cycle_compare_mode`
  reply would mis-route · severity: medium (residual: low after the inline
  pre-phase check) · → mitigation: inline pre-phase mobile_res_correlation_check
- **No real phone in the loop.** The live check drives the real `_handle` and
  router over a scripted socket, not a paired phone over TLS. A device-specific
  difference, such as cadence feel or parked panes on screen, would not be
  caught · severity: medium · → mitigation: applink_device_manual_check
- **Fallback idle clock resets.** Each phone session gets a fresh local, so
  in-process `idle_seconds` restart per session. Server mode is unaffected ·
  severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: mobile_res_correlation_check | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: a mobile client that matches replies by order would mis-route the deferred compare reply | desc: resolve aitasks_mobile by logical name, find how res/err frames are correlated, stop and re-ask before the deferred path if it is FIFO
- timing: post-phase | name: suite_spawns_no_status_server | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: an applink test reaching ensure_server on the live tmux | desc: snapshot status-server pids/sockets around the Python suite plus every applink .sh test and confirm none was left outside a scratch path
- timing: after | name: applink_device_manual_check | type: manual_verification | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: no real paired phone exercised the server-mode push and verb paths | desc: with a real paired phone - pane list badges update, a focused pane streams at its fast cadence, send_keys/kill work, d-cycle answer matches the desktop monitor, a parked agent streamed by the phone shows live and an unstreamed one shows parked, and applink with no device connected leaves no status server running after its grace

## Step 9 (Post-Implementation)

This runs on the current branch (fast profile, no worktree). After review:
- Commit the code as
  `feature: Subscribe applink to the monitor status server (t2037_4)`, naming
  only the paths.
- Commit the plan via `aitask_task_commit.sh`.
- Archive the child.
- This is the last child, so the parent t2037 archives too. Its cross-repo
  handoff note to `aitasks_go#47` (t2034_1's inbox note on t2037) is then due.
  Re-check the dependent list first.

## Post-Review Changes

### Change Request 1 (2026-11-09)
- **Requested by user.** Two review findings, both confirmed against the code
  before any change:
  - **The parked guard lost a recovery keyframe.** The guard cleared `force`
    but kept `row_sigs` and `last_hash`. A pane that streamed live, then got a
    `request_keyframe` that met a parked placeholder, then went live again:
    - with changed content, it was sent as a **delta** (frame types `[1, 2]`,
      the user's repro), against a baseline the phone may not hold;
    - with unchanged content, **nothing** was sent at all.
  - **Deferred replies were unbounded.** `_spawn_deferred` made a task for every
    `cycle_compare_mode`. While the status server withheld its reply, a burst
    grew the tasks and the client's pending requests without limit: 1,000 in
    the user's repro, 50 in ours.
- **Changes made.**
  - **The guard resyncs.** `PaneState.resync_on_live` is new. Suppressing a
    placeholder now does four things: reset `row_sigs` and `last_hash`, set the
    mark, and clear `force`, so a pane that stays parked draws no refresh every
    pass. On the next live snapshot the mark puts the pane back into `force`,
    which only a delivered (or finally dropped) frame clears, so a failed send
    keeps the resync. The frame is then forced, which bypasses both the
    unchanged-hash gate and the cadence gate, and goes out as a keyframe.
  - **Admission before task creation.** `MAX_DEFERRED_PER_CONN = 4`.
    `_spawn_deferred` returns `False` and creates nothing once the connection
    has 4 in flight, and `_handle` then answers at once with `err INTERNAL`,
    `detail: {reason: too_many_pending, limit: 4}`, which the audit log records.
    Ordinary verbs are unaffected.
  - **Spec.** The "Consumers: applink" section of
    `aidocs/framework/monitor_status_protocol.md` describes the resync and the
    bound.
- **Tests,** in `tests/test_applink_status_subscribe.py`:
  - **Live → parked → live, two variants.** A multi-row pane where the change
    touches one row: with a one-row pane the delta cost rule picks a keyframe
    anyway, which hid the bug in the first version of this test. Both variants
    expect `[keyframe, keyframe]`.
  - **A burst against a silent server.** 50 compare requests while every reply
    is held:
    - exactly 4 tasks and 4 pending status-server requests;
    - 46 refusals with `too_many_pending`;
    - a `send_keys` sent after the burst is answered;
    - after the replies are released, admission recovers.
- **Positive controls,** each failing its test, run from a scratch script that
  swaps the code under test:
  - the guard as `force.discard` only → `[1]` (unchanged content) and `[1, 2]`
    (changed content);
  - `_spawn_deferred` without its check → 50 tasks in flight against the
    expected 4.
- **Files affected:** `.aitask-scripts/applink/content.py`,
  `.aitask-scripts/applink/pusher.py`, `.aitask-scripts/applink/server.py`,
  `tests/test_applink_status_subscribe.py`,
  `aidocs/framework/monitor_status_protocol.md`.
- **Verification:** the applink and client Python modules, 93 passed; the
  pusher, router, server-limits and content `.sh` tests all pass.

## Final Implementation Notes

- **Actual work done:**
  - **`monitor/status_client.py`**, additive:
    - `start_detached()`: startup owned by the client, never by a caller;
    - `status_snapshot()`: subscription snapshot while subscribed, the local
      `capture_pane` otherwise;
    - `parked_pairs()` and the `capture_pins` property;
    - `status_snapshot` added to `READ_SURFACE_NAMES`.
  - **`applink/status_view.py`** (new): `view_snapshots`, the one projection,
    `client_view_snapshots` with the client's parked set and pins, shared by
    the push loop and the restart gate.
  - **`applink/router.py`:**
    - `set_monitor`;
    - `DeferredReply`, plus `_deferred_compare` for `cycle_compare_mode` on any
      monitor that has `cycle_compare_mode_async`;
    - `_status_snapshot`, the restart idle gate.
  - **`applink/pusher.py`:**
    - the `publish_pins` kwarg;
    - `_refresh_targets` and `_prepare_server_read`: start-wait, pins, one
      batched refresh after `flush_pins`, then the read;
    - `view_snapshots` on every read;
    - the parked guard with resync.
  - **`applink/content.py`:** `PaneState.last_refresh_t`, `resync_on_live`.
  - **`applink/server.py`:**
    - the client lifecycle: `_acquire_status_monitor`, `_build_client` (a
      fresh local, detached start), `_release_client_if_idle`;
    - pins: `_streamed_pins`, `_publish_pins`, after every frame and on
      connection removal;
    - deferred replies: `_spawn_deferred`, bounded by `MAX_DEFERRED_PER_CONN = 4`;
    - `start()` starts the base control client only in-process;
    - `stop()` cancels deferred tasks and closes the client;
    - class defaults so `__new__`-built test servers keep the old path, and a
      `_local_factory` test seam.
  - **Tests:**
    - `tests/test_applink_status_subscribe.py`, 21 tests;
    - `tests/test_applink_status_subscribe_live.py`, 2 tests on an isolated
      tmux socket;
    - 8 `SharedClientTests` added to `tests/test_monitor_status_client.py`;
    - `tests/test_applink_headless_live.sh` pinned to
      `AITASKS_MONITOR_SERVER=0`.
  - **Docs:**
    - the spec's "A shared client starts detached", the projection and
      `status_snapshot` notes, and the new "Consumers: applink" section;
    - `aidocs/applink/monitor_port_design.md`, cadence and compare-mode text;
    - the website applink Listener paragraph and the monitor reference
      `AITASKS_MONITOR_SERVER` row.
- **Deviations from plan:**
  - **Two plan-review rounds** reshaped the design before implementation:
    - shared startup ownership (`start_detached`);
    - pins published independently of push passes;
    - the per-cadence refresh of every streamed content pane, which replaced
      "focused or forced only".
  - **One code-review round** (Change Request 1) added the parked resync and
    the deferred-reply bound.
  - **Helper placement.** The deferred compare coroutine lives in the router as
    a closure that catches `Exception` by name, so the router still imports no
    asyncio. `status_view.py` holds only the projection.
  - **A `_local_factory` server seam** was added so unit tests never build a
    real `TmuxMonitor`, whose cursor capture would reach the developer's tmux.
  - **The `start()` control-client assertion for the disabled path** was not
    unit-tested: `start()` returns before that point without an SSL context. The
    disabled path's pusher and router routing is tested instead.
- **Issues encountered:**
  - **A test that hid its bug.** The first live → parked → live test used
    one-row content, so the delta cost rule picked a keyframe anyway. A
    multi-row fixture exposes the `[1, 2]` delta.
  - **An unchanged-output leg that missed its control.** The first version
    ended exactly at the next due point, where attempt-based and send-based
    timing agree. Passes after that point now separate them.
  - **Concurrent sessions.** Another session's commits (t2245, t2246) landed
    under `monitor_status_protocol.md` mid-session. The diff against HEAD
    showed only this task's hunks.
  - **The temp volume** hit its quota once near the end (other sessions' data).
    A retry succeeded.
- **Key decisions:**
  - Lazy lifecycle, per the user: no subscription while no phone streams.
  - Pins are the streamed content panes' windows, per the user. Status-only
    parked panes show as parked.
  - A deferred, authoritative compare answer, per the user. The pre-phase
    `mobile_res_correlation_check` confirmed that `aitasks_mobile`'s
    `KtorMonitorStreamClient.kt` keeps an `id`-keyed `pending` map (`:79`,
    insert `:139`, `pending.remove(id)` on `res`/`err` `:230-231`), so an
    out-of-order `res` is matched correctly.
  - Routes are chosen by type (`isinstance` / `getattr` probe), never by
    `client.mode`.
- **Verification:**
  - **Full suite:** `PYTHON SUITE: PASSED (runner=pytest, exit=0)`, with 11764
    passed and 6 skipped, plus 15 serial. That run predates Change Request 1;
    after it, the affected modules passed (93) and so did the
    pusher/router/limits/content `.sh` tests.
  - **Shell tests:** all 15 `tests/test_applink_*.sh` pass, the headless live
    one included.
  - **Website:** `check_links.py --build`, `SWEEP: PASSED`.
  - **Positive controls,** each failing its test:
    - no `start_detached`, at client and applink level;
    - focused-or-forced only;
    - send-driven due-ness;
    - refresh before pins;
    - pins only from push passes;
    - the restart gate via `capture_pane`;
    - a sync compare answer;
    - the guard without resync (`[1]`, `[1, 2]`);
    - no admission bound (50 tasks).
  - **Post-phase `suite_spawns_no_status_server`: PASS.**
    - Before (12:51) and after (13:04) the suite plus all applink `.sh` tests:
      the only status server was pid 820754, the user's own on
      `/tmp/tmux-1000/ait`.
    - The runtime dir `/run/user/1000/aitasks/` held the same files before and
      after: `monitor-2d0b888256e321e6-0.40.1.{lock,log,sock}`, plus older
      `1d10f373…` and `e4af9df2…-vchk` leftovers. No new socket.
- **Upstream defects identified:**
  - `.aitask-scripts/monitor/status_client.py:387-405` — `MonitorClient.start()`
    awaits its startup task unshielded, so cancelling the first caller cancels
    the shared startup, and the client is left `connecting` with no fallback and
    no reconnect. This was worked around for applink with `start_detached()`.
    The monitor apps own their client, so they are unaffected today, but any
    future shared caller would hit it.
- **Notes for sibling tasks:** t2037_4 is the last child of t2037.
  - **For the Go port (aitasks_go#47).** applink speaks the unchanged protocol
    as `kind: applink`, subscribing with `include_shadows: false`. It sends
    `set_pins` updates often, and partial `refresh{panes}` at phone cadences
    (300 ms focused, ≥ 500 ms idle). A Go server must therefore serve frequent
    partial refreshes cheaply, and apply `set_pins` before answering it.
