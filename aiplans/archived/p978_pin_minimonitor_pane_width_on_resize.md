---
Task: t978_pin_minimonitor_pane_width_on_resize.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: Pin minimonitor companion pane width on resize (t978)

## Context

The `minimonitor` companion pane (the narrow ~40-column side column spawned
next to an agent pane by `ait pick` etc.) grows much wider than intended after
the terminal is resized — notably the detach → resize-terminal → reattach
sequence. Observed live: an `agent-pick-891_4` window whose minimonitor
companion pane became very wide.

**Root cause.** The width is set **only once, at spawn time**.
`agent_launch_utils.maybe_spawn_minimonitor()` creates the pane with
`split-window -h -l <width>` (`width=40` default, `.aitask-scripts/lib/agent_launch_utils.py:670`;
override `tmux.minimonitor.width` at `:686-687`; split at `:743-744`). The `-l 40`
sizes the pane only at that instant. tmux then stores the window layout as
**proportions**, so on any later window resize its layout engine rescales every
pane proportionally to fill the new width — a 40-of-N-column pane becomes the
same *fraction* of the now-wider terminal, far exceeding 40 columns. Nothing
re-pins the width afterward: no `resize-pane` anywhere in `.aitask-scripts/`, no
tmux resize hooks, and `minimonitor_app.py` has no width handling (its CSS uses
`1fr`/`auto` and simply adapts to whatever pane width tmux hands it).

**Intended outcome.** The minimonitor companion pane re-pins itself to its
configured width whenever it is resized (including on detach→reattach), so it
never grows above the standard width. Per repo direction (task **t952**, Done),
the new `resize-pane` invocation must go through the shared tmux gateway
(`TmuxClient` in `.aitask-scripts/lib/tmux_exec.py`) — not an inline
`tmux resize-pane` call. This is also enforced by `tests/test_no_raw_tmux.sh`.

## Approach

Three small, additive changes — no behavior change to existing paths.

### 1. Gateway: add `resize_pane` to `TmuxClient` (`.aitask-scripts/lib/tmux_exec.py`)

Make the gateway the sole owner of the `resize-pane` verb, alongside the
existing `session_target` / `window_target` helpers. Add a method that builds
the args and dispatches through the same control-mode-aware path the rest of the
monitor uses (`run_via_control` when a backend is supplied, else `run`):

```python
def resize_pane(
    self, pane: str, *, x: int | None = None, y: int | None = None,
    backend=None, timeout: float = _DEFAULT_TIMEOUT,
) -> tuple[int, str]:
    """Resize ``pane`` to ``x`` columns and/or ``y`` rows.

    Sole owner of the ``resize-pane`` verb. Dispatches via the control client
    when ``backend`` is alive (same strategy as :meth:`run_via_control`), else a
    direct subprocess.
    """
    args = ["resize-pane", "-t", pane]
    if x is not None:
        args += ["-x", str(x)]
    if y is not None:
        args += ["-y", str(y)]
    if backend is not None:
        return self.run_via_control(backend, args, timeout=timeout)
    return self.run(args, timeout=timeout)
```

### 2. Monitor: thin delegation `TmuxMonitor.resize_pane` (`.aitask-scripts/monitor/tmux_monitor.py`)

Mirror the existing `tmux_run` thin-delegation pattern (`:216-231`) so callers
that hold a `TmuxMonitor` (the minimonitor app) reach the gateway with the
live control backend threaded in:

```python
def resize_pane(self, pane: str, *, x: int | None = None,
                y: int | None = None, timeout: float = 2.0) -> tuple[int, str]:
    """Resize a pane via the gateway (control client when alive, else subprocess)."""
    return self._tmux.resize_pane(
        pane, x=x, y=y, backend=self._backend, timeout=timeout
    )
```

### 3. Minimonitor app: re-pin own pane on resize (`.aitask-scripts/monitor/minimonitor_app.py`)

- **Plumb the target width in.** Add a `target_width: int = 40` parameter to
  `MiniMonitorApp.__init__`, stored as `self._target_width`. In `main()` read
  `tmux.minimonitor.width` (the same key the spawner uses) from the already-loaded
  `tmux_config` and pass it:

  ```python
  mm_cfg = tmux_config.get("minimonitor", {})
  target_width = int(mm_cfg["width"]) if isinstance(mm_cfg, dict) and "width" in mm_cfg else 40
  ```
  (`_load_project_tmux_config` at `:1041` already returns the `tmux` section;
  `main()` at `:1055` constructs the app.)

- **Add an `on_resize` handler** (Textual hook — same hook `monitor_app.py:1469`
  and other TUIs already use). When the app's own pane is wider than the target,
  clamp it back through the gateway:

  ```python
  def on_resize(self, event) -> None:
      self._maybe_pin_width()

  def _maybe_pin_width(self) -> None:
      """Re-pin this minimonitor's companion pane to its configured width.

      tmux rescales panes proportionally on a window resize (incl.
      detach→reattach), so a pane spawned at N columns drifts wider. Clamp it
      back to the configured target whenever we exceed it. Self-terminating:
      after the resize the pane width equals the target, so the follow-up
      Resize event no-ops.
      """
      if self._monitor is None:
          return
      own_pane = os.environ.get("TMUX_PANE")
      if not own_pane:
          return
      if self.size.width <= self._target_width:
          return
      self._monitor.resize_pane(own_pane, x=self._target_width)
  ```

  Notes:
  - **No oscillation.** The handler acts only when strictly wider than the
    target; once tmux clamps the pane to the target, `self.size.width` equals
    the target and the next Resize returns early. Worst case is one extra tmux
    call per genuine resize.
  - **Narrow-terminal safety.** If the window is too narrow for the target,
    tmux clamps `-x` to what fits; `self.size.width` stays ≤ target, so no
    repeat.
  - Routes entirely through the gateway → satisfies `test_no_raw_tmux.sh`.

