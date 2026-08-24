"""Base-layer module: the shared row axis for the weekly backlog series.

The derivation both backlog surfaces need and neither owns — the CLI text
report (`aitask_stats.py::render_backlog_level` / `render_backlog_netflow`) and
the stats TUI panes (`stats/panes/backlog.py`). t1544_4 kept this logic private
to the CLI on purpose, refusing to shape a helper around a *guessed* consumer;
t1544_5 supplied the real second one, and t1586 lifted the parts they genuinely
share down here.

What lives here is the part that must not diverge: the accumulating all-tasks
re-key, the three level axes with their per-call clamp sink, and the
deterministic ordering rule. What deliberately does NOT live here is anything
about *presentation* — pipe-table formatting, truncating label cells and
width-adaptive numeric cells are the CLI's; the row cap, the `Other` bucket and
the chart series split are the TUI's. The two net-flow row-MEMBERSHIP predicates
also stay with their surfaces: membership is a per-table decision (a category
can have real flow and a level of zero at every offset), and only the ORDERING
is shared.

It sits in ``lib/`` because both layers above depend on it and it depends on
none of them — `stats_data` and `task_category` are base-layer siblings.
``tests/test_no_lib_to_tui_import.sh`` freezes that direction, and
``tests/test_backlog_view_is_single_sourced.py`` freezes the other half: that
neither surface re-declares what was lifted here.
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

# Make lib/ importable however this module is loaded (path-loaded by a test, or
# imported bare with lib/ on sys.path). Both modules imported below live beside
# this one — it reaches into no sibling package.
_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
from stats_data import StatsData, backlog_levels  # noqa: E402
from task_category import category_display_name, is_followup_category  # noqa: E402

#: The `backlog_excluded` reasons that count TASKS. `negative_level` is
#: deliberately absent: it counts clamped OUTPUT CELLS, so summing it into a
#: task total would overstate the tally (t1544_3's recorded contract). Both
#: surfaces read this tuple rather than mirroring it, so the two can no longer
#: disagree about which reasons are task-level.
BACKLOG_TASK_EXCLUSION_REASONS = (
    "no_frontmatter",
    "folded",
    "invalid_followup_kind",
    "no_created_at",
    "future_created_at",
    "archived_no_completed_at",
    "future_completed_at",
)


@dataclass
class BacklogAxis:
    """Row axis + derived levels shared by the two backlog sections.

    Built ONCE per render. `backlog_levels`' `excluded=` sink counts clamped
    output cells per call, so calling it again per section would multiply-book
    `negative_level` and make the render non-idempotent; each axis therefore
    gets its own scratch counter, reported separately from the seven task-level
    reasons.

    Carries no presentation state. Cell widths in particular are per-surface and
    per-table — the CLI derives one width for its level table and another for
    its flow table, and the TUI derives none at all — so they are locals at the
    render site, never fields here.
    """

    offsets: List[int]
    levels: Counter
    scope_levels: Counter
    total_levels: Counter
    followup_rows: List[str]
    genuine_rows: List[str]
    clamped_cells: int = 0

    @property
    def has_rows(self) -> bool:
        return bool(self.followup_rows or self.genuine_rows)


def aggregate_all(flow: Counter) -> Counter:
    """Re-key a `(category, offset)` flow onto a single `("all", offset)` axis.

    MUST accumulate. A dict comprehension keeps only the LAST value written for
    each `("all", offset)` key, so every category arriving in the same week
    would silently overwrite the previous one -- `TOTAL OPEN` would then be one
    arbitrary category's level and would disagree with the parent/child
    partition, destroying the invariant this independent axis exists to protect.

    It matters more on the TUI than on the CLI: the pane CAPS its rows, so
    `TOTAL OPEN` cannot be recovered by summing what is on screen -- it has to
    come from this independent axis.
    """
    agg: Counter = Counter()
    for (_category, offset), n in flow.items():
        agg[("all", offset)] += n
    return agg


def order_categories(
    categories: Iterable[str], levels: Counter, *, followups_first: bool = False
) -> List[str]:
    """Deterministic category order: current level descending, name as tie-break.

    The explicit tie-break is load-bearing: sorting a Counter keyset on `-level`
    alone is insertion-order dependent, which makes the table non-deterministic
    between runs over the same data.

    `followups_first=True` prefixes the follow-up/genuine partition, which is how
    both net-flow surfaces order a membership they compute for themselves. The
    level tables get the same key without that prefix and partition afterwards,
    so the two orderings cannot drift apart.
    """
    def key(cat: str):
        base = (-levels.get((cat, 0), 0), category_display_name(cat))
        return (not is_followup_category(cat), *base) if followups_first else base

    return sorted(categories, key=key)


def build_backlog_axis(data: StatsData, offsets: Sequence[int]) -> BacklogAxis:
    """Derive every level series the two backlog sections render.

    The `excluded=` sink is a **per-call scratch Counter**, never
    `data.backlog_excluded`. t1544_3's contract says to pass the shared counter
    "to keep the clamp counter live" -- correct for the one-shot CLI, wrong for a
    long-lived TUI: `stats_app._show_pane` re-renders against the SAME cached
    `StatsData` on every pane switch, so the shared counter would accumulate
    `negative_level` without bound for the life of the session.

    The scratch counter is read out onto `clamped_cells` rather than dropped --
    allocating a sink and discarding it is capturing a diagnostic without
    surfacing it.
    """
    clamps: Counter = Counter()
    levels = backlog_levels(data.backlog_arrivals, data.backlog_departures, offsets, excluded=clamps)
    scope_levels = backlog_levels(
        data.backlog_scope_arrivals, data.backlog_scope_departures, offsets, excluded=clamps
    )
    total_levels = backlog_levels(
        aggregate_all(data.backlog_arrivals), aggregate_all(data.backlog_departures), offsets, excluded=clamps
    )

    categories = {c for c, _ in data.backlog_arrivals} | {c for c, _ in data.backlog_departures}
    # backlog_levels emits explicit ZERO cells for every requested offset, so
    # "all-zero" must be tested on the values -- key absence means nothing here.
    visible = order_categories(
        (c for c in categories if any(levels.get((c, o), 0) for o in offsets)), levels
    )

    return BacklogAxis(
        offsets=list(offsets),
        levels=levels,
        scope_levels=scope_levels,
        total_levels=total_levels,
        followup_rows=[c for c in visible if is_followup_category(c)],
        genuine_rows=[c for c in visible if not is_followup_category(c)],
        clamped_cells=clamps.get("negative_level", 0),
    )


def backlog_columns(offsets: Sequence[int], now_label: str) -> Tuple[List[int], List[str]]:
    """Column offsets and their labels, shared by both backlog tables.

    Chronological, oldest first, with the current week LAST. Defined once so the
    level and flow tables cannot drift into different column orders: they are
    meant to be read stacked, and aligning them is the whole point of the shared
    layout (t1588).

    `now_label` differs by table -- the flow table marks its current column
    `Now*` because a flow over a partial week is genuinely incomplete, while a
    level is a stock and is correct as-of-now.
    """
    weeks = [o for o in offsets if o != 0]
    return weeks + [0], [f"W-{o}" for o in weeks] + [now_label]
