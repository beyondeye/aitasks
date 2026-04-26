"""Sessions category panes: per-session totals comparison."""
from __future__ import annotations

from textual.containers import Container

from stats.stats_data import StatsData

from .base import PaneDef, empty_state, register, render_chart


def _render_totals(stats: StatsData, container: Container) -> None:
    breakdown = stats.session_breakdown
    if not breakdown:
        empty_state(
            container,
            "Per-session breakdown unavailable — only one aitasks session detected",
        )
        return

    labels = [s.project_name for s in breakdown]
    today = [s.tasks_today for s in breakdown]
    seven = [s.tasks_7d for s in breakdown]
    thirty = [s.tasks_30d for s in breakdown]

    def setup(plt):
        if hasattr(plt, "multiple_bar"):
            plt.multiple_bar(labels, [today, seven, thirty],
                             labels=["Today", "7d", "30d"])
        else:
            plt.bar(labels, today, label="Today")
            plt.bar(labels, seven, label="7d")
            plt.bar(labels, thirty, label="30d")
        plt.title("Per-session totals")

    render_chart(setup, container)


register(PaneDef("sessions.totals", "Per-session totals", "Sessions", _render_totals))
