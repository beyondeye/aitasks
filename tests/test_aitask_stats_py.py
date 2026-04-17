"""Unit tests for .aitask-scripts/aitask_stats.py."""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
from datetime import date
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch


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
        (metadata / "models_geminicli.json").write_text(
            json.dumps({"models": [{"name": "gemini2_5pro", "cli_id": "gemini-2.5-pro"}]}),
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

        stats.TASK_DIR = self.base / "aitasks"
        stats.ARCHIVE_DIR = stats.TASK_DIR / "archived"
        stats.TASK_TYPES_FILE = stats.TASK_DIR / "metadata" / "task_types.txt"

    def tearDown(self):
        stats.TASK_DIR = self.orig_task_dir
        stats.ARCHIVE_DIR = self.orig_archive_dir
        stats.TASK_TYPES_FILE = self.orig_task_types
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
        self.assertEqual(len(data.csv_rows[0]), 10)

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
            ],
        )
        self.assertIn(
            ["2026-03-04", "Wed", "0", "t4_legacy_impl", "epsilon", "feature", "parent", "codex/gpt-5", "codex", "gpt5"],
            rows[1:],
        )

    def test_run_plot_summary_uses_descriptive_titles(self):
        data = stats.collect_stats(today=date(2026, 3, 5), week_start_dow=1)
        titles = []
        plot_sizes = []

        class FakePlotext:
            def clear_figure(self):
                pass

            def plotsize(self, width, height):
                plot_sizes.append((width, height))

            def title(self, value):
                titles.append(value)

            def plot(self, *args, **kwargs):
                pass

            def xticks(self, *args, **kwargs):
                pass

            def bar(self, *args, **kwargs):
                pass

            def theme(self, *args, **kwargs):
                pass

            def show(self):
                pass

        fake_plotext = FakePlotext()

        with patch.dict(sys.modules, {"plotext": types.SimpleNamespace(
            clear_figure=fake_plotext.clear_figure,
            plotsize=fake_plotext.plotsize,
            title=fake_plotext.title,
            plot=fake_plotext.plot,
            xticks=fake_plotext.xticks,
            bar=fake_plotext.bar,
            theme=fake_plotext.theme,
            show=fake_plotext.show,
        )}), patch.object(stats.shutil, "get_terminal_size", return_value=types.SimpleNamespace(columns=100, lines=30)), patch("sys.stdout", new_callable=io.StringIO) as stdout:
            stats.run_plot_summary(data, days=7, today=date(2026, 3, 5), week_start_dow=1)

        self.assertEqual(len(titles), 8)
        self.assertEqual(plot_sizes, [(100, 25)] * 8)
        self.assertEqual(stdout.getvalue(), "\n\n" * 8)
        self.assertIn("Daily Completions - last 7 days", titles)
        self.assertIn(
            "Average Completions by Weekday - last 30 days (week starts Monday)",
            titles,
        )
        self.assertIn("Top Labels by Completed Tasks - all time", titles)
        self.assertIn("Issue Types - this week (week starts Monday)", titles)
        self.assertIn(
            "Code Agents by Completed Tasks - last 4 weeks (week starts Monday)",
            titles,
        )
        self.assertIn(
            "Code Agents by Completed Tasks - this week (week starts Monday)",
            titles,
        )
        self.assertIn(
            "LLM Models by Completed Tasks - last 4 weeks (week starts Monday)",
            titles,
        )
        self.assertIn(
            "LLM Models by Completed Tasks - this week (week starts Monday)",
            titles,
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

        (metadata / "models_geminicli.json").write_text(
            json.dumps({"models": [{"name": "gemini2_5pro", "cli_id": "gemini-2.5-pro"}]}),
            encoding="utf-8",
        )

        self.orig_task_dir = stats.TASK_DIR
        stats.TASK_DIR = self.base / "aitasks"

    def tearDown(self):
        stats.TASK_DIR = self.orig_task_dir
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

    def test_verified_plots_chart_count(self):
        vdata = stats.load_verified_rankings()
        titles = []

        class FakePlotext:
            def clear_figure(self): pass
            def plotsize(self, w, h): pass
            def title(self, v): titles.append(v)
            def plot(self, *a, **k): pass
            def xticks(self, *a, **k): pass
            def bar(self, *a, **k): pass
            def theme(self, *a, **k): pass
            def show(self): pass

        fake = FakePlotext()
        with patch.dict(sys.modules, {"plotext": types.SimpleNamespace(
            clear_figure=fake.clear_figure, plotsize=fake.plotsize,
            title=fake.title, plot=fake.plot, xticks=fake.xticks,
            bar=fake.bar, theme=fake.theme, show=fake.show,
        )}), patch("sys.stdout", new_callable=io.StringIO):
            stats.run_verified_plots(vdata)

        # 2 operations (explain, pick) -> 2 charts
        self.assertEqual(len(titles), 2)
        self.assertTrue(any("pick" in t for t in titles))
        self.assertTrue(any("explain" in t for t in titles))


if __name__ == "__main__":
    unittest.main()
