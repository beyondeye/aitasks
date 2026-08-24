"""Unit tests for the stats TUI backlog panes (t1544_5).

Covers the pure row-derivation half of `.aitask-scripts/stats/panes/backlog.py`
(no Textual app needed), the pane registration that guards the eager-import trap,
and the `stats_config` preset-precedence contract.

The live-render half — real widget mounting, the empty-path message, and the
`#content` height budget — is `tests/test_stats_backlog_panes_live.py`.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, cast

PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_DIR / ".aitask-scripts"
for _p in (str(SCRIPTS), str(SCRIPTS / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from stats import stats_config  # noqa: E402
from stats.panes import PANE_DEFS  # noqa: E402  (side-effect: registers every pane)
from stats.panes import backlog as bk  # noqa: E402
import stats_data  # noqa: E402
from config_utils import load_layered_config  # noqa: E402


def _load_cli():
    """Load `aitask_stats.py` the way `tests/test_aitask_stats_py.py` does."""
    script = SCRIPTS / "aitask_stats.py"
    spec = importlib.util.spec_from_file_location("aitask_stats_py_backlog", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CLI = cast(Any, _load_cli())


def _stats(
    arrivals: Dict[tuple, int] | None = None,
    departures: Dict[tuple, int] | None = None,
    scope_arrivals: Dict[tuple, int] | None = None,
    scope_departures: Dict[tuple, int] | None = None,
    excluded: Dict[str, int] | None = None,
) -> stats_data.StatsData:
    """A `StatsData` carrying only the backlog counters these panes read.

    Every non-backlog field is zero/empty: the panes read nothing else, and an
    empty corpus keeps the CLI parity fixtures small.
    """
    d = stats_data.StatsData(
        total_tasks=0,
        tasks_7d=0,
        tasks_30d=0,
        daily_counts=Counter(),
        daily_tasks={},
        dow_counts_thisweek=Counter(),
        dow_counts_30d=Counter(),
        dow_counts_total=Counter(),
        label_counts_total=Counter(),
        label_week_counts=Counter(),
        label_dow_counts_30d=Counter(),
        type_week_counts=Counter(),
        label_type_week_counts=Counter(),
        codeagent_week_counts=Counter(),
        model_week_counts=Counter(),
        all_labels=set(),
        all_codeagents=set(),
        all_models=set(),
        codeagent_display_names={},
        model_display_names={},
        csv_rows=[],
    )
    d.backlog_arrivals = Counter(arrivals or {})
    d.backlog_departures = Counter(departures or {})
    d.backlog_scope_arrivals = Counter(scope_arrivals or {})
    d.backlog_scope_departures = Counter(scope_departures or {})
    d.backlog_excluded = Counter(excluded or {})
    return d


def _rows_by_label(rows: List[tuple]) -> Dict[str, List[str]]:
    return {label: cells for label, cells in rows}


def _parse_cli_table(text: str) -> tuple[List[str], Dict[str, List[str]]]:
    """`(headers, {row_label: cells})` from a rendered CLI pipe table."""
    lines = [ln for ln in text.splitlines() if ln.startswith("|")]
    cells = [[c.strip() for c in ln.strip("|").split("|")] for ln in lines]
    # Drop the `|---|---|` separator row.
    body = [row for row in cells if not set("".join(row)) <= {"-"}]
    headers = body[0][1:]
    return headers, {row[0]: row[1:] for row in body[1:]}


class TestPaneRegistration(unittest.TestCase):
    """The eager-import trap: a module missing from `stats/panes/__init__.py`
    never registers, and a wrong entry is a ModuleNotFoundError that stops the
    whole TUI from starting."""

    def test_backlog_panes_are_registered(self):
        """Importing ONLY the package must register both panes.

        Run in a subprocess on purpose. This module imports
        `stats.panes.backlog` directly for the row functions, and that import
        alone runs `register()` — so an in-process assertion on `PANE_DEFS`
        would pass even with the module missing from the eager-import list,
        which is exactly the trap this test exists to catch.
        """
        code = (
            "import sys;"
            f"sys.path[:0]=[{str(SCRIPTS)!r},{str(SCRIPTS / 'lib')!r}];"
            "from stats.panes import PANE_DEFS;"
            "print(int('backlog.level' in PANE_DEFS and 'backlog.netflow' in PANE_DEFS))"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, cwd=PROJECT_DIR
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "1", proc.stdout + proc.stderr)

    def test_registered_panes_share_the_backlog_category(self):
        self.assertEqual(PANE_DEFS["backlog.level"].category, "Backlog")
        self.assertEqual(PANE_DEFS["backlog.netflow"].category, "Backlog")


class TestPresetPrecedence(unittest.TestCase):
    """The layered-config contract, asserted on the EFFECTIVE config.

    Never an equality test between `DEFAULT_PRESETS` and the JSON literal — that
    would lock the duplication in permanently.
    """

    def test_backlog_preset_is_in_the_effective_config(self):
        self.assertEqual(
            stats_config.load()["presets"]["backlog"],
            ["backlog.level", "backlog.netflow"],
        )

    def test_a_json_preset_list_replaces_the_code_list(self):
        """`deep_merge` merges dicts per key but REPLACES lists.

        This is the real, unnoticed drift: a pane added to an EXISTING code
        preset is silently masked for any project whose JSON pins that preset.
        The test pins the behaviour; it does not change it.
        """
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "stats_config.json"
            project.write_text(
                json.dumps({"presets": {"overview": ["overview.summary"]}}),
                encoding="utf-8",
            )
            merged = load_layered_config(
                project,
                local_path=Path(tmp) / "absent.local.json",
                defaults=stats_config.DEFAULTS,
            )
        self.assertEqual(merged["presets"]["overview"], ["overview.summary"])
        self.assertNotEqual(
            merged["presets"]["overview"], stats_config.DEFAULT_PRESETS["overview"]
        )

    def test_backlog_survives_an_existing_json_presets_block(self):
        """Adding the pane cannot discard a user's layout overrides."""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "stats_config.json"
            project.write_text(
                json.dumps({"presets": {"overview": ["overview.summary"]}}),
                encoding="utf-8",
            )
            merged = load_layered_config(
                project,
                local_path=Path(tmp) / "absent.local.json",
                defaults=stats_config.DEFAULTS,
            )
        self.assertEqual(
            merged["presets"]["backlog"], ["backlog.level", "backlog.netflow"]
        )
        self.assertEqual(merged["presets"]["overview"], ["overview.summary"])


