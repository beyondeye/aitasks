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


if __name__ == "__main__":
    unittest.main()
