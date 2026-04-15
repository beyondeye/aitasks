---
Task: t556_task_restart_action.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Add "restart task" action to ait monitor TUI (t556)

## Context

The `ait monitor` Textual TUI shows all tmux panes running code agents. It already has an `n` action ("pick next sibling") that, on a focused agent pane, finds the next Ready sibling/child task and opens the shared `AgentCommandScreen` to spawn `/aitask-pick <id>` in a new session/window/pane.

We want a complementary action: **restart the task currently running in the focused pane**. The use case is: the agent session for task `tN` got stuck, finished off-track, or we want to re-run pick on the same task from scratch. Today the user has to manually kill the pane (`k`) and then pick the task again from board or another TUI — this bundles both into a single, safer workflow.

Requirements (from the task description):
1. New action on the monitor TUI, tied to a binding, that restarts the focused task.
2. Active **only when the associated terminal is currently idle** (pane's `snap.is_idle` is true).
3. Shows a confirmation dialog that **warns if the task is not in `Ready` status**.
4. On approval of the restart confirmation, open the **shared agent-spawn dialog** (`AgentCommandScreen`) for `/aitask-pick <task_id>`.
5. The old pane must be **killed only after** the agent-spawn dialog is confirmed (i.e. after the user picks a target session/window and clicks Run). If the user cancels the spawn dialog, nothing is killed.

## Approach

Mirror the structure of `action_pick_next_sibling` / `_on_next_sibling_result` / `NextSiblingDialog` closely, with three differences:

- **Idle gate up front.** Return early with a warning notification if the pane is not idle.
- **Same task id**, not "next sibling": the target of pick is the current task (which we read from `snap.pane.window_name` via `TaskInfoCache.get_task_id`).
- **Kill timing**: the `kill_pane` call happens inside the `AgentCommandScreen` result callback — after the launch completes successfully — rather than before the spawn dialog opens (as `_on_next_sibling_result` does for Done/parent tasks).

A new `RestartConfirmDialog` (simple warning modal) gates the flow, and a new `action_restart_task` handler wires it all together.

## Files to modify

All changes are in **one file**: `.aitask-scripts/monitor/monitor_app.py`.

No shared library changes, no new module — this is a monitor-only action that reuses `AgentCommandScreen`, `TmuxLaunchConfig`, `launch_in_tmux`, `maybe_spawn_minimonitor`, `resolve_dry_run_command`, `resolve_agent_string`, and `TmuxMonitor.kill_pane` which are all already imported.

## Implementation steps

### Step 1 — Add binding

In `.aitask-scripts/monitor/monitor_app.py`, `MonitorApp.BINDINGS` (around line 378-394), add a new binding after the existing `n` binding:

```python
Binding("R", "restart_task", "Restart"),
```

Rationale for the key choice: `r` is already taken by "Refresh", and uppercase `R` is free, unambiguous, and mnemonic ("Restart"). It avoids reusing `n` which stays for "pick next sibling".

### Step 2 — Add `RestartConfirmDialog` modal

Add a new `ModalScreen` subclass in `.aitask-scripts/monitor/monitor_app.py`, immediately after `NextSiblingDialog` (currently ending around line 298, right before the `# -- Main app` comment).

It takes the current task id, title, status, and the pane's idle duration, and shows:
- Header: "Restart Task"
- Task line: `Current: tN: <title>  (Status: <status>)`
- Idle line: `Terminal idle for <N>s`
- If status != "Ready": a yellow warning line: `⚠ Task status is '<status>' (not Ready) — pick workflow may behave unexpectedly`
- A note: `The current pane will be killed after you confirm the spawn dialog.`
- Buttons: `Restart` (variant warning), `Cancel` (variant default)

The dialog dismisses with `True` on confirm and `False`/`None` on cancel. Shape:

```python
class RestartConfirmDialog(ModalScreen):
    """Confirmation dialog for restarting the task in the focused agent pane."""

    BINDINGS = [Binding("escape", "dismiss_dialog", "Close", show=False)]

    DEFAULT_CSS = """
    RestartConfirmDialog { align: center middle; }
    #restart-dialog { width: 70%; height: auto; background: $surface;
                      border: thick $warning; padding: 1 2; }
    #restart-header { text-style: bold; color: $warning; margin: 0 0 1 0; }
    #restart-details { margin: 0 0 1 0; }
    #restart-buttons { width: 100%; height: auto; layout: horizontal; }
    #restart-buttons Button { margin: 0 1; }
    """

    def __init__(self, task_id: str, title: str, status: str, idle_seconds: float) -> None:
        super().__init__()
        self._task_id = task_id
        self._title = title
        self._status = status
        self._idle_seconds = idle_seconds

    def compose(self) -> ComposeResult:
        with Container(id="restart-dialog"):
            yield Static("[bold yellow]Restart Task[/]", id="restart-header")
            lines = [
                f"Current:   [bold]t{self._task_id}[/]: {self._title}  (Status: {self._status})",
                f"Terminal:  idle for {int(self._idle_seconds)}s",
            ]
            if self._status != "Ready":
                lines.append(
                    f"\n[yellow]⚠ Task status is '{self._status}' (not Ready) — "
                    f"pick workflow may behave unexpectedly[/]"
                )
            lines.append(
                "\n[dim]The current pane will be killed after you confirm the spawn dialog.[/]"
            )
            yield Static("\n".join(lines), id="restart-details")
            with Container(id="restart-buttons"):
                yield Button("Restart", variant="warning", id="btn-restart")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-restart")

    def action_dismiss_dialog(self) -> None:
        self.dismiss(False)
```

### Step 3 — Add `action_restart_task` and callback

Add the action handler after `_on_next_sibling_result` (currently ending around line 1416). It mirrors `action_pick_next_sibling` for pane/task resolution, but:
1. Checks `snap.is_idle` up front and bails with a warning if false.
2. Opens `RestartConfirmDialog` instead of `NextSiblingDialog`.
3. After confirmation, opens `AgentCommandScreen` for the **same** `task_id`.
4. Kills the old pane **inside** the `AgentCommandScreen` result callback, only when a `TmuxLaunchConfig` is returned and after `launch_in_tmux` succeeds.

```python
def action_restart_task(self) -> None:
    """Kill the focused idle agent pane and re-run pick for the same task."""
    if self._monitor is None:
        return
    pane_id = self._get_focused_pane_id()
    if not pane_id:
        self.notify("Focus an agent pane first", severity="warning")
        return
    snap = self._snapshots.get(pane_id)
    if not snap:
        return
    if not snap.is_idle:
        self.notify(
            "Restart only available when the terminal is idle",
            severity="warning",
        )
        return
    task_id = self._task_cache.get_task_id(snap.pane.window_name)
    if not task_id:
        self.notify("No task ID in window name", severity="warning")
        return
    self._task_cache.invalidate(task_id)
    info = self._task_cache.get_task_info(task_id)
    title = info.title if info else f"(archived t{task_id})"
    status = info.status if info else "Done"

    self.push_screen(
        RestartConfirmDialog(task_id, title, status, snap.idle_seconds),
        callback=lambda ok: self._on_restart_confirmed(ok, pane_id, task_id),
    )

def _on_restart_confirmed(
    self, confirmed: bool | None, pane_id: str, task_id: str
) -> None:
    if not confirmed:
        return
    if self._monitor is None:
        return
    # Re-fetch snapshot — could have disappeared while the dialog was open.
    snap = self._snapshots.get(pane_id)
    if not snap:
        self.notify("Focused pane no longer exists", severity="warning")
        return

    full_cmd = resolve_dry_run_command(self._project_root, "pick", task_id)
    if not full_cmd:
        self.notify(
            f"Failed to resolve pick command for t{task_id}",
            severity="error",
        )
        return

    prompt_str = f"/aitask-pick {task_id}"
    window_name = f"agent-pick-{task_id}"
    agent_string = resolve_agent_string(self._project_root, "pick")
    screen = AgentCommandScreen(
        f"Pick Task t{task_id}", full_cmd, prompt_str,
        default_window_name=window_name,
        project_root=self._project_root,
        operation="pick",
        operation_args=[task_id],
        default_agent_string=agent_string,
    )

    old_window_name = snap.pane.window_name

    def on_pick_result(pick_result):
        # Only kill AFTER the user confirmed the spawn dialog AND launch succeeded.
        if isinstance(pick_result, TmuxLaunchConfig):
            _, err = launch_in_tmux(screen.full_command, pick_result)
            if err:
                self.notify(f"Launch failed: {err}", severity="error")
                return
            if self._monitor and self._monitor.kill_pane(pane_id):
                if self._focused_pane_id == pane_id:
                    self._focused_pane_id = None
                self.notify(f"Killed {old_window_name}")
            if pick_result.new_window:
                maybe_spawn_minimonitor(pick_result.session, pick_result.window)
            self.notify(f"Restarted agent for t{task_id}")
        self.call_later(self._refresh_data)

    self.push_screen(screen, on_pick_result)
```

Notes on the closure:
- `pane_id` and `task_id` are captured at action time so that even if focus moves while a dialog is open, the restart targets the originally-focused pane.
- The snapshot (`snap`) is re-read inside `_on_restart_confirmed` rather than captured, because the pane might have been killed between the idle check and confirmation. `_snapshots.get(pane_id)` returning `None` aborts cleanly.
- `kill_pane` is called **after** `launch_in_tmux` succeeds. Ordering: if the new launch fails we keep the old pane (it was idle anyway, so the user loses nothing). The kill happens before the `maybe_spawn_minimonitor` call and notifications so the UI is coherent on the next `_refresh_data`.

### Step 4 — Verify imports

`AgentCommandScreen`, `TmuxLaunchConfig`, `launch_in_tmux`, `maybe_spawn_minimonitor`, `resolve_dry_run_command`, `resolve_agent_string` are all already imported at the top of `monitor_app.py` (verified via the existing `action_pick_next_sibling` method which uses them all). No import changes needed.

`Binding`, `Button`, `Container`, `Static`, `ModalScreen`, `ComposeResult` are also already imported (used by `NextSiblingDialog`). No new imports for the dialog either.

## Verification

Run the monitor TUI manually and exercise every branch. Because the monitor depends on tmux panes, automated tests are not practical for the dialog interaction — instead, test end-to-end in a real session.

1. **Happy path**
   - Start `ait monitor` inside tmux with at least one idle `agent-pick-<N>` pane.
   - Focus the pane (tab/arrow), press `R`.
   - Confirm the `Restart Task` dialog appears with the correct task id/title and idle duration.
   - Click `Restart` → `AgentCommandScreen` opens for `/aitask-pick <N>`.
   - Choose a tmux launch config → click Run.
   - Expected: the old pane is killed, a new `agent-pick-<N>` window/pane is spawned, `_refresh_data` updates the list on next tick.

2. **Not-idle gate**
   - Focus an actively-running agent pane (`is_idle == False`).
   - Press `R`.
   - Expected: warning notification "Restart only available when the terminal is idle", no dialog.

3. **Non-Ready status warning**
   - Manually edit a task's status to `Implementing` or `Postponed`.
   - Restart its pane when idle.
   - Expected: the `RestartConfirmDialog` shows the yellow warning line about the non-Ready status but still allows confirmation.

4. **Cancel at restart dialog**
   - Press `R`, then Cancel on the `RestartConfirmDialog`.
   - Expected: no kill, no spawn dialog, no notifications except dismissal.

5. **Cancel at spawn dialog**
   - Press `R`, confirm restart, then Cancel (or Escape) in the `AgentCommandScreen`.
   - Expected: **no kill**, old pane still running. This is the critical requirement from the task: kill must not happen until the spawn is actually confirmed.

6. **No focused pane**
   - Press `R` with focus on a non-pane widget (e.g., the preview scroll) or no pane at all.
   - Expected: warning "Focus an agent pane first".

7. **Task file archived/missing**
   - Archive the task while the pane is idle and then press `R`.
   - Expected: dialog shows `(archived t<N>)` title and `Done` status with the warning; restart still proceeds if confirmed.

8. **Binding visible in footer**
   - Check the Textual footer shows `R Restart` alongside the other bindings.

## Post-implementation (Step 9)

Per the task-workflow SKILL.md Step 9:
- No separate branch (profile `create_worktree: false`), so no merge step.
- `verify_build` from `project_config.yaml`: none configured → skip.
- Commit with `feature: Add task restart action to ait monitor TUI (t556)`.
- Archive via `./.aitask-scripts/aitask_archive.sh 556` (no linked issue, no folded tasks).
- Push via `./ait git push`.

## Final Implementation Notes

- **Actual work done:** Added `Binding("R", "restart_task", "Restart")` and a `RestartConfirmDialog` modal (alongside `NextSiblingDialog`) in `.aitask-scripts/monitor/monitor_app.py`. Added `action_restart_task` / `_on_restart_confirmed` handlers following the plan. Also added `TmuxMonitor.kill_window(pane_id)` in `.aitask-scripts/monitor/tmux_monitor.py` — see the deviation below.
- **Deviations from plan:** The plan called `kill_pane` inside the `on_pick_result` callback, ordered **after** `launch_in_tmux`. Review caught a bug: since the restart target reuses the same `agent-pick-<id>` window name, `maybe_spawn_minimonitor` (which resolves the target by first-matching name in `tmux list-windows`) would attach the new minimonitor to the still-alive old window, leaving the new window without a companion pane. The fix flips the ordering and uses `kill_window` instead of `kill_pane`: the old window (including any leftover minimonitor split) is destroyed first, then `launch_in_tmux` creates the new window, then `maybe_spawn_minimonitor` attaches cleanly. `kill_window` was added to `TmuxMonitor` for symmetry with `kill_pane`; it runs `tmux kill-window -t <pane_id>` (tmux resolves a pane target to its window).
- **Issues encountered:** The window-name ambiguity in `maybe_spawn_minimonitor` is a latent issue that affects any code path that reuses an `agent-pick-<id>` name before the previous instance is torn down. Fixed locally here via ordering + `kill_window`; a broader review was split out as t557 (see Notes for sibling tasks).
- **Key decisions:**
  - Used uppercase `R` for the binding (lowercase `r` is Refresh).
  - Idle gate is enforced in `action_restart_task` with a warning notification rather than dynamically hiding the binding, matching the pattern of other conditionally-valid actions (e.g., `action_pick_next_sibling` reporting "No ready siblings").
  - Captured `pane_id` / `task_id` in a closure for the confirmation callback so focus changes mid-flow don't redirect the restart.
  - Re-fetch `snap` inside `_on_restart_confirmed` so the code is resilient to the pane disappearing between the idle check and the user confirming.
- **Notes for sibling tasks:** Follow-up task **t557** was created to investigate minimonitor lifecycle across all agent-spawn flows. Key questions: (1) can two agent panes coexist in a single window today; (2) should `_on_next_sibling_result`'s `kill_pane` path also use `kill_window`; (3) what is the detection rule for orphaned minimonitor panes. t557 depends on t556.
