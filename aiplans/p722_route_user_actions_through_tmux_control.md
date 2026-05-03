---
Task: t722_route_user_actions_through_tmux_control.md
Base branch: main
plan_verified: []
---

# Plan: t722 — Route user-action tmux calls through TmuxControlClient

## Context

Follow-up to **t719** (recent commits `5f723644` and `01430974`). t719's Phase 1 routed only the *async hot-path* tmux invocations (`list-panes`, `capture-pane`) in `.aitask-scripts/monitor/` through the persistent `tmux -C` control client. **All user-action sites (kill, send-keys, switch-pane, env, display-message, list-windows, …) remain on plain `subprocess.run`.** That was an acceptable boundary for t719's perf goal but leaves the monitor's tmux interaction split across two surfaces.

The motivation for consolidating now is the planned **mobile-device bridge** that will speak the control-mode protocol once and route everything through it. A single contact surface inside `TmuxMonitor` for all tmux ops removes the need for the bridge to know about a second ad-hoc subprocess code path. Doing the consolidation after t719_2 has settled, before mobile-bridge work begins, avoids retrofitting under deadline pressure.

## Approach (architectural)

The user-action call sites are mostly **sync** methods (`def kill_pane`, `def send_keys`, …) called from Textual handlers that run on the same thread as the asyncio main loop. Naive `asyncio.run`/`run_until_complete` from inside a Textual handler would deadlock the reader task on the main loop.

**Selected architecture (per user choice in planning):** move the control client onto a **dedicated background asyncio loop in a worker thread**. All tmux requests — sync or async — route through `asyncio.run_coroutine_threadsafe` so the request and its response are demultiplexed on a different thread/loop than the calling Textual handler.

```
Main thread (Textual loop) ─┐
                            │ tmux_run(args)   ─sync──┐
                            │                         │
                            │ _tmux_async(args) ─await┤
                            │                         │
                            ▼  run_coroutine_threadsafe
                       Bg thread (control loop)
                            │
                            ▼
                          tmux -C
```

Two public entry points on `TmuxMonitor`:

- `tmux_run(args, timeout=5.0) -> (rc, stdout)` — **new**, sync. For sync user-action call sites.
- `_tmux_async(args, timeout=5.0) -> (rc, stdout)` — **existing**, async. Re-implemented to use the same bg loop.

Both fall back to subprocess on any failure / when the bg loop is unavailable, preserving the existing fallback semantics from t719_1.

`TmuxControlClient` itself stays unchanged — it is still a single-threaded async client. All threading lives in a new `TmuxControlBackend` wrapper.

## Critical files

- `.aitask-scripts/monitor/tmux_control.py` — add `TmuxControlBackend` class (loop + thread + client lifecycle)
- `.aitask-scripts/monitor/tmux_monitor.py` — replace `_control: TmuxControlClient | None` with `_backend: TmuxControlBackend | None`; add `tmux_run`; rewrite `_tmux_async`; migrate sync user-action methods (lines ~297, 334, 369, 487, 544, 563, 584, 596, 611, 636, 652, 684, 713)
- `.aitask-scripts/monitor/monitor_app.py` — migrate user-action sites (lines ~535, 552, 795, 816, 924) to `self._monitor.tmux_run(...)`
- `.aitask-scripts/monitor/minimonitor_app.py` — migrate user-action sites (lines ~169, 280, 487, 513, 644, 660, 675, 684) to `self._monitor.tmux_run(...)`
- `tests/test_tmux_control.sh` — add Case 5 (sync wrapper / `TmuxControlBackend` smoke + parity + dead-loop fallback)
- New: `tests/test_kill_agent_pane_smart.sh` — regression test for the kill flow

## Implementation steps

### Step 1 — Add `TmuxControlBackend` to `tmux_control.py`

Add a new class at the end of `tmux_control.py` that owns a background asyncio loop in a worker thread and drives a `TmuxControlClient` on that loop. The existing `TmuxControlClient` class stays untouched.

