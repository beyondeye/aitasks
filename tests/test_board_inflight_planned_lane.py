"""Tests for the In-Flight Planned lane, admission and phase chips (t1603_3).

Two axes, one authority. The LANE ("what happens next":
planned/human/agent/blocked) is derived from t1603_2's PHASE and from nothing
else — before this task it was a parallel ladder over the same
`TaskGateState`, which is what let a card's lane and its chip contradict each
other. `PhaseIsTheOnlyLaneAuthorityTest` freezes that structurally;
`LaneChipAgreementTests` freezes it behaviourally.

Fixtures are real task files written into the class fixture tree and parsed by
the production gate parser, with a valid `active_gates` tuple and the shipped
`metadata/gates.yaml` staged — so "active" vs "filtered" vs "absent from both"
stay genuinely distinct, and `plan_approved` / `review_approved` really are
`type: human` while `docs_updated` really is `kind: procedure`. A tree without
those does not merely lose cosmetics; it silently reclassifies.
"""

from __future__ import annotations

import ast
import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402

BOARD_SRC = REPO_ROOT / ".aitask-scripts" / "board" / "aitask_board.py"

#: The deferred-plan marker (t1595). Its presence on a `Ready` task is half of
#: `approved_unstarted`; every "no marker" control below drops exactly this line.
MARKER_FM = "plan_approved_at: 2026-08-25 10:24\n"


def _manager(ab):
    """Bare TaskManager built from the *fixture-bound* board module.

    `ab` is threaded in rather than imported: under the harness the board is
    loaded under a synthetic module name, so a local `import aitask_board` would
    reach a different module object than the one under test.
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
    mgr.gate_digest_cache = ab._DIGEST_UNSET
    mgr.settings = {}
    return mgr


def _run(gate: str, status: str, **fields) -> str:
    """One `## Gate Runs` marker line, matching the production writer's shape."""
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


#: Shared with the phase-axis and actor-axis suites — never re-defined here.
_tuple_fm = bf.active_tuple_fm


# --- Fixture bodies, named for the state they encode -------------------------

def _planned_body(*, extra_fm: str = "") -> str:
    """An approve-and-stop task: `Ready`, marked, AND carrying a ledger.

    The ledger is the whole point of this fixture. `plan-approved-stop.md`
    records `plan_approved: pass` BEFORE reverting the status and nothing
    strips `## Gate Runs`, so a real Planned task has `has_ledger` true,
    `resume_point == IMPLEMENT`, and a PENDING `review_approved`. A
    ledger-free "planned" fixture would satisfy every guard assertion below
    vacuously and is the wrong control.
    """
    return _body(
        "Ready",
        MARKER_FM + extra_fm + _tuple_fm(["plan_approved", "review_approved"],
                                         ["plan_approved", "review_approved"], []),
        _ledger(_run("plan_approved", "pass", type="human"),
                _run("review_approved", "pending", type="human")))


def _implementing_twin_body() -> str:
    """The same ledger and gates as `_planned_body`, but `Implementing`.

    The positive control for every guard: the ONLY difference is the status +
    marker pair, so a guard written as `has_ledger`-only — or as "always
    refuse" — fails here.
    """
    return _body(
        "Implementing",
        _tuple_fm(["plan_approved", "review_approved"],
                  ["plan_approved", "review_approved"], []),
        _ledger(_run("plan_approved", "pass", type="human"),
                _run("review_approved", "pending", type="human")))


class PlannedLaneTestBase(bf.FixtureBoardTestBase):
    """Shared plumbing: real task files in the class tree, real derivation."""

    def _write_task(self, name: str, body: str):
        path = self.tasks_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        self.addCleanup(path.unlink, missing_ok=True)
        return self.ab.Task.from_text(path, body)

    def _item(self, name: str, body: str, *, also: list[tuple[str, str]] = ()):
        """The single `InFlightItem` for `name`, with `also` staged alongside.

        `also` exists for dependency fixtures: since t1527 a dep id resolves
        against the tasks tree on disk, so the upstream must be a real file,
        not just an entry in `task_datas`.
        """
        mgr = _manager(self.ab)
        for extra_name, extra_body in also:
            extra = self._write_task(extra_name, extra_body)
            mgr.task_datas[extra.filename] = extra
        task = self._write_task(name, body)
        mgr.task_datas[task.filename] = task
        items = [i for i in mgr.get_inflight_items() if i.task_id == name.split("_")[0]]
        self.assertEqual(len(items), 1,
                         f"fixture {name} must yield exactly one in-flight item")
        return items[0], mgr

    def _chip(self, item) -> str:
        """The EXPANDED chip — the shared spec t1603_4 will reuse verbatim."""
        return self.ab.phase_chip_text(item.phase, item.provenance, item.progress,
                                       error=item.state_error)

    def _card_chip(self, item) -> str:
        """The COMPACT chip the card actually renders (label + fraction)."""
        return self.ab.phase_chip_text(item.phase, item.provenance, item.progress,
                                       error=item.state_error, compact=True)


