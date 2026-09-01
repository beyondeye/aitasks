"""The expanded gate surface in the board's task detail screen (t1603_4).

An In-Flight card carries only a *compact* phase chip, because a card is a
narrow surface. This module covers the `Gates` collapsible that shows the full
passed / current / pending list on the detail screen.

The whole point of the surface is that it **agrees with the card**, so nothing
in the production builder derives gate state locally — it reads
`derive_workflow_phase`, `phase_chip_text`, `_failed_active_gates`,
`_pending_procedure_gates` and `archive_pending`. Four things here are
load-bearing and each fails silently:

* **A declared gate that never ran has no `current` entry.** `state.current` is
  built only from parsed ledger runs, while `archive_pending` holds every
  unsatisfied active gate — so indexing `current[g]` in the pending branch
  raises `KeyError` on the *ordinary* state of a freshly claimed task.
  `test_never_run_gate_renders_pending` is that case, and it is a first-class
  row of the classification table rather than an edge case.
* **A fraction requires a ledger.** `_gate_progress` answers `(0, N)` for an
  `Implementing` task with declared gates and no `## Gate Runs`, while
  `derive_workflow_phase` deliberately answers `None` so neither the chip nor
  this section prints a fabricated `0/N`. `NoLedgerTitleTests` pins the title
  against recomputing it.
* **The error short-circuit is what carries the diagnostic.** Ordering it
  before the phase row is what keeps the one-row contract (`phase_chip_text`
  renders `error` provenance with the same opening words, so emitting the phase
  row first would print it twice). But the row COUNT is not what a regression
  changes: with `state is None` the builder returns right after the phase row
  either way, so deleting the short-circuit still yields one row — just the
  bare label, with the underlying error silently gone. Asserting the message
  text is the only thing that tells the two apart, which is why
  `test_unreadable_ledger_is_exactly_one_row` does both.
* **Gate names are task-controlled text.** They reach `active_gates` from
  frontmatter with no charset validation (only ledger *markers* are constrained
  to `[A-Za-z0-9_]+`), and `ReadOnlyField` is a `Static`, which parses Rich
  markup. Every real registry gate is plain snake_case, so `MarkupEscapingTests`
  is the only test here that would fail if `escape()` were dropped.

Fixtures are real task files written into the fixture tree and parsed by the
production parser, per `tests/test_board_workflow_phase.py`: a hand-built
`TaskGateState` can encode a combination the parser never emits, and matching
production semantics is the point.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_detail_gates_section.py -v
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402


#: A code digest no fixture signature is stamped with, so a signed human gate
#: reads as stale. It must be pinned rather than computed: the fixture tree is a
#: temp directory with no git repo, so `gate_ledger.code_digest()` answers
#: `None` — "freshness is unverifiable" — which `witness_state` resolves to
#: `unstamped` (accept), making staleness unreachable through the real digest.
#: A `str` here is state 3 of `_resolve_digest`'s documented four-state channel
#: ("an already-computed digest, used as-is"), i.e. the same channel production
#: fills from `TaskManager.code_digest_for_refresh` — not a patch or a stub.
PINNED_DIGEST = "feedfacefeed"


def _manager(ab, digest=None):
    """Bare `TaskManager` built from the *fixture-bound* board module.

    `ab` is threaded in rather than imported: under the harness the board loads
    under a synthetic module name, so a local `import aitask_board` would reach
    a different module object than the one under test. Same shape as
    `test_board_workflow_phase._manager` — seven other modules build one this
    way; there is no shared builder to reuse.

    `digest` pre-seeds the once-per-refresh digest memo; leaving it `None` keeps
    the default `_DIGEST_UNSET` and lets the real `code_digest()` run.
    """
    TaskManager = ab.TaskManager
    mgr = TaskManager.__new__(TaskManager)
    mgr.task_datas = {}
    mgr.child_task_datas = {}
    mgr.archived_task_cache = {}
    mgr.columns = []
    mgr.column_order = []
    mgr.modified_files = set()
    mgr.lock_map = {}
    mgr.xdep_status_cache = {}
    mgr.gate_state_cache = {}
    mgr.gate_registry_cache = None
    mgr.gate_registry_error = ""
    mgr._dep_resolver = None
    mgr.gate_digest_cache = ab._DIGEST_UNSET if digest is None else digest
    mgr.settings = {}
    return mgr


def _run(gate: str, status: str, **fields) -> str:
    icon = {"pass": "✅", "fail": "❌", "error": "❌", "skip": "⏭",
            "pending": "⏸"}.get(status, "⏸")
    extra = "".join(f" {k}={v}" for k, v in fields.items())
    return (f"> **{icon} gate:{gate}** run=2026-01-01T00:00:00Z "
            f"status={status} attempt=1{extra}\n")


def _ledger(*runs: str) -> str:
    return "\n## Gate Runs\n\n" + "".join(runs)


def _body(status: str, extra_fm: str = "", ledger: str = "") -> str:
    return f"""---
