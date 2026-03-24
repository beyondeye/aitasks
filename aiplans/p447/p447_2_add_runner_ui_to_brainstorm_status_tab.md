---
Task: t447_2_add_runner_ui_to_brainstorm_status_tab.md
Parent Task: aitasks/t447_add_crew_runner_control_to_brainstorm_tui.md
Sibling Tasks: aitasks/t447/t447_1_extract_runner_control_shared_module.md, aitasks/t447/t447_3_push_crew_worktree_after_addwork.md
Archived Sibling Plans: aiplans/archived/p447/p447_1_extract_runner_control_shared_module.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Plan: Add runner control UI to brainstorm TUI Status tab

### Step 1: Add import to `brainstorm_app.py`

After the existing `agentcrew` imports (line 62-68), add:

```python
from agentcrew.agentcrew_runner_control import (
    get_runner_info,
    start_runner,
    stop_runner,
)
```

### Step 2: Add CSS for runner bar

In the `CSS` class variable of `BrainstormApp`, add after the StatusLogRow styles (around line 752):

```css
/* Runner control bar */
#runner_bar { height: auto; padding: 0 1; margin-bottom: 1; }
.btn_runner_start { margin: 0 1; }
.btn_runner_stop { margin: 0 1; }
```

### Step 3: Add runner status section to `_refresh_status_tab()`

In `_refresh_status_tab()`, after the worktree existence check (line 972) and before reading groups (line 974), insert:

```python
# Runner status section
crew_id = self.session_data.get("crew_id", "")
if crew_id:
    runner = get_runner_info(crew_id)
    status = runner["status"]
    stale = runner["stale"]

    # Determine display text and color
    if status == "none":
        status_text = "No runner"
        color = "#888888"
    elif status == "stopped":
        status_text = "Runner stopped"
        color = "#888888"
    elif stale:
        status_text = "Runner stale"
        color = "#FF5555"
    else:
        status_text = "Runner active"
        color = "#50FA7B"

    # Build info line
    info_parts = [f"[{color}]{status_text}[/{color}]"]
    if runner["hostname"]:
        info_parts.append(f"Host: {runner['hostname']}")
    if runner["heartbeat_age"] != "never":
        info_parts.append(f"Heartbeat: {runner['heartbeat_age']}")

    container.mount(
        Label("[bold]Runner[/bold]", classes="status_section_title")
    )
    container.mount(Label("  ".join(info_parts), id="runner_status_line"))

    # Mount start/stop buttons
    runner_active = status not in ("none", "stopped") and not stale
    with container.mount(Horizontal(id="runner_bar")):
        pass
    bar = self.query_one("#runner_bar", Horizontal)
    if not runner_active:
        bar.mount(Button("Start Runner", classes="btn_runner_start"))
    else:
        bar.mount(Button("Stop Runner", classes="btn_runner_stop"))
```

**Note:** The container is a `VerticalScroll` (`#status_content`). Mount the `Horizontal` for buttons, then populate it. The pattern follows how other sections mount widgets in this method.

### Step 4: Add button handlers

Add as methods on `BrainstormApp`:

```python
@on(Button.Pressed, ".btn_runner_start")
def _on_runner_start(self, event: Button.Pressed) -> None:
    crew_id = self.session_data.get("crew_id", "")
    if crew_id and start_runner(crew_id):
        self.notify("Runner started")
    else:
        self.notify("Failed to start runner", severity="error")
    self._refresh_status_tab()

@on(Button.Pressed, ".btn_runner_stop")
def _on_runner_stop(self, event: Button.Pressed) -> None:
    crew_id = self.session_data.get("crew_id", "")
    if crew_id and stop_runner(crew_id):
        self.notify("Runner stop requested")
    else:
        self.notify("Failed to stop runner", severity="error")
    self._refresh_status_tab()
```

### Step 5: Verify

1. Launch brainstorm TUI and navigate to Status tab (press 5)
2. Verify runner status section appears at top of Status tab
3. Test "Start Runner" button launches the runner process
4. Test "Stop Runner" button sends stop request
5. Verify 30-second auto-refresh updates runner status display
6. Verify other Status tab content (groups, agents, logs) still renders correctly below

### Step 9: Post-Implementation

Archive task and plan per workflow.

## Post-Review Changes

### Change Request 1 (2026-03-24 12:00)
- **Requested by user:** Start Runner button crashes with DuplicateIds error
- **Changes made:** Changed `id="runner_status_line"` and `id="runner_bar"` to CSS classes (`.runner_bar`), matching the pattern used by all other widgets in `_refresh_status_tab()`. Fixed CSS selector from `#runner_bar` to `.runner_bar`.
- **Files affected:** `.aitask-scripts/brainstorm/brainstorm_app.py`

## Final Implementation Notes
- **Actual work done:** Added runner control UI to the brainstorm TUI Status tab. Imports `get_runner_info`, `start_runner`, `stop_runner` from the shared `agentcrew_runner_control` module (t447_1). Displays color-coded runner status (none/stopped→gray, stale→red, active→green) with hostname and heartbeat age. Mounts Start/Stop buttons conditionally based on runner state.
- **Deviations from plan:** Used CSS classes instead of IDs for dynamically re-mounted widgets to avoid DuplicateIds crashes on refresh. Dropped individual button margin CSS rules since the generic `Button { margin: 0 1; }` already covers them. Used `.get("heartbeat_age", "never")` instead of direct dict access since `get_runner_info()` omits this key for "none" status.
- **Issues encountered:** DuplicateIds crash when clicking Start Runner — `_refresh_status_tab()` re-mounts widgets after `remove_children()`, and Textual's ID registry requires unique IDs. Fixed by switching to CSS classes. Also discovered `ait crew runner` has a pre-existing import bug (`ModuleNotFoundError: No module named 'agentcrew'`) — created sibling task t447_4 to address this.
- **Key decisions:** Followed the existing pattern in `_refresh_status_tab()` of using classes (not IDs) for all dynamically mounted widgets.
- **Notes for sibling tasks:** The `ait crew runner` command fails with a `ModuleNotFoundError` because `agentcrew_runner.py` uses package-style imports (`from agentcrew.agentcrew_utils`) but the shell wrapper doesn't set `PYTHONPATH` to `.aitask-scripts/`. The fix is to add `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` to `agentcrew_runner.py` or set `PYTHONPATH` in `aitask_crew_runner.sh`.
