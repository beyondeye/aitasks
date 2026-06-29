"""Pipeline category panes: time-in-phase timing + in-flight (gated) tasks.

Ledger-derived multi-stage views (t635_20). Both render gracefully when there
is no gate data yet (the common case until async/human gates are adopted).
"""
from __future__ import annotations

import statistics
from datetime import date, timedelta

from textual.containers import Container
from textual.widgets import Static

from stats.stats_data import StatsData, build_chart_title, format_duration

from .base import PaneDef, empty_state, register, render_chart

_INFLIGHT_DAYS = 30


def _render_timing(stats: StatsData, container: Container) -> None:
    """Time-in-phase spans (ledger timestamps only; each span its own N)."""
    pt = stats.phase_timings
    rows = [
        ("Implement (plan→review)", pt.implement_hours if pt else []),
        ("Review→Merge (review→merge)", pt.review_merge_hours if pt else []),
    ]
    if not any(samples for _, samples in rows):
        empty_state(container, "No gated tasks with ledger timing yet")
        return

    lines = [
        "[bold]Time in phase[/bold] [dim](gated tasks; ledger timestamps)[/dim]",
        "",
        f"  [dim]{'Span':<28} {'Median':>8} {'Mean':>8} {'N':>5}[/dim]",
    ]
    for label, samples in rows:
        if samples:
            median = format_duration(statistics.median(samples))
            mean = format_duration(statistics.fmean(samples))
            n = str(len(samples))
        else:
            median = mean = n = "—"
        lines.append(f"  {label:<28} {median:>8} {mean:>8} {n:>5}")
    container.mount(Static("\n".join(lines)))


def _render_inflight(stats: StatsData, container: Container) -> None:
    """In-flight 'completed, awaiting gates' tasks — a series separate from totals."""
    inflight = stats.inflight
    if inflight is None or inflight.count == 0:
        empty_state(container, "No in-flight tasks (none awaiting gates)")
        return

    today = date.today()
    dseq = [today - timedelta(days=i) for i in range(_INFLIGHT_DAYS - 1, -1, -1)]
    labels = [d.isoformat()[5:] for d in dseq]
    values = [inflight.daily_counts.get(d, 0) for d in dseq]

    container.mount(
        Static(
            f"[bold]{inflight.count}[/bold] task(s) implementation-done, "
            f"awaiting gates [dim](not counted in completions)[/dim]"
        )
    )
    if any(values):
        def setup(plt):
            positions = list(range(len(labels)))
            plt.bar(positions, values)
            plt.xticks(positions[::3], labels[::3])
            plt.title(build_chart_title("In-flight by review date", f"last {_INFLIGHT_DAYS} days"))

        render_chart(setup, container)


register(PaneDef("pipeline.timing", "Time in phase", "Pipeline", _render_timing))
register(PaneDef("pipeline.inflight", "In-flight (gated)", "Pipeline", _render_inflight))
