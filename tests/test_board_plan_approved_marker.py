"""Deferred-plan marker (`plan_approved_at`) on board cards and detail (t1603_1).

t1595 shipped the `plan_approved_at` frontmatter marker — "plan approved,
implementation deliberately deferred" — and two read surfaces (`ait ls -v`, the
planning prompt), deferring the board. This module covers the board.

**This file is committed in two commits, deliberately.** The first carries only
`StatusBadgeBaselineTests` below, written and run against *unmodified* code: it
is the inline pre-phase risk mitigation `characterize_status_badge_render` from
`aiplans/p1603/p1603_1_*.md`. Its job is to give the "an unmarked task renders
byte-identically to today" requirement **independent ground truth**, rather than
an expectation copied out of the implementation it is supposed to guard. Every
string in it was read off the running board, not predicted.

Four card shapes matter, because the qualifier's fallback branch sits on the
badge's *suppression* path and each shape reaches it differently:

* **plain** — the ordinary badge, `📋 Ready`.
* **blocked** — the badge is suppressed and replaced by `🚫 blocked`. A `Ready`
  task can legitimately be blocked *and* marked: the risk-mitigation "before"
  stop deliberately keeps the marker (`task-workflow/SKILL.md:553`).
* **parent with an implementing child** — suppressed too, and with no assignee
  `status_parts` ends up **empty**, so compose yields *no status label at all*.
  That absence is the baseline for this shape, and it is why `_status_line`
  returns `None` rather than raising.
* **non-string status** — `lib/task_yaml.py` leaves frontmatter type-honest, so
  `status: [Ready]` reaches compose as a `list` and the f-string renders
  `📋 ['Ready']`. This shape is only safe *by accident*: an f-string is total
  over any type where a `" · ".join()` raises `TypeError` and would crash card
  composition. It is in the baseline precisely because the implementation
  replaces that f-string with a join.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402

# `extra=` is dict.update-ed over the base frontmatter — how an arbitrary key
# like `plan_approved_at` reaches a fixture file.
PLAIN = "t9100_plain.md"          # no marker at all — the control
MARKED = "t9101_marked.md"        # the canonical string form

MARKER_TOPOLOGY = (
    bf.FixtureTask(task_id="9100", col="c0", idx=10, slug="plain"),
    bf.FixtureTask(task_id="9101", col="c0", idx=20, slug="marked",
                   extra={"plan_approved_at": "2026-02-01 14:30"}),
)

# The status label is the join of `status_parts`, and every part it can hold
# begins with one of these. No other `.task-info` label on a card does: effort
# opens with 💪, deps with 🔗, cross-repo with ↗, folded with 📎, an
# implementing child with ⚡, a child count with 👶, a lock with 🔒.
_STATUS_PREFIXES = ("🚫", "🌐", "📋", "👤")


def _manager(ab):
    """Bare TaskManager built from the *fixture-bound* board module.

    `ab` is threaded in rather than imported: under the harness the board is
    loaded under a synthetic module name, so a local `import aitask_board` would
    reach a different module object than the one under test. Copied from
    `tests/test_board_followup_glyph.py:66-89`.
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
    mgr.settings = {}
    return mgr


def _body(status: str = "Ready", extra: str = "") -> str:
    """Frontmatter written as raw text, NOT via a dict.

    `status: [Ready]` has to reach the loader as YAML for the list to survive as
    a list — building the metadata in Python would beg the very question the
    non-string cases exist to ask.
    """
    return f"---\npriority: high\neffort: low\nstatus: {status}\n{extra}---\n\nBody.\n"


