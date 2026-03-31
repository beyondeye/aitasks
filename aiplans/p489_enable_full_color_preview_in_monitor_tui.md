---
Task: t489_enable_full_color_preview_in_monitor_tui.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: Enable full color preview in monitor TUI (t489)

## Context

The monitor TUI preview pane shows black-and-white content because (1) `tmux capture-pane` strips ANSI escapes without the `-e` flag, and (2) the raw ANSI text isn't converted to Rich `Text` objects properly.

## Changes

### 1. Add `-e` flag to `tmux capture-pane` call

**File:** `.aitask-scripts/monitor/tmux_monitor.py:136`

```python
# Before:
["tmux", "capture-pane", "-p", "-t", pane_id, "-S", f"-{self.capture_lines}"]
# After:
["tmux", "capture-pane", "-p", "-e", "-t", pane_id, "-S", f"-{self.capture_lines}"]
```

- [x] Done

### 2. Use `Text.from_ansi()` for preview rendering

**File:** `.aitask-scripts/monitor/monitor_app.py:779-780`

`Text` is already imported at line 44. Replace the plain `Text()` constructor + `append()` with `Text.from_ansi()`:

```python
# Before:
content = Text(no_wrap=True)
content.append("\n".join(display_lines))
# After:
content = Text.from_ansi("\n".join(display_lines), no_wrap=True)
```

- [x] Done

## Verification

1. Run `ait monitor` in a tmux session with active code agents
2. Focus an agent pane — the preview should show colored output matching the real tmux pane
3. Verify no performance degradation (overhead is <2ms per refresh per the task's benchmarks)

## Final Implementation Notes
- **Actual work done:** Both changes implemented exactly as planned — added `-e` flag and switched to `Text.from_ansi()`
- **Deviations from plan:** None
- **Issues encountered:** None — `Text` was already imported, and `Text.from_ansi()` accepts `no_wrap` parameter directly
- **Key decisions:** Used `Text.from_ansi()` class method rather than `Text()` constructor + manual ANSI parsing, which is the canonical Rich approach
