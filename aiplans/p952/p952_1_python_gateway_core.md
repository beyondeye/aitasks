---
Task: t952_1_python_gateway_core.md
Parent Task: aitasks/t952_centralize_tmux_invocations_shared_gateway.md
Sibling Tasks: aitasks/t952/t952_2_*.md, aitasks/t952/t952_3_*.md, aitasks/t952/t952_4_*.md, aitasks/t952/t952_5_*.md
Worktree: aiwork/t952_1_python_gateway_core
Branch: aitask/t952_1_python_gateway_core
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-10 13:03
---

# t952_1 — Python gateway core (`lib/tmux_exec.py`)

## Context

Stage 1 of the t952 tmux-centralization decomposition (parent plan:
`aiplans/p952_centralize_tmux_invocations_shared_gateway.md`). Introduces the
Python tmux command **gateway** that will become the only place a raw `tmux`
process is spawned from Python. **Pure addition + unit tests** — builds the
gateway, migrates **no** call sites, does **not** touch control-mode.
Behavior-preserving by construction (nothing imports it yet). It is the
foundation t952_2 (Python migration), t952_3 (control-mode + monitor), and
t952_4 (shell mirror) build on — they depend only on this child's **contract**
(the `AITASKS_TMUX_SOCKET` env var, the typed-method signatures, the
`(rc, stdout)` failure contract), not its internals.

**Anchors re-verified against the live tree (verify pass, 2026-06-10):**
`tmux_session_target`/`tmux_window_target` @ `agent_launch_utils.py:29-48`;
`_persistent_new_session_prefix` @ `:557`, `_new_session_tmux_argv` @ `:592`
(server-existence probe `get_tmux_sessions()` @ `:606` — the split-brain
concern is real); spawn primitives `_run_tmux_async`/`_run_tmux_subprocess` @
`monitor/tmux_monitor.py:103-152`. All accurate; no plan changes needed.

## Key files to modify
- **NEW** `.aitask-scripts/lib/tmux_exec.py` — the `TmuxClient` gateway module.
- **NEW** `tests/test_tmux_exec.py` — unit + one isolated integration test.

## Reference files (read-only, reuse — do not rebuild)
- `agent_launch_utils.py:29-48` — `tmux_session_target()` (`={session}`) /
  `tmux_window_target()` (`={session}:{window}`). The gateway absorbs/re-exports
  these and makes them **mandatory** (typed methods).
- `agent_launch_utils.py:557-621` — `_persistent_new_session_prefix` /
  `_new_session_tmux_argv` (systemd-run → setsid → plain persistence ladder, and
  the `get_tmux_sessions()` server-existence probe). **Move this logic** into the
  gateway; keep the ladder byte-for-byte (load-bearing for t943/t956 server
  survival).
- `monitor/tmux_monitor.py:103-152` — the `(-1, "")`-on-error spawn primitives
  whose contract the gateway preserves verbatim.

## Implementation plan
1. **`TmuxClient` spawn surface:**
   - `run(args, timeout=5.0) -> (rc, str)` — sync `subprocess.run` capture.
   - `run_async(args, timeout=5.0) -> (rc, str)` — `asyncio.create_subprocess_exec`.
   - `spawn(args) -> subprocess.Popen` — fire-and-forget, no capture.
   - Each prepends `["tmux", *self._socket_args]`. Preserve the `(-1, "")`
     failure contract exactly (FileNotFoundError / OSError / TimeoutExpired →
     `(-1, "")`; async timeout kills the proc then returns `(-1, "")`). Lift the
     bodies from `tmux_monitor.py:103-152` so semantics match.
2. **Socket knob (the cross-child contract):** module-level
   `tmux_socket_args() -> list[str]` reading env `AITASKS_TMUX_SOCKET` (empty →
   `[]`; non-empty → `["-L", value]`). `TmuxClient.__init__` caches it **once**
   into `self._socket_args` (never per-call — monitor fallback is a hot path).
   Docstring marks `AITASKS_TMUX_SOCKET` as the single future dedicated-socket
   knob, shared with `lib/tmux_exec.sh` (t952_4) and the control attach (t952_3).
3. **Mandatory target formatting:** expose `session_target(session)` /
   `window_target(session, window)` on the client (re-export the existing module
   functions), preserving `={session}` / `={session}:{window}` and the
   trailing-colon `new-window` idiom.
4. **Persistence argv builder:** add `new_session_argv(session, root, window,
   cmd)` (+ `_persistent_new_session_prefix`) as client methods, injecting
   `self._socket_args` into the `tmux new-session`. The server-existence probe
   must go through the gateway's own `run(["list-sessions", ...])` so probe and
   create share one socket (no split-brain). Keep systemd-run/setsid/plain
   byte-for-byte.

## Risk

### Code-health risk: low
- Moved persistence ladder (systemd-run/setsid/plain) must stay byte-faithful —
  it is load-bearing for t943/t956 server survival, but only goes live when
  t952_2 activates it · severity: low · → mitigation: the persistence-ladder
  unit test in this plan's verification (no follow-up task needed).
- Pure addition with zero live callers in this child → no existing path can
  regress. Blast radius: one new module + one new test.

### Goal-achievement risk: low
- The gateway interface is a contract t952_2/3/4 consume, so a wrong surface has
  amplified downstream cost · severity: low · → mitigation: contract is pinned
  by the task body and was pressure-tested during parent planning; children
  exercise it directly. None identified beyond this.

## Verification
- **`tests/test_tmux_exec.py`** (no real tmux for most):
  - socket-args prepend with `AITASKS_TMUX_SOCKET` set / unset;
  - target-format methods (`=session`, `=session:window`, trailing colon);
  - persistence ladder via monkeypatched `shutil.which` / `_systemd_user_available`
    → assert systemd-run vs setsid vs plain argv shape;
  - `(-1, "")` contract on FileNotFoundError;
  - one integration spawn under `require_isolated_tmux` (source
    `tests/lib/tmux_isolation.sh`).
- Existing suite unchanged (nothing migrated yet): `tests/test_tmux_run_parity.sh`,
  `tests/test_launch_in_tmux_pane_pid.py`, `tests/test_tmux_exact_session_targeting.sh`.

See **Step 9 (Post-Implementation)** of the task-workflow for archival.