class TestHorizon(unittest.TestCase):
    def test_pane_horizon_tracks_the_shared_constant(self):
        """Both row functions default to `stats_data.BACKLOG_WEEKS_DEFAULT`.

        What this does NOT buy: it cannot distinguish a read of the constant from
        a hardcoded `8` today, because both compare equal. It is a DRIFT guard —
        it goes red the day `BACKLOG_WEEKS_DEFAULT` changes and a pane-local
        literal stays behind, which is exactly the CLI/TUI divergence the task
        forbids.
        """
        import inspect

        for fn in (bk._level_rows, bk._netflow_rows):
            default = inspect.signature(fn).parameters["weeks"].default
            self.assertEqual(default, stats_data.BACKLOG_WEEKS_DEFAULT, fn.__name__)

    def test_row_functions_emit_one_column_per_horizon_week(self):
        d = _stats(arrivals={("type:feature", 3): 2})
        headers, _rows, _diag = bk._level_rows(d)
        labels, _totals, _sl, _sv = bk._netflow_rows(d)
        self.assertEqual(len(headers), stats_data.BACKLOG_WEEKS_DEFAULT)
        self.assertEqual(len(labels), stats_data.BACKLOG_WEEKS_DEFAULT)


class TestSharedCounterIsNotMutated(unittest.TestCase):
    def test_rendering_does_not_mutate_the_shared_exclusion_counter(self):
        """`stats_app` re-renders against ONE cached StatsData on every pane
        switch, so an `excluded=stats.backlog_excluded` sink would accumulate
        `negative_level` for the life of the session."""
        d = _stats(
            arrivals={("type:feature", 4): 1},
            # Departures with no matching arrival force a clamped negative level.
            departures={("type:bug", 5): 3},
            excluded={"folded": 2},
        )
        before = Counter(d.backlog_excluded)
        for _ in range(3):
            bk._level_rows(d)
            bk._netflow_rows(d)
        self.assertEqual(d.backlog_excluded, before)
        self.assertNotIn("negative_level", d.backlog_excluded)


