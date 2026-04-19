"""Agents category panes: per agent, per model, verified rankings."""
from __future__ import annotations

from textual.containers import Container
from textual.widgets import DataTable

from stats.stats_data import (
    StatsData,
    build_chart_title,
    chart_totals,
    codeagent_display_name,
    load_verified_rankings,
)

from .base import PaneDef, empty_state, register, render_chart


def _render_per_agent(stats: StatsData, container: Container) -> None:
    labels, values = chart_totals(
        stats.codeagent_week_counts, codeagent_display_name, range(4)
    )
    if not labels:
        empty_state(container)
        return

    def setup(plt):
        plt.bar(labels, values)
        plt.title(build_chart_title("Tasks by Code Agent", "last 4 weeks"))

    render_chart(setup, container)


def _render_per_model(stats: StatsData, container: Container) -> None:
    def display(key: str) -> str:
        return stats.model_display_names.get(key, key)

    labels, values = chart_totals(stats.model_week_counts, display, range(4), limit=10)
    if not labels:
        empty_state(container)
        return

    def setup(plt):
        plt.bar(labels, values, orientation="horizontal")
        plt.title(build_chart_title("Tasks by Model", "last 4 weeks"))

    render_chart(setup, container)


def _render_verified(stats: StatsData, container: Container) -> None:
    vdata = load_verified_rankings()
    if not vdata.operations:
        empty_state(container, "No verified rankings available")
        return

    op = vdata.operations[0]
    providers = vdata.by_window.get(op, {})
    entries = providers.get("all_providers", {}).get("all_time", [])
    if not entries:
        empty_state(container, f"No rankings for operation '{op}'")
        return

    table: DataTable = DataTable(zebra_stripes=True)
    container.mount(table)
    table.add_columns("Rank", "Model", "Provider", "Score", "Runs")
    for rank, entry in enumerate(entries, start=1):
        table.add_row(
            str(rank),
            entry.display_name,
            entry.provider,
            str(entry.score),
            str(entry.runs),
        )


register(PaneDef("agents.per_agent", "Per agent (4w)", "Agents", _render_per_agent))
register(PaneDef("agents.per_model", "Per model (4w)", "Agents", _render_per_model))
register(PaneDef("agents.verified", "Verified rankings", "Agents", _render_verified))
