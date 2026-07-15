---
Task: t1152_minimonitor_shadow_launch_with_agent_picker.md
Worktree: (current branch — fast profile)
Branch: (current branch)
Base branch: main
---

# t1152 — Minimonitor shadow launch with agent picker (`E` shortcut)

## Context

t1148 added an `X` "explore + pick agent" shortcut to the TUI switcher: instead
of firing an explore agent with the wrapper's default agent/model, it opens the
narrow `AgentCommandScreen` so the user can confirm/change the code agent and
model first. This task applies the same idea to minimonitor's **shadow** launch.

Today minimonitor's lowercase `e` (`action_launch_shadow`) is fire-and-forget:
it resolves the shadow command with the wrapper's default agent/model and
launches immediately, with no chance to pick a different model. We add an
uppercase `E` shortcut that opens the narrow agent/model picker **first**, then
launches the shadow with the chosen agent — while preserving everything the
existing shadow launch does (duplicate guard, specialized split placement, and
the `@aitask_shadow_target` stamp + cleanup-hook lifecycle wiring). The
lowercase `e` behavior is unchanged.

All changes are in `.aitask-scripts/monitor/minimonitor_app.py` plus a new test.

## Key design decision (task complication 2 & 5)

The picker dialog returns its **own** `TmuxLaunchConfig` (from its tmux tab:
session/window/split/new-window). The shadow, however, needs a *specialized*
placement that the dialog cannot express: a split to the RIGHT of the followed
**agent** pane, sized to `shadow_pane_width` and anchored against the agent pane
(not the active minimonitor pane), or a separate `agent-shadow-<task>` window
when `tmux.shadow_same_window` is false.

**Decision:** use the dialog **only** to let the user change the agent/model —
consume `screen.full_command` (which bakes in the chosen agent) and **discard
the dialog's returned placement config**. Keep building the shadow's own
`TmuxLaunchConfig` exactly as `action_launch_shadow` does today. This is why
`shadow` intentionally not being in `agent_command_screen._FRESH_WINDOW_OPERATIONS`
is fine — the dialog's placement tab is never consulted for the actual launch.

To guarantee the confirm-path placement + wiring are byte-for-byte identical to
the existing `e` path (and to avoid drift), extract the placement-build +
launch + post-launch wiring into **one shared helper** (`_spawn_shadow`) that
both `action_launch_shadow` and the new `action_launch_shadow_pick` call.

## Changes (all in `.aitask-scripts/monitor/minimonitor_app.py`)

### 1. New binding (after the `e` binding, line 212)

```python
Binding("e", "launch_shadow", "Shadow", show=False),
Binding("E", "launch_shadow_pick", "Shadow (pick agent)", show=False),
```

`E` (shift-e) is a distinct Textual key from `e`. The `e` binding is a plain
literal in `BINDINGS` (not registered via `ShortcutsMixin` — there is no
`check_action` gate in minimonitor), so `E` as a plain literal binds the same
way with no separate registry step.

### 2. Footer hint (compose(), line ~286)

Change the shadow segment from `e:shadow` to `e/E:shadow`:

```python
"k:kill  n:next  e/E:shadow\n"
```

### 3. Extract shared helper `_spawn_shadow(...)`

Refactor the placement/launch/wiring tail of `action_launch_shadow` (current
lines 1105–1165) into a helper. `action_launch_shadow` keeps its guard +
command-resolution head (lines 1077–1103) and ends by calling the helper.

```python
def _spawn_shadow(
    self,
    full_cmd: str,
    followed_pane: str,
    task_id: str | None,
    target_root: Path,
    snap: PaneSnapshot,
) -> None:
    """Place, launch, and lifecycle-wire the shadow companion.

    Shared by the fire-and-forget ``e`` shortcut (``action_launch_shadow``)
    and the pick-agent ``E`` shortcut (``action_launch_shadow_pick``).
    ``full_cmd`` is the resolved shadow command (with any agent/model override
    already baked in). Placement is ALWAYS handler-controlled here — a
    same-window split to the RIGHT of the followed AGENT pane sized to
    ``shadow_pane_width``, or a separate window when ``tmux.shadow_same_window``
    is false — never the picker dialog's own placement.
    """
    # (body = current action_launch_shadow lines 1105-1165 verbatim:
    #  _load_project_tmux_config → same_window branch building the split /
    #  separate-window TmuxLaunchConfig → launch_in_tmux → resolve_pane_id_by_pid
    #  → set @aitask_shadow_target → attach_shadow_cleanup_hook →
    #  notify → self.call_later(self._refresh_data))
```

`action_launch_shadow` tail becomes:

