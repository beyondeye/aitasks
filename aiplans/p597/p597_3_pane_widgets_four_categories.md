---
Task: t597_3_pane_widgets_four_categories.md
Parent Task: aitasks/t597_ait_stats_tui.md
Sibling Tasks: aitasks/t597/t597_1_*.md, aitasks/t597/t597_2_*.md, aitasks/t597/t597_4_*.md, aitasks/t597/t597_5_*.md, aitasks/t597/t597_6_*.md
Archived Sibling Plans: aiplans/archived/p597/p597_*_*.md
Worktree: (no worktree — current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-19 19:45
---

# Plan: t597_3 — Pane widgets for the 4 preset categories

## Context

Implements the 12 pane widgets (4 categories × 3 panes each) that render `StatsData` into the content area of the TUI skeleton built in t597_2. This task establishes the `PaneDef` registry pattern that the config modal (t597_4) consumes, and replaces the `STUB_PANES` placeholder in `.aitask-scripts/stats/stats_app.py` with a registry-driven dispatch.

Verified against the current codebase on 2026-04-19. The data layer (`stats/stats_data.py` from t597_1) and the skeleton (`stats/stats_app.py` from t597_2) are both in place.

### Verification findings vs. the original plan

The original plan referenced `StatsData` field names that come from an earlier sibling draft (`p597_3` pre-t597_1). t597_1's final notes already called this out — this verified plan uses the canonical names:

| Original plan reference | Canonical `StatsData` field / derivation |
|---|---|
| `stats.label_counts` | `stats.label_counts_total` |
| `stats.issue_type_counts` | `stats.type_week_counts[(issue_type, 0)]` for this week (issue types are week-scoped, not a flat counter) |
| `stats.label_week_pairs` | `stats.label_week_counts` (Counter keyed by `(label, week_offset)`) |
| `stats.agent_counts_4w` | `chart_totals(stats.codeagent_week_counts, codeagent_display_name, range(4))` |
| `stats.model_counts_4w` | `chart_totals(stats.model_week_counts, lambda k: stats.model_display_names.get(k, k), range(4))` |
| `stats.parent_child` | `stats.type_week_counts[("parent", w)]` and `type_week_counts[("child", w)]` per week |

Integration points in the current `stats_app.py` to preserve:
- `_pane_id_to_widget_id()` / `_widget_id_to_pane_id()` helpers — keep and reuse (Textual widget ids can't contain `.`).
- `self.active_layout` is currently `list[tuple[str, str]]` — this task changes it to `list[str]` (pane ids only), with labels fetched from `PANE_DEFS[pid].title`.
- `collect_stats(date.today(), 1)` (Monday-start week) stays as-is; t597_4 will make it configurable.
- `action_config()` stub stays — it's t597_4's job.

## Key Files

### New
- `.aitask-scripts/stats/panes/__init__.py` — imports all submodules so `register()` fires; re-exports `PANE_DEFS` and `PaneDef`.
- `.aitask-scripts/stats/panes/base.py` — `PaneDef` dataclass, `PANE_DEFS` registry, `register()` helper, and the `render_chart()` plotext-to-Textual helper.
- `.aitask-scripts/stats/panes/overview.py` — `overview.summary`, `overview.daily`, `overview.weekday`.
- `.aitask-scripts/stats/panes/labels.py` — `labels.top`, `labels.issue_types`, `labels.heatmap`.
- `.aitask-scripts/stats/panes/agents.py` — `agents.per_agent`, `agents.per_model`, `agents.verified`.
- `.aitask-scripts/stats/panes/velocity.py` — `velocity.daily`, `velocity.rolling`, `velocity.parent_child`.

### Modified
- `.aitask-scripts/stats/stats_app.py` — replace `STUB_PANES`/`_show_pane()` stub with `PANE_DEFS`-driven dispatch. Change `active_layout` type from `list[tuple[str, str]]` to `list[str]`.

## Reference Files for Patterns

- `.aitask-scripts/aitask_stats.py:442-598` — `chart_plot_size()`, `show_chart()`, `run_plot_summary()`, `_import_plotext()`. Mirror the titles, axis setup, color choices. `show_chart()` calls `plt.show()` (writes to terminal) — we replace that with `plt.build()` (returns string). t597_5 deletes this code; patterns must be translated first.
- `.aitask-scripts/stats/stats_data.py:539-560` — `chart_totals()` already exists for the "top N with Other bucket" pattern; reuse it instead of re-implementing.
- `.aitask-scripts/stats/stats_data.py:512-537` — `codeagent_display_name()`, `week_start_display_name()`, `build_chart_title()` — reuse for consistent titles.
- `aiplans/archived/p597/p597_1_stats_data_module_refactor.md` (Final Implementation Notes §"Notes for sibling tasks → t597_3") — canonical `StatsData` field names.
- `aiplans/archived/p597/p597_2_tui_skeleton_and_switcher.md` (Final Implementation Notes) — the `_pane_id_to_widget_id` helpers and `active_layout` shape.

## Implementation Plan

### 1. `panes/base.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING

from rich.text import Text
from textual.containers import Container
from textual.widgets import Static

if TYPE_CHECKING:
    from stats.stats_data import StatsData


@dataclass(frozen=True)
class PaneDef:
    id: str               # stable, dotted: "category.pane"
    title: str            # sidebar label
    category: str         # "Overview" | "Labels" | "Agents" | "Velocity"
    render: Callable[["StatsData", Container], None]


PANE_DEFS: dict[str, PaneDef] = {}


def register(pane: PaneDef) -> PaneDef:
    if pane.id in PANE_DEFS:
        raise ValueError(f"Duplicate pane id: {pane.id}")
    PANE_DEFS[pane.id] = pane
    return pane


def render_chart(setup_fn, container: Container, width: int = 80, height: int = 20) -> None:
    """Build a plotext chart as a string and mount it inside `container`.

    `plt.build()` returns an ANSI-colored string; Rich's `Text.from_ansi()`
    turns it into a Static-compatible renderable that preserves colors.
    Falls back to a plain-text placeholder if plotext is not installed.
    """
    try:
        import plotext as plt  # type: ignore
    except ImportError:
        container.mount(Static("[dim]plotext not installed — run 'ait setup'[/dim]"))
        return
    plt.clear_figure()
    plt.plotsize(width, height)
    plt.theme("pro")
    setup_fn(plt)
    text = plt.build()
    plt.clear_figure()
    container.mount(Static(Text.from_ansi(text)))


def empty_state(container: Container, message: str = "No data") -> None:
    container.mount(Static(f"[dim]{message}[/dim]"))
```

### 2. `panes/__init__.py`

```python
"""Pane registry for the stats TUI.

Importing this package imports each category module, which in turn calls
`register()` to populate `PANE_DEFS`. Consumers should do
`from stats.panes import PANE_DEFS`.
"""
from .base import PANE_DEFS, PaneDef  # noqa: F401 — re-export
from . import overview, labels, agents, velocity  # noqa: F401 — side-effect imports

__all__ = ["PANE_DEFS", "PaneDef"]
```

### 3. `panes/overview.py`

Three panes. All must handle empty `StatsData` (`total_tasks == 0`).

- `overview.summary` — `Horizontal` container of `Static` counter cards. Fields: `stats.total_tasks`, `stats.tasks_7d`, `stats.tasks_30d`, plus "Today" = `stats.daily_counts.get(date.today(), 0)`. Use Rich markup `[bold]NN[/bold]\n[dim]Label[/dim]`.
- `overview.daily` — line chart using `plt.plot()` + `plt.xticks()` with categorical positions (matches `show_chart(..., kind="line", force_categorical=True)` in `aitask_stats.py:465-471`). X = last 30 days as `MM-DD`, Y = `stats.daily_counts.get(d, 0)`.
- `overview.weekday` — bar chart. X = weekday names from `DAY_NAMES[dow]`, Y = `stats.dow_counts_30d.get(dow, 0)`. Iterate `dow` as `((week_start_dow - 1 + j) % 7) + 1 for j in range(7)` with `week_start_dow=1` (Monday) — matches `run_plot_summary()` at `aitask_stats.py:516`.

### 4. `panes/labels.py`

- `labels.top` — bar chart of top 10 labels sorted by `stats.label_counts_total`. Use `sorted(stats.all_labels, key=lambda lbl: (-stats.label_counts_total.get(lbl, 0), lbl))[:10]`.
- `labels.issue_types` — bar chart. X = issue types from `get_valid_task_types()` (imported from `stats_data`), Y = `stats.type_week_counts.get((t, 0), 0)` for this week. Title timeframe: `"this week"`. Mirrors `aitask_stats.py:532-538`.
- `labels.heatmap` — `DataTable` with columns = ["Label", "W-3", "W-2", "W-1", "W0"] and rows for the top ~10 labels. Values pulled from `stats.label_week_counts[(label, w)]`. Use `DataTable.add_row()` with cell values; Textual styling for the table is enough — skip background-color formatting unless trivial.

### 5. `panes/agents.py`

- `agents.per_agent` — bar chart. Use `chart_totals(stats.codeagent_week_counts, codeagent_display_name, range(4))` from `stats_data` → `(labels, values)`. Timeframe: `"last 4 weeks"`.
- `agents.per_model` — bar chart. Use `chart_totals(stats.model_week_counts, lambda k: stats.model_display_names.get(k, k), range(4))`. Same timeframe.
- `agents.verified` — `DataTable`. Call `load_verified_rankings()` (from `stats_data`) → `VerifiedRankingData`. Pick one op (e.g. first in `vdata.operations`) and the `all_providers` / `all_time` window. Columns = ["Rank", "Model", "Score", "Runs"]. Rows from `vdata.by_window[op]["all_providers"]["all_time"]` (already sorted desc by score). If no operations, empty-state placeholder.

### 6. `panes/velocity.py`

- `velocity.daily` — line chart (last 30 days) — same data shape as `overview.daily` but titled "Daily velocity". Reuse the same builder helper if convenient.
- `velocity.rolling` — line chart. Series 1 = daily counts (30 days). Series 2 = 7-day rolling average computed inline (simple list comprehension). Plot both with `plt.plot()` twice before `build()`.
- `velocity.parent_child` — bar chart. X = `["W-3", "W-2", "W-1", "W0"]`. Two series: parents = `[stats.type_week_counts.get(("parent", w), 0) for w in (3,2,1,0)]`, children = `[stats.type_week_counts.get(("child", w), 0) for w in (3,2,1,0)]`. Use `plt.multiple_bar()` (plotext's grouped bar API). Fallback: two sequential single bars if `multiple_bar` is not available in this plotext version.

### 7. Wire into `stats_app.py`

Replace:

```python
STUB_PANES: list[tuple[str, str]] = [...]
```

with:

```python
from stats.panes import PANE_DEFS

# Hardcoded layout — t597_4 replaces with config-driven resolution.
HARDCODED_LAYOUT: list[str] = [
    "overview.summary", "overview.daily", "overview.weekday",
]
```

Change `self.active_layout` initialization in `__init__`:

```python
self.active_layout: list[str] = [pid for pid in HARDCODED_LAYOUT if pid in PANE_DEFS]
```

Update `compose()` sidebar construction:

```python
yield ListView(
    *[
        ListItem(Label(PANE_DEFS[pid].title), id=_pane_id_to_widget_id(pid))
        for pid in self.active_layout
    ],
    id="sidebar",
)
```

Update `on_mount()`:

```python
if self.active_layout:
    self._show_pane(self.active_layout[0])
    ...
```

Update `action_refresh()`:

```python
if 0 <= idx < len(self.active_layout):
    self._show_pane(self.active_layout[idx])
```

Replace `_show_pane()` body:

```python
def _show_pane(self, pane_id: str) -> None:
    content = self.query_one("#content", Container)
    content.remove_children()
    pane = PANE_DEFS.get(pane_id)
    if pane is None or self.stats_data is None:
        content.mount(Static("[dim]Pane unavailable[/dim]"))
        return
    pane.render(self.stats_data, content)
```

### 8. plotext as runtime dep (lazy fallback)

`render_chart()` already handles `ImportError`. For the two DataTable panes (`labels.heatmap`, `agents.verified`), plotext is not needed so they work even without it. For counter cards (`overview.summary`), plotext is not needed either.

## Verification

```bash
# Hardcoded layout visible
ait stats-tui
#   → sidebar lists "Summary", "Daily completions", "Weekday distribution"
#   → ↑/↓ cycles panes; each renders (cards, line chart, bar chart)
#   → r refreshes; q quits; j opens switcher

# All 12 panes: temporarily edit HARDCODED_LAYOUT in stats_app.py to include all 12
# and verify each renders without errors. (Final cross-pane validation is t597_6.)

# Empty-state: in a sandbox with no archived tasks, launch and verify "No data"
# placeholders render instead of crashes.

shellcheck .aitask-scripts/aitask_stats_tui.sh

python3 -c "
import sys; sys.path.insert(0, '.aitask-scripts')
from stats.panes import PANE_DEFS
assert len(PANE_DEFS) == 12, f'Expected 12 panes, got {len(PANE_DEFS)}: {list(PANE_DEFS)}'
for pid in ('overview.summary','overview.daily','overview.weekday',
            'labels.top','labels.issue_types','labels.heatmap',
            'agents.per_agent','agents.per_model','agents.verified',
            'velocity.daily','velocity.rolling','velocity.parent_child'):
    assert pid in PANE_DEFS, pid
print('PASS: 12 panes registered')
"
```

Step 9 (Post-Implementation) — commit/archive/push follows the standard workflow.

## Out of Scope

- Config modal / preset switching (t597_4 — sidebar stays hardcoded to one preset here).
- Persistence (t597_4).
- Removing `--plot` (t597_5).
- Cross-pane visual QA (t597_6).
