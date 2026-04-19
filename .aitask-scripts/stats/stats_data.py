"""Pure data extraction layer for ait stats.

Used by the CLI text/CSV report (`aitask_stats.py`) and the TUI (`stats_app.py`).
No rendering, no plotext — just dataclasses, parsers, and `collect_stats()`.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Make `lib/` importable so `archive_iter` resolves regardless of how this
# module is loaded (via the CLI wrapper, the TUI wrapper, or a test harness).
_LIB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
from archive_iter import iter_all_archived_markdown  # noqa: E402

TASK_DIR = Path("aitasks")
ARCHIVE_DIR = TASK_DIR / "archived"
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


@dataclass
class VerifiedModelEntry:
    """A single model's verified score for ranking display."""
    cli_id: str
    display_name: str
    provider: str  # agent name or "all_providers"
    score: int     # round(score_sum / runs)
    runs: int


@dataclass
class VerifiedRankingData:
    """Verified model rankings by operation, provider, and time window."""
    # {operation: {provider_or_"all_providers": {window: [VerifiedModelEntry, ...]}}}
    by_window: Dict[str, Dict[str, Dict[str, List[VerifiedModelEntry]]]]
    operations: List[str]  # sorted list of discovered operations


def bucket_avg(runs: int, score_sum: int) -> int:
    """Compute rounded average from verifiedstats bucket values."""
    if runs <= 0:
        return 0
    return round(score_sum / runs)


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


