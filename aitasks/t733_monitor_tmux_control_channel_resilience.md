---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [monitor, tmux, reliability, bug]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-03 18:53
updated_at: 2026-05-03 19:13
---

## Context

User reports tmux instability ("tmux crashes that take down all running code agents in the aitasks session") and is concerned that the recent monitor refactor (t719_1, t719_2, t722) may be a contributing cause.

After **t722** (commit `8fb777bd`), the same persistent `tmux -C attach` channel is used for both polling AND user actions (kill, send-keys, switch-pane, etc.). If that channel breaks, both functions break with no automatic recovery — which the user flags as invalidating the new architecture's safety story.

## Findings from /aitask-explore

- **No direct tmux-server-killing code paths.** No `kill-server` anywhere; `kill-pane`/`kill-window` correctly target a single pane/window.
- **Channel has no automatic reconnect.** A single `_tmux_async` 5 s timeout marks the client permanently dead via `_teardown_pending`; the rest of the TUI's lifetime falls back to subprocess. Polling AND user actions both go to fallback together — and never recover.
- **`_start_monitoring()` re-entry leak** at `monitor_app.py:586`/`588`. The `_on_session_rename` callback re-enters `_start_monitoring()` without first `await`ing `close_control_client()` on the prior `TmuxMonitor`, leaking a bg thread + `tmux -C attach` subprocess and *doubling* the polling rate.
- **Subprocess fallback is parity-tested for steady state** in t722 but **mid-flight transitions are not**: request issued via control client → control dies before response → fallback retry path. Especially relevant for state-mutating ops (`kill_pane`, `kill_agent_pane_smart`, `send_keys`).
- **Current load:** 4 control-mode clients on the `aitasks` session (1 monitor + 3 minimonitors) — matched 1:1 to live processes, not leaked. Each TUI launch is one persistent `tmux -C attach`. Acceptable, but a new load surface introduced by t719.
- tmux 3.6a; supports `-f no-output,ignore-size`. Not the bottleneck.

## Deliverables

### 1. Reconnect-with-backoff in `TmuxControlBackend`

`.aitask-scripts/monitor/tmux_control.py`:

- When `is_alive` flips False (timeout / EOF / `%exit` / broken pipe), the bg loop respawns `tmux -C attach` with exponential backoff (e.g., 0.5 → 1 → 2 → 4 → 8 s, capped at 30 s).
- After N consecutive failed attempts (e.g., 5), stop trying and stay on subprocess fallback.
- Expose a state enum `connected` / `reconnecting` / `fallback` plus a thread-safe accessor for the UI.
- Reconnect loop must be idempotent w.r.t. `stop()` — `stop()` cancels any pending reconnect.
- Document the contract in the module docstring (it currently says "do not auto-restart" — that statement gets replaced).

### 2. Fix `_start_monitoring()` re-entry leak

`.aitask-scripts/monitor/monitor_app.py` and `.aitask-scripts/monitor/minimonitor_app.py`:

- Before re-initializing `self._monitor` and re-arming `set_interval`, `await close_control_client()` on the prior monitor and cancel the prior interval handle.
- Verify with a regression test (synthetic call) that two consecutive `_start_monitoring()` calls leave exactly one bg thread, one `tmux -C attach` subprocess, and one set_interval timer.

### 3. Footer status indicator

Both monitor and minimonitor apps:

- Tiny inline label showing `control` / `reconnecting` / `fallback`. Polled from the backend's state enum each refresh tick.
- Doesn't consume a dedicated key binding — passive indicator only.

### 4. New `tests/test_tmux_control_resilience.sh`

Covers the gaps left by t722's parity tests (which only assert steady-state behavior):

- **Mid-flight transition:** issue request → externally kill the `tmux -C` subprocess → in-flight request resolves cleanly with `(-1, "")` → next request reconnects (or falls back) without hang.
- **Forced timeout:** trigger a `request_async` timeout via a deliberately slow command → subsequent calls reconnect.
- **Concurrent fallback under reconnect:** 50 sync `tmux_run` calls fired during a forced reconnect window → none raise, none hang, all complete via either control or fallback.
- **Reconnect-then-recover:** kill `tmux -C`; assert state goes `reconnecting`; allow respawn; assert state goes back to `connected` and a follow-up request succeeds via control mode.
- **Max-retries cap:** simulate persistent failure (e.g., point at non-existent session); assert state lands at `fallback` after N attempts and stops retrying.

### 5. Targeted parity assertion for state-mutating user actions

`kill_pane`, `kill_agent_pane_smart`, `send_keys`, `select-window`, `select-pane`:

- Pin down rc-on-target-missing semantics (control client returns `1`; subprocess returns `1`; both with empty stdout) so a retry across a reconnect race cannot double-act.
- Assert in `test_tmux_control_resilience.sh` that "request sent on control before death + retry on subprocess after death" produces the same end state as a single subprocess call, with no double-kill and no spurious error to the user.

### 6. Downgrade and annotate `t719_4_pipe_pane_push`

`aitasks/t719/t719_4_pipe_pane_push.md`:

- Lower priority field from `medium` to `low`.
- Append a `## Stability caveats` section to the task body documenting:
  - **OOM-on-tmux risk**: tmux's `bufferevent` evbuffer grows in tmux server memory when consumers are slow. Sustained slow drain on a busy code agent (Claude Code can burst >100 KB/s during streaming) → unbounded growth → eventual OOM kill of the tmux server. This is the very "tmux crashed" symptom the resilience task addresses; pipe-pane makes it strictly more probable.
  - **Per-pane fd cost** scales with sessions × monitors × panes; on a multi-session dev box the count adds up.
  - **Raw VT-stream complexity** vs `capture-pane`'s rendered output — consumer needs an embedded terminal emulator (or has to round-trip through capture-pane anyway).
  - **Single-threaded tmux event loop** competes with all other clients (real terminal + control mode) on the same loop; per-pane pipe-pane reader events add work.
- Note in the task body that pipe-pane should NOT be implemented until the resilience deliverables here have landed AND been validated on a real workload.

## Verification

- `bash tests/test_tmux_control_resilience.sh` passes.
- `bash tests/test_tmux_control.sh` and `bash tests/test_tmux_run_parity.sh` (from t722) still pass — no regression.
- `bash tests/test_kill_agent_pane_smart.sh` (from t722) still passes.
- Manual smoke: launch `ait monitor`; externally `kill -9 $(pgrep -f 'tmux -C attach')` for the monitor's control client; observe footer flips to `reconnecting`, then back to `control` once respawn succeeds. User actions (kill, send-keys) keep working throughout.
- Manual smoke for re-entry leak: trigger session-rename via `SessionRenameDialog`; assert one bg thread / one tmux client / one timer remain in `ps` / `threading.enumerate()`.
- `aitasks/t719/t719_4_pipe_pane_push.md` shows `priority: low` and a new `## Stability caveats` section with the four bullets above.

## Out of Bounds

- Multi-channel architecture (separate control client for user actions vs polling). Defer to t719_6's architecture-evaluation outcome if reconnect alone proves insufficient under real load.
- Adaptive polling (t719_3) and pipe-pane implementation (t719_4) — both blocked behind this resilience work.
- OS-level / tmux-upstream investigation of the actual tmux-crash reports — needs reproduction with logs first; out of code-change scope here.
- Touching tmux invocations outside `.aitask-scripts/monitor/` (e.g., `agent_launch_utils`, bash helpers).
