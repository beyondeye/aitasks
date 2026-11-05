---
Task: t2037_2_monitor_status_client.md
Parent Task: aitasks/t2037_python_monitor_status_server.md
Sibling Tasks: aitasks/t2037/t2037_3_monitor_minimonitor_subscribe.md, aitasks/t2037/t2037_4_applink_subscribe_status_server.md
Archived Sibling Plans: aiplans/archived/p2037/p2037_*_*.md
Base branch: main
Output branch: main
---

# t2037_2 — `MonitorClient`: the subscription-backed `TmuxMonitor` stand-in

## Context

t2037_1 shipped the shared status server (`monitor/status_server.py`), with
`ensure_server()` / `probe_async()` and the wire codec `status_protocol.py`
(`StreamState`, `decode`/`encode`, `read_line`). t2034_3 shipped the replayer
`status_recording.ReplayServer` and the fixture `tests/fixtures/monitor_status/basic.jsonl`.
Nothing consumes the server yet.

This task builds the **Python client**. t2037_3 (monitor and minimonitor) and
t2037_4 (applink) swap their `TmuxMonitor` for it with small app-side edits. The
Textual twin of the Go parity demo (aitasks_go#16_5) uses its replay mode. It
changes no user-visible behaviour, because no app constructs the client yet.

Shape: `MonitorClient` wraps a **local `TmuxMonitor`**, the one the app already
builds with its own config. It has three modes:

- **server**: the read surface comes from a `StreamState` fed by the subscription.
  The local instance is only an action gateway (send-keys, kill, tmux_run, raw-tail
  captures), with no scan and no control client.
- **fallback**: every call is delegated to the local instance, which is today's
  in-process code, unchanged.
- **replay**: the client connects to a `ReplayServer` it runs on a temporary
  socket. It is read-only, and actions refuse.

Inputs carried forward (advisory notes and t2037_1's sibling notes):
- call `ensure_server()` from a worker thread;
- `UNAVAILABLE:*` means fall back;
- `welcome.server.impl` is `python`, or `replay` for a replayer;
- compare-mode results can wait up to one tick;
- pins take effect on the next capture;
- clients still apply `client_view_snapshots(...)` themselves. The apps already do
  this in `AgentMarksMixin._project_snapshots`, so the client returns
  producer-equivalent, **unprojected** dicts.

## Read surface the apps use (from grep of `monitor_app.py`, `minimonitor_app.py`, `monitor_shared.py`)

Producer state, which comes **from the subscription** in server mode:
`capture_all_async`, `capture_all_classified_async` + `capture_generation` +
`commit_snapshots`, `capture_pane_classified_async` + `commit_snapshot` (the fast
preview), `refresh_shadow_snapshot`, `get_shadow_snapshot`, `get_pane`,
`get_session_to_project_mapping[_async]`, `get_compare_mode`,
`is_compare_mode_overridden`, `get_last_change_wall`, `cycle_compare_mode`,
`set_compare_mode`, `control_state`, `last_enumerated_sessions`,
`last_discovered_agents`, `last_discovered_panes`, `set_parked_agents`,
`start_control_client`, `close_control_client`.

Gateway (always **local**): `tmux_run`, `tmux_run_async`, `send_keys`,
`send_enter`, `forward_key`, `switch_to_pane`, `find_companion_pane_id`,
`kill_pane`, `kill_window`, `kill_agent_pane_smart`, `kill_agent_run_guarded`,
`spawn_tui`, `get_running_tuis`, `get_missing_tuis`, `resize_pane`,
`get_pane_option`, `get_pane_option_sync`, `capture_pane`, `capture_pane_async`,
`capture_pane_content_async`, `capture_cursor_async`, `discover_window_panes[_async]`,
`invalidate_sessions_cache`, `_run_offloaded`, plus the config attributes
`session`, `capture_lines`, `idle_threshold`, `agent_prefixes`, `tui_names` and
`compare_mode_default`.

**The gateway reads `_pane_cache`.** `kill_agent_pane_smart` uses it for the window
collapse, and `switch_to_pane`, `capture_pane*`, `kill_agent_run_guarded` and
`get_running_tuis` use it too. A non-scanning local instance has an empty cache,
so in server mode it would quietly change action behaviour, for example a kill
that never collapses the window. The client therefore seeds the local cache from
the subscription (step 1).

## Design decisions

- **Construction.** `MonitorClient(local, *, kind, own_pane=None, session="",
  project_root=None, content="all", include_shadows=True, pins=frozenset(),
  version=None, ensure=None, replay=None, replay_speed=1.0, enabled=None, log=None,
  connect_deadline=3.0, ping_after=10.0, ping_timeout=10.0, resync_timeout=10.0, backoff=(0, .5, 1, 2, 4, 8, 16, 30))`.
  - `local` may be `None` only with `replay`.
  - `ensure` defaults to `status_server.ensure_server`. Tests inject a fake.
  - `enabled` defaults to `os.environ.get("AITASKS_MONITOR_SERVER", "1") != "0"`.
    When it is false the client is permanently in fallback and never calls
    `ensure`. That is the escape hatch for users and the "fallback mode" leg of
    t2037_3's both-modes tests.
- **Modes** (`ClientMode` enum: `CONNECTING`, `SERVER`, `FALLBACK`, `REPLAY`), a
  `mode` property, `server_info` (the last welcome's `server` and `replay`), and
  `last_error` (a string).
- **`start()`** (aliased by `start_control_client()`, so the app's existing
  control-client worker starts it) runs the first attempt and returns `True` once
  it resolves either way.
  - It calls `await asyncio.to_thread(ensure, version=…, session=…,
    project_root=…, deadline=connect_deadline)`.
  - `RUNNING`/`STARTED` → it connects (`asyncio.open_unix_connection(limit=sp.MAX_SERVER_LINE_BYTES)`),
    sends `hello{kind, pane, pid}` and requires a `welcome` whose `proto` and
    `version` match (a replayer's `replay` member is accepted). It then sends
    `subscribe{id, content, include_shadows, pins}` and applies the snapshot →
    `SERVER`.
  - Any failure (UNAVAILABLE, connect error, error reply, malformed line, timeout)
    → `FALLBACK`. The local control client starts in a background task, exactly as
    the app does today. The reconnect loop then runs (below).
  - Async read methods called while `CONNECTING` await the first attempt's
    outcome, so the app's first refresh never reads an empty state.
- **Subscribed modes.** `SERVER` and `REPLAY` are both *subscription-backed*.
  Every rule below written for server mode (reads from the state, `set_content`,
  `set_pins`, `request_refresh`, the fast preview, pane-cache seeding) applies to
  both. Only reconnect and fallback are `SERVER`-only.
- **Request/reply completion.** Every request the client sends carries an integer
  `id`, including `subscribe` and `set_content`.
  - The reader resolves the pending future for that `id` on a `result` or an
    `error`, **and on a `snapshot` whose `id` matches**. A snapshot is applied to
    the `StreamState` first and then resolves its request with the snapshot, so
    the caller of `subscribe` / `set_content` returns only once the state already
    reflects the reply.
  - The handshake (`hello` → `welcome`) is read inline by the connect path before
    the reader task starts. After that, every reply is consumed by the reader
    alone.
  - Callers that await a reply are never the reader: `start()`, the reconnect
    loop, `set_content()`, `request_refresh()` and the ping.
- **A snapshot-answered request that fails, fails the connection.** `subscribe`
  and `set_content` are answered by a snapshot. The other outcomes are:
  - an `error` carrying their `id`. The server does send this without closing:
    `_Connection.send` (status_server.py ~L534) turns an unencodable reply into
    `error{internal, id}`, and the server may already have switched the
    connection's selection;
  - missing their deadline;
  - `ConnectionLost`.

  Any of these leaves the client's state not known to match the server's stream,
  so the caller runs the established loss handling `_lost(reason)`: fallback, then
  reconnect, then a clean resubscribe. The exception is `ConnectionLost`, which
  means `_lost` already ran. `set_content()` then returns `False` instead of
  raising.
- **Gap recovery is a bounded request outside the reader.** On `StreamGap` the
  reader sets `resyncing = True` and, if no resync task is running, spawns one.
  The reader never awaits a reply.
  - The resync task calls the ordinary `link.request(subscribe{id, current
    settings}, timeout=resync_timeout)` (default 10 s; a resubscribe can wait for
    one tick under the server's producer lock).
  - The reader resolves it like any snapshot reply: it applies the snapshot, which
    replaces the state, clears `resyncing`, and resolves the future.
  - An error reply or a missed deadline goes to `_lost("resync failed: …")`.
  - While `resyncing` is set, deltas are dropped without another resubscribe.
    They were ordered before the reply snapshot, which supersedes them.
  - The drop window is bounded by `resync_timeout`. Neither ongoing traffic nor a
    successful liveness ping can extend it, because the deadline belongs to the
    request, not to the silence watchdog.
- **Reader task.** It reads with `sp.read_line` and decodes `direction=SERVER`.
  - `snapshot`/`delta` go to `StreamState.apply` (see the completion rule above).
  - A stale delta (`None`) is ignored.
  - `StreamGap` → the gap recovery above.
  - Unknown types are ignored, as the spec says.
  - A `ProtocolError`, `FramingError` or `StreamError` other than a gap, or EOF,
    → `_lost(reason)`.
  - After each applied message: bump the client generation, invalidate the
    converted-snapshot cache, seed the local pane cache, and call listeners.
- **Losing the server** (`_lost`) does six things:
  - fail every pending request with `ConnectionLost`;
  - close the socket;
  - **release the subscription-owned pane cache**: `local.seed_pane_cache({})`,
    before any fallback capture runs. In a subscribed mode the local cache holds
    only seeded entries, because the local instance does no discovery and
    `discover_window_panes*` never writes the cache. Clearing it wholesale is
    therefore exact. `_clean_stale` cannot do this job: it picks stale ids from
    `_last_content`, which seeded panes never entered. Until the first fallback
    discovery, the cache is empty, as on a cold in-process start. Every
    cache-backed accessor then takes its cache-miss route, which is the fail-safe
    one: a plain pane kill, never a window collapse;
  - switch to `FALLBACK`, so the UI keeps refreshing in-process with no frozen
    gap;
  - start the local control client;
  - start the reconnect loop.

  The reconnect loop calls `ensure` again, which starts a new server if the old
  one died: that is the "reconnect when the server restarts" path. It walks the
  backoff table and stays at its last entry (30 s). On success the client returns
  to `SERVER`, closes the local control client (its control-mode stream parse was
  the producer's main cost, per t2034_1), and resets the backoff.
- **Liveness.** After `ping_after` seconds with no server message, the client
  sends `set_pins` with its current pins as a ping. The request is idempotent,
  and the result arrives within one tick. With no result within `ping_timeout`,
  the connection is treated as lost. This detects a hung but alive server
  independently of the configurable tick interval (1–60 s), and the spec already
  says clients fall back in that case.
- **Generation token.** The client owns `capture_generation`, a counter bumped by
  every capture call and by every mode switch.
  - `capture_all_classified_async()` returns `(token, payload)`, and
    `commit_snapshots(token, payload)` returns `None` unless `token` is still
    current.
  - The payload is mode-tagged. In fallback it wraps the local
    `(gen, classified)` and commits through `local.commit_snapshots`. In server
    mode it carries the state's snapshots.
  - A call that straddles a mode switch is discarded, the same "superseded → skip"
    contract the apps already handle.
  - `capture_all_async()` = classified + commit.
- **Server-mode capture semantics.**
  - `capture_all*` **reads** the current state. It never sends `refresh`, or N
    clients would be back to N scans.
  - `request_refresh(panes=None, shadows=None) -> int | None` sends `refresh` and
    returns the `gen`. It is a no-op returning `None` in fallback. t2037_3 calls it
    from the keypress refresh sites.
  - `capture_pane_classified_async(pane_id)` sends `refresh{panes:[id]}`. It then
    returns `(token, pane, snap, None)` from the state, which already applied that
    generation because results follow their delta. `commit_snapshot` returns that
    snap if the token is current. `pane` is `None` when the record is gone or the
    request failed, which is what the apps already skip.
  - `refresh_shadow_snapshot(id)` sends `refresh{shadows:[id]}` and returns
    `get_shadow_snapshot(id)`.
  - `capture(pane_id, lines) -> str | None` is the wire `capture{}`. It is offered
    for t2037_4, while `capture_pane_content_async` stays local, as t2037_3
    requires for the review loop.
- **Sync accessors in server mode.**
  - Records are converted with `sp.pane_snapshot` once per generation and cached.
  - `get_pane(id)` reads `panes[id].pane` and never shadows (cache-boundary
    invariant).
  - The session mapping is `{s: Path(root)}`.
  - Compare mode, override and last change come from the record. An unknown pane
    falls back to `local.get_compare_mode(id)`, `False` and `None`.
  - `control_state()` returns `TmuxControlState(value)`, or the raw string for an
    unknown open value, which compares unequal to every enum member, so no badge
    is shown.
  - The discovery accessors rebuild today's shapes from `discovery`: a frozenset
    of sessions, a frozenset of `(s, w)`, and `{(s, w): [(id, pid, dead)]}`.
- **Compare mode.** The authoritative paths are `async set_compare_mode_async` and
  `async cycle_compare_mode_async`, which return `(mode, following_default)` from
  the server's `result`.
  - The sync `cycle_compare_mode` / `set_compare_mode` that the apps call today
    still work in server mode. They schedule the request and return a
    **prediction** from the record: default → raw → stripped → default. When the
    prediction is "back to default", the default is the record's mode if it is not
    overridden, else `local.compare_mode_default`.
  - The next delta corrects the record. The docstring says so, and the t2037_3
    handoff names the async variant as the one to switch to.
  - In fallback both delegate.
  - In `REPLAY` the replayer answers `unavailable`. The async variants raise
    `ReplayReadOnly`. The sync ones send nothing and return the record's current
    `(mode, not override)`.
- **Pins.**
  - `set_capture_pins(pins)` accepts a frozenset of pairs or `CAPTURE_PIN_ALL`.
    It stores them, and in server mode sends `set_pins` only when the value
    changed. They are always included in every (re)subscribe.
  - `set_parked_agents(skip)` delegates in fallback and is ignored in server mode,
    because the server computes the skip set from pins.
  - Wiring the mixin's `_publish_parked_agents` to also call `set_capture_pins` is
    t2037_3's job, and the handoff note says so.
- **Content.** `set_content(selection)` stores the selection. In either subscribed
  mode, **`REPLAY` included** (the replayer answers `set_content` with a current
  snapshot under the new selection), it sends `set_content{id}` and returns once
  the reply snapshot is applied. In `FALLBACK`/`CONNECTING` it only stores the
  selection, which the next (re)subscribe carries. A record without content converts to `""`, as `pane_snapshot`
  already does.
- **Listeners.** `add_update_listener(cb)` → `cb(Applied)` after every applied
  message, and `add_mode_listener(cb)` → `cb(ClientMode)`. Exceptions are caught
  and passed to `log`. This lets t2037_3 render on push. Nothing requires it.
- **Delegation.**
  - `__getattr__` is called only for names the class does not define.
  - In fallback (and while connecting) it delegates everything to `local`.
  - In server mode it delegates **only** the `GATEWAY_NAMES` allowlist above, and
    raises `AttributeError("MonitorClient: <name> is producer state, not served by the subscription")`
    otherwise. An unlisted producer read fails loudly instead of silently
    returning the empty local state. `getattr(monitor, x, None)` probes still
    behave.
  - In replay mode, gateway names raise `ReplayReadOnly(AttributeError)`, because
    fixture pane ids must never reach the user's real tmux.
- **Replay.**
  - `replay=<path or Recording>` → `start()` makes `tempfile.mkdtemp(prefix="ait-replay-")`
    (a short path, for `sun_path`). It runs `ReplayServer(recording, <dir>/r.sock, speed=replay_speed)`
    on the running loop and connects through the same handshake and subscribe
    code → `REPLAY`.
  - No fallback and no reconnect. A failure leaves `mode=REPLAY` disconnected,
    with `last_error` set and listeners told.
  - `close()` closes the server and removes the directory.
- **`close()`** (aliased by `close_control_client()`) cancels the reader, ping and
  reconnect tasks, fails pending requests, closes the socket, releases the seeded
  pane cache (subscribed modes), and closes the local control client. It is
  idempotent.
- **Logging.** Only through the injected `log` callable. Never stderr, because the
  client lives inside Textual apps.

## Implementation

### Pre-phase (risk mitigations)
1. [inventory_monitor_surface] Create `tests/test_monitor_client_surface.py` **before** `status_client.py` exists.
   - It extracts, with `ast` and not regex, so comments and strings do not count:
     - every attribute access on `self._monitor` in `monitor/monitor_app.py`,
       `monitor/minimonitor_app.py`, `monitor/monitor_shared.py` and
       `monitor/review_loop.py`;
     - every attribute access on the monitor attribute in `applink/router.py` and
       `applink/pusher.py`. Resolve that attribute's real name by reading those
       files first.
     - `getattr(<monitor>, "<name>", …)` probes in the same files.
   - Completeness cross-check: the extracted set must include the names already
     inventoried in this plan's "Read surface" section (for example
     `capture_all_async`, `get_shadow_snapshot`, `kill_agent_pane_smart`,
     `last_discovered_agents`), so a broken extractor fails rather than passing
     vacuously.
   - It asserts that each name is either defined on `status_client.MonitorClient`
     (a class attribute, method or property) or a member of
     `status_client.GATEWAY_NAMES`.
   - Run it and confirm it fails red because the module is missing. It turns green
     at the end of step 2, and later catches any new app call site that would raise
     in server mode.

1. **`monitor_core.py` — additive seam `TmuxMonitor.seed_pane_cache(panes)`.**
   - It rebinds `self._pane_cache = dict(panes)` (`pane_id → TmuxPaneInfo`).
   - Its docstring says it is only for a subscription-backed client whose producer
     runs elsewhere. Callers pass agent-facing panes only, never shadows
     (cache-boundary invariant), and it is never mixed with this instance's own
     discovery.
   - **The caller owns the release.** `seed_pane_cache({})` empties the cache. The
     docstring states that `_clean_stale` does not reap seeded entries, because it
     iterates `_last_content`. So a caller leaving subscription mode must release
     the cache before the instance does its own discovery. The client does this in
     `_lost` and `close()`.
   - In-process callers never call it, so their behaviour is unchanged.
   - Before editing, check that `monitor_core.py` is clean against both HEAD and
     the index (`git diff --quiet HEAD -- <f>`), because other sessions edit this
     file.
2. **New `.aitask-scripts/monitor/status_client.py`.**
   - It uses the same dual import shim as `status_server.py`, and imports
     `status_protocol as sp`, `status_server` (for `ensure_server` and
     `framework_version`), `status_recording` (for `ReplayServer`) and the
     `monitor_core` names it needs.
   - It is headless and does not import Textual.
   - Contents:
     - `ClientMode`, `ConnectionLost`, `ReplayReadOnly`;
     - the `GATEWAY_NAMES` and `READ_SURFACE_NAMES` frozensets;
     - `pins_to_wire`;
     - `class MonitorClient`, with everything in "Design decisions";
     - `class _Link`: one connection, made of a reader, a writer, a pending-id map
       (integer ids from `itertools.count(1)`) and a write lock. It provides
       `request(msg, timeout) -> dict` and `run_reader()`.
3. **Spec — `aidocs/framework/monitor_status_protocol.md`.**
   - Add a "Python client" section in current-state prose, covering: the three
     modes and the `AITASKS_MONITOR_SERVER=0` opt-out; the connect deadline and
     the in-process fallback; fallback while the reconnect loop backs off, and the
     return to server mode; the `set_pins` liveness ping; that a reply snapshot resolves
     the request carrying its `id`, and gap recovery resubscribes as a bounded request
     outside the reader; that an error or a missed deadline on any
     snapshot-answered request fails the connection; that the seeded pane cache is released when the client
     leaves a subscribed mode; `set_content` in replay; that capture reads the
     state and `request_refresh` triggers a scan; the client-owned generation
     token; seeding the gateway's pane cache; replay mode being read-only; and that
     projection stays with the app.
   - Add `status_client.py` names to the codec reference.

### Post-phase (risk mitigations)
1. [live_client_reconnect] Add `tests/test_monitor_status_client_live.py`, which runs against a real isolated tmux server.
   - Setup and teardown:
     - Copy `LiveCase`'s environment pattern from
       `tests/test_monitor_status_server_live.py`: `-L ait_t2037_2_<pid>_<n>`, plus
       scratch `TMUX_TMPDIR`, `XDG_RUNTIME_DIR`, `HOME` and
       `AITASKS_AGENT_MARKS_FILE` under one short scratch directory.
     - Apply it in-process with `unittest.mock.patch.dict(os.environ, …)`, because
       `ensure_server` and `TmuxClient` read the environment at call time, and the
       spawned server inherits it.
     - Skip only when `tmux` is missing.
   - The test:
     1. Create one session in a temporary project with an `agent-pick-1` window
        running a printer loop.
     2. Build `MonitorClient(TmuxMonitor(), kind="test", connect_deadline=20)` and
        start it.
     3. Assert `SERVER`, and that `capture_all_async()` contains the agent pane.
        Record `server_info["pid"]`.
     4. Send SIGTERM to that pid, but only if `/proc/<pid>/cmdline` contains the
        scratch path.
     5. Wait for `FALLBACK`. While in fallback, `capture_all_async()` still
        returns the agent pane.
     6. Wait for `SERVER` again with a different server pid.
     7. Assert the agent pane is present.
   - Cleanup: `close()` the client. Signal only the server pids collected from
     `server_info`, after the same `cmdline` ownership check. Kill the tmux server
     by its explicit `-L` name only.
   - If this proves timing-sensitive under the xdist lane, add it to the runner's
     serial carve-out and to the CLAUDE.md list in the same commit.

## Tests — new `tests/test_monitor_status_client.py` (unittest, `IsolatedAsyncioTestCase`)

These tests reach no tmux server. Two kinds of server are used:
- **`ScriptedServer`**: a real asyncio Unix server whose lines the test writes by
  hand (`sp.encode` with `direction=SERVER`, raw bytes for the malformed cases).
  It records what it receives. Use it for the protocol edges.
- **Real `StatusServer`**: built over `FakeProducer` / `FakeMarks` /
  `FakeTaskCache`, reached through `import test_monitor_status_server as fx`. Only
  the module alias is imported, so pytest collects no foreign `TestCase` classes.
  Use it for integration.

The local instance is a `FakeLocal` that records calls (`capture_all_async`,
control start and close, `set_parked_agents`, gateway calls). The pane-cache test
uses a real `TmuxMonitor()`, which is side-effect free to construct.

Cases:
- **Subscribe and snapshot.** After `start()` the mode is `SERVER`.
  - The client sends `hello` (with kind, pane and pid) and then `subscribe` (with
    content, include_shadows and pins).
  - `capture_all_async()` equals the snapshot's records, compared via
    `pane_snapshot`.
  - These all reflect the snapshot: `get_shadow_snapshot`, `get_pane`,
    `get_session_to_project_mapping[_async]` (`Path` values), compare mode,
    override, last change, `control_state()` as an enum (and an unknown string
    passed through), and the three discovery accessors.
  - `FakeLocal` saw no capture and no control start.
- **Delta.** A patch, a removal, a new full record and a top-level replace all
  apply. An update listener gets an `Applied` with the changed ids.
- **Stale gen dropped.** After gen 5, a delta at gen 5 and one at gen 3 leave the
  state unchanged, fire no listener, and do not bump `capture_generation`.
- **Request/reply completion, through the real reply path.** Each request is
  given a 1 s timeout and must return well inside it, so a resolve that only
  happens on timeout fails the test.
  - Initial `subscribe` against the real `StatusServer` returns the snapshot.
  - `set_content([...])` against the real server returns with the state already
    under the new selection.
  - A scripted server that answers `subscribe` with a snapshot whose `id` does not
    match leaves the request pending until its timeout. This negative control
    proves the completion is keyed on `id`.
- **Gap → resync, never awaited in the reader.** The scripted server sends a
  snapshot at gen 1, then a delta at gen 3.
  - The client sends exactly one `subscribe{id}`.
  - The server then sends a delta at gen 4 (dropped, with no second subscribe),
    the reply snapshot with that `id` at gen 5, and a delta at gen 6.
  - Final `state.gen == 6`. The reader stayed alive throughout, shown by a later
    delta still applying.
- **Resync answered by a matching error.** After a gap the scripted server answers
  the resync `subscribe` with `error{code:"internal", id}` and keeps sending deltas.
  The client calls `_lost`, goes to `FALLBACK` and starts the reconnect loop,
  within the test's `resync_timeout`. The deltas after the error are never
  applied.
- **Resync with no matching snapshot while traffic continues.**
  - After a gap the scripted server never sends the reply snapshot. It keeps
    sending deltas and answers every `set_pins` ping with a `result`
    (`ping_after=0.05`, `resync_timeout=0.3`).
  - The client still goes to `FALLBACK` once `resync_timeout` expires. Traffic and
    successful pings do not keep the frozen state alive.
- **`set_content` answered by an error** → connection lost and `FALLBACK`.
  `set_content()` returns `False`.
- **Malformed line / framing error / error reply to subscribe → fallback.**
  - The mode becomes `FALLBACK`, `capture_all_async` delegates to `FakeLocal`, and
    the local control client was started.
  - The reconnect loop calls `ensure` again. A healthy server returns the client
    to `SERVER`, the local control client is closed, and the backoff resets.
- **Server restart → reconnect** (real `StatusServer`):
  - subscribe;
  - `close()` server A;
  - the client goes to `FALLBACK`;
  - server B starts on the same path, holding different `FakeProducer` snaps;
  - the client is back in `SERVER` and `capture_all_async` shows B's panes.
- **Unreachable → fallback.** The fake `ensure` returns
  `UNAVAILABLE:no_tmux_server`. Then the mode is `FALLBACK`, every read surface
  call delegates, and `set_parked_agents` reaches `FakeLocal`.
  - `version_mismatch` from the server also → fallback.
  - `AITASKS_MONITOR_SERVER=0` → `ensure` is never called.
- **Hung server.** The scripted server sends a snapshot and then stops answering,
  using `ping_after=0.05` and `ping_timeout=0.1`. The client sends `set_pins` and
  then falls back.
- **Generation token.**
  - Two overlapping `capture_all_classified_async` calls: the first one's commit
    returns `None`.
  - A capture started in fallback that completes after the switch to `SERVER`
    commits `None`.
- **Fast preview.** `capture_pane_classified_async(id)` sends `refresh{panes:[id]}`
  to the real server, and the commit returns the refreshed record.
  `refresh_shadow_snapshot` sends `refresh{shadows}`. With the request pending,
  dropping the connection gives `pane is None` and no exception.
- **Pins.**
  - `set_capture_pins` sends one `set_pins`. The same value again sends nothing.
  - `CAPTURE_PIN_ALL` → `"all"`.
  - A reconnect's `subscribe` carries the current pins.
  - A real server's skip set reflects them (via `FakeProducer.skip`).
- **Compare mode.**
  - `cycle_compare_mode_async` returns the server's `(mode, following)`.
  - The sync `cycle_compare_mode` returns the prediction (default → raw) and the
    request reaches the server. After the next delta, `get_compare_mode` reports
    the server's value.
- **Content.** `set_content(["%1"])` → the reply snapshot is applied, and other
  panes' content is `""`.
- **Pane-cache seeding.** With a real `TmuxMonitor` as `local`, a pane from the
  snapshot is in `local.get_pane()`, a shadow is not, and a pane removed by a delta
  is gone.
- **Seeded cache released on fallback.**
  - Seed an agent pane and a TUI pane (`category: tui`, a `tui_names` window).
  - Drop the connection, so the client goes to `FALLBACK`. Before any local
    discovery, `local.get_pane(id)` is `None` and `local.get_running_tuis()` is
    empty.
  - Negative control, pinning why the release is needed: on a bare `TmuxMonitor`,
    `seed_pane_cache({id: pane})` followed by `_clean_stale(set())` leaves `id`
    cached.
  - `close()` releases the cache too.
- **Delegation.**
  - In server mode, a gateway name reaches `FakeLocal`, and a non-allowlisted
    producer name (e.g. `discover_panes_async`) raises `AttributeError`.
  - In fallback, the same name delegates.
  - `getattr(client, "nonexistent", None)` is `None`.
- **Replay** (`replay=tests/fixtures/monitor_status/basic.jsonl`, `replay_speed=0`):
  - the mode is `REPLAY`;
  - after playback, `capture_all_async()` equals the final reconstructed state from
    `sr.read_recording` applied to a `StreamState`;
  - `server_info["impl"] == "replay"`;
  - `ensure` is never called;
  - a gateway call raises `ReplayReadOnly`;
  - `close()` removes the temporary directory.
  - **Content selection in replay.** Start with `content="none"`, so every record
    has `""` content. Then `set_content(["%1"])`. After it returns, `%1`'s content
    equals the recording's reconstructed content for `%1`, and other panes stay
    `""`. `local=None` throughout, so no tmux can be reached.
  - **Compare mode in replay.** `cycle_compare_mode_async` raises
    `ReplayReadOnly`, and the sync form returns the record's current mode.
- **close()** is idempotent, leaves no pending tasks, and fails pending requests.

## Verification

```bash
python3 tests/test_monitor_client_surface.py        # [inventory_monitor_surface]
python3 tests/test_monitor_status_client.py
python3 tests/test_monitor_status_client_live.py    # [live_client_reconnect]
python3 tests/test_monitor_status_server.py         # fixtures imported by alias still pass
python3 tests/test_monitor_status_protocol.py       # spec tables unchanged
python3 tests/test_monitor_producer_seams.py        # producer characterization unchanged
python3 tests/test_monitor_client_agnostic.py
bash tests/test_no_raw_tmux.sh                      # client reaches tmux only via TmuxMonitor
set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -3   # read the last line
```

## Risk

### Code-health risk: medium
- Delegating through `__getattr__` is an implicit contract between the client and every app call site. If a producer read is missing from both the read surface and the gateway allowlist, it raises in server mode only. That shows up only once t2037_3/4 wire the client in, as a TUI crash in one mode · severity: low (residual — addressed by inline pre-phase inventory_monitor_surface) · → mitigation: inline pre-phase inventory_monitor_surface
- The background task set on the app's loop (reader, ping, reconnect loop, local control-client start and close) could leak tasks, or start the local control client twice across rapid mode flips · severity: medium · → mitigation: covered in-plan (close-idempotency, reconnect and mode-flip tests)
- The new `seed_pane_cache` seam sits on the action path (kill window collapse, switch, raw captures). A wrong seed, such as a shadow or a stale pane, would change action behaviour. A seed left behind after fallback would survive, because `_clean_stale` reaps from `_last_content` only · severity: low · → mitigation: covered in-plan (seeding test; caller-owned release in `_lost`/`close()`, with a test for a seeded pane disappearing before fallback discovery and a `_clean_stale` negative control)
- Request/reply plumbing: snapshot replies resolving their `id`, and gap recovery as a bounded request outside the reader. A wrong completion path would stall subscribe, `set_content` or resync. An unbounded resync would freeze the state while traffic and pings continue · severity: low · → mitigation: covered in-plan (real-reply-path tests with short timeouts, an id-mismatch negative control, the gap sequence test, the matching-error and no-snapshot-while-traffic-continues resync cases, and the `set_content` error case)

### Goal-achievement risk: low
- The `ensure` → detached spawn → reconnect lifecycle is tested only against in-process servers and a fake `ensure`. These are unproven:
  - the real path: `ensure_server` in a worker thread under a running loop, spawning the real `serve` process;
  - "reconnect when the server restarts" against a killed real server.

  · severity: low (residual — addressed by inline post-phase live_client_reconnect) · → mitigation: inline post-phase live_client_reconnect
- In server mode the sync `cycle_compare_mode` returns a prediction, which can disagree with the server's answer for one tick when the session's default differs from the app's · severity: low · → mitigation: covered in-plan (authoritative async variants; t2037_3 handoff)

### Planned mitigations
- timing: pre-phase | name: inventory_monitor_surface | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — implicit __getattr__ delegation contract vs app call sites | desc: ast-based tripwire asserting every monitor attribute the apps/applink use is served by MonitorClient or allowlisted as gateway
- timing: post-phase | name: live_client_reconnect | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: low | addresses: goal-achievement — real ensure/spawn/reconnect lifecycle unproven | desc: live isolated-tmux test: client reaches SERVER, server SIGTERMed, FALLBACK, back to SERVER with a new pid

## Step 9 (Post-Implementation)

- Commit the code as `feature: Add the MonitorClient with fallback and replay modes (t2037_2)`.
- Commit the plan with `aitask_task_commit.sh` and archive through Step 9.
- At Step 8e, re-check the dependents (`grep xdeps` in aitasks_go) and send the
  cross-repo note the inbox suggested to aitasks_go#16_5. It should cover the
  client API, replay mode, how to start a server for a demo (`status_server.py
  ensure`), the test and fixture paths, and the commit.
- Send t2037_3 a note covering the pins wiring, `request_refresh` at the keypress
  sites, the async compare-mode variants, `AITASKS_MONITOR_SERVER=0` for
  both-mode tests, and the CLI-override caveat: in server mode the server uses
  each session's `project_config.yaml`, not the app's command-line overrides.
