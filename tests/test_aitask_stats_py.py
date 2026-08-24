"""Unit tests for .aitask-scripts/aitask_stats.py."""

from __future__ import annotations

import contextlib
import csv
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from datetime import date
from pathlib import Path
from typing import Any, cast


def _load_stats_module():
    script = Path(__file__).resolve().parents[1] / ".aitask-scripts" / "aitask_stats.py"
    spec = importlib.util.spec_from_file_location("aitask_stats_py", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


stats = cast(Any, _load_stats_module())

# After the data-extraction split (t597_1), constants TASK_DIR / ARCHIVE_DIR /
# TASK_TYPES_FILE live in `stats_data` (promoted from stats/ to the base layer
# lib/ in t1235) and are re-exported from `aitask_stats`. Tests that patch the
# constants must mutate the source module so functions defined there (e.g.
# collect_stats, load_verified_rankings) pick up the temp paths.
stats_data_mod = cast(Any, sys.modules["stats_data"])


class TestWeekStart(unittest.TestCase):
    def test_resolve_week_start_prefix(self):
        self.assertEqual(stats.resolve_week_start("mon"), 1)
        self.assertEqual(stats.resolve_week_start("sun"), 7)

    def test_resolve_week_start_invalid_defaults_monday(self):
        self.assertEqual(stats.resolve_week_start("zzz"), 1)


class TestArgParsing(unittest.TestCase):
    def test_days_accepts_trailing_dot(self):
        args = stats.parse_args(["-d", "7."])
        self.assertEqual(args.days, 7)


class TestFrontmatterParsing(unittest.TestCase):
    def test_completed_at_fallback_to_updated_at(self):
        fm = {
            "status": "Done",
            "updated_at": "2026-03-01 12:30",
        }
        self.assertEqual(stats.parse_completed_date(fm), date(2026, 3, 1))


class TestCollection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

        metadata = self.base / "aitasks" / "metadata"
        archived = self.base / "aitasks" / "archived"
        metadata.mkdir(parents=True)
        archived.mkdir(parents=True)

        (metadata / "models_codex.json").write_text(
            json.dumps(
                {
                    "models": [
                        {"name": "gpt5_4", "cli_id": "gpt-5.4"},
                        {"name": "gpt5_3codex", "cli_id": "gpt-5.3-codex"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        (metadata / "models_claudecode.json").write_text(
            json.dumps({"models": [
                {"name": "opus4_6", "cli_id": "claude-opus-4-6"},
                {"name": "opus4_7", "cli_id": "claude-opus-4-7", "verifiedstats": {}},
            ]}),
            encoding="utf-8",
        )
        (metadata / "models_opencode.json").write_text(
            json.dumps(
                {
                    "models": [
                        {
                            "name": "openai_gpt_5_3_codex",
                            "cli_id": "openai/gpt-5.3-codex",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        (archived / "t1_parent.md").write_text(
            "---\n"
            "status: Done\n"
            "completed_at: 2026-03-01 10:00\n"
            "labels: [alpha]\n"
            "issue_type: bug\n"
            "implemented_with: codex/gpt5_4\n"
            "---\n"
            "parent\n",
            encoding="utf-8",
        )

        child_dir = archived / "t1"
        child_dir.mkdir()
        (child_dir / "t1_1_child.md").write_text(
            "---\n"
            "status: Done\n"
            "completed_at: 2026-03-02 11:00\n"
            "labels: [beta]\n"
            "issue_type: feature\n"
            "implemented_with: claudecode/opus4_6\n"
            "---\n"
            "child\n",
            encoding="utf-8",
        )

        (archived / "t3_missing_impl.md").write_text(
            "---\n"
            "status: Done\n"
            "completed_at: 2026-03-03 08:00\n"
            "labels: [delta]\n"
            "issue_type: documentation\n"
            "---\n"
            "missing\n",
            encoding="utf-8",
        )

        (archived / "t4_legacy_impl.md").write_text(
            "---\n"
            "status: Done\n"
            "completed_at: 2026-03-04 12:00\n"
            "labels: [epsilon]\n"
            "issue_type: feature\n"
            "implemented_with: codex/gpt-5\n"
            "---\n"
            "legacy\n",
            encoding="utf-8",
        )

        # Use numbered archive (_b0/old0.tar.zst) instead of legacy old.tar.zst
        tar_dir = archived / "_b0"
        tar_dir.mkdir()
        tar_path = tar_dir / "old0.tar.zst"
        old = self.base / "old_task.md"
        old.write_text(
            "---\n"
            "status: Done\n"
            "completed_at: 2026-02-20 09:00\n"
            "labels: [gamma]\n"
            "issue_type: refactor\n"
            "implemented_with: opencode/openai_gpt_5_3_codex\n"
            "---\n"
            "old\n",
            encoding="utf-8",
        )
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            tf.add(old, arcname="t2_old_task.md")
        buf.seek(0)
        subprocess.run(
            ["zstd", "-q", "-f", "-o", str(tar_path)],
            input=buf.read(), check=True,
        )

        self.orig_task_dir = stats.TASK_DIR
        self.orig_archive_dir = stats.ARCHIVE_DIR
        self.orig_task_types = stats.TASK_TYPES_FILE

        new_task_dir = self.base / "aitasks"
        new_archive_dir = new_task_dir / "archived"
        new_task_types = new_task_dir / "metadata" / "task_types.txt"
        for mod in (stats, stats_data_mod):
            mod.TASK_DIR = new_task_dir
            mod.ARCHIVE_DIR = new_archive_dir
            mod.TASK_TYPES_FILE = new_task_types

    def tearDown(self):
        for mod in (stats, stats_data_mod):
            mod.TASK_DIR = self.orig_task_dir
            mod.ARCHIVE_DIR = self.orig_archive_dir
            mod.TASK_TYPES_FILE = self.orig_task_types
        self.tmp.cleanup()

    def test_collect_stats_includes_archived_and_tar(self):
        data = stats.collect_stats(today=date(2026, 3, 5), week_start_dow=1)
        self.assertEqual(data.total_tasks, 5)
        self.assertEqual(data.tasks_7d, 4)
        self.assertEqual(data.tasks_30d, 5)
        self.assertEqual(data.label_counts_total["alpha"], 1)
        self.assertEqual(data.label_counts_total["beta"], 1)
        self.assertEqual(data.label_counts_total["gamma"], 1)
        self.assertEqual(data.codeagent_week_counts[("codex", 0)], 1)
        self.assertEqual(data.codeagent_week_counts[("codex", 1)], 1)
        self.assertEqual(data.codeagent_week_counts[("claudecode", 0)], 1)
        self.assertEqual(data.codeagent_week_counts[("opencode", 2)], 1)
        self.assertEqual(data.codeagent_week_counts[("unknown", 0)], 1)
        self.assertEqual(data.model_week_counts[("gpt5", 0)], 1)
        self.assertEqual(data.model_week_counts[("gpt5_4", 1)], 1)
        self.assertEqual(data.model_week_counts[("opus4_6", 0)], 1)
        self.assertEqual(data.model_week_counts[("gpt5_3codex", 2)], 1)
        self.assertEqual(data.model_week_counts[("unknown", 0)], 1)
        self.assertEqual(len(data.csv_rows), 5)
        # 12 since t1544_4 appended created_at + category to the fact table.
        self.assertEqual(len(data.csv_rows[0]), 12)

    def test_normalize_implemented_with_handles_legacy_and_missing_values(self):
        canonical = stats.normalize_implemented_with("codex/gpt5_4")
        legacy = stats.normalize_implemented_with("codex/gpt-5")
        missing = stats.normalize_implemented_with("")
        unknown_model = stats.normalize_implemented_with("codex/not_a_known_model")

        self.assertEqual(canonical.codeagent_key, "codex")
        self.assertEqual(canonical.model_key, "gpt5_4")
        self.assertEqual(canonical.model_display, "GPT5.4")
        self.assertEqual(legacy.codeagent_key, "codex")
        self.assertEqual(legacy.model_key, "gpt5")
        self.assertEqual(legacy.model_display, "GPT5")
        self.assertEqual(missing.codeagent_key, "unknown")
        self.assertEqual(missing.model_key, "unknown")
        self.assertEqual(unknown_model.codeagent_key, "codex")
        self.assertEqual(unknown_model.model_key, "unknown")

    def test_render_text_report_includes_codeagent_and_model_sections(self):
        data = stats.collect_stats(today=date(2026, 3, 5), week_start_dow=1)

        report = stats.render_text_report(
            data,
            days=7,
            verbose=False,
            week_start_dow=1,
            today=date(2026, 3, 5),
        )

        self.assertIn("### By Code Agent - Weekly Trend (Last 4 Weeks)", report)
        self.assertIn("### By LLM Model - Weekly Trend (Last 4 Weeks)", report)
        self.assertIn("Codex", report)
        self.assertIn("Claude Code", report)
        self.assertIn("GPT5.4", report)
        self.assertIn("GPT5.3-Codex", report)
        self.assertIn("Unknown", report)

    def test_label_type_table_uses_canonical_display_names(self):
        """The label x type table must render types through the canonical map.

        Before t1577 this table used a bare ``issue_type.capitalize()``, so the
        same type printed two ways in one report -- ``Bug Fixes`` in the
        adjacent ``### By Task Type`` table and ``Bug`` here. The fixture has no
        ``task_types.txt``, so ``get_valid_task_types()`` falls back to
        ``["bug", "feature", "refactor"]`` -- exactly the three types whose
        display name differs from ``raw.capitalize()``.
        """
        data = stats.collect_stats(today=date(2026, 3, 5), week_start_dow=1)
        report = stats.render_text_report(
            data,
            days=7,
            verbose=False,
            week_start_dow=1,
            today=date(2026, 3, 5),
        )

        section = report.split("### By Issue Type per Label")[1].split("\n###")[0]

        # Parse the Type cell per row rather than substring-matching: "| Bug |"
        # is a substring of "| Bug Fixes |", so a bare assertNotIn would pass
        # against the fixed code for the wrong reason.
        rendered = {}
        for line in section.splitlines():
            if not line.startswith("| ") or line.startswith("| Label"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rendered[cells[0]] = cells[1]

        # Exact equality: the pre-fix raw.capitalize() forms were Bug /
        # Feature / Refactor, so each of these fails against the old code.
        self.assertEqual(rendered["alpha"], "Bug Fixes")
        self.assertEqual(rendered["beta"], "Features")
        self.assertEqual(rendered["gamma"], "Refactors")
        self.assertEqual(rendered["epsilon"], "Features")

        # The Type column is wide enough for the longest display name
        # (Manual_verification, 19 chars).
        self.assertIn("| Label        | Type                | Total |", section)

    def test_stats_tui_issue_type_chart_uses_canonical_display_names(self):
        """The stats-TUI "Issue types" bar chart shares the same display map.

        Drives the real ``_render_issue_types`` and captures the labels handed
        to ``plt.bar``; ``render_chart`` is patched on the pane module (where it
        is name-bound by the ``from .base import ...``) so no Textual app or
        plotext figure is needed.
        """
        import stats.panes.labels as pane_mod

        captured = {}

        class _Plt:
            def bar(self, labels, values):
                captured["labels"] = list(labels)

            def title(self, *args, **kwargs):
                pass

        original = pane_mod.render_chart
        pane_mod.render_chart = lambda setup_fn, container: setup_fn(_Plt())
        try:
            data = stats.collect_stats(today=date(2026, 3, 5), week_start_dow=1)
            pane_mod._render_issue_types(data, object())
        finally:
            pane_mod.render_chart = original

        self.assertIn("Bug Fixes", captured["labels"])
        self.assertIn("Refactors", captured["labels"])
        self.assertIn("Features", captured["labels"])
        self.assertNotIn("Bug", captured["labels"])
        self.assertNotIn("Refactor", captured["labels"])

    def test_write_csv_includes_implementation_columns(self):
        data = stats.collect_stats(today=date(2026, 3, 5), week_start_dow=1)
        output = self.base / "stats.csv"

        stats.write_csv(output, data.csv_rows)

        with output.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))

        self.assertEqual(
            rows[0],
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
                "created_at",
                "category",
            ],
        )
        # The fixture tasks carry no created_at, so that cell is empty and the
        # category falls through to the issue_type half of the axis.
        self.assertIn(
            [
                "2026-03-04", "Wed", "0", "t4_legacy_impl", "epsilon", "feature", "parent",
                "codex/gpt-5", "codex", "gpt5", "", "type:feature",
            ],
            rows[1:],
        )

class TestVerifiedRankings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

        metadata = self.base / "aitasks" / "metadata"
        metadata.mkdir(parents=True)

        # codex: gpt-5.4 with pick stats, gpt-5.3-codex with pick+explain
        (metadata / "models_codex.json").write_text(
            json.dumps({
                "models": [
                    {
                        "name": "gpt5_4", "cli_id": "gpt-5.4",
                        "verifiedstats": {
                            "pick": {
                                "all_time": {"runs": 5, "score_sum": 400},
                                "month": {"period": "2026-03", "runs": 2, "score_sum": 180},
                                "week": {"period": "2026-W10", "runs": 1, "score_sum": 80},
                            }
                        },
                        "verified": {"pick": 80},
                    },
                    {
                        "name": "gpt5_3codex", "cli_id": "gpt-5.3-codex",
                        "verifiedstats": {
                            "pick": {
                                "all_time": {"runs": 3, "score_sum": 240},
                                "month": {"period": "2026-03", "runs": 1, "score_sum": 80},
                                "week": {"period": "2026-W10", "runs": 0, "score_sum": 0},
                            },
                            "explain": {
                                "all_time": {"runs": 2, "score_sum": 180},
                                "month": {"period": "2026-03", "runs": 1, "score_sum": 100},
                                "week": {"period": "2026-W10", "runs": 0, "score_sum": 0},
                            },
                        },
                        "verified": {"pick": 80, "explain": 90},
                    },
                ]
            }),
            encoding="utf-8",
        )

        # claudecode: opus with pick stats (opus4_6) + newly-registered opus4_7 with empty stats
        (metadata / "models_claudecode.json").write_text(
            json.dumps({
                "models": [
                    {
                        "name": "opus4_6", "cli_id": "claude-opus-4-6",
                        "verifiedstats": {
                            "pick": {
                                "all_time": {"runs": 10, "score_sum": 960},
                                "month": {"period": "2026-03", "runs": 4, "score_sum": 400},
                                "week": {"period": "2026-W10", "runs": 2, "score_sum": 200},
                            }
                        },
                        "verified": {"pick": 96},
                    },
                    {
                        "name": "opus4_7", "cli_id": "claude-opus-4-7",
                        "verifiedstats": {},
                        "verified": {},
                    },
                ]
            }),
            encoding="utf-8",
        )

        # opencode: gpt-5.3-codex (same underlying model as codex's, for cross-provider test)
        (metadata / "models_opencode.json").write_text(
            json.dumps({
                "models": [
                    {
                        "name": "openai_gpt_5_3_codex",
                        "cli_id": "openai/gpt-5.3-codex",
                        "verifiedstats": {
                            "pick": {
                                "all_time": {"runs": 2, "score_sum": 160},
                                "month": {"period": "2026-03", "runs": 1, "score_sum": 80},
                                "week": {"period": "2026-W10", "runs": 0, "score_sum": 0},
                            }
                        },
                        "verified": {"pick": 80},
                    }
                ]
            }),
            encoding="utf-8",
        )

        self.orig_task_dir = stats.TASK_DIR
        new_task_dir = self.base / "aitasks"
        for mod in (stats, stats_data_mod):
            mod.TASK_DIR = new_task_dir

    def tearDown(self):
        for mod in (stats, stats_data_mod):
            mod.TASK_DIR = self.orig_task_dir
        self.tmp.cleanup()

    def test_load_verified_rankings_structure(self):
        vdata = stats.load_verified_rankings()
        self.assertEqual(sorted(vdata.operations), ["explain", "pick"])
        self.assertIn("all_providers", vdata.by_window["pick"])
        self.assertIn("codex", vdata.by_window["pick"])
        self.assertIn("claudecode", vdata.by_window["pick"])
        self.assertIn("opencode", vdata.by_window["pick"])

    def test_all_providers_aggregation(self):
        vdata = stats.load_verified_rankings()
        ap_at = vdata.by_window["pick"]["all_providers"]["all_time"]
        # Find gpt-5.3-codex aggregate (codex 3 runs + opencode 2 runs = 5)
        codex_entry = [e for e in ap_at if "5.3" in e.display_name]
        self.assertEqual(len(codex_entry), 1)
        self.assertEqual(codex_entry[0].runs, 5)  # 3 + 2
        self.assertEqual(codex_entry[0].score, 80)  # round((240+160)/5) = 80

    def test_all_providers_aggregation_month(self):
        vdata = stats.load_verified_rankings()
        ap_mo = vdata.by_window["pick"]["all_providers"]["month"]
        codex_mo = [e for e in ap_mo if "5.3" in e.display_name]
        self.assertEqual(len(codex_mo), 1)
        self.assertEqual(codex_mo[0].runs, 2)  # 1 + 1 (same period)

    def test_rankings_sorted_by_score_desc(self):
        vdata = stats.load_verified_rankings()
        at = vdata.by_window["pick"]["all_providers"]["all_time"]
        scores = [e.score for e in at]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_render_verified_rankings_sections(self):
        vdata = stats.load_verified_rankings()
        output = stats.render_verified_rankings(vdata)
        self.assertIn("### Verified Model Rankings", output)
        self.assertIn("#### pick", output)
        self.assertIn("#### explain", output)
        self.assertIn("Opus 4.6", output)
        self.assertIn("GPT5.4", output)

    def test_render_verified_rankings_provider_breakdown(self):
        vdata = stats.load_verified_rankings()
        output = stats.render_verified_rankings(vdata)
        # pick has 3 providers, should show provider breakdown
        self.assertIn("By provider:", output)
        self.assertIn("Claude Code:", output)

    def test_render_verified_rankings_skips_empty_op(self):
        # Overwrite models to have only empty verifiedstats
        metadata = self.base / "aitasks" / "metadata"
        (metadata / "models_codex.json").write_text(
            json.dumps({"models": [{"name": "gpt5_4", "cli_id": "gpt-5.4", "verifiedstats": {}}]}),
            encoding="utf-8",
        )
        (metadata / "models_claudecode.json").write_text(
            json.dumps({"models": [
                {"name": "opus4_6", "cli_id": "claude-opus-4-6"},
                {"name": "opus4_7", "cli_id": "claude-opus-4-7", "verifiedstats": {}},
            ]}),
            encoding="utf-8",
        )
        (metadata / "models_opencode.json").write_text(
            json.dumps({"models": []}),
            encoding="utf-8",
        )
        vdata = stats.load_verified_rankings()
        self.assertEqual(vdata.operations, [])
        output = stats.render_verified_rankings(vdata)
        self.assertEqual(output, "")

    def test_bucket_avg(self):
        self.assertEqual(stats.bucket_avg(0, 0), 0)
        self.assertEqual(stats.bucket_avg(3, 240), 80)
        self.assertEqual(stats.bucket_avg(10, 960), 96)


# --------------------------------------------------------------------------
# Backlog sections, flags and CSV (t1544_4). The data-layer arithmetic is
# already pinned by tests/test_stats_multistage.py -- everything here is about
# RENDERING, the CLI surface and the exported contract.
# --------------------------------------------------------------------------

_BACKLOG_TODAY = date(2026, 3, 5)   # a Thursday; week (dow=1) starts 2026-03-02
_BACKLOG_DOW = 1


def _section(report, heading):
    """Slice one '### ' section out of a rendered report."""
    return report.split(heading)[1].split("\n###")[0]


def _table_headers(section):
    """The column labels of a rendered backlog table, in emission order."""
    return [c.strip() for c in section.splitlines()[1].strip().strip("|").split("|")][1:]


def _table_rows(section):
    """{label: [cells]} for every pipe row except the header and separator."""
    rows = {}
    for line in section.splitlines():
        if not line.startswith("| ") or line.startswith("| Category"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows[cells[0]] = cells[1:]
    return rows


def _synthetic_stats(arrivals=None, departures=None, excluded=None):
    """An empty StatsData with only the backlog counters populated."""
    data = stats_data_mod._empty_stats_data()
    data.backlog_arrivals.update(arrivals or {})
    data.backlog_departures.update(departures or {})
    data.backlog_excluded.update(excluded or {})
    for (cat, off), n in (arrivals or {}).items():
        data.backlog_scope_arrivals[("parent", off)] += n
    for (cat, off), n in (departures or {}).items():
        data.backlog_scope_departures[("parent", off)] += n
    return data


def _render_level(data, weeks=8):
    out = io.StringIO()
    axis = stats._build_backlog_axis(data, stats.backlog_week_offsets(weeks))
    stats.render_backlog_level(axis, data, out, _BACKLOG_TODAY, _BACKLOG_DOW)
    return out.getvalue()


class TestBacklogSections(unittest.TestCase):
    """Fixture-backed rendering tests with their own tree.

    Deliberately does NOT extend TestCollection's fixture: those six tests pin
    an archive with no created_at, and widening it would churn them.
    """

    LEVEL_H = "### Backlog Level (Open Tasks) - Weekly (Last 8 Weeks)"
    FLOW_H = "### Backlog Net Flow (Arrivals - Departures) - Weekly (Last 8 Weeks)"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        tasks = self.base / "aitasks"
        archived = tasks / "archived"
        archived.mkdir(parents=True)
        (tasks / "metadata").mkdir()

        def write(path, **fm):
            body = fm.pop("body", "Body.")
            text = "---\n" + "".join(f"{k}: {v}\n" for k, v in fm.items()) + "---\n" + body + "\n"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

        # Live/open. alpha and beta share an arrival WEEK with different
        # categories -- the discriminating case for the all-tasks re-key: a dict
        # comprehension would keep only one of them and TOTAL OPEN would then
        # disagree with parents + children.
        write(tasks / "t10_alpha.md", status="Ready", created_at="2026-02-18 09:00", issue_type="feature")
        write(tasks / "t11_beta.md", status="Ready", created_at="2026-02-18 09:00", issue_type="bug")
        write(tasks / "t10" / "t10_1_child.md", status="Ready", created_at="2026-02-18 09:00", issue_type="feature")
        write(
            tasks / "t12_mv.md",
            status="Ready", created_at="2026-02-25 09:00",
            issue_type="chore", followup_kind="manual_verification",
        )
        # Excluded: no created_at at all.
        write(tasks / "t14_missing.md", status="Ready", issue_type="feature")

        # Archived. `churn` arrives and departs in the SAME week, so its level
        # is 0 at every rendered offset while its flow is real -- the row a
        # level-based suppression would wrongly hide from the flow table.
        write(
            archived / "t20_churn.md",
            status="Done", created_at="2026-02-17 09:00", completed_at="2026-02-19 09:00", issue_type="chore",
        )
        # Departs a week after it is still open, giving a NEGATIVE net at
        # offset 1 -- the discriminating case for an inverted sign.
        write(
            archived / "t21_doc.md",
            status="Done", created_at="2026-02-10 09:00", completed_at="2026-02-25 09:00", issue_type="documentation",
        )

        self.orig = (stats.TASK_DIR, stats.ARCHIVE_DIR, stats.TASK_TYPES_FILE)
        for mod in (stats, stats_data_mod):
            mod.TASK_DIR = tasks
            mod.ARCHIVE_DIR = archived
            mod.TASK_TYPES_FILE = tasks / "metadata" / "task_types.txt"

        self.data = stats.collect_stats(today=_BACKLOG_TODAY, week_start_dow=_BACKLOG_DOW)
        self.report = stats.render_text_report(
            self.data, days=7, verbose=False, week_start_dow=_BACKLOG_DOW, today=_BACKLOG_TODAY
        )

    def tearDown(self):
        for mod in (stats, stats_data_mod):
            mod.TASK_DIR, mod.ARCHIVE_DIR, mod.TASK_TYPES_FILE = self.orig
        self.tmp.cleanup()

    def test_both_sections_render_with_the_unified_category_axis(self):
        self.assertIn(self.LEVEL_H, self.report)
        self.assertIn(self.FLOW_H, self.report)
        rows = _table_rows(_section(self.report, self.LEVEL_H))
        # Follow-up kinds render lowercase, issue types Title Case via the
        # display map -- a bare .capitalize() here would regress t1577.
        self.assertIn("manual verification", rows)
        self.assertIn("Features", rows)
        self.assertIn("Bug Fixes", rows)

    def test_totals_reconcile_across_all_three_axes(self):
        section = _section(self.report, self.LEVEL_H)
        rows = _table_rows(section)
        # Resolve the column by HEADER, never by a hardcoded index: the layout
        # is chronological with "Now" last, and an index would silently read a
        # different week if the column order ever changes again.
        now_col = _table_headers(section).index("Now")
        now = lambda label: int(rows[label][now_col])  # noqa: E731
        self.assertEqual(now("-- follow-ups") + now("-- genuine"), now("TOTAL OPEN"))
        self.assertEqual(now("of which parents") + now("of which children"), now("TOTAL OPEN"))
        self.assertEqual(now("TOTAL OPEN"), 4)   # alpha, beta, child, mv
        self.assertEqual(now("of which children"), 1)

    def test_all_tasks_axis_sums_categories_sharing_a_week(self):
        """The discriminating assertion for the re-key.

        alpha (type:feature) and beta (type:bug) both arrive in week offset 2.
        A dict comprehension over the flows keeps only the last, so TOTAL OPEN
        would read 1 short at every offset from 2 onward.
        """
        rows = _table_rows(_section(self.report, self.LEVEL_H))
        headers = _table_headers(_section(self.report, self.LEVEL_H))
        col = headers.index("W-2")
        # alpha + beta + child (all created that week) + doc (created earlier,
        # not yet departed). churn arrived and departed inside the week, so it
        # contributes 0.
        self.assertEqual(int(rows["TOTAL OPEN"][col]), 4)
        # The two independent cross-checks. Under the dict-comprehension bug the
        # aggregate keeps one arbitrary category's arrivals for this offset, so
        # TOTAL OPEN reads 1-2 and both of these break.
        self.assertEqual(
            int(rows["of which parents"][col]) + int(rows["of which children"][col]),
            int(rows["TOTAL OPEN"][col]),
        )
        self.assertEqual(
            int(rows["-- follow-ups"][col]) + int(rows["-- genuine"][col]),
            int(rows["TOTAL OPEN"][col]),
        )

    def test_zero_level_category_with_flow_appears_only_in_the_flow_table(self):
        """Row membership is per-table, not shared.

        `Chores` arrives and departs in one week: level 0 everywhere, real flow.
        Reusing the level table's all-zero suppression here deletes the row.
        """
        self.assertNotIn("Chores", _table_rows(_section(self.report, self.LEVEL_H)))
        self.assertIn("Chores", _table_rows(_section(self.report, self.FLOW_H)))

    def test_level_table_runs_chronologically_with_now_last(self):
        headers = _table_headers(_section(self.report, self.LEVEL_H))
        self.assertEqual(headers[0], "W-7")
        self.assertEqual(headers[-1], "Now")
        self.assertEqual(headers, [f"W-{o}" for o in range(7, 0, -1)] + ["Now"])
        # A level is a stock and is correct as-of-now, so it carries NO partial
        # marker -- that asterisk belongs to the flow table alone.
        self.assertNotIn("Now*", headers)

    def test_both_tables_share_one_column_layout(self):
        """The two tables are meant to be read stacked, so their columns must
        line up. Only the current-week label differs (`Now` vs `Now*`)."""
        level = _table_headers(_section(self.report, self.LEVEL_H))
        flow = _table_headers(_section(self.report, self.FLOW_H))
        self.assertEqual(level[:-1], flow[:-1])
        self.assertEqual((level[-1], flow[-1]), ("Now", "Now*"))

    def test_flow_table_puts_the_partial_week_last_and_marks_it(self):
        section = _section(self.report, self.FLOW_H)
        headers = _table_headers(section)
        self.assertEqual(headers[-1], "Now*")
        self.assertEqual(headers[0], "W-7")
        # A flow covers a span, so the marker names a range.
        self.assertIn("_Now* covers 2026-03-02..2026-03-05 (partial week)._", section)

    def test_flow_table_carries_a_negative_net(self):
        section = _section(self.report, self.FLOW_H)
        headers = _table_headers(section)
        rows = _table_rows(section)
        self.assertEqual(rows["Documentation"][headers.index("W-1")], "-1")

    def test_exclusion_tally_is_reported_with_reason_and_count(self):
        section = _section(self.report, self.LEVEL_H)
        self.assertIn("no_created_at: 1", section)
        self.assertIn("Excluded from the backlog series: 1 task(s)", section)
        # negative_level counts CELLS, never tasks -- it must not appear in the
        # task tally, and nothing clamps on this fixture.
        self.assertNotIn("Clamped negative level cells", section)

    def test_backlog_csv_is_a_complete_dense_series(self):
        axis = stats._build_backlog_axis(self.data, stats.backlog_week_offsets(8))
        out = self.base / "backlog.csv"
        stats.write_backlog_csv(out, self.data, axis, _BACKLOG_TODAY, _BACKLOG_DOW)
        with out.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))

        self.assertEqual(rows[0], ["week_ending", "category", "open", "arrived", "departed", "net"])

        offsets = stats.backlog_week_offsets(8)
        categories = {c for c, _ in self.data.backlog_arrivals} | {c for c, _ in self.data.backlog_departures}

        # The COMPLETE expected row set, built independently of the writer from
        # the documented contract. A len() plus two membership checks would pass
        # against display labels on unasserted categories, dropped zero rows,
        # swapped arrived/departed, or an inverted net -- comparing the whole
        # set of tuples catches all four at once.
        expected = set()
        for offset in offsets:
            ending = stats.week_end_for_offset(_BACKLOG_TODAY, _BACKLOG_DOW, offset).isoformat()
            for category in categories:
                arrived = self.data.backlog_arrivals.get((category, offset), 0)
                departed = self.data.backlog_departures.get((category, offset), 0)
                expected.add((
                    ending,
                    category,                                   # raw namespaced key, never a display name
                    str(axis.levels.get((category, offset), 0)),
                    str(arrived),
                    str(departed),
                    str(arrived - departed),
                ))
        self.assertEqual({tuple(r) for r in rows[1:]}, expected)
        # Dense: every category x every rendered week, zero cells included. (Set
        # equality alone would tolerate duplicate rows, so pin the count too.)
        self.assertEqual(len(rows) - 1, len(categories) * len(offsets))

        # Emission order is GLOBALLY non-decreasing by week, not merely
        # "oldest first": a category-major emission still starts at the oldest
        # week while interleaving every later one.
        weeks = [r[0] for r in rows[1:]]
        self.assertEqual(weeks, sorted(weeks))
        # Unclamped canonical week end -- in the FUTURE for the current week.
        # Clamping it to today would export one calendar week under two
        # different dates on two different days, silently breaking joins.
        self.assertEqual(weeks[-1], "2026-03-08")

        # Spot values from fixture knowledge, so the set above is not purely
        # self-referential. arrived/departed are not interchangeable: doc
        # departs in a week it did not arrive; feature arrives twice in one.
        by_key = {(r[0], r[1]): r for r in rows[1:]}
        self.assertEqual(tuple(by_key[("2026-03-01", "type:documentation")][2:]), ("0", "0", "1", "-1"))
        self.assertEqual(tuple(by_key[("2026-02-22", "type:feature")][2:]), ("2", "2", "0", "2"))
        self.assertEqual(tuple(by_key[("2026-02-22", "type:chore")][2:]), ("0", "1", "1", "0"))

    def test_backlog_csv_open_minus_next_equals_net(self):
        """The exported identity, on a clamp-free fixture.

        open[w] - open[w+1] == net[w] for every offset except the oldest
        rendered one, which has no cell past the horizon to subtract.
        """
        axis = stats._build_backlog_axis(self.data, stats.backlog_week_offsets(8))
        self.assertEqual(axis.clamped_cells, 0)
        out = self.base / "backlog2.csv"
        stats.write_backlog_csv(out, self.data, axis, _BACKLOG_TODAY, _BACKLOG_DOW)
        with out.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        offsets = stats.backlog_week_offsets(8)
        ends = {o: stats.week_end_for_offset(_BACKLOG_TODAY, _BACKLOG_DOW, o).isoformat() for o in offsets}
        table = {(r["week_ending"], r["category"]): r for r in rows}
        checked = 0
        for category in {r["category"] for r in rows}:
            for older, newer in zip(offsets, offsets[1:]):   # oldest -> newest
                cur, prev = table[(ends[newer], category)], table[(ends[older], category)]
                self.assertEqual(
                    int(cur["open"]) - int(prev["open"]), int(cur["net"]),
                    msg=f"{category} at {ends[newer]}",
                )
                checked += 1
        self.assertGreater(checked, 0)


class TestBacklogRendering(unittest.TestCase):
    """Renderer-level tests driven by synthetic counters.

    Magnitudes like a five-digit level are unreachable through a file fixture,
    and the layout contract is a property of the renderer, not of the corpus.
    """

    LEVEL_H = "### Backlog Level (Open Tasks) - Weekly (Last 8 Weeks)"

    def test_default_horizon_table_is_exactly_80_chars(self):
        report = _render_level(_synthetic_stats({("type:feature", 4): 12, ("kind:docs_gap", 2): 3}))
        pipe_rows = [ln for ln in report.splitlines() if ln.startswith("|")]
        self.assertTrue(pipe_rows)
        self.assertEqual({len(ln) for ln in pipe_rows}, {80})

    def test_five_digit_values_widen_every_row_uniformly(self):
        """`f"{v:>4}"` widens rather than truncating, so the guarantee is that
        the table stays ALIGNED, not that it stays 80 characters."""
        report = _render_level(_synthetic_stats({("type:feature", 4): 12345}))
        pipe_rows = [ln for ln in report.splitlines() if ln.startswith("|")]
        widths = {len(ln) for ln in pipe_rows}
        self.assertEqual(len(widths), 1, msg=f"ragged table: {sorted(widths)}")
        self.assertNotEqual(widths.pop(), 80)
        self.assertIn("12345", report)

    def test_over_long_category_label_is_truncated_not_wrapped(self):
        long_type = "a" * 40
        report = _render_level(_synthetic_stats({(f"type:{long_type}", 3): 1}))
        pipe_rows = [ln for ln in report.splitlines() if ln.startswith("|")]
        self.assertEqual({len(ln) for ln in pipe_rows}, {80})
        self.assertIn("| " + ("A" + "a" * 19)[:20] + " |", report)

    def test_empty_state_still_surfaces_the_exclusion_tally(self):
        """The tally is the EXPLANATION for the table's absence, not a footnote
        of it -- main()'s has_backlog predicate admits such a repo precisely
        because these counters are non-empty."""
        report = _render_level(_synthetic_stats(excluded={"no_created_at": 7, "folded": 2}))
        self.assertIn("No open tasks could be placed in the backlog series.", report)
        self.assertIn("no_created_at: 7", report)
        self.assertIn("folded: 2", report)
        self.assertIn("9 task(s)", report)

    def test_empty_state_without_exclusions_says_so(self):
        report = _render_level(_synthetic_stats())
        self.assertIn("No open tasks found.", report)
        self.assertNotIn("Excluded from the backlog series", report)

    def test_clamped_cells_are_reported_separately_from_tasks(self):
        # A departure with no matching arrival forces a negative raw level.
        report = _render_level(_synthetic_stats(departures={("type:feature", 2): 3}))
        self.assertIn("Clamped negative level cells", report)
        # ... and is never summed into a task count.
        self.assertNotIn("task(s)", report.split("Clamped")[1])



class TestBacklogFlags(unittest.TestCase):
    def test_backlog_weeks_default_is_the_shared_constant(self):
        """Asserted against the CONSTANT, not the literal 8.

        The stats TUI pane reads the same constant; a literal default here is
        exactly how two surfaces drift into different windows for one metric.
        """
        args = stats.parse_args([])
        self.assertIs(args.backlog_weeks, stats_data_mod.BACKLOG_WEEKS_DEFAULT)

    def test_backlog_weeks_bounds(self):
        for accepted in (1, 8, 26, 99):
            self.assertEqual(stats.parse_args(["--backlog-weeks", str(accepted)]).backlog_weeks, accepted)
        # 0 would make backlog_week_offsets() return [] -- a header row with no
        # data columns. 100 would print `W-100`, wider than the 4-char cell.
        for rejected in ("0", "-1", "100", "abc"):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                stats.parse_args(["--backlog-weeks", rejected])

    def test_bare_csv_flags_use_distinct_defaults(self):
        """A missing `const` makes the bare flag parse identically to an omitted
        one -- exit 0, no file, no message. Assert the value, and assert it is
        not None, so a dropped const cannot pass."""
        backlog = stats.parse_args(["--csv-backlog"]).csv_backlog
        self.assertIsNotNone(backlog)
        self.assertEqual(backlog, "aitask_backlog.csv")
        self.assertEqual(stats.parse_args(["--csv"]).csv, "aitask_stats.csv")
        # ... and the two defaults must differ, or the bare pair would collide.
        both = stats.parse_args(["--csv", "--csv-backlog"])
        self.assertNotEqual(both.csv, both.csv_backlog)

    def test_colliding_csv_paths_are_refused_including_aliases(self):
        for pair in (
            ["--csv", "out.csv", "--csv-backlog", "out.csv"],
            ["--csv", "out.csv", "--csv-backlog", "./out.csv"],
            ["--csv", "out.csv", "--csv-backlog", "sub/../out.csv"],
        ):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                stats.parse_args(pair)


class TestMainDegenerateStates(unittest.TestCase):
    """The two early-return messages, plus the cases that must bypass them.

    Neither message had any test before t1544_4, so a regression shipped
    silently; these are the first.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.tasks = self.base / "aitasks"
        self.archived = self.tasks / "archived"
        self.tasks.mkdir()
        self.orig = (stats.TASK_DIR, stats.ARCHIVE_DIR, stats.TASK_TYPES_FILE)
        for mod in (stats, stats_data_mod):
            mod.TASK_DIR = self.tasks
            mod.ARCHIVE_DIR = self.archived
            mod.TASK_TYPES_FILE = self.tasks / "metadata" / "task_types.txt"

    def tearDown(self):
        for mod in (stats, stats_data_mod):
            mod.TASK_DIR, mod.ARCHIVE_DIR, mod.TASK_TYPES_FILE = self.orig
        self.tmp.cleanup()

    def _write(self, name, **fm):
        path = self.tasks / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + "".join(f"{k}: {v}\n" for k, v in fm.items()) + "---\nBody.\n", encoding="utf-8")

    def _run(self, argv=()):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = stats.main(list(argv))
        return rc, buf.getvalue()

    def test_open_tasks_with_no_archive_render_the_backlog_section(self):
        """total_tasks counts ARCHIVED tasks only, so a young repo with open
        work and no archive -- the repo that most needs this report -- used to
        print 'No completed tasks found.' and exit."""
        self._write("t1_open.md", status="Ready", created_at="2026-02-18 09:00", issue_type="feature")
        rc, out = self._run()
        self.assertEqual(rc, 0)
        self.assertNotIn("No completed tasks found.", out)
        self.assertNotIn("No archived tasks found", out)
        self.assertIn("### Backlog Level (Open Tasks)", out)
        self.assertIn("TOTAL OPEN", out)

    def test_all_excluded_repo_names_the_reason_and_count(self):
        """The discriminating case for the has_backlog predicate.

        No arrivals and no levels, so a bare early-returning empty state would
        render a heading and nothing else -- passing a 'section renders' check
        while hiding the tasks and the reason they were dropped.
        """
        self._write("t1_nocreated.md", status="Ready", issue_type="feature")
        self._write("t2_nocreated.md", status="Ready", issue_type="bug")
        rc, out = self._run()
        self.assertEqual(rc, 0)
        self.assertNotIn("No completed tasks found.", out)
        self.assertIn("### Backlog Level (Open Tasks)", out)
        self.assertIn("no_created_at: 2", out)
        self.assertIn("2 task(s)", out)

    def test_repo_with_nothing_prints_the_original_messages_verbatim(self):
        rc, out = self._run()
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), f"No archived tasks found in {self.archived}")

        # ... and with an archive directory present but empty, the other one.
        self.archived.mkdir()
        rc, out = self._run()
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "No completed tasks found.")

    def test_bare_csv_flags_write_two_files_and_do_not_collide(self):
        self._write("t1_open.md", status="Ready", created_at="2026-02-18 09:00", issue_type="feature")
        cwd = os.getcwd()
        os.chdir(self.base)
        try:
            rc, _ = self._run(["--csv", "--csv-backlog"])
        finally:
            os.chdir(cwd)
        self.assertEqual(rc, 0)
        self.assertTrue((self.base / "aitask_stats.csv").exists())
        self.assertTrue((self.base / "aitask_backlog.csv").exists())

    def test_colliding_paths_leave_both_files_untouched(self):
        """The guard is a preflight: write_csv is the last statement in main(),
        so a collision caught at the writers would already have destroyed the
        requested task CSV."""
        self._write("t1_open.md", status="Ready", created_at="2026-02-18 09:00", issue_type="feature")
        target = self.base / "out.csv"
        target.write_text("SENTINEL\n", encoding="utf-8")
        before = target.read_bytes()
        # The alias forms must be resolved against the same cwd, or they simply
        # name two different files and the test proves nothing.
        cwd = os.getcwd()
        os.chdir(self.base)
        try:
            with self.assertRaises(SystemExit) as ctx, contextlib.redirect_stderr(io.StringIO()):
                self._run(["--csv", "out.csv", "--csv-backlog", "./out.csv"])
        finally:
            os.chdir(cwd)
        self.assertNotEqual(ctx.exception.code, 0)
        # Untouched: without the preflight, main() writes the fact table to this
        # path first and only then overwrites it with the backlog export.
        self.assertEqual(target.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