```python
import threading

class TmuxControlBackend:
    """Owns a dedicated asyncio loop in a background thread that drives a
    TmuxControlClient. Provides sync (`request_sync`) and async
    (`request_async`) entry points; both route through
    asyncio.run_coroutine_threadsafe so callers on any thread/loop see
    consistent semantics. Fallback to subprocess is the caller's
    responsibility (TmuxMonitor handles it).
    """

    def __init__(self, session: str, command_timeout: float = 5.0):
        self._session = session
        self._command_timeout = command_timeout
        self._client: Optional[TmuxControlClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()

    @property
    def is_alive(self) -> bool:
        return self._client is not None and self._client.is_alive

    def start(self) -> bool:
        """Start bg thread + loop, then start the client on it. Returns
        True iff the client successfully attached."""
        if self._thread is not None:
            return self.is_alive
        self._thread = threading.Thread(
            target=self._thread_main, name="tmux-control-loop", daemon=True
        )
        self._thread.start()
        self._ready.wait(timeout=2.0)
        if self._loop is None:
            return False
        client = TmuxControlClient(self._session, self._command_timeout)
        fut = asyncio.run_coroutine_threadsafe(client.start(), self._loop)
        try:
            ok = fut.result(timeout=5.0)
        except Exception:
            ok = False
        if ok:
            self._client = client
        return ok

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()

    def stop(self) -> None:
        """Close the client (on bg loop), stop the loop, join the thread."""
        loop = self._loop
        client = self._client
        if loop is not None and client is not None:
            with contextlib.suppress(Exception):
                fut = asyncio.run_coroutine_threadsafe(client.close(), loop)
                fut.result(timeout=3.0)
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        self._client = None
        self._loop = None
        self._thread = None

    def request_sync(self, args: list[str], timeout: float | None = None
                     ) -> tuple[int, str]:
        """Issue a tmux command and block until the response arrives."""
        if self._loop is None or self._client is None or not self._client.is_alive:
            return (-1, "")
        eff = timeout if timeout is not None else self._command_timeout
        fut = asyncio.run_coroutine_threadsafe(
            self._client.request(args, timeout=eff), self._loop,
        )
        try:
            return fut.result(timeout=eff + 1.0)
        except Exception:
            with contextlib.suppress(Exception):
                fut.cancel()
            return (-1, "")

    async def request_async(self, args: list[str], timeout: float | None = None
                            ) -> tuple[int, str]:
        """Issue a tmux command from an async caller on a different loop."""
        if self._loop is None or self._client is None or not self._client.is_alive:
            return (-1, "")
        eff = timeout if timeout is not None else self._command_timeout
        cf = asyncio.run_coroutine_threadsafe(
            self._client.request(args, timeout=eff), self._loop,
        )
        try:
            return await asyncio.wrap_future(cf)
        except Exception:
            return (-1, "")
```

Key design notes:
- `start()` is **sync** and idempotent. The bg thread creates the loop and signals `_ready` before the caller schedules anything on it.
- `stop()` schedules `client.close()` on the bg loop, then `loop.stop()`, then joins. Idempotent.
- All client interaction goes through `run_coroutine_threadsafe` — no direct cross-thread state mutation. `TmuxControlClient`'s existing `_write_lock` (asyncio.Lock) and FIFO `_pending` deque both run on the bg loop, so single-threaded async semantics are preserved.

### Step 2 — Update `TmuxMonitor` to use the backend

In `tmux_monitor.py`:

- Replace `self._control: TmuxControlClient | None = None` (line 184) with `self._backend: TmuxControlBackend | None = None`.
- Rewrite `start_control_client` / `close_control_client` / `has_control_client` (lines 186–201) to delegate to the backend. **Keep them `async def`** so the four existing call sites in monitor_app.py / minimonitor_app.py (`await self._monitor.start_control_client()`) don't need to change. The body becomes synchronous (`backend.start()`) — `await`-ing a synchronously-completing coroutine has no correctness impact.

```python
async def start_control_client(self) -> bool:
    from .tmux_control import TmuxControlBackend
    backend = TmuxControlBackend(self.session)
    if backend.start():
        self._backend = backend
        return True
    backend.stop()  # tear down the thread we just started
    return False

async def close_control_client(self) -> None:
    if self._backend is not None:
        self._backend.stop()
        self._backend = None

def has_control_client(self) -> bool:
    return self._backend is not None and self._backend.is_alive
```