# --- Admission ---------------------------------------------------------------

class PlannedAdmissionTests(PlannedLaneTestBase, unittest.TestCase):

    def test_ready_with_marker_and_ledger_is_admitted_as_planned(self):
        item, _ = self._item("t1300_planned.md", _planned_body())
        self.assertEqual(item.group, "planned")
        self.assertEqual(item.next_action, "approved plan — pick to implement")
        self.assertTrue(item.approved_unstarted)
        self.assertTrue(item.has_ledger)
        # The chip is derived, not restated: 1 of 2 active gates is satisfied.
        self.assertEqual((item.phase, item.provenance, item.progress),
                         ("plan_approved", "ledger", (1, 2)))
        self.assertEqual(self._chip(item), "plan approved · 1/2")

    def test_ready_with_marker_and_no_ledger_is_admitted_from_the_marker(self):
        """The marker is frontmatter and wholly independent of the ledger, so a
        task approved under a non-recording profile still reaches the lane —
        and its chip must NOT claim a missing ledger, which would be false for
        the reachable case where one exists but does not corroborate."""
        item, _ = self._item("t1301_planned_bare.md", _body("Ready", MARKER_FM))
        self.assertEqual(item.group, "planned")
        self.assertEqual((item.phase, item.provenance), ("plan_approved", "marker"))
        self.assertIsNone(item.progress)
        self.assertEqual(self._chip(item), "plan approved (from marker)")

    def test_ready_without_the_marker_stays_excluded(self):
        """NEGATIVE CONTROL for both rows above: the identical ledger-carrying
        fixture with the marker line removed must not enter the view at all.
        Without this, admission could be keyed on `has_ledger` and every
        assertion above would still pass."""
        mgr = _manager(self.ab)
        body = _planned_body().replace(MARKER_FM, "")
        self.assertNotIn("plan_approved_at", body)
        task = self._write_task("t1302_unmarked.md", body)
        mgr.task_datas[task.filename] = task
        self.assertEqual(mgr.get_inflight_items(), [])

    def test_non_ready_non_implementing_statuses_stay_excluded(self):
        """The pre-filter admits a superset of what the phase model accepts; a
        marked `Postponed` / `Editing` / `Done` task must still be rejected."""
        for status in ("Editing", "Postponed", "Done"):
            with self.subTest(status=status):
                mgr = _manager(self.ab)
                task = self._write_task(f"t1303_{status.lower()}.md",
                                        _body(status, MARKER_FM))
                mgr.task_datas[task.filename] = task
                self.assertEqual(mgr.get_inflight_items(), [])


# --- The routing hole the admission opens ------------------------------------

