---
title: "Stats"
linkTitle: "Stats"
weight: 35
description: "Terminal UI for browsing archive completion statistics through configurable pane layouts"
maturity: [experimental]
depth: [intermediate]
---

{{< static-img src="imgs/home/statistics.svg" alt="Stats TUI showing summary, daily completions, and weekday distribution panes" caption="The Stats TUI with the overview layout active." >}}

## Launching

```bash
ait stats-tui
```

The Stats TUI requires the shared Python virtual environment (installed by `ait setup`) with the `textual` and `pyyaml` packages. Interactive chart panes additionally need the optional `plotext` package — `ait setup` prompts `Install plotext for 'ait stats-tui' chart panes? [y/N]` in the Python venv step. Without `plotext`, the TUI still launches but chart panes render placeholders instead of charts.

Inside tmux you can also reach the TUI via the [TUI switcher](../monitor/how-to/#how-to-jump-to-another-tui) — press **`j`** in any other aitasks TUI and pick Stats.

## Purpose

Stats is the interactive, pane-based view of archived task completion data. It reuses the same `stats/stats_data.py` extraction module that backs the text-only [`ait stats`]({{< relref "/docs/commands/board-stats#ait-stats" >}}) command — the two share a single source of truth for summary counts, daily/weekly trends, label and issue-type breakdowns, code agent / LLM model histograms, and verified model score rankings.

Use `ait stats` for a scrollable text report you can pipe or redirect; use `ait stats-tui` when you want to flip between charts, try different layout combinations, or watch a single pane full-width.

## Layout

```
┌──────────────┬──────────────────┐
│  sidebar     │                  │
│  (active     │   content        │
│   layout     │   (chart or      │
│   panes)     │    summary)      │
├──────────────┤                  │
│  layout      │                  │
│  picker      │                  │
└──────────────┴──────────────────┘
```

The left column is split into two list panels:

- **Pane sidebar** (top) — the panes that belong to the currently active layout. Highlighting a row shows that pane immediately on the right; no Enter needed.
- **Layout picker** (bottom) — the set of available layouts. The active layout is marked with a `●` bullet. Press Enter on a row to activate that layout (its panes replace the sidebar contents).

**Tab** / **Shift+Tab** flips focus between the two list panels, and the focused panel gets a primary-colored left border as a visual hint.

## Built-in layouts (presets)

Four presets ship with the framework, each bundling three panes:

| Preset | Panes |
|--------|-------|
| **overview** | Summary · Daily completions · Weekday distribution |
| **labels** | Top labels · Issue types · Label × week |
| **agents** | Per agent (4w) · Per model (4w) · Verified rankings |
| **velocity** | Daily velocity · Rolling average · Parent vs child |

Presets are defined in `aitasks/metadata/stats_config.json` and are read-only at runtime: editing them happens out of the TUI, by editing that file directly.

## Custom layouts

You can define your own layouts on top of the presets. With focus on the layout picker:

- **n** — create a new custom layout. You are prompted for a name (must be unique across presets and existing customs), then a pane selector opens where you tick the panes you want to include.
- **e** — edit the highlighted custom layout's pane list. Opens the same pane selector pre-populated with the current selection.
- **d** — delete the highlighted custom layout. Only custom layouts can be deleted; presets are protected.

Custom layouts appear below the presets in the picker with a `[dim](custom)` suffix.

## Config persistence

The TUI uses a layered configuration:

- **Project layer** — `aitasks/metadata/stats_config.json` ships the four default presets and is checked into git. It is treated as read-only at runtime.
- **User layer** — `aitasks/metadata/stats_config.local.json` is gitignored and holds your runtime choices: the active layout name, your custom layouts, and the `days` / `week_start` preferences. Every Enter on the layout picker and every successful custom-layout save writes to this file.

This split keeps shared presets consistent across a team while letting each developer keep their own customizations local.

## Navigating

| Key | Action |
|-----|--------|
| **↑ / ↓** | Move highlight in the focused panel (sidebar highlights a pane, layout picker highlights a layout) |
| **Enter** | Activate the highlighted layout (on the layout picker); sidebar panes show on highlight — no Enter needed |
| **Tab / Shift+Tab** | Switch focus between sidebar and layout picker |
| **c** | Jump focus to the layout picker |
| **n** | New custom layout (focus must be on layout picker) |
| **e** | Edit highlighted custom layout |
| **d** | Delete highlighted custom layout |
| **r** | Refresh data from the archive |
| **j** | Open the [TUI switcher](../monitor/how-to/#how-to-jump-to-another-tui) |
| **q** | Quit |

---

**Next:** Back to the [TUI overview](../) or jump to the text command [`ait stats`]({{< relref "/docs/commands/board-stats#ait-stats" >}}).