```python
    args = [followed_pane] + ([task_id] if task_id else [])
    full_cmd = resolve_dry_run_command(target_root, "shadow", *args)
    if not full_cmd:
        self.notify("Failed to resolve shadow command", severity="error")
        return
    self._spawn_shadow(full_cmd, followed_pane, task_id, target_root, snap)
```

### 4. New handler `action_launch_shadow_pick`

Mirrors `_launch_pick_for_own` (dialog-then-callback shape) but keeps the
shadow's guard head and hands the confirm path to `_spawn_shadow`:

```python
def action_launch_shadow_pick(self) -> None:
    """Open the agent/model picker, then spawn the shadow with the choice.

    Same as ``action_launch_shadow`` (duplicate guard, specialized placement,
    @aitask_shadow_target stamp + cleanup hook) but opens the narrow
    AgentCommandScreen first so the user can confirm/change agent+model.
    Cancelling launches nothing.
    """
    if self._monitor is None:
        return
    snap = self._find_own_agent_snapshot()
    if snap is None:
        self.notify("No followed agent to shadow", severity="warning")
        return
    followed_pane = snap.pane.pane_id
    if not followed_pane:
        self.notify("Followed agent pane id unavailable", severity="warning")
        return
    # Duplicate guard runs BEFORE opening the dialog (don't pop a picker to fail).
    if self._find_shadow_pane_for_sync(followed_pane):
        self.notify("A shadow is already running for this agent", severity="warning")
        return
    task_id = self._task_cache.get_task_id_for_pane(snap.pane)
    target_root = self._root_for_snap(snap)
    args = [followed_pane] + ([task_id] if task_id else [])
    full_cmd = resolve_dry_run_command(target_root, "shadow", *args)
    if not full_cmd:
        self.notify("Failed to resolve shadow command", severity="error")
        return
    agent_string = resolve_agent_string(target_root, "shadow")
    screen = AgentCommandScreen(
        "Shadow (pick agent)",
        full_cmd,
        "/aitask-shadow " + " ".join(args),
        project_root=target_root,
        operation="shadow",
        operation_args=args,
        default_agent_string=agent_string,
        narrow=True,
    )

    def on_shadow_result(result):
        # Confirm returns a TmuxLaunchConfig; its placement is intentionally
        # discarded — only the (possibly agent-overridden) full_command is used.
        # None (cancel) / "run" launch nothing (mirrors _launch_pick_for_own).
        if isinstance(result, TmuxLaunchConfig):
            self._spawn_shadow(
                screen.full_command, followed_pane, task_id, target_root, snap
            )

    self.push_screen(screen, on_shadow_result)
```

Notes:
- `narrow=True` matches the pick flow (minimonitor width; `_switcher_narrow`).
- `skill_name`/`default_profile` are **omitted** (like the t1148
  `action_shortcut_explore_pick`, which also omits them) — the picker still lets
  the user change agent/model, which is the whole point; a profile row is not
  needed for the advisory shadow.
- The confirm callback uses `screen.full_command` (post-override), never
  `full_cmd` captured at push time.

## Tests (new file `tests/test_minimonitor_shadow_pick.py`)

Mock-based, same style as `tests/test_minimonitor_concern_action.py`
(`MiniMonitorApp.__new__`, `_mk_app`-style spies, monkeypatch module globals in
`mm`). Reference: `tests/test_tui_switcher_agent_launch.py` (t1148).

1. **Binding + hint registration** — assert exactly one `Binding` with
   `key == "E"` / `action == "launch_shadow_pick"` in
   `mm.MiniMonitorApp.BINDINGS`, and that the compose footer string advertises
   `e/E:shadow` (assert the `#mini-key-hints` static text via a rendered
   `compose()` scan or a substring check on the source constant).
2. **Duplicate guard fires before the dialog** — with `_FakeMon(sync_list="%5\t%1")`
   (an existing shadow bound to the followed pane) and `push_screen` spied,
   call `action_launch_shadow_pick()`; assert `push_screen` was NOT called and a
   "already running" warning was notified (guard head parity with
   `action_launch_shadow`).
3. **Dialog opened with shadow contract** — no existing shadow; stub
   `_find_own_agent_snapshot`, `_root_for_snap`, `_task_cache`, and monkeypatch
   `mm.resolve_dry_run_command` / `mm.resolve_agent_string`; call the handler and
   assert the pushed screen is an `AgentCommandScreen` with `operation=="shadow"`,
   `narrow is True`, and `operation_args == [followed_pane, task_id]`.
4. **Confirm path launches + wires** — invoke the captured callback with a
   `TmuxLaunchConfig`; with `mm.launch_in_tmux` (returns a fake pid),
   `mm.resolve_pane_id_by_pid` (returns `%9`), `mm.attach_shadow_cleanup_hook`,
   and `mm._load_project_tmux_config` monkeypatched, assert: `launch_in_tmux` was
   called with `screen.full_command`; the `@aitask_shadow_target` `set-option`
   was issued via the monitor spy pointing at `followed_pane`; and
   `attach_shadow_cleanup_hook(followed_pane, ...)` ran. (This is the
   post-launch stamp + cleanup-hook wiring assertion the AC requires.)