- Rewrite `_tmux_async` (line 203) to route through the backend:

```python
async def _tmux_async(self, args, timeout=5.0):
    if self._backend is not None and self._backend.is_alive:
        rc, out = await self._backend.request_async(args, timeout=timeout)
        if rc != -1:
            return rc, out
    return await _run_tmux_async(args, timeout=timeout)
```

- Add a new `tmux_run` method (sync) right after `_tmux_async`:

```python
def tmux_run(self, args, timeout=5.0) -> tuple[int, str]:
    """Sync user-action wrapper: control client when alive, subprocess fallback.

    Returns (rc, stdout). rc semantics match `_tmux_async`:
      0 = ok, 1 = tmux command error, -1 = transport / fallback failure.
    """
    if self._backend is not None and self._backend.is_alive:
        rc, out = self._backend.request_sync(args, timeout=timeout)
        if rc != -1:
            return rc, out
    return _run_tmux_subprocess(args, timeout=timeout)
```

- Add a sibling sync helper `_run_tmux_subprocess` next to the existing async `_run_tmux_async` (line 98) — same `(rc, stdout)` contract:

```python
def _run_tmux_subprocess(args: list[str], timeout: float = 5.0) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["tmux", *args], capture_output=True, text=True, timeout=timeout,
        )
        return result.returncode, result.stdout or ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return (-1, "")
```

### Step 3 — Migrate sync user-action sites in `tmux_monitor.py`

For each of the 13 sites, replace inline `subprocess.run(["tmux", ...])` with `self.tmux_run([...])`. Mechanical translation. Example:

```python
# Before
def send_enter(self, pane_id: str) -> bool:
    try:
        result = subprocess.run(
            ["tmux", "send-keys", "-t", pane_id, "Enter"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False

# After
def send_enter(self, pane_id: str) -> bool:
    rc, _ = self.tmux_run(["send-keys", "-t", pane_id, "Enter"])
    return rc == 0
```

Sites to migrate (per the audit): `_discover_panes_multi` (~297), `discover_panes` (~334), `discover_window_panes` (~369), `capture_pane` (~487), `send_enter` (~544), `send_keys` (~563), `switch_to_pane` (two calls, ~584 + ~596), `find_companion_pane_id` (~611), `kill_pane` (~636), `kill_window` (~652), `kill_agent_pane_smart` (~684), `spawn_tui` (~713).

Each migration:
- Drops the `subprocess.TimeoutExpired/FileNotFoundError/OSError` try/except (pushed into `_run_tmux_subprocess`).
- Reads `(rc, stdout)` directly. Where the original code parsed `result.stdout`, parse `stdout` instead.
- Where `text=True` was used, the new path always returns text — no change needed in parsing.
- No site inspects `stderr` (confirmed in audit), so dropping it is safe.

### Step 4 — Migrate sites in `monitor_app.py` and `minimonitor_app.py`

Each Textual app holds `self._monitor: TmuxMonitor`. After the monitor is constructed, `self._monitor.tmux_run(...)` is the canonical entry point.

`monitor_app.py` sites: `on_mount` rename-window (~535), `on_mount` has-session (~552), `_consume_focus_request` (~795), `_clear_focus_request` (~816), `_read_attached_session` (~924). All run after `self._monitor` is constructed.

`minimonitor_app.py` sites: `on_mount` display-message (~169), `_update_own_window_info` (~280), `_find_sibling_pane_id` (~487), `_focus_sibling_pane` (~513), `action_switch_to_monitor` set-environment (~644), `action_switch_to_monitor` list-windows (~660), `action_switch_to_monitor` select-window (~675), `action_switch_to_monitor` new-window (~684).

Two pre-monitor-init sites stay on subprocess (intentionally not migrated, called before `TmuxMonitor` is constructed):
- `monitor_app.py:_detect_tmux_session` (~1758)
- `minimonitor_app.py:_detect_tmux_session` (~701)

