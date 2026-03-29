---
priority: high
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [aitask_monitor, tui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-29 10:37
updated_at: 2026-03-29 12:47
---

## Core Monitoring Library

Non-UI Python module for tmux pane discovery, content capture, idle detection, and pane categorization.

### Context

This is the foundational library for the tmux Monitor TUI (parent task t475). It provides all tmux interaction logic without any Textual dependency, allowing reuse by the monitor app, TUI switcher widget, and board integration.

### Key Files to Create

- `.aitask-scripts/monitor/__init__.py` — empty package init
- `.aitask-scripts/monitor/tmux_monitor.py` — core module

### Key Files to Reference

- `.aitask-scripts/lib/agent_launch_utils.py` — existing tmux utilities (subprocess patterns, `load_tmux_defaults()`, `get_tmux_sessions()`, `get_tmux_windows()`)
- `aitasks/metadata/project_config.yaml` — config structure for `tmux.monitor` section

### Implementation Plan

#### 1. Data classes

```python
class PaneCategory(Enum):
    AGENT = "agent"    # Code agent window (matches configurable prefixes)
    TUI = "tui"        # TUI app window (matches configurable names)
    OTHER = "other"    # Unrecognized

@dataclass
class TmuxPaneInfo:
    window_index: str
    window_name: str
    pane_index: str
    pane_id: str        # e.g., %3
    pane_pid: int
    current_command: str
    width: int
    height: int
    category: PaneCategory

@dataclass
class PaneSnapshot:
    pane: TmuxPaneInfo
    content: str            # last N lines of captured text
    timestamp: float        # time.monotonic()
    idle_seconds: float     # seconds since last content change
    is_idle: bool           # idle_seconds > threshold (only for AGENT category)
```

#### 2. TmuxMonitor class

```python
class TmuxMonitor:
    def __init__(self, session: str, capture_lines: int = 30,
                 idle_threshold: float = 5.0, exclude_pane: str | None = None,
                 agent_prefixes: list[str] | None = None,
                 tui_names: set[str] | None = None)
```

**Methods:**
- `discover_panes()` — `tmux list-panes -s -t <session> -F` with tab-delimited fields
- `classify_pane(window_name)` — match against `agent_prefixes` and `tui_names` (from config)
- `capture_pane(pane_id)` — `tmux capture-pane -p -t <pane_id> -S -<N>`
- `capture_all()` — discover + capture all panes, compute idle_seconds
- `send_enter(pane_id)` — `tmux send-keys -t <pane_id> Enter`
- `switch_to_pane(pane_id)` — `tmux select-window` + `tmux select-pane`
- `spawn_tui(tui_name)` — `tmux new-window -t <session> -n <name> 'ait <name>'`
- `get_running_tuis()` / `get_missing_tuis()` — compare discovered TUI panes vs known TUI names

#### 3. Configurable classification

Read from `project_config.yaml`:
```yaml
tmux:
  monitor:
    refresh_seconds: 3
    idle_threshold_seconds: 5
    capture_lines: 30
    agent_window_prefixes:
      - "agent-"
    tui_window_names:
      - board
      - codebrowser
      - settings
      - brainstorm
      - monitor
      - diffviewer
```

Defaults used when config keys are absent.

#### 4. Idle detection

Store `_last_content: dict[str, str]` and `_last_change_time: dict[str, float]` per pane.
On each `capture_all()`, compare new content vs stored. If identical, keep old `last_change_time`.
If different, update both. `idle_seconds = monotonic() - last_change_time`. Only track for AGENT panes.

#### 5. Self-exclusion

If `$TMUX_PANE` env var is set, pass it as `exclude_pane` to filter out the monitor's own pane.

#### 6. Update existing agent window names to use `agent-` prefix

- `.aitask-scripts/board/aitask_board.py`: `pick-{num}` → `agent-pick-{num}`, `create-task` → `agent-create`
- `.aitask-scripts/codebrowser/codebrowser_app.py`: `explain-{filename}` → `agent-explain-{filename}`
- `.aitask-scripts/codebrowser/history_screen.py`: `qa-{task_id}` → `agent-qa-{task_id}`
- `.aitask-scripts/lib/agent_command_screen.py`: default fallback `aitask` → `agent-task`

### Verification

- Unit test: mock subprocess calls, verify pane discovery parsing
- Unit test: verify classify_pane with various window names
- Unit test: verify idle detection across multiple capture_all() calls
- Integration: run with actual tmux session, verify panes are listed correctly
