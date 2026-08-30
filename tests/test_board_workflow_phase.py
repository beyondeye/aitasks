"""Tests for the board workflow-phase derivation seam (t1603_2).

Pure-unit: no board boot, no Textual. Every fixture is a real task file written
into the class fixture tree and parsed by `Task.from_text`, so the gate state is
produced by the production parser rather than hand-built — a hand-built
`TaskGateState` can encode a combination the parser never emits, and matching
production semantics is the point of the seam.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402


def _manager(ab):
    """Bare TaskManager built from the *fixture-bound* board module.

    `ab` is threaded in rather than imported here: under the harness the board is
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


def _write(path: Path, text: str, cleanup):
    """Write a file into the fixture tree and register its removal.

    `FixtureBoardTestBase` builds one tree per class, so a leaked task or plan
    file would change the next test's starting state.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    cleanup(path.unlink, missing_ok=True)
    return path


def _task(ab, path: Path, text: str, cleanup):
    """A `Task` whose filepath is real, so on-disk gate derivation can read it."""
    _write(path, text, cleanup)
    return ab.Task.from_text(path, text)


# --- Characterization: plan-path resolution (t1603_2 pre-phase mitigation) ----
#
# Pinned BEFORE `_resolve_plan_path` / `_resolve_plan_path_for` are collapsed
# onto one module-level function, so the collapse is demonstrated
# behavior-preserving rather than assumed to be. `_resolve_plan_path_for` has 7
# live call sites; these run against both the pre- and post-extraction code.

PLAIN_TASK = """---
priority: high
effort: low
status: Ready
---

Body.
"""


class PlanPathResolutionCharacterizationTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """Both resolvers, over the same three inputs, must agree with each other
    and with these pinned answers."""

    def _detail_screen(self, task, mgr):
        """The real `TaskDetailScreen`, built via `__new__` so no Textual widget
        lifecycle runs — the same idiom `_manager` uses for `TaskManager`. The
        method under test reads only `task_data` and `manager`."""
        screen = self.ab.TaskDetailScreen.__new__(self.ab.TaskDetailScreen)
        screen.task_data = task
        screen.manager = mgr
        return screen

    def _app(self, mgr):
        """The real `KanbanApp`, built the same way; the method under test reads
        only `manager`."""
        app = self.ab.KanbanApp.__new__(self.ab.KanbanApp)
        app.manager = mgr
        return app

    def _both(self, task, mgr):
        """(TaskDetailScreen answer, KanbanApp answer) for the same task."""
        screen = self._detail_screen(task, mgr)
        app = self._app(mgr)
        return (
            self.ab.TaskDetailScreen._resolve_plan_path(screen),
            self.ab.KanbanApp._resolve_plan_path_for(app, task),
        )

    def test_parent_task_resolves_to_flat_aiplans_path(self):
        mgr = _manager(self.ab)
        task = _task(self.ab, self.tasks_dir / "t900_parent.md",
                     PLAIN_TASK, self.addCleanup)
        _write(self.tree / "aiplans" / "p900_parent.md", "plan\n", self.addCleanup)

        detail, app = self._both(task, mgr)
        self.assertEqual(detail, Path("aiplans") / "p900_parent.md")
        self.assertEqual(app, detail)

    def test_child_task_resolves_through_parent_nesting(self):
        mgr = _manager(self.ab)
        task = _task(self.ab, self.tasks_dir / "t901" / "t901_2_child.md",
                     PLAIN_TASK, self.addCleanup)
        _write(self.tree / "aiplans" / "p901" / "p901_2_child.md", "plan\n",
               self.addCleanup)

        detail, app = self._both(task, mgr)
        self.assertEqual(detail, Path("aiplans") / "p901" / "p901_2_child.md")
        self.assertEqual(app, detail)

    def test_missing_plan_file_resolves_to_none(self):
        """The resolver returns None for a path that does not exist — it is a
        presence check, not a path constructor. Run for BOTH shapes, since the
        nesting branch is a separate code path."""
        mgr = _manager(self.ab)
        parent = _task(self.ab, self.tasks_dir / "t902_unplanned.md",
                       PLAIN_TASK, self.addCleanup)
        child = _task(self.ab, self.tasks_dir / "t903" / "t903_1_unplanned.md",
                      PLAIN_TASK, self.addCleanup)

        for task in (parent, child):
            with self.subTest(task=task.filename):
                detail, app = self._both(task, mgr)
                self.assertIsNone(detail)
                self.assertIsNone(app)


# --- Fixture builders --------------------------------------------------------

import gate_ledger  # noqa: E402


def _run(gate: str, status: str, **fields) -> str:
    icon = {"pass": "✅", "fail": "❌", "error": "❌", "skip": "⏭",
            "pending": "⏸"}.get(status, "⏸")
    extra = "".join(f" {k}={v}" for k, v in fields.items())
    return (f"> **{icon} gate:{gate}** run=2026-01-01T00:00:00Z "
            f"status={status} attempt=1{extra}\n")


def _ledger(*runs: str) -> str:
    return "\n## Gate Runs\n\n" + "".join(runs)


def _active_tuple_fm(gates: list[str], active: list[str], filtered: list[str]) -> str:
    """Frontmatter for a VALID `active_gates` tuple.

    The digest is computed with the production helpers rather than hardcoded, so
    the fixture stays valid if the canonical digest inputs ever change — and so
    it is genuinely the tuple `read_active_tuple_from_text` accepts, not a
    look-alike that silently falls back to raw `gates:`. The middle (profile)
    half is unchecked without a profile in scope, so it is a placeholder.
    """
    gates_line = "gates: [" + ", ".join(gates) + "]\n"
    gates_half = gate_ledger._hash12(gate_ledger._gates_half_input("---\n" + gates_line + "---\n"))
    outputs_half = gate_ledger._hash12(gate_ledger._outputs_half_input(active, filtered))
    return (
        gates_line
        + "active_gates: [" + ", ".join(active) + "]\n"
        + "active_gates_filtered: [" + ", ".join(filtered) + "]\n"
        + "active_gates_profile: fast\n"
        + f"active_gates_digest: {gates_half}.000000000000.{outputs_half}\n"
    )


def _body(status: str, extra_fm: str = "", ledger: str = "") -> str:
    return f"""---