These are **out of scope** for t722 — no `self._monitor` exists yet. Document this in the plan's Final Implementation Notes. (Also: `minimonitor_app.py:on_mount` display-message at ~169 currently runs *before* `_start_monitoring()` constructs the monitor. That site must be migrated by **moving the display-message call to after `_start_monitoring()`** — `_update_own_window_info` already does the same query and runs every refresh tick, so the on_mount call can be eliminated entirely once `_start_monitoring` is called.) Verify this rearrangement during implementation; if it adds churn, leave the on_mount call as subprocess and document the exception.

### Step 5 — Tests

Threading + asyncio in a background loop is a class of bug magnet. The test suite has to cover concurrency, lifecycle, fallback, and shutdown explicitly — manual smoke is not enough. New tests live in three files; each is a self-contained bash script following the existing `tests/test_tmux_control.sh` fixture pattern (per-case `TMUX_TMPDIR`, embedded Python helper via `PYTHONPATH=$REPO_ROOT/.aitask-scripts`).

#### 5a — Extend `tests/test_tmux_control.sh` with backend-focused cases

**Case 5: backend smoke + sync wrapper basics**
- `TmuxControlBackend.start()` → `is_alive` True; `_thread.is_alive()` True.
- `request_sync(["display-message", "-p", "#S"])` → `(0, "<session>\n")`.
- `request_sync(["list-panes", "-F", "#{pane_id}"])` returns one line per pane in the fixture.
- `stop()` → thread joined within 3 s; `is_alive` False.
- Calling `request_sync` after `stop()` → `(-1, "")` (no exception).
- Calling `stop()` twice → second is a no-op (no exception, returns quickly).

**Case 6: concurrent sync requests from multiple threads**
- Start backend.
- Spawn N=10 worker threads via `concurrent.futures.ThreadPoolExecutor`. Each calls `request_sync(["display-message", "-p", "#{pane_id}"])` against a different pane id.
- Assert: every thread observes `rc==0` and stdout matches the pane id it queried (no cross-talk — proves FIFO + write-lock keeps the request/response correlation correct under contention).
- Repeat with N=50 to flush out any latent ordering bugs at higher contention.
- Stop backend; thread joined.

**Case 7: mixed sync + async callers on the same backend**
- Start backend on bg thread.
- On the main thread, run an `asyncio.run(...)` block that:
  - Schedules `await backend.request_async([...])` calls (5 of them) in a `gather`.
  - From the same `async` block, also runs a sync `request_sync([...])` via `loop.run_in_executor(None, lambda: backend.request_sync(...))`.
- All complete with the correct results.
- This is the **load-bearing test** that proves the architecture solves the deadlock the all-async option was meant to avoid: a sync caller invoked from inside a running asyncio loop succeeds without blocking the loop's reader task (because the reader runs on the bg loop, not this one).

**Case 8: lifecycle — idempotency, restart, mid-flight stop**
- `start()` twice without intervening `stop()` → second call returns same `is_alive`, no second thread spawned (assert by checking thread identity).
- `start()` → `stop()` → `start()` → reusable across cycles. (If we choose one-shot semantics instead, the second `start()` should return False and document the contract; pick one and assert it.)
- Issue a request, then call `stop()` on the same thread before the response arrives (use a contrived timing knob — e.g., issue with `timeout=10` but immediately call `stop()`):
  - `stop()` returns within its own timeout (say 4 s).
  - The pending request future resolves with `(-1, "")` (via `_teardown_pending`).
  - Thread joined.

**Case 9: transport-failure path under load + recovery**
- Start backend.
- Issue a few `request_sync` calls — succeed.
- Externally `tmux kill-server` for the fixture server.
- Within ≤2 s, `is_alive` flips to False (reader detects EOF and calls `_teardown_pending`).
- Subsequent `request_sync` calls return `(-1, "")` without raising and without auto-restart.
- `stop()` is still clean (no hang, thread joins).

**Case 10: timeout handling**
- Start backend.
- Issue `request_sync([...], timeout=0.001)` — must return `(-1, "")` quickly. (Per existing `TmuxControlClient.request`, a timeout marks the client dead via `_teardown_pending`.)
- Subsequent `request_sync` also returns `(-1, "")` — proves the dead-client semantics propagate through the backend.
- `stop()` is clean.

