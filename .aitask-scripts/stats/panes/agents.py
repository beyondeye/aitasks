"""Agents category panes: per agent, per model, verified rankings."""
from __future__ import annotations

from textual.containers import Container, Vertical
from textual.widgets import DataTable, Static

from stats.stats_data import (
    StatsData,
    VerifiedRankingData,
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


def _ops_sorted_by_runs(vdata: VerifiedRankingData) -> list[str]:
    """Operations with > 0 all_providers/all_time runs, desc by run count, tie-broken by name asc."""
    def total_runs(op: str) -> int:
        entries = vdata.by_window.get(op, {}).get("all_providers", {}).get("all_time", [])
        return sum(e.runs for e in entries)

    ranked = [(op, total_runs(op)) for op in vdata.operations]
    ranked = [(op, n) for op, n in ranked if n > 0]
    ranked.sort(key=lambda x: (-x[1], x[0]))
    return [op for op, _ in ranked]


class VerifiedRankingsPane(Vertical):
    """Verified-rankings pane: header + DataTable, cyclable with ← / →."""

    DEFAULT_CSS = """
    VerifiedRankingsPane { height: auto; }
    VerifiedRankingsPane > #verified_header { height: auto; padding: 0 0 1 0; }
    """

    def __init__(self, vdata: VerifiedRankingData) -> None:
        super().__init__()
        self._vdata = vdata
        self._ops = _ops_sorted_by_runs(vdata)
        self._op_idx = 0
        self._header: Static | None = None
        self._table: DataTable | None = None

    def compose(self):
        self._header = Static(id="verified_header")
        yield self._header
        self._table = DataTable(zebra_stripes=True, cursor_type="row")
        yield self._table

    def on_mount(self) -> None:
        assert self._table is not None
        self._table.add_columns("Rank", "Model", "Provider", "Score", "Runs")
        self._populate()

    def _populate(self) -> None:
        assert self._header is not None and self._table is not None
        if not self._ops:
            self._header.update("[dim]No verified rankings with runs[/dim]")
            return
        op = self._ops[self._op_idx]
        entries = (
            self._vdata.by_window.get(op, {})
            .get("all_providers", {})
            .get("all_time", [])
        )
        total_runs = sum(e.runs for e in entries)
        nav_hint = "  [dim]← prev op · next op →[/dim]" if len(self._ops) > 1 else ""
        self._header.update(
            f"Operation: [b]{op}[/b]  ({total_runs} runs){nav_hint}"
        )
        self._table.clear(columns=False)
        for rank, entry in enumerate(entries, start=1):
            self._table.add_row(
                str(rank),
                entry.display_name,
                entry.provider,
                str(entry.score),
                str(entry.runs),
            )

    def cycle_op(self, delta: int) -> None:
        if len(self._ops) <= 1:
            return
        self._op_idx = (self._op_idx + delta) % len(self._ops)
        self._populate()


def _render_verified(stats: StatsData, container: Container) -> None:
    vdata = load_verified_rankings()
    if not _ops_sorted_by_runs(vdata):
        empty_state(container, "No verified rankings available")
        return
    container.mount(VerifiedRankingsPane(vdata))


register(PaneDef("agents.per_agent", "Per agent (4w)", "Agents", _render_per_agent))
register(PaneDef("agents.per_model", "Per model (4w)", "Agents", _render_per_model))
register(PaneDef("agents.verified", "Verified rankings", "Agents", _render_verified))
