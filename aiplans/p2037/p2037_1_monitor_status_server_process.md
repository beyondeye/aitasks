---
Task: t2037_1_monitor_status_server_process.md
Parent Task: aitasks/t2037_python_monitor_status_server.md
Sibling Tasks: aitasks/t2037/t2037_2_monitor_status_client.md, aitasks/t2037/t2037_3_monitor_minimonitor_subscribe.md, aitasks/t2037/t2037_4_applink_subscribe_status_server.md
Archived Sibling Plans: aiplans/archived/p2037/p2037_*_*.md
Base branch: main
Output branch: main
---

# t2037_1 — Monitor status server process and lifecycle

## Context

`ait monitor`, every `ait minimonitor` and applink each run their own
`TmuxMonitor` scan. On the host t2034_1 measured, about 42 scanners drove the
tmux server to 65–73 % of a core. t2034_2 made `TmuxMonitor` a client-agnostic
producer. t2034_3 specified the wire (NDJSON over a Unix socket, snapshot plus
one delta per generation) and shipped its codec (`monitor/status_protocol.py`)
and a recorder/replayer (`monitor/status_recording.py`).

This task builds the **server process** that owns ONE `TmuxMonitor` per (tmux
server, framework `VERSION`) and serves that protocol. It also builds the `ensure`
entry point clients use to reach or start it. Clients and consumers (t2037_2–4)
are out of scope. Nothing in the framework calls the server yet, so the change
does not alter any existing user-visible behaviour.

**Producer changes are needed, and every one is additive.** The parent says to
reuse `monitor_core` unchanged. But two things this child requires cannot be done
from outside the producer:

- **Per-session config.** `TmuxMonitor` holds one `capture_lines`,
  `idle_threshold`, `agent_prefixes`, `tui_names` and `compare_mode_default`.
- **`%exit`.** `TmuxControlClient._reader_loop` breaks on `%exit` silently, so
  nothing outside it can see that it happened.

Each new seam falls back to the existing instance attributes when nothing has been
published. The in-process monitor, minimonitor and applink therefore behave
exactly as before.

