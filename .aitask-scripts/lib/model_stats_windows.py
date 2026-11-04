"""model_stats_windows — date-correct time windows over the per-model counters.

`usagestats` and `verifiedstats` in `aitasks/metadata/models_<agent>.json` keep,
per skill, an `all_time` bucket plus three windowed buckets, each stamped with a
`period`:

    month       YYYY-MM    (writers: `date +%Y-%m`, local time)
    prev_month  YYYY-MM
    week        YYYY-Www   (writers: `date +%G-W%V` — ISO 8601 week and ISO year)

The writers (`aitask_usage_update.sh`, `aitask_verified_update.sh`) roll those
buckets over only when they record the NEXT run for that model and skill. A
model nobody has used for months therefore still carries its old `month` /
`prev_month` / `week` buckets. So a reader must never trust a bucket's slot
name. A bucket counts toward a window only when its `period` equals that
window's period computed from today. A stored `month` bucket from last month
(not rolled over yet) is last month's data, so it counts as `prev_month`.

This is the one implementation of that rule. The agent/model picker, the
settings TUI and `stats_data` (`ait stats`, the stats TUI) all read through it.

Standard library only, so any layer can import it.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, NamedTuple, Optional, Tuple

#: Codeagent operation key -> the skill name its runs are recorded under, for
#: the operations whose launched skill runs Satisfaction Feedback under a
#: different name. ``batch-review`` launches aitask-review, which records as
#: ``review``. Every other operation records under its own key.
STATS_KEY_BY_OPERATION: Dict[str, str] = {"batch-review": "review"}

#: The windowed bucket names, in display order. ``recent`` is month + prev_month.
WINDOW_NAMES: Tuple[str, ...] = ("month", "prev_month", "week", "recent")


def stats_key_for_operation(operation: str) -> str:
    """The usagestats / verifiedstats key that holds `operation`'s runs.

    Use it only where counters are looked up BY CODEAGENT OPERATION (the model
    picker, the settings Agent Defaults tab). Readers that iterate the recorded
    keys themselves (`ait stats`, the Models tab) already label by skill name.
    """
    return STATS_KEY_BY_OPERATION.get(operation, operation)


class Periods(NamedTuple):
    """The period strings of the current windows, in the writers' formats."""

    month: str
    prev_month: str
    week: str


def current_periods(today: Optional[date] = None) -> Periods:
    """Periods of the current month, the previous calendar month and the ISO week."""
    d = today if today is not None else date.today()
    if d.month > 1:
        prev_year, prev_month = d.year, d.month - 1
    else:
        prev_year, prev_month = d.year - 1, 12
    iso_year, iso_week, _ = d.isocalendar()
    return Periods(
        month=f"{d.year:04d}-{d.month:02d}",
        prev_month=f"{prev_year:04d}-{prev_month:02d}",
        week=f"{iso_year:04d}-W{iso_week:02d}",
    )


def _count(value) -> int:
    # bool is an int subclass; a hand-edited `true` is not a run count.
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 0


def _period(bucket) -> str:
    if isinstance(bucket, dict):
        value = bucket.get("period")
        if isinstance(value, str):
            return value
    return ""


def _counts(bucket) -> Tuple[int, int]:
    if not isinstance(bucket, dict):
        return 0, 0
    runs = _count(bucket.get("runs"))
    if runs <= 0:
        return 0, 0
    score_sum = bucket.get("score_sum", 0)
    if not isinstance(score_sum, int) or isinstance(score_sum, bool):
        score_sum = 0
    return runs, score_sum


def resolve_windows(buckets, today: Optional[date] = None) -> Dict[str, dict]:
    """Resolve one skill's stored buckets into the windows as of `today`.

    Returns ``{"month", "prev_month", "week": {"period", "runs", "score_sum"},
    "recent": {"runs", "score_sum"}}``. Each dated window is stamped with its
    current period, so the result can be stored or aggregated and resolved
    again unchanged. `score_sum` is 0 for usagestats, which records no scores.

    - ``month`` is the stored ``month`` bucket iff its period is this month.
    - ``prev_month`` is the FIRST of (stored ``prev_month``, stored ``month``)
      whose period is the previous month. The second case is a month the
      writer has not rolled over yet. Never both, so nothing is counted twice.
    - ``week`` is the stored ``week`` bucket iff its period is this ISO week.

    A missing or empty period, a non-dict bucket, or the old flat
    ``{runs, score_sum}`` format contributes nothing to any window.
    """
    periods = current_periods(today)
    stored = buckets if isinstance(buckets, dict) else {}
    stored_month = stored.get("month")
    stored_prev = stored.get("prev_month")
    stored_week = stored.get("week")

    month = _counts(stored_month) if _period(stored_month) == periods.month else (0, 0)
    prev = (0, 0)
    for candidate in (stored_prev, stored_month):
        if _period(candidate) == periods.prev_month:
            prev = _counts(candidate)
            break
    week = _counts(stored_week) if _period(stored_week) == periods.week else (0, 0)

    return {
        "month": {"period": periods.month, "runs": month[0], "score_sum": month[1]},
        "prev_month": {"period": periods.prev_month, "runs": prev[0], "score_sum": prev[1]},
        "week": {"period": periods.week, "runs": week[0], "score_sum": week[1]},
        "recent": {"runs": month[0] + prev[0], "score_sum": month[1] + prev[1]},
    }


def recent_aggregate(buckets, today: Optional[date] = None) -> Tuple[int, int]:
    """Return (runs, score_sum) for the current plus the previous month."""
    recent = resolve_windows(buckets, today)["recent"]
    return recent["runs"], recent["score_sum"]
