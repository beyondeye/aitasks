---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitor]
created_at: 2026-03-30 22:22
updated_at: 2026-03-30 22:22
---

## Problem

The monitor TUI preview pane displays black-and-white content from code agent windows instead of full color. This is not a tmux limitation — it's a two-part code issue.

## Root Cause

1. **Missing `-e` flag on `tmux capture-pane`** (`.aitask-scripts/monitor/tmux_monitor.py:136`): Without `-e`, tmux strips all ANSI escape sequences from the captured output, returning plain text only.

2. **No ANSI-to-Rich conversion in preview rendering** (`.aitask-scripts/monitor/monitor_app.py:792`): Even with `-e`, passing raw ANSI-encoded text to Textual's `Static.update(str)` treats it as Rich markup, not ANSI. The content must be converted using `Text.from_ansi()` from Rich.

## Fix

### File 1: `.aitask-scripts/monitor/tmux_monitor.py`
- Add `-e` flag to the `capture-pane` subprocess call at line 136

### File 2: `.aitask-scripts/monitor/monitor_app.py`
- Import `Text` from `rich.text`
- In `_update_content_preview()` (~line 792), convert the display text using `Text.from_ansi()` before passing to `preview.update()`

## Performance Impact

Benchmarked (100 iterations each):
- Capture time: 1.31ms → 1.72ms (+0.41ms)
- Data size: ~14KB → ~18KB (+30%)
- `Text.from_ansi()` conversion: 1.26ms
- **Total overhead: +1.7ms per refresh vs 300ms refresh interval (<0.6%) — negligible**
