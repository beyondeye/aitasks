"""The board reference doc's literals are pinned to the board's own strings (t1603_5).

`website/content/docs/tuis/board/reference.md` documents the In-Flight lane
titles, the workflow-phase chip vocabulary, the card's deferred-plan badge and
the six `Gates` rows. Website docs pages have no accuracy guard of their own, so
a rename in `aitask_board.py` silently rots the published page. This module makes
that a test failure instead.

**The source is the authority; the doc is the assertion target.** Nothing here
hardcodes a documented string — every expected value is imported from, or
rendered by, the board module. A copy in this file would be a third place to
drift.

**The documentation contract came first, and this guard asserts exactly what the
documentation presents.** That distinction is load-bearing, because the two do
not coincide by default:

* `phase_chip_text("plan_approved", "marker", None)` renders
  `plan approved (from marker)`, which is a *different* string from the bare
  `plan approved` in the phase-label table. Both are documented, so both are
  asserted — but only because the doc genuinely presents both.
* `_status_badge_text` interpolates a status, and the doc deliberately shows the
  concrete `Ready` case rather than a `<status>` token. It is therefore asserted
  **concretely**, not normalized. Normalizing it would demand a form the page
  never presents, i.e. the guard would force accidental prose.
* The fraction (`· 2/3`, `Gates (2/3)`) appears in the doc only as
  `<satisfied>/<enforced>` prose. A placeholder is not a render, so it is
  **deliberately not asserted**.

Three literal classes, because one "output appears in the doc" assertion is
wrong for the third:

a. **plain constants** — asserted verbatim;
b. **zero-interpolation renders** — the real function is called and its return
   value asserted verbatim, with no normalization;
c. **templated renders** — the six `Gates` rows interpolate a gate name
   (`✓ risk_evaluated — passed`) while the doc writes `✓ <gate> — passed`.
   Asserting the raw output would always fail, and asserting a substring
   (`— passed`) would let the glyph, the em-dash or the wording drift unnoticed
   — the exact hole this guard exists to close. So the rows are rendered from
   real fixtures through the production builder and then normalized **on the
   gate names those fixtures themselves supplied**, never on a pattern guessed
   over the output: a substitution keyed on the input cannot silently erase a
   genuine change.

Fixtures are real task files parsed by the production parser and rendered by
`TaskDetailScreen._build_gate_fields`, following
`tests/test_board_detail_gates_section.py` — a hand-built row would only pin this
file against itself.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_board_reference_doc_literals.py -v
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

#: Absolute, resolved at import time. The fixture base chdirs the process into a
#: temp tree, so a relative path here would read nothing (or the wrong thing).
DOC = REPO_ROOT / "website" / "content" / "docs" / "tuis" / "board" / "reference.md"
DOC_LABEL = DOC.relative_to(REPO_ROOT).as_posix()

#: The placeholder the documentation uses where a gate name is interpolated.
GATE_TOKEN = "<gate>"

#: See `test_board_detail_gates_section.PINNED_DIGEST` — the fixture tree has no
#: git repo, so a computed digest answers `None` ("freshness is unverifiable")
#: and staleness is unreachable through the real digest. Pre-seeding the memo
#: with a `str` is the same channel production fills from
#: `TaskManager.code_digest_for_refresh`, not a patch.
PINNED_DIGEST = "feedfacefeed"

#: What the fixture's *signature* is stamped with. It MUST differ from
#: `PINNED_DIGEST`: staleness is exactly "the witness names a digest other than
#: the current one", so stamping both the same yields a clean `pass` and the
#: `⚠` row never renders — the fixture would silently test nothing.
WITNESS_DIGEST = "deadbeefdead"


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


def _manager(ab, digest=None):
    """Bare `TaskManager` from the fixture-bound board module.

    `ab` is threaded in rather than imported: under the harness the board loads
    under a synthetic module name, so a local `import aitask_board` would reach a
    different module object than the one under test.
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


