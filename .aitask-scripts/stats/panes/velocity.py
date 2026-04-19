"""Velocity category panes: daily line, rolling average, parent/child split."""
from __future__ import annotations

from datetime import date, timedelta

from textual.containers import Container

from stats.stats_data import StatsData, build_chart_title

from .base import PaneDef, empty_state, register, render_chart

_DAILY_DAYS = 30
_ROLLING_WINDOW = 7


def _daily_series(stats: StatsData, days: int) -> tuple[list[str], list[int]]:
    today = date.today()
    dseq = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
    labels = [d.isoformat()[5:] for d in dseq]
    values = [stats.daily_counts.get(d, 0) for d in dseq]
    return labels, values


def _render_daily(stats: StatsData, container: Container) -> None:
    if stats.total_tasks == 0:
        empty_state(container)
        return
    labels, values = _daily_series(stats, _DAILY_DAYS)

    def setup(plt):
        positions = list(range(len(labels)))
        plt.plot(positions, values, marker="dot")
        plt.xticks(positions[::3], labels[::3])
        plt.title(build_chart_title("Daily Velocity", f"last {_DAILY_DAYS} days"))

    render_chart(setup, container)


def _render_rolling(stats: StatsData, container: Container) -> None:
    if stats.total_tasks == 0:
        empty_state(container)
        return
    labels, values = _daily_series(stats, _DAILY_DAYS)
    rolling = []
    for i in range(len(values)):
        start = max(0, i - _ROLLING_WINDOW + 1)
        window = values[start : i + 1]
        rolling.append(round(sum(window) / len(window), 2))

    def setup(plt):
        positions = list(range(len(labels)))
        plt.plot(positions, values, marker="dot", label="daily")
        plt.plot(positions, rolling, marker="hd", label=f"{_ROLLING_WINDOW}d avg")
        plt.xticks(positions[::3], labels[::3])
        plt.title(
            build_chart_title(
                "Daily Velocity + Rolling Average", f"last {_DAILY_DAYS} days"
            )
        )

    render_chart(setup, container)


def _render_parent_child(stats: StatsData, container: Container) -> None:
    weeks = [3, 2, 1, 0]
    week_labels = [f"W-{w}" if w > 0 else "W0" for w in weeks]
    parents = [stats.type_week_counts.get(("parent", w), 0) for w in weeks]
    children = [stats.type_week_counts.get(("child", w), 0) for w in weeks]
    if sum(parents) + sum(children) == 0:
        empty_state(container, "No completions in the last 4 weeks")
        return

    def setup(plt):
        if hasattr(plt, "multiple_bar"):
            plt.multiple_bar(week_labels, [parents, children], labels=["Parent", "Child"])
        else:
            plt.bar(week_labels, parents, label="Parent")
            plt.bar(week_labels, children, label="Child")
        plt.title(build_chart_title("Parent vs Child Tasks", "last 4 weeks"))

    render_chart(setup, container)


register(PaneDef("velocity.daily", "Daily velocity", "Velocity", _render_daily))
register(PaneDef("velocity.rolling", "Rolling average", "Velocity", _render_rolling))
register(PaneDef("velocity.parent_child", "Parent vs child", "Velocity", _render_parent_child))
