---
Task: t597_3_pane_widgets_four_categories.md
Parent Task: aitasks/t597_ait_stats_tui.md
Sibling Tasks: aitasks/t597/t597_1_*.md, aitasks/t597/t597_2_*.md, aitasks/t597/t597_4_*.md, aitasks/t597/t597_5_*.md, aitasks/t597/t597_6_*.md
Archived Sibling Plans: aiplans/archived/p597/p597_*_*.md
Worktree: (no worktree — current branch)
Branch: main
Base branch: main
---

# Plan: t597_3 — Pane widgets for the 4 preset categories

## Context

Implements the 12 pane widgets (4 categories × 3 panes each) that render `StatsData` into the content area of the TUI skeleton built in t597_2. Backend is `plotext` for charts and Textual `Static` / `DataTable` for counters and tables.

This task establishes the `PaneDef` registry pattern that the config modal (t597_4) consumes.

## Implementation Plan

### 1. `panes/base.py`

```python
from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING
if TYPE_CHECKING:
    from textual.containers import Container
    from stats.stats_data import StatsData


@dataclass(frozen=True)
class PaneDef:
    id: str               # stable, dotted: "category.pane"
    title: str            # sidebar label
    category: str         # "Overview" | "Labels" | "Agents" | "Velocity"
    render: Callable[["StatsData", "Container"], None]


PANE_DEFS: dict[str, PaneDef] = {}


def register(pane: PaneDef) -> PaneDef:
    if pane.id in PANE_DEFS:
        raise ValueError(f"Duplicate pane id: {pane.id}")
    PANE_DEFS[pane.id] = pane
    return pane
```

### 2. `panes/__init__.py`

```python
from . import overview, labels, agents, velocity  # noqa: F401 — side-effect imports register panes
from .base import PANE_DEFS, PaneDef  # re-export
```

### 3. plotext-in-Textual helper

In `panes/base.py` (or a new `panes/_plotext.py`):

```python
def render_chart(setup_fn, container, width=80, height=20) -> None:
    """Build a plotext chart string and mount it as a Static."""
    import plotext as plt
    plt.clear_figure()
    plt.plotsize(width, height)
    setup_fn(plt)
    text = plt.build()
    plt.clear_figure()
    container.mount(Static(text, markup=False))
```

### 4. Per-category modules

For each `panes/<cat>.py`, define one `register(PaneDef(...))` per pane, render functions consume `StatsData`:

#### `panes/overview.py`
- `overview.summary` — Horizontal of counter cards (total, last 7d, last 30d, today). Use `Static` with Rich markup for big numbers.
- `overview.daily` — line chart from `stats.daily_counts` (last N days).
- `overview.weekday` — bar chart from `stats.dow_counts_30d`.

#### `panes/labels.py`
- `labels.top` — bar chart of top 10 labels from `stats.label_counts`.
- `labels.issue_types` — bar of `stats.issue_type_counts`.
- `labels.heatmap` — `DataTable` (label × week, last 4 weeks) from `stats.label_week_pairs`. Use background-color formatting where possible.

#### `panes/agents.py`
- `agents.per_agent` — bar of `stats.agent_counts_4w`.
- `agents.per_model` — bar of `stats.model_counts_4w` with display names from `load_model_cli_ids()`.
- `agents.verified` — `DataTable` from `load_verified_rankings()`.

#### `panes/velocity.py`
- `velocity.daily` — line from `stats.daily_counts` (last 30 days).
- `velocity.rolling` — same series + 7-day rolling average overlay.
- `velocity.parent_child` — stacked bar (parent vs child counts per week).

### 5. Empty-state safety

Every render function must handle empty data:

```python
def render(stats: StatsData, container: Container) -> None:
    if not stats.daily_counts:
        container.mount(Static("[dim]No data[/dim]"))
        return
    # … real render
```

### 6. Wire into `stats_app.py`

Replace `STUB_PANES` and the stub `_show_pane`:

```python
from stats.panes import PANE_DEFS

# Hardcoded for this task — t597_4 replaces with config-driven layout
ACTIVE_LAYOUT = ["overview.summary", "overview.daily", "overview.weekday"]

# Sidebar:
yield ListView(
    *[ListItem(Label(PANE_DEFS[pid].title), id=pid.replace(".", "_"))
      for pid in ACTIVE_LAYOUT if pid in PANE_DEFS],
    id="sidebar",
)

# In _show_pane:
def _show_pane(self, pane_id: str) -> None:
    content = self.query_one("#content", Container)
    content.remove_children()
    pane = PANE_DEFS.get(pane_id)
    if pane is None or self.stats_data is None:
        content.mount(Static("[dim]Pane unavailable[/dim]"))
        return
    pane.render(self.stats_data, content)
```

### 7. plotext as runtime dep

Verify `plotext` is importable. If `aitask_stats.py`'s old code used a lazy import for graceful fallback (no plotext installed), the TUI can do the same — render a `Static` with "Install plotext: pip install plotext" instead of crashing. Reuse the lazy-import pattern from the old `_import_plotext()` (still in `aitask_stats.py` until t597_5).

## Verification

```bash
ait stats-tui                              # all 3 hardcoded panes render charts
# Cycle ↑/↓ — overview.summary cards, overview.daily line chart, overview.weekday bars all visible
# Empty-state test: in a sandbox with no archived tasks, launch and verify "No data" placeholders
shellcheck .aitask-scripts/aitask_stats_tui.sh
```

For the other 9 panes (labels/agents/velocity), test them by temporarily editing `ACTIVE_LAYOUT` in `stats_app.py`. Final validation across all 12 happens in t597_6.

## Out of Scope

- Config modal / preset switching (t597_4 — sidebar still hardcoded to one preset here).
- Persistence (t597_4).
- Removing `--plot` (t597_5).
