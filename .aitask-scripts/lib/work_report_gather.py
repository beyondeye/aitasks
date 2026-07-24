#!/usr/bin/env python3
"""work_report_gather - deterministic report input for /aitask-work-report.

Emits the board columns a report covers, the parent tasks they contain in board
order, a per-bucket throughput estimate, and a completion projection. Two
consumers share it: the `/aitask-work-report` skill (interactive + argument
paths) and the board's `w` flow, which passes the reviewed selection back as
`--columns` / `--tasks`.

Line protocol (exit 0 for every validation outcome; nonzero only for usage or
infrastructure failures):

    COLUMN:<col_id>|<title>
    TASK:<col_id>|<task_id>|<boardidx>|<status>|<priority>|<effort>|<pending_children>|<remaining_items>|<task_file_path>
    VELOCITY_MODEL:<model_id>|<window_days>|<start_date>|<end_date>|<model_label>
    VELOCITY:<bucket_id>|<observed_units>|<completed_count>|<avg_per_unit>|<bucket_label>
    PROJECTION:<remaining_total>|<projected_date>|<days_ahead>|<basis_completions>|<caveat>
    PROJECTION:<remaining_total>|none|insufficient_data|<basis_completions>|<caveat>
    ERROR:<kind>:<id>
    NO_TASKS

PROJECTION is emitted only under --project. It is deliberately not a default
output: the models count tasks and are blind to task size, blockers and
capacity, so a projected date extrapolates past throughput rather than
estimating delivery. <basis_completions> reports how many completions the
estimate rests on, and <caveat> names the limitation consumers must surface.

At most one free-text field per record and it is always LAST, so consumers
split on '|' with a fixed maxsplit and need no escaping engine.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

# Make the sibling script packages importable however this module is invoked
# (via the .sh wrapper or directly from a test). Mirrors the bootstrap in
# stats/stats_data.py. `lib/` is already sys.path[0] when run as a script, so
# task_yaml needs no insert (t1217 moved it there). `stats` is the one
# remaining upward reach — see the allowlist in
# tests/test_no_lib_to_tui_import.sh.
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ("stats",):
    _sub_dir = os.path.join(_SCRIPTS_DIR, _sub)
    if _sub_dir not in sys.path:
        sys.path.insert(0, _sub_dir)

from config_utils import load_layered_config, metadata_dir, task_dir  # noqa: E402
from stats_data import DAY_NAMES, collect_stats  # noqa: E402
from task_yaml import BOARD_KEYS, normalize_board_idx, parse_frontmatter  # noqa: E402

# Board defaults, kept in sync with aitask_board.py DEFAULT_COLUMNS/DEFAULT_ORDER.
DEFAULT_COLUMNS = [
    {"id": "now", "title": "Now ⚡", "color": "#FF5555"},
    {"id": "next", "title": "Next Week 📅", "color": "#50FA7B"},
    {"id": "backlog", "title": "Backlog 🗄️", "color": "#BD93F9"},
]
DEFAULT_ORDER = ["now", "next", "backlog"]

UNORDERED_ID = "unordered"
UNORDERED_TITLE = "Unsorted / Inbox"

DEFAULT_VELOCITY_WINDOW = 90
PROJECTION_MAX_DAYS = 3650

# Fewest completions in the window before a completion date may be projected.
# Below this the weekday averages are dominated by individual events and the
# resulting date is noise wearing a number's clothes.
PROJECTION_MIN_COMPLETIONS = 10

# Named limitation every consumer must surface alongside a projection: the
# models count TASKS, so they are blind to task size (the `effort` field the
# TASK rows already carry), blockers, and capacity changes. A projection is an
# extrapolation of past task throughput, never a delivery estimate.
PROJECTION_CAVEAT = "unweighted_task_counts"

TASK_FILE_RE = re.compile(r"^t(\d+(?:_\d+)?)_")

EXIT_USAGE = 2
EXIT_INFRA = 3


# --- Delimiter safety -------------------------------------------------------
#
# The protocol has no escaping engine, so a value that can contain '|', CR or LF
# would make the record boundary undecidable. col_id comes from user-editable
# board_config.json and status/priority/effort from user-editable task YAML, so
# neither is pipe-free by construction — each field class gets an explicit,
# tested policy instead of an assumption.

_RECORD_BREAKING = ("|", "\r", "\n")
INVALID_ENUM = "invalid"
UNKNOWN_ENUM = "unknown"


def _has_record_breaking(value: str) -> bool:
    return any(ch in value for ch in _RECORD_BREAKING)


def _free_text(value: str) -> str:
    """Sanitize a free-text LAST field: '|' survives (maxsplit), CR/LF cannot."""
    return value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")


def _enum_field(value) -> str:
    """A fixed-position enum-ish field: absent -> `unknown`, unsafe -> `invalid`."""
    if value is None or value == "":
        return UNKNOWN_ENUM
    text = str(value)
    return INVALID_ENUM if _has_record_breaking(text) else text


def _die(msg: str, code: int) -> None:
    print(f"work_report_gather: {msg}", file=sys.stderr)
    sys.exit(code)


# --- Task membership --------------------------------------------------------


@dataclass(frozen=True)
class TaskRow:
    task_id: str
    col_id: str
    board_idx: int
    status: str
    priority: str
    effort: str
    pending_children: int
    remaining_items: int
    path: str
    filename: str


def _work_counts(metadata: dict, status: str, filename: str) -> tuple[int, int]:
    """(pending_children, remaining_items) under the pinned type policy.

    A leaf contributes one unit of remaining work unless it is already Done.
    `children_to_implement` is trusted only when it is a list or None — any
    other type is user error that would otherwise miscount silently
    (len("t1_2") == 4) or crash (len(None)).
    """
    leaf = (0, 0 if status == "Done" else 1)
    if "children_to_implement" not in metadata:
        return leaf
    raw = metadata["children_to_implement"]
    if raw is None:
        return 0, 0
    if isinstance(raw, list):
        return len(raw), len(raw)
    print(
        f"work_report_gather: {filename}: children_to_implement is "
        f"{type(raw).__name__}, expected a list — counting the task as a leaf",
        file=sys.stderr,
    )
    return leaf


def scan_tasks() -> list[TaskRow]:
    """Top-level parent tasks, ordered exactly as the board orders a column.

    Mirrors TaskManager.load_tasks/get_column_tasks: only `<task_dir>/t*.md`
    (no archived, no children), phantom stubs dropped using the board's own
    BOARD_KEYS, no status filter, and the (board_idx, filename) sort key the
    board now uses too.
    """
    rows: list[TaskRow] = []
    # Deliberately an unsorted glob, exactly like TaskManager.load_tasks: the
    # explicit sort key below is the only thing that establishes order, so a
    # regression in it cannot be masked by an incidentally-sorted scan.
    for found in glob.glob(str(task_dir() / "*.md")):
        path = Path(found)
        match = TASK_FILE_RE.match(path.name)
        if not match:
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            parsed = parse_frontmatter(raw)
        except Exception:
            # Board parity: Task.load() swallows any parse failure and leaves
            # the task metadata-empty, so a malformed top-level file is simply
            # absent from the board. Letting the YAML error escape here would
            # abort the whole run and emit no protocol line at all.
            parsed = None
        metadata = parsed[0] if parsed else {}
        if not metadata or set(metadata.keys()) <= set(BOARD_KEYS):
            continue  # phantom stub or unparseable — invisible on the board too

        col_raw = metadata.get("boardcol", UNORDERED_ID)
        # A non-string boardcol matches no column on the board either; "" can
        # never equal a validated column id, so such a task stays unreportable.
        col_id = col_raw if isinstance(col_raw, str) else ""
        status = _enum_field(metadata.get("status"))
        pending, remaining = _work_counts(metadata, status, path.name)
        rows.append(
            TaskRow(
                task_id=match.group(1),
                col_id=col_id,
                board_idx=normalize_board_idx(metadata.get("boardidx", 0)),
                status=status,
                priority=_enum_field(metadata.get("priority")),
                effort=_enum_field(metadata.get("effort")),
                pending_children=pending,
                remaining_items=remaining,
                path=str(path),
                filename=path.name,
            )
        )
    rows.sort(key=lambda r: (r.board_idx, r.filename))
    return rows


# --- Board columns ----------------------------------------------------------


def load_columns() -> tuple[list[str], dict[str, str]]:
    """(configured column ids in board order, {col_id: title}).

    A `column_order` entry with no matching `columns` definition is dropped —
    the board's renderer skips it too, so it is not a reportable column.
    """
    config = load_layered_config(
        str(metadata_dir() / "board_config.json"),
        defaults={"columns": DEFAULT_COLUMNS, "column_order": DEFAULT_ORDER},
    )
    # `.get(key, default)`, not `or default`: a board deliberately configured
    # with no columns must stay empty here, exactly as TaskManager.load_metadata
    # leaves it — falling back on a falsy-but-present [] would invent the stock
    # Now/Next/Backlog board the user never sees.
    columns = config.get("columns", DEFAULT_COLUMNS)
    order = config.get("column_order", DEFAULT_ORDER)

    titles: dict[str, str] = {}
    for entry in columns:
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            titles[entry["id"]] = str(entry.get("title", entry["id"]))

    configured = [cid for cid in order if isinstance(cid, str) and cid in titles]
    for cid in configured:
        if _has_record_breaking(cid):
            _die(
                f"board_config.json: column id {cid!r} contains '|', CR or LF, "
                "which cannot round-trip through the report protocol",
                EXIT_INFRA,
            )
    titles[UNORDERED_ID] = UNORDERED_TITLE
    return configured, titles


# --- Velocity estimation (swappable seam) -----------------------------------
#
# A model turns completion history into generic buckets plus rate_for(day).
# rate_for is the ONLY thing the projection walk consumes, and the walk lives
# in project_completion() below — so a model supplies rates, never policy. It
# never decides the stop condition, the bound, or the insufficient_data rule.
# Adding a model is one class plus one VELOCITY_MODELS entry; emission and
# projection stay untouched.


@dataclass(frozen=True)
class VelocityBucket:
    bucket_id: str          # pipe-free, model-defined ("1".."7", "all", ...)
    observed_units: int     # denominator: units observed, not units with work
    completed_count: int
    avg_per_unit: float
    bucket_label: str       # free text, emitted LAST


@dataclass(frozen=True)
class VelocityEstimate:
    buckets: tuple[VelocityBucket, ...]
    bucket_for_day: Callable[[date], str]

    def rate_for(self, day: date) -> float:
        """Expected completions on `day`."""
        wanted = self.bucket_for_day(day)
        for bucket in self.buckets:
            if bucket.bucket_id == wanted:
                return bucket.avg_per_unit
        return 0.0

    def has_signal(self) -> bool:
        return any(bucket.avg_per_unit > 0 for bucket in self.buckets)

    def total_completed(self) -> int:
        """Completions the estimate rests on — the projection's confidence basis."""
        return sum(bucket.completed_count for bucket in self.buckets)


