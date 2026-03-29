---
Task: t475_3_monitor_tui_app.md
Parent Task: aitasks/t475_monitor_tui.md
Sibling Tasks: aitasks/t475/t475_1_*.md, aitasks/t475/t475_2_*.md
Archived Sibling Plans: aiplans/archived/p475/p475_*_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Implementation Plan: Monitor TUI App

## Step 1: Create monitor_app.py scaffold

Create `.aitask-scripts/monitor/monitor_app.py` with `MonitorApp(App, TuiSwitcherMixin)`.

Imports: `TmuxMonitor` from `tmux_monitor`, `TuiSwitcherMixin` from `lib.tui_switcher`.

## Step 2: Define widgets

### SessionBar(Static)
One-line bar: "tmux Monitor — session: aitasks (7 panes, 2 idle)"

### AttentionCard(Static, can_focus=True)
Renders: `[!] <window>:<pane> — idle <N>s`. Shows last line of captured content as subtitle.

### PaneCard(Static, can_focus=True)
Renders: `● <window_index>:<window_name> (<pane_index>) <command> <status>`. Color-coded dot: green=active, yellow=idle.

### TuiCard(Static, can_focus=True)
Renders: `● <name> [switch]` for running, `○ <name> [spawn]` for missing.

### ContentPreview(Static)
Shows last N lines of focused pane's captured output. Updates on focus change.

## Step 3: Layout with compose()

```python
def compose(self):
    yield Header()
    yield SessionBar(id="session-bar")
    yield VerticalScroll(id="attention-section")  # Attention cards
    with Horizontal(id="main-panels"):
        yield VerticalScroll(id="pane-list")       # Agent + Other cards
        yield VerticalScroll(id="tui-panel")       # TUI cards
    yield Static(id="content-preview")
    yield Footer()
```

## Step 4: Refresh logic

```python
def on_mount(self):
    self.monitor = TmuxMonitor(session=..., exclude_pane=os.environ.get("TMUX_PANE"))
    self.attention_queue: list[str] = []
    self.call_later(self._refresh_data)
    self.set_interval(self.refresh_seconds, self._refresh_data)

async def _refresh_data(self):
    snapshots = self.monitor.capture_all()
    self._update_attention_queue(snapshots)
    self._rebuild_attention_section(snapshots)
    self._rebuild_pane_list(snapshots)
    self._rebuild_tui_panel()
    self._update_content_preview()
```

## Step 5: Attention queue logic

- On refresh: for each AGENT snapshot, if `is_idle` and pane_id not in queue → append
- If pane was in queue but no longer idle → remove
- `_rebuild_attention_section()`: mount AttentionCards in queue order

## Step 6: Action handlers

- `action_confirm()`: `send_enter()` on focused pane, remove from queue, notify
- `action_decide_later()`: move pane_id to end of queue, rebuild attention section
- `action_switch_to()`: `switch_to_pane()` on focused pane
- `action_spawn_tui()`: `spawn_tui()` for focused TuiCard, notify

## Step 7: Content preview

On focus change (watch `on_descendant_focus`), if focused widget is AttentionCard or PaneCard, update `#content-preview` with that pane's captured content.

## Step 8: Keybindings

```python
BINDINGS = [
    *TuiSwitcherMixin.SWITCHER_BINDINGS,
    Binding("q", "quit", "Quit"),
    Binding("enter", "confirm", "Confirm"),
    Binding("c", "confirm", "Confirm", show=False),
    Binding("d", "decide_later", "Later"),
    Binding("s", "switch_to", "Switch"),
    Binding("t", "spawn_tui", "Spawn TUI"),
    Binding("r", "refresh", "Refresh"),
    Binding("f5", "refresh", "Refresh", show=False),
]
```

## Step 9: Entry point with argparse

Parse `--session`, `--interval`, `--lines`. Load defaults from `load_monitor_config()`. CLI args override.

## Step 10: Wrapper script (aitask_monitor.sh)

Follow `aitask_board.sh` pattern: check Python, deps (textual, pyyaml), tmux, terminal.

## Step 11: CLI dispatcher

Add `monitor)` case to `ait` and update `show_usage()`.

## Step 12: CSS

Style sections: attention=top (collapsible if empty), main-panels=horizontal split, content-preview=bottom fixed height. Color scheme matching board TUI conventions.

## Verification

- `ait monitor` launches successfully
- Attention queue populates for idle agents
- Confirm/Decide Later/Switch actions work
- TUI panel shows running/missing correctly
- Content preview updates on focus
- CLI args work
- Graceful error when no tmux session

## Step 9 Reference (Post-Implementation)

Commit, archive, push per task-workflow Step 9.