class DocLiteralTestBase(bf.FixtureBoardTestBase):
    """Shared doc text plus the assertion that names what drifted."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Read through the absolute path — the class-level fixture tree is now
        # the process cwd.
        cls.doc = DOC.read_text(encoding="utf-8")

    def assertDocumented(self, literal: str, what: str):
        """`literal` must appear in the reference page, verbatim.

        The message names the drifted value AND the file that no longer carries
        it: a bare `assertIn` failure on a long page says only "not found", which
        is the least useful half of the answer.
        """
        self.assertIn(
            literal, self.doc,
            f"{what} is no longer documented: the board renders {literal!r}, "
            f"which does not appear in {DOC_LABEL}. Either the board string "
            f"changed and the page must follow, or the page was reworded past "
            f"the literal.")


# --- class (a): plain constants ----------------------------------------------


class PlainConstantTests(DocLiteralTestBase, unittest.TestCase):
    """Values that are literals in the source and literals on the page."""

    def test_every_inflight_lane_title_is_documented(self):
        titles = self.ab.InFlightColumn.TITLES
        self.assertEqual(len(titles), 4, "lane vocabulary changed size")
        for lane, title in titles.items():
            self.assertDocumented(title, f"In-Flight lane title for {lane!r}")

    def test_every_phase_label_is_documented(self):
        labels = self.ab.PHASE_LABELS
        self.assertEqual(set(labels), set(self.ab.WORKFLOW_PHASES),
                         "PHASE_LABELS and WORKFLOW_PHASES disagree")
        for phase, label in labels.items():
            self.assertDocumented(label, f"phase label for {phase!r}")

    def test_every_phase_name_is_documented(self):
        """The page names the phases themselves, not only their labels."""
        for phase in self.ab.WORKFLOW_PHASES:
            self.assertDocumented(phase, f"phase name {phase!r}")


# --- class (b): zero-interpolation renders -----------------------------------


class ZeroInterpolationRenderTests(DocLiteralTestBase, unittest.TestCase):
    """Real renders that interpolate nothing, asserted verbatim.

    Deliberately NOT normalized. These are the forms the documentation presents
    concretely, and normalizing them is exactly what would make this guard fail
    by construction and force accidental prose onto the page.
    """

    def test_marker_provenance_qualifier(self):
        got = self.ab.phase_chip_text("plan_approved", "marker", None)
        self.assertDocumented(got, "the marker-provenance chip")

    def test_no_ledger_degraded_forms(self):
        for provenance in ("unknown", "derived"):
            got = self.ab.phase_chip_text("implementing", provenance, None)
            self.assertDocumented(got, f"the no-ledger chip ({provenance})")

    def test_unreadable_ledger_form(self):
        """The no-`error`-argument form only.

        With an error argument the render appends the message text, which the
        page presents as prose rather than a literal — so the suffix is out of
        this guard's scope by design.
        """
        got = self.ab.phase_chip_text("implementing", "error", None)
        self.assertDocumented(got, "the unreadable-ledger chip")

    def test_deferred_plan_card_badge(self):
        """Asserted CONCRETELY, with the status the page actually shows.

        `_status_badge_text` interpolates the status, but the documented example
        is `Ready` — the only status that can carry the qualifier in practice,
        since the marker branch requires it. Normalizing to `<status>` would
        assert a string the page never presents.
        """
        got = self.ab._status_badge_text("Ready", "2026-08-25 10:24")
        self.assertDocumented(got, "the deferred-plan card badge")

    def test_unmarked_badge_is_the_same_renderer(self):
        """A negative control on the pair: without a marker there is no
        qualifier, so a guard that passed on both would not be reading the
        qualifier at all."""
        plain = self.ab._status_badge_text("Ready", None)
        marked = self.ab._status_badge_text("Ready", "2026-08-25 10:24")
        self.assertNotEqual(plain, marked)
        self.assertTrue(marked.startswith(plain))


# --- class (c): templated renders --------------------------------------------


class GateRowTests(DocLiteralTestBase, unittest.TestCase):
    """The six `Gates` rows, rendered by production and normalized on input.

    Every row is produced by `TaskDetailScreen._build_gate_fields` from a real
    task file, over gates the shipped `gates.yaml` actually defines, so the
    glyph, the separator and the wording all come from the source.
    """

    #: `(fixture name, frontmatter gates, ledger runs, needs a stale witness)`.
    #: Between them these reach every branch of the row table.
    def _rows_for(self, name, gates, runs, *, witness=None):
        """Normalized gate rows for one fixture.

        Normalization replaces **the gate names this fixture supplied** with the
        documentation's placeholder. The substitution key is the input, never a
        pattern matched against the output, so it cannot absorb a genuine change
        to the row form.
        """
        ab = self.ab
        digest = None
        if witness is not None:
            task_num, gate = witness
            wpath = (self.tree / ".aitask-gates" / f"t{task_num}"
                     / f"{gate}.signed")
            wpath.parent.mkdir(parents=True, exist_ok=True)
            wpath.write_text(f"code_digest={WITNESS_DIGEST}\n", encoding="utf-8")
            self.addCleanup(wpath.unlink, missing_ok=True)
            digest = PINNED_DIGEST

        body = _body("Implementing",
                     bf.active_tuple_fm(list(gates), list(gates), []),
                     _ledger(*runs) if runs else "")
        path = self.tasks_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        self.addCleanup(path.unlink, missing_ok=True)

        screen = ab.TaskDetailScreen(ab.Task.from_text(path, body),
                                     _manager(ab, digest))
        rows, _ = screen._build_gate_fields()
        out = []
        for row in (str(r.render()) for r in rows):
            if row[:1] not in {"✓", "⚠", "⊘", "✗", "◈", "·"}:
                continue          # the phase row, not a gate row
            for gate in gates:
                row = row.replace(gate, GATE_TOKEN)
            out.append(row)
        return out

    def _all_normalized_rows(self):
        forms = set()
        forms |= set(self._rows_for(
            "t9610_pending.md", ["risk_evaluated"], []))
        forms |= set(self._rows_for(
            "t9611_pass.md", ["risk_evaluated"],
            [_run("risk_evaluated", "pass", type="machine")]))
        forms |= set(self._rows_for(
            "t9612_skip.md", ["risk_evaluated"],
            [_run("risk_evaluated", "skip", type="machine")]))
        forms |= set(self._rows_for(
            "t9613_fail.md", ["tests_pass"],
            [_run("tests_pass", "fail", type="machine")]))
        forms |= set(self._rows_for(
            "t9614_proc.md", ["docs_updated"],
            [_run("plan_approved", "pass", type="human")]))
        forms |= set(self._rows_for(
            "t9615_stale.md", ["plan_approved", "review_approved"],
            [_run("plan_approved", "pass", type="human"),
             _run("review_approved", "pass", type="human")],
            witness=("9615", "review_approved")))
        return forms

    def test_every_gate_row_form_is_documented(self):
        forms = self._all_normalized_rows()
        self.assertEqual(
            len(forms), 6,
            f"expected the six documented row forms, rendered {len(forms)}: "
            f"{sorted(forms)}")
        for form in sorted(forms):
            self.assertDocumented(form, "a Gates row form")

    def test_normalization_did_not_swallow_the_gate_name(self):
        """A control on the normalizer itself.

        Too aggressive a substitution would erase the drift this guard exists to
        catch, and the symptom would be silent: every row would still be found.
        Each form must carry exactly one placeholder and no residual gate name.
        """
        for form in sorted(self._all_normalized_rows()):
            self.assertEqual(form.count(GATE_TOKEN), 1,
                             f"row form has no single placeholder: {form!r}")
            for gate in ("risk_evaluated", "tests_pass", "docs_updated",
                         "plan_approved", "review_approved"):
                self.assertNotIn(gate, form,
                                 f"row form still names a gate: {form!r}")


if __name__ == "__main__":
    unittest.main()