def _window_dates(now: date, window_days: int) -> list[date]:
    """The `window_days` calendar days ending at `now`, inclusive."""
    start = now - timedelta(days=window_days - 1)
    return [start + timedelta(days=offset) for offset in range(window_days)]


class DayOfWeekVelocity:
    """Average completions per weekday — the default.

    Days with no completions stay in the denominator, so a habitually quiet
    Monday lowers the Monday average rather than vanishing from it. That is
    what makes the projection walk track a real weekly rhythm.
    """

    model_id = "dow"
    model_label = "Average completions per weekday"

    def estimate(self, daily_counts, now: date, window_days: int) -> VelocityEstimate:
        observed: Counter = Counter()
        completed: Counter = Counter()
        for day in _window_dates(now, window_days):
            dow = day.isoweekday()
            observed[dow] += 1
            completed[dow] += daily_counts.get(day, 0)
        buckets = tuple(
            VelocityBucket(
                bucket_id=str(dow),
                observed_units=observed[dow],
                completed_count=completed[dow],
                avg_per_unit=(completed[dow] / observed[dow]) if observed[dow] else 0.0,
                bucket_label=DAY_NAMES[dow],
            )
            for dow in range(1, 8)
        )
        return VelocityEstimate(buckets, lambda day: str(day.isoweekday()))