class TestRowMembership(unittest.TestCase):
    def test_zero_level_category_with_flow_is_a_netflow_row(self):
        """The live `kind:docs_gap` case: equal arrivals and departures in one
        week means a level of zero at every offset but real flow. The level table
        suppresses it; the flow table must not."""
        d = _stats(
            arrivals={("type:feature", 4): 5, ("kind:docs_gap", 4): 3},
            departures={("kind:docs_gap", 4): 3},
        )
        _headers, level_rows, _diag = bk._level_rows(d)
        _labels, _totals, series_labels, _sv = bk._netflow_rows(d)

        self.assertNotIn("docs gap", _rows_by_label(level_rows))
        self.assertIn("docs gap", series_labels)

    def test_netflow_totals_count_the_zero_net_category(self):
        d = _stats(
            arrivals={("type:feature", 4): 5, ("kind:docs_gap", 4): 3},
            departures={("kind:docs_gap", 4): 3},
        )
        labels, totals, _sl, _sv = bk._netflow_rows(d)
        col = labels.index("W-4")
        by_label = _rows_by_label(totals)
        self.assertEqual(by_label["ARRIVALS"][col], "8")
        self.assertEqual(by_label["DEPARTURES"][col], "3")
        self.assertEqual(by_label["NET"][col], "+5")


class TestTotalsAndCap(unittest.TestCase):
    def _over_cap(self):
        """More genuine categories than `_LEVEL_ROW_CAP`, all with distinct levels."""
        types = [
            "feature", "bug", "chore", "documentation",
            "enhancement", "performance", "refactor", "test",
        ]
        arrivals = {(f"type:{t}", 5): 10 + i for i, t in enumerate(types)}
        scope_arrivals = {("parent", 5): sum(arrivals.values()) - 4, ("child", 5): 4}
        return _stats(arrivals=arrivals, scope_arrivals=scope_arrivals), sum(arrivals.values())

    def test_total_open_is_independent_of_the_row_cap(self):
        d, corpus_total = self._over_cap()
        headers, rows, _diag = bk._level_rows(d)
        by_label = _rows_by_label(rows)
        col = headers.index("Now")

        self.assertEqual(by_label["TOTAL OPEN"][col], str(corpus_total))
        self.assertEqual(
            int(by_label["of which parents"][col]) + int(by_label["of which children"][col]),
            corpus_total,
        )

    def test_the_cap_actually_engages(self):
        d, _ = self._over_cap()
        _headers, rows, _diag = bk._level_rows(d)
        labels = [label for label, _ in rows]
        self.assertIn("Other", labels)
        category_rows = labels[: labels.index("Other")]
        self.assertEqual(len(category_rows), bk._LEVEL_ROW_CAP - 1)

    def test_other_row_and_shown_rows_reconcile_with_the_block_subtotal(self):
        d, _ = self._over_cap()
        headers, rows, _diag = bk._level_rows(d)
        labels = [label for label, _ in rows]
        subtotal_idx = labels.index("-- genuine")
        block = rows[:subtotal_idx]
        subtotal = rows[subtotal_idx][1]

        for col in range(len(headers)):
            shown = sum(int(cells[col]) for _label, cells in block)
            self.assertEqual(shown, int(subtotal[col]), f"column {headers[col]}")

    def test_an_empty_block_emits_no_subtotal(self):
        """A repo with only genuine work must not show an all-zero
        `-- follow-ups` row."""
        d = _stats(arrivals={("type:feature", 4): 3})
        _headers, rows, _diag = bk._level_rows(d)
        labels = [label for label, _ in rows]
        self.assertNotIn("-- follow-ups", labels)
        self.assertIn("-- genuine", labels)