priority: high
effort: low
status: {status}
{extra_fm}---

Body.
{ledger}
"""


class GateSectionTestBase(bf.FixtureBoardTestBase):
    """Real task file on disk -> production gate derivation -> section rows."""

    def _section(self, name: str, body: str, *, break_ledger_read: bool = False,
                 manager: bool = True, digest=None):
        """`(row_texts, fraction)` for a task written into the fixture tree.

        `break_ledger_read` fails the way production fails — the `Task` points
        at a path that is not on disk while its in-memory content still carries
        the `## Gate Runs` markers. That is exactly the combination
        `gate_state_for` produces (`has_ledger` is resolved from `task.content`
        BEFORE the call that raises), so the real `except` branch builds the
        result: no patching, no hand-built `GateStateResult`.
        """
        ab = self.ab
        path = self.tasks_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        self.addCleanup(path.unlink, missing_ok=True)
        task = ab.Task.from_text(path, body)
        if break_ledger_read:
            task.filepath = self.tasks_dir / "definitely_not_on_disk.md"
        screen = ab.TaskDetailScreen(
            task, _manager(ab, digest) if manager else None)
        rows, fraction = screen._build_gate_fields()
        return [str(r.render()) for r in rows], fraction

    @staticmethod
    def _gate_rows(rows: list[str]) -> list[str]:
        """Rows carrying a classification glyph — i.e. not the phase row."""
        return [r for r in rows if r[:1] in {"✓", "⚠", "⊘", "✗", "◈", "·"}]

    def _tuple_fm(self, gates, active, filtered=()):
        return bf.active_tuple_fm(list(gates), list(active), list(filtered))

    def _witness(self, task_num: str, gate: str, digest: str):
        """Write the code-bound signature `ait gate pass` writes.

        Staleness is decided by THIS file, not by a `code_digest=` field on the
        ledger marker line — `stale_signed_gates` pre-filters on
        `_has_stamped_witness`, which reads
        `.aitask-gates/t<id>/<gate>.signed` (the registry's `signal_target`
        template). A fixture that only stamps the marker produces a clean
        `pass` and silently tests nothing.
        """
        path = self.tree / ".aitask-gates" / f"t{task_num}" / f"{gate}.signed"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"code_digest={digest}\n", encoding="utf-8")
        self.addCleanup(path.unlink, missing_ok=True)


# --- 1. one test per row of the classification table --------------------------


class GateRowClassificationTests(GateSectionTestBase, unittest.TestCase):
    """Each row of the table, on real registry gates.

    `risk_evaluated` / `tests_pass` are `type: machine`, `plan_approved` /
    `review_approved` are `type: human`, and `docs_updated` is the registry's
    one `kind: procedure` gate — so every branch is reachable with a gate the
    shipped `gates.yaml` actually defines.
    """

    def test_never_run_gate_renders_pending(self):
        """THE ordinary state: a declared gate with no run at all.

        `state.current` has no entry for it, so a `current[g].status` lookup in
        the pending branch raises `KeyError` and takes the whole detail screen
        down. This is not an exotic fixture — it is every task the moment it is
        claimed, this one included.
        """
        rows, _ = self._section("t9510_neverrun.md", _body(
            "Implementing", self._tuple_fm(["risk_evaluated"], ["risk_evaluated"])))
        self.assertIn("· risk_evaluated — pending", rows)

    def test_passed_gate(self):
        rows, _ = self._section("t9511_pass.md", _body(
            "Implementing", self._tuple_fm(["risk_evaluated"], ["risk_evaluated"]),
            _ledger(_run("risk_evaluated", "pass", type="machine"))))
        self.assertIn("✓ risk_evaluated — passed", rows)

    def test_failed_gate(self):
        rows, _ = self._section("t9512_fail.md", _body(
            "Implementing", self._tuple_fm(["tests_pass"], ["tests_pass"]),
            _ledger(_run("tests_pass", "fail", type="machine"))))
        self.assertIn("✗ tests_pass — failed", rows)

    def test_skipped_gate_is_satisfied_but_distinct_from_pass(self):
        """`skip` is terminal-satisfied, as in the ledger — but it must not
        render as `passed`, or the surface loses a distinction the ledger
        makes."""
        rows, fraction = self._section("t9513_skip.md", _body(
            "Implementing", self._tuple_fm(["risk_evaluated"], ["risk_evaluated"]),
            _ledger(_run("risk_evaluated", "skip", type="machine"))))
        self.assertIn("⊘ risk_evaluated — skipped (not applicable)", rows)
        self.assertNotIn("✓ risk_evaluated — passed", rows)
        # Satisfied: it counts toward the numerator despite not being a pass.
        self.assertEqual(fraction, (1, 1))

    def test_procedure_gate_pending_needs_attended_agent(self):
        rows, _ = self._section("t9514_proc.md", _body(
            "Implementing", self._tuple_fm(["docs_updated"], ["docs_updated"]),
            _ledger(_run("plan_approved", "pass", type="human"))))
        self.assertIn("◈ docs_updated — pending; needs attended agent", rows)

    def test_stale_signature_shows_both_facts(self):
        """The ledger really does say `pass` AND the signature no longer binds.

        Showing either fact alone is the exact disagreement this surface exists
        to remove (`gate_ledger.py:167-174`), so the row is asserted whole.
        """
        self._witness("9515", "review_approved", "deadbeefdead")
        rows, _ = self._section("t9515_stale.md", _body(
            "Implementing",
            self._tuple_fm(["plan_approved", "review_approved"],
                           ["plan_approved", "review_approved"]),
            _ledger(_run("plan_approved", "pass", type="human"),
                    _run("review_approved", "pass", type="human"))),
            digest=PINNED_DIGEST)
        row = "⚠ review_approved — pass, signature stale; needs re-sign"
        self.assertIn(row, rows)
        # Not silently demoted to a bare "pending", and not reported as a clean
        # pass either.
        self.assertNotIn("· review_approved — pending", rows)
        self.assertNotIn("✓ review_approved — passed", rows)


# --- 2. the filtered-gates audit block ---------------------------------------


class FilteredGatesAuditTests(GateSectionTestBase, unittest.TestCase):
    """A profile-filtered gate is listed for audit and counted in nothing.

    `TaskGateState`'s contract is that a historical run of a filtered gate must
    never drive a classification, so it may not move the fraction either.
    """

    LEDGER = _ledger(_run("plan_approved", "pass", type="human"),
                     _run("lint", "fail", type="machine"))

    def test_filtered_gate_is_listed_under_an_audit_label(self):
        rows, _ = self._section("t9520_filtered.md", _body(
            "Implementing",
            self._tuple_fm(["plan_approved", "lint"], ["plan_approved"], ["lint"]),
            self.LEDGER))
        joined = "\n".join(rows)
        self.assertIn("filtered by profile (audit only)", joined)
        self.assertIn("· lint", joined)
        # Its historical `fail` must not classify it.
        self.assertNotIn("✗ lint — failed", rows)

    def test_filtered_gate_does_not_move_the_fraction(self):
        """Same task with and without the filtered gate: identical fraction."""
        _, with_filtered = self._section("t9521_wf.md", _body(
            "Implementing",
            self._tuple_fm(["plan_approved", "lint"], ["plan_approved"], ["lint"]),
            self.LEDGER))
        _, without = self._section("t9522_wo.md", _body(
            "Implementing",
            self._tuple_fm(["plan_approved"], ["plan_approved"]),
            _ledger(_run("plan_approved", "pass", type="human"))))
        self.assertEqual(with_filtered, (1, 1))
        self.assertEqual(with_filtered, without)


# --- 3. degraded and error rendering come from the SHARED renderer -----------


class DegradedRenderingTests(GateSectionTestBase, unittest.TestCase):

    def test_unreadable_ledger_is_exactly_one_row(self):
        """One row, no list, no counts — and no phase row beside it.

        `derive_workflow_phase` returns `error` provenance for an `Implementing`
        task, which `phase_chip_text` renders as this same string. Emitting the
        phase row before the short-circuit would print it twice.
        """
        rows, fraction = self._section("t9530_err.md", _body(
            "Implementing", self._tuple_fm(["risk_evaluated"], ["risk_evaluated"]),
            _ledger(_run("risk_evaluated", "pass", type="machine"))),
            break_ledger_read=True)
        self.assertEqual(len(rows), 1, f"expected exactly one row, got {rows}")
        self.assertIsNone(fraction)
        # The row must carry the DIAGNOSTIC, not just the label. Deleting the
        # short-circuit does not change the row count — `state is None` makes the
        # builder return right after the phase row, and `phase_chip_text` renders
        # `error` provenance with the same opening words — so a
        # `startswith("Gate state unavailable")` assertion passes against a
        # builder that has silently dropped the message. This is the only
        # assertion here that tells the two apart.
        self.assertIn("definitely_not_on_disk", rows[0],
                      "the underlying error must reach the surface, not just "
                      f"the generic label: {rows[0]!r}")

    def test_no_ledger_row_is_the_shared_renderers_string(self):
        """Asserted equal to `phase_chip_text`'s own output, not to a literal.

        A literal here would still pass if the card's renderer changed, which is
        precisely the card/detail divergence this section exists to prevent.
        """
        rows, _ = self._section("t9531_noledger.md", _body(
            "Implementing", self._tuple_fm(["risk_evaluated"], ["risk_evaluated"])))
        expected = self.ab.phase_chip_text("implementing", "unknown", None)
        self.assertEqual(rows[0], expected)
        self.assertIn("No gate ledger", expected)


# --- 4. the title fraction is never recomputed -------------------------------


class NoLedgerTitleTests(GateSectionTestBase, unittest.TestCase):
    """A fraction is a progress claim, so it requires a ledger."""

    def test_no_ledger_yields_no_fraction_at_all(self):
        """`_gate_progress` would answer `(0, 2)` here; the card shows none.

        Asserted as absence, not as "not (0, 2)": any fraction is wrong on this
        branch, and pinning only the specific wrong value would let a different
        fabricated one through.
        """
        rows, fraction = self._section("t9540_noledger.md", _body(
            "Implementing",
            self._tuple_fm(["risk_evaluated", "docs_updated"],
                           ["risk_evaluated", "docs_updated"])))
        self.assertIsNone(fraction)
        # The declared gates are still listed — a per-gate enforcement fact,
        # which is a different claim from "0 of 2 done".
        self.assertEqual(len(self._gate_rows(rows)), 2)
        self.assertIn("No gate ledger", rows[0])

    def test_negative_control_recomputing_here_would_fabricate_a_fraction(self):
        """The independent derivation the builder must NOT use.

        Without this the test above passes against a builder that simply has no
        fraction feature at all; this shows the value is available and was
        deliberately suppressed.
        """
        ab = self.ab
        path = self.tasks_dir / "t9541_control.md"
        body = _body("Implementing",
                     self._tuple_fm(["risk_evaluated", "docs_updated"],
                                    ["risk_evaluated", "docs_updated"]))
        path.write_text(body, encoding="utf-8")
        self.addCleanup(path.unlink, missing_ok=True)
        task = ab.Task.from_text(path, body)
        state = _manager(ab).gate_state_for(task).state
        self.assertEqual(ab._gate_progress(state)[0], (0, 2))

    def test_ledger_present_yields_the_fraction(self):
        _, fraction = self._section("t9542_ledger.md", _body(
            "Implementing",
            self._tuple_fm(["plan_approved", "review_approved"],
                           ["plan_approved", "review_approved"]),
            _ledger(_run("plan_approved", "pass", type="human"))))
        self.assertEqual(fraction, (1, 2))


# --- 5. cross-surface parity with the card's compact chip --------------------


class CrossSurfaceParityTests(GateSectionTestBase, unittest.TestCase):
    """The section title's fraction IS the card chip's fraction.

    Asserted on the rendered strings rather than by comparing two derivations:
    that is what makes this a parity test rather than a restatement. It fails
    both if someone re-inlines a count here and if someone reintroduces a
    fraction the card suppresses — INCLUDING the cases where both show none,
    which is why the no-ledger and marker fixtures are in the matrix.
    """

    def _cases(self):
        both = ["plan_approved", "review_approved"]
        return {
            "ledger_partial": _body(
                "Implementing", self._tuple_fm(both, both),
                _ledger(_run("plan_approved", "pass", type="human"))),
            "ledger_complete": _body(
                "Implementing", self._tuple_fm(both, both),
                _ledger(_run("plan_approved", "pass", type="human"),
                        _run("review_approved", "pass", type="human"))),
            "no_ledger": _body(
                "Implementing", self._tuple_fm(both, both)),
            "marker_only": _body(
                "Ready", self._tuple_fm(both, both)
                + "plan_approved_at: 2026-08-25 10:24\n"),
        }

    def test_title_fraction_matches_the_compact_chip(self):
        ab = self.ab
        for i, (label, body) in enumerate(self._cases().items()):
            with self.subTest(case=label):
                name = f"t95{50 + i}_{label}.md"
                path = self.tasks_dir / name
                path.write_text(body, encoding="utf-8")
                self.addCleanup(path.unlink, missing_ok=True)
                task = ab.Task.from_text(path, body)
                mgr = _manager(ab)
                result = mgr.gate_state_for(task)
                phase = ab.derive_workflow_phase(
                    task, result, mgr.gate_registry(),
                    plan_exists_probe=lambda: False)

                screen = ab.TaskDetailScreen(task, _manager(ab))
                _, fraction = screen._build_gate_fields()

                title = "Gates" if fraction is None else \
                    f"Gates ({fraction[0]}/{fraction[1]})"
                chip = ab.phase_chip_text(phase.phase, phase.provenance,
                                          phase.progress, compact=True)
                if fraction is None:
                    self.assertNotIn("/", title)
                    self.assertNotIn("/", chip,
                                     "card shows a fraction the section hides")
                else:
                    self.assertIn(f"{fraction[0]}/{fraction[1]}", chip)


# --- 6. section presence -----------------------------------------------------


class SectionPresenceTests(GateSectionTestBase, unittest.TestCase):

    def test_ungated_task_builds_no_rows(self):
        rows, fraction = self._section("t9560_ungated.md", _body("Ready"))
        self.assertEqual(rows, [])
        self.assertIsNone(fraction)

    def test_no_manager_builds_no_rows(self):
        """Read-only / archived screens are constructed without a manager, and
        `gate_state_for` is a manager method."""
        rows, _ = self._section(
            "t9561_nomgr.md",
            _body("Implementing",
                  self._tuple_fm(["risk_evaluated"], ["risk_evaluated"])),
            manager=False)
        self.assertEqual(rows, [])


# --- 7. gate names are task-controlled text ----------------------------------


class MarkupEscapingTests(GateSectionTestBase, unittest.TestCase):
    """`ReadOnlyField` is a `Static`, so it parses Rich markup, and gate names
    reach `active_gates` from frontmatter with no charset validation.

    Every gate in the shipped registry is plain snake_case, so this is the ONLY
    test in this module that fails if `escape()` is dropped — every other one
    passes against a builder that renders task-controlled text as markup.
    """

    NAME = "weird[b]name"

    def test_bracketed_name_renders_literally_in_an_active_row(self):
        rows, _ = self._section("t9570_markup.md", _body(
            "Implementing",
            self._tuple_fm([f'"{self.NAME}"'], [f'"{self.NAME}"'])))
        self.assertIn(f"· {self.NAME} — pending", rows)

    def test_bracketed_name_renders_literally_in_the_filtered_block(self):
        rows, _ = self._section("t9571_markupf.md", _body(
            "Implementing",
            self._tuple_fm(["plan_approved", f'"{self.NAME}"'],
                           ["plan_approved"], [f'"{self.NAME}"']),
            _ledger(_run("plan_approved", "pass", type="human"))))
        self.assertIn(self.NAME, "\n".join(rows))


# --- 8. the section actually mounts, in the right place ----------------------


class GateSectionMountTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """Boots the real board: the rows above prove content, this proves the
    collapsible exists, sits between Risk and Dependencies, and is absent for a
    task with nothing to report."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KanbanApp = cls.ab.KanbanApp
        cls.TaskDetailScreen = cls.ab.TaskDetailScreen

    def _run(self, coro):
        return asyncio.run(coro)

    def _first_parent_task(self, app):
        for filename, task in app.manager.task_datas.items():
            if filename.startswith("t9") and "_" in filename:
                return task
        self.fail("fixture must load a parent task")

    def _gated_task(self, app):
        """A real on-disk gated task, parsed by the production parser."""
        fm = bf.active_tuple_fm(["plan_approved", "review_approved"],
                                ["plan_approved", "review_approved"], [])
        body = _body("Implementing", fm,
                     _ledger(_run("plan_approved", "pass", type="human")))
        path = self.tree / "aitasks" / "t9580_mounted.md"
        path.write_text(body, encoding="utf-8")
        self.addCleanup(path.unlink, missing_ok=True)
        return self.ab.Task.from_text(path, body)

    def test_gates_section_mounts_between_risk_and_relations(self):
        from textual.widgets import Collapsible

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                task = self._gated_task(app)
                task.metadata["risk_code_health"] = "low"
                task.metadata["risk_goal_achievement"] = "low"

                app.push_screen(self.TaskDetailScreen(task, app.manager))
                await pilot.pause()

                section = app.screen.query_one("#sec_gates", Collapsible)
                self.assertTrue(section.collapsed,
                                "gates section must be collapsed by default")
                self.assertEqual(section.title, "Gates (1/2)")

                ids = [s.id for s in app.screen.query(".meta-section")]
                self.assertEqual(ids[:3], ["sec_risk", "sec_gates", "sec_relations"])
        self._run(go())

    def test_no_section_for_a_task_with_no_gates(self):
        """Widget ABSENCE, not a blank widget — an empty collapsible would
        satisfy a text assertion while cluttering every ordinary task."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                task = self._first_parent_task(app)
                app.push_screen(self.TaskDetailScreen(task, app.manager))
                await pilot.pause()
                self.assertFalse(app.screen.query("#sec_gates"),
                                 "ungated task must grow no gates section")
        self._run(go())


if __name__ == "__main__":
    unittest.main()
