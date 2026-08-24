"""Backlog category panes: open-task level and net flow, both by category.

The TUI half of t1544 — the same two series `ait stats` renders as text
(`aitask_stats.py::render_backlog_level` / `render_backlog_netflow`), shown here
as a `DataTable` and a `multiple_bar` chart.

Week start is **Monday**, like every other pane. Said explicitly rather than
inherited silently: `stats_app.py` passes `week_start_dow` as the literal `1` at
both `collect_stats` call sites, and the string->dow resolver `resolve_week_start`
lives in the CLI rather than in `lib/`, so honouring `stats_config`'s
persisted-but-unread `week_start` key would require moving that resolver first.
See the `t597_4` TODO in `overview.py`. This module derives no dates, so it needs
no `week_start_dow` of its own.

The row-axis / ordering / subtotal logic below duplicates `aitask_stats.py`'s,
whose versions are underscore-private, absent from its `__all__`, and part of the
CLI rather than `lib/` — importing them would make this the first pane->CLI
import and invert the layering. t1586 lifts the shared parts into
`lib/backlog_view.py`, designed against this module as the real second consumer.
"""
from __future__ import annotations

from collections import Counter
from typing import List, Sequence, Tuple

from rich.text import Text
from textual.containers import Container
from textual.widgets import DataTable, Static

from stats_data import (
    BACKLOG_WEEKS_DEFAULT,
    StatsData,
    backlog_levels,
    backlog_week_offsets,
    build_chart_title,
)
from task_category import category_display_name, is_followup_category

from .base import PaneDef, register, render_chart

#: Rows shown per block (follow-ups / genuine) in the level table. The `Other`
#: bucket counts toward it, so at most `_LEVEL_ROW_CAP - 1` real categories show.
_LEVEL_ROW_CAP = 6

#: Series in the net-flow chart, `Other` included. `render_chart` builds at
#: width=100 and 8 weeks x 5 series is already 40 bars, so the split is capped,
#: never stacked.
_NETFLOW_SERIES = 5

#: Chart height. `#content` is a plain Container with no scrollbar, so the
#: totals strip (4 rows) + this + padding (2) must fit the terminal.
_NETFLOW_CHART_H = 18

#: The `backlog_excluded` reasons that count TASKS. `negative_level` is
#: deliberately absent: it counts clamped OUTPUT CELLS, so summing it into a
#: task total would overstate the tally (t1544_3's recorded contract).
#: Mirrors `aitask_stats.BACKLOG_TASK_EXCLUSION_REASONS`, which is private there.
_TASK_EXCLUSION_REASONS = (
    "no_frontmatter",
    "folded",
    "invalid_followup_kind",
    "no_created_at",
    "future_created_at",
    "archived_no_completed_at",
    "future_completed_at",
)

_OTHER_LABEL = "Other"


def _columns(offsets: Sequence[int], now_label: str) -> Tuple[List[int], List[str]]:
    """Column offsets and their labels, shared by both backlog panes.

    Chronological, oldest first, with the current week LAST. Defined once so the
    two panes cannot drift into different column orders: they are meant to be
    read stacked, and aligning them is the whole point of the shared layout.

    `now_label` differs by pane -- the flow pane marks its current column `Now*`
    because a flow over a partial week is genuinely incomplete, while a level is
    a stock and is correct as-of-now.

    Mirrors `aitask_stats._backlog_columns` (t1588), which is private to the CLI.
    Keeping the same shape here is what makes t1586's extraction a straight lift.
    """
    weeks = [o for o in offsets if o != 0]
    return weeks + [0], [f"W-{o}" for o in weeks] + [now_label]


def _aggregate_all(flow: Counter) -> Counter:
    """Re-key a `(category, offset)` flow onto a single `("all", offset)` axis.

    MUST accumulate. A dict comprehension keeps only the LAST value written for
    each `("all", offset)` key, so every category arriving in the same week would
    silently overwrite the previous one. That matters more here than in the CLI:
    this pane CAPS its rows, so `TOTAL OPEN` cannot be recovered by summing what
    is on screen -- it has to come from this independent axis.
    """
    agg: Counter = Counter()
    for (_category, offset), n in flow.items():
        agg[("all", offset)] += n
    return agg


def _derive_levels(stats: StatsData, offsets: Sequence[int]):
    """`(levels, scope_levels, total_levels, clamped_cells)` for one render.

    The `excluded=` sink is a **per-call scratch Counter**, never
    `stats.backlog_excluded`. t1544_3's contract says to pass the shared counter
    "to keep the clamp counter live" -- correct for the one-shot CLI, wrong here:
    `stats_app._show_pane` re-renders against the SAME cached `StatsData` on every
    pane switch, so the shared counter would accumulate `negative_level` without
    bound for the life of the session.

    The scratch counter is read out and returned rather than dropped -- allocating
    a sink and discarding it is capturing a diagnostic without surfacing it.
    """
    clamps: Counter = Counter()
    levels = backlog_levels(
        stats.backlog_arrivals, stats.backlog_departures, offsets, excluded=clamps
    )
    scope_levels = backlog_levels(
        stats.backlog_scope_arrivals,
        stats.backlog_scope_departures,
        offsets,
        excluded=clamps,
    )
    total_levels = backlog_levels(
        _aggregate_all(stats.backlog_arrivals),
        _aggregate_all(stats.backlog_departures),
        offsets,
        excluded=clamps,
    )
    return levels, scope_levels, total_levels, clamps.get("negative_level", 0)


