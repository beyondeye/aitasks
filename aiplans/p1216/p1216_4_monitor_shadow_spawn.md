---
Task: t1216_4_monitor_shadow_spawn.md
Parent Task: aitasks/t1216_monitor_shadow_pane_view_and_concern_picker.md
Sibling Tasks: aitasks/t1216/t1216_1_shared_shadow_seam.md, aitasks/t1216/t1216_2_monitor_shadow_zone.md, aitasks/t1216/t1216_3_monitor_concern_picker.md
Base branch: main
Output branch: main
---

# p1216_4 — Port shadow spawn (`e` / `E`) to the full monitor

Depends on **t1216_1** (the shared seam, incl. the **sync** `find_shadow_pane`
the duplicate guard needs).

## Goal

Bring `e` (launch shadow) and `E` (launch shadow, pick agent) to `ait monitor`,
acting on the **selected** agent. Without this the monitor still cannot create a
shadow and the user keeps bouncing to minimonitor — the friction t1216 exists to
remove.

## Step 1 — dedupe `_load_project_tmux_config`

The identical function exists twice: `minimonitor_app.py:1695-1706` and
`monitor_app.py:1993`. Both read `aitasks/metadata/project_config.yaml` and
return `data.get("tmux", {})`. Move one copy to the shared module (alongside the
t1216_1 lifts) and delete both. This is on the parent's "must not grow the known
duplication set" list.

## Step 2 — lift `_spawn_shadow`

Move `minimonitor_app._spawn_shadow` (L1191-1271) to the shared module:

```python
def spawn_shadow(
    monitor, *, full_cmd: str, followed_pane: str, task_id: str | None,
    target_root: Path, snap: PaneSnapshot, session: str, companion_pane: str,
    notify,
) -> str | None:
```

Preserve verbatim:

- `tmux_cfg = load_project_tmux_config(target_root)`;
  `same_window = bool(tmux_cfg.get("shadow_same_window", True))`;
  `shadow_width = int(tmux_cfg.get("shadow_pane_width", 60))` with
  `TypeError` / `ValueError` → 60.
- **Same-window branch:** `TmuxLaunchConfig(session=session,
  window=snap.pane.window_name, new_session=False, new_window=False,
  split_direction=str(tmux_cfg.get("default_split", "horizontal")),
  split_size=shadow_width, split_target_pane=followed_pane,
  cwd=str(target_root))`. The split targets the **agent pane** — not the
  window's active pane, which in minimonitor's case is the narrow sidebar.
- **Separate-window branch:** `new_window=True`,
  `window=f"agent-shadow-{task_id or 'x'}"`.
- `pane_pid, err = launch_in_tmux(full_cmd, cfg)` → notify and return on error.
- `shadow_pane = resolve_pane_id_by_pid(session, pane_pid) if pane_pid else None`.
- Stamp: `monitor.tmux_run(["set-option", "-p", "-t", shadow_pane,
  SHADOW_TARGET_OPTION, followed_pane])`.
- `attach_shadow_cleanup_hook(followed_pane, companion_pane)`.
- The `"Shadow launched, but its pane could not be classified — it may appear in
  the agent list"` warning when the pane id cannot be resolved.

## Step 3 — PINNED: the `TMUX_PANE` companion-pane coupling

The single sharp edge of this child. Minimonitor currently ends with (L1262):

```python
companion_pane = os.environ.get("TMUX_PANE", "") or shadow_pane
attach_shadow_cleanup_hook(followed_pane, companion_pane)
```

`TMUX_PANE` there means *"minimonitor's own pane"* — the companion that should
be despawned once no real agent sibling remains in the followed agent's window.

**The lifted helper takes `companion_pane` as an explicit parameter and must
never read `TMUX_PANE` itself.** If the monitor passed its own `TMUX_PANE`,
`aitask_companion_cleanup.sh` job 2 would **kill the monitor's own pane**
whenever the agent's window runs out of real agents.

- **minimonitor** keeps passing `os.environ.get("TMUX_PANE", "") or shadow_pane`
  at its call site — behaviour unchanged.
- **monitor** passes `companion_pane = shadow_pane`.

Verified safe against `.aitask-scripts/aitask_companion_cleanup.sh`:

- **Job 1** (L36-44) lists panes across the **session** and kills every pane
  whose `@aitask_shadow_target` equals the dying primary — so the bound shadow
  dies with its agent regardless of `companion`, including under separate-window
  placement.
- **Job 2** (L46-58) counts real-agent siblings **in the primary's window**,
  excluding the primary, the companion, and any pane carrying
  `@aitask_shadow_target`; if zero it runs `tmux kill-pane -t "$companion"`,
  which on the already-dead shadow pane is a `2>/dev/null || true` no-op.

## Step 4 — the monitor actions

```python
def action_launch_shadow(self) -> None:        # e
def action_launch_shadow_pick(self) -> None:   # E
```

Both sync (matching minimonitor), and both resolve the agent from
`self._focused_pane_id` → `self._snapshots` — **not** `_get_focused_pane_id()`
(`monitor_app.py:1529-1535`), which returns `None` whenever focus is off a
`PaneCard`.

Shared prologue:

