---
priority: high
effort: high
depends: [t475_2]
issue_type: feature
status: Ready
labels: [aitask_monitor, tui]
created_at: 2026-03-29 10:41
updated_at: 2026-03-29 10:41
---

## Monitor TUI App

Full Textual application with attention queue, session overview, content preview, and CLI integration (`ait monitor`).

### Context

This is the main TUI for the tmux Monitor (parent t475). It uses the core library from t475_1 and integrates the TUI Switcher from t475_2. The monitor is a session control center showing all tmux panes categorized as agents, TUIs, or other.

### Key Files to Create

- `.aitask-scripts/monitor/monitor_app.py` — main Textual app
- `.aitask-scripts/aitask_monitor.sh` — wrapper shell script

### Key Files to Modify

- `ait` — add `monitor)` case to dispatcher + usage text

### Key Files to Reference

- `.aitask-scripts/monitor/tmux_monitor.py` — core library (t475_1)
- `.aitask-scripts/lib/tui_switcher.py` — TUI switcher widget (t475_2)
- `.aitask-scripts/board/aitask_board.py` — reference for Textual app patterns (widgets, refresh, CSS)
- `.aitask-scripts/aitask_board.sh` — reference for wrapper script pattern
- `.aitask-scripts/lib/agent_launch_utils.py` — tmux utilities

### Implementation Plan

#### 1. TUI Layout

```
+------------------------------------------------------------+
| Header: tmux Monitor — session: aitasks (7 panes, 2 idle)  |
+------------------------------------------------------------+
| NEEDS ATTENTION (2)                                        |
| [!] 1:agent-pick-42 (pane 0) — idle 25s   [C] [D] [S]    |
| [!] 3:agent-review (pane 0)  — idle 12s   [C] [D] [S]    |
+------------------------------------------------------------+
| CODE AGENTS (4)                  | TUIs                    |
| ● 1:agent-pick-42 IDLE 25s      | ● board     [switch]   |
| ● 2:agent-explore Active        | ○ codebrowser [spawn]  |
| ● 3:agent-review  IDLE 12s      | ○ brainstorm  [spawn]  |
| ● 5:agent-pick-99 Active        | ● settings  [switch]   |
| OTHER (1)                        |                        |
| ○ 0:main bash                   |                        |
+------------------------------------------------------------+
| Content Preview (focused: 1:agent-pick-42)                 |
| > Allow Read tool on src/main.py?                          |
| > (Y)es / (N)o / Yes to all                               |
+------------------------------------------------------------+
| [Enter] Confirm  [d] Later  [s] Switch  [j] Jump TUI      |
+------------------------------------------------------------+
```

#### 2. Widgets

- `AttentionCard(Static, can_focus=True)` — idle agent card in attention section, shows window name, idle duration, last output snippet
- `PaneCard(Static, can_focus=True)` — pane status entry in agents/other section
- `TuiCard(Static, can_focus=True)` — TUI entry (running: [switch], missing: [spawn])
- `ContentPreview(Static)` — last N lines of focused pane's captured output
- `SessionBar(Static)` — session name, total pane count, idle count

#### 3. Attention Queue Logic

- `attention_queue: list[str]` — pane_ids ordered by user triage priority
- On refresh: if AGENT pane becomes idle (crosses threshold), append to queue if not present
- On refresh: if AGENT pane becomes active again (content changed), remove from queue
- **Confirm** (`Enter` or `c`): call `monitor.send_enter(pane_id)`, remove from queue, show notification
- **Decide Later** (`d`): move pane_id to end of `attention_queue`
- **Switch To** (`s`): call `monitor.switch_to_pane(pane_id)`, keep in queue

#### 4. TUI Panel (right side)

Same spawn/switch behavior as TuiSwitcher overlay but rendered inline:
- Show all known TUIs
- Running ones: `s` to switch
- Missing ones: `t` to spawn
- Uses `monitor.get_running_tuis()` and `monitor.get_missing_tuis()`

#### 5. Keybindings

- `q` — Quit
- `Enter/c` — Confirm (send Enter to focused agent pane)
- `d` — Decide Later (move to bottom of attention queue)
- `s` — Switch To (focus pane in tmux)
- `t` — Spawn TUI (when focused on missing TUI entry)
- `r/F5` — Force refresh
- `Up/Down` — Navigate within section
- `Tab` — Cycle focus between sections
- `j` — TUI Switcher overlay (via TuiSwitcherMixin)

#### 6. Refresh Timer

```python
def on_mount(self):
    self.monitor = TmuxMonitor(session=..., ...)
    self.call_later(self._refresh_data)
    self.set_interval(self.refresh_seconds, self._refresh_data)
```

#### 7. Entry Point

```python
def main():
    import argparse
    parser = argparse.ArgumentParser(description="tmux pane monitor")
    parser.add_argument("--session", "-s", default=None)
    parser.add_argument("--interval", "-i", type=int, default=None)
    parser.add_argument("--lines", "-n", type=int, default=None)
    args = parser.parse_args()
    # Load defaults from project_config.yaml, CLI args override
    MonitorApp(session=..., ...).run()
```

#### 8. Wrapper Script (`aitask_monitor.sh`)

Follow `aitask_board.sh` pattern:
- Source `terminal_compat.sh`
- Check Python (venv preferred, system fallback)
- Check `textual` and `pyyaml` packages
- Check tmux is installed
- `ait_warn_if_incapable_terminal`
- `exec "$PYTHON" "$SCRIPT_DIR/monitor/monitor_app.py" "$@"`

#### 9. CLI Dispatcher

Add to `ait` between `diffviewer` and `settings`:
```bash
monitor)      shift; exec "$SCRIPTS_DIR/aitask_monitor.sh" "$@" ;;
```

Add to `show_usage()` TUI section:
```
  monitor        Monitor tmux panes running code agents
```

### Verification

- Launch `ait monitor` with active tmux session
- Verify attention queue populates for idle agent panes
- Test Confirm/Decide Later/Switch To actions
- Test TUI panel: switch to running, spawn missing
- Test content preview updates on focus change
- Test from inside and outside tmux
- Test with no tmux session (graceful error message)
- Test `--session`, `--interval`, `--lines` CLI args
