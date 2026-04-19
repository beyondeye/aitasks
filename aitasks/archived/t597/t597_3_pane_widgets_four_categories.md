---
priority: medium
effort: high
depends: [t597_2]
issue_type: feature
status: Done
labels: [statistics, aitask_monitor]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-19 17:51
updated_at: 2026-04-19 22:53
completed_at: 2026-04-19 22:53
---

## Context

Third child of t597. Implements the actual pane widgets for the four preset categories defined in the parent plan: Overview, Labels & Issue Types, Agents & Models, Velocity. Each pane is a Textual widget that consumes `StatsData` from t597_1's `stats.stats_data` module and renders into the content container of the skeleton built in t597_2.

This is the heaviest of the children (12 panes total, grouped into 4 categories). Backend: `plotext` for line/bar/heatmap charts; `Static`/`DataTable` for tables and counter cards.

## Key Files to Modify

- `.aitask-scripts/stats/panes/__init__.py` (NEW) — `PANE_DEFS` registry mapping `id → PaneDef`.
- `.aitask-scripts/stats/panes/base.py` (NEW) — `PaneDef` dataclass + helpers.
- `.aitask-scripts/stats/panes/overview.py` (NEW) — `overview.summary`, `overview.daily`, `overview.weekday`.
- `.aitask-scripts/stats/panes/labels.py` (NEW) — `labels.top`, `labels.issue_types`, `labels.heatmap`.
- `.aitask-scripts/stats/panes/agents.py` (NEW) — `agents.per_agent`, `agents.per_model`, `agents.verified`.
- `.aitask-scripts/stats/panes/velocity.py` (NEW) — `velocity.daily`, `velocity.rolling`, `velocity.parent_child`.
- `.aitask-scripts/stats/stats_app.py` — replace stub pane list / content rendering with the registry-driven version. Use `PANE_DEFS[pane_id].render(stats_data, content_container)`.

## Reference Files for Patterns

- `.aitask-scripts/aitask_stats.py` lines 1021–1157 (`show_chart()`, `run_plot_summary()`) — the existing `--plot` rendering. Mirror chart titles, axis setup, color choices for visual consistency. (Note: t597_5 will delete this code; copy/translate the patterns into the new pane modules first.)
- Sibling `aiplans/p597/p597_1_*.md` for which `StatsData` Counters back which pane.
- Sibling `aiplans/p597/p597_2_*.md` for the skeleton's `Container(id="content")` it plugs into.

## Implementation Plan

1. **`base.py`**: define
   ```python
   @dataclass
   class PaneDef:
       id: str
       title: str
       category: str   # "Overview" | "Labels" | "Agents" | "Velocity"
       render: Callable[["StatsData", "Container"], None]
   ```
   Plus a small `register(pane_def)` helper that pane modules call at import time.
2. **`__init__.py`**: import each pane module so registrations fire; expose `PANE_DEFS` dict.
3. **plotext-in-Textual pattern**: wrap each chart in a `Static` widget whose `update(...)` is called with `plt.build()` output (plotext's `build()` returns a string). Set Static `markup=False` to preserve ANSI. Reuse a small helper `render_plotext_chart(plt_setup_fn) -> str` to avoid duplication.
4. **Counter cards** (`overview.summary`): `Horizontal` of `Static` widgets, each with a label + big number (use Rich markup for size if helpful).
5. **Tables** (`agents.verified`, `labels.heatmap`): use `DataTable`.
6. **Wire into skeleton**: in `stats_app.py`, replace the stub list with `[PANE_DEFS[pid] for pid in active_layout]`. On `ListView.selected`, clear `#content` children and call `pane_def.render(self.stats_data, content)`.
7. Each render function must be safe for empty `StatsData` (no archived tasks) — show "No data" placeholder rather than crash.

## Verification Steps

```bash
ait stats-tui                              # all 12 panes selectable; charts render
# Test with empty fixture: rm -rf aitasks/archived/* (in a sandbox), launch — no crash
shellcheck .aitask-scripts/aitask_stats_tui.sh    # still clean
```

Visual verification will happen in t597_6.

## Out of Scope

- Config modal / preset switching (t597_4 — sidebar still hardcoded to one preset).
- Persistence (t597_4).
- Removing `--plot` (t597_5).
