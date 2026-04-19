---
priority: medium
effort: medium
depends: [t597_1]
issue_type: feature
status: Ready
labels: [statistics, aitask_monitor]
created_at: 2026-04-19 17:51
updated_at: 2026-04-19 17:51
---

## Context

Second child of t597. Builds the Textual app skeleton (sidebar + content area), the `ait stats-tui` dispatcher entry, the bash wrapper, and the tmux TUI switcher integration. Panes (t597_3) and the config modal (t597_4) plug into this skeleton later.

Layout decision (parent plan): single active pane + sidebar — sidebar lists configured panes; one pane shown full-screen at a time; arrow-key navigation. No `n` key binding (per user).

## Key Files to Modify

- `.aitask-scripts/stats/stats_app.py` (NEW) — Textual `App`.
- `.aitask-scripts/aitask_stats_tui.sh` (NEW) — bash wrapper.
- `ait` (dispatcher) — add `stats-tui` subcommand.
- `.aitask-scripts/lib/tui_switcher.py` — add `("stats", "Statistics", "ait stats-tui")` to `KNOWN_TUIS`.

## Reference Files for Patterns

- `.aitask-scripts/monitor/minimonitor_app.py` — simple Textual app with single content pane (~700 LOC, easier to model than `aitask_board.py`).
- `.aitask-scripts/codebrowser/codebrowser_app.py` — sidebar + content layout (`Tree` on left + content on right).
- `.aitask-scripts/lib/tui_switcher.py` lines 59–65 (`KNOWN_TUIS`), line 86 (`_TUI_SHORTCUTS`), `TuiSwitcherMixin` (around line 465) — wire-up pattern.
- `.aitask-scripts/diffviewer/diffviewer_app.py` (274 LOC) — minimal Textual app structure with TuiSwitcherMixin.
- `ait` — existing dispatcher subcommand pattern (e.g., how `board`, `monitor`, `codebrowser` route to their `aitask_*.sh` wrappers).
- Sibling `aiplans/p597/p597_1_*.md` for the data layer this skeleton imports from.

## Implementation Plan

1. **Wrapper script** `.aitask-scripts/aitask_stats_tui.sh`:
   - Standard shebang `#!/usr/bin/env bash`, `set -euo pipefail`
   - Source `terminal_compat.sh`
   - Set `PYTHONPATH` to include `.aitask-scripts/` so `from stats.stats_data import …` resolves
   - `exec python3 .aitask-scripts/stats/stats_app.py "$@"`
2. **Dispatcher**: add `stats-tui)` case in `ait` that calls the wrapper.
3. **Switcher**: add `("stats", "Statistics", "ait stats-tui")` to `KNOWN_TUIS`. Optionally add a shortcut letter to `_TUI_SHORTCUTS` (e.g., `"stats": "t"` if free) — verify no clash with existing shortcuts.
4. **Textual app** `.aitask-scripts/stats/stats_app.py`:
   - `class StatsApp(TuiSwitcherMixin, App)` — set `self.current_tui_name = "stats"` in `__init__`
   - `BINDINGS = [Binding("up", ...), Binding("down", ...), Binding("r", "refresh", "Refresh"), Binding("c", "config", "Config"), Binding("q", "quit", "Quit"), *TuiSwitcherMixin.SWITCHER_BINDINGS]`
   - `compose()`: `Horizontal(ListView(...), Container(id="content"))` with explicit widths (sidebar narrow, content fills remainder)
   - Sidebar: `ListView` with `ListItem(Label(title))` for each pane in active layout. For now, populate from a hardcoded stub list so we can test sidebar/content swap before t597_3 lands.
   - `on_list_view_selected` → swap content container's child to a stub `Static` with the pane title.
   - `action_refresh()`: re-load `StatsData` from disk (calls `collect_stats()` from t597_1's module). Stub-render in content for now.
   - `action_config()`: stub — `self.notify("Config modal coming in t597_4")`.
5. **Priority binding caveat** (memory `feedback_textual_priority_bindings`): if the modal added in t597_4 redefines any of these, scope guards to `self.screen.query_one(...)` and raise `SkipAction` on miss. Document this for the next child.

## Verification Steps

```bash
ait stats-tui                              # opens TUI; sidebar shows stub panes
# Inside TUI: ↑/↓ should swap content; r should re-collect (no visible change yet); j opens switcher; q quits
ait board                                  # check switcher overlay (j) lists "Statistics"
shellcheck .aitask-scripts/aitask_stats_tui.sh
```

## Out of Scope

- Actual pane widgets (t597_3).
- Config modal logic (t597_4 — `c` is a stub here).
- Removing `--plot` (t597_5).
