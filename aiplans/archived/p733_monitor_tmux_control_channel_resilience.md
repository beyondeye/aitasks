---
Task: t733_monitor_tmux_control_channel_resilience.md
Base branch: main
plan_verified: []
---

# Plan — t733: monitor tmux control channel resilience

## Context

Task **t733** (`aitasks/t733_monitor_tmux_control_channel_resilience.md`) was created from an `/aitask-explore` investigation triggered by user reports of tmux instability that takes down all running code agents in the `aitasks` session.

After **t719** (commits `5f723644`, `01430974`) and **t722** (commit `8fb777bd`), the monitor's persistent `tmux -C attach` channel carries **both** the per-tick polling traffic AND every user action (kill-pane, send-keys, switch-pane, kill-window, …). The user's concern is well-founded: a single channel for everything means a transient channel failure simultaneously knocks out polling and the only way to send commands. Today the code's response is "mark the client dead, fall back to subprocess for the rest of the TUI's lifetime" — there is **no automatic reconnect**, so a single 5 s timeout permanently downgrades the session.

This plan ships protective measures: reconnect-with-backoff, a session-rename re-entry leak fix, a small footer status indicator, and a resilience test suite that covers the mid-flight transition cases t722's parity tests don't reach. It also annotates and downgrades the pending pipe-pane task (t719_4) because pipe-pane makes the very "tmux server runs out of memory because a Python consumer is slow" failure mode strictly more likely.

The plan is intentionally additive — the single-channel architecture stays. If real-world load shows reconnect alone is insufficient, t719_6 (architecture evaluation) is the right place to revisit.

## Scope at a glance (deliverables)

| # | Deliverable | Files |
|---|-------------|-------|
| 1 | Reconnect-with-backoff in `TmuxControlBackend` + `state` accessor | `.aitask-scripts/monitor/tmux_control.py` |
| 2 | Fix `_start_monitoring()` re-entry leak | `.aitask-scripts/monitor/monitor_app.py`, `.aitask-scripts/monitor/minimonitor_app.py` |
| 3 | Footer / session-bar status indicator | `.aitask-scripts/monitor/monitor_app.py`, `.aitask-scripts/monitor/minimonitor_app.py` |
| 4 | New resilience test | `tests/test_tmux_control_resilience.sh` (new) |
| 5 | Reconnect-race parity assertions for state-mutating user actions | folded into the new test |
| 6 | Downgrade + annotate `t719_4` | `aitasks/t719/t719_4_pipe_pane_push.md` |

## Critical files (reading map)

- `.aitask-scripts/monitor/tmux_control.py` (~400 LOC) — `TmuxControlClient` (lines 62–246) and `TmuxControlBackend` (lines 248–401). Today: `_teardown_pending` at 163–171 marks the client dead and resolves all futures with `(-1, "")`; nothing reconnects.
- `.aitask-scripts/monitor/tmux_monitor.py:208–264` — `_backend` field, `start_control_client`, `close_control_client`, `_tmux_async`, `tmux_run`. Already falls back to subprocess on `(-1, "")` — no change needed in this file.
- `.aitask-scripts/monitor/monitor_app.py:586–633` — `_start_monitoring`, `_on_session_rename`, `on_unmount`. The leak source: `_on_session_rename → _start_monitoring` re-enters without first awaiting `close_control_client()` on the prior monitor and without canceling the prior `set_interval` Timer.
- `.aitask-scripts/monitor/monitor_app.py:114–118, 886–917, 513` — `SessionBar` widget definition + `_rebuild_session_bar`. Natural place for the new control-state badge.
- `.aitask-scripts/monitor/minimonitor_app.py:121–227` — mirror of the same structure on the minimonitor side.
- `tests/test_tmux_control.sh` — fixture and case patterns to reuse for the new resilience test (each case uses a per-case `TMUX_TMPDIR` subshell + embedded Python via `PYTHONPATH=$REPO_ROOT/.aitask-scripts`).
- `aitasks/t719/t719_4_pipe_pane_push.md` — frontmatter `priority` field on line 2; new section appends to the end.

## Step 1 — Reconnect logic in `TmuxControlBackend`

`.aitask-scripts/monitor/tmux_control.py`

### 1a. State enum + thread-safe accessor

Add at module scope (after the existing constants, before `TmuxControlClient`):