1. `self._monitor is None` → return.
2. No selected agent snapshot → notify `"Focus an agent pane first"`.
3. Empty `pane_id` → notify.
4. **Duplicate guard, before anything else user-visible:**
   `if self._monitor.find_shadow_pane(followed_pane): notify("A shadow is
   already running for this agent"); return`. Use the **sync** lookup so the
   guard runs before a dialog opens with no await trap — minimonitor does the
   same at L1112 / L1155 and `test_minimonitor_shadow_pick.py::DuplicateGuardTests`
   asserts it.
5. `task_id = self._task_cache.get_task_id_for_pane(snap.pane)`;
   `target_root = self._root_for_snap(snap)`;
   `args = [followed_pane] + ([task_id] if task_id else [])`;
   `full_cmd = resolve_dry_run_command(target_root, "shadow", *args)`.

`e` → `spawn_shadow(...)` directly.

`E` → `push_screen(AgentCommandScreen("Shadow (pick agent)", full_cmd,
"/aitask-shadow " + " ".join(args), project_root=target_root,
operation="shadow", operation_args=args,
default_agent_string=resolve_agent_string(target_root, "shadow")))` with
`narrow=False` (the monitor is full-width). The callback consumes
**`screen.full_command`** (post-override — not the `full_cmd` captured before
the dialog) and **deliberately discards** the dialog's `TmuxLaunchConfig`
placement: placement stays handler-controlled, exactly as minimonitor documents
at L1137-1141. `callback(None)` and a non-config truthy value launch nothing.

Both end with `self.call_later(self._refresh_data)`.

Bindings: `e` and `E` are free in `monitor_app.BINDINGS` (L391-410) and match
minimonitor's keys, so muscle memory carries over. `ShortcutsMixin.__init__`
rewrites `self.BINDINGS` via `register_app_bindings("monitor", …)`, so the new
keys are user-rebindable automatically; `monitor_app` is already in
`KNOWN_BINDING_SOURCES`, so no `lib/shortcut_scopes.py` change is needed.

Per `aidocs/framework/tui_conventions.md` ("TUI footer must surface every
operation"), declare both with `show=True` and short labels.

## Step 5 — docs

- `website/content/docs/tuis/monitor/reference.md` — `e` / `E` rows.
- `website/content/docs/tuis/monitor/how-to.md` — a "Launch a shadow agent"
  section mirroring `website/content/docs/tuis/minimonitor/how-to.md:109-135`.
- `website/content/docs/workflows/shadow-agent.md` and
  `aidocs/framework/shadow_agent.md` ("Spawn path and binding", which says *"The
  shadow is launched from **minimonitor** with the `e` key"*) — the monitor is
  now a second spawn surface. Per
  `aidocs/framework/documentation_conventions.md`, describe the current state;
  do not narrate the change.

## Verification

New `tests/test_monitor_shadow_pick.py`, mirroring
`tests/test_minimonitor_shadow_pick.py`: `MonitorApp.__new__` + spy-lambda
harness, `with patch.object(mod, "resolve_dry_run_command", return_value=...),
patch.object(mod, "resolve_agent_string", return_value=...)`, and a recorder
swapped in for `launch_in_tmux` / `resolve_pane_id_by_pid` /
`attach_shadow_cleanup_hook` / `load_project_tmux_config`, restored in
`finally`.

- **Binding registration** — exactly one `e` → `launch_shadow` and one `E` →
  `launch_shadow_pick` in `MonitorApp.BINDINGS`, both `show=True`.
- **Duplicate guard** fires *before* the dialog opens (`spy_pushed == []`), with
  the "already running" notify, and used the **sync** reader (assert on the fake
  monitor's `sync_calls`, not `async_calls`).
- **Dialog contract** — pushed screen is an `AgentCommandScreen` with
  `operation == "shadow"`, `operation_args == ["%1", "42"]` (and `["%1"]`
  without a task id), prompt `"/aitask-shadow %1 42"`.
- **Confirm path** — launches `screen.full_command` (post-override, not the
  pre-dialog capture); stamps `SHADOW_TARGET_OPTION` exactly once, targeting the
  resolved shadow pane with the followed pane's id as the value;
  `callback(None)` and `callback("run")` launch nothing.
- **New assertion —** `attach_shadow_cleanup_hook` is called with the **shadow**
  pane as `companion_pane`, plus a **negative control**: set `TMUX_PANE` to a
  distinctive sentinel in the test environment and assert that value never
  appears in the call. Without the negative control a test would pass even if
  the helper still read `TMUX_PANE` and the environment happened to be unset.
- A test that minimonitor's own call site still passes its `TMUX_PANE`-derived
  companion (the lift must not change minimonitor's behaviour) — this is also
  covered by `test_minimonitor_shadow_pick.py::ConfirmPathTests` passing
  unmodified.

```bash
bash tests/run_all_python_tests.sh
bash tests/test_no_raw_tmux.sh
```

Manual, **from a shell outside the main aitasks tmux session** (see the
"Tmux-stress tasks" section of `aidocs/framework/tui_conventions.md` — this
child kills panes): press `e` in `ait monitor` on a selected agent, confirm the
shadow splits beside **that agent** (not beside the monitor), press `e` again
and confirm the duplicate refusal, then kill the agent and confirm the shadow
dies **and the monitor survives**. Repeat with
`tmux.shadow_same_window: false` for the separate-window placement.