5. **Cancel launches nothing** — invoke the callback with `None`; assert
   `mm.launch_in_tmux` was never called.

Run: `python3 tests/test_minimonitor_shadow_pick.py` (and it is picked up by
`bash tests/run_all_python_tests.sh`).

## Verification

- **Unit:** `python3 tests/test_minimonitor_shadow_pick.py` passes; existing
  `python3 tests/test_minimonitor_concern_action.py` still passes (guard head +
  `action_launch_shadow` behavior unchanged after the `_spawn_shadow` extract).
- **Lint/compile:** `python3 -m py_compile .aitask-scripts/monitor/minimonitor_app.py`.
- **Live (manual, in tmux):** launch `ait minimonitor` beside a followed agent;
  press `E` → the narrow picker opens showing the current default agent; change
  the model and confirm → a shadow spawns as a split to the right of the agent
  pane (or a separate window per `tmux.shadow_same_window`), is NOT listed as an
  agent (correct `@aitask_shadow_target` classification), and dies when the agent
  pane closes (cleanup hook). Press `E` again → "already running" (guard). Press
  `e` → unchanged fire-and-forget behavior. This live check is a good candidate
  for the manual-verification follow-up offered at Step 8c.

## Cross-agent note

Minimonitor is Claude Code TUI Python source, not a skill — no cross-agent skill
port is required (per the task's Cross-agent note).

## Step 9 (Post-Implementation)

After review/approval: commit code (`feature: ... (t1152)`), run the
`risk_evaluated` gate via the Step-9 orchestrator, and archive per the shared
task-workflow Step 9. No branch/worktree cleanup (fast profile works on the
current branch).

## Risk

### Code-health risk: low
- The change is additive (one new binding, one new handler) plus a
  behavior-preserving extraction of `_spawn_shadow` shared by the existing `e`
  path; the refactor risks a subtle divergence in the extracted placement/wiring
  block · severity: low · → mitigation: TBD (covered by keeping
  `test_minimonitor_concern_action.py` green + the new confirm-path wiring test).

### Goal-achievement risk: low
- The approach directly mirrors the proven t1148 dialog-then-callback pattern and
  the task spec is explicit; the only judgment call (discard dialog placement,
  reuse the shadow's own config) is the task's recommended approach · severity:
  low · → mitigation: TBD.

## Final Implementation Notes

- **Actual work done:** Added `Binding("E", "launch_shadow_pick", ...)` after the
  `e` binding, updated the footer hint to `e/E:shadow`, extracted the shadow
  placement + launch + `@aitask_shadow_target` stamp + cleanup-hook wiring from
  `action_launch_shadow` into a shared `_spawn_shadow(full_cmd, followed_pane,
  task_id, target_root, snap)` helper, and added `action_launch_shadow_pick`
  which runs the duplicate guard, opens the narrow `AgentCommandScreen`
  (`operation="shadow"`, `narrow=True`), and on a `TmuxLaunchConfig` confirm
  calls `_spawn_shadow(screen.full_command, ...)` — discarding the dialog's own
  placement. New test file `tests/test_minimonitor_shadow_pick.py` (8 tests).
- **Deviations from plan:** None. Implemented exactly as planned (discard the
  dialog placement; single shared `_spawn_shadow` helper).
- **Issues encountered:** Test tweaks only — Textual `Static` exposes content via
  `.render()` (not `.renderable`), and `TmuxLaunchConfig` requires `new_session`
  / `new_window` positionally. Both fixed; all 8 new tests + the existing 25
  `test_minimonitor_concern_action.py` tests pass; module byte-compiles.
- **Key decisions:** The picker dialog is used ONLY for agent/model selection;
  placement stays handler-controlled in `_spawn_shadow` because the shadow's
  split-target-the-followed-AGENT-pane geometry cannot be expressed by the
  dialog's tmux tab. Rejected refactoring `AgentCommandScreen` to model that
  placement (wide blast radius: 14 call sites) per the user's "don't refactor if
  it adds risk" guidance.
- **Upstream defects identified:** `.aitask-scripts/lib/agent_model_picker.py:317 — AgentModelPickerScreen is fixed at width:65% and is not narrow-aware; option rows render "<agent>/<name>" and on a narrow minimonitor pane the long "claudecode/" prefix (11 chars) eats the visible width, clipping the claudecode model name (e.g. opus4_8) — surfaced by the new E shadow-pick dialog but pre-existing and shared by board/monitor/codebrowser/switcher.` Follow-up task requested by the user (Step 8b).