def load_verified_rankings() -> VerifiedRankingData:
    """Load verifiedstats from all models_*.json and build rankings.

    Returns rankings by operation, provider, and time window, plus
    all_providers aggregation using canonical_model_id() normalization.
    """
    metadata_dir = TASK_DIR / "metadata"
    agents = ("claudecode", "codex", "geminicli", "opencode")

    # Collect raw verifiedstats: {(agent, cli_id): {op: {window: {runs, score_sum, period?}}}}
    raw: Dict[Tuple[str, str], Dict[str, Dict[str, dict]]] = {}
    cli_id_set: Dict[Tuple[str, str], str] = {}  # (agent, cli_id) -> cli_id for display

    for agent in agents:
        path = metadata_dir / f"models_{agent}.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for model in payload.get("models", []):
            cli_id = model.get("cli_id", "")
            vstats = model.get("verifiedstats")
            if not isinstance(vstats, dict) or not vstats or not cli_id:
                continue
            key = (agent, cli_id)
            cli_id_set[key] = cli_id
            raw[key] = {}
            for op, buckets in vstats.items():
                if not isinstance(buckets, dict):
                    continue
                # Handle both new bucketed format and old flat format
                if "all_time" in buckets:
                    at = buckets["all_time"]
                elif "runs" in buckets and "all_time" not in buckets:
                    # Old flat format: {runs, score_sum} at top level
                    at = buckets
                else:
                    continue
                at_runs = at.get("runs", 0)
                if at_runs <= 0:
                    continue
                raw[key][op] = {
                    "all_time": {"runs": at_runs, "score_sum": at.get("score_sum", 0)},
                    "month": buckets.get("month", {}),
                    "week": buckets.get("week", {}),
                }

    if not raw:
        return VerifiedRankingData(by_window={}, operations=[])

    # Discover all operations
    all_ops: set = set()
    for entry_ops in raw.values():
        all_ops.update(entry_ops.keys())

    # Build per-provider entries
    by_window: Dict[str, Dict[str, Dict[str, List[VerifiedModelEntry]]]] = {}
    for op in sorted(all_ops):
        by_window[op] = {}
        for (agent, cli_id), entry_ops in raw.items():
            if op not in entry_ops:
                continue
            buckets = entry_ops[op]
            if agent not in by_window[op]:
                by_window[op][agent] = {"all_time": [], "month": [], "week": []}
            display = model_display_from_cli_id(cli_id)
            at = buckets["all_time"]
            by_window[op][agent]["all_time"].append(
                VerifiedModelEntry(cli_id, display, agent, bucket_avg(at["runs"], at["score_sum"]), at["runs"])
            )
            for win in ("month", "week"):
                wb = buckets.get(win, {})
                w_runs = wb.get("runs", 0)
                if w_runs > 0:
                    by_window[op][agent][win].append(
                        VerifiedModelEntry(cli_id, display, agent, bucket_avg(w_runs, wb.get("score_sum", 0)), w_runs)
                    )

    # All-providers aggregation: group by canonical_model_id
    for op in sorted(all_ops):
        # Collect per-canonical: {canonical: {window: {runs, score_sum, period?}}}
        grouped: Dict[str, Dict[str, dict]] = defaultdict(lambda: {
            "all_time": {"runs": 0, "score_sum": 0},
            "month": {"runs": 0, "score_sum": 0, "period": ""},
            "week": {"runs": 0, "score_sum": 0, "period": ""},
        })
        canonical_display: Dict[str, str] = {}
        canonical_cli: Dict[str, str] = {}
        for (agent, cli_id), entry_ops in raw.items():
            if op not in entry_ops:
                continue
            canon = canonical_model_id(cli_id)
            if canon not in canonical_display:
                canonical_display[canon] = model_display_from_cli_id(cli_id)
                canonical_cli[canon] = cli_id
            buckets = entry_ops[op]
            at = buckets["all_time"]
            grouped[canon]["all_time"]["runs"] += at["runs"]
            grouped[canon]["all_time"]["score_sum"] += at["score_sum"]
            for win in ("month", "week"):
                wb = buckets.get(win, {})
                w_runs = wb.get("runs", 0)
                w_period = wb.get("period", "")
                if w_runs <= 0 or not w_period:
                    continue
                g = grouped[canon][win]
                if not g["period"]:
                    g["period"] = w_period
                if g["period"] == w_period:
                    g["runs"] += w_runs
                    g["score_sum"] += wb.get("score_sum", 0)

        ap_entries: Dict[str, List[VerifiedModelEntry]] = {"all_time": [], "month": [], "week": []}
        for canon, windows in grouped.items():
            at = windows["all_time"]
            if at["runs"] > 0:
                ap_entries["all_time"].append(
                    VerifiedModelEntry(
                        canonical_cli.get(canon, canon),
                        canonical_display.get(canon, canon),
                        "all_providers",
                        bucket_avg(at["runs"], at["score_sum"]),
                        at["runs"],
                    )
                )
            for win in ("month", "week"):
                wb = windows[win]
                if wb["runs"] > 0:
                    ap_entries[win].append(
                        VerifiedModelEntry(
                            canonical_cli.get(canon, canon),
                            canonical_display.get(canon, canon),
                            "all_providers",
                            bucket_avg(wb["runs"], wb["score_sum"]),
                            wb["runs"],
                        )
                    )
        by_window[op]["all_providers"] = ap_entries

    # Sort all entry lists: score desc, display_name asc
    def _sort_key(e: VerifiedModelEntry) -> Tuple[int, str]:
        return (-e.score, e.display_name)

    for op in by_window:
        for provider in by_window[op]:
            for win in by_window[op][provider]:
                by_window[op][provider][win].sort(key=_sort_key)

    return VerifiedRankingData(by_window=by_window, operations=sorted(all_ops))


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
    return iter_all_archived_markdown(ARCHIVE_DIR)


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


def codeagent_display_name(key: str) -> str:
    return AGENT_DISPLAY_NAMES.get(key, titleize_words(key))


def sorted_weekly_keys(keys: Iterable[str], weekly_counts: Counter, display_lookup) -> List[str]:
    return sorted(
        keys,
        key=lambda key: (
            -sum(weekly_counts.get((key, wk), 0) for wk in range(4)),
            display_lookup(key),
        ),
    )


def week_start_display_name(week_start_dow: int) -> str:
    if 1 <= week_start_dow < len(DAY_FULL_NAMES):
        return DAY_FULL_NAMES[week_start_dow]
    return "Monday"


def build_chart_title(subject: str, timeframe: str, week_start_dow: Optional[int] = None) -> str:
    title = f"{subject} - {timeframe}"
    if week_start_dow is not None:
        title += f" (week starts {week_start_display_name(week_start_dow)})"
    return title


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
        other_total = sum(count for _, count in items[limit - 1:])
        if other_total:
            visible.append(("__other__", other_total))
        items = visible

    labels = ["Other" if key == "__other__" else display_lookup(key) for key, _ in items]
    values = [count for _, count in items]
    return labels, values


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