class FlatVelocity:
    """One blended rate across the whole window — the same rate every day."""

    model_id = "flat"
    model_label = "Average completions per day"

    def estimate(self, daily_counts, now: date, window_days: int) -> VelocityEstimate:
        days = _window_dates(now, window_days)
        total = sum(daily_counts.get(day, 0) for day in days)
        bucket = VelocityBucket(
            bucket_id="all",
            observed_units=len(days),
            completed_count=total,
            avg_per_unit=(total / len(days)) if days else 0.0,
            bucket_label="All days",
        )
        return VelocityEstimate((bucket,), lambda day: "all")


VELOCITY_MODELS = {
    model.model_id: model for model in (DayOfWeekVelocity(), FlatVelocity())
}


def project_completion(
    remaining_total: int, estimate: VelocityEstimate, now: date
) -> tuple[date | None, int | None]:
    """Walk forward from `now` (inclusive) burning down `remaining_total`.

    Returns (projected_date, days_ahead), or (None, None) when the history is
    too thin to project from, there is no throughput signal at all, or the walk
    exceeds PROJECTION_MAX_DAYS.

    The floor matters as much as the walk: a single in-window completion is
    enough to make `has_signal()` true, and extrapolating a delivery date from
    one data point produces a confident-looking number with nothing behind it.
    """
    if remaining_total <= 0:
        return now, 0
    if estimate.total_completed() < PROJECTION_MIN_COMPLETIONS:
        return None, None
    if not estimate.has_signal():
        return None, None
    remaining = float(remaining_total)
    for offset in range(PROJECTION_MAX_DAYS):
        day = now + timedelta(days=offset)
        remaining -= estimate.rate_for(day)
        if remaining <= 0:
            return day, offset
    return None, None