## Files to modify

- `.aitask-scripts/lib/tmux_exec.py` — add `TmuxClient.resize_pane`.
- `.aitask-scripts/monitor/tmux_monitor.py` — add `TmuxMonitor.resize_pane` thin delegation.
- `.aitask-scripts/monitor/minimonitor_app.py` — `target_width` param + `main()` config read + `on_resize`/`_maybe_pin_width`.
- `tests/test_tmux_exec.py` — add a case asserting `resize_pane` arg construction (`resize-pane -t <pane> -x <n>`), following the existing arg-assertion style in that file.

## Rejected / deferred

- **tmux `client-resized` hook** (install a global hook that re-applies
  `resize-pane`): global, harder to scope to the right pane, and leaves a hook
  installed on the user's server. The app-owned `on_resize` keeps the constraint
  local to the minimonitor and tears down with it. Rejected.
- **`main-vertical` layout with `main-pane-width`**: would reshape the whole
  window layout (affects the agent pane too) and fights the simple `-h` split
  the spawner uses. Rejected as larger blast radius.
- **Centralizing the default-40 duplication** between `agent_launch_utils.py`
  and `minimonitor_app.main()`: both independently read the same config key with
  a 40 default. Noted but **deferred** — folding into one shared constant is a
  separate cleanup, not required for the fix.

## Verification

1. **Unit:** `python tests/test_tmux_exec.py` (and the new `resize_pane` case);
   `bash tests/test_no_raw_tmux.sh` (confirms no raw `tmux` introduced);
   `bash tests/test_tmux_run_parity.sh`.
2. **Smoke:** `bash tests/test_multi_session_minimonitor.sh`.
3. **Manual (the reported scenario):**
   - `ait pick <N>` so an `agent-*` window spawns with a minimonitor companion pane (~40 cols).
   - Detach tmux (`prefix d`), resize the terminal much wider, reattach (`tmux attach`).
   - Confirm the minimonitor pane snaps back to ~40 columns instead of staying proportionally wide.
   - Also resize the terminal live (no detach) and confirm the pane stays pinned.
   - Set `tmux.minimonitor.width: 50` in `aitasks/metadata/project_config.yaml`, relaunch, and confirm it pins to 50.

## Risk

### Code-health risk: low
- All three changes are additive (new gateway method + thin delegation + a new
  Textual hook); no existing path changes behavior. Blast radius is confined to
  the minimonitor and the tmux gateway. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- The fix depends on Textual emitting a `Resize` event to `MiniMonitorApp` on
  tmux detach→reattach. This is the standard behavior (the driver re-reports
  size on reattach, as the other TUIs' `on_resize` handlers rely on), and the
  live-resize path is covered regardless; manual verification confirms the
  reattach case explicitly. · severity: low · → mitigation: TBD

## Post-implementation

Follow task-workflow Step 8 (user review) → Step 9 (archival via
`./.aitask-scripts/aitask_archive.sh 978`, then `./ait git push`). Commit
message: `bug: Pin minimonitor companion pane width on resize (t978)`.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. (1) Added
  `TmuxClient.resize_pane(pane, *, x=None, y=None, backend=None, timeout=...)`
  to `.aitask-scripts/lib/tmux_exec.py` as the sole owner of the `resize-pane`
  verb, dispatching through `run_via_control` when a backend is supplied else a
  direct `run`. (2) Added a thin `TmuxMonitor.resize_pane` delegation in
  `.aitask-scripts/monitor/tmux_monitor.py`, mirroring the `tmux_run` pattern.
  (3) In `.aitask-scripts/monitor/minimonitor_app.py` added a `target_width`
  constructor param (default 40), read `tmux.minimonitor.width` in `main()`, and
  added `on_resize` → `_maybe_pin_width()` that clamps the companion pane back to
  the target when it exceeds it. (4) Added 4 `TestResizePane` cases to
  `tests/test_tmux_exec.py`.
- **Deviations from plan:** None.
- **Issues encountered:** None. The `resize_pane` test asserts against
  `tmux_exec._DEFAULT_TIMEOUT` (module constant) rather than hardcoding a value,
  matching the gateway's default.
- **Key decisions:** The `resize-pane` verb construction lives in the gateway
  (per t952 direction and the user's steer) with an optional `backend` param so
  the minimonitor reaches it via `TmuxMonitor.resize_pane` with the live control
  backend threaded in — same shape as `tmux_run`. The clamp is strictly
  "only when wider than target", which makes it self-terminating (no oscillation)
  and narrow-terminal-safe (tmux clamps `-x` to fit).
- **Upstream defects identified:** None.
- **Verification:** `python tests/test_tmux_exec.py` (41 passed),
  `bash tests/test_no_raw_tmux.sh` (5/5), `bash tests/test_tmux_run_parity.sh`
  (pass), `bash tests/test_multi_session_minimonitor.sh` (39/39), byte-compile of
  all edited modules OK. The tmux detach→reattach behavior is the plan's manual
  verification step (cannot be covered by automated tests).