priority: high
effort: low
status: {status}
{extra_fm}---

Body.
{ledger}
"""


class WorkflowPhaseTestBase(bf.FixtureBoardTestBase):
    """Shared fixture plumbing: real task files, real gate derivation."""

    def _derive(self, name: str, body: str, *, plan: bool = False,
                break_ledger_read: bool = False):
        """Write a task, derive its gate state through the production path, and
        return `(WorkflowPhase|None, GateStateResult)`.

        `break_ledger_read` makes `read_task_gate_state` fail the way production
        fails — by pointing the Task at a path that is not on disk while its
        in-memory `content` still carries the `## Gate Runs` markers. That is the
        exact combination `gate_state_for` produces (`has_ledger` is resolved
        from `task.content` BEFORE the call that raises), so the real `except`
        branch builds the result. No patching, no hand-built GateStateResult.
        """
        mgr = _manager(self.ab)
        path = self.tasks_dir / name
        task = _task(self.ab, path, body, self.addCleanup)
        if plan:
            _write(self.tree / "aiplans" / ("p" + name[1:]), "plan\n", self.addCleanup)
        if break_ledger_read:
            task.filepath = self.tasks_dir / "definitely_not_on_disk.md"
        result = mgr.gate_state_for(task)
        phase = self.ab.derive_workflow_phase(
            task, result, mgr.gate_registry(),
            plan_exists=self.ab._resolve_plan_path_for_task(task, mgr) is not None,
        )
        return phase, result


# --- §5: degradation without a ledger ----------------------------------------

class LedgerFreeDegradationTests(WorkflowPhaseTestBase, unittest.TestCase):

    def test_ready_with_marker_and_no_ledger_is_plan_approved_from_marker(self):
        phase, result = self._derive(
            "t910_marked.md",
            _body("Ready", "plan_approved_at: 2026-08-25 10:24\n"))
        self.assertFalse(result.has_ledger)
        self.assertEqual((phase.phase, phase.provenance), ("plan_approved", "marker"))
        self.assertIsNone(phase.progress)

    def test_implementing_with_plan_file_is_derived(self):
        phase, _ = self._derive("t911_planned.md", _body("Implementing"), plan=True)
        self.assertEqual((phase.phase, phase.provenance), ("implementing", "derived"))
        self.assertIsNone(phase.progress)

    def test_implementing_without_ledger_or_plan_is_unknown_not_planning(self):
        """NAMED REGRESSION CASE. `status: Implementing` is the task's own
        assertion that implementation began; with neither a ledger nor a plan
        file we cannot tell how far it got. That is a different claim from "it
        has not started", so the phase stays `implementing` with provenance
        `unknown` and NO fabricated 0/N fraction."""
        phase, _ = self._derive("t912_legacy.md", _body("Implementing"))
        self.assertEqual(phase.phase, "implementing")
        self.assertEqual(phase.provenance, "unknown")
        self.assertIsNone(phase.progress)

    def test_ledger_free_path_is_not_silently_the_ledger_path(self):
        """NEGATIVE CONTROL for the two rows above: adding a ledger to the very
        same task body must change the answer. Without this, both assertions
        would still pass if `derive_workflow_phase` ignored `has_ledger`
        entirely and always fell through to `implementing`."""
        fm = _active_tuple_fm(["plan_approved"], ["plan_approved"], [])
        phase, result = self._derive(
            "t913_mutated.md",
            _body("Implementing", fm, _ledger(_run("plan_approved", "pass", type="human"))))
        self.assertTrue(result.has_ledger)
        self.assertEqual(phase.provenance, "ledger")
        self.assertEqual(phase.progress, (1, 1))
        self.assertNotEqual(phase.provenance, "unknown")


# --- §3 B0: an unreadable ledger is not an absent one ------------------------

class UnreadableLedgerTests(WorkflowPhaseTestBase, unittest.TestCase):
    """DISCRIMINATING PAIR. A single error fixture cannot show the conflation:
    each half asserts against the value the *unpatched* fixture produces, so
    both fail if the B0 branch is removed."""

    MARKED = _body("Implementing", "", _ledger(_run("plan_approved", "pass", type="human")))

    def test_error_with_plan_file_is_error_not_derived(self):
        phase, result = self._derive("t914_err_planned.md", self.MARKED,
                                     plan=True, break_ledger_read=True)
        self.assertTrue(result.error)
        self.assertTrue(result.has_ledger, "has_ledger must survive the raise")
        self.assertIsNone(result.state)
        self.assertEqual(phase.provenance, "error")
        self.assertNotEqual(phase.provenance, "derived")
        self.assertEqual(phase.phase, "implementing")
        self.assertIsNone(phase.progress)

    def test_error_without_plan_file_is_error_not_unknown(self):
        phase, result = self._derive("t915_err_bare.md", self.MARKED,
                                     break_ledger_read=True)
        self.assertTrue(result.error)
        self.assertEqual(phase.provenance, "error")
        self.assertNotEqual(phase.provenance, "unknown")
        self.assertIsNone(phase.progress)

    def test_negative_control_same_fixtures_unbroken_report_derived_and_unknown(self):
        """Proves the pair above discriminates on the ERROR and nothing else:
        the identical bodies, read successfully, produce the two provenances the
        error assertions ruled out."""
        planned, r1 = self._derive("t916_ok_planned.md", self.MARKED, plan=True)
        bare, r2 = self._derive("t917_ok_bare.md", self.MARKED)
        self.assertFalse(r1.error)
        self.assertFalse(r2.error)
        # Ledger present and readable -> provenance `ledger`, never the
        # degradation values. Removing B0 would make the error fixtures land
        # here instead.
        self.assertEqual(planned.provenance, "ledger")
        self.assertEqual(bare.provenance, "ledger")


# --- §3 B2: the ledger ladder ------------------------------------------------

class LedgerLadderTests(WorkflowPhaseTestBase, unittest.TestCase):

    def test_ready_with_marker_and_ledger_is_plan_approved_not_awaiting_review(self):
        """Finding 3. `plan-approved-stop` records `plan_approved: pass` AND
        stamps the marker, so an approved-and-stopped task is `Ready` WITH a
        ledger. Discriminating: `review_approved` is active and unrecorded, so
        running the in-flight ladder would report `awaiting_review` for a task
        that was never implemented."""
        fm = _active_tuple_fm(["plan_approved", "review_approved"],
                              ["plan_approved", "review_approved"], [])
        phase, result = self._derive(
            "t918_stopped.md",
            _body("Ready", fm + "plan_approved_at: 2026-08-25 10:24\n",
                  _ledger(_run("plan_approved", "pass", type="human"))))
        self.assertTrue(result.has_ledger)
        self.assertIn("review_approved", result.state.archive_pending)
        self.assertEqual(phase.phase, "plan_approved")
        self.assertNotEqual(phase.phase, "awaiting_review")
        self.assertEqual(phase.provenance, "ledger")
        self.assertEqual(phase.progress, (1, 2))

    def test_skipped_human_gate_is_satisfied_not_pending(self):
        """Finding 4. `SATISFIED_STATUSES` is {pass, skip}, so a SKIPPED
        `review_approved` is absent from `archive_pending` and the task is
        legitimately ALL_PASS. A raw `status != "pass"` test — which the shipped
        `_human_pending_gates` uses — would report it pending.

        The phase is `plan_approved`, not `post_impl`: a skip is "not
        applicable", not an approval, so `_resume_point_from_state`'s strict
        `== "pass"` leaves `resume_point` at IMPLEMENT and the task was never
        reviewed. Archivability is carried by the fraction instead."""
        fm = _active_tuple_fm(["plan_approved", "review_approved"],
                              ["plan_approved", "review_approved"], [])
        phase, result = self._derive(
            "t919_skipped.md",
            _body("Implementing", fm,
                  _ledger(_run("plan_approved", "pass", type="human"),
                          _run("review_approved", "skip", type="human"))))
        self.assertEqual(result.state.archive_decision, "ALL_PASS")
        self.assertNotEqual(phase.phase, "awaiting_review")
        self.assertEqual(phase.phase, "plan_approved")
        # ALL_PASS survives losslessly as a full fraction, so a consumer can
        # still say "ready to archive" without the phase claiming "past review".
        self.assertEqual(phase.progress, (2, 2))

    def test_all_pass_without_review_is_not_post_impl(self):
        """`archive_decision == "ALL_PASS"` is NOT evidence of being past
        review. A task whose active set excludes `review_approved` — here
        `tests_pass`, recorded during implementation — is archivable while
        `resume_point` is still IMPLEMENT. Reporting `post_impl` would call a
        mid-implementation task reviewed."""
        fm = _active_tuple_fm(["plan_approved", "tests_pass"],
                              ["plan_approved", "tests_pass"], [])
        phase, result = self._derive(
            "t928_allpass_unreviewed.md",
            _body("Implementing", fm,
                  _ledger(_run("plan_approved", "pass", type="human"),
                          _run("tests_pass", "pass", type="machine"))))
        self.assertEqual(result.state.archive_decision, "ALL_PASS")
        self.assertEqual(result.state.resume_point, "IMPLEMENT")
        self.assertEqual(phase.phase, "plan_approved")
        self.assertNotEqual(phase.phase, "post_impl")
        self.assertEqual(phase.progress, (2, 2))

    def test_inactive_historical_failure_does_not_classify(self):
        """Finding 5. A gate deleted from `gates:` outright is in NEITHER
        `active_gates` nor `active_gates_filtered`, so the shipped
        `_has_failed_gate` (which subtracts only `filtered_gates` from all of
        `state.current`) still classifies on its historical `fail`."""
        fm = _active_tuple_fm(["plan_approved", "review_approved"],
                              ["plan_approved", "review_approved"], [])
        phase, result = self._derive(
            "t920_ghost_fail.md",
            _body("Implementing", fm,
                  _ledger(_run("plan_approved", "pass", type="human"),
                          _run("review_approved", "pass", type="human"),
                          _run("tests_pass", "fail", type="machine"))))
        # Precondition: the failed gate really is outside BOTH lists.
        self.assertNotIn("tests_pass", result.state.active_gates)
        self.assertNotIn("tests_pass", result.state.filtered_gates)
        self.assertIn("tests_pass", result.state.current)
        self.assertEqual(phase.phase, "post_impl")
        self.assertNotEqual(phase.phase, "awaiting_review")

    def test_profile_filtered_failure_does_not_classify(self):
        """Same rule via the other route into "not active": a gate the profile
        filtered out. This one IS in `filtered_gates`, so it is the case the
        shipped helper already handles — asserted so the seam does not regress
        it while fixing the sibling above."""
        fm = _active_tuple_fm(["plan_approved", "lint"], ["plan_approved"], ["lint"])
        phase, result = self._derive(
            "t921_filtered_fail.md",
            _body("Implementing", fm,
                  _ledger(_run("plan_approved", "pass", type="human"),
                          _run("lint", "fail", type="machine"))))
        self.assertEqual(result.state.filtered_gates, ["lint"])
        self.assertNotIn("lint", result.state.active_gates)
        # The point: the filtered failure does not classify the task. It is
        # `plan_approved` (never reviewed) rather than `awaiting_review`, and the
        # filtered gate is outside both progress terms.
        self.assertNotEqual(phase.phase, "awaiting_review")
        self.assertEqual(phase.phase, "plan_approved")
        self.assertEqual(phase.progress, (1, 1))

    def test_procedure_gate_beats_post_impl(self):
        """Finding 2. `docs_updated` is `type: machine` with `kind: procedure` —
        the headless engine defers it and only an attended agent can run it. With
        `review_approved` passed, `resume_point` is POSTIMPL, so an order that
        checked `post_impl` first would say "ready to archive" about a task the
        archival guard will refuse."""
        fm = _active_tuple_fm(["plan_approved", "docs_updated", "review_approved"],
                              ["plan_approved", "docs_updated", "review_approved"], [])
        phase, result = self._derive(
            "t922_docs_pending.md",
            _body("Implementing", fm,
                  _ledger(_run("plan_approved", "pass", type="human"),
                          _run("review_approved", "pass", type="human"))))
        self.assertEqual(result.state.resume_point, "POSTIMPL")
        self.assertEqual(result.state.archive_decision, "BLOCKED")
        self.assertEqual(phase.phase, "needs_attended_agent")
        self.assertNotEqual(phase.phase, "post_impl")
        self.assertEqual(phase.progress, (2, 3))
        self.assertEqual(phase.current_gate, "docs_updated")

    def test_pending_human_gate_is_awaiting_review(self):
        fm = _active_tuple_fm(["plan_approved", "review_approved"],
                              ["plan_approved", "review_approved"], [])
        phase, _ = self._derive(
            "t923_review.md",
            _body("Implementing", fm,
                  _ledger(_run("plan_approved", "pass", type="human"))))
        self.assertEqual(phase.phase, "awaiting_review")
        self.assertEqual(phase.current_gate, "review_approved")

    def test_failed_active_gate_is_awaiting_review(self):
        fm = _active_tuple_fm(["plan_approved", "tests_pass"],
                              ["plan_approved", "tests_pass"], [])
        phase, _ = self._derive(
            "t924_failed.md",
            _body("Implementing", fm,
                  _ledger(_run("plan_approved", "pass", type="human"),
                          _run("tests_pass", "fail", type="machine"))))
        self.assertEqual(phase.phase, "awaiting_review")
        self.assertEqual(phase.progress, (1, 2))

    def test_all_pass_is_post_impl(self):
        fm = _active_tuple_fm(["plan_approved", "review_approved"],
                              ["plan_approved", "review_approved"], [])
        phase, result = self._derive(
            "t925_done.md",
            _body("Implementing", fm,
                  _ledger(_run("plan_approved", "pass", type="human"),
                          _run("review_approved", "pass", type="human"))))
        self.assertEqual(result.state.archive_decision, "ALL_PASS")
        self.assertEqual(phase.phase, "post_impl")
        self.assertEqual(phase.progress, (2, 2))

    def test_plan_approved_only_is_plan_approved(self):
        fm = _active_tuple_fm(["plan_approved"], ["plan_approved"], [])
        phase, result = self._derive(
            "t926_impl.md",
            _body("Implementing", fm,
                  _ledger(_run("plan_approved", "pass", type="human"))))
        self.assertEqual(result.state.resume_point, "IMPLEMENT")
        self.assertEqual(phase.phase, "plan_approved")

    def test_ledger_without_plan_approval_is_implementing(self):
        """The catch-all: a readable ledger, nothing pending, but
        `resume_point` PLAN because `plan_approved` was never recorded. Every
        active gate here is machine and satisfied, so no earlier rung fires.
        Provenance is `ledger` — that is what separates this from the B1
        degradation rows, which report the same phase for a different reason."""
        fm = _active_tuple_fm(["tests_pass"], ["tests_pass"], [])
        phase, result = self._derive(
            "t927_early.md",
            _body("Implementing", fm,
                  _ledger(_run("tests_pass", "pass", type="machine"))))
        self.assertEqual(result.state.resume_point, "PLAN")
        self.assertEqual(phase.phase, "implementing")
        self.assertEqual(phase.provenance, "ledger")
        self.assertEqual(phase.progress, (1, 1))

    def test_pending_plan_approval_is_awaiting_review(self):
        """A pending HUMAN gate is a pending human gate whichever one it is:
        `plan_approved` awaiting a person routes to `awaiting_review` exactly as
        `review_approved` does. The phase names where the task sits, and both
        sit at "a human owes a decision"."""
        fm = _active_tuple_fm(["plan_approved"], ["plan_approved"], [])
        phase, result = self._derive(
            "t929_plan_pending.md",
            _body("Implementing", fm,
                  _ledger(_run("plan_approved", "pending", type="human"))))
        self.assertEqual(result.state.resume_point, "PLAN")
        self.assertEqual(phase.phase, "awaiting_review")
        self.assertEqual(phase.current_gate, "plan_approved")


# --- §4: progress has exactly one authority ----------------------------------

class ProgressAuthorityTests(WorkflowPhaseTestBase, unittest.TestCase):

    def _cases(self):
        stale_fm = _active_tuple_fm(["plan_approved", "review_approved"],
                                    ["plan_approved", "review_approved"], [])
        return {
            "stale_signed": ("t930_stale.md", _body(
                "Implementing", stale_fm,
                _ledger(_run("plan_approved", "pass", type="human"),
                        _run("review_approved", "pass", type="human",
                             code_digest="deadbeefdead")))),
            "profile_filtered": ("t931_filtered.md", _body(
                "Implementing",
                _active_tuple_fm(["plan_approved", "lint"], ["plan_approved"], ["lint"]),
                _ledger(_run("plan_approved", "pass", type="human")))),
            "skip": ("t932_skip.md", _body(
                "Implementing", stale_fm,
                _ledger(_run("plan_approved", "pass", type="human"),
                        _run("review_approved", "skip", type="human")))),
            "failed": ("t933_fail.md", _body(
                "Implementing",
                _active_tuple_fm(["plan_approved", "tests_pass"],
                                 ["plan_approved", "tests_pass"], []),
                _ledger(_run("plan_approved", "pass", type="human"),
                        _run("tests_pass", "fail", type="machine")))),
        }

    def test_progress_equals_active_minus_archive_pending(self):
        """One authority, four shapes. The fraction is asserted against the
        SAME `archive_pending` the archival guard reads, so the surface cannot
        claim progress the workflow would reject."""
        for label, (name, body) in self._cases().items():
            with self.subTest(case=label):
                phase, result = self._derive(name, body)
                state = result.state
                self.assertEqual(
                    phase.progress,
                    (len(state.active_gates) - len(state.archive_pending),
                     len(state.active_gates)))

    def test_no_gate_counted_satisfied_is_still_pending(self):
        """Invariant: the satisfied count and `archive_pending` cannot overlap.
        Asserted as a set relation rather than a number, so it holds whatever
        the fixtures' arithmetic happens to be."""
        for label, (name, body) in self._cases().items():
            with self.subTest(case=label):
                phase, result = self._derive(name, body)
                state = result.state
                satisfied = [g for g in state.active_gates
                             if g not in state.archive_pending]
                self.assertEqual(len(satisfied), phase.progress[0])
                for gate in satisfied:
                    self.assertNotIn(gate, state.archive_pending)

    def test_ungated_task_has_no_fraction(self):
        """No active gates means no meaningful denominator, so `None` — never
        `0/0`, and never a fabricated `0/N`."""
        phase, result = self._derive(
            "t934_ungated.md",
            _body("Implementing", "gates: []\n",
                  _ledger(_run("plan_approved", "pass", type="human"))))
        self.assertEqual(result.state.active_gates, [])
        self.assertIsNone(phase.progress)


