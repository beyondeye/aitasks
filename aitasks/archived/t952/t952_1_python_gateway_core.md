---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: refactor
status: Done
labels: [tmux, ait_bridge]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-10 12:47
updated_at: 2026-06-10 13:17
completed_at: 2026-06-10 13:17
---

## Context

Stage 1 of the t952 tmux-centralization decomposition (see `aiplans/p952_*`).
Introduces the Python tmux command **gateway** that will become the only place
a raw `tmux` process is spawned from Python. This child is a **pure addition +
unit tests** — it builds the gateway and migrates **no** call sites and does
**not** touch control-mode. Behavior-preserving by construction (nothing calls
it yet).

This is the foundation the other children build on. Children t952_2 (simple
Python migration), t952_3 (control-mode absorption + monitor re-point), and
t952_4 (shell mirror) all depend only on this child's **contract** — the
`AITASKS_TMUX_SOCKET` env var name (default empty → no flag), the typed-method
signatures, and the `(rc, stdout)` failure contract — not its internals.

## Key files to modify
- **NEW** `.aitask-scripts/lib/tmux_exec.py` — the `TmuxClient` gateway module.

## Reference files for patterns (read-only)
- `.aitask-scripts/lib/agent_launch_utils.py:29-48` — existing
  `tmux_session_target()` (`={session}`) and `tmux_window_target()`
  (`={session}:{window}`) helpers. The gateway absorbs / re-exports these and
  makes them **mandatory** (typed methods, not optional helpers).
- `.aitask-scripts/lib/agent_launch_utils.py:557-621` — existing
  `_persistent_new_session_prefix` / `_new_session_tmux_argv` (the new-session
  systemd-run / setsid / plain persistence-wrapping argv builder). **Move
  ownership** of this logic into the gateway (do not rebuild it).
- `.aitask-scripts/monitor/tmux_monitor.py:103-152` — the existing raw spawn
  primitives `_run_tmux_async()` (asyncio) and `_run_tmux_subprocess()` (sync),
  whose exact `(-1, "")`-on-FileNotFoundError/OSError/timeout contract the
  gateway must preserve verbatim.

## Implementation plan
1. Create `TmuxClient` with the spawn surface:
   - `run(args, timeout=5.0) -> (rc, str)` — sync, `subprocess.run` capture.
   - `run_async(args, timeout=5.0) -> (rc, str)` — `asyncio.create_subprocess_exec`.
   - `spawn(args) -> Popen` — fire-and-forget, no capture.
   - All three prepend `["tmux", *self._socket_args]` to the argv.
   - Preserve the `(-1, "")` failure contract exactly (FileNotFoundError /
     OSError / TimeoutExpired → `(-1, "")`; async timeout kills the proc).
2. **Socket knob (the one cross-child contract):** module-level
   `tmux_socket_args() -> list[str]` reading env `AITASKS_TMUX_SOCKET` (empty →
   `[]`; non-empty → `["-L", value]` — pick `-L` socket-name form). `TmuxClient`
   caches it **once at construction** into `self._socket_args` (never per-call —
   the monitor fallback is a perf hot path). Document `AITASKS_TMUX_SOCKET` as
   the single future dedicated-socket knob.
3. **Mandatory target formatting:** expose `session_target(session)` and
   `window_target(session, window)` on the client (or re-export the existing
   module functions) so callers cannot hand-format `-t`. Keep the existing
   `={session}` / `={session}:{window}` semantics (incl. trailing-colon idiom).
4. **Persistence argv builder:** add `new_session_argv(session, root, window,
   cmd) -> list[str]` (+ the `_persistent_new_session_prefix` helper) as
   client methods, injecting `self._socket_args` into the eventual
   `tmux new-session`. Its server-existence probe (currently
   `get_tmux_sessions()`) must go through the gateway so probe and create share
   the same socket — no split-brain. Keep the systemd-run/setsid/plain
   degradation ladder byte-for-byte.

## Verification
- **NEW** `tests/test_tmux_exec.py` (no real tmux needed for most):
  - socket-args prepend asserted with `AITASKS_TMUX_SOCKET` set and unset;
  - target-format methods (`=session`, `=session:window`, trailing colon);
  - persistence ladder via monkeypatched `shutil.which` / systemd-availability
    → assert systemd-run vs setsid vs plain argv shape;
  - `(-1, "")` contract on FileNotFoundError.
  - One integration test that actually spawns tmux under
    `require_isolated_tmux` (source `tests/lib/tmux_isolation.sh`).
- Run the existing tmux suite to confirm no regression (nothing should change
  yet): `test_tmux_run_parity.sh`, `test_launch_in_tmux_pane_pid.py`,
  `test_tmux_exact_session_targeting.sh`.
- This child gets its own Risk evaluation at pick time.
