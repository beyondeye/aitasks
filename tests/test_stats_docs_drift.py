"""Drift guard: stats docs <-> stats source (t1591).

Three hand-written doc claims duplicate values the code owns, and two of them
had already drifted unnoticed (t1544_6: "Four presets" against seven shipped;
the skill doc's 7 CSV columns against 12). This file asserts each claim against
the source so the next drift fails a test instead of shipping:

1. the preset table in the stats TUI page  == ``DEFAULT_PRESETS`` x pane titles;
2. the ``--csv`` / ``--csv-backlog`` column lists (website + skill doc)
   == the headers ``write_csv`` / ``write_backlog_csv`` emit;
3. the numbered "Statistics provided" lists (website + skill doc)
   == the ``### `` sections ``ait stats`` (``main()``) prints, in order.

Everything is synthetic: no assertion depends on this repository's task data.
Every parser fails closed -- a renamed heading, a restructured table or an
unrecognised list entry raises ``DocParseError`` instead of silently comparing
nothing, and ``TestGuardsFailClosed`` proves it on mutated copies of the docs.

When a test here fails, update the doc to match the source. If you added,
removed, renamed or reordered a report section, update both numbered doc lists
and ``SECTIONS`` below together.
"""

from __future__ import annotations

import contextlib
import csv
import importlib.util
import io
import re
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterator, List, cast

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / ".aitask-scripts"