class PlannedRoutingGuardTests(PlannedLaneTestBase, unittest.TestCase):
    """`g resume` / `s sign-off` / `f fail` must refuse on an approved-but-
    unstarted task — advertisement AND action, on the underlying state.

    A Planned task carries a ledger whose `review_approved` is pending, so a
    `has_ledger`-keyed guard would offer a resume that bypasses the planning
    checkpoint and its remote drift check (t1595's visibility-not-routing
    constraint), and a sign-off on code that does not exist.
    """

    def _app(self, card):
        """A `KanbanApp` stubbed down to what the two guarded actions read
        before they decide. Records notifications, pushed screens, and whether
        the action reached its real body (`_focus_existing_agent_window` /
        `_append_human_gate` are the first calls past each guard)."""
        app = self.ab.KanbanApp.__new__(self.ab.KanbanApp)
        app._modal_is_active = lambda: False
        app._focused_card = lambda: card
        app.notices = []
        app.pushed = []
        app.reached = []
        app.notify = lambda msg, severity="information": app.notices.append(msg)
        app.push_screen = lambda *a, **k: app.pushed.append(a)
        app.refresh_board = lambda *a, **k: None
        app._focus_existing_agent_window = lambda num: (
            app.reached.append(("resume", num)) or True)
        app._append_human_gate = lambda focused, gate, status: app.reached.append(
            ("gate", gate, status))
        return app

    def _card(self, item):
        """An `InFlightTaskCard` without a widget lifecycle — the guards read
        only `.item`, and the bodies past them read `.task_data`."""
        card = self.ab.InFlightTaskCard.__new__(self.ab.InFlightTaskCard)
        card.item = item
        card.task_data = item.task
        return card

    def _drive(self, item):
        """(ops hint, app after `g`, app after `s`) for one item."""
        hint = self.ab.InFlightTaskCard._ops_hint(item)
        resume_app = self._app(self._card(item))
        self.ab.KanbanApp.action_gate_resume(resume_app)
        gate_app = self._app(self._card(item))
        self.ab.KanbanApp._record_focused_human_gate(gate_app, "pass")
        return hint, resume_app, gate_app

    def test_planned_card_offers_pick_only_and_both_actions_refuse(self):
        item, _ = self._item("t1310_planned.md", _planned_body())
        # Precondition: the fixture really does carry the ledger and the
        # pending human gate that make this hazardous.
        self.assertTrue(item.has_ledger)
        self.assertEqual(item.human_gates, ["review_approved"])

        hint, resume_app, gate_app = self._drive(item)
        self.assertEqual(hint, "[p pick]")
        for banned in ("[g resume]", "[s sign-off]", "[f fail]"):
            self.assertNotIn(banned, hint)

        self.assertEqual(resume_app.reached, [])
        self.assertEqual(resume_app.pushed, [])
        self.assertTrue(any("has not started" in n for n in resume_app.notices))

        self.assertEqual(gate_app.reached, [])
        self.assertTrue(any("has not started" in n for n in gate_app.notices))

    def test_implementing_twin_still_offers_and_reaches_every_op(self):
        """POSITIVE CONTROL. Same gates, same ledger, same pending human gate —
        only the status and marker differ. A guard written as `has_ledger`-only,
        or one that always refuses, fails here."""
        item, _ = self._item("t1311_twin.md", _implementing_twin_body())
        self.assertFalse(item.approved_unstarted)

        hint, resume_app, gate_app = self._drive(item)
        for expected in ("[p pick]", "[g resume]", "[s sign-off]", "[f fail]"):
            self.assertIn(expected, hint)
        self.assertEqual(resume_app.reached, [("resume", "1311")])
        self.assertEqual(gate_app.reached, [("gate", "review_approved", "pass")])
        self.assertEqual(resume_app.notices, [])
        self.assertEqual(gate_app.notices, [])

    def test_dependency_blocked_planned_task_still_refuses_every_route(self):
        """THE DISCRIMINATING CASE for the guard's KEY (finding 3b).

        A blocking dependency claims the lane first, so this task renders in
        **Blocked** — `group != "planned"`. Written as `group == "planned"`,
        all three guards pass every row above and hand back `g resume`,
        `s sign-off` and `f fail` here, on a task that was never implemented.
        Both halves are asserted: the card is still correctly shown as blocked,
        AND every route still refuses.
        """
        item, _ = self._item(
            "t1312_planned_blocked.md",
            _planned_body(extra_fm="depends: [1313]\n"),
            also=[("t1313_upstream.md", _body("Implementing"))])

        # Half one: the lane is genuinely NOT "planned" here.
        self.assertEqual(item.blockers, ["t1313"])
        self.assertEqual(item.group, "blocked")
        self.assertEqual(item.next_action, "blocked by dependencies")
        # ...while the underlying state is unchanged, which is what the guards read.
        self.assertTrue(item.approved_unstarted)
        # ...and the chip still reports the workflow phase, lane notwithstanding.
        self.assertEqual(self._chip(item), "plan approved · 1/2")

        # Half two: every route still refuses.
        hint, resume_app, gate_app = self._drive(item)
        self.assertEqual(hint, "[p pick]")
        self.assertEqual(resume_app.reached, [])
        self.assertEqual(gate_app.reached, [])


