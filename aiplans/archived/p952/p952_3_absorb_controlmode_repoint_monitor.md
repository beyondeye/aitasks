---
Task: t952_3_absorb_controlmode_repoint_monitor.md
Parent Task: aitasks/t952_centralize_tmux_invocations_shared_gateway.md
Sibling Tasks: aitasks/t952/t952_1_*.md, aitasks/t952/t952_2_*.md, aitasks/t952/t952_4_*.md, aitasks/t952/t952_5_*.md
Archived Sibling Plans: aiplans/archived/p952/p952_1_python_gateway_core.md, aiplans/archived/p952/p952_2_migrate_python_subprocess_sites.md
Worktree: aiwork/t952_3_absorb_controlmode_repoint_monitor
Branch: aitask/t952_3_absorb_controlmode_repoint_monitor
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-10 17:41
---

# t952_3 — Absorb control-mode + re-point monitor (perf-sensitive)

Stage 3 of the t952 tmux-centralization decomposition. Depends on **t952_1**
(done). **Behavior-preserving.**

## Context

The Python tmux gateway `lib/tmux_exec.py` (`TmuxClient`, from t952_1) already
owns the per-tick subprocess primitives `run` / `run_async` / `spawn` — exact
byte-for-byte ports of `monitor/tmux_monitor.py`'s `_run_tmux_subprocess` /
`_run_tmux_async`, including the `(-1, "")`-on-error contract — and the socket
flag from `AITASKS_TMUX_SOCKET`. t952_2 (done) migrated the simple Python
subprocess sites onto it.

Two tmux-spawning concerns are still **outside** the gateway:

1. The **control-mode dispatcher** — the "control-client when alive, subprocess
   fallback on `rc == -1`" logic is inlined in `TmuxMonitor.tmux_run`
   (`tmux_monitor.py:266-285`) and `TmuxMonitor._tmux_async` (`:255-264`). This
   is the monitor refresh **hot path**.
2. The **persistent control client** `tmux -C attach` spawn
   (`monitor/tmux_control.py:98-99`) — a raw `tmux` process that does **not**
   thread the socket flag, so it would diverge from the gateway under a
   dedicated-socket move.

This child folds the dispatcher into the gateway and threads the socket flag
into the control attach, so the gateway becomes the single owner of *both* the
exec-strategy choice and every raw `tmux` spawn on the Python side.

## ⚠️ t822_3 coordination — re-verified at pick time (2026-06-10)