class _MarkerTestBase(bf.FixtureBoardTestBase):
    FIXTURE_TASKS = MARKER_TOPOLOGY

    def _run(self, coro):
        return asyncio.run(coro)

    def _task(self, filename: str, body: str):
        return self.ab.Task.from_text(Path(filename), body)

    def _info_texts(self, card) -> list[str]:
        """Every `.task-info` label on a card, in compose order.

        Per-card `CardApp` — no board boot. Idiom from
        `tests/test_board_followup_glyph.py:309-329`.
        """
        from textual.app import App
        from textual.widgets import Label

        found = {}

        class CardApp(App):
            def compose(self):
                yield card

        async def go():
            app = CardApp()
            async with app.run_test(size=(90, 24)) as pilot:
                await pilot.pause()
                found["texts"] = [
                    str(label.render())
                    for label in card.query(".task-info").results(Label)
                ]

        self._run(go())
        return found["texts"]

    @staticmethod
    def _status_line(texts: list[str]) -> str | None:
        """The status-parts label, or `None` when compose yielded none.

        Selected by content rather than by position: a card yields several
        `.task-info` labels and the status one is neither first nor last on
        every surface — on `TrailTaskCard` the trail badges precede it, so
        `.first(Label)` would silently assert against the wrong line.
        """
        for text in texts:
            if text.startswith(_STATUS_PREFIXES):
                return text
        return None

    # -- the four card shapes, built the way production builds them --

    def _plain_card(self, status: str = "Ready", extra: str = ""):
        return self.ab.TaskCard(
            self._task("t9000_plain.md", _body(status, extra)),
            _manager(self.ab), is_child=False, column_id="c0")

    def _blocked_card(self, extra: str = ""):
        """Blocked via a dependency that resolves to nothing."""
        return self.ab.TaskCard(
            self._task("t9001_blocked.md", _body("Ready", "depends: [8888]\n" + extra)),
            _manager(self.ab), is_child=False, column_id="c0")

    def _implementing_child_card(self, extra: str = ""):
        """A parent whose child is `Implementing` — the third suppression path.

        `get_child_tasks_for_parent` (aitask_board.py:1604) matches
        `child_task_datas` **keys** by the `t<parent>_` prefix, so the dict key
        is what makes the child discoverable, not anything on the Task.
        """
        mgr = _manager(self.ab)
        mgr.child_task_datas["t9002_1_kid.md"] = self._task(
            "t9002_1_kid.md", _body("Implementing"))
        return self.ab.TaskCard(
            self._task("t9002_parent.md", _body("Ready", extra)),
            mgr, is_child=False, column_id="c0")

    def _trail_card(self, status: str = "Ready", extra: str = ""):
        task = self._task("t9004_trail.md", _body(status, extra))
        view = self.ab.TrailEntryView(
            {"task": "aitasks#9004", "position": 1,
             "classification": "core", "confidence": "high"},
            task, "", landed=False)
        return self.ab.TrailTaskCard(view, {"ordinal": 1}, None, "trail-w1")


class StatusBadgeBaselineTests(_MarkerTestBase, unittest.TestCase):
    """Characterization of the card status line BEFORE the qualifier exists.

    Every expected string here was read off the running board against
    unmodified code. These are the bytes the implementation must not change for
    an unmarked task — asserted, not assumed.
    """

    def test_fixture_facts(self):
        """Precondition: the fixture actually carries what the suite assumes.

        Without this, reshaping the topology turns the marker assertions
        vacuous instead of failing them.
        """
        plain = (self.tasks_dir / PLAIN).read_text(encoding="utf-8")
        marked = (self.tasks_dir / MARKED).read_text(encoding="utf-8")
        self.assertNotIn("plan_approved_at", plain,
                         f"{PLAIN} is the unmarked control and must carry no marker")
        self.assertIn("plan_approved_at: 2026-02-01 14:30", marked,
                      f"{MARKED} must carry the canonical string-form marker")

    def test_baseline_plain_card(self):
        self.assertEqual(self._status_line(self._info_texts(self._plain_card())),
                         "📋 Ready")

    def test_baseline_blocked_card(self):
        """Blocked suppresses the badge entirely — no 📋 on the line."""
        line = self._status_line(self._info_texts(self._blocked_card()))
        self.assertEqual(line, "🚫 blocked")
        self.assertNotIn("📋", line)

    def test_baseline_implementing_child_card_has_no_status_line(self):
        """`status_parts` ends up empty, so compose yields no status label.

        Asserted as an absence rather than as an empty string: the label is not
        blank, it does not exist.
        """
        texts = self._info_texts(self._implementing_child_card())
        self.assertIsNone(self._status_line(texts))
        self.assertIn("⚡ t9002_1", texts,
                      "the implementing child must actually be discovered, "
                      "otherwise this shape is an ordinary parent and the "
                      "assertion above is vacuous")

    def test_baseline_non_string_status_renders_via_f_string(self):
        """`status: [Ready]` survives as a list and renders `📋 ['Ready']`.

        The f-string is total over any type. Anything that replaces it must
        reproduce this byte-for-byte, and must not raise.
        """
        self.assertEqual(
            self._status_line(self._info_texts(self._plain_card(status="[Ready]"))),
            "📋 ['Ready']")

    def test_baseline_trail_card(self):
        """The second badge call site. Its status label is NOT the first
        `.task-info` — the trail badges are."""
        texts = self._info_texts(self._trail_card())
        self.assertEqual(self._status_line(texts), "📋 Ready")
        self.assertTrue(texts[0].startswith("●"),
                        f"expected trail badges first, got {texts!r} — if this "
                        f"changes, _status_line's content-based selection is "
                        f"the thing keeping the assertion honest")