class TestDiagnostics(unittest.TestCase):
    def test_diagnostics_are_surfaced_on_the_populated_path(self):
        d = _stats(
            arrivals={("type:feature", 4): 3},
            excluded={"no_frontmatter": 3, "folded": 5},
        )
        _headers, rows, diagnostics = bk._level_rows(d)
        self.assertTrue(rows)
        self.assertEqual(len(diagnostics), 1)
        self.assertIn("8 task(s)", diagnostics[0])
        self.assertIn("no_frontmatter: 3", diagnostics[0])
        self.assertIn("folded: 5", diagnostics[0])

    def test_no_diagnostics_when_nothing_was_excluded(self):
        d = _stats(arrivals={("type:feature", 4): 3})
        _headers, _rows, diagnostics = bk._level_rows(d)
        self.assertEqual(diagnostics, [])

    def test_diagnostics_explain_an_empty_level_table(self):
        """An all-excluded repo: no placeable task, but the counters are exactly
        what makes `main()`'s `has_backlog` predicate admit it. The TUI must
        explain the absence rather than report a generic 'no data'."""
        d = _stats(excluded={"no_frontmatter": 3, "folded": 5})
        _headers, rows, diagnostics = bk._level_rows(d)
        self.assertEqual(rows, [])
        self.assertEqual(len(diagnostics), 1)
        self.assertIn("8 task(s)", diagnostics[0])

    def test_clamped_cells_are_reported_separately_from_the_task_tally(self):
        """`negative_level` counts clamped OUTPUT CELLS, never tasks."""
        d = _stats(
            arrivals={("type:feature", 4): 3},
            departures={("type:bug", 5): 2},
            excluded={"folded": 5},
        )
        _headers, _rows, diagnostics = bk._level_rows(d)
        self.assertEqual(len(diagnostics), 2)
        task_line, clamp_line = diagnostics
        # The task total counts ONLY the seven task reasons.
        self.assertIn("5 task(s)", task_line)
        self.assertNotIn("negative_level", task_line)
        self.assertIn("Clamped negative level cells:", clamp_line)


class TestNetflowSeriesSelection(unittest.TestCase):
    def test_netflow_series_are_ranked_by_horizon_volume(self):
        """Volume is arrivals + departures, NOT net.

        `churn` has the largest volume in the window but nets to zero every week;
        ranking on net (or |net|) would bucket exactly the category this pane
        exists to show into `Other`.
        """
        d = _stats(
            arrivals={
                ("type:feature", 4): 40,
                ("kind:carry_over", 4): 30,
                ("type:bug", 4): 20,
                ("type:chore", 4): 10,
                ("type:test", 4): 5,
                ("type:refactor", 4): 4,
            },
            departures={("kind:carry_over", 4): 30},
        )
        _labels, _totals, series_labels, series_values = bk._netflow_rows(d)

        # Exact list, order included: a membership-only check would pass a
        # net-based ranking, a missing tie-break, and a mis-bucketed Other.
        self.assertEqual(
            series_labels,
            ["carry-over", "Features", "Bug Fixes", "Chores", "Other"],
        )
        col = _labels.index("W-4")
        by_label = dict(zip(series_labels, series_values))
        self.assertEqual(by_label["carry-over"][col], 0)   # 30 in, 30 out
        self.assertEqual(by_label["Features"][col], 40)
        self.assertEqual(by_label["Other"][col], 9)        # test 5 + refactor 4

    def test_other_is_omitted_when_the_remainder_is_all_zero(self):
        d = _stats(
            arrivals={("type:feature", 4): 5, ("type:bug", 4): 3, ("type:chore", 4): 2},
        )
        _labels, _totals, series_labels, _sv = bk._netflow_rows(d)
        self.assertNotIn("Other", series_labels)

    def test_empty_flow_yields_no_totals(self):
        d = _stats()
        _labels, totals, series_labels, series_values = bk._netflow_rows(d)
        self.assertEqual(totals, [])
        self.assertEqual(series_labels, [])
        self.assertEqual(series_values, [])