t822_3 (`monitor_port_design`) is still **`Ready` — not started**. Re-checking
its task definition corrected the original assumption: **t822_3 is a
documentation-only task** ("Produces no code changes under
`.aitask-scripts/monitor/`" — t822_3 lines 12, 20, 90). It only *reads*
`tmux_monitor.py` / `tmux_control.py` to write
`aidocs/applink/monitor_port_design.md`, which specs a *future* `monitor_core`
extraction. So there is **no hard concurrent-code collision** — the original
"rebase or collide" framing was over-stated.

The genuine coordination concern is that t822_3's design doc (a) enumerates the
`monitor_core` public API including `TmuxControlBackend / TmuxControlClient` and
the tmux exec path, and (b) cites specific `tmux_control.py` / `tmux_monitor.py`
line ranges. After t952_3 lands, the **exec-strategy dispatcher lives in
`lib/tmux_exec.py`, not in `monitor/`**, the helpers `_run_tmux_subprocess` /
`_run_tmux_async` are gone, and line numbers shift. t822_3's design must
therefore treat the gateway as the tmux-exec substrate `monitor_core`
*delegates to* (not re-owns), and note that the physical relocation of
`TmuxControlBackend` / `TmuxControlClient` into the core is the natural home for
the move t952_3 deliberately deferred.

**Per the user's instruction, this child updates t822_3's task definition** to
add a forward pointer to this refactor (see implementation step below), so
whoever picks t822_3 — reading its task file, not this plan — is warned.

## Design decision (resolves the two "decide at plan time" forks in the task body)

The task body left two choices open. Both are resolved toward **minimum blast
radius**, consistent with the t822_3 coordination and the staged-refactor
intent of the parent:

**(1) Gateway owns the dispatcher + socket; control-client classes stay in
`monitor/tmux_control.py` (physical relocation DEFERRED to t822_3).**

- The gateway gains the *dispatch policy* (try-backend-then-subprocess) and the
  *socket threading*. The `TmuxControlBackend` / `TmuxControlClient` *class
  definitions* stay where they are for now.
- Rationale — blast radius: physically moving `tmux_control.py` → `lib/` would
  touch **5 importers** (`monitor/monitor_app.py`, `monitor/minimonitor_app.py`,
  `monitor/tmux_monitor.py`, `tests/test_tmux_control.sh`,
  `tests/test_tmux_control_resilience.sh`) and collide head-on with t822_3,
  which is extracting exactly these files into `monitor_core`. Moving the file
  now is double-churn: t822_3 will re-home it anyway. The reusability the task
  asks for ("control-mode reusable beyond monitor") is delivered by the
  *dispatcher living in `lib/`* — any caller can construct a backend and pass it
  to the gateway dispatcher; the class's physical home rides with monitor_core.
- "What if someone edits this unaware?" — after this change the fallback-on-`-1`
  logic exists in **exactly one place** (the gateway). `TmuxMonitor.tmux_run` /
  `_tmux_async` become pure one-line delegations, so there is no second copy to
  drift.

**(2) DELETE the now-orphaned raw helpers `_run_tmux_subprocess` /
`_run_tmux_async` from `tmux_monitor.py`.**

- The gateway's `run` / `run_async` are already byte-identical ports and become
  the canonical fallback primitives. After the dispatcher delegates to the
  gateway, the two module-level helpers have **zero remaining callers** (grep
  confirms: only the two dispatcher sites use them; nothing in `tests/` imports
  them). Keeping them would be exactly the duplication t952 exists to remove,
  and t952_5's lint guard then only needs to whitelist the gateway.

**Dependency direction.** `monitor/` already imports from `lib/` (e.g.
`tmux_monitor.py` does `from agent_launch_utils import …` after inserting
`_LIB_DIR` on `sys.path`). So `tmux_control.py` importing `tmux_socket_args`
from `tmux_exec` is the correct `monitor → lib` direction. The gateway dispatcher
takes the backend as a **parameter** (duck-typed: `.is_alive`,
`.request_sync`, `.request_async`) — it does **not** import from `monitor/`,
avoiding a `lib → monitor` cycle and keeping the gateway stateless w.r.t. the
control channel (the backend lifecycle stays owned by `TmuxMonitor`).

## Key files to modify

### `.aitask-scripts/lib/tmux_exec.py` — grow the control-mode dispatcher
Add two methods to `TmuxClient`, porting `tmux_monitor.py:255-285` **verbatim**
(the `rc != -1` fallback branch is load-bearing). The backend is passed in:

```python
def run_via_control(
    self, backend, args: list[str], timeout: float = _DEFAULT_TIMEOUT
) -> tuple[int, str]:
    """Control-client when alive, subprocess fallback on rc == -1 (sync).

    `backend` is a control-mode backend (duck-typed: `.is_alive` /
    `.request_sync`) or None. Behavior-preserving port of
    `TmuxMonitor.tmux_run`'s dispatch.
    """
    if backend is not None and backend.is_alive:
        rc, out = backend.request_sync(args, timeout=timeout)
        if rc != -1:
            return rc, out
    return self.run(args, timeout=timeout)

async def run_async_via_control(
    self, backend, args: list[str], timeout: float = _DEFAULT_TIMEOUT
) -> tuple[int, str]:
    """Async sibling — port of `TmuxMonitor._tmux_async`'s dispatch."""
    if backend is not None and backend.is_alive:
        rc, out = await backend.request_async(args, timeout=timeout)
        if rc != -1:
            return rc, out
    return await self.run_async(args, timeout=timeout)
```

### `.aitask-scripts/monitor/tmux_control.py` — thread socket into `tmux -C attach`
- Add a `_LIB_DIR` `sys.path` insert + `from tmux_exec import tmux_socket_args`
  at module top (mirror `tmux_monitor.py:30-33`), so the file resolves
  `tmux_exec` even when imported directly as `monitor.tmux_control` by the test
  harnesses (`PYTHONPATH=.aitask-scripts`).
- `TmuxControlClient.__init__`: accept `socket_args: list[str] | None = None`;
  cache `self._socket_args = list(socket_args) if socket_args is not None else
  tmux_socket_args()` **once** (never per-call — hot path).
- Extract an `_attach_argv()` method (so the argv is unit-testable without
  spawning) and call it from `start()`:
  ```python
  def _attach_argv(self) -> list[str]:
      # socket flag goes between "tmux" and "-C"
      return ["tmux", *self._socket_args, "-C", "attach", "-t", self.session,
              "-f", "no-output,ignore-size"]
  ```
  `start()` uses `*self._attach_argv()` in `create_subprocess_exec`.
- `TmuxControlBackend.__init__`: accept and store `socket_args` the same way,
  and pass it through to **every** `TmuxControlClient(...)` it constructs — both
  in `start()` (line ~345) and in the supervisor's reconnect (`_supervisor_loop`,
  line ~415) — so a reconnected client keeps the socket flag.