Notes received (advisory, from t2034_1/2/3 on the parent): use `StreamEncoder` /
`filter_message` / `monitor_pane_record` / `read_line` (open the reader with
`limit=MAX_CLIENT_LINE_BYTES`; `FramingError` → `too_long` + close). Keep one
ordered outbound queue per connection (the `_ReplayConnection` model). Compute
`completed`, the global `parked` set and the skip set (`parked_capture_skip` over
every subscriber's pins). Publish the skip set before each capture. Keep
compare-mode overrides shared. A pane whose capture failed is `removed` for that
generation. Fill the spec's "Lifecycle and socket path" placeholder; the Go twin
(aitasks_go#47_1) mirrors it.

## Design decisions

- **Socket key.** The client asks the tmux server for its socket path through the
  gateway: `TmuxClient().run(["list-sessions", "-F", "#{socket_path}"])`, using
  the first line, which must be an absolute path. This is the same probe
  `lib/tmux_bootstrap.sh` and `spawn_sitrep` use. It is authoritative under
  `-L <name>`, the `AITASKS_TMUX_SOCKET=""` ambient-`$TMUX` case, and
  `TMUX_TMPDIR`.
  - A non-zero rc means **no tmux server**, and `ensure` answers
    `UNAVAILABLE:no_tmux_server`. There is nothing to monitor.
  - Key = `sha256(socket_path)[:16]`.
  - VERSION is kept verbatim if it matches `[A-Za-z0-9._+-]{1,64}`. Otherwise it
    becomes `v` + sha256[:12].
- **Paths.** The directory is `$XDG_RUNTIME_DIR/aitasks/` when that variable is an
  existing directory, else `~/.aitask/run/`. It is created with mode 0700, then
  re-checked with `lstat`: it must be a real directory, owned by our uid, with
  `mode & 0o077 == 0`. A directory we own that fails the mode check is
  `chmod 0700`'d. Anything else is refused (`UNAVAILABLE:unsafe_runtime_dir`).
  Files in it:
  - `monitor-<key>-<ver>.sock`
  - `monitor-<key>-<ver>.lock`
  - `monitor-<key>-<ver>.log` (server stderr, truncated on each start)

  A socket path longer than 103 bytes (the macOS limit) is refused with
  `UNAVAILABLE:socket_path_too_long`.
- **Lock = "a server (or its starter) is alive".** An exclusive `fcntl.flock`
  covers the `.lock` file.
  - `ensure` takes it non-blocking, retrying until a deadline (default 10 s) and
    probing the socket between tries.
  - Once it holds the lock, nobody else can be running. Any leftover `.sock` is
    therefore stale and is unlinked, but only after an `lstat` shows it is a
    socket owned by us (`S_ISSOCK`).
  - `ensure` then spawns the server with `pass_fds=(lock_fd,)` and `--lock-fd N`.
    The child shares the open file description, so the lock stays held for the
    server's whole life after `ensure` closes its own fd. Never `LOCK_UN`: that
    would release the child's lock too.
  - A server started by hand without `--lock-fd` takes the lock itself
    (non-blocking) and exits `ALREADY_RUNNING` on failure.

  Double start is impossible. A hung-but-alive server keeps its lock and is never
  replaced, so clients fall back in-process: the fail-safe direction.
- **Detached start.**
  `subprocess.Popen([sys.executable, <status_server.py>, "serve", "--socket", P, "--lock-fd", N, "--version", V, "--tmux-socket-path", S, "--session", <caller session or "">, "--project-root", R], start_new_session=True, stdin=DEVNULL, stdout=log, stderr=log, close_fds=True, pass_fds=(N,))`.
  `start_new_session` is `setsid`. `ensure` polls the probe every 50 ms until a
  `welcome` arrives. The server binds before it starts the control client
  (background task), so readiness is not delayed by the backend's ~14 s worst
  case.
  - The child exits before answering → `UNAVAILABLE:server_failed:<last log line>`.
  - The deadline passes → `UNAVAILABLE:start_timeout`.
- **Server self-checks at start.** The server refuses to start if a `hello` to the
  path already answers, or if its own `list-sessions` socket path differs from
  `--tmux-socket-path`. The second check means a server is never keyed under
  another tmux server's socket.
- **One producer operation at a time.** An `asyncio.Lock` (`_producer_lock`)
  serializes every operation that captures or that changes capture inputs:
  - every full tick, every `refresh`, and every `%exit` control-client restart;
  - **`set_compare_mode` / `cycle_compare_mode`**, because
    `capture_all_classified_async` reads each pane's mode on the loop (~L3647)
    and then awaits the offloaded classify. A `set_compare_mode` in that window
    clears `_last_content`, and the in-flight commit then writes an old-mode
    baseline while records report the new mode. The next unchanged capture would
    then see a change and reset the idle clock. Under the lock, the mode change
    lands strictly between two captures. Its `result` waits at most one tick.
  - **`set_pins`**, which republishes the skip set (below).

  Without the lock, a single-pane `capture_pane_classified_async` would also
  reserve a newer capture generation and make a full tick's `commit_snapshots`
  return `None`. `capture` neither reserves a generation nor changes inputs, so it
  runs outside the lock.
- **The skip set is republished before every capture, not only per tick.**
  `capture_pane_classified_async` refuses a parked pane by reading the
  previously published `_parked_agents` (`_is_parked_pane`). So `_publish_skip_set()`
  runs under the producer lock:
  - at the start of every tick (step 6 below);
  - **at the start of every partial `refresh`**, before its captures;
  - inside `set_pins` (and inside a `subscribe` that carries `pins`).

  It recomputes `marks_view.refresh()`, then
  `global_parked = parked_session_windows(marks_view.parked_windows(), self._mapping)`,
  using the last tick's session→root map, and then
  `monitor.set_parked_agents(parked_capture_skip(global_parked, current subscribers' pins))`.

  Two consequences:
  - A `set_pins` that pins a parked agent, followed at once by
    `refresh{panes:[id]}`, captures that agent live.
  - A removed pin takes effect on the very next capture.

  A connection that disconnects republishes too, so its pins stop protecting
  agents at once.
- **Broadcast is a synchronous section.** Two operations each run with no `await`
  in between, which is the asyncio equivalent of the spec's lock held across
  "read state + enqueue":
  - `encoder.update(frame)` followed by putting the filtered delta on each
    subscriber's queue;
  - `encoder.snapshot(...)` followed by putting the reply on the requester's
    queue.

  Every reply snapshot therefore falls between two deltas, and `result{refresh,
  gen}` is enqueued after the delta that carries its `gen`. The full-view bytes
  are encoded once per commit and shared. Restricted views are encoded per
  connection.
- **Tick cadence.** Ticks run only while there is ≥1 subscriber.
  - Interval = the minimum `tmux.monitor.refresh_seconds` over the mapped
    sessions' project configs, clamped to [1, 60], default 3.
  - `load_monitor_config` does **not** return `refresh_seconds`; the value lives
    in `tmux.monitor.refresh_seconds`. The apps read it via
    `load_project_tmux_config(root).get("monitor", {}).get("refresh_seconds", 3)`
    (`monitor_app.py` ~L4034). So the server's per-root config cache,
    `ProjectConfigCache.get(root) -> ProjectConfig(monitor: dict, refresh_seconds: float | None)`,
    loads it separately through `load_project_tmux_config(root)`.
  - **The default is resolved per project before the minimum**, matching
    `monitor_app`, which defaults each project's missing setting to 3.
    `ProjectConfig.refresh_seconds` is therefore always a number. It is the
    configured value when that value is an `int`/`float` (not `bool`), finite and
    `> 0`, else `3.0`. That covers a missing key, a missing file, and an invalid
    value.
  - Only `.monitor`, the `load_monitor_config` shape, ever reaches
    `set_session_configs`. No unsupported key reaches `TmuxMonitor`.
  - `tick_interval(configs) = clamp(min(c.refresh_seconds for every mapped project) if any mapped else 3, 1, 60)`.
    So project A at 7 and project B unset gives 3, not 7. The interval is
    recomputed after each tick, and the scheduler sleeps the current value.
  - A `subscribe` (first or resync) whose last commit is older than one interval,
    or that comes before any commit, first runs a tick under the producer lock.
    The connection then gets a fresh snapshot, not a stale one, after an idle
    period.
- **Tick body**, all under the producer lock:
  1. Get the session→root map: `mapping = await get_session_to_project_mapping_async()`.
  2. Publish per-session config with
     `monitor.set_session_configs({s: cache.get(root).monitor})`. The
     `ProjectConfigCache` entry for a root holds `load_monitor_config(root)` plus
     the separately loaded `refresh_seconds`, keyed on `project_config.yaml`
     `(st_mtime_ns, st_size, st_ino)`. A missing file is cached as the defaults
     with `refresh_seconds=3.0`.
  3. Update the task cache: `task_cache.update_session_mapping(mapping)`, and
     store `self._mapping = mapping`.
  4–6. Run `_publish_skip_set()`: marks refresh, global parked set, then
     `set_parked_agents(parked_capture_skip(...))`. This must happen **before**
     the capture.
  7. Capture: `gen, classified = await capture_all_classified_async()`.
  8. Commit: `snaps = commit_snapshots(gen, classified)`. `None` is logged and the
     commit skipped. It cannot happen under the lock.
  9. Store `snaps` as the current agent map and build the frame:
     - `panes = {id: monitor_pane_record(monitor, s)}`;
     - `shadows = {k: monitor_pane_record(monitor, s) for k, s in monitor.shadow_snapshots().items()}`;
     - `completed`;
     - `sessions_member(mapping)`;
     - `parked = global_parked`;
     - `discovery_member(last_enumerated_sessions(), last_discovered_agents(), last_discovered_panes())`;
     - `control_state().value`.
  10. Broadcast.

  A tick that raises is logged to stderr and produces no commit. The server stays
  up.
- **`completed`.** AGENT panes that are not parked or frozen in their snapshot
  **and** whose `(session, window)` is not in the global parked set, whose task
  (`task_cache.get_task_id_for_pane`) satisfies `is_task_completed(get_task_info(id, session))`.
  The global-set clause keeps it client-independent: a pane pinned live by one
  subscriber is still parked for everyone else. The spec text is updated to say
  so.
- **`refresh` request.**
  - With no members it runs a full tick.
  - Partial refreshes (`panes` / `shadows`) first run `_publish_skip_set()`
    under the producer lock.
  - With `panes`, each pane is captured with `capture_pane_classified_async` +
    `commit_snapshot`. A non-`None` result is merged into the current agent map.
    A failed capture leaves the prior record, which is the in-process fast-preview
    rule.
  - With `shadows`, each followed pane gets `refresh_shadow_snapshot`.

  Then the frame is rebuilt (other members carried over), committed, broadcast,
  and answered with `result{request:"refresh", gen}`. Records the refresh did not
  touch keep their last-captured values in that generation. The spec records
  this as a known limit.
- **`set_compare_mode` / `cycle_compare_mode`.** The pane must be in the current
  agent map, else `not_found`. The call goes to the producer **under the producer
  lock**, and the reply is `result{mode, following_default}`. The change reaches every client in the next
  delta, as the spec says.
- **`capture`.** The pane is resolved from the current agent map, or from a shadow
  record whose `pane.pane_id` matches (rebuilt via `pane_snapshot(...).pane`).
  Then `capture_pane_content_async(pane_id, capture_lines=lines, pane=pane)` runs,
  and the reply is `result{pane, content: tail_lines(content, lines)}`. A miss is
  `not_found`; a failed capture is `unavailable`.
- **Connections.**
  - The protocol state machine follows `_ReplayConnection`: hello gate,
    version/proto gate, `set_content` requires subscribe, unknown types answer
    `unknown_type`, `bad_message` keeps the connection after the handshake.
  - `hello` gets a welcome with `server:{impl:"python", pid}`. A wrong proto or
    version is answered with `proto_mismatch` / `version_mismatch` and the
    connection is closed.
  - A connection that has not completed `hello` within 10 s is closed.
  - `set_pins` before `subscribe` is stored. Pins count only while the connection
    is subscribed.
  - The outbound queue is bounded at 128 messages. On overflow the connection is
    closed (logged), and the client reconnects and resyncs. The spec records this.
- **Exit conditions** (a watchdog task every 0.5 s):
  - The idle grace passes with zero subscribers (`--grace`, default 30 s,
    counted from start and from each drop to zero).
  - The socket path's inode is not the one we bound. Someone removed or replaced
    it, so we no longer own the address.
  - `monitor.control_exit_seen()` is true. This calls `_probe_tmux_alive()`
    (`list-sessions -F #{socket_path}` via the gateway in a thread):
    - Failure or a different path → exit.
    - Still alive → the `%exit` was a session detach (the attached session was
      killed). The server restarts the control client, under the producer lock,
      on a live mapped session: `close_control_client()`, set `monitor.session`,
      `start_control_client()`. With no mapped session left it stays on
      subprocess fallback.
  - SIGTERM/SIGINT.

  On exit the server stops accepting connections, closes them, closes the control
  client, unlinks the socket only if its inode is still ours, and returns. Process
  exit releases the lock.

## Implementation

### Pre-phase (risk mitigations)
1. [pin_producer_defaults] Before any `monitor_core.py` edit, create
   `tests/test_monitor_producer_seams.py` with a `NoConfigCharacterization`
   class that pins today's outputs:
   - `classify_pane(w)` for an `agent-`, a TUI, a `brainstorm-` and another
     window;
   - `_apply_bookkeeping(...).is_idle` just below and above `idle_threshold`,
     for an AGENT and a non-AGENT pane;
   - `_capture_args("%1")` and `_capture_args("%1", 50)`;
   - `get_compare_mode` for a cached agent pane, a shadow pane (not in
     `_pane_cache`), a pane with `session_name=""`, an undiscovered id, and an
     overridden pane;
   - each of the above on a monitor built with a non-default
     `compare_mode_default="raw"`, `idle_threshold=2.0`, `capture_lines=77`.

   Run it green on the unmodified tree. Keep it unchanged through steps 1–2 and
   run it again after them. It must stay green, and it must not be edited to
   pass.

1. **`monitor_core.py` — per-session config seam (additive).**
   - Add `self._session_configs: dict[str, dict] = {}` and
     `self._pane_sessions: dict[str, str] = {}` in `TmuxMonitor.__init__`.
   - Add `set_session_configs(configs)`. It rebinds the dict and never mutates it
     in place, with a docstring in the style of `set_parked_agents`.
   - Add `_cfg(session_name, key)`. It returns
     `self._session_configs.get(session_name, {}).get(key, getattr(self, key))`
     for `key` in `capture_lines | idle_threshold | agent_prefixes | tui_names | compare_mode_default`.
     An unknown, empty or `None` session falls through to the instance attribute.
   - `classify_pane(window_name, session_name=None)` uses `_cfg` for prefixes and
     TUI names. Pass the session at both discovery call sites: `session_name` at
     ~L2860 and `self.session` at ~L3062.
   - `_apply_bookkeeping` uses `_cfg(pane.session_name, "idle_threshold")`.
   - `_capture_args(pane_id, capture_lines=None, session_name=None)`: the default
     `n` comes from `_cfg(session_name, "capture_lines")`. `capture_pane`,
     `capture_pane_async` and `capture_pane_content_async` pass the pane's
     `session_name`.
   - `get_compare_mode(pane_id)` keeps its signature, because ~10 test fakes and
     both apps call it with an id only. The default becomes
     `_cfg(self._pane_sessions.get(pane_id), "compare_mode_default")`.
     `_pane_sessions` is filled for every discovered pane, agents **and
     shadows**, at the discovery site that refreshes `_pane_cache`, and is reaped
     in `_clean_stale`. A shadow therefore follows its own session's default.
   - Add `shadow_snapshots() -> dict[str, PaneSnapshot]`, returning a shallow copy
     of `_shadow_snapshots`. It is the public accessor the frame builder needs.
2. **`monitor_core.py` — `%exit` visibility (additive).**
   - `TmuxControlClient` gains `self.saw_exit = False`, set to `True` immediately
     before the `break` on `_EXIT_RE`.
   - `TmuxControlBackend` gains a sticky `threading.Event` `_exit_seen`. The
     supervisor sets it when the client it observed dying has `saw_exit` (Phase 2
     entry).
   - The backend gains a property `exit_seen` = event set **or** the current
     client's `saw_exit`.
   - `TmuxMonitor.control_exit_seen()` returns `False` with no backend, else
     `backend.exit_seen`. A fresh backend after `close_control_client()` /
     `start_control_client()` starts clear.
3. **Move `is_task_completed` into `monitor_core.py`** unchanged (pure, no Textual).
   `monitor_shared.py` re-imports it from there, so every existing importer
   (`monitor_app`, `minimonitor_app`, tests) keeps working. The server must not
   import `monitor_shared`, because that pulls in Textual.
4. **`status_protocol.py`.** Promote `status_recording._tail` to a public
   `tail_lines(content, lines)`, with its docstring and its "split on `\n` only"
   rule. `status_recording.py` uses `sp.tail_lines`. Behaviour is identical.
5. **New `.aitask-scripts/monitor/status_server.py`** (headless; stdlib + `monitor_core`,
   `status_protocol`, `lib/agent_marks`, `lib/tmux_exec`, `lib/framework_version`;
   uses the same dual import shim as `status_protocol.py`). Contents:
   - `RuntimePaths` dataclass and `runtime_dir()`, `tmux_socket_path(client=None) -> str | None`,
     `server_paths(socket_path, version) -> RuntimePaths`, `version_slug()`.
   - `async probe(sock_path, version, timeout=1.0) -> dict | None`. It sends
     `hello{kind:"probe"}` and returns the decoded welcome, or `None`. It **never**
     subscribes, so it never counts as a subscriber.
   - `ensure_server(*, version=None, session="", project_root=None, deadline=10.0, grace=None) -> EnsureResult(state, socket, pid, reason)`,
     where `state` ∈ `RUNNING|STARTED|UNAVAILABLE`. It is sync, implementing the
     algorithm above (run the async probe via `asyncio.run` in a helper), so
     t2037_2's client can call it from a worker thread. The stale-socket unlink
     and the spawn happen only while the lock is held.
   - `class StatusServer` with:
     - `__init__(monitor, *, socket_path, version, project_root, grace, lock_fd, clock=time.monotonic, probe_tmux=None)`.
       `monitor` is injected; `serve` builds the real `TmuxMonitor(session=…)` with
       default config. `probe_tmux` is the injectable liveness seam.
     - `async start()` binds with `asyncio.start_unix_server(..., limit=sp.MAX_CLIENT_LINE_BYTES)`.
       It records the bound inode, sets `os.umask`-independent `chmod 0600` on the
       socket, and starts the watchdog and the control-client task.
     - `async serve_until_exit()` returns the exit reason (`idle`, `exit_seen`,
       `socket_replaced`, `signal`).
     - `async close()`.
     - `_tick()`, `_refresh(...)`, `_commit(frame)`, `_build_frame()`,
       `_completed()`, `_publish_skip_set()`, `_restart_control_client()`,
       `tick_interval()`;
     - plus the module-level `ProjectConfigCache` / `ProjectConfig`.
   - `class _Connection`, modelled on `status_recording._ReplayConnection`: one
     bounded outbound queue, one writer task, `_next_line` with a closing event,
     `_send_error` with bounded echo fields, and the `_handle` dispatch for all
     eight request types.
   - CLI (`argparse`):
     - `serve …` prints `SERVING:<sock>` to stderr, then `EXIT:<reason>`. The exit
       code is 0 for a clean exit and `3` for `ALREADY_RUNNING`.
     - `ensure [--version V] [--session S] [--grace G] [--deadline D]` prints one
       stdout line: `RUNNING:<sock>|<pid>`, `STARTED:<sock>|<pid>` or
       `UNAVAILABLE:<reason>`. The exit code is 0 for the first two and 1 for
       the third.
     - `path [--version V]` prints the socket path, for debugging and tests.

   tmux is reached only through `TmuxMonitor` and `TmuxClient`
   (`tests/test_no_raw_tmux.sh` must stay green).
6. **Spec — `aidocs/framework/monitor_status_protocol.md`.**
   - Replace the "Lifecycle and socket path" placeholder with the current-state
     description of every decision above: path layout and key derivation, lock
     semantics, `ensure` states and reasons, detached start, idle grace, `%exit`
     handling (probe; restart on session detach), socket-inode watchdog, hello
     timeout, outbound bound, tick cadence and the pause with no subscribers.
     Name `status_server.py` and its CLI.
   - Also document:
     - the tick interval's source (`tmux.monitor.refresh_seconds`, 3 per project
       when missing or invalid, then the minimum over mapped projects, clamp
       [1, 60]);
     - that compare-mode requests and `set_pins` are serialized with captures, and
       a compare-mode `result` may wait up to one tick;
     - that pins take effect on the next capture, including a partial `refresh`.
   - In the `completed` bullet, add the global-parked clause.
   - In "Known limits", add the refresh-generation rule (untouched records keep
     their last-captured values) and drop the "not yet against the real producer"
     line only if the live recording test (below) lands.
   - Change the sentence "Until the status server exists (t2037), live recording is
     exercised against the replayer" to state that the recorder is exercised
     against both the replayer and the server.
   - Add `status_server.py` names to the codec reference.

   The spec stays free of version-history prose (documentation conventions).

### Post-phase (risk mitigations)
1. [record_live_server_stream] In `tests/test_monitor_status_server_live.py`,
   add `test_live_stream_records_and_checks`, which runs against the real server
   on the isolated socket.
   - Start one aitasks session with two `agent-…` panes running a looping
     printer.
   - Over at least 5 ticks: change one pane's output, bind a shadow
     (`@aitask_shadow_target`) to the other pane, open a new `agent-` window,
     and kill a pane.
   - Record with `status_recording.record_connect(..., max_deltas=N)` while
     driving those changes through `refresh` requests.
   - Assert that `check_recording` passes and the recording contains a `removed`,
     a new full record and a `shadows` entry.
   - Assert that the final `StreamState` equals a fresh `subscribe` snapshot
     taken at the same `gen`, ignoring the timing fields `ts`, `idle_seconds`
     and `last_change`.

   When this lands, the spec's "not yet against the real producer" known-limit
   line is reworded to state what is now proven (step 6).

## Tests (new files; unittest style, runnable directly and via the runner)

- `tests/test_monitor_producer_seams.py`, no tmux:
  - With no configs, `classify_pane` / idle verdict / `_capture_args` /
    `get_compare_mode` equal the instance values.
  - Two sessions with different `idle_threshold` give different `is_idle` for the
    same idle age through `_apply_bookkeeping`.
  - The per-session `agent_window_prefixes` classifies `work-x` as AGENT in one
    session and OTHER in the other.
  - The per-session `capture_lines` reaches `-S -N`.
  - The per-session compare default applies to a shadow via `_pane_sessions`.
  - `TmuxControlClient` fed `%exit` sets `saw_exit`. This drives `_reader_loop`
    over an `asyncio.StreamReader` fake stdout, so no process is involved.
  - `shadow_snapshots()` returns a copy.
  - `monitor_shared.is_task_completed is monitor_core.is_task_completed`.
- `tests/test_monitor_status_server.py`, in-process. It uses a `FakeProducer`
  that implements the `TmuxMonitor` slice the server calls and records the order
  of `set_parked_agents` vs `capture_all_classified_async`, plus a scratch socket
  in a temp dir:
  - welcome `impl=python`; `version_mismatch` / `proto_mismatch` close;
    pre-handshake request closes; hello timeout;
  - **delta ordering by `gen`** with two subscribers through `StreamState`:
    contiguous gens; a mid-stream resync snapshot `gen` == the last delta, and the
    next delta is `gen+1`; `set_content` reply under the new selection;
    `result{refresh}.gen` arrives after its delta;
  - the skip set is published before capture and is the union over subscribers'
    pins; `pins:"all"` disables skipping; a disconnected subscriber's pins drop
    out;
  - **`set_pins` then an immediate partial refresh**, using a real `TmuxMonitor`
    with `_tmux_async` / discovery stubbed and a parked agent in the marks store:
    - one full tick, so the agent is a parked placeholder;
    - `set_pins` pinning it, with no further tick;
    - `refresh{panes:[id]}` delivers a live record (`parked:false`, content
      present);
    - then `set_pins []`, then `refresh{panes:[id]}` delivers the parked
      placeholder again;
  - **compare-mode vs in-flight tick**, again a real `TmuxMonitor` with stubbed
    tmux:
    - `_run_offloaded` is overridden with a barrier, so a tick blocks inside the
      classify;
    - `set_compare_mode(pane, "raw")` is sent while the tick is blocked, and the
      barrier is then released;
    - assert (a) the old tick's delta is enqueued **before** the mode `result`;
    - assert (b) right after the `result`, `pane not in monitor._last_content`.
      This follows existing `set_compare_mode` semantics: the setter drops the
      baseline, and serialization means no stale write lands after it;
    - assert (c) one further tick (raw mode) establishes the raw-form baseline;
    - assert (d) a second tick with unchanged content keeps
      `get_last_change_wall(pane)` unchanged, so there is no idle-clock reset.

    The control case runs the same interleaving with the lock bypassed: the test
    calls `monitor.set_compare_mode` directly while the tick is blocked. It must
    **fail (b)**, because the old tick writes its stripped-form baseline after the
    setter. That proves the test detects the stale-write race.
  - **refresh interval**:
    - projects with `refresh_seconds` 7 and 2 give 2;
    - **7 and one project with the key unset give 3** (the mixed
      configured-plus-default case), and 7 plus a project with no config file
      also gives 3;
    - 0.2 is clamped to 1;
    - a lone 500 is clamped to 60;
    - `"fast"`, `true`, `0`, `-1` and `nan` each resolve to 3 for their project
      (so with 7 alongside, the result is 3);
    - no mapped session gives 3;
    - only the five monitor keys reach `set_session_configs`, checked by a
      recording fake;
  - `completed` excludes a pane pinned live but globally parked;
  - a shared compare mode set by A is visible in B's next delta; `capture`
    returns the tail and `not_found`;
  - outbound overflow closes only the slow connection;
  - **idle exit**: an injected clock passes `grace` with no subscriber, so
    `serve_until_exit()` returns `idle`, the socket is unlinked and ticking was
    paused;
  - **`%exit`**: the fake `control_exit_seen` plus a failing `probe_tmux` gives
    `exit_seen`; with a passing probe the control client is restarted and the
    server keeps serving;
  - **socket replaced** → exit, with the stranger's socket left untouched;
  - `record_connect` against the server, then `check_recording` passes.
- `tests/test_monitor_status_server_live.py`, real tmux on an isolated `-L ait_t2037_1_<pid>`
  socket with `TMUX_TMPDIR`, `XDG_RUNTIME_DIR`, `HOME` and
  `AITASKS_AGENT_MARKS_FILE` all under one scratch dir. It skips when `tmux` is
  absent. Sessions are pane-voted into temp project roots that hold
  `aitasks/metadata/project_config.yaml`.
  - **Single start under concurrent `ensure`**: eight `ensure` CLI processes are
    launched at once. All report the same socket and pid. Exactly one says
    `STARTED`. One process holds the lock (`flock` NB fails from the test).
  - **Stale-socket recovery**: a bound-then-abandoned socket file at the path is
    replaced, and the new server answers.
  - **Per-version isolation**: `--version A` and `--version B` give two sockets
    and two pids, and `hello{version:B}` to A's socket gets `version_mismatch`.
  - **Idle exit**: with `--grace 1` and no subscriber, the process exits, the
    socket is gone and the lock is free.
  - **Per-session config**: session A's project sets `agent_window_prefixes: [work-]`
    and `idle_threshold_seconds: 1`, session B uses the defaults. After a
    subscribe plus two refreshes, `work-x` in A is AGENT and in B is OTHER, and
    an idle `agent-…` pane in A is `is_idle` before B's.
  - **`%exit`**: `kill-server` on the isolated socket only, using an explicit
    `-L` plus the scratch `TMUX_TMPDIR`, never the user's server. The server
    process exits.

  Cleanup kills only pids taken from that test's own welcomes whose
  `/proc/<pid>/cmdline` contains the scratch socket path, and waits until they are
  gone.

## Verification

```bash
python3 tests/test_monitor_producer_seams.py
python3 tests/test_monitor_status_server.py
python3 tests/test_monitor_status_server_live.py
python3 tests/test_monitor_status_protocol.py      # spec tables + codec unchanged
python3 tests/test_monitor_status_recording.py     # tail_lines refactor, fixture byte-identical
python3 tests/test_monitor_client_agnostic.py      # producer contract
bash tests/test_no_raw_tmux.sh
set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -3   # read the last line
```

A manual smoke test against the isolated socket:
`python3 .aitask-scripts/monitor/status_server.py ensure`, then `status_recording.py
record --connect <sock> --out /tmp/x.jsonl --max-deltas 3`, then `check`.

If the live module proves timing-sensitive under the xdist lane, add it to the
runner's serial carve-out and to the CLAUDE.md list in the same commit.

## Step 9 (Post-Implementation)

Commit the code with
`feature: Add the monitor status server process and lifecycle (t2037_1)`. Commit
the plan through `aitask_task_commit.sh` and archive via the standard Step 9
flow.

When t2037 itself completes, which is not this child, the parent's note
suggests a cross-repo note to aitasks_go#47 carrying the lifecycle decisions.
This child's spec section is the content for it.

## Risk

Levels re-assessed once after the inline mitigations were added. Code health
stays medium because of the detached-process lifecycle. Goal achievement drops to
low, because the live recording now exercises the real producer's tick-to-tick
output.

### Code-health risk: medium
- The per-session config lookups and `_pane_sessions` touch `TmuxMonitor` hot paths every in-process client uses (`classify_pane`, `_apply_bookkeeping`, `_capture_args`, `get_compare_mode`). A fallback that differs from the instance attribute in any edge case (empty session, shadow pane, a pane not yet discovered) would silently change in-process monitor behaviour · severity: medium · → mitigation: inline pre-phase pin_producer_defaults
- A new long-lived detached process: a defect in the exit paths leaks a server per tmux server and VERSION on user machines, and leaks test processes on CI · severity: medium · → mitigation: covered in-plan (lock = liveness, idle grace, inode watchdog, ownership-checked test cleanup)
- Live tests with wall-clock deadlines (process start, idle exit) can flake under the parallel lane · severity: low · → mitigation: covered in-plan (generous deadlines; serial carve-out if needed)

### Goal-achievement risk: low
- Delta and patch semantics are proven encoder-to-state, but not against the real producer's tick-to-tick output. A producer behaviour (for example a record member appearing or vanishing between ticks, which `_diff_entries` raises on) could break the stream only under live tmux · severity: medium · → mitigation: inline post-phase record_live_server_stream
- `%exit` also arrives when only the attached session is destroyed, not only when the server goes away. Exiting on it alone would kill the server while other sessions still run · severity: low · → mitigation: covered in-plan (liveness probe; restart the control client on session detach)

### Planned mitigations
- timing: pre-phase | name: pin_producer_defaults | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — per-session config seams on TmuxMonitor hot paths | desc: characterization test pinning TmuxMonitor's no-config behaviour before the seam edits, re-run unchanged after
- timing: post-phase | name: record_live_server_stream | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: low | addresses: goal-achievement — delta semantics unproven against the real producer | desc: live test recording the real server's stream over several ticks with removal/appearance/shadow changes, check_recording + state equality