class PlanApprovedMarkerBoundaryTests(_MarkerTestBase, unittest.TestCase):
    """`_plan_approved_marker` totality over what the loader actually produces.

    Every case is built by **parsing YAML**, not by handing the boundary a
    Python object: the point of the table is that `plan_approved_at: 2026-02-01`
    becomes a `date` and `…14:30:05` a `datetime` before the board ever sees
    them, and constructing those in Python would beg that question.
    """

    @staticmethod
    def _meta(line: str) -> dict:
        from task_yaml import parse_frontmatter
        metadata, _, _ = parse_frontmatter(f"---\n{line}\n---\nbody\n")
        return metadata

    def _marker(self, line: str):
        return self.ab._plan_approved_marker(self._meta(line))

    def test_absent_key_is_no_marker(self):
        self.assertIsNone(self.ab._plan_approved_marker({}))
        self.assertIsNone(self.ab._plan_approved_marker(None))
        self.assertIsNone(self._marker("priority: high"))

    def test_null_and_blank_are_no_marker(self):
        self.assertIsNone(self._marker("plan_approved_at:"))
        self.assertIsNone(self._marker('plan_approved_at: ""'))
        self.assertIsNone(self._marker('plan_approved_at: "   "'))

    def test_canonical_string_is_returned_verbatim(self):
        """The seconds-less form `aitask_update.sh:822` writes stays a `str`."""
        self.assertEqual(self._marker("plan_approved_at: 2026-02-01 14:30"),
                         "2026-02-01 14:30")

    def test_a_datetime_is_formatted_not_repr_ed(self):
        """A hand-edited value carrying seconds parses as a `datetime`."""
        self.assertIsInstance(
            self._meta("plan_approved_at: 2026-02-01 14:30:05")["plan_approved_at"],
            datetime,
            "precondition: the loader must actually yield a datetime here")
        self.assertEqual(self._marker("plan_approved_at: 2026-02-01 14:30:05"),
                         "2026-02-01 14:30")

    def test_a_bare_date_is_formatted_with_a_zero_time(self):
        """A bare `2026-02-01` parses as a `date`, whose strftime fills 00:00.

        This is the row that would raise `NameError` if `date` were not
        imported at module scope — `aitask_board.py` imported only `datetime`
        before t1603_1.
        """
        self.assertEqual(self._marker("plan_approved_at: 2026-02-01"),
                         "2026-02-01 00:00")

    def test_junk_renders_a_literal_and_never_vanishes(self):
        """A value that cannot be read must not look like an absent one.

        Following `_followup_marker`'s rule: silently dropping a bad value makes
        it indistinguishable from a task that never carried a marker, so the
        board would show nothing and the user would never learn the field is
        malformed.
        """
        for line in ("plan_approved_at: [1, 2]",
                     "plan_approved_at: {a: b}",
                     "plan_approved_at: 42",
                     "plan_approved_at: true"):
            with self.subTest(line=line):
                self.assertEqual(self._marker(line), "set (unreadable)")

    def test_it_is_not_normalize_opaque_scalar(self):
        """The deliberate divergence from `board/aitask_merge.py:151`.

        That helper answers `""` for every non-`str` — right for comparison,
        wrong for rendering, because it would hide a datetime-parsed marker that
        `ait ls` (a bash frontmatter parse, blind to YAML types) still shows.
        """
        from aitask_merge import _normalize_opaque_scalar
        raw = self._meta("plan_approved_at: 2026-02-01 14:30:05")["plan_approved_at"]
        self.assertEqual(_normalize_opaque_scalar(raw), "",
                         "precondition: the merge helper drops this value")
        self.assertEqual(self.ab._plan_approved_marker(
            {"plan_approved_at": raw}), "2026-02-01 14:30",
            "the render boundary must NOT drop what the merge helper drops")


