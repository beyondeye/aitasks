"""Unit tests for .aitask-scripts/aitask_stats.py."""

from __future__ import annotations

import csv
import importlib.util
import io
import json
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
            json.dumps({"models": [{"name": "opus4_6", "cli_id": "claude-opus-4-6"}]}),
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

        tar_path = archived / "old.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tf:
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
            tf.add(old, arcname="aitasks/archived/t2_old_task.md")

        self.orig_task_dir = stats.TASK_DIR
        self.orig_archive_dir = stats.ARCHIVE_DIR
        self.orig_archive_tar = stats.ARCHIVE_TAR
        self.orig_task_types = stats.TASK_TYPES_FILE

        stats.TASK_DIR = self.base / "aitasks"
        stats.ARCHIVE_DIR = stats.TASK_DIR / "archived"
        stats.ARCHIVE_TAR = stats.ARCHIVE_DIR / "old.tar.gz"
        stats.TASK_TYPES_FILE = stats.TASK_DIR / "metadata" / "task_types.txt"

    def tearDown(self):
        stats.TASK_DIR = self.orig_task_dir
        stats.ARCHIVE_DIR = self.orig_archive_dir
        stats.ARCHIVE_TAR = self.orig_archive_tar
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


if __name__ == "__main__":
    unittest.main()