WEBSITE_TUI = REPO / "website" / "content" / "docs" / "tuis" / "stats" / "_index.md"
WEBSITE_CMD = REPO / "website" / "content" / "docs" / "commands" / "board-stats.md"
SKILL_DOC = REPO / ".claude" / "skills" / "aitask-stats" / "SKILL.md"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load_stats_module():
    # A distinct module name: tests/test_aitask_stats_py.py registers its own
    # copy as "aitask_stats_py", and replacing that entry under a shared pytest
    # worker would swap module state out from under it.
    spec = importlib.util.spec_from_file_location("aitask_stats_docs_drift", SCRIPTS / "aitask_stats.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


stats = cast(Any, _load_stats_module())
stats_data_mod = cast(Any, sys.modules["stats_data"])

from stats.panes import PANE_DEFS  # noqa: E402 -- needs SCRIPTS on sys.path
from stats.stats_config import DEFAULT_PRESETS  # noqa: E402

# (heading main() prints, board-stats.md label, aitask-stats SKILL.md label).
# The doc labels are prose and the headings are code, so pairing them needs an
# explicit table; this is the one place a new report section is registered.
SECTIONS = [
    ("### Summary", "Summary", "Summary"),
    ("### Backlog Level (Open Tasks) - Weekly (Last 8 Weeks)", "Backlog level", "Backlog Level"),
    ("### Backlog Net Flow (Arrivals - Departures) - Weekly (Last 8 Weeks)", "Backlog net flow", "Backlog Net Flow"),
    ("### Daily Completions (Last 7 Days)", "Daily breakdown", "Daily Breakdown"),
    ("### Average Completions by Day of Week", "Day of week averages", "Day of Week Stats"),
    ("### Pipeline Timing (gated tasks)", "Pipeline timing", "Pipeline Timing"),
    ("### Completions by Label - Weekly Trend (Last 4 Weeks)", "Label weekly trends", "Label Weekly Trends"),
    ("### Label Avg by Day of Week (Last 30 Days)", "Label day-of-week", "Label Day-of-Week Breakdown"),
    ("### By Task Type - Weekly Trend (Last 4 Weeks)", "Task type trends", "Task Type Weekly Trends"),
    ("### By Issue Type per Label - Weekly Trend (Last 4 Weeks)", "Label + type trends", "Features/Bugs by Label Trends"),
    ("### By Code Agent - Weekly Trend (Last 4 Weeks)", "Code agent trends", "Code Agent Weekly Trends"),
    ("### By LLM Model - Weekly Trend (Last 4 Weeks)", "LLM model trends", "LLM Model Weekly Trends"),
    ("### Verified Model Rankings", "Verified model rankings", "Verified Model Rankings"),
]

PRESET_HEADING = "## Built-in layouts (presets)"
WEBSITE_LIST_ANCHOR = "**Statistics provided:**"
SKILL_LIST_HEADING = "## Statistics Provided"

WEBSITE_CSV_RE = r"`--csv` writes one row per \*completed\* task: `([^`]+)`"
WEBSITE_BACKLOG_RE = r"`--csv-backlog` writes `([^`]+)`"
SKILL_CSV_RE = r"\*\*CSV Export \(`--csv`\):\*\*[^\n]*\n- ([^\n]+)"
SKILL_BACKLOG_RE = r"\*\*Backlog Export \(`--csv-backlog`\):\*\*[^\n]*\n- ([^\n]+)"

_ORDERED_ITEM_RE = re.compile(r"^\s*\d+[.)]\s")
_STRICT_ITEM_RE = re.compile(r"^(\d+)\. \*\*(.+?)\*\*")
_PRESET_ROW_RE = re.compile(r"^\| \*\*(\w+)\*\* \| (.+?) \|$")
_TABLE_SEPARATOR_RE = re.compile(r"^\|[-:| ]+\|$")
_HEADING_RE = re.compile(r"^(#{1,6}) ")


class DocParseError(AssertionError):
    """A doc no longer has the shape the guard reads -- a failure, never a skip."""


# --------------------------------------------------------------------------
# Doc-side parsers (strict)
# --------------------------------------------------------------------------


def section(text: str, heading: str) -> str:
    """Body under an exact heading line, up to the next heading of the same or
    a higher level. Lines inside ``` fences are never read as headings."""
    level = len(heading) - len(heading.lstrip("#"))
    lines = text.splitlines()
    try:
        start = lines.index(heading)
    except ValueError:
        raise DocParseError(f"heading {heading!r} not found") from None
    body: List[str] = []
    in_fence = False
    for line in lines[start + 1:]:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            m = _HEADING_RE.match(line)
            if m and len(m.group(1)) <= level:
                break
        body.append(line)
    return "\n".join(body)


def parse_preset_table(text: str) -> Dict[str, List[str]]:
    table = [line for line in section(text, PRESET_HEADING).splitlines() if line.startswith("|")]
    if len(table) < 3:
        raise DocParseError(f"preset table under {PRESET_HEADING!r} has no data rows")
    if not _TABLE_SEPARATOR_RE.match(table[1]):
        raise DocParseError(f"preset table separator row not found: {table[1]!r}")
    presets: Dict[str, List[str]] = {}
    for row in table[2:]:
        m = _PRESET_ROW_RE.match(row)
        if not m:
            raise DocParseError(f"unrecognised preset table row: {row!r}")
        name = m.group(1)
        if name in presets:
            raise DocParseError(f"duplicate preset row: {name!r}")
        panes = [p.strip() for p in m.group(2).split("·")]
        if not all(panes):
            raise DocParseError(f"empty pane cell in preset row: {row!r}")
        presets[name] = panes
    return presets


def _split_columns(raw: str, where: str) -> List[str]:
    columns = [c.strip() for c in raw.split(",")]
    if not all(columns):
        raise DocParseError(f"empty column name in {where}: {raw!r}")
    return columns


def parse_columns(text: str, pattern: str) -> List[str]:
    """The one comma-separated column list ``pattern`` captures. Zero matches,
    or more than one (two disagreeing copies), is a parse failure."""
    matches = re.findall(pattern, text)
    if len(matches) != 1:
        raise DocParseError(f"expected exactly one match for {pattern!r}, found {len(matches)}")
    return _split_columns(matches[0], pattern)


def parse_numbered_bold_list(region: str) -> List[str]:
    """Bold labels of the ``N. **Label** ...`` list in ``region``.

    EVERY ordered-list-looking line in the region must have the strict form: an
    unbolded ``14. Extra section`` raises instead of being skipped, which a
    bold-only regex would silently do.
    """
    labels: List[str] = []
    for line in region.splitlines():
        if not _ORDERED_ITEM_RE.match(line):
            continue
        m = _STRICT_ITEM_RE.match(line)
        if not m:
            raise DocParseError(f"numbered entry without the '<n>. **Label**' form: {line!r}")
        expected = len(labels) + 1
        if int(m.group(1)) != expected:
            raise DocParseError(f"list numbering broken: expected {expected}, found {line!r}")
        labels.append(m.group(2))
    if not labels:
        raise DocParseError("no numbered entries found")
    return labels


def website_section_list(text: str) -> List[str]:
    if WEBSITE_LIST_ANCHOR not in text:
        raise DocParseError(f"anchor {WEBSITE_LIST_ANCHOR!r} not found")
    region: List[str] = []
    for line in text.split(WEBSITE_LIST_ANCHOR, 1)[1].splitlines()[1:]:
        if line.startswith("**") or _HEADING_RE.match(line):
            break
        region.append(line)
    return parse_numbered_bold_list("\n".join(region))


def skill_section_list(text: str) -> List[str]:
    return parse_numbered_bold_list(section(text, SKILL_LIST_HEADING))


# --------------------------------------------------------------------------
# Source side (synthetic -- never this repository's task data)
# --------------------------------------------------------------------------

_FIXED_TODAY = date(2026, 3, 5)


@contextlib.contextmanager
def synthetic_repo() -> Iterator[Path]:
    """A one-archived-task repo patched into the stats modules, then restored.

    One task, because main() exits early on an empty repo. Patches both modules
    exactly as tests/test_aitask_stats_py.py does: collect_stats lives in
    stats_data and reads its globals there.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        tasks = base / "aitasks"
        archived = tasks / "archived"
        archived.mkdir(parents=True)
        (tasks / "metadata").mkdir()
        (archived / "t1_fixture.md").write_text(
            "---\nstatus: Done\nissue_type: feature\n"
            "created_at: 2026-01-01 09:00\ncompleted_at: 2026-01-02 09:00\n---\nBody.\n",
            encoding="utf-8",
        )
        names = ("TASK_DIR", "ARCHIVE_DIR", "TASK_TYPES_FILE")
        saved = [(mod, {n: getattr(mod, n) for n in names}) for mod in (stats, stats_data_mod)]
        try:
            for mod, _ in saved:
                mod.TASK_DIR = tasks
                mod.ARCHIVE_DIR = archived
                mod.TASK_TYPES_FILE = tasks / "metadata" / "task_types.txt"
            yield base
        finally:
            for mod, values in saved:
                for n, v in values.items():
                    setattr(mod, n, v)


def source_presets() -> Dict[str, List[str]]:
    return {k: [PANE_DEFS[i].title for i in v] for k, v in DEFAULT_PRESETS.items()}


def source_csv_headers() -> Dict[str, List[str]]:
    with synthetic_repo() as base:
        data = stats.collect_stats(today=_FIXED_TODAY, week_start_dow=1)
        csv_path = base / "stats.csv"
        backlog_path = base / "backlog.csv"
        stats.write_csv(csv_path, [])
        stats.write_backlog_csv(
            backlog_path,
            data,
            stats.build_backlog_axis(data, stats.backlog_week_offsets(8)),
            _FIXED_TODAY,
            1,
        )
        headers = {}
        for key, path in (("csv", csv_path), ("backlog", backlog_path)):
            with path.open(newline="", encoding="utf-8") as handle:
                headers[key] = next(csv.reader(handle))
        return headers


def source_section_headings() -> List[str]:
    """The ``### `` headings the real command assembly prints.

    Drives main() rather than concatenating the renderers here, so a reorder or
    a dropped print in main() is seen. Rankings are stubbed to one synthetic
    operation (main() prints them only when one exists); no --csv flag, so
    nothing is written.
    """
    vdata = stats_data_mod.VerifiedRankingData(
        by_window={"pick": {"all_providers": {"all_time": [
            stats_data_mod.VerifiedModelEntry("m", "M", "all_providers", 80, 3),
        ]}}},
        operations=["pick"],
    )
    original = stats.load_verified_rankings
    out = io.StringIO()
    with synthetic_repo():
        stats.load_verified_rankings = lambda **_kwargs: vdata
        try:
            with contextlib.redirect_stdout(out):
                rc = stats.main([])
        finally:
            stats.load_verified_rankings = original
    if rc != 0:
        raise AssertionError(f"ait stats main() exited {rc}:\n{out.getvalue()}")
    return [line for line in out.getvalue().splitlines() if line.startswith("### ")]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


_FIX = "update the doc to match the source"


# --------------------------------------------------------------------------
# Claim 1 -- preset table
# --------------------------------------------------------------------------


class TestPresetTable(unittest.TestCase):
    def test_website_table_matches_shipped_presets(self):
        self.assertEqual(
            parse_preset_table(_read(WEBSITE_TUI)),
            source_presets(),
            msg=f"{WEBSITE_TUI.relative_to(REPO)} {PRESET_HEADING!r} drifted from "
                f"DEFAULT_PRESETS / pane titles -- {_FIX}",
        )


# --------------------------------------------------------------------------
# Claim 2 -- CSV column lists
# --------------------------------------------------------------------------


class TestCsvColumns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.headers = source_csv_headers()

    def _check(self, path: Path, pattern: str, key: str):
        self.assertEqual(
            parse_columns(_read(path), pattern),
            self.headers[key],
            msg=f"{path.relative_to(REPO)} column list ({pattern!r}) drifted from the "
                f"emitted {key} CSV header -- {_FIX}",
        )

    def test_website_csv_columns(self):
        self._check(WEBSITE_CMD, WEBSITE_CSV_RE, "csv")

    def test_website_backlog_columns(self):
        self._check(WEBSITE_CMD, WEBSITE_BACKLOG_RE, "backlog")

    def test_skill_csv_columns(self):
        self._check(SKILL_DOC, SKILL_CSV_RE, "csv")

    def test_skill_backlog_columns(self):
        self._check(SKILL_DOC, SKILL_BACKLOG_RE, "backlog")


# --------------------------------------------------------------------------
# Claim 3 -- rendered section list
# --------------------------------------------------------------------------


class TestSectionList(unittest.TestCase):
    def test_source_headings_match_pin_table(self):
        self.assertEqual(
            source_section_headings(),
            [h for h, _, _ in SECTIONS],
            msg="ait stats sections changed -- add/remove/reorder the entry in BOTH numbered "
                "doc lists (board-stats.md, aitask-stats SKILL.md) and in SECTIONS",
        )

    def test_website_list_matches(self):
        self.assertEqual(
            website_section_list(_read(WEBSITE_CMD)),
            [w for _, w, _ in SECTIONS],
            msg=f"{WEBSITE_CMD.relative_to(REPO)} {WEBSITE_LIST_ANCHOR!r} drifted -- {_FIX} (and SECTIONS)",
        )

    def test_skill_list_matches(self):
        self.assertEqual(
            skill_section_list(_read(SKILL_DOC)),
            [s for _, _, s in SECTIONS],
            msg=f"{SKILL_DOC.relative_to(REPO)} {SKILL_LIST_HEADING!r} drifted -- {_FIX} (and SECTIONS)",
        )


# --------------------------------------------------------------------------
# Negative controls -- mutated copies of the real docs, never the files
# --------------------------------------------------------------------------


def _mutate(text: str, old: str, new: str) -> str:
    if old not in text:
        raise AssertionError(f"negative control is stale: {old!r} is no longer in the doc")
    return text.replace(old, new, 1)


class TestGuardsFailClosed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tui = _read(WEBSITE_TUI)
        cls.cmd = _read(WEBSITE_CMD)
        cls.skill = _read(SKILL_DOC)

    # -- a missing anchor raises, for every parser -------------------------

    def test_missing_preset_heading_raises(self):
        with self.assertRaises(DocParseError):
            parse_preset_table(_mutate(self.tui, PRESET_HEADING, "## Layouts"))

    def test_missing_csv_anchors_raise(self):
        cases = [
            (self.cmd, WEBSITE_CSV_RE, "`--csv` writes one row per", "`--csv` emits one row per"),
            (self.cmd, WEBSITE_BACKLOG_RE, "`--csv-backlog` writes `", "`--csv-backlog` emits `"),
            (self.skill, SKILL_CSV_RE, "**CSV Export (`--csv`):**", "**CSV (`--csv`):**"),
            (self.skill, SKILL_BACKLOG_RE, "**Backlog Export (`--csv-backlog`):**", "**Backlog (`--csv-backlog`):**"),
        ]
        for text, pattern, old, new in cases:
            with self.subTest(pattern=pattern), self.assertRaises(DocParseError):
                parse_columns(_mutate(text, old, new), pattern)

    def test_missing_list_anchors_raise(self):
        with self.assertRaises(DocParseError):
            website_section_list(_mutate(self.cmd, WEBSITE_LIST_ANCHOR, "**Stats:**"))
        with self.assertRaises(DocParseError):
            skill_section_list(_mutate(self.skill, SKILL_LIST_HEADING, "## Stats"))

    # -- malformed content raises ------------------------------------------

    def test_unbolded_preset_row_raises(self):
        with self.assertRaises(DocParseError):
            parse_preset_table(_mutate(self.tui, "| **overview** |", "| overview |"))

    def test_numbering_gap_raises(self):
        with self.assertRaises(DocParseError):
            parse_numbered_bold_list("1. **A** — x\n3. **B** — y\n")

    def test_unbolded_trailing_entry_raises(self):
        # The case a bold-only regex passes: 13 good entries plus an extra one.
        cases = [
            (website_section_list, self.cmd, "13. **Verified model rankings**"),
            (skill_section_list, self.skill, "13. **Verified Model Rankings**"),
        ]
        for parse, text, anchor in cases:
            line = next(ln for ln in text.splitlines() if ln.startswith(anchor))
            with self.subTest(anchor=anchor), self.assertRaises(DocParseError):
                parse(_mutate(text, line, line + "\n14. Extra report section"))

    def test_unbolded_mid_list_entry_raises(self):
        cases = [
            (website_section_list, self.cmd, "4. **Daily breakdown**", "4. Daily breakdown"),
            (skill_section_list, self.skill, "4. **Daily Breakdown**", "4. Daily Breakdown"),
        ]
        for parse, text, old, new in cases:
            with self.subTest(old=old), self.assertRaises(DocParseError):
                parse(_mutate(text, old, new))

    # -- a real drift compares unequal -------------------------------------

    def test_renamed_pane_title_is_detected(self):
        mutated = _mutate(self.tui, "Weekday distribution", "Weekday breakdown")
        self.assertNotEqual(parse_preset_table(mutated), source_presets())

    def test_dropped_csv_column_is_detected(self):
        mutated = _mutate(self.cmd, "created_at, category`", "created_at`")
        self.assertNotEqual(parse_columns(mutated, WEBSITE_CSV_RE), source_csv_headers()["csv"])

    def test_removed_section_entry_is_detected(self):
        line = next(ln for ln in self.cmd.splitlines() if ln.startswith("13. **Verified model rankings**"))
        mutated = _mutate(self.cmd, line + "\n", "")
        self.assertNotEqual(website_section_list(mutated), [w for _, w, _ in SECTIONS])


if __name__ == "__main__":
    unittest.main()
