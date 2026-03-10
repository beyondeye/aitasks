#!/usr/bin/env python3
"""Calculate and display AI task completion statistics.

Supports text output, CSV export, and optional interactive terminal plots
(when plotext is installed).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import shutil
import sys
import tarfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

TASK_DIR = Path("aitasks")
ARCHIVE_DIR = TASK_DIR / "archived"
ARCHIVE_TAR = ARCHIVE_DIR / "old.tar.gz"
TASK_TYPES_FILE = TASK_DIR / "metadata" / "task_types.txt"

DAY_NAMES = ["", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_FULL_NAMES = [
    "",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

AGENT_DISPLAY_NAMES = {
    "claudecode": "Claude Code",
    "codex": "Codex",
    "geminicli": "Gemini CLI",
    "opencode": "OpenCode",
    "unknown": "Unknown",
}

# Historic values found in archived tasks before the wrapper settled on the
# current normalized agent/model names.
LEGACY_IMPLEMENTED_WITH_CLI_IDS = {
    "codex/gpt-5": "gpt-5",
    "codex/gpt5": "gpt-5",
    "opencode/openai_gpt_5_3_codex": "openai/gpt-5.3-codex",
    "opencode/zen_gpt_5_4": "gpt-5.4",
}


@dataclass
class TaskRecord:
    completed_date: date
    task_id: str
    labels: List[str]
    issue_type: str
    task_type: str


@dataclass
class StatsData:
    total_tasks: int
    tasks_7d: int
    tasks_30d: int
    daily_counts: Counter
    daily_tasks: Dict[date, List[str]]
    dow_counts_thisweek: Counter
    dow_counts_30d: Counter
    dow_counts_total: Counter
    label_counts_total: Counter
    label_week_counts: Counter
    label_dow_counts_30d: Counter
    type_week_counts: Counter
    label_type_week_counts: Counter
    codeagent_week_counts: Counter
    model_week_counts: Counter
    all_labels: set
    all_codeagents: set
    all_models: set
    codeagent_display_names: Dict[str, str]
    model_display_names: Dict[str, str]
    csv_rows: List[List[str]]


@dataclass(frozen=True)
class ImplementationInfo:
    raw: str
    codeagent_key: str
    codeagent_display: str
    model_key: str
    model_display: str


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
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Show interactive terminal charts (requires optional plotext)",
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


def week_start_for(d: date, week_start_dow: int) -> date:
    offset = (d.isoweekday() - week_start_dow + 7) % 7
    return d - timedelta(days=offset)


def week_offset_for(completed: date, today: date, week_start_dow: int) -> int:
    comp = week_start_for(completed, week_start_dow)
    curr = week_start_for(today, week_start_dow)
    if comp > curr:
        return -1
    return (curr - comp).days // 7


def parse_frontmatter(content: str) -> Dict[str, str]:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    result: Dict[str, str] = {}
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def parse_labels(raw: Optional[str]) -> List[str]:
    if not raw:
        return ["(unlabeled)"]

    cleaned = raw.strip()
    if cleaned.startswith("[") and cleaned.endswith("]"):
        cleaned = cleaned[1:-1]

    labels = [part.strip() for part in cleaned.split(",") if part.strip()]
    return labels if labels else ["(unlabeled)"]


def parse_completed_date(frontmatter: Dict[str, str]) -> Optional[date]:
    completed_at = frontmatter.get("completed_at", "")
    status = frontmatter.get("status", "")

    if not completed_at and status in {"Done", "Completed"}:
        completed_at = frontmatter.get("updated_at", "")

    if not completed_at:
        return None

    date_str = completed_at[:10]
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        return None


def load_model_cli_ids() -> Dict[Tuple[str, str], str]:
    result: Dict[Tuple[str, str], str] = {}
    metadata_dir = TASK_DIR / "metadata"

    for agent in ("claudecode", "codex", "geminicli", "opencode"):
        path = metadata_dir / f"models_{agent}.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        for model in payload.get("models", []):
            name = model.get("name")
            cli_id = model.get("cli_id")
            if isinstance(name, str) and isinstance(cli_id, str) and name and cli_id:
                result[(agent, name)] = cli_id

    return result


def canonical_model_id(cli_id: str) -> str:
    if "/" in cli_id:
        cli_id = cli_id.split("/", 1)[1]
    cli_id = re.sub(r"-preview$", "", cli_id)
    cli_id = re.sub(r"-\d{8}$", "", cli_id)
    return cli_id


def slugify_key(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.lower())).strip("_") or "unknown"


def titleize_words(value: str) -> str:
    parts = re.split(r"[-_]+", value)
    return " ".join(part.upper() if part in {"gpt", "glm"} else part.capitalize() for part in parts if part)


def model_key_from_cli_id(cli_id: str) -> str:
    value = canonical_model_id(cli_id)

    match = re.match(r"^gpt-([0-9]+)(?:\.([0-9]+))?(?:-(.+))?$", value)
    if match:
        major = match.group(1)
        minor = match.group(2)
        suffix = match.group(3)
        key = f"gpt{major}"
        if minor:
            key += f"_{minor}"
        if suffix:
            parts = suffix.split("-")
            key += parts[0]
            for part in parts[1:]:
                key += f"_{part}"
        return key

    match = re.match(r"^claude-([a-z]+)-([0-9]+)-([0-9]+)$", value)
    if match:
        family, major, minor = match.groups()
        return f"{family}{major}_{minor}"

    match = re.match(r"^claude-([0-9]+)-([0-9]+)-([a-z]+)$", value)
    if match:
        major, minor, family = match.groups()
        return f"{family}{major}_{minor}"

    match = re.match(r"^gemini-([0-9]+(?:\.[0-9]+)?)-([a-z]+)(?:-([a-z]+))?$", value)
    if match:
        version, model_type, suffix = match.groups()
        key = f"gemini{version.replace('.', '_')}{model_type}"
        if suffix and suffix != "preview":
            key += f"_{suffix}"
        return key

    return slugify_key(value)


def model_display_from_cli_id(cli_id: str) -> str:
    value = canonical_model_id(cli_id)

    match = re.match(r"^gpt-([0-9]+)(?:\.([0-9]+))?(?:-(.+))?$", value)
    if match:
        major = match.group(1)
        minor = match.group(2)
        suffix = match.group(3)
        label = f"GPT{major}"
        if minor:
            label += f".{minor}"
        if suffix:
            for part in suffix.split("-"):
                label += f"-{part.upper() if part in {'gpt', 'glm'} else part.capitalize()}"
        return label

    match = re.match(r"^claude-([a-z]+)-([0-9]+)-([0-9]+)$", value)
    if match:
        family, major, minor = match.groups()
        return f"{family.capitalize()} {major}.{minor}"

    match = re.match(r"^claude-([0-9]+)-([0-9]+)-([a-z]+)$", value)
    if match:
        major, minor, family = match.groups()
        return f"{family.capitalize()} {major}.{minor}"

    match = re.match(r"^gemini-([0-9]+(?:\.[0-9]+)?)-([a-z]+)(?:-([a-z]+))?$", value)
    if match:
        version, model_type, suffix = match.groups()
        label = f"Gemini {version} {model_type.capitalize()}"
        if suffix and suffix != "preview":
            label += f" {suffix.capitalize()}"
        return label

    return titleize_words(value)


def normalize_implemented_with(
    raw: Optional[str], model_cli_ids: Optional[Dict[Tuple[str, str], str]] = None
) -> ImplementationInfo:
    cleaned = (raw or "").strip()
    if not cleaned:
        return ImplementationInfo("", "unknown", AGENT_DISPLAY_NAMES["unknown"], "unknown", "Unknown")

    agent_match = re.match(r"^([a-z]+)/([A-Za-z0-9_.-]+)$", cleaned)
    if not agent_match:
        return ImplementationInfo(
            cleaned, "unknown", AGENT_DISPLAY_NAMES["unknown"], "unknown", "Unknown"
        )

    agent, model = agent_match.groups()
    codeagent_key = agent if agent in AGENT_DISPLAY_NAMES else "unknown"
    codeagent_display = AGENT_DISPLAY_NAMES.get(codeagent_key, AGENT_DISPLAY_NAMES["unknown"])

    if model_cli_ids is None:
        model_cli_ids = load_model_cli_ids()

    cli_id = model_cli_ids.get((agent, model))
    if cli_id is None:
        cli_id = LEGACY_IMPLEMENTED_WITH_CLI_IDS.get(cleaned)

    if cli_id is None:
        return ImplementationInfo(cleaned, codeagent_key, codeagent_display, "unknown", "Unknown")

    return ImplementationInfo(
        cleaned,
        codeagent_key,
        codeagent_display,
        model_key_from_cli_id(cli_id),
        model_display_from_cli_id(cli_id),
    )


def is_child_task(filename: str) -> bool:
    return bool(re.match(r"^t\d+_\d+_", filename))


def iter_archived_markdown_files() -> Iterable[Tuple[str, str]]:
    if ARCHIVE_DIR.exists():
        for path in sorted(ARCHIVE_DIR.glob("t*_*.md")):
            if is_child_task(path.name):
                continue
            try:
                yield path.name, path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

        for path in sorted(ARCHIVE_DIR.glob("t*/t*_*_*.md")):
            try:
                yield path.name, path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

    if ARCHIVE_TAR.exists():
        try:
            with tarfile.open(ARCHIVE_TAR, "r:gz") as tf:
                for member in tf.getmembers():
                    if not member.isfile() or not member.name.endswith(".md"):
                        continue
                    extracted = tf.extractfile(member)
                    if extracted is None:
                        continue
                    raw = extracted.read()
                    text = raw.decode("utf-8", errors="replace")
                    yield os.path.basename(member.name), text
        except (tarfile.TarError, OSError):
            return


def get_valid_task_types() -> List[str]:
    if TASK_TYPES_FILE.exists():
        try:
            types = sorted(
                {line.strip() for line in TASK_TYPES_FILE.read_text().splitlines() if line.strip()}
            )
            if types:
                return types
        except OSError:
            pass
    return ["bug", "feature", "refactor"]


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


def collect_stats(today: date, week_start_dow: int) -> StatsData:
    daily_counts: Counter = Counter()
    daily_tasks: Dict[date, List[str]] = defaultdict(list)
    dow_counts_thisweek: Counter = Counter()
    dow_counts_30d: Counter = Counter()
    dow_counts_total: Counter = Counter()
    label_counts_total: Counter = Counter()
    label_week_counts: Counter = Counter()
    label_dow_counts_30d: Counter = Counter()
    type_week_counts: Counter = Counter()
    label_type_week_counts: Counter = Counter()
    codeagent_week_counts: Counter = Counter()
    model_week_counts: Counter = Counter()
    all_labels: set = set()
    all_codeagents: set = set()
    all_models: set = set()
    codeagent_display_names: Dict[str, str] = {"unknown": AGENT_DISPLAY_NAMES["unknown"]}
    model_display_names: Dict[str, str] = {"unknown": "Unknown"}
    csv_rows: List[List[str]] = []
    model_cli_ids = load_model_cli_ids()

    total_tasks = 0
    tasks_7d = 0
    tasks_30d = 0
    curr_week_start = week_start_for(today, week_start_dow)

    for filename, content in iter_archived_markdown_files():
        frontmatter = parse_frontmatter(content)
        completed = parse_completed_date(frontmatter)
        if completed is None:
            continue

        issue_type = frontmatter.get("issue_type") or "feature"
        labels = parse_labels(frontmatter.get("labels"))
        implementation = normalize_implemented_with(frontmatter.get("implemented_with"), model_cli_ids)
        task_type = "child" if is_child_task(filename) else "parent"
        task_id = Path(filename).stem
        week_offset = week_offset_for(completed, today, week_start_dow)
        dow = completed.isoweekday()

        total_tasks += 1
        daily_counts[completed] += 1
        daily_tasks[completed].append(task_id)
        dow_counts_total[dow] += 1

        if week_start_for(completed, week_start_dow) == curr_week_start:
            dow_counts_thisweek[dow] += 1

        delta_days = (today - completed).days
        if 0 <= delta_days < 7:
            tasks_7d += 1
        if 0 <= delta_days < 30:
            tasks_30d += 1
            dow_counts_30d[dow] += 1

        for label in labels:
            all_labels.add(label)
            label_counts_total[label] += 1

            if 0 <= week_offset <= 3:
                label_week_counts[(label, week_offset)] += 1
                label_type_week_counts[(label, issue_type, week_offset)] += 1

            if 0 <= delta_days < 30:
                label_dow_counts_30d[(label, dow)] += 1

        if 0 <= week_offset <= 3:
            type_week_counts[(task_type, week_offset)] += 1
            type_week_counts[(issue_type, week_offset)] += 1
            codeagent_week_counts[(implementation.codeagent_key, week_offset)] += 1
            model_week_counts[(implementation.model_key, week_offset)] += 1
            all_codeagents.add(implementation.codeagent_key)
            all_models.add(implementation.model_key)
            codeagent_display_names[implementation.codeagent_key] = implementation.codeagent_display
            model_display_names[implementation.model_key] = implementation.model_display

        csv_rows.append(
            [
                completed.isoformat(),
                DAY_NAMES[dow],
                str(week_offset),
                task_id,
                ";".join(labels),
                issue_type,
                task_type,
                implementation.raw,
                implementation.codeagent_key,
                implementation.model_key,
            ]
        )

    return StatsData(
        total_tasks=total_tasks,
        tasks_7d=tasks_7d,
        tasks_30d=tasks_30d,
        daily_counts=daily_counts,
        daily_tasks=daily_tasks,
        dow_counts_thisweek=dow_counts_thisweek,
        dow_counts_30d=dow_counts_30d,
        dow_counts_total=dow_counts_total,
        label_counts_total=label_counts_total,
        label_week_counts=label_week_counts,
        label_dow_counts_30d=label_dow_counts_30d,
        type_week_counts=type_week_counts,
        label_type_week_counts=label_type_week_counts,
        codeagent_week_counts=codeagent_week_counts,
        model_week_counts=model_week_counts,
        all_labels=all_labels,
        all_codeagents=all_codeagents,
        all_models=all_models,
        codeagent_display_names=codeagent_display_names,
        model_display_names=model_display_names,
        csv_rows=csv_rows,
    )


def sorted_weekly_keys(keys: Iterable[str], weekly_counts: Counter, display_lookup) -> List[str]:
    return sorted(
        keys,
        key=lambda key: (
            -sum(weekly_counts.get((key, wk), 0) for wk in range(4)),
            display_lookup(key),
        ),
    )


def codeagent_display_name(key: str) -> str:
    return AGENT_DISPLAY_NAMES.get(key, titleize_words(key))


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


def chart_totals(
    weekly_counts: Counter,
    display_lookup,
    week_offsets: Sequence[int],
    limit: Optional[int] = None,
) -> Tuple[List[str], List[int]]:
    totals: Dict[str, int] = defaultdict(int)
    for (key, week_offset), count in weekly_counts.items():
        if week_offset in week_offsets:
            totals[key] += count

    items = sorted(totals.items(), key=lambda item: (-item[1], display_lookup(item[0])))
    if limit is not None and len(items) > limit:
        visible = items[: limit - 1]
        other_total = sum(count for _, count in items[limit - 1 :])
        if other_total:
            visible.append(("__other__", other_total))
        items = visible

    labels = ["Other" if key == "__other__" else display_lookup(key) for key, _ in items]
    values = [count for _, count in items]
    return labels, values


def week_start_display_name(week_start_dow: int) -> str:
    if 1 <= week_start_dow < len(DAY_FULL_NAMES):
        return DAY_FULL_NAMES[week_start_dow]
    return "Monday"


def build_chart_title(subject: str, timeframe: str, week_start_dow: Optional[int] = None) -> str:
    title = f"{subject} - {timeframe}"
    if week_start_dow is not None:
        title += f" (week starts {week_start_display_name(week_start_dow)})"
    return title


def chart_plot_size() -> Tuple[int, int]:
    size = shutil.get_terminal_size(fallback=(120, 40))
    width = max(60, size.columns)
    height = max(12, size.lines - 5)
    return width, height


def run_plot_summary(data: StatsData, days: int, today: date, week_start_dow: int) -> None:
    try:
        import plotext as plt  # type: ignore
    except Exception:
        print(
            "Warning: --plot requested but 'plotext' is not installed. "
            "Install it via 'ait setup' (stats graph support).",
            file=sys.stderr,
        )
        return

    def show_chart(
        title: str,
        x: List[str],
        y: List[int],
        kind: str = "bar",
        force_categorical: bool = False,
    ) -> None:
        if not x:
            return
        plt.clear_figure()
        width, height = chart_plot_size()
        if hasattr(plt, "plotsize"):
            plt.plotsize(width, height)
        plt.title(title)
        if kind == "line":
            # plotext attempts date parsing for strings like "02-27".
            # Use numeric x-values and explicit tick labels for stable behavior.
            if force_categorical:
                x_positions = list(range(len(x)))
                plt.plot(x_positions, y, marker="dot")
                plt.xticks(x_positions, x)
            else:
                plt.plot(x, y, marker="dot")
        else:
            plt.bar(x, y)
        plt.theme("pro")
        plt.show()
        if sys.stdin.isatty():
            try:
                input("Press Enter for next chart... ")
            except EOFError:
                pass
        print()
        print()

    dseq = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
    show_chart(
        build_chart_title("Daily Completions", f"last {days} days"),
        [d.isoformat()[5:] for d in dseq],
        [data.daily_counts.get(d, 0) for d in dseq],
        kind="line",
        force_categorical=True,
    )

    week_dows = [((week_start_dow - 1 + j) % 7) + 1 for j in range(7)]
    show_chart(
        build_chart_title("Average Completions by Weekday", "last 30 days", week_start_dow),
        [DAY_NAMES[dow] for dow in week_dows],
        [data.dow_counts_30d.get(dow, 0) for dow in week_dows],
    )

    top_labels = sorted(data.all_labels, key=lambda lbl: (-data.label_counts_total.get(lbl, 0), lbl))[:8]
    show_chart(
        build_chart_title("Top Labels by Completed Tasks", "all time"),
        top_labels,
        [data.label_counts_total.get(lbl, 0) for lbl in top_labels],
    )

    types = get_valid_task_types()[:8]
    show_chart(
        build_chart_title("Issue Types", "this week", week_start_dow),
        [t.capitalize() for t in types],
        [data.type_week_counts.get((t, 0), 0) for t in types],
    )

    codeagent_4w_x, codeagent_4w_y = chart_totals(
        data.codeagent_week_counts, codeagent_display_name, range(4)
    )
    show_chart(
        build_chart_title("Code Agents by Completed Tasks", "last 4 weeks", week_start_dow),
        codeagent_4w_x,
        codeagent_4w_y,
    )

    codeagent_1w_x, codeagent_1w_y = chart_totals(
        data.codeagent_week_counts, codeagent_display_name, [0]
    )
    show_chart(
        build_chart_title("Code Agents by Completed Tasks", "this week", week_start_dow),
        codeagent_1w_x,
        codeagent_1w_y,
    )

    model_4w_x, model_4w_y = chart_totals(
        data.model_week_counts, lambda key: data.model_display_names.get(key, "Unknown"), range(4), limit=8
    )
    show_chart(
        build_chart_title("LLM Models by Completed Tasks", "last 4 weeks", week_start_dow),
        model_4w_x,
        model_4w_y,
    )

    model_1w_x, model_1w_y = chart_totals(
        data.model_week_counts, lambda key: data.model_display_names.get(key, "Unknown"), [0], limit=8
    )
    show_chart(
        build_chart_title("LLM Models by Completed Tasks", "this week", week_start_dow),
        model_1w_x,
        model_1w_y,
    )


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

    if args.csv is not None:
        csv_path = Path(args.csv)
        write_csv(csv_path, data.csv_rows)
        print(f"CSV exported to: {csv_path}")

    if args.plot:
        run_plot_summary(data, days=args.days, today=today, week_start_dow=week_start_dow)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
