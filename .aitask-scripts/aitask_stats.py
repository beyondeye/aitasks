#!/usr/bin/env python3
"""Calculate and display AI task completion statistics.

Supports text output and CSV export. Pure data extraction lives in
`stats/stats_data.py` and is shared with the stats TUI (`ait stats-tui`).
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys

# Make the stats package importable regardless of how this script is launched.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Sequence

from stats.stats_data import (
    AGENT_DISPLAY_NAMES,
    ARCHIVE_DIR,
    DAY_FULL_NAMES,
    DAY_NAMES,
    ImplementationInfo,
    LEGACY_IMPLEMENTED_WITH_CLI_IDS,
    StatsData,
    TASK_DIR,
    TASK_TYPES_FILE,
    TaskRecord,
    UsageModelEntry,
    UsageRankingData,
    VerifiedModelEntry,
    VerifiedRankingData,
    WINDOW_KEYS,
    bucket_avg,
    build_chart_title,
    canonical_model_id,
    chart_totals,
    codeagent_display_name,
    collect_stats,
    get_valid_task_types,
    is_child_task,
    iter_archived_markdown_files,
    load_model_cli_ids,
    load_usage_rankings,
    load_verified_rankings,
    model_display_from_cli_id,
    model_key_from_cli_id,
    normalize_implemented_with,
    parse_completed_date,
    parse_frontmatter,
    parse_labels,
    recent_aggregate,
    slugify_key,
    sorted_weekly_keys,
    titleize_words,
    week_offset_for,
    week_start_display_name,
    week_start_for,
)

# Re-exports (kept at module scope so existing tests and call sites that
# reference `aitask_stats.X` continue to work after the data layer split).
__all__ = [
    "AGENT_DISPLAY_NAMES",
    "ARCHIVE_DIR",
    "DAY_FULL_NAMES",
    "DAY_NAMES",
    "ImplementationInfo",
    "LEGACY_IMPLEMENTED_WITH_CLI_IDS",
    "StatsData",
    "TASK_DIR",
    "TASK_TYPES_FILE",
    "TaskRecord",
    "UsageModelEntry",
    "UsageRankingData",
    "VerifiedModelEntry",
    "VerifiedRankingData",
    "WINDOW_KEYS",
    "bucket_avg",
    "build_chart_title",
    "canonical_model_id",
    "chart_totals",
    "codeagent_display_name",
    "collect_stats",
    "get_valid_task_types",
    "is_child_task",
    "iter_archived_markdown_files",
    "load_model_cli_ids",
    "load_usage_rankings",
    "load_verified_rankings",
    "model_display_from_cli_id",
    "model_key_from_cli_id",
    "normalize_implemented_with",
    "parse_completed_date",
    "parse_frontmatter",
    "parse_labels",
    "recent_aggregate",
    "slugify_key",
    "sorted_weekly_keys",
    "titleize_words",
    "week_offset_for",
    "week_start_display_name",
    "week_start_for",
]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    def parse_days_arg(raw: str) -> int:
        # Be tolerant to accidental trailing dot, e.g. "--days 7."
        value = raw.strip()
        if value.endswith("."):
            value = value[:-1]
        try:
            parsed = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"invalid int value: '{raw}'") from exc
        if parsed <= 0:
            raise argparse.ArgumentTypeError("days must be > 0")
        return parsed

    parser = argparse.ArgumentParser(
        prog="aitask_stats.sh",
        description="Calculate and display AI task completion statistics.",
    )
    parser.add_argument(
        "-d",
        "--days",
        type=parse_days_arg,
        default=7,
        help="Show daily breakdown for last N days",
    )
    parser.add_argument(
        "-w",
        "--week-start",
        default="mon",
        help="First day of week (e.g., mon, sun, tue). Default: Monday",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show individual task IDs in daily breakdown"
    )
    parser.add_argument(
        "--csv",
        nargs="?",
        const="aitask_stats.csv",
        default=None,
        metavar="FILE",
        help="Export raw data to CSV (default: aitask_stats.csv)",
    )
    return parser.parse_args(argv)


def resolve_week_start(value: str) -> int:
    value = (value or "").strip().lower()
    if not value:
        return 1

    day_names = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    matches = [idx + 1 for idx, name in enumerate(day_names) if name.startswith(value)]

    if len(matches) == 1:
        return matches[0]
    if len(matches) == 0:
        print(
            f"Warning: '{value}' does not match any day of the week. Using default (Monday).",
            file=sys.stderr,
        )
    else:
        names = ", ".join(day_names[m - 1] for m in matches)
        print(
            f"Warning: '{value}' is ambiguous (matches: {names}). Using default (Monday).",
            file=sys.stderr,
        )
    return 1


def avg(num: int, denom: int) -> str:
    if denom <= 0:
        return "0.0"
    return f"{num / float(denom):.1f}"


def get_type_display_name(raw: str) -> str:
    mapping = {
        "feature": "Features",
        "bug": "Bug Fixes",
        "refactor": "Refactors",
        "documentation": "Documentation",
        "performance": "Performance",
        "style": "Style Changes",
        "test": "Tests",
        "chore": "Chores",
        "parent": "Parent Tasks",
        "child": "Child Tasks",
    }
    return mapping.get(raw, raw.capitalize())


def render_text_report(data: StatsData, days: int, verbose: bool, week_start_dow: int, today: date) -> str:
    out = io.StringIO()

    print("## Task Completion Statistics", file=out)
    print(file=out)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", file=out)
    print(file=out)

    print("### Summary", file=out)
    print("| Metric                    | Count |", file=out)
    print("|---------------------------|-------|", file=out)
    print(f"| Total Tasks Completed     | {data.total_tasks:<5} |", file=out)
    print(f"| Completed (Last 7 days)   | {data.tasks_7d:<5} |", file=out)
    print(f"| Completed (Last 30 days)  | {data.tasks_30d:<5} |", file=out)
    print(file=out)

    print(f"### Daily Completions (Last {days} Days)", file=out)
    if verbose:
        print("| Date       | Day | Count | Tasks |", file=out)
        print("|------------|-----|-------|-------|", file=out)
    else:
        print("| Date       | Day | Count |", file=out)
        print("|------------|-----|-------|", file=out)

    for i in range(days):
        d = today - timedelta(days=i)
        count = data.daily_counts.get(d, 0)
        if verbose:
            tasks = ",".join(data.daily_tasks.get(d, []))
            print(f"| {d.isoformat()} | {DAY_NAMES[d.isoweekday()]:<3} | {count:<5} | {tasks} |", file=out)
        else:
            print(f"| {d.isoformat()} | {DAY_NAMES[d.isoweekday()]:<3} | {count:<5} |", file=out)
    print(file=out)

    print("### Average Completions by Day of Week", file=out)
    print("| Day       | This Week | Last 30d Avg | All-time Avg |", file=out)
    print("|-----------|-----------|--------------|--------------|", file=out)

    dow_occurrences_30d = Counter((today - timedelta(days=i)).isoweekday() for i in range(30))

    first_date = min(data.daily_counts.keys()) if data.daily_counts else today
    total_days = (today - first_date).days + 1
    total_weeks = max(1, (total_days + 6) // 7)
    current_dow = today.isoweekday()

    for j in range(7):
        dow = ((week_start_dow - 1 + j) % 7) + 1
        this_week = data.dow_counts_thisweek.get(dow, 0)
        count_30d = data.dow_counts_30d.get(dow, 0)
        count_total = data.dow_counts_total.get(dow, 0)
        occurrences = dow_occurrences_30d.get(dow, 1)

        thisweek_display = str(this_week)
        today_offset = (current_dow - week_start_dow + 7) % 7
        day_offset = (dow - week_start_dow + 7) % 7
        if day_offset > today_offset:
            thisweek_display = "-"

        print(
            f"| {DAY_FULL_NAMES[dow]:<9} | {thisweek_display:<9} | {avg(count_30d, occurrences):<12} | {avg(count_total, total_weeks):<12} |",
            file=out,
        )
    print(file=out)

    print("### Completions by Label - Weekly Trend (Last 4 Weeks)", file=out)
    print("| Label          | Total | W-3 | W-2 | W-1 | This Week |", file=out)
    print("|----------------|-------|-----|-----|-----|-----------|", file=out)

    sorted_labels = sorted(data.all_labels, key=lambda lbl: (-data.label_counts_total.get(lbl, 0), lbl))
    for label in sorted_labels:
        print(
            f"| {label:<14} | {data.label_counts_total.get(label, 0):<5} | "
            f"{data.label_week_counts.get((label, 3), 0):<3} | {data.label_week_counts.get((label, 2), 0):<3} | "
            f"{data.label_week_counts.get((label, 1), 0):<3} | {data.label_week_counts.get((label, 0), 0):<9} |",
            file=out,
        )
    print(file=out)

    print("### Label Avg by Day of Week (Last 30 Days)", file=out)
    header_days = [DAY_NAMES[((week_start_dow - 1 + j) % 7) + 1] for j in range(7)]
    print("| Label        | " + " | ".join(header_days) + " |", file=out)
    print("|--------------|" + "-----|" * 7, file=out)

    for label in sorted_labels:
        cells = []
        for j in range(7):
            dow = ((week_start_dow - 1 + j) % 7) + 1
            count = data.label_dow_counts_30d.get((label, dow), 0)
            occurrences = dow_occurrences_30d.get(dow, 1)
            cells.append(f"{avg(count, occurrences):<3}")
        print(f"| {label:<12} | " + " | ".join(cells) + " |", file=out)
    print(file=out)

    print("### By Task Type - Weekly Trend (Last 4 Weeks)", file=out)
    print("| Type           | Total | W-3 | W-2 | W-1 | This Week |", file=out)
    print("|----------------|-------|-----|-----|-----|-----------|", file=out)

    for t in ["parent", "child"] + get_valid_task_types():
        total = sum(data.type_week_counts.get((t, wk), 0) for wk in range(4))
        print(
            f"| {get_type_display_name(t):<14} | {total:<5} | {data.type_week_counts.get((t, 3), 0):<3} | "
            f"{data.type_week_counts.get((t, 2), 0):<3} | {data.type_week_counts.get((t, 1), 0):<3} | "
            f"{data.type_week_counts.get((t, 0), 0):<9} |",
            file=out,
        )
    print(file=out)

    print("### By Issue Type per Label - Weekly Trend (Last 4 Weeks)", file=out)
    print("| Label        | Type    | Total | W-3 | W-2 | W-1 | This Week |", file=out)
    print("|--------------|---------|-------|-----|-----|-----|-----------|", file=out)

    for label in sorted_labels:
        if label == "(unlabeled)":
            continue
        for issue_type in get_valid_task_types():
            total = sum(data.label_type_week_counts.get((label, issue_type, wk), 0) for wk in range(4))
            if total == 0:
                continue
            print(
                f"| {label:<12} | {issue_type.capitalize():<7} | {total:<5} | "
                f"{data.label_type_week_counts.get((label, issue_type, 3), 0):<3} | "
                f"{data.label_type_week_counts.get((label, issue_type, 2), 0):<3} | "
                f"{data.label_type_week_counts.get((label, issue_type, 1), 0):<3} | "
                f"{data.label_type_week_counts.get((label, issue_type, 0), 0):<9} |",
                file=out,
            )
    print(file=out)

    print("### By Code Agent - Weekly Trend (Last 4 Weeks)", file=out)
    print("| Code Agent   | Total | W-3 | W-2 | W-1 | This Week |", file=out)
    print("|--------------|-------|-----|-----|-----|-----------|", file=out)

    for codeagent in sorted_weekly_keys(data.all_codeagents, data.codeagent_week_counts, codeagent_display_name):
        total = sum(data.codeagent_week_counts.get((codeagent, wk), 0) for wk in range(4))
        print(
            f"| {codeagent_display_name(codeagent):<12} | {total:<5} | "
            f"{data.codeagent_week_counts.get((codeagent, 3), 0):<3} | "
            f"{data.codeagent_week_counts.get((codeagent, 2), 0):<3} | "
            f"{data.codeagent_week_counts.get((codeagent, 1), 0):<3} | "
            f"{data.codeagent_week_counts.get((codeagent, 0), 0):<9} |",
            file=out,
        )
    print(file=out)

    print("### By LLM Model - Weekly Trend (Last 4 Weeks)", file=out)
    print("| LLM Model    | Total | W-3 | W-2 | W-1 | This Week |", file=out)
    print("|--------------|-------|-----|-----|-----|-----------|", file=out)

    for model in sorted_weekly_keys(
        data.all_models, data.model_week_counts, lambda key: data.model_display_names.get(key, "Unknown")
    ):
        total = sum(data.model_week_counts.get((model, wk), 0) for wk in range(4))
        print(
            f"| {data.model_display_names.get(model, 'Unknown'):<12} | {total:<5} | "
            f"{data.model_week_counts.get((model, 3), 0):<3} | "
            f"{data.model_week_counts.get((model, 2), 0):<3} | "
            f"{data.model_week_counts.get((model, 1), 0):<3} | "
            f"{data.model_week_counts.get((model, 0), 0):<9} |",
            file=out,
        )
    print(file=out)

    return out.getvalue()


def render_verified_rankings(vdata: VerifiedRankingData) -> str:
    """Render verified model score rankings as a text report section."""
    if not vdata.operations:
        return ""

    out = io.StringIO()
    print("### Verified Model Rankings\n", file=out)

    for op in vdata.operations:
        op_data = vdata.by_window.get(op, {})
        ap = op_data.get("all_providers", {})
        at_entries = ap.get("all_time", [])
        if not at_entries:
            continue

        print(f"#### {op}\n", file=out)

        # Build month lookup for all_providers
        mo_entries = ap.get("month", [])
        mo_lookup: Dict[str, VerifiedModelEntry] = {e.display_name: e for e in mo_entries}

        # Main table: all_providers all_time top 5
        print("| Model | Score | Runs | This month |", file=out)
        print("|-------|-------|------|------------|", file=out)
        for entry in at_entries[:5]:
            mo = mo_lookup.get(entry.display_name)
            mo_cell = f"{mo.score} ({mo.runs})" if mo else "-"
            print(f"| {entry.display_name} | {entry.score} | {entry.runs} | {mo_cell} |", file=out)
        print(file=out)

        # Per-provider breakdown (only when >1 provider has data)
        providers_with_data = [
            p for p in sorted(op_data.keys())
            if p != "all_providers" and op_data[p].get("all_time")
        ]
        if len(providers_with_data) > 1:
            print("By provider:", file=out)
            for prov in providers_with_data:
                prov_display = AGENT_DISPLAY_NAMES.get(prov, prov)
                prov_entries = op_data[prov]["all_time"][:3]
                parts = [f"{e.display_name} {e.score} ({e.runs} runs)" for e in prov_entries]
                print(f"  {prov_display}: {' · '.join(parts)}", file=out)
            print(file=out)

    return out.getvalue()


def write_csv(path: Path, rows: Sequence[Sequence[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "date",
                "day_of_week",
                "week_offset",
                "task_id",
                "labels",
                "issue_type",
                "task_type",
                "implemented_with",
                "codeagent",
                "llm_model",
            ]
        )
        for row in sorted(rows, key=lambda x: x[0], reverse=True):
            writer.writerow(row)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)

    if not ARCHIVE_DIR.exists():
        print(f"No archived tasks found in {ARCHIVE_DIR}")
        return 0

    week_start_dow = resolve_week_start(args.week_start)
    today = date.today()
    data = collect_stats(today=today, week_start_dow=week_start_dow)

    if data.total_tasks == 0:
        print("No completed tasks found.")
        return 0

    report = render_text_report(data, days=args.days, verbose=args.verbose, week_start_dow=week_start_dow, today=today)
    print(report, end="")

    vdata = load_verified_rankings()
    if vdata.operations:
        print(render_verified_rankings(vdata), end="")

    if args.csv is not None:
        csv_path = Path(args.csv)
        write_csv(csv_path, data.csv_rows)
        print(f"CSV exported to: {csv_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