**Case 11: tmux not on PATH**
- Run the embedded Python helper with `env -i PATH=/no-tmux-here ...` (no `tmux` binary reachable).
- `backend.start()` returns False (the underlying `TmuxControlClient.start()` catches `FileNotFoundError`).
- `is_alive` False; `request_sync` returns `(-1, "")`.
- `stop()` is clean (idempotent even when start failed).

**Case 12: shutdown while the bg loop has work queued**
- Start backend.
- From the main thread, schedule (but don't await) 20 `request_async` futures via `run_coroutine_threadsafe` directly (bypassing the wrapper) so several requests are mid-flight.
- Immediately call `stop()`.
- Assert `stop()` completes within timeout.
- All scheduled futures resolve (either with a real result or with `(-1, "")`); none stay pending.

#### 5b — New `tests/test_tmux_run_parity.sh` — per-subcommand parity

Drives `TmuxMonitor.tmux_run` (with backend started) against `subprocess.run(["tmux", ...])` directly and asserts identical `(returncode, stdout)` for each subcommand the migration touches. A parity gap here would hide a behavior change behind a successful-looking migration.

For each of the following, run both forms and assert match (rc + stdout, with a substring match where stdout is timestamp- or id-volatile):

- `display-message -p "#S"` (used by `_read_attached_session`, `_detect_tmux_session`).
- `display-message -p -t <pane> "#{window_id}\t#{window_index}\t#{window_name}"` (minimonitor own-window query).
- `list-panes -s -t <session> -F <fmt>` (sync `discover_panes`).
- `list-panes -t <window> -F "#{pane_id}\t#{pane_pid}"` (`find_companion_pane_id`, `kill_agent_pane_smart`).
- `list-windows -t <session> -F "#{window_name}"` (`action_switch_to_monitor`).
- `has-session -t <session>` (rc=0 vs rc=1 paths both checked).
- `show-environment -t <session> AITASK_MONITOR_FOCUS_WINDOW` (set, then read; assert exact stdout shape).
- `set-environment -t <session> -u AITASK_MONITOR_FOCUS_WINDOW` (mutator, rc only).
- `rename-window monitor` (mutator, verify via subsequent `display-message -p "#W"`).
- `send-keys -t <pane> Enter` and `send-keys -t <pane> -l "literal text"` (verify by capturing the pane and looking for a sentinel).
- `select-pane -t <pane>` and `select-window -t <window>` (verify via `display-message -p "#{window_active},#{pane_active}"`).
- `kill-pane -t <pane>` and `kill-window -t <window>` (verify via `list-panes` / `list-windows` afterwards).
- `new-window -t <session> -n <name>` (verify by listing).
- `capture-pane -p -J -S -1000 -t <pane>` (compare body bytes — this is the same path t719_1 already tests for the async variant; replicate here for the sync wrapper).

Run the whole battery against (a) backend started — exercises `request_sync` path, (b) backend NOT started (`monitor._backend is None`) — exercises subprocess fallback. Both must produce identical `(rc, stdout)` results. This is the canonical regression suite for the migration.

#### 5c — New `tests/test_kill_agent_pane_smart.sh` — kill-flow regression

Mirrors the task description's manual-verification target, automated. Two passes against the same fixture shape:

- **Pass 1 (control-client path):** backend started.
- **Pass 2 (subprocess fallback path):** backend stopped (or never started).

Fixture shape per pass:
- Window W1 with two agent-prefixed panes A1, A2 plus a companion pane C1 (a sleep loop spawned with `tmux split-window` whose parent process matches `_is_companion_process`'s heuristic — likely a child of `python3` running a sleep). If reproducing the companion heuristic is too brittle, the test can either:
  - (a) Stub `_is_companion_process` via monkey-patch in the embedded helper, OR
  - (b) Skip the companion-preservation assertion and only verify pane/window state changes.
  Pick (a) for tighter coverage; document the monkey-patch.

Assertions per pass:
1. `monitor.kill_agent_pane_smart(A1.pane_id)` → returns `(True, False)` (killed pane only).
2. After: A1 absent, A2 present, C1 present, W1 present (`tmux list-panes -t W1` shows A2 + C1).
3. `monitor.kill_agent_pane_smart(A2.pane_id)` → returns `(True, True)` (last agent → window collapsed).
4. After: W1 absent (`tmux list-windows -t <session>` does not include W1's id), which also implicitly cleans up C1.

Both passes must yield identical end states. This proves that the migration didn't change observable behavior for the most state-mutating user action.

#### 5d — Smoke: no extra clients, no thread leaks

A small bash assertion appended to one of the new tests:
- After `monitor.start_control_client()` succeeds, `tmux list-clients -t <session>` shows exactly one control-mode client. Re-issue 50 `tmux_run` calls; client count stays at 1 (sync and async share it).
- After `monitor.close_control_client()`, the control-mode client is gone (`tmux list-clients -t <session>` does not show it) and the bg thread is joined (`threading.enumerate()` does not contain a `tmux-control-loop` thread).

#### Test runner notes

- Each new test file follows the existing skip-on-missing-tmux/python3 convention from `tests/test_tmux_control.sh:11-22`.
- Tests fan out via `make_fixture` / `teardown_fixture`. EXIT trap teardown is required because thread-leak assertions only make sense when each case runs in a clean process; helper subprocesses must not leak servers.
- Where a test needs a controlled timing knob (e.g., Case 8 mid-flight stop), use a small `time.sleep` or schedule a no-op delay — do **not** monkey-patch the production code path with conditional debug hooks.
- Add the three new files to any existing test runner / CI list. (No central runner exists — tests are run individually per CLAUDE.md.)

If a test proves persistently flaky on threading timing (Case 8 in particular has the most uncertainty), document the flakiness in the test's header and convert that specific assertion to a manual checklist item; do not silently weaken assertions or insert `sleep` retries.

### Step 6 — Manual verification

Launch `ait monitor` and `ait minimonitor`. Exercise:
- `x` (kill-pane) — single agent pane killed, window preserved when siblings remain; window collapsed when last agent killed.
- `s` / `Tab` (switch / focus-sibling) — focus moves correctly across panes and across sessions in multi-session mode.
- `Enter` and arbitrary send-keys — agent input still routed.
- `M` (multi-session toggle) — session list updates.
- Minimonitor → "switch to full monitor" handoff (`M` in minimonitor) — focus-window env var is set, monitor pane focuses correctly.
- Smoke check: `tmux list-clients` shows exactly **one** control client per project (the `tmux -C attach` from the bg loop), not multiples — confirms a single client serves both sync and async paths.

Surface this manual-verification checklist either as a child task or as the eventual t722 follow-up; per CLAUDE.md, the planning workflow will offer that explicitly.

## Verification

- `bash tests/test_tmux_control.sh` — passes (with new Case 5).
- `bash tests/test_kill_agent_pane_smart.sh` — passes.
- `grep -nE 'subprocess\.(run|Popen).*tmux' .aitask-scripts/monitor/*.py` — returns **only** the fallback path inside `_run_tmux_subprocess` plus the two `_detect_tmux_session` pre-init sites. All other tmux invocations route through `tmux_run` / `_tmux_async`.
- Manual smoke per Step 6.
- `tmux list-clients -F '#{client_session} #{client_termname}'` (run inside a project session while monitor is active) shows one tmux-control-mode client, not two — sync and async share it.

## Out of bounds

- The mobile-device bridge itself.
- Tmux invocations *outside* `.aitask-scripts/monitor/` (agent_launch_utils, terminal_compat, helper bash scripts).
- The two `_detect_tmux_session()` pre-monitor-init helpers in `monitor_app.py:1753` and `minimonitor_app.py:696` (no `self._monitor` exists yet).

## Step 9 (Post-Implementation) reference

After approval and implementation: the standard task-workflow Step 8 → 9 flow archives `t722` and `p722_route_user_actions_through_tmux_control.md`. No worktree to clean up (Step 5 chose current-branch). No issue is linked.