### `.aitask-scripts/monitor/tmux_monitor.py` — re-point dispatcher, delete orphaned helpers
- `__init__`: add `from tmux_exec import TmuxClient` (top, alongside the existing
  `agent_launch_utils` import) and `self._tmux = TmuxClient()`.
- `_tmux_async` (`:255-264`) → one-line delegation:
  ```python
  async def _tmux_async(self, args, timeout=5.0):
      return await self._tmux.run_async_via_control(self._backend, args, timeout=timeout)
  ```
- `tmux_run` (`:266-285`) → keep the docstring, body becomes:
  ```python
  return self._tmux.run_via_control(self._backend, args, timeout=timeout)
  ```
- **Delete** `_run_tmux_async` (`:103-128`) and `_run_tmux_subprocess`
  (`:131-152`) — now orphaned. Update the stale docstring reference at
  `tmux_control.py:185` ("mirror `tmux_monitor._run_tmux_async`") to point at the
  gateway.

### `aitasks/t822/t822_3_monitor_port_design.md` — add coordination pointer (per user instruction)
Append a coordination note so a future t822_3 picker is warned. Insert after the
`## Depends on` section (it has no code-dependency, only a design-accuracy one):

```markdown
## Coordination — tmux gateway (t952_3)

t952_3 ("absorb control-mode + re-point monitor") moves the tmux **exec-strategy
dispatcher** (control-client-when-alive, subprocess-fallback-on-`-1`) and the
socket-flag ownership into `lib/tmux_exec.py` (`TmuxClient.run_via_control` /
`run_async_via_control`), threads `AITASKS_TMUX_SOCKET` into the `tmux -C attach`
spawn, and deletes the `_run_tmux_subprocess` / `_run_tmux_async` helpers from
`tmux_monitor.py`. When writing the monitor_core design:
- Treat `lib/tmux_exec.py` as the tmux-exec substrate that `monitor_core`
  **delegates to** — do NOT design monitor_core to re-own the dispatcher.
- The physical relocation of `TmuxControlBackend` / `TmuxControlClient` out of
  `monitor/tmux_control.py` was deliberately deferred from t952_3 to ride with
  this extraction — monitor_core is their natural home.
- Re-verify all `tmux_control.py` / `tmux_monitor.py` file:line citations after
  t952_3 lands; the line numbers shift and the two deleted helpers are gone.
```