class StatusBadgeTextTests(_MarkerTestBase, unittest.TestCase):
    """`_status_badge_text` — the single authority for both badge forms."""

    def test_the_four_combinations(self):
        badge = self.ab._status_badge_text
        self.assertEqual(badge("Ready", "2026-02-01 14:30"), "📋 Ready · Planned")
        self.assertEqual(badge("Ready", None), "📋 Ready")
        self.assertEqual(badge("", "2026-02-01 14:30"), "📋 Planned")
        self.assertEqual(badge("", None), "",
                         "with nothing to say the helper must stay silent, so "
                         "a call site can append its result unconditionally")

    def test_a_non_string_status_does_not_raise_and_matches_the_f_string(self):
        """The regression this helper's `str()` exists for.

        `status` is a raw frontmatter value. A bare `' · '.join((status, …))`
        raises `TypeError` on every one of these, and a raising `compose` takes
        the board down. The expected text is `f"{value}"` — the exact bytes the
        f-string this replaced produced.
        """
        badge = self.ab._status_badge_text
        for value in (["Ready"], 42, True, date(2026, 2, 1)):
            with self.subTest(value=value):
                self.assertEqual(badge(value, None), f"📋 {value}")
                self.assertEqual(badge(value, "2026-02-01 14:30"),
                                 f"📋 {value} · Planned")

    def test_falsey_non_strings_suppress_exactly_like_an_empty_string(self):
        """Truthiness is read off the RAW value, matching the old `if status:`."""
        badge = self.ab._status_badge_text
        for value in (0, [], {}, False, None, ""):
            with self.subTest(value=value):
                self.assertEqual(badge(value, None), "")
                self.assertEqual(badge(value, "2026-02-01 14:30"), "📋 Planned")

    def test_the_badge_glyph_has_exactly_one_home(self):
        """Drift guard: the 📋 glyph lives in one *rendered* literal.

        The qualifier has two call sites and both of them are suppression-aware,
        so a second literal is the natural mistake — and it would drift
        silently, since each site renders fine in isolation.

        Scoped to string literals via `ast`, deliberately, rather than a raw
        `source.count()`: prose about the badge is not a drift risk, and a guard
        that fires on its own explanatory comment is a guard people delete. Only
        a literal that can reach a screen counts, so docstrings are excluded
        too — an f-string's static pieces are `Constant` nodes and *are* caught.
        """
        import ast

        path = REPO_ROOT / ".aitask-scripts" / "board" / "aitask_board.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))

        docstrings = set()
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(node, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef)) and body:
                first = body[0]
                if (isinstance(first, ast.Expr)
                        and isinstance(first.value, ast.Constant)
                        and isinstance(first.value.value, str)):
                    docstrings.add(id(first.value))

        hits = [node for node in ast.walk(tree)
                if isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
                and "📋" in node.value]
        lines = sorted(node.lineno for node in hits)
        self.assertEqual(
            len(hits), 1,
            f"expected the 📋 glyph in exactly one rendered literal (inside "
            f"_status_badge_text), found {len(hits)} at line(s) {lines}. Route "
            f"the new badge through _status_badge_text rather than spelling the "
            f"glyph again; widen this guard only if a surface genuinely cannot "
            f"use the helper.")