def _diagnostic_lines(stats: StatsData, clamped_cells: int) -> List[str]:
    """Data-quality lines, mirroring `aitask_stats._render_backlog_exclusions`.

    Returns `[]` when there is nothing to say. The task tally and the clamp count
    are separate lines because they count different things: seven reasons name
    TASKS that contributed to neither flow, while `negative_level` counts clamped
    output CELLS and must never be summed into a task total.
    """
    lines: List[str] = []
    present = [(r, stats.backlog_excluded.get(r, 0)) for r in _TASK_EXCLUSION_REASONS]
    present = [(r, n) for r, n in present if n]
    if present:
        detail = ", ".join(f"{r}: {n}" for r, n in present)
        total = sum(n for _, n in present)
        lines.append(f"Excluded from the backlog series: {total} task(s) ({detail}).")
    if clamped_cells:
        lines.append(f"Clamped negative level cells: {clamped_cells} (data-quality signal).")
    return lines


def _cap_block(block: List[str], levels: Counter, columns: Sequence[int]):
    """Split a block into shown rows and an optional `Other` row.

    `Other` sums the remainder per column, so `shown + Other == subtotal` holds
    for every column -- which is what keeps the capped table reconcilable.
    """
    if len(block) <= _LEVEL_ROW_CAP:
        return block, None
    shown = block[: _LEVEL_ROW_CAP - 1]
    rest = block[_LEVEL_ROW_CAP - 1:]
    other = [sum(levels.get((c, o), 0) for c in rest) for o in columns]
    return shown, (other if any(other) else None)


def _level_rows(
    stats: StatsData, weeks: int = BACKLOG_WEEKS_DEFAULT
) -> Tuple[List[str], List[Tuple[str, List[str]]], List[str]]:
    """`(headers, rows, diagnostics)` for the level table. Pure -- no Textual.

    Columns run chronologically with the current week LAST, matching the CLI
    (t1588) and the flow pane below. The column is labelled `Now` rather than
    `Now*`: offset 0 is a *stock*, correct as-of-now, so unlike a flow it is not
    distorted by the current week being partial.
    """
    offsets = backlog_week_offsets(weeks)
    levels, scope_levels, total_levels, clamped = _derive_levels(stats, offsets)
    diagnostics = _diagnostic_lines(stats, clamped)

    columns, headers = _columns(offsets, "Now")

    categories = {c for c, _ in stats.backlog_arrivals} | {c for c, _ in stats.backlog_departures}
    # `backlog_levels` emits explicit ZERO cells for every requested offset, so
    # "all-zero" must be tested on the values -- key absence means nothing here.
    visible = [c for c in categories if any(levels.get((c, o), 0) for o in offsets)]
    # Explicit tie-break: sorting a Counter keyset on -level alone is
    # insertion-order dependent, which makes the table non-deterministic.
    visible.sort(key=lambda c: (-levels.get((c, 0), 0), category_display_name(c)))

    followups = [c for c in visible if is_followup_category(c)]
    genuine = [c for c in visible if not is_followup_category(c)]

    def cells(source: Counter, key: str) -> List[str]:
        return [str(source.get((key, o), 0)) for o in columns]

    rows: List[Tuple[str, List[str]]] = []
    for block, subtotal_label in ((followups, "-- follow-ups"), (genuine, "-- genuine")):
        if not block:
            # No categories in this half -- an all-zero subtotal of nothing is
            # noise, and TOTAL OPEN still accounts for the other half.
            continue
        shown, other = _cap_block(block, levels, columns)
        for cat in shown:
            rows.append((category_display_name(cat), cells(levels, cat)))
        if other is not None:
            rows.append((_OTHER_LABEL, [str(n) for n in other]))
        rows.append(
            (
                subtotal_label,
                [str(sum(levels.get((c, o), 0) for c in block)) for o in columns],
            )
        )

    if rows:
        rows.append(("TOTAL OPEN", cells(total_levels, "all")))
        rows.append(("of which parents", cells(scope_levels, "parent")))
        rows.append(("of which children", cells(scope_levels, "child")))

    return headers, rows, diagnostics