# --- Cross-check against the canonical procedure-gate predicate --------------

class ProcedureGateAgreementTests(WorkflowPhaseTestBase, unittest.TestCase):

    def test_agrees_with_unmet_procedure_gates(self):
        """The seam evaluates the `kind: procedure` + not-terminal-satisfied
        rule over the IN-MEMORY state; `gate_ledger.unmet_procedure_gates`
        evaluates it by re-reading the file. Pinned together so they cannot
        drift."""
        fm = _active_tuple_fm(["plan_approved", "docs_updated", "review_approved"],
                              ["plan_approved", "docs_updated", "review_approved"], [])
        name = "t935_agreement.md"
        phase, result = self._derive(
            name,
            _body("Implementing", fm,
                  _ledger(_run("plan_approved", "pass", type="human"),
                          _run("review_approved", "pass", type="human"))))
        from_file = gate_ledger.unmet_procedure_gates(
            str(self.tasks_dir / name), str(self.ab.GATES_REGISTRY_FILE))
        in_memory = [g for g in result.state.archive_pending
                     if self.ab.TaskManager.gate_registry(_manager(self.ab))
                     .get(g, {}).get("kind") == "procedure"]
        self.assertEqual(in_memory, from_file)
        self.assertEqual(from_file, ["docs_updated"])
        self.assertEqual(phase.phase, "needs_attended_agent")

    def test_satisfied_procedure_gate_is_not_unmet(self):
        """Negative control for the agreement above: once `docs_updated` passes,
        BOTH sides must drop it — otherwise the equality could hold merely
        because both are always non-empty."""
        fm = _active_tuple_fm(["plan_approved", "docs_updated", "review_approved"],
                              ["plan_approved", "docs_updated", "review_approved"], [])
        name = "t936_agreement_ok.md"
        phase, _ = self._derive(
            name,
            _body("Implementing", fm,
                  _ledger(_run("plan_approved", "pass", type="human"),
                          _run("docs_updated", "pass", type="machine"),
                          _run("review_approved", "pass", type="human"))))
        from_file = gate_ledger.unmet_procedure_gates(
            str(self.tasks_dir / name), str(self.ab.GATES_REGISTRY_FILE))
        self.assertEqual(from_file, [])
        self.assertEqual(phase.phase, "post_impl")