class PlannedCardRenderTests(PlannedLaneTestBase, unittest.TestCase):
    """Render-level: mount a real card and read what the Labels display, so the
    ops hint and the chip are asserted post-markup rather than as helper
    strings. `markup=False` is load-bearing on both — Rich would otherwise eat
    `[p pick]` and any bracket in a gate name or error string."""

    def _render(self, item, mgr):
        from textual.app import App
        from textual.widgets import Label

        InFlightTaskCard = self.ab.InFlightTaskCard

        async def go():
            class CardApp(App):
                def compose(self):
                    yield InFlightTaskCard(item, mgr, column_id="inflight-planned")

            app = CardApp()
            async with app.run_test(size=(90, 24)) as pilot:
                await pilot.pause()
                card = app.query_one(InFlightTaskCard)
                return {
                    cls: card.query_one(f".inflight-{cls}", Label).render().plain
                    for cls in ("ops", "action", "phase")
                }

        return asyncio.run(go())

    def test_planned_card_renders_pick_only_and_its_chip(self):
        item, mgr = self._item("t1320_planned.md", _planned_body())
        rendered = self._render(item, mgr)
        self.assertEqual(rendered["ops"], "[p pick]")
        self.assertEqual(rendered["action"], "approved plan — pick to implement")
        self.assertEqual(rendered["phase"], "plan approved · 1/2")

    def test_chip_renders_on_an_implementing_card_too(self):
        """The chip is on EVERY card, not only Planned ones: a chip that
        disappears makes its absence ambiguous, and the same value one lane
        over is not redundant (rows A/B)."""
        item, mgr = self._item("t1321_twin.md", _implementing_twin_body())
        rendered = self._render(item, mgr)
        self.assertEqual(rendered["phase"], "awaiting review · 1/2")
        self.assertIn("[g resume]", rendered["ops"])

    def test_no_ledger_card_chip_does_not_echo_its_own_action_line(self):
        """REGRESSION, found by live-checking a real 100-column terminal.

        The EXPANDED chip reads "No gate ledger — implementing (unknown)"
        directly beneath "No gate information yet — pick/resume": two lines
        saying the same thing on a 44-column card, the lower one in exactly the
        ledger jargon `test_inflight_card_renders_literal_ops_and_friendly_copy`
        keeps off this surface (t635_9). The card renders the COMPACT form — the
        phase axis and nothing else — while the expanded literal survives for
        t1603_4's detail surface.
        """
        item, mgr = self._item("t1322_bare.md", _body("Implementing"))
        rendered = self._render(item, mgr)
        self.assertEqual(rendered["action"], "No gate information yet — pick/resume")
        self.assertEqual(rendered["phase"], "implementing")
        self.assertNotIn("ledger", rendered["phase"].lower())
        # ...and the two lines are not restatements of one another.
        self.assertNotIn(rendered["phase"], rendered["action"])
        # The expanded form, which t1603_4 reuses verbatim, is unchanged.
        self.assertEqual(self._chip(item), "No gate ledger — implementing (unknown)")

    def test_compact_chip_never_carries_the_error_text(self):
        """A raw exception string has no budget on a 44-column card and would
        restate the action line's "gate state unavailable". The phase is still
        reported — `implementing`, which is what the task's own status asserts."""
        mgr = _manager(self.ab)
        body = _body("Implementing",
                     _tuple_fm(["plan_approved"], ["plan_approved"], []),
                     _ledger(_run("plan_approved", "pass", type="human")))
        task = self._write_task("t1323_unreadable.md", body)
        task.filepath = self.tasks_dir / "definitely_not_on_disk.md"
        mgr.task_datas[task.filename] = task
        item = mgr.get_inflight_items()[0]

        self.assertTrue(item.state_error)
        self.assertEqual(self._card_chip(item), "implementing")
        self.assertTrue(self._chip(item).startswith("Gate state unavailable: "))


# --- The two-axes model ------------------------------------------------------