Update t822_3's `updated_at` to the current timestamp. Commit the task-file
change via `./ait git` (it lives on the aitask-data branch) — separately from
the code commit, e.g. `ait: Add t952_3 coordination note to t822_3`.

## Reference / pattern files (read-only)
- `lib/tmux_exec.py:141-198` — `run` / `run_async` (the fallback primitives the
  dispatcher delegates to) and the `_argv` socket-prepend.
- `tmux_monitor.py:30-40` — the `_LIB_DIR` `sys.path` insert + `from <lib> import`
  pattern to mirror in `tmux_control.py`.
- `tmux_control.py:88-121` — current `start()` / attach spawn.

## Verification
- **Keystone oracle:** `bash tests/test_tmux_run_parity.sh` — runs
  `monitor.tmux_run` with the backend on (request_sync) and off (subprocess
  fallback) and asserts identical `(rc, stdout)` vs raw `subprocess`. With
  `AITASKS_TMUX_SOCKET` unset, the gateway argv is `["tmux", *args]` —
  byte-identical to today, so parity holds. This is the behavior-preservation
  oracle.
- `bash tests/test_tmux_control.sh`, `bash tests/test_tmux_control_resilience.sh`
  — control client + reconnect/resilience still green (constructors gain an
  optional arg defaulting to today's behavior).
- **New attach-argv assertion** (add to `tests/test_tmux_exec.py`, no real
  tmux): construct `TmuxControlClient(session="s", socket_args=["-L","sock"])`
  and assert `_attach_argv()` == `["tmux","-L","sock","-C","attach","-t","s",
  "-f","no-output,ignore-size"]`; and with default (env unset) that no `-L`
  appears. Also a dispatcher unit test with a fake backend: `request_sync`
  returning `(-1,"")` falls through to `run`; returning `(0,"x")` short-circuits.
- Run the tmux suites under `require_isolated_tmux` (the test scripts already
  source `tests/lib/tmux_isolation.sh`).
- Sanity-import all three modules to catch import/name errors.

See **Step 9 (Post-Implementation)** of the task-workflow for archival.

## Risk

### Code-health risk: medium
- Edits two hot-path monitor files (`monitor/tmux_monitor.py`,
  `monitor/tmux_control.py`) and shifts line numbers / deletes helpers that
  t822_3's design doc cites · severity: medium · → mitigation: t822_3 is
  doc-only (no concurrent code edit — re-verified at pick time), so there is no
  merge collision; this child proactively updates t822_3's task definition with
  a coordination pointer so its future design reflects the moved dispatcher and
  re-checks its line citations. The monitor/ edit surface is minimized (no file
  relocation; dispatcher reduced to one-line delegations).
- Monitor refresh hot path: a per-call socket-env read would regress refresh
  latency · severity: low · → mitigation: socket args cached once at client
  construction (never per-call), mirroring the established t952_1 pattern.
- Deleting `_run_tmux_subprocess` / `_run_tmux_async` removes load-bearing
  fallback primitives from `tmux_monitor.py` · severity: low · → mitigation: the
  gateway's `run` / `run_async` are byte-identical ports and become the sole
  fallback; the keystone parity oracle (`test_tmux_run_parity.sh`) exercises the
  fallback path on every subcommand.

### Goal-achievement risk: low
- Behavior-preserving verbatim port of a proven pattern (t952_1/t952_2) with a
  dedicated behavior-preservation oracle (`test_tmux_run_parity.sh`) · severity:
  low · → mitigation: none needed beyond the verification section. None
  identified beyond this.

## Rejected alternatives
- **Physically move `tmux_control.py` → `lib/` now.** Rejected: 5-importer blast
  radius + direct collision with t822_3's `monitor_core` extraction (which
  re-homes these files anyway). Deferred to ride with monitor_core.
