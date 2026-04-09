---
Task: t496_2_core_minimonitor_tui.md
Parent Task: aitasks/t496_minimonitor.md
Sibling Tasks: aitasks/t496/t496_1_extract_monitor_shared.md, aitasks/t496/t496_3_autospawn_integration.md
Archived Sibling Plans: aiplans/archived/p496/p496_1_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Core Mini Monitor TUI (t496_2)

## Overview

Create the mini monitor TUI app — a narrow side-column Textual app that displays all code agents with idle status, supports key actions (switch, info, kill, quit), and auto-closes when no agents remain in its tmux window.

## Steps

### 1. Create `.aitask-scripts/monitor/minimonitor_app.py`

**~350 LOC Textual app.** Key design:

- **Layout:** 3 components — 1-line session bar (top), scrollable pane list (fill), 1-line key hints (bottom). No Header/Footer widgets.
- **Side-column design:** Optimized for ~40 column width. No preview zone.
- **Single zone:** No Tab zone cycling. Just up/down navigation in pane list.
- **CRITICAL:** No `tmux rename-window` — runs inside agent window, must keep agent name.

**Classes:**
- `MiniPaneCard(Static, can_focus=True)` — stores `pane_id`
- `MiniMonitorApp(TuiSwitcherMixin, App)` — main app

**Bindings:** `j` (switcher), `s` (switch), `i` (info), `k` (kill), `q` (quit), `r` (refresh)

**Refresh (every 3s):**
1. `capture_all()` session-wide
2. Auto-close check: `discover_window_panes(own_window_id)` → if only self remains → `self.exit()`
3. Rebuild session bar: `"{session} {N} agents {M idle}"`
4. Rebuild pane list: AGENT panes only, sorted by window_index
5. Restore focus

**Auto-close grace:** Track `_mount_time = time.monotonic()`. Skip auto-close check if `< 5s` since mount.

**Pane card format:**
```
● agent-pick-42       ok
  Fix login validation
```

**Entrypoint `main()`:** CLI args `--session`, `--interval`. Config from `project_config.yaml`. Session: CLI > detected > configured > "aitasks".

### 2. Create `.aitask-scripts/aitask_minimonitor.sh`

Shell launcher — same pattern as `aitask_monitor.sh`:
- Check python (venv > system), check textual+yaml, check tmux
- `ait_warn_if_incapable_terminal`
- `exec "$PYTHON" "$SCRIPT_DIR/monitor/minimonitor_app.py" "$@"`
- Make executable: `chmod +x`

### 3. Update `ait` dispatcher

- Help text: add `  minimonitor    Compact monitor for tmux agent panes` under TUI section
- Skip list (line 149): add `minimonitor`
- Dispatch case (after monitor): `minimonitor) shift; exec "$SCRIPTS_DIR/aitask_minimonitor.sh" "$@" ;;`

### 4. Update `aitasks/metadata/project_config.yaml`

Add `minimonitor` to `tmux.monitor.tui_window_names` list.

## Verification

1. `ait minimonitor --help` — shows help
2. Inside tmux: `ait minimonitor` — launches, shows agent list
3. `q` key — exits cleanly
4. `j` key — TUI switcher opens
5. Up/down + `i` — task info dialog
6. Up/down + `k` — kill confirmation
7. Narrow terminal (40 cols) — renders correctly
8. Kill all other panes in same window → minimonitor auto-closes after ~5s

## Step 9: Post-Implementation
Archive task, push changes, collect feedback.
