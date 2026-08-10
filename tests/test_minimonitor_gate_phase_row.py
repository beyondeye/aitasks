"""Tests for minimonitor's merged gate-summary + workflow-phase row (t1479).

A gated task's minimonitor card used to spend two of its four rows saying one
thing twice over::

    ★ ● ◆ ≈ agent-pick-1420      PROMPT 12s
      merge the gates and phase lines
      gates: 3/4 pass, 1 pending
      phase: IMPLEMENT ⏸

Those two rows are now one label-free line, ``IMPLEMENT ⏸ · 3/4 pass,
1 pending``, and the card is three rows. What is pinned here:

* ``workflow_phase.render_phase_narrow`` — the new narrow renderer — **and**
  ``render_phase``'s four labelled outputs, verbatim. The labelled form is what
  ``ait monitor`` renders and it had no test of its own; without that pin,
  "the full monitor is unchanged" is an unverified claim about a function this
  task refactored.
* ``gate_ledger.abbreviate_gate_summary`` and its drift guard against
  ``GATE_SUMMARY_TAIL``.
* ``minimonitor_app.format_gate_phase_row`` — every rung of the shed ladder,
  measured in **cells** (``rich.cells.cell_len``), never code points.
* The card's line structure at the source (``_agent_card_text``) and on a
  **composited** 40-column screen — a widget's render string cannot reveal that
  Rich ellipsised or wrapped the row on its way to the terminal (t1351).

Fixture note (t1351 hand-off): every card fixture here uses a short,
single-cell window name that fits row 1 with headroom. Row 1's budget and its
cell-aware truncation belong to t1351; an over-budget row 1 *wraps*, which
would break the "card is 3 rows" assertions for reasons that have nothing to do
with this task.

Run: python3 tests/test_minimonitor_gate_phase_row.py
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# MiniMonitorApp only renames its tmux window when constructed by the production
# launcher, but scrub the ambient tmux env anyway so nothing here can touch the
# pane the suite is running in (t1240).
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from rich.cells import cell_len  # noqa: E402
from rich.text import Text  # noqa: E402
from textual.app import App, ComposeResult  # noqa: E402
from textual.containers import VerticalScroll  # noqa: E402

import gate_ledger  # noqa: E402
import workflow_phase  # noqa: E402
from monitor import minimonitor_app as mm  # noqa: E402
from monitor.monitor_core import PaneCategory, TaskInfo  # noqa: E402

# 40-wide tmux pane minus MiniPaneCard's `padding: 0 1`; the detail rows carry a
# further 2-space indent. Same arithmetic as `mm._row_budget` / `_detail_budget`,
# restated here only as the value under test.
_TARGET_WIDTH = 40
_ROW_WIDTH_BUDGET = 38
_DETAIL_BUDGET = 36


def _sig(**kwargs) -> workflow_phase.PhaseSignal:
    return workflow_phase.PhaseSignal(**kwargs)


class NarrowPhaseRendererTests(unittest.TestCase):
    """`render_phase_narrow` drops the label and shortens the unknown variants;
    `render_phase` does neither, now or ever."""

    def test_known_phase_is_label_free(self):
        self.assertEqual(
            workflow_phase.render_phase_narrow(_sig(phase="IMPLEMENT")),
            "IMPLEMENT")

    def test_known_phase_keeps_the_waiting_glyph(self):
        self.assertEqual(
            workflow_phase.render_phase_narrow(
                _sig(phase="IMPLEMENT", waiting="WAITING")),
            "IMPLEMENT ⏸")

    def test_unknown_recording_off_is_shortened(self):
        self.assertEqual(
            workflow_phase.render_phase_narrow(_sig(recording="off")),
            "unknown (rec off)")

    def test_unknown_ledger_only_is_shortened(self):
        self.assertEqual(
            workflow_phase.render_phase_narrow(
                _sig(detail="ledger only, no prompt markers seen")),
            "unknown (ledger)")

    def test_unknown_waiting_keeps_the_glyph(self):
        self.assertEqual(
            workflow_phase.render_phase_narrow(_sig(waiting="WAITING")),
            "unknown ⏸")

    def test_nothing_honest_to_say_renders_empty(self):
        self.assertEqual(workflow_phase.render_phase_narrow(_sig()), "")

    def test_render_phase_output_is_unchanged(self):
        """The negative control for "`ait monitor` is unchanged" (t1479
        decision 5): the full monitor renders through `render_phase`, which this
        task refactored to share a branch table with the narrow form."""
        self.assertEqual(
            workflow_phase.render_phase(
                _sig(phase="IMPLEMENT", waiting="WAITING")),
            "phase: IMPLEMENT ⏸")
        self.assertEqual(
            workflow_phase.render_phase(_sig(phase="POSTIMPL")),
            "phase: POSTIMPL")
        self.assertEqual(
            workflow_phase.render_phase(_sig(recording="off")),
            "phase: unknown (gate recording off)")
        self.assertEqual(
            workflow_phase.render_phase(
                _sig(detail="ledger only, no prompt markers seen")),
            "phase: unknown (ledger only)")
        self.assertEqual(
            workflow_phase.render_phase(_sig(waiting="WAITING")),
            "phase: unknown ⏸")
        self.assertEqual(workflow_phase.render_phase(_sig()), "")


_LEDGER_ALL_PARTS = (
    "---\nstatus: Implementing\n---\n\n## Gate Runs\n\n"
    "> **✅ gate:plan_approved** run=2026-01-01T00:00:00Z status=pass attempt=1 type=human\n\n"
    "> **✅ gate:review_approved** run=2026-01-01T00:01:00Z status=pass attempt=1 type=human\n\n"
    "> **⏳ gate:build_verified** run=2026-01-01T00:02:00Z status=pending type=machine\n\n"
    "> **❌ gate:docs_updated** run=2026-01-01T00:03:00Z status=fail attempt=1 type=machine\n"
)


def _state_with_every_tail_part() -> gate_ledger.TaskGateState:
    """A real parsed `TaskGateState` whose summary carries every tail part.

    Parsed from ledger text by the module's own reader rather than fabricated,
    so the guard below measures what `compact_gate_summary` really emits.
    `stale_signed` is a separate derivation (a signature that no longer binds),
    so it is set on the parsed state — one of the two recorded passes then
    counts as stale.
    """
    with tempfile.TemporaryDirectory(prefix="t1479_gate_") as tmp:
        task = Path(tmp) / "t10_demo.md"
        task.write_text(_LEDGER_ALL_PARTS, encoding="utf-8")
        state = gate_ledger.read_task_gate_state(str(task))
    return dataclasses.replace(state, stale_signed=["review_approved"])


class AbbreviateGateSummaryTests(unittest.TestCase):
    def test_head_loses_the_pass_word(self):
        self.assertEqual(gate_ledger.abbreviate_gate_summary("2/2 pass"), "2/2")

    def test_full_tail_collapses_to_letters(self):
        self.assertEqual(
            gate_ledger.abbreviate_gate_summary(
                "1/4 pass, 1 pending, 1 failed, 1 stale"),
            "1/4 1p 1f 1s")

    def test_empty_summary_stays_empty(self):
        self.assertEqual(gate_ledger.abbreviate_gate_summary(""), "")

    def test_unrecognised_part_survives_verbatim(self):
        """Terse is fine; untrue is not — an unknown part is passed through
        rather than dropped, and the known ones still abbreviate."""
        self.assertEqual(
            gate_ledger.abbreviate_gate_summary("1/4 pass, 1 skipped, 1 failed"),
            "1/4 1 skipped 1f")

    def test_drift_guard_every_tail_label_has_an_abbreviation(self):
        """`compact_gate_summary` writes through `GATE_SUMMARY_TAIL` and the
        abbreviator reads back through it. Head and tail are modelled
        separately **because they shed separately**: the head is always
        `<n>/<total> pass` and its word is deliberately absent from the table
        (the narrow form strips it), so a blanket "every emitted label is in the
        table" assertion would fail on `pass` rather than catch drift.
        """
        summary = gate_ledger.compact_gate_summary(_state_with_every_tail_part())
        self.assertEqual(summary, "1/4 pass, 1 pending, 1 failed, 1 stale")
        head, *tail = summary.split(", ")
        self.assertRegex(head, r"^\d+/\d+ pass$")
        self.assertEqual(
            gate_ledger.abbreviate_gate_summary(head), head[:-len(" pass")],
            "the head must shed the word 'pass' and keep its ratio")

        known = dict(gate_ledger.GATE_SUMMARY_TAIL)
        self.assertTrue(tail, "fixture produced no tail parts to guard")
        for part in tail:
            count, _sep, label = part.partition(" ")
            self.assertIn(
                label, known,
                f"compact_gate_summary emits tail label {label!r} with no entry "
                f"in GATE_SUMMARY_TAIL — the narrow form would leak the long "
                f"word onto a 36-cell row")
            self.assertIn(
                f"{count}{known[label]}",
                gate_ledger.abbreviate_gate_summary(summary))


class MergedRowLadderTests(unittest.TestCase):
    """`format_gate_phase_row`, pure — no Textual, no app."""

    def _assert_fits(self, line: str, budget: int) -> None:
        self.assertLessEqual(
            cell_len(line), budget,
            f"{line!r} is {cell_len(line)} cells, budget is {budget}")

    def test_best_case_joins_verbatim(self):
        line = mm.format_gate_phase_row("IMPLEMENT ⏸", "2/2 pass", _DETAIL_BUDGET)
        self.assertEqual(line, "IMPLEMENT ⏸ · 2/2 pass")
        self._assert_fits(line, _DETAIL_BUDGET)

    def test_multi_part_summary_still_joins_verbatim_when_it_fits(self):
        line = mm.format_gate_phase_row(
            "IMPLEMENT ⏸", "3/4 pass, 1 pending", _DETAIL_BUDGET)
        self.assertEqual(line, "IMPLEMENT ⏸ · 3/4 pass, 1 pending")
        self._assert_fits(line, _DETAIL_BUDGET)

    def test_phase_alone(self):
        self.assertEqual(
            mm.format_gate_phase_row("IMPLEMENT ⏸", "", _DETAIL_BUDGET),
            "IMPLEMENT ⏸")

    def test_gates_alone(self):
        self.assertEqual(
            mm.format_gate_phase_row("", "3/4 pass, 1 pending", _DETAIL_BUDGET),
            "3/4 pass, 1 pending")

    def test_both_empty_renders_no_row(self):
        self.assertEqual(mm.format_gate_phase_row("", "", _DETAIL_BUDGET), "")

    def test_rung_1_over_budget_abbreviates_the_tail(self):
        line = mm.format_gate_phase_row(
            "POSTIMPL", "1/4 pass, 1 pending, 1 failed, 1 stale", _DETAIL_BUDGET)
        self.assertEqual(line, "POSTIMPL · 1/4 1p 1f 1s")
        self._assert_fits(line, _DETAIL_BUDGET)

    def test_worst_realistic_case_fits_the_default_pane(self):
        line = mm.format_gate_phase_row(
            "unknown (rec off)", "0/4 pass, 1 pending, 1 failed, 1 stale",
            _DETAIL_BUDGET)
        self.assertEqual(line, "unknown (rec off) · 0/4 1p 1f 1s")
        self._assert_fits(line, _DETAIL_BUDGET)

    def test_rung_2_clips_the_phase_and_keeps_every_count(self):
        """The counts are the last thing to give way: a failed or stale gate is
        exactly what this row exists to surface."""
        line = mm.format_gate_phase_row(
            "SOMEVERYLONGPHASENAME ⏸", "1/4 pass, 1 pending, 1 failed, 1 stale",
            30)
        self._assert_fits(line, 30)
        self.assertTrue(line.endswith("· 1/4 1p 1f 1s"), line)
        self.assertIn("…", line, "the phase should have been clipped, not the counts")

    def test_rung_3_drops_a_phase_that_would_carry_no_information(self):
        line = mm.format_gate_phase_row(
            "SOMEVERYLONGPHASENAME ⏸", "1/4 pass, 1 pending, 1 failed, 1 stale",
            14)
        self.assertEqual(line, "1/4 1p 1f 1s")
        self._assert_fits(line, 14)

    def test_rung_4_terminal_clip_when_the_summary_alone_overflows(self):
        line = mm.format_gate_phase_row(
            "PLAN", "100000/200000 pass, 10000 pending, 10000 failed", 12)
        self._assert_fits(line, 12)
        self.assertTrue(line.endswith("…"), line)

    def test_single_half_is_clipped_too(self):
        """The budget guard has one exit, so a lone (long) summary cannot wrap
        the way it could when it had its own unbounded line."""
        line = mm.format_gate_phase_row(
            "", "100000/200000 pass, 10000 pending", 12)
        self._assert_fits(line, 12)
        self.assertTrue(line.endswith("…"), line)

    def test_degenerate_budgets_never_overshoot(self):
        """The ellipsis costs a cell of its own; budgets 0 and 1 are answered
        before it is appended."""
        self.assertEqual(mm.format_gate_phase_row("IMPLEMENT", "2/2 pass", 0), "")
        one = mm.format_gate_phase_row("IMPLEMENT", "2/2 pass", 1)
        self.assertEqual(one, "…")
        self.assertEqual(cell_len(one), 1)

    def test_detail_budget_matches_the_documented_arithmetic(self):
        self.assertEqual(mm._detail_budget(_TARGET_WIDTH), _DETAIL_BUDGET)
        self.assertEqual(mm._row_budget(_TARGET_WIDTH), _ROW_WIDTH_BUDGET)

    def test_budgets_report_real_geometry_at_a_tiny_configured_width(self):
        """`tmux.minimonitor.width` is user-configurable with no minimum, so a
        floor in the helper would hand callers more cells than the pane has and
        the row would wrap — the exact outcome the budget prevents."""
        self.assertEqual(mm._detail_budget(10), 6)
        self.assertEqual(mm._row_budget(10), 8)
        self.assertEqual(mm._detail_budget(3), 0)

    def test_gates_only_row_fits_a_width_10_pane(self):
        budget = mm._detail_budget(10)
        line = mm.format_gate_phase_row("", "2/2 pass", budget)
        self.assertEqual(line, "2/2")
        self._assert_fits(line, budget)

    def test_merged_row_fits_a_width_10_pane(self):
        budget = mm._detail_budget(10)
        line = mm.format_gate_phase_row("IMPLEMENT ⏸", "2/2 pass", budget)
        self._assert_fits(line, budget)

    def test_a_pane_too_narrow_to_say_anything_renders_nothing(self):
        self.assertEqual(
            mm.format_gate_phase_row("IMPLEMENT", "2/2 pass", mm._detail_budget(3)),
            "")


def _snap(*, window_name: str = "agent-pick-42", content: str = "",
          awaiting_input: bool = False, awaiting_input_kind: str = "",
          command: str = "node"):
    pane = SimpleNamespace(
        pane_id="%1", session_name="s1", window_index="1", pane_index="0",
        window_name=window_name, category=PaneCategory.AGENT,
        current_command=command,
    )
    return SimpleNamespace(
        pane=pane, content=content, is_idle=False, idle_seconds=0.0,
        awaiting_input=awaiting_input, awaiting_input_kind=awaiting_input_kind,
    )


def _gated_app(summary: str, phase_signal: workflow_phase.PhaseSignal):
    """A `__new__`-constructed app stubbed just enough for `_agent_card_text`'s
    gated branch to run — the `_mk_list_app` stub in
    `tests/test_minimonitor_other_section.py` resolves every pane to no task, so
    that branch never executes there."""
    app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
    app._target_width = _TARGET_WIDTH
    app._completed_pane_ids = frozenset()
    app._monitor = SimpleNamespace(
        get_compare_mode=lambda pid: "stripped",
        is_compare_mode_overridden=lambda pid: False,
        get_shadow_snapshot=lambda pid: None,
    )
    app._task_cache = SimpleNamespace(
        get_task_id_for_pane=lambda pane: "1479",
        get_task_info=lambda task_id, session=None: TaskInfo(
            task_id="1479", task_file="aitasks/t1479_demo.md", title="Demo task",
            priority="medium", effort="low", issue_type="enhancement",
            status="Implementing", body="", plan_content=None,
            task_file_abs="/nonexistent/t1479_demo.md",
        ),
    )
    app._gate_cache = SimpleNamespace(
        summary_for=lambda info: summary,
        phase_for=lambda info, **kw: phase_signal,
        clear=lambda: None,
    )
    app._init_agent_marks()
    return app


class CardShapeTests(unittest.TestCase):
    """The card's line structure, pinned at the source. Complements the
    composited test below: a wrap on screen can hide a missing line, so the
    row *count* is asserted here where the markup is unambiguous."""

    def test_gated_card_is_three_lines(self):
        app = _gated_app("3/4 pass, 1 pending",
                         _sig(phase="IMPLEMENT", waiting="WAITING"))
        markup = app._agent_card_text(_snap())
        lines = markup.split("\n")
        self.assertEqual(
            len(lines), 3,
            f"gated card should be 3 rows (was 4 before t1479): {markup!r}")
        merged = Text.from_markup(lines[2]).plain.strip()
        self.assertEqual(merged, "IMPLEMENT ⏸ · 3/4 pass, 1 pending")
        self.assertNotIn("gates: ", markup)
        self.assertNotIn("phase: ", markup)

    def test_gates_without_a_phase_render_alone(self):
        app = _gated_app("2/2 pass", _sig())
        lines = app._agent_card_text(_snap()).split("\n")
        self.assertEqual(len(lines), 3)
        self.assertEqual(Text.from_markup(lines[2]).plain.strip(), "2/2 pass")

    def test_phase_without_counted_gate_runs_renders_alone(self):
        app = _gated_app("", _sig(phase="PLAN"))
        lines = app._agent_card_text(_snap()).split("\n")
        self.assertEqual(len(lines), 3)
        self.assertEqual(Text.from_markup(lines[2]).plain.strip(), "PLAN")

    def test_ungated_task_with_no_phase_has_no_third_row(self):
        app = _gated_app("", _sig())
        lines = app._agent_card_text(_snap()).split("\n")
        self.assertEqual(len(lines), 2, "name + title only")

    def test_merged_row_fits_the_detail_budget(self):
        app = _gated_app("0/4 pass, 1 pending, 1 failed, 1 stale",
                         _sig(recording="off"))
        merged = Text.from_markup(
            app._agent_card_text(_snap()).split("\n")[2]).plain
        self.assertLessEqual(
            cell_len(merged), _ROW_WIDTH_BUDGET,
            f"merged row is {cell_len(merged)} cells: {merged!r}")


class _RowHost(App):
    """A 40-column host that renders one card with minimonitor's metrics.

    Mounting is what makes this a *composited*-screen assertion: a widget's own
    render string cannot reveal that Rich ellipsised or wrapped the row on its
    way to the terminal (t1351). Same shape as
    `tests/test_minimonitor_other_section.py::_RowHost`.
    """

    CSS = """
    #mini-pane-list { height: 1fr; }
    MiniPaneCard { height: auto; padding: 0 1; }
    """

    def __init__(self, text: str) -> None:
        super().__init__()
        self._text = text

    def compose(self) -> ComposeResult:
        yield VerticalScroll(id="mini-pane-list")

    def on_mount(self) -> None:
        self.query_one("#mini-pane-list", VerticalScroll).mount(
            mm.MiniPaneCard("%1", self._text)
        )


class CompositedRowTests(unittest.TestCase):
    """The AC's composited-screen assertion at width 40."""

    def _screen(self, markup: str) -> list[str]:
        async def run():
            host = _RowHost(markup)
            async with host.run_test(size=(_TARGET_WIDTH, 10)):
                await host.workers.wait_for_complete()
                return [strip.text.rstrip()
                        for strip in host.screen._compositor.render_strips()]

        return asyncio.run(run())

    def _assert_row(self, summary: str, sig: workflow_phase.PhaseSignal,
                    expected: str) -> None:
        app = _gated_app(summary, sig)
        markup = app._agent_card_text(_snap())
        rows = [ln for ln in self._screen(markup) if ln.strip()]
        self.assertEqual(
            len(rows), 3,
            "gated card should composite to exactly 3 rows:\n"
            + "\n".join(repr(r) for r in rows))
        merged = rows[2]
        self.assertEqual(merged.strip(), expected)
        self.assertNotIn(
            "…", merged, f"row was ellipsised by the compositor: {merged!r}")
        self.assertLessEqual(
            cell_len(merged), _ROW_WIDTH_BUDGET,
            f"row is {cell_len(merged)} cells, budget is {_ROW_WIDTH_BUDGET}")

    def test_best_case(self):
        self._assert_row("2/2 pass", _sig(phase="IMPLEMENT", waiting="WAITING"),
                         "IMPLEMENT ⏸ · 2/2 pass")

    def test_multi_part_gate_summary(self):
        self._assert_row(
            "1/4 pass, 1 pending, 1 failed, 1 stale", _sig(phase="POSTIMPL"),
            "POSTIMPL · 1/4 1p 1f 1s")

    def test_longest_unknown_phase_variant(self):
        self._assert_row(
            "0/4 pass, 1 pending, 1 failed, 1 stale", _sig(recording="off"),
            "unknown (rec off) · 0/4 1p 1f 1s")


if __name__ == "__main__":
    unittest.main(verbosity=2)