# --- Emission ---------------------------------------------------------------


def _fmt_avg(value: float) -> str:
    text = f"{value:.2f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def emit_velocity_block(
    out, rows: list[TaskRow], model, now: date, window_days: int, project: bool
) -> None:
    """VELOCITY_MODEL / VELOCITY, and PROJECTION only when explicitly asked for.

    History comes from the same task tree membership does: stats_data resolves
    its archive through the shared TASK_DIR resolver, so `project_root=None`
    cannot pick up a different project's completions.
    """
    daily_counts = collect_stats(now, 1, project_root=None).daily_counts
    estimate = model.estimate(daily_counts, now, window_days)
    window = _window_dates(now, window_days)

    print(
        f"VELOCITY_MODEL:{model.model_id}|{window_days}|{window[0].isoformat()}"
        f"|{window[-1].isoformat()}|{_free_text(model.model_label)}",
        file=out,
    )
    for bucket in estimate.buckets:
        if _has_record_breaking(bucket.bucket_id):
            _die(
                f"velocity model {model.model_id!r} produced a bucket id "
                f"{bucket.bucket_id!r} containing '|', CR or LF",
                EXIT_INFRA,
            )
        print(
            f"VELOCITY:{bucket.bucket_id}|{bucket.observed_units}"
            f"|{bucket.completed_count}|{_fmt_avg(bucket.avg_per_unit)}"
            f"|{_free_text(bucket.bucket_label)}",
            file=out,
        )

    if not project:
        return

    remaining_total = sum(row.remaining_items for row in rows)
    basis = estimate.total_completed()
    projected, days_ahead = project_completion(remaining_total, estimate, now)
    if projected is None:
        print(
            f"PROJECTION:{remaining_total}|none|insufficient_data"
            f"|{basis}|{PROJECTION_CAVEAT}",
            file=out,
        )
    else:
        print(
            f"PROJECTION:{remaining_total}|{projected.isoformat()}|{days_ahead}"
            f"|{basis}|{PROJECTION_CAVEAT}",
            file=out,
        )


def emit_errors(out, errors: list[str]) -> None:
    for error in errors:
        print(f"ERROR:{error}", file=out)


# --- CLI --------------------------------------------------------------------


def _parse_csv(raw: str, flag: str, strip_t: bool = False) -> list[str]:
    """Split a csv argument, normalize, and dedup preserving first occurrence."""
    values: list[str] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if _has_record_breaking(part):
            _die(f"{flag}: value contains '|', CR or LF", EXIT_USAGE)
        if strip_t and len(part) > 1 and part[0] == "t" and part[1].isdigit():
            part = part[1:]
        if part not in values:
            values.append(part)
    return values