def _netflow_rows(
    stats: StatsData, weeks: int = BACKLOG_WEEKS_DEFAULT
) -> Tuple[List[str], List[Tuple[str, List[str]]], List[str], List[List[int]]]:
    """`(week_labels, totals_rows, series_labels, series_values)`. Pure.

    Columns run chronologically with the current week LAST, because offset 0 is
    partial by construction -- matching the CLI.

    Row MEMBERSHIP is the FLOW rule, not the level rule: a category can have real
    flow inside the window and a level of zero at every offset (measured live:
    `kind:docs_gap`, 3 arrivals and 3 departures), and an all-zero-*level* test
    would suppress exactly the row a flow table exists to show.
    """
    offsets = backlog_week_offsets(weeks)
    levels, _scope, _total, _clamped = _derive_levels(stats, offsets)

    columns, labels = _columns(offsets, "Now*")

    arrivals, departures = stats.backlog_arrivals, stats.backlog_departures

    def net(cat: str, offset: int) -> int:
        return arrivals.get((cat, offset), 0) - departures.get((cat, offset), 0)

    categories = {c for c, _ in arrivals} | {c for c, _ in departures}
    members = [
        c
        for c in categories
        if any(arrivals.get((c, o), 0) or departures.get((c, o), 0) for o in offsets)
    ]
    if not members:
        return labels, [], [], []

    # Same ordering rule as the level table (follow-ups first, then current level
    # descending, name as tie-break) over a DIFFERENT membership.
    members.sort(
        key=lambda c: (not is_followup_category(c), -levels.get((c, 0), 0), category_display_name(c))
    )

    # Chart series are ranked by HORIZON VOLUME (arrivals + departures), not by
    # net. A category with many arrivals and equally many departures nets to ~0
    # while being among the most active -- ranking on net would bucket exactly
    # the category this pane exists to show into `Other`.
    def volume(cat: str) -> int:
        return sum(arrivals.get((cat, o), 0) + departures.get((cat, o), 0) for o in offsets)

    ranked = sorted(members, key=lambda c: (-volume(c), category_display_name(c)))
    chosen = ranked[: _NETFLOW_SERIES - 1]
    rest = ranked[_NETFLOW_SERIES - 1:]

    series_labels = [category_display_name(c) for c in chosen]
    series_values = [[net(c, o) for o in columns] for c in chosen]
    if rest:
        other = [sum(net(c, o) for c in rest) for o in columns]
        if any(other):
            series_labels.append(_OTHER_LABEL)
            series_values.append(other)

    arr = [sum(arrivals.get((c, o), 0) for c in members) for o in columns]
    dep = [sum(departures.get((c, o), 0) for c in members) for o in columns]
    totals_rows = [
        ("ARRIVALS", [str(n) for n in arr]),
        ("DEPARTURES", [str(n) for n in dep]),
        ("NET", [f"{a - d:+d}" if a - d else "0" for a, d in zip(arr, dep)]),
    ]
    return labels, totals_rows, series_labels, series_values


def _totals_strip(labels: Sequence[str], rows: Sequence[Tuple[str, List[str]]]) -> str:
    """The ARRIVALS / DEPARTURES / NET block as fixed-width plain text."""
    label_w = max(len(name) for name, _ in rows)
    cell_w = max(4, *(len(c) for _, cells in rows for c in cells), *(len(h) for h in labels))
    out = [" " * label_w + "".join(f" {h:>{cell_w}}" for h in labels)]
    for name, cells in rows:
        out.append(f"{name:<{label_w}}" + "".join(f" {c:>{cell_w}}" for c in cells))
    return "\n".join(out)


def _render_level(stats: StatsData, container: Container) -> None:
    headers, rows, diagnostics = _level_rows(stats)

    if not rows:
        # Not the generic empty state: the CLI splits this two ways and prints
        # the tally here too, because on the empty path it is the EXPLANATION for
        # the table's absence -- `main()`'s `has_backlog` predicate admits an
        # all-excluded repo precisely on the strength of those counters.
        if any(stats.backlog_excluded.get(r, 0) for r in _TASK_EXCLUSION_REASONS):
            message = "No open tasks could be placed in the backlog series."
        else:
            message = "No open tasks found."
        container.mount(Static(Text("\n".join([message, *diagnostics]))))
        return

    table: DataTable = DataTable(zebra_stripes=True, cursor_type="row")
    container.mount(table)
    table.add_columns("Category", *headers)
    for label, cells in rows:
        table.add_row(label, *cells)

    if diagnostics:
        container.mount(Static(Text("\n".join(diagnostics))))


def _render_netflow(stats: StatsData, container: Container) -> None:
    labels, totals_rows, series_labels, series_values = _netflow_rows(stats)

    if not totals_rows:
        container.mount(
            Static(Text(f"No backlog arrivals or departures in the last {BACKLOG_WEEKS_DEFAULT} weeks."))
        )
        return

    container.mount(Static(Text(_totals_strip(labels, totals_rows))))

    def setup(plt):
        if hasattr(plt, "multiple_bar"):
            plt.multiple_bar(labels, series_values, labels=series_labels)
        else:
            for name, values in zip(series_labels, series_values):
                plt.bar(labels, values, label=name)
        plt.title(
            build_chart_title(
                "Backlog Net Flow by Category", f"last {BACKLOG_WEEKS_DEFAULT} weeks"
            )
        )

    render_chart(setup, container, height=_NETFLOW_CHART_H)


register(PaneDef("backlog.level", "Backlog level", "Backlog", _render_level))
register(PaneDef("backlog.netflow", "Net flow", "Backlog", _render_netflow))