class CardQualifierTests(_MarkerTestBase, unittest.TestCase):
    """The qualifier on every card surface, including the suppressed paths.

    The unmarked halves are covered by `StatusBadgeBaselineTests` above — those
    assertions were captured against pre-change code, so together these two
    classes pin "changed exactly where intended, nowhere else".
    """

    MARKER = "plan_approved_at: 2026-02-01 14:30\n"

    def test_a_marked_card_reads_the_qualifier(self):
        line = self._status_line(self._info_texts(self._plain_card(extra=self.MARKER)))
        self.assertEqual(line, "📋 Ready · Planned")

    def test_a_blocked_marked_card_still_surfaces_planned(self):
        """The badge is suppressed, the qualifier is not.

        A `Ready` task can be blocked *and* carry the marker: the
        risk-mitigation "before" stop reverts the task to `Ready` and
        deliberately keeps `plan_approved_at`, because the plan is blocked
        rather than invalidated (task-workflow/SKILL.md:553).
        """
        texts = self._info_texts(self._blocked_card(extra=self.MARKER))
        self.assertEqual(self._status_line(texts), "🚫 blocked | 📋 Planned")

    def test_a_parent_with_an_implementing_child_still_surfaces_planned(self):
        """The third suppression trigger, and it is production-reachable.

        The single-repo decomposition cleanup (`planning.md:281`) reverts a
        parent with `--status Ready --assigned-to ""` and -- unlike its
        cross-repo twin (`cross-repo-child-assignment.md:115`) -- does NOT clear
        `plan_approved_at`. So an approved-and-stopped task that is later
        re-picked and decomposed keeps a marker its single-task plan no longer
        justifies. The board is a read-only mirror: rendering it is what makes
        that staleness visible, rather than the board deciding the field is
        wrong. Baseline for this shape is *no status line at all*.
        """
        texts = self._info_texts(self._implementing_child_card(extra=self.MARKER))
        self.assertEqual(self._status_line(texts), "📋 Planned")
        self.assertIn("⚡ t9002_1", texts,
                      "the implementing child must actually be discovered, "
                      "otherwise this is an ordinary parent and the suppression "
                      "branch was never exercised")

    def test_the_trail_card_carries_the_qualifier_too(self):
        """The second call site. `TrailTaskCard` fully overrides `compose` with
        no `super()`, so a qualifier added to `TaskCard` alone leaves By-Trail
        blind."""
        texts = self._info_texts(self._trail_card(extra=self.MARKER))
        self.assertEqual(self._status_line(texts), "📋 Ready · Planned")

    def test_an_absent_status_still_surfaces_planned_on_both_card_surfaces(self):
        """The empty-status suppression trigger, asserted on BOTH surfaces.

        `TaskCard` reaches it through the `elif plan_marker` branch;
        `TrailTaskCard` through its `status or plan_marker` guard. These are two
        separately-written conditions over the same rule, so a single-surface
        test would let them drift — which they did: By-Trail rendered nothing
        here until the guard was widened from a bare `if status:`.

        A task file with no `status:` key is hand-edited, but so is every other
        input `_plan_approved_marker`'s totality table exists for, and the
        kanban card already committed to showing the qualifier for it.
        """
        no_status = "---\npriority: high\neffort: low\n" + self.MARKER + "---\n\nBody.\n"

        card = self.ab.TaskCard(self._task("t9500_nostatus.md", no_status),
                                _manager(self.ab), is_child=False, column_id="c0")
        self.assertIsNone(card.task_data.metadata.get("status"),
                          "precondition: the fixture must genuinely lack a status")
        self.assertEqual(self._status_line(self._info_texts(card)), "📋 Planned")

        task = self._task("t9501_nostatus.md", no_status)
        view = self.ab.TrailEntryView(
            {"task": "aitasks#9501", "position": 1,
             "classification": "core", "confidence": "high"}, task, "", landed=False)
        trail = self.ab.TrailTaskCard(view, {"ordinal": 1}, None, "trail-w1")
        self.assertEqual(self._status_line(self._info_texts(trail)), "📋 Planned")

    def test_an_unmarked_statusless_trail_card_still_yields_no_status_label(self):
        """Parity for the widened guard: it must add the qualifier case only.

        Widening `if status:` to `if status or plan_marker:` could have started
        emitting an empty label for a card with neither. It does not, because
        the guard is exactly the helper's non-empty condition.
        """
        body = "---\npriority: high\neffort: low\n---\n\nBody.\n"
        task = self._task("t9502_bare.md", body)
        view = self.ab.TrailEntryView(
            {"task": "aitasks#9502", "position": 1,
             "classification": "core", "confidence": "high"}, task, "", landed=False)
        trail = self.ab.TrailTaskCard(view, {"ordinal": 1}, None, "trail-w1")
        texts = self._info_texts(trail)
        self.assertIsNone(self._status_line(texts))
        self.assertNotIn("", [t for t in texts if not t.strip()],
                         f"no blank status label may be emitted, got {texts!r}")

    def test_a_junk_marker_still_surfaces_on_a_card(self):
        line = self._status_line(
            self._info_texts(self._plain_card(extra="plan_approved_at: [1, 2]\n")))
        self.assertEqual(line, "📋 Ready · Planned",
                         "an unreadable marker is still a marker — the card "
                         "qualifier is presence-only, so it must not vanish")


