---
Task: t439_4_brainstorm_status_tab.md
Parent Task: aitasks/t439_agentcrew_logging.md
Sibling Tasks: aitasks/t439/t439_1_runner_log_capture.md, aitasks/t439/t439_2_shared_log_utils.md, aitasks/t439/t439_3_dashboard_log_browser.md
Archived Sibling Plans: aiplans/archived/p439/p439_*_*.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

## Plan: Add Log Browsing to Brainstorm TUI Status Tab

### Context

The Status tab (tab 5) was **already implemented by t423_7** with operation group display, agent status monitoring, expand/collapse, output previews, and auto-refresh. This task adds **log browsing only** on top of that existing infrastructure, reusing shared log utilities from t439_2.

**Already in place from t423_7 (DO NOT re-implement):**
- `GroupRow` widget — expandable operation groups
- `AGENT_STATUS_COLORS` constant — color-coded agent statuses
- `_refresh_status_tab()` — populates `#status_content` with groups + agent rows
- `_mount_group_agents()` / `_mount_agent_row()` — agent detail with heartbeat + output preview
- Auto-refresh timer (30s) and `on_tabbed_content_tab_activated()`
- `self._expanded_groups` set for expand/collapse state
- CSS for `GroupRow`, `.status_section_title`, `.status_agent_detail`, `.status_output_preview`
- Imports: `list_agent_files`, `format_elapsed`, `read_yaml` from `agentcrew_utils`

See `aiplans/archived/p423/p423_7_status_tab_crew_agent_monitoring.md` for full t423_7 implementation notes.

### Changes to `.aitask-scripts/brainstorm/brainstorm_app.py`

#### 1. Add log utility imports

```python
from agentcrew.agentcrew_log_utils import (
    list_agent_logs, read_log_tail, read_log_full, format_log_size,
)
```

#### 2. Create `LogDetailModal` (modal screen)

Modal screen for viewing log content, following `NodeDetailModal` pattern:
- Keybindings: `escape` to dismiss, `r` to refresh, `t` for tail, `f` for full
- Shows agent name + file size in header
- Content area with scrollable log text

#### 3. Create `StatusLogRow` (focusable widget)

Focusable row for log file entries. Shows: agent name, file size, last modified time.
Enter on focused row → push `LogDetailModal`.

#### 4. Extend `_refresh_status_tab()` — append log section

At the end of the existing `_refresh_status_tab()` method (after groups and ungrouped agents sections), add:

```python
# Log files section (added by t439_4)
logs = list_agent_logs(wt_path)
if logs:
    container.mount(Label(""))
    container.mount(Label("[bold]Agent Logs[/bold]  (Enter to view)", classes="status_section_title"))
    for log_info in logs:
        container.mount(StatusLogRow(log_info))
```

#### 5. Wire up log opening in `on_key()`

Add Enter handler for `StatusLogRow` — when focused and Enter pressed, push `LogDetailModal`:

```python
if isinstance(focused, StatusLogRow):
    self.push_screen(LogDetailModal(focused.log_info["path"], focused.log_info["name"]))
    event.prevent_default()
    event.stop()
    return
```

#### 6. Add CSS for log widgets

```css
StatusLogRow { height: 1; padding: 0 1; }
StatusLogRow:focus { background: $accent 20%; }
#log_modal_container { width: 90%; height: 85%; background: $surface; border: solid $primary; padding: 1 2; }
#log_modal_scroll { height: 1fr; }
```

### Verification
1. `ait brainstorm init <task_num>` → initialize session
2. Launch an explore from Actions tab
3. Switch to Status tab (press `5`)
4. Verify existing agent statuses still display correctly (from t423_7)
5. Verify agent logs are listed below the agent section, sorted by mtime
6. Press Enter on a log → modal opens with content
7. Press `t`/`f`/`r` in modal for tail/full/refresh
8. Verify auto-refresh updates both agent statuses and log list

### Post-Implementation
Archive task, commit, push per standard workflow.