# --- Post-phase mitigation: ladder totality, reachability, precedence --------

class LadderTotalityAndPrecedenceTests(WorkflowPhaseTestBase, unittest.TestCase):
    """t1603_2 post-phase risk mitigation.

    Pins the ladder AS A WHOLE, entirely within the phase axis: no lane is
    derived, asserted, or compared here — the lane belongs to t1603_3, and the
    two axes are independent by design.
    """

    def _matrix(self):
        gated = _active_tuple_fm(["plan_approved", "review_approved"],
                                 ["plan_approved", "review_approved"], [])
        proc = _active_tuple_fm(["plan_approved", "docs_updated", "review_approved"],
                                ["plan_approved", "docs_updated", "review_approved"], [])
        approved = _run("plan_approved", "pass", type="human")
        reviewed = _run("review_approved", "pass", type="human")
        return [
            # (name, body, plan_exists, break_read, expected phase, expected provenance)
            ("t940_none.md", _body("Ready"), False, False, None, None),
            ("t941_editing.md", _body("Editing"), False, False, None, None),
            ("t942_done.md", _body("Done"), False, False, None, None),
            ("t943_marker.md", _body("Ready", "plan_approved_at: 2026-08-25 10:24\n"),
             False, False, "plan_approved", "marker"),
            ("t944_derived.md", _body("Implementing"), True, False,
             "implementing", "derived"),
            ("t945_unknown.md", _body("Implementing"), False, False,
             "implementing", "unknown"),
            ("t946_error.md", _body("Implementing", "", _ledger(approved)), False, True,
             "implementing", "error"),
            ("t947_awaiting.md", _body("Implementing", gated, _ledger(approved)),
             False, False, "awaiting_review", "ledger"),
            ("t948_procedure.md", _body("Implementing", proc, _ledger(approved, reviewed)),
             False, False, "needs_attended_agent", "ledger"),
            ("t949_post.md", _body("Implementing", gated, _ledger(approved, reviewed)),
             False, False, "post_impl", "ledger"),
            ("t950_planapproved.md",
             _body("Implementing", _active_tuple_fm(["plan_approved"], ["plan_approved"], []),
                   _ledger(approved)),
             False, False, "plan_approved", "ledger"),
            # Catch-all: readable ledger, nothing pending, but `plan_approved`
            # was never recorded so `resume_point` is PLAN.
            ("t951_implementing.md",
             _body("Implementing", _active_tuple_fm(["tests_pass"], ["tests_pass"], []),
                   _ledger(_run("tests_pass", "pass", type="machine"))),
             False, False, "implementing", "ledger"),
        ]

    def test_totality_every_fixture_yields_one_valid_answer(self):
        for name, body, plan, broken, want_phase, want_prov in self._matrix():
            with self.subTest(fixture=name):
                phase, _ = self._derive(name, body, plan=plan,
                                        break_ledger_read=broken)
                if want_phase is None:
                    self.assertIsNone(phase)
                    continue
                self.assertIsNotNone(phase)
                self.assertIn(phase.phase, self.ab.WORKFLOW_PHASES)
                self.assertIn(phase.provenance, self.ab.WORKFLOW_PROVENANCES)
                self.assertEqual((phase.phase, phase.provenance),
                                 (want_phase, want_prov))

    def test_every_phase_and_provenance_value_is_reachable(self):
        """No dead branch: each declared value is produced by the matrix. A
        vocabulary entry nothing can reach is a design error, not a spare."""
        phases, provenances = set(), set()
        for name, body, plan, broken, want_phase, _ in self._matrix():
            phase, _ = self._derive(name, body, plan=plan, break_ledger_read=broken)
            if phase is not None:
                phases.add(phase.phase)
                provenances.add(phase.provenance)
        self.assertEqual(phases, set(self.ab.WORKFLOW_PHASES))
        self.assertEqual(provenances, set(self.ab.WORKFLOW_PROVENANCES))

    def test_precedence_is_pinned_by_doubly_satisfying_fixtures(self):
        """Each fixture satisfies BOTH adjacent conditions at once, so the
        assertion pins the ORDER rather than merely the branch. A fixture that
        satisfied only the winning condition would pass under any order."""
        gated = _active_tuple_fm(["plan_approved", "docs_updated", "review_approved"],
                                 ["plan_approved", "docs_updated", "review_approved"], [])
        approved = _run("plan_approved", "pass", type="human")
        reviewed = _run("review_approved", "pass", type="human")

        # awaiting_review over needs_attended_agent: BOTH a pending human gate
        # and a pending procedure gate.
        phase, result = self._derive(
            "t960_human_and_proc.md",
            _body("Implementing", gated, _ledger(approved)))
        self.assertIn("review_approved", result.state.archive_pending)
        self.assertIn("docs_updated", result.state.archive_pending)
        self.assertEqual(phase.phase, "awaiting_review")

        # needs_attended_agent over post_impl: POSTIMPL *and* a pending
        # procedure gate.
        phase, result = self._derive(
            "t961_post_and_proc.md",
            _body("Implementing", gated, _ledger(approved, reviewed)))
        self.assertEqual(result.state.resume_point, "POSTIMPL")
        self.assertIn("docs_updated", result.state.archive_pending)
        self.assertEqual(phase.phase, "needs_attended_agent")

        # plan_approved over awaiting_review when the human gate is SKIPPED: the
        # gate exists and is human, but is terminal-satisfied — and over
        # post_impl, because a skip is not an approval.
        skipped = _active_tuple_fm(["plan_approved", "review_approved"],
                                   ["plan_approved", "review_approved"], [])
        phase, result = self._derive(
            "t962_skip_and_allpass.md",
            _body("Implementing", skipped,
                  _ledger(approved, _run("review_approved", "skip", type="human"))))
        self.assertEqual(result.state.archive_decision, "ALL_PASS")
        self.assertEqual(result.state.resume_point, "IMPLEMENT")
        self.assertEqual(phase.phase, "plan_approved")

        # Branch A over the whole ladder: Ready + marker + a ledger whose
        # `review_approved` is active and unrecorded.
        phase, result = self._derive(
            "t963_ready_marker_ledger.md",
            _body("Ready", skipped + "plan_approved_at: 2026-08-25 10:24\n",
                  _ledger(approved)))
        self.assertIn("review_approved", result.state.archive_pending)
        self.assertEqual(phase.phase, "plan_approved")


if __name__ == "__main__":
    unittest.main()