class DetailRowTests(_MarkerTestBase, unittest.TestCase):
    """The read-only `Plan approved:` row in Tracking & provenance.

    App-free: `_build_tracking_fields` reads only its `meta` argument, so it can
    be called unbound and its widget list inspected directly. That makes "the
    row is absent" a *structural* assertion — no such widget — rather than a
    search through screen text that a blank row would also satisfy.
    """

    def _rows(self, meta) -> list[str]:
        fields = self.ab.TaskDetailScreen._build_tracking_fields(None, meta)
        return [field.render().plain for field in fields]

    BASE = {"labels": ["ui"], "created_at": "2026-01-01 00:00"}

    def test_the_row_is_present_and_worded_like_ait_ls(self):
        rows = self._rows({**self.BASE, "plan_approved_at": "2026-02-01 14:30"})
        self.assertIn("Plan approved: 2026-02-01 14:30", rows)

    def test_the_row_is_absent_entirely_when_unmarked(self):
        rows = self._rows(dict(self.BASE))
        self.assertFalse([r for r in rows if "Plan approved" in r],
                         f"expected no Plan approved widget at all, got {rows!r}")
        self.assertTrue(rows, "precondition: other tracking rows still render, "
                              "so an empty list would not prove anything")

    def test_the_collapsible_count_follows_the_row(self):
        """The `Tracking & provenance (<n>)` title counts this list, so the
        header adjusts for free — but only if the row is genuinely added and
        removed rather than rendered blank."""
        marked = self.ab.TaskDetailScreen._build_tracking_fields(
            None, {**self.BASE, "plan_approved_at": "2026-02-01 14:30"})
        unmarked = self.ab.TaskDetailScreen._build_tracking_fields(
            None, dict(self.BASE))
        self.assertEqual(len(marked), len(unmarked) + 1)

    def test_a_bracket_in_the_value_renders_literally(self):
        """`ReadOnlyField` parses Rich markup, so the value must be escaped.

        Unescaped, `2026-02-01 [b]14:30` renders as `2026-02-01 14:30` — the
        `[b]` is silently eaten and the user sees a plausible-looking wrong
        timestamp rather than the malformed value they typed.
        """
        rows = self._rows({**self.BASE,
                           "plan_approved_at": "2026-02-01 [b]14:30"})
        self.assertIn("Plan approved: 2026-02-01 [b]14:30", rows)

    def test_a_junk_marker_shows_the_fallback_rather_than_vanishing(self):
        rows = self._rows({**self.BASE, "plan_approved_at": ["oops"]})
        self.assertIn("Plan approved: set (unreadable)", rows)


if __name__ == "__main__":
    unittest.main()