class TwoAxisFixtureTests(PlannedLaneTestBase, unittest.TestCase):
    """The executable form of the claim the docs make. If either pair collapses
    to a single lane or a single chip, the model is wrong and this says so."""

    def test_same_phase_different_lanes(self):
        """Rows A/B: one phase (`plan_approved`), two lanes."""
        a, _ = self._item("t1330_approve_stop.md", _planned_body())
        b, _ = self._item(
            "t1331_resume_implement.md",
            _body("Implementing",
                  _tuple_fm(["plan_approved", "review_approved", "tests_pass"],
                            ["plan_approved", "review_approved", "tests_pass"], []),
                  _ledger(_run("plan_approved", "pass", type="human"),
                          _run("review_approved", "skip", type="human"),
                          _run("tests_pass", "pending", type="machine"))))
        self.assertEqual(a.phase, b.phase, "the pair must share ONE phase")
        self.assertEqual(a.phase, "plan_approved")
        self.assertEqual((a.group, b.group), ("planned", "agent"))

    def test_same_lane_different_phases(self):
        """Rows C/D: one lane (`human`), two phases."""
        c, _ = self._item(
            "t1332_pending_human.md",
            _body("Implementing",
                  _tuple_fm(["plan_approved", "review_approved"],
                            ["plan_approved", "review_approved"], []),
                  _ledger(_run("plan_approved", "pass", type="human"),
                          _run("review_approved", "pending", type="human"))))
        d, _ = self._item(
            "t1333_post_impl.md",
            _body("Implementing",
                  _tuple_fm(["plan_approved", "review_approved", "tests_pass"],
                            ["plan_approved", "review_approved", "tests_pass"], []),
                  _ledger(_run("plan_approved", "pass", type="human"),
                          _run("review_approved", "pass", type="human"),
                          _run("tests_pass", "pending", type="machine"))))
        self.assertEqual(c.group, d.group, "the pair must share ONE lane")
        self.assertEqual(c.group, "human")
        self.assertEqual((c.phase, d.phase), ("awaiting_review", "post_impl"))


# --- Lane/chip agreement across every ledger state ---------------------------

class LaneChipAgreementTests(PlannedLaneTestBase, unittest.TestCase):
    """The pre-phase mitigation, behavioural half.

    One table of `(lane, chip, next_action)` literals over every state the
    ledger can be in. A second lane derivation that drifts from the phase — the
    defect this task removes — shows up here as a pair that no longer matches.
    """

    def _rows(self):
        gated = _tuple_fm(["plan_approved", "review_approved"],
                          ["plan_approved", "review_approved"], [])
        machine = _tuple_fm(["plan_approved", "tests_pass"],
                            ["plan_approved", "tests_pass"], [])
        procedure = _tuple_fm(["plan_approved", "docs_updated", "review_approved"],
                              ["plan_approved", "docs_updated", "review_approved"], [])
        approved = _run("plan_approved", "pass", type="human")
        return [
            ("no_ledger", _body("Implementing"),
             ("agent", "No gate ledger — implementing (unknown)",
              "No gate information yet — pick/resume")),
            ("pending_human", _body("Implementing", gated, _ledger(approved)),
             ("human", "awaiting review · 1/2", "pending human gate")),
            ("failed_active", _body(
                "Implementing", machine,
                _ledger(approved, _run("tests_pass", "fail", type="machine"))),
             ("human", "awaiting review · 1/2",
              "failed gate — inspect/sign off or fail")),
            ("all_pass", _body(
                "Implementing", gated,
                _ledger(approved, _run("review_approved", "pass", type="human"))),
             ("human", "post-implementation · 2/2",
              "all gates pass — archive/re-enter")),
            ("post_impl", _body(
                "Implementing",
                _tuple_fm(["plan_approved", "review_approved", "tests_pass"],
                          ["plan_approved", "review_approved", "tests_pass"], []),
                _ledger(approved, _run("review_approved", "pass", type="human"),
                        _run("tests_pass", "pending", type="machine"))),
             ("human", "post-implementation · 2/3",
              "reviewed — post-implementation")),
            ("resume_implement", _body(
                "Implementing",
                _tuple_fm(["plan_approved", "review_approved", "tests_pass"],
                          ["plan_approved", "review_approved", "tests_pass"], []),
                _ledger(approved, _run("review_approved", "skip", type="human"),
                        _run("tests_pass", "pending", type="machine"))),
             ("agent", "plan approved · 2/3",
              "plan approved — resume implementation")),
            ("needs_attended_agent", _body(
                "Implementing", procedure,
                _ledger(approved, _run("review_approved", "pass", type="human"))),
             ("human", "needs attended agent · 2/3",
              "needs an attended agent: docs_updated")),
            ("planned_marker", _planned_body(),
             ("planned", "plan approved · 1/2",
              "approved plan — pick to implement")),
        ]

    def test_lane_and_chip_agree_across_every_ledger_state(self):
        seen_lanes, seen_phases = set(), set()
        for name, body, expected in self._rows():
            with self.subTest(state=name):
                item, _ = self._item(f"t134{len(seen_lanes)}_{name}.md"
                                     .replace(f"t134{len(seen_lanes)}",
                                              f"t1340{abs(hash(name)) % 100:02d}"),
                                     body)
                self.assertEqual(
                    (item.group, self._chip(item), item.next_action), expected)
                seen_lanes.add(item.group)
                seen_phases.add(item.phase)

        # Vacuity guards: the table must actually exercise more than one lane
        # and more than one phase, or every equality above could hold trivially.
        self.assertGreaterEqual(len(seen_lanes), 3, f"lanes exercised: {seen_lanes}")
        self.assertGreaterEqual(len(seen_phases), 4, f"phases exercised: {seen_phases}")

    # The `stale_signed` row of this table is asserted in
    # `tests/test_board_gate_digest_budget.py::StaleSignatureInFlightTests`
    # instead, and deliberately not duplicated here. Staleness is not a ledger
    # shape: it needs a real signal WITNESS file whose `code_digest=` no longer
    # matches a freshly computed `code_digest()`, which is what that module's
    # `_sign_all()` / `_mutate_code()` harness builds. A fixture that merely
    # writes `code_digest=` onto the ledger line produces `stale_signed == []`
    # and would pass this table vacuously — the wrong control.

    def test_unreadable_ledger_reports_the_error_on_both_axes(self):
        """`has_ledger` true with an unreadable state is a POSITIVE state, not
        an absent ledger: the lane stays `agent` and the chip names the error
        rather than degrading to the no-ledger wording."""
        mgr = _manager(self.ab)
        body = _body("Implementing",
                     _tuple_fm(["plan_approved"], ["plan_approved"], []),
                     _ledger(_run("plan_approved", "pass", type="human")))
        task = self._write_task("t1351_unreadable.md", body)
        # The exact combination production reaches: `has_ledger` is resolved
        # from `task.content` BEFORE the read that raises.
        task.filepath = self.tasks_dir / "definitely_not_on_disk.md"
        mgr.task_datas[task.filename] = task

        item = mgr.get_inflight_items()[0]
        self.assertTrue(item.state_error)
        self.assertEqual(item.group, "agent")
        self.assertEqual((item.phase, item.provenance), ("implementing", "error"))
        self.assertEqual(item.next_action, "gate state unavailable")
        self.assertTrue(self._chip(item).startswith("Gate state unavailable: "))