class TestCliParity(unittest.TestCase):
    """[pin_cli_tui_backlog_parity] — surface against surface, never against a
    third probe. One `StatsData`, rendered by the CLI and by the pane."""

    TODAY = date(2026, 8, 24)

    def _cli_sections(self, d):
        offsets = stats_data.backlog_week_offsets(stats_data.BACKLOG_WEEKS_DEFAULT)
        level_axis = CLI.build_backlog_axis(d, offsets)
        out = io.StringIO()
        CLI.render_backlog_level(level_axis, d, out, self.TODAY, 1)
        level_text = out.getvalue()
        # A fresh axis per section: `backlog_levels`' clamp sink counts per call,
        # which is the same non-idempotency the pane avoids with a scratch Counter.
        flow_axis = CLI.build_backlog_axis(d, offsets)
        out = io.StringIO()
        CLI.render_backlog_netflow(flow_axis, d, out, self.TODAY, 1)
        return level_text, out.getvalue()

    def _under_cap(self):
        arrivals = {
            ("type:feature", 5): 12,
            ("type:bug", 5): 7,
            ("kind:manual_verification", 5): 9,
            ("kind:risk_mitigation", 4): 4,
        }
        departures = {("type:feature", 3): 5, ("kind:manual_verification", 2): 2}
        scope_arrivals = {("parent", 5): 24, ("child", 5): 4, ("child", 4): 4}
        scope_departures = {("parent", 3): 5, ("child", 2): 2}
        return _stats(arrivals, departures, scope_arrivals, scope_departures)

    def test_level_table_matches_the_cli_row_for_row(self):
        d = self._under_cap()
        level_text, _flow_text = self._cli_sections(d)
        cli_headers, cli_rows = _parse_cli_table(level_text)
        headers, rows, _diag = bk._level_rows(d)
        pane_rows = _rows_by_label(rows)

        self.assertEqual(headers, cli_headers)
        # Under the cap the row sets are directly comparable.
        self.assertEqual(set(pane_rows), set(cli_rows))
        for label, cells in pane_rows.items():
            self.assertEqual(cells, cli_rows[label], f"row {label}")

    def test_level_totals_match_the_cli_even_over_the_cap(self):
        """The cap is the one thing that could break the totals, so they are
        asserted where it engages."""
        types = ["feature", "bug", "chore", "documentation", "enhancement",
                 "performance", "refactor", "test", "style"]
        arrivals = {(f"type:{t}", 5): 10 + i for i, t in enumerate(types)}
        total = sum(arrivals.values())
        d = _stats(
            arrivals=arrivals,
            scope_arrivals={("parent", 5): total - 6, ("child", 5): 6},
        )
        level_text, _flow = self._cli_sections(d)
        _cli_headers, cli_rows = _parse_cli_table(level_text)
        _headers, rows, _diag = bk._level_rows(d)
        pane_rows = _rows_by_label(rows)

        self.assertIn("Other", pane_rows)          # the cap engaged
        self.assertNotIn("Other", cli_rows)        # the CLI never caps
        for label in ("TOTAL OPEN", "of which parents", "of which children", "-- genuine"):
            self.assertEqual(pane_rows[label], cli_rows[label], f"row {label}")

    def test_netflow_totals_and_per_category_nets_match_the_cli(self):
        d = self._under_cap()
        _level_text, flow_text = self._cli_sections(d)
        cli_headers, cli_rows = _parse_cli_table(flow_text)
        labels, totals, series_labels, series_values = bk._netflow_rows(d)
        pane_totals = _rows_by_label(totals)

        self.assertEqual(labels, cli_headers)
        for label in ("ARRIVALS", "DEPARTURES", "NET"):
            self.assertEqual(pane_totals[label], cli_rows[label], f"row {label}")

        # Series order differs by design (the chart ranks by volume, the CLI
        # table by follow-up-ness then level), so compare as a mapping.
        for name, values in zip(series_labels, series_values):
            if name == "Other":
                continue
            self.assertEqual(
                values, [int(c) for c in cli_rows[name]], f"series {name}"
            )

    def test_diagnostics_match_the_cli_exclusion_footnote(self):
        d = self._under_cap()
        d.backlog_excluded = Counter({"no_frontmatter": 3, "folded": 5})
        level_text, _flow = self._cli_sections(d)
        _headers, _rows, diagnostics = bk._level_rows(d)

        self.assertEqual(len(diagnostics), 1)
        # The CLI wraps its footnote in markdown italics; the sentence inside
        # must be byte-identical to the pane's diagnostic line.
        self.assertIn(f"_{diagnostics[0]}_", level_text)


if __name__ == "__main__":
    unittest.main()