```python
import enum
class TmuxControlState(enum.Enum):
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FALLBACK = "fallback"     # gave up after max attempts; subprocess only
    STOPPED = "stopped"       # backend.stop() called or never started
```

On `TmuxControlBackend` add a `_state` field (default `STOPPED`), a `_state_lock = threading.Lock()`, and a public `state` property. `is_alive` keeps its existing semantics (`self._client is not None and self._client.is_alive`).

### 1b. Reconnect coroutine on the bg loop

Add a new instance attribute `self._reconnect_task: Optional[asyncio.Task] = None`. On client death (i.e., when `_teardown_pending` fires inside `_reader_loop`'s `finally`), `TmuxControlClient` does **not** know about the backend — but the backend's `_reader_loop` runs on the bg loop, and the reader's exit path is already detectable via `self._client.is_alive` flipping False.

Strategy: instead of teaching `TmuxControlClient` about reconnects, run a **supervisor coroutine on the bg loop** that periodically wakes (via the reader's exit notification) and spawns a fresh `TmuxControlClient`. Concretely:

1. In `TmuxControlBackend.start()`, after the first successful client attach, schedule `self._supervisor_loop()` on the bg loop. Store the task in `self._reconnect_task`.
2. `_supervisor_loop()` is an async coroutine on the bg loop:
   ```python
   async def _supervisor_loop(self) -> None:
       BACKOFFS = [0.5, 1.0, 2.0, 4.0, 8.0]
       MAX_ATTEMPTS = 5
       while not self._stop_requested:
           # Wait for the current client to die.
           while self._client is not None and self._client.is_alive:
               await asyncio.sleep(0.5)  # cheap poll; reader-side death is async
           if self._stop_requested:
               return
           self._set_state(TmuxControlState.RECONNECTING)
           attempts = 0
           while attempts < MAX_ATTEMPTS and not self._stop_requested:
               delay = BACKOFFS[min(attempts, len(BACKOFFS) - 1)]
               await asyncio.sleep(delay)
               new_client = TmuxControlClient(self.session, self.command_timeout)
               if await new_client.start():
                   self._client = new_client
                   self._set_state(TmuxControlState.CONNECTED)
                   break
               attempts += 1
           else:
               # Hit the inner else only if the while exited via `attempts < MAX_ATTEMPTS` failure.
               self._set_state(TmuxControlState.FALLBACK)
               return  # supervisor exits; subprocess fallback for the rest of life
   ```
   The 0.5 s poll for "client died" is intentional: faster than tick interval (3 s) so reconnects are user-visible quickly, slow enough that the loop's idle cost is negligible. An alternative — having the reader signal via `asyncio.Event` — is tidier but requires a back-edge from `_reader_loop` to the backend, which keeps the client cleanly decoupled today; sticking with the poll for v1.
3. `start()` initializes `self._stop_requested = False`. `stop()` sets `self._stop_requested = True` and additionally cancels `self._reconnect_task` to wake any pending `asyncio.sleep`.
4. `_set_state(s)` writes `self._state = s` under `self._state_lock` and (optionally, future work) emits a logger record. Single-line synchronous helper.

Note: when reconnect succeeds, `self._client` is replaced. Existing in-flight callers via `request_async` / `request_sync` route through `self._client.request(...)` resolved at scheduling time on the bg loop — by the time the supervisor swaps `_client`, any failed in-flight request has already been resolved with `(-1, "")` by the dead client's `_teardown_pending`. New requests after swap get the fresh client.

### 1c. Update the docstring

Replace the line "On EOF / `%exit` / broken pipe / timeout: mark `is_alive = False`, … do not auto-restart" with a short paragraph describing the supervisor + backoff schedule + max-attempts cap. State the new `TmuxControlState` lifecycle.

### 1d. Update `stop()` to cancel the supervisor

Inside `TmuxControlBackend.stop()`, before tearing down the loop:

```python
self._stop_requested = True
if self._reconnect_task is not None and self._loop is not None:
    with contextlib.suppress(Exception):
        cf = asyncio.run_coroutine_threadsafe(self._cancel_reconnect(), self._loop)
        cf.result(timeout=1.0)
```

Where `_cancel_reconnect` is a tiny coroutine that cancels `self._reconnect_task` and awaits its completion. This keeps shutdown clean even if a reconnect is in flight.

## Step 2 — Fix `_start_monitoring()` re-entry leak

### 2a. `monitor_app.py`

`monitor_app.py:586` is `_start_monitoring`. The session-rename callback at line 581 (`_on_session_rename`) re-enters this method without first closing the prior monitor.

Refactor `_start_monitoring()`:

1. Add an instance attribute `self._refresh_timer: Timer | None = None` to `__init__` (alongside `self._preview_timer` at 505).
2. At the top of `_start_monitoring()`, before the new `TmuxMonitor(...)` construction, run the **teardown helper**:
   ```python
   self._teardown_prior_monitoring()
   ```
   The helper:
   ```python
   def _teardown_prior_monitoring(self) -> None:
       if self._refresh_timer is not None:
           with contextlib.suppress(Exception):
               self._refresh_timer.stop()
           self._refresh_timer = None
       if self._monitor is not None:
           prev = self._monitor
           self._monitor = None
           # close_control_client is async — fire-and-forget on the app loop.
           # The runtime ordering does not matter here because we already
           # nulled self._monitor; the next tick will use the fresh one.
           async def _close_prev() -> None:
               with contextlib.suppress(Exception):
                   await prev.close_control_client()
           self.run_worker(
               _close_prev(),
               exclusive=False, exit_on_error=False,
               group="tmux-control-teardown",
           )
   ```
3. Replace `self.set_interval(self._refresh_seconds, self._refresh_data)` with `self._refresh_timer = self.set_interval(self._refresh_seconds, self._refresh_data)`.

### 2b. `minimonitor_app.py`

Mirror change at lines 121–227. Same pattern: store the interval Timer in `self._refresh_timer`; introduce `_teardown_prior_monitoring()`; call it before re-init. Minimonitor doesn't have an explicit session-rename flow, but the helper is cheap and protects against future re-entry paths.

### 2c. Async `on_unmount` already calls `close_control_client`

No change to `on_unmount` (already at `monitor_app.py:628`). The teardown helper handles only the *re-entry* case; the unmount path stays single-shot.

## Step 3 — Footer / session-bar status indicator

### 3a. monitor

`_rebuild_session_bar()` (line 886–917) already composes the bar's text. After computing `total / sessions / desync`, append a control-state badge **only when state is not `CONNECTED`** (the steady-state case is the most common; surface only the noteworthy states):

```python
state_badge = ""
if self._monitor is not None and self._monitor.has_control_client():
    s = self._monitor.control_state()  # new method — see 3c
    if s == TmuxControlState.RECONNECTING:
        state_badge = "  [yellow]control: reconnecting[/]"
    elif s == TmuxControlState.FALLBACK:
        state_badge = "  [red]control: fallback[/]"
# else: connected — no badge (steady-state silent)
# elif backend was never started or has died entirely → also surface fallback
elif self._monitor is not None and not self._monitor.has_control_client():
    state_badge = "  [red]control: fallback[/]"
```

Append `state_badge` to both the multi-session and single-session branches of the bar `update(...)` call.

### 3b. minimonitor

Same approach. Minimonitor's session-bar equivalent is in `_rebuild_session_bar` (or the closest analogue — confirm during implementation). Append the badge.

### 3c. Expose state via `TmuxMonitor`

Add a single method on `TmuxMonitor` (lines 208–232 region):

```python
def control_state(self) -> "TmuxControlState":
    if self._backend is None:
        from .tmux_control import TmuxControlState
        return TmuxControlState.STOPPED
    return self._backend.state
```

Keeps the import deferred to match the existing pattern.

## Step 4 — `tests/test_tmux_control_resilience.sh`

New test file modeled on `tests/test_tmux_control.sh` (per-case `TMUX_TMPDIR` subshell, embedded Python via `PYTHONPATH=$REPO_ROOT/.aitask-scripts`). Cases:

### Case A — Reconnect-then-recover

1. Start backend; assert `state == CONNECTED` and `is_alive == True`.
2. From the Python helper, find the `tmux -C` child PID and `kill -KILL` it.
3. Within ≤2 s, observe `state` flips to `RECONNECTING`.
4. Within ≤6 s (one backoff window), observe `state` flips back to `CONNECTED`; `request_sync(["display-message", "-p", "#S"])` succeeds with rc==0.
5. Stop backend cleanly.

### Case B — Max-retries cap

1. Start backend with a session that exists.
2. Externally `tmux kill-session -t <session>` (the server keeps running but the target session is gone).
3. Within ≤30 s (sum of backoffs ~16.5 s + slack), observe `state` lands at `FALLBACK` and the supervisor task is finished. `is_alive == False`.
4. Subsequent `request_sync` returns `(-1, "")`; no thread leak, supervisor task done.
5. Stop backend; thread joined.

### Case C — Mid-flight transition

1. Start backend.
2. From a worker thread, issue `request_sync` with timeout=10 against a deliberately slow command (e.g., `run-shell -b "sleep 5"` chained with a short query — practical knob: issue a long-running command via `run-shell -b 'sleep 5'`, then `display-message -p "x"` and `kill -KILL` the `tmux -C` child mid-flight).
3. Assert the in-flight `request_sync` returns `(-1, "")` (already covered by `_teardown_pending`).
4. Within ≤6 s, the next `request_sync` either succeeds via reconnect or returns through the subprocess fallback path on the calling `TmuxMonitor.tmux_run` (this case primarily tests the bg-loop side; the fallback is exercised in Case E).
5. No raise, no hang.

### Case D — 50 concurrent sync requests during a forced reconnect

1. Start backend on a fixture session.
2. Spawn N=50 worker threads (`concurrent.futures.ThreadPoolExecutor`) that each call `backend.request_sync(["display-message", "-p", "#{pane_id}"], timeout=5)`.
3. Mid-batch (e.g., after the 10th thread starts), `kill -KILL` the `tmux -C` child.
4. Assert: every thread returns either `(0, <pane_id>)` or `(-1, "")`. None raise. None hang past `2 × command_timeout`.
5. Final state is `CONNECTED` (reconnect succeeded) or `FALLBACK` (max attempts hit) — both acceptable; what matters is no thread leak and no future-pending future.

### Case E — Reconnect race for state-mutating user actions

This is the **subprocess fallback parity assertion** under transition (deliverable #5).

1. Fixture: window W with two agent panes A1, A2.
2. Start `TmuxMonitor` + `start_control_client`. Confirm `has_control_client() == True`.
3. Issue `monitor.kill_pane(A1.pane_id)` → returns `True`. Assert via `tmux list-panes` that A1 is gone, A2 remains. (Steady-state via control client; this is covered by t722's `test_kill_agent_pane_smart.sh`, but anchor it here too as a baseline.)
4. `kill -KILL` the `tmux -C` child.
5. Issue `monitor.kill_pane(A2.pane_id)` immediately. Two paths converge here:
   - The backend may still report `is_alive == True` for one tick → request goes via `request_sync` and gets `(-1, "")` → caller falls through to `_run_tmux_subprocess`.
   - Or the backend's reader has already detected EOF and `is_alive` is False → caller goes straight to subprocess.
   Both must produce the same end state: A2 gone, window collapsed (since W has no remaining agents → `kill_agent_pane_smart` returns `(True, True)`).
6. Re-issue `monitor.kill_pane(<gone-pane-id>)` after reconnect: both control and subprocess paths return `rc == 1` (target missing). Asserts no double-kill / no spurious side effect.

### Test-runner discipline

- Per-case `EXIT` traps for fixture cleanup (each case spins its own `tmux -L <socket>` server via `TMUX_TMPDIR`).
- `kill -KILL` of `tmux -C` is the deterministic trigger; it is tighter than waiting on a timeout.
- For Case B, use a dedicated socket so killing the session does not nuke other servers.
- Embedded Python uses `from monitor.tmux_control import TmuxControlBackend, TmuxControlState` and `from monitor.tmux_monitor import TmuxMonitor`.
- Add the new test to `CLAUDE.md`'s mention of testing only if it improves discoverability — current convention is "tests are run individually", so just dropping the file in `tests/` is sufficient.

## Step 5 — Downgrade and annotate `t719_4`

`aitasks/t719/t719_4_pipe_pane_push.md`:

1. Change frontmatter line 2 from `priority: medium` to `priority: low`.
2. Update `updated_at` to today's date+time.
3. Append a new section before the existing `## Verification Steps` (or at the natural narrative end — pick the place that reads best):

   ```markdown
   ## Stability caveats (added 2026-05-03 by t733)

   Prior to implementation, weigh these stability concerns surfaced during
   the t733 channel-resilience investigation. Pipe-pane introduces strictly
   more failure surface than the current control-mode polling, in exchange
   for sub-second update latency:

   - **OOM-on-tmux risk.** tmux uses libevent `bufferevent` for `pipe-pane`
     output. If the Python consumer cannot drain fast enough, tmux buffers
     in *its own* memory — unbounded growth, not byte-drop. A busy code
     agent (Claude Code can burst >100 KB/s during streaming) × N panes ×
     M monitors increases the probability that a slow Python tick triggers
     tmux server OOM kill — exactly the "tmux crashed and took everything
     down" symptom that motivated t733.
   - **Per-pane fd cost.** Each subscribed pane is one fifo + one consumer
     stdin; on a multi-session dev box (e.g. `aitasks` + `aitasks_mob`)
     × multiple monitor / minimonitor instances, the count grows quickly.
     Audit the hard fd ceiling on the user's host before subscribing
     unconditionally.
   - **Raw VT-stream complexity.** Pipe-pane emits the unrendered terminal
     byte stream (cursor moves, alt-screen toggles, clearing). The Python
     consumer must implement a terminal emulator or round-trip through
     `capture-pane` after the fact to recover the rendered text the
     compare-mode logic relies on. This is more code than the bench
     prototype would suggest.
   - **Single-threaded tmux event loop.** Per-pane pipe-pane I/O competes
     with control-mode + real-terminal rendering on the same loop. Many
     fifos = more fd-event work per tick.

   **Pre-condition:** Do not implement Phase 4b until the t733 resilience
   deliverables (reconnect + transition tests) have landed and been
   validated on a real workload. The investigation phase (4a) can proceed
   independently — the gate's ≥2× decision criterion is the right place
   to weigh the latency win against this risk surface.
   ```

4. Commit via `./ait git`:
   ```bash
   ./ait git add aitasks/t719/t719_4_pipe_pane_push.md
   ./ait git commit -m "ait: Downgrade t719_4 + add stability caveats (t733)"
   ```

## Verification

End-to-end:

1. **Tests pass:**
   ```bash
   bash tests/test_tmux_control.sh             # t719_1 — must still pass
   bash tests/test_tmux_run_parity.sh          # t722 — must still pass
   bash tests/test_kill_agent_pane_smart.sh    # t722 — must still pass
   bash tests/test_tmux_control_resilience.sh  # NEW — five cases
   ```

2. **Manual smoke (reconnect):** launch `ait monitor`. In another shell, `pgrep -f 'tmux -C attach' | xargs kill -KILL`. Observe the session-bar badge flips `control: reconnecting`, then disappears once respawn succeeds. User actions (kill-pane via `k`, send-keys via `Enter`, switch via `s`) keep working throughout.

3. **Manual smoke (re-entry leak):** launch `ait monitor` against a session whose name differs from `expected_session`. Trigger the rename dialog and accept. After rename:
   - `pgrep -af 'tmux -C attach' | wc -l` shows the same count as before (one client per live monitor process).
   - `python3 -c "import threading; [print(t.name) for t in threading.enumerate()]"` (run inside the monitor's process via debugger or worker) shows exactly one `tmux-control-loop` thread.
   - Polling cadence visibly remains at the configured `refresh_seconds` (no doubled flicker).

4. **t719_4 file inspection:** `grep -n 'priority' aitasks/t719/t719_4_pipe_pane_push.md` returns `priority: low`. The new `## Stability caveats` section is present.

## Out of scope (and why)

- **Multi-channel architecture** (one control client per use-case, e.g., separate kill-channel from polling-channel). That is the right escalation if reconnect alone is insufficient under real load — defer to t719_6's architecture-evaluation outcome.
- **Adaptive polling** (t719_3) and **pipe-pane** (t719_4) — both blocked behind this resilience landing per the description.
- **OS-level / tmux-upstream investigation** of the actual tmux-crash reports — needs reproduction with logs first; out of code-change scope here.
- **Touching tmux invocations outside `.aitask-scripts/monitor/`** (agent_launch_utils, terminal_compat, helper bash scripts).

## Step 9 — Post-Implementation reference

Standard archival per `task-workflow/SKILL.md` Step 9. No worktree (chose current branch in Step 5). No issue is linked. The plan file commits separately via `./ait git` with the task ID in the message body.

## Final Implementation Notes

- **Actual work done:** Implemented all 6 deliverables per the plan: (1) `TmuxControlState` enum + supervisor coroutine with backoff in `tmux_control.py`; (2) `_teardown_prior_monitoring()` in monitor_app.py and minimonitor_app.py with `_refresh_timer` capture; (3) control-state badges in both session bars; (4) `tests/test_tmux_control_resilience.sh` with 5 cases (A-E); (5) folded into Case E (state-mutating action parity through subprocess fallback); (6) `aitasks/t719/t719_4_pipe_pane_push.md` downgraded to `low` priority + `## Stability caveats` section appended.
- **Deviations from plan:** Case C revised after empirical probing showed neither `run-shell` (without -b) nor `if-shell` actually block in tmux control mode — both ack the dispatch immediately and run async. `wait-for` partially works but only the first invocation per channel returns immediately (subsequent calls queue). Rather than chase a synthetic blocking primitive, Case C now uses a deterministic kill-then-burst pattern: kill `tmux -C` subprocess, wait for `is_alive` to flip, then fire 5 sequential `request_sync` calls and assert each completes within `command_timeout` (no hangs). Then verify the supervisor reconnects and a final request succeeds via control. This still proves the resilience contract (no hangs, no exceptions, supervisor recovers) without depending on a fragile in-flight blocking trick.
- **Issues encountered:**
  - First Case E run was flaky (3/5 fails). The "issue `kill_pane(A2)` immediately after SIGKILL" path is racy because writes to a freshly-killed subprocess's stdin can buffer in the kernel pipe — the request hangs until `command_timeout` (5 s) before falling back. Resolved by adding a deterministic `await is_alive == False` wait, which pins the test to the documented post-EOF subprocess fallback path that the plan's Step 7 enumerates as one of the "two paths". The other path (truly mid-flight write race) is conceptually covered but not as a hard assertion — would need a different blocking primitive to test reliably.
  - Discovered that fixture sessions are auto-destroyed by tmux when their last window collapses. Case E adds a `keepalive` window so `list-panes -s -t SESSION` keeps working after both agent panes are killed.
- **Key decisions:**
  - **Supervisor poll cadence (0.5 s).** Tighter than the 3 s monitor refresh tick so the badge transition is visible to the user; loose enough that idle bg-loop cost is negligible. Plan's recommendation; kept verbatim.
  - **Bounded backoff (0.5/1/2/4/8 s × 5 attempts = 15.5 s).** Matches the plan; covers transient failures (channel churn during heavy load) without retrying forever on permanent failures (session destroyed).
  - **Module-level `_RECONNECT_*` constants** rather than instance attrs. Per memory `feedback_single_source_of_truth_for_versions`: cross-script constants in one place. The supervisor reads them directly; if a future tuning experiment wants per-instance overrides, that change is one edit at module top.
  - **State exposed via `TmuxMonitor.control_state()`** (deferred-import of enum) rather than via a direct `_backend.state` attribute access. Keeps the layering pattern that tmux_monitor.py already uses for tmux_control (`TYPE_CHECKING`-only top-level import + deferred runtime import).
  - **Compact badge in minimonitor (`rc:retry` / `rc:fb`)** because the minimonitor session bar is narrow (40-column side column). The full-monitor bar uses verbose `control: reconnecting` / `control: fallback` since it has the width.
  - **No retroactive switch to `require_ait_python_fast`** for monitor / minimonitor: per CLAUDE.md note, those launchers are exceptions because their bottleneck is `fork+exec(tmux)`, not Python. Sibling task t718_5 will empirically re-evaluate.
- **Upstream defects identified:** None. Diagnosis in this task surfaced only behaviors of the in-tree control client; no separate pre-existing bug elsewhere in the codebase was implicated.

## Post-Review Changes

### Change Request 1 (2026-05-04 10:05)
- **Requested by user:** Confirm minimonitor's auto-despawn behavior (exit when associated codeagent window dies) is preserved.
- **Changes made:** No code changes — verified behavior is preserved. `_check_auto_close()` (minimonitor_app.py:298) is unchanged; `_refresh_timer` is now properly captured but the timer still fires `_refresh_data` which still calls `_check_auto_close` after the 5 s mount grace. The tmux pane-died hook (`.aitask-scripts/aitask_companion_cleanup.sh`) is at the script layer and untouched. Even mid-reconnect, `_check_auto_close → discover_window_panes → tmux_run` reaches a real answer via the t722 subprocess fallback.
- **Files affected:** none (verification only).