# --- The two deliberate deltas ----------------------------------------------

class LaneDeltaTests(PlannedLaneTestBase, unittest.TestCase):
    """The two shipped classifications the single-mapping refactor moved.

    Both are corrections, not accidents — pinned so a future edit that restores
    the old ladder has to argue with a test rather than pass silently.
    """

    def test_delta1_procedure_gate_before_review_is_the_humans(self):
        """Δ1. A pending `kind: procedure` gate is owed by a person launching an
        attended agent. The old ladder checked `resume_point` first and filed
        this under "Agent can continue"."""
        item, mgr = self._item(
            "t1360_delta1.md",
            _body("Implementing",
                  _tuple_fm(["plan_approved", "docs_updated", "review_approved"],
                            ["plan_approved", "docs_updated", "review_approved"], []),
                  _ledger(_run("plan_approved", "pass", type="human"),
                          _run("review_approved", "skip", type="human"))))
        # Precondition: this really is the resume_point the old ladder read.
        state = mgr.gate_state_for(item.task).state
        self.assertEqual(state.resume_point, "IMPLEMENT")
        self.assertEqual(item.phase, "needs_attended_agent")
        self.assertEqual(item.group, "human")
        self.assertEqual(item.next_action, "needs an attended agent: docs_updated")

    def test_delta2_postimpl_with_a_pending_human_gate_names_that_gate(self):
        """Δ2. `review_approved` passed — so `resume_point` really is POSTIMPL —
        but `merge_approved` is still pending, which is the ordinary state of a
        task between review and merge. The lane is unchanged (`human`); the
        sentence now says a human gate is pending instead of announcing a
        post-implementation phase, which the old ladder reached by testing
        `resume_point` ahead of the pending-human rung.
        """
        item, mgr = self._item(
            "t1361_delta2.md",
            _body("Implementing",
                  _tuple_fm(["plan_approved", "review_approved", "merge_approved"],
                            ["plan_approved", "review_approved", "merge_approved"],
                            []),
                  _ledger(_run("plan_approved", "pass", type="human"),
                          _run("review_approved", "pass", type="human"),
                          _run("merge_approved", "pending", type="human"))))
        # Precondition: this really is the resume_point the old ladder read
        # first — otherwise the row would not be discriminating.
        state = mgr.gate_state_for(item.task).state
        self.assertEqual(state.resume_point, "POSTIMPL")
        self.assertEqual(item.human_gates, ["merge_approved"])
        self.assertEqual(item.phase, "awaiting_review")
        self.assertEqual(item.group, "human")
        self.assertEqual(item.next_action, "pending human gate")


