"""Labels category panes: top labels, issue types, label-by-week heatmap."""
from __future__ import annotations

from textual.containers import Container
from textual.widgets import DataTable

from stats.stats_data import StatsData, build_chart_title, get_valid_task_types

from .base import PaneDef, empty_state, register, render_chart

_TOP_LABELS = 10
_HEATMAP_LABELS = 10
_HEATMAP_WEEKS = 4  # W-3 .. W0


def _render_top(stats: StatsData, container: Container) -> None:
    if not stats.all_labels:
        empty_state(container)
        return
    ordered = sorted(
        stats.all_labels,
        key=lambda lbl: (-stats.label_counts_total.get(lbl, 0), lbl),
    )[:_TOP_LABELS]
    values = [stats.label_counts_total.get(lbl, 0) for lbl in ordered]

    def setup(plt):
        plt.bar(ordered, values, orientation="horizontal")
        plt.title(build_chart_title("Top Labels", "all time"))

    render_chart(setup, container)


def _render_issue_types(stats: StatsData, container: Container) -> None:
    types = get_valid_task_types()
    values = [stats.type_week_counts.get((t, 0), 0) for t in types]
    if sum(values) == 0:
        empty_state(container, "No completions this week")
        return

    def setup(plt):
        plt.bar([t.capitalize() for t in types], values)
        plt.title(build_chart_title("Issue Types", "this week"))

    render_chart(setup, container)


def _render_heatmap(stats: StatsData, container: Container) -> None:
    if not stats.all_labels:
        empty_state(container)
        return
    ordered = sorted(
        stats.all_labels,
        key=lambda lbl: (-stats.label_counts_total.get(lbl, 0), lbl),
    )[:_HEATMAP_LABELS]
    week_cols = list(range(_HEATMAP_WEEKS - 1, -1, -1))  # [3, 2, 1, 0]

    table: DataTable = DataTable(zebra_stripes=True)
    container.mount(table)
    table.add_columns("Label", *(f"W-{w}" if w > 0 else "W0" for w in week_cols))
    for label in ordered:
        row_values = [
            str(stats.label_week_counts.get((label, w), 0)) for w in week_cols
        ]
        table.add_row(label, *row_values)


register(PaneDef("labels.top", "Top labels", "Labels", _render_top))
register(PaneDef("labels.issue_types", "Issue types", "Labels", _render_issue_types))
register(PaneDef("labels.heatmap", "Label × week", "Labels", _render_heatmap))
