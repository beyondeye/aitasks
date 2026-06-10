---
Task: t952_1_python_gateway_core.md
Parent Task: aitasks/t952_centralize_tmux_invocations_shared_gateway.md
Sibling Tasks: aitasks/t952/t952_2_*.md, aitasks/t952/t952_3_*.md, aitasks/t952/t952_4_*.md, aitasks/t952/t952_5_*.md
Worktree: aiwork/t952_1_python_gateway_core
Branch: aitask/t952_1_python_gateway_core
Base branch: main
---

# t952_1 — Python gateway core (`lib/tmux_exec.py`)

Stage 1 of the t952 decomposition — see the parent plan
`aiplans/p952_centralize_tmux_invocations_shared_gateway.md` for the full
cross-cutting context, the socket-knob contract, and the dependency graph.
**Pure addition + unit tests; no call-site migration; no control-mode.**

## Implementation steps

1. **New module `.aitask-scripts/lib/tmux_exec.py`** with class `TmuxClient`:
   - `run(args, timeout=5.0) -> (rc, str)` — sync `subprocess.run` capture.
   - `run_async(args, timeout=5.0) -> (rc, str)` — `asyncio.create_subprocess_exec`.
   - `spawn(args) -> subprocess.Popen` — fire-and-forget.
   - Each prepends `["tmux", *self._socket_args]`.
   - **Preserve `(-1, "")` failure contract verbatim** (FileNotFoundError /
     OSError / TimeoutExpired → `(-1, "")`; async timeout kills proc then
     returns `(-1, "")`). Lift the bodies from
     `monitor/tmux_monitor.py:103-152` so semantics match exactly.

2. **Socket knob (cross-child contract):** module-level
   `tmux_socket_args() -> list[str]` reading env `AITASKS_TMUX_SOCKET`
   (empty → `[]`; else `["-L", value]`). `TmuxClient.__init__` caches it once
   into `self._socket_args` (never read per-call — monitor fallback is a hot
   path). Module docstring documents this as the single future dedicated-socket
   knob, shared with `lib/tmux_exec.sh` (t952_4) and the control attach (t952_3).

3. **Mandatory target formatting:** expose `session_target(session)` →
   `={session}` and `window_target(session, window)` → `={session}:{window}`
   (absorb/re-export from `agent_launch_utils.py:29-48`, preserving the
   trailing-colon idiom for `new-window`).

4. **Persistence argv builder:** add `new_session_argv(session, root, window,
   cmd)` + `_persistent_new_session_prefix` as client methods (move the logic
   from `agent_launch_utils.py:557-621`), injecting `self._socket_args` into the
   `tmux new-session`. The server-existence probe must go through the gateway so
   probe and create share one socket. Keep the systemd-run/setsid/plain ladder
   byte-for-byte.

## Verification

- **New `tests/test_tmux_exec.py`** (mostly no real tmux):
  socket-args prepend (knob set/unset), target-format methods, persistence
  ladder via monkeypatched `shutil.which`/systemd-availability, `(-1,"")` on
  FileNotFoundError; one integration spawn under `require_isolated_tmux`
  (source `tests/lib/tmux_isolation.sh`).
- Existing suite unchanged: `tests/test_tmux_run_parity.sh`,
  `tests/test_launch_in_tmux_pane_pid.py`,
  `tests/test_tmux_exact_session_targeting.sh`.

See **Step 9 (Post-Implementation)** of the task-workflow for archival.