# --- The pre-phase mitigation, structural half -------------------------------

class PhaseIsTheOnlyLaneAuthorityTest(unittest.TestCase):
    """FROZEN: the lane is derived from the phase and from primitives, never
    from a second read of the gate state.

    Modelled on `SharedGatePredicateContractTest` (t1642) and for the same
    reason: an outcome table alone cannot protect this. A re-implementation
    that DUPLICATES the corrected ordering inside `_inflight_item_for` passes
    every behavioural assertion in this file today and silently restores the
    drift. The delegation is frozen here, so removing it must be a conscious
    edit to this test.
    """

    #: Reading any of these off a `TaskGateState` IS the lane logic that must
    #: live in the phase model and nowhere else.
    FORBIDDEN_ATTRS = {"resume_point", "archive_decision", "stale_signed",
                       "archive_pending", "active_gates", "filtered_gates",
                       "current"}

    def _tree(self):
        return ast.parse(BOARD_SRC.read_text(encoding="utf-8"))

    def _function(self, name: str) -> ast.FunctionDef:
        for node in ast.walk(self._tree()):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name == name:
                return node
        self.fail(f"{name} not found — renamed or deleted, and this scan would "
                  "otherwise pass vacuously")

    def _callers_of(self, name: str) -> set[str]:
        found: set[str] = set()
        stack: list[str] = []

        class V(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                stack.append(node.name)
                self.generic_visit(node)
                stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Call(self, node):
                fn = node.func
                hit = (isinstance(fn, ast.Name) and fn.id == name) or (
                    isinstance(fn, ast.Attribute) and fn.attr == name)
                if hit and stack:
                    found.add(stack[-1])
                self.generic_visit(node)

        V().visit(self._tree())
        return found

    def test_lane_helper_reads_no_gate_state(self):
        for name in ("_inflight_lane", "_inflight_next_action"):
            with self.subTest(function=name):
                fn = self._function(name)
                attrs = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
                offending = attrs & self.FORBIDDEN_ATTRS
                self.assertEqual(
                    offending, set(),
                    f"{name} reads {sorted(offending)} off the gate state — that "
                    "is the second derivation t1603_3 removed")

    def test_lane_helper_has_exactly_its_one_caller(self):
        for name in ("_inflight_lane", "_inflight_next_action"):
            with self.subTest(function=name):
                self.assertEqual(self._callers_of(name), {"_inflight_item_for"})

    def test_classifier_no_longer_branches_on_the_gate_state(self):
        """The other half: the ladder must be GONE from `_inflight_item_for`,
        not merely duplicated into a helper. `stale_signed` is exempt — the item
        still carries the list as a fact (it is what the re-sign copy names) —
        but the routing attributes must not reappear."""
        fn = self._function("_inflight_item_for")
        attrs = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
        offending = attrs & (self.FORBIDDEN_ATTRS - {"stale_signed"})
        self.assertEqual(offending, set(),
                         f"_inflight_item_for still reads {sorted(offending)}")


class LaneMappingTotalityTests(PlannedLaneTestBase, unittest.TestCase):

    def test_every_phase_has_a_lane_and_every_lane_is_known(self):
        """A sixth phase must not be able to land without a lane: the mapping
        would raise `KeyError` inside a refresh and take the board down."""
        self.assertEqual(set(self.ab.LANE_FOR_PHASE), set(self.ab.WORKFLOW_PHASES))
        self.assertTrue(set(self.ab.LANE_FOR_PHASE.values())
                        <= set(self.ab.INFLIGHT_LANES))
        self.assertEqual(set(self.ab.PHASE_LABELS), set(self.ab.WORKFLOW_PHASES))

    def test_planned_is_a_lane_but_never_a_phase(self):
        """The two axes share no vocabulary — `planned` is a LANE value and
        `plan_approved` is a PHASE value, and neither list may borrow the
        other's."""
        self.assertIn("planned", self.ab.INFLIGHT_LANES)
        self.assertNotIn("planned", self.ab.WORKFLOW_PHASES)
        self.assertNotIn("plan_approved", self.ab.INFLIGHT_LANES)

    def test_lanes_conserve_every_item_exactly_once(self):
        """No lane swallows an item and none double-counts one: the grouping the
        refresh path builds must partition `get_inflight_items()`."""
        mgr = _manager(self.ab)
        for name, body in (
            ("t1370_planned.md", _planned_body()),
            ("t1371_impl.md", _implementing_twin_body()),
            ("t1372_bare.md", _body("Implementing")),
            ("t1373_excluded.md", _body("Ready")),
        ):
            task = self._write_task(name, body)
            mgr.task_datas[task.filename] = task

        items = mgr.get_inflight_items()
        grouped = {lane: [] for lane in self.ab.INFLIGHT_LANES}
        for item in items:
            self.assertIsInstance(item.group, str)
            grouped[item.group].append(item.task_id)

        self.assertEqual(sum(len(v) for v in grouped.values()), len(items))
        self.assertEqual(len(items), 3, "the Ready-without-marker task is excluded")
        flat = [tid for members in grouped.values() for tid in members]
        self.assertEqual(len(flat), len(set(flat)), "a task id appears in two lanes")


# --- Post-phase mitigation: the narrow-terminal budget -----------------------

class NarrowTerminalLaneBudgetTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """t1603_3 post-phase risk mitigation.

    MEASURED (swept 80→200 columns, headless, then confirmed in a real pty):
    each lane occupies `width: 44` and the `margin: (0, 1)` gaps COLLAPSE
    between neighbours, so `n` lanes need `45n + 1` columns — **181 for four**,
    up from 136 for three. `min_width: 34` never engages: `#board_container` is
    a `HorizontalScroll`, so the columns keep their preferred 44 at every
    terminal width and the container scrolls instead. Three lanes therefore
    already scrolled below 136 columns before this task; the fourth extends an
    existing scroll rather than introducing one.

    The chosen behaviour is the status quo made deliberate: below 181 the view
    SCROLLS, and no lane is dropped, folded or collapsed away.
    """

    #: `45n + 1` — the measured geometry, as a formula so it stays true if a
    #: lane is ever added or removed. Pinned live below.
    LANE_SPAN = 45 * 4 + 1                       # 181 columns

    def test_lane_vocabulary_is_complete_and_distinct(self):
        self.assertEqual(len(self.ab.INFLIGHT_LANES), 4)
        self.assertEqual(set(self.ab.InFlightColumn.TITLES),
                         set(self.ab.INFLIGHT_LANES))
        self.assertEqual(set(self.ab.InFlightColumn.COLORS),
                         set(self.ab.INFLIGHT_LANES))
        # Four distinct lane colours — a repeated one would make two lanes
        # indistinguishable at a glance, which is the whole point of the split.
        self.assertEqual(len(set(self.ab.InFlightColumn.COLORS.values())), 4)

    def test_all_four_lanes_render_and_the_view_scrolls_when_narrow(self):
        InFlightColumn = self.ab.InFlightColumn
        KanbanApp = self.ab.KanbanApp

        async def go():
            app = KanbanApp()
            # 100 columns: well below the measured 181-column span, so this is
            # genuinely the narrow case rather than a wide one that would make
            # every assertion below vacuous.
            async with app.run_test(size=(100, 40)) as pilot:
                await pilot.pause()
                await pilot.press("i")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(app.base_filter, "inflight")

                columns = list(app.query(InFlightColumn))
                self.assertEqual([c.group for c in columns],
                                 list(self.ab.INFLIGHT_LANES),
                                 "a lane was dropped or reordered when narrow")
                self.assertEqual(
                    [c.query_one("ColumnHeader").col_title for c in columns],
                    [InFlightColumn.TITLES[g] for g in self.ab.INFLIGHT_LANES])

                container = app.query_one("#board_container")
                # The measurement itself, pinned: narrow the lanes, change the
                # margin, or add a fifth lane and the threshold recorded in the
                # plan stops being true — this fails before the layout changes
                # silently.
                self.assertEqual(container.virtual_size.width, self.LANE_SPAN)
                self.assertEqual([c.outer_size.width for c in columns],
                                 [44] * 4,
                                 "min_width must NOT engage — the columns keep "
                                 "their preferred width and the view scrolls")
                self.assertGreater(
                    container.virtual_size.width, container.container_size.width,
                    "four lanes must overflow a 100-column terminal — if they "
                    "fit, the geometry changed and the recorded threshold is stale")
                self.assertTrue(container.allow_horizontal_scroll,
                                "the overflow must be reachable by scrolling")

        asyncio.run(go())


if __name__ == "__main__":
    unittest.main()