- **Gateway holds the backend as state** (`self._tmux.backend = …`). Rejected:
  couples the stateless gateway to monitor's backend lifecycle; passing the
  backend per-call keeps the gateway stateless and the dispatcher reusable by
  any caller.
- **Keep `_run_tmux_subprocess` / `_run_tmux_async` as documented exceptions.**
  Rejected: they would be zero-caller duplicates of the gateway's `run` /
  `run_async` — exactly the duplication t952 removes; deletion shrinks t952_5's
  lint allowlist to just the gateway.

## Final Implementation Notes
- **Actual work done:** (1) `lib/tmux_exec.py` — added `TmuxClient.run_via_control`
  / `run_async_via_control`, a verbatim port of the former
  `TmuxMonitor.tmux_run` / `_tmux_async` dispatch ("control client when alive,
  subprocess fallback on `rc == -1`"); the backend is a duck-typed parameter, so
  the gateway has no `monitor/` dependency and stays stateless w.r.t. the
  channel. (2) `monitor/tmux_control.py` — `_LIB_DIR` `sys.path` insert +
  `from tmux_exec import tmux_socket_args`; `socket_args` cached once in
  `TmuxControlClient` and `TmuxControlBackend`; new `_attach_argv()` threads the
  socket flag between `"tmux"` and `"-C"`; backend passes its cached socket args
  to every client it builds, including the supervisor reconnect. (3)
  `monitor/tmux_monitor.py` — `self._tmux = TmuxClient()`; `tmux_run` /
  `_tmux_async` reduced to one-line delegations; deleted the orphaned
  `_run_tmux_subprocess` / `_run_tmux_async`. (4) `tests/test_tmux_exec.py` —
  +10 tests (dispatcher: None/dead → subprocess, alive → short-circuit, `-1` →
  fallback, `rc==1` → no retry, sync+async; attach-argv socket threading,
  default-from-env). (5) Per user instruction, added a coordination pointer to
  `aitasks/t822/t822_3_monitor_port_design.md`.
- **Deviations from plan:** none in approach. Beyond the plan: tidied three now-
  stale gateway docstrings in `tmux_exec.py` that referenced the deleted
  `_run_tmux_*` helpers / described t952_3 as "a later stage" (current-state
  doc convention).
- **Issues encountered:** none. The keystone parity oracle
  (`test_tmux_run_parity.sh`) passed first try on both the backend-on
  (`request_sync`) and subprocess-fallback paths; control + resilience suites
  green. No `AIT_NO_SYSTEMD_RUN` workaround needed (this child does not exercise
  `new_session_argv`'s systemd-run rung).
- **Key decisions:** backend passed **per-call** (not held as gateway state) to
  avoid coupling the stateless gateway to monitor's backend lifecycle and to
  avoid a `lib → monitor` import cycle; the `monitor → lib` direction
  (`tmux_control` importing `tmux_socket_args`) is the correct one and already
  used by `tmux_monitor`.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t952_4 (shell mirror):** read the same `AITASKS_TMUX_SOCKET` (`-L` form);
    no Python coupling with this child.
  - **t952_5 (registry collapse + lint guard):** after this child, the *only*
    Python sites still spawning raw `tmux` outside the gateway's `run`/`run_async`/
    `spawn` are `monitor/tmux_control.py`'s `_attach_argv()` (the control attach —
    now carries the socket flag and is the gateway's control-mode primitive;
    whitelist it) and the two registry readers in `agent_launch_utils.py` (yours).
    The `_run_tmux_subprocess` / `_run_tmux_async` helpers are **gone** — do not
    whitelist them.
  - **t822_3 (monitor_port_design):** its task file now carries a coordination
    note; `monitor_core` should delegate tmux exec to `lib/tmux_exec.py`, and the
    physical relocation of `TmuxControlBackend`/`TmuxControlClient` into the core
    is the natural home for the move deferred here.