def _parse_now(raw: str | None) -> date:
    if not raw:
        return date.today()
    # Date-only on purpose: the history seam subtracts date objects, and
    # `datetime - date` raises. Accepting a timestamp would either crash or
    # silently discard the time component.
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        _die(f"--now: expected YYYY-MM-DD, got {raw!r}", EXIT_USAGE)
    raise AssertionError("unreachable")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aitask_work_report_gather.sh",
        description="Deterministic report input for the work-report skill.",
    )
    parser.add_argument(
        "--list-columns",
        action="store_true",
        help="enumerate reportable columns and exit (no task or velocity output)",
    )
    parser.add_argument("--columns", help="comma-separated column ids to report on")
    parser.add_argument("--tasks", help="comma-separated task ids (order is significant)")
    parser.add_argument("--now", help="freeze 'today' as YYYY-MM-DD (testing seam)")
    parser.add_argument(
        "--velocity-window",
        type=int,
        default=DEFAULT_VELOCITY_WINDOW,
        help=f"lookback window in days (default {DEFAULT_VELOCITY_WINDOW})",
    )
    parser.add_argument(
        "--velocity-model",
        default=DayOfWeekVelocity.model_id,
        help="velocity estimator id (default %(default)s)",
    )
    parser.add_argument(
        "--project",
        action="store_true",
        help=(
            "also emit a projected completion date. Off by default: the models "
            "count tasks, so a projection ignores task size, blockers and "
            "capacity, and is an extrapolation of past throughput rather than "
            "a delivery estimate"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = sys.stdout

    configured, titles = load_columns()
    rows = scan_tasks()

    if args.list_columns:
        if args.columns or args.tasks:
            _die("--list-columns cannot be combined with --columns/--tasks", EXIT_USAGE)
        listed = list(configured)
        if any(row.col_id == UNORDERED_ID for row in rows):
            listed.insert(0, UNORDERED_ID)
        for col_id in listed:
            print(f"COLUMN:{col_id}|{_free_text(titles[col_id])}", file=out)
        return 0

    if not args.columns:
        _die("--columns is required (or use --list-columns)", EXIT_USAGE)
    if args.velocity_window < 1:
        _die("--velocity-window: expected a positive number of days", EXIT_USAGE)
    if args.velocity_model not in VELOCITY_MODELS:
        _die(
            f"--velocity-model: unknown model {args.velocity_model!r} "
            f"(registered: {', '.join(sorted(VELOCITY_MODELS))})",
            EXIT_USAGE,
        )
    model = VELOCITY_MODELS[args.velocity_model]
    now = _parse_now(args.now or os.environ.get("WORK_REPORT_NOW"))

    # Stage 1 — columns. Later stages are meaningless against an invalid
    # selection, so a failure here is emitted alone (fail-closed, staged).
    selected = _parse_csv(args.columns, "--columns")
    known = set(configured) | {UNORDERED_ID}
    unknown = [f"unknown_column:{cid}" for cid in selected if cid not in known]
    if unknown:
        emit_errors(out, unknown)
        return 0

    # Canonical column order: unordered first (the board prepends it), then
    # configured order.
    ordered_cols = [cid for cid in selected if cid == UNORDERED_ID]
    ordered_cols += [cid for cid in configured if cid in selected]

    by_column: dict[str, list[TaskRow]] = {cid: [] for cid in ordered_cols}
    for row in rows:
        if row.col_id in by_column:
            by_column[row.col_id].append(row)
    ordered_rows = [row for cid in ordered_cols for row in by_column[cid]]

    # Stage 2 — task membership.
    task_ids = _parse_csv(args.tasks, "--tasks", strip_t=True) if args.tasks else None
    if task_ids is not None:
        all_ids = {row.task_id for row in rows}
        selectable = {row.task_id for row in ordered_rows}
        errors = []
        for tid in task_ids:
            if tid not in all_ids:
                errors.append(f"unknown_task:{tid}")
            elif tid not in selectable:
                errors.append(f"task_not_in_selected_columns:{tid}")
        if errors:
            emit_errors(out, errors)
            return 0

        # Stage 3 — the reviewed sequence must still match board order.
        wanted = set(task_ids)
        canonical = [row.task_id for row in ordered_rows if row.task_id in wanted]
        if canonical != task_ids:
            emit_errors(out, [f"task_order_changed:{','.join(canonical)}"])
            return 0

        ordered_rows = [row for row in ordered_rows if row.task_id in wanted]

    if not ordered_rows:
        print("NO_TASKS", file=out)
    else:
        for col_id in ordered_cols:
            print(f"COLUMN:{col_id}|{_free_text(titles[col_id])}", file=out)
        for col_id in ordered_cols:
            for row in ordered_rows:
                if row.col_id != col_id:
                    continue
                print(
                    f"TASK:{row.col_id}|{row.task_id}|{row.board_idx}|{row.status}"
                    f"|{row.priority}|{row.effort}|{row.pending_children}"
                    f"|{row.remaining_items}|{_free_text(row.path)}",
                    file=out,
                )

    emit_velocity_block(
        out, ordered_rows, model, now, args.velocity_window, args.project
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
