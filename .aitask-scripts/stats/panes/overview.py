"""Overview category panes: summary counters, daily chart, weekday chart."""
from __future__ import annotations

from datetime import date, timedelta

from textual.containers import Container, Horizontal
from textual.widgets import Static

from stats.stats_data import DAY_NAMES, StatsData, build_chart_title

from .base import PaneDef, empty_state, register, render_chart

_WEEK_START_DOW = 1  # Monday; t597_4 will make this configurable.
_DAILY_DAYS = 30


def _render_summary(stats: StatsData, container: Container) -> None:
    today = date.today()
    today_count = stats.daily_counts.get(today, 0)
    cards = [
        ("Total", stats.total_tasks),
        ("Last 7 days", stats.tasks_7d),
        ("Last 30 days", stats.tasks_30d),
        ("Today", today_count),
    ]
    row = Horizontal()
    container.mount(row)
    for label, value in cards:
        row.mount(
            Static(
                f"[bold]{value}[/bold]\n[dim]{label}[/dim]",
                classes="summary_card",
            )
        )


def _render_daily(stats: StatsData, container: Container) -> None:
    if stats.total_tasks == 0:
        empty_state(container)
        return
    today = date.today()
    dseq = [today - timedelta(days=i) for i in range(_DAILY_DAYS - 1, -1, -1)]
    labels = [d.isoformat()[5:] for d in dseq]
    values = [stats.daily_counts.get(d, 0) for d in dseq]

    def setup(plt):
        positions = list(range(len(labels)))
        plt.plot(positions, values, marker="dot")
        plt.xticks(positions[::3], labels[::3])
        plt.title(build_chart_title("Daily Completions", f"last {_DAILY_DAYS} days"))

    render_chart(setup, container)


def _render_weekday(stats: StatsData, container: Container) -> None:
    if stats.total_tasks == 0:
        empty_state(container)
        return
    week_dows = [((_WEEK_START_DOW - 1 + j) % 7) + 1 for j in range(7)]
    labels = [DAY_NAMES[dow] for dow in week_dows]
    values = [stats.dow_counts_30d.get(dow, 0) for dow in week_dows]

    def setup(plt):
        plt.bar(labels, values)
        plt.title(
            build_chart_title(
                "Completions by Weekday", "last 30 days", _WEEK_START_DOW
            )
        )

    render_chart(setup, container)


register(PaneDef("overview.summary", "Summary", "Overview", _render_summary))
register(PaneDef("overview.daily", "Daily completions", "Overview", _render_daily))
register(PaneDef("overview.weekday", "Weekday distribution", "Overview", _render_weekday))
