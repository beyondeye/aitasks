"""`followup_kind` in the board's task detail screen (t1468_8).

t1468_3 put a provenance glyph on every board *card*. `TaskDetailScreen` showed
nothing, so the glyph had no legend and a mis-classified follow-up — there are
~95 of them from the t1468_6 heuristic backfill — could be seen on the board but
only corrected from the CLI. This module covers the row that closes that loop.

Five things here are load-bearing and each fails silently:

* **Clearing is key REMOVAL, not an empty value.** The field persists through
  `aitask_update.sh --followup-kind ""`, whose emit skips the line entirely.
  Writing `""` (or `"none"`) as a *value* would round-trip back through
  `normalize_followup_kind` as an unrecognised kind and paint `·` on every task
  the user had just cleared. `FollowupKindLiveRoundTripTests` drives the real
  script and probes for key ABSENCE, which a value probe cannot distinguish.
* **The screen must not go dirty on open.** The field is deliberately outside
  `_original_values`; a seeded default there would light up Save the moment any
  ordinary task was opened, because the field is legitimately absent on most.
* **An immediate write on a screen with deferred writes.** Success calls
  `_reload_detail_screen`, which REPLACES the screen and drops any pending
  CycleField edit. `FollowupKindDirtyGuardTests` pins the guard in BOTH
  directions and carries its own negative control.
* **Colour must beat the widget CSS.** `.meta-ro` sets `color: $text-muted` on
  the whole row. If that wins over the glyph's literal Rich style, the kind is
  distinguishable by shape alone and half the acceptance criterion is lost —
  while everything still looks fine. Only a composited strip is evidence.
* **An unrecognised value must survive the picker.** It matches no row, so the
  clear row would take default focus and one reflexive Enter would delete the
  very value the user opened the dialog to diagnose.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402

# One task per interesting case. `extra=` is dict.update-ed over the base
# frontmatter, which is how an arbitrary key like `followup_kind` reaches a
# fixture file. Kinds are chosen so no two fixtures share a glyph.
PLAIN = "t9100_plain.md"      # no followup_kind — the control
RISK = "t9101_risk.md"        # risk_mitigation  -> yellow ▲
DOCS = "t9102_docs.md"        # docs_gap         -> #808080 ▤
TYPO = "t9103_typo.md"        # unrecognised     -> uncoloured ·

DETAIL_TOPOLOGY = (
    bf.FixtureTask(task_id="9100", col="c0", idx=10, slug="plain"),
    bf.FixtureTask(task_id="9101", col="c0", idx=20, slug="risk",
                   extra={"followup_kind": "risk_mitigation"}),
    bf.FixtureTask(task_id="9102", col="c1", idx=10, slug="docs",
                   extra={"followup_kind": "docs_gap"}),
    bf.FixtureTask(task_id="9103", col="c1", idx=20, slug="typo",
                   extra={"followup_kind": "risk_mitgation"}),  # sic: typo
)


class _DetailFollowupBase(bf.FixtureBoardTestBase):
    FIXTURE_TASKS = DETAIL_TOPOLOGY

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KanbanApp = cls.ab.KanbanApp
        cls.TaskDetailScreen = cls.ab.TaskDetailScreen
        cls.FollowupKindField = cls.ab.FollowupKindField
        cls.FollowupKindPickerScreen = cls.ab.FollowupKindPickerScreen
        cls.FollowupKindPickerItem = cls.ab.FollowupKindPickerItem
        cls.FOLLOWUP_KINDS = cls.ab.FOLLOWUP_KINDS

    def _run(self, coro):
        return asyncio.run(coro)

    @staticmethod
    async def _settle(pilot, times=5):
        """Drain deferred work AND scheduled animations.

        `tests/test_board_bytrail_view.py:134-144`: focus scroll is both
        deferred and animated, so an assertion that runs too early observes the
        pre-scroll frame.
        """
        for _ in range(times):
            await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

    def _task(self, app, filename):
        task = app.manager.task_datas.get(filename)
        self.assertIsNotNone(task, f"fixture must load {filename}")
        return task

    def _field(self, app):
        """The mounted follow-up row, or None."""
        found = app.screen.query("#ff_followup_kind")
        return found.first() if found else None

    @staticmethod
    def _painted(app) -> dict:
        """`{text: resolved-truecolor-hex}` for every styled run on the screen.

        The only way to prove a colour reached the terminal: `render().plain`
        drops style entirely and `render().spans` reports a colour that may
        never have resolved. Lifted from
        `tests/test_board_followup_glyph.py:135-158`.
        """
        painted = {}
        for strip in app.screen._compositor.render_strips(app.screen.size):
            for seg in strip:
                text = seg.text.strip()
                if not text or seg.style is None or seg.style.color is None:
                    continue
                painted.setdefault(text, seg.style.color.get_truecolor().hex.lower())
        return painted

    @staticmethod
    def _screen_text(app) -> str:
        return "\n".join(strip.text for strip
                         in app.screen._compositor.render_strips(app.screen.size))


# --- 1. the field's own rendering, per value --------------------------------


class FollowupKindFieldRenderTests(_DetailFollowupBase, unittest.TestCase):
    """App-free: `render()` reads only `self.kind` / `read_only` / `blocked` and
    pure module functions, so no board boot is needed — which keeps the whole
    value matrix cheap enough to actually enumerate."""

    def _render(self, kind, *, read_only=False, blocked=False) -> str:
        field = self.FollowupKindField(kind, None, MagicMock(),
                                       read_only=read_only)
        field.blocked = blocked          # set directly: no mount, no refresh()
        return field.render().plain

    def test_fixture_facts(self):
        """Preconditions the rest of this class reads off the vocabulary."""
        self.assertEqual(self.FOLLOWUP_KINDS["risk_mitigation"][0], "▲")
        self.assertEqual(self.FOLLOWUP_KINDS["risk_mitigation"][2],
                         "risk mitigation")
        self.assertEqual(self.ab.UNKNOWN_GLYPH, "·")

    def test_every_kind_renders_its_glyph_and_human_label(self):
        """Parametrised over the vocabulary itself — this is the drift guard.
        It fails the moment a kind is added to `followup_kinds.py` that the
        detail row cannot render."""
        for kind, (glyph, _colour, label) in self.FOLLOWUP_KINDS.items():
            with self.subTest(kind=kind):
                plain = self._render(kind)
                self.assertIn(glyph, plain, f"{kind}'s glyph is missing")
                self.assertIn(label, plain, f"{kind}'s human label is missing")
                self.assertIn("Follow-up:", plain)

    def test_unset_renders_none_and_the_set_hint(self):
        plain = self._render(None)
        self.assertIn("(none)", plain)
        self.assertIn("(enter to set)", plain)
        self.assertNotIn("(enter to change)", plain)

    def test_a_set_kind_renders_the_change_hint(self):
        plain = self._render("risk_mitigation")
        self.assertIn("(enter to change)", plain)
        self.assertNotIn("(enter to set)", plain)

    def test_read_only_renders_no_hint_at_all(self):
        """A read-only screen offers no way to edit, so an affordance there
        would be a lie."""
        plain = self._render("risk_mitigation", read_only=True)
        self.assertIn("▲", plain)
        self.assertNotIn("enter to", plain)
        self.assertNotIn("pending edits", plain)

    def test_blocked_replaces_the_hint_with_the_remedy(self):
        """The guard must be legible in the row itself, not only in a
        notification the user may have dismissed."""
        plain = self._render("risk_mitigation", blocked=True)
        self.assertIn("(save or revert pending edits first)", plain)
        self.assertNotIn("(enter to change)", plain)
        self.assertNotIn("(enter to set)", plain)

    def test_read_only_wins_over_blocked(self):
        """Both suppress the edit affordance; neither hint may appear."""
        plain = self._render("risk_mitigation", read_only=True, blocked=True)
        self.assertNotIn("enter to", plain)
        self.assertNotIn("pending edits", plain)

    def test_an_unrecognised_kind_shows_the_fallback_glyph_and_the_raw_value(self):
        """`label_for` answers "" for an unknown kind, so the raw value is what
        is shown — a typo must be diagnosable from the screen that can fix it,
        and the glyph degrades exactly as it does on the card."""
        plain = self._render("risk_mitgation")
        self.assertIn("·", plain)
        self.assertIn("risk_mitgation", plain)
        self.assertIn("(enter to change)", plain,
                      "an unrecognised value is still a value — the row must "
                      "offer to change it, not to 'set' it")

    def test_totality_over_the_junk_frontmatter_lets_through(self):
        """`lib/task_yaml.py` leaves frontmatter values type-honest, so a
        hand-edited field arrives as any Python type. Every one of these is
        'not a follow-up' — the same three-way rule the cards use."""
        for raw in (None, "", "   ", [], {}, 0, True, 42):
            with self.subTest(raw=raw):
                plain = self._render(raw)
                self.assertIn("(none)", plain)
                self.assertIn("(enter to set)", plain)


# --- 2. wiring into the detail screen ---------------------------------------


class FollowupKindDetailScreenTests(_DetailFollowupBase, unittest.TestCase):

    def test_the_row_is_the_last_child_of_meta_editable(self):
        """Row 5 of the primary block, after Type. Pins BOTH the placement
        decision and the requirement that follow-up kind stay visually distinct
        from `issue_type` rather than merged into it."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                app.push_screen(self.TaskDetailScreen(
                    self._task(app, RISK), app.manager))
                await self._settle(pilot)

                block = app.screen.query_one("#meta_editable")
                kids = list(block.children)
                self.assertIsInstance(kids[-1], self.FollowupKindField,
                                      "the follow-up row must be last")
                self.assertEqual(kids[-2].id, "cf_issue_type",
                                 "and must sit immediately after Type")
                self.assertEqual(len(kids), 5)
        self._run(go())

    def test_save_stays_disabled_on_open_with_and_without_a_kind(self):
        """THE dirty-check regression. The field is deliberately absent from
        `_original_values`; a seeded default there would light up Save the
        moment any ordinary task was opened."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                for filename in (RISK, PLAIN, TYPO):
                    app.push_screen(self.TaskDetailScreen(
                        self._task(app, filename), app.manager))
                    await self._settle(pilot)
                    btn = app.screen.query_one("#btn_save")
                    self.assertTrue(
                        btn.disabled,
                        f"{filename}: opening a task must not mark it dirty")
                    self.assertFalse(app.screen.has_unsaved_edits())
                    app.pop_screen()
                    await self._settle(pilot)
        self._run(go())

    def test_read_only_shows_a_plain_line_and_enter_opens_nothing(self):
        """'No editable control' operationally: the row renders, but Enter
        cannot reach the picker."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                app.push_screen(self.TaskDetailScreen(
                    self._task(app, RISK), app.manager, read_only=True))
                await self._settle(pilot)

                field = self._field(app)
                self.assertIsNotNone(field, "a set kind must still be shown")
                self.assertTrue(field.read_only)
                self.assertNotIn("enter to", field.render().plain)

                depth = len(app.screen_stack)
                app.set_focus(field)
                await pilot.press("enter")
                await self._settle(pilot)
                self.assertEqual(len(app.screen_stack), depth,
                                 "read-only Enter must push no picker")
        self._run(go())

    def test_read_only_omits_the_row_entirely_when_no_kind_is_set(self):
        """A read-only screen offers no way to set one, so an always-shown
        '(none)' would be pure noise. Mirrors AnchorField's own rule."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                app.push_screen(self.TaskDetailScreen(
                    self._task(app, PLAIN), app.manager, read_only=True))
                await self._settle(pilot)
                self.assertIsNone(self._field(app))
        self._run(go())

    def test_the_editable_row_is_shown_even_when_unset(self):
        """The set-affordance must be discoverable — that is the whole backfill
        review loop."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                app.push_screen(self.TaskDetailScreen(
                    self._task(app, PLAIN), app.manager))
                await self._settle(pilot)
                field = self._field(app)
                self.assertIsNotNone(field)
                self.assertFalse(field.read_only)
                self.assertIn("(enter to set)", field.render().plain)
        self._run(go())


# --- 3. the dirty guard -----------------------------------------------------


class FollowupKindDirtyGuardTests(_DetailFollowupBase, unittest.TestCase):
    """An immediate write on a screen whose other four fields are deferred.

    `_reload_detail_screen` replaces the screen with a fresh instance that
    re-seeds `_original_values` from disk, so firing the picker while a
    CycleField edit is pending would discard that edit with no warning.
    """

    async def _open(self, app, pilot, filename=RISK):
        app.push_screen(self.TaskDetailScreen(
            self._task(app, filename), app.manager))
        await self._settle(pilot)
        return self._field(app)

    @staticmethod
    async def _dirty(app, pilot):
        """Make a real pending edit through the production path."""
        app.screen.query_one("#cf_priority").cycle_next()
        await pilot.pause()

    def test_a_pending_cyclefield_edit_blocks_the_row(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                field = await self._open(app, pilot)
                self.assertFalse(field.blocked, "clean on open")

                await self._dirty(app, pilot)

                self.assertFalse(app.screen.query_one("#btn_save").disabled)
                self.assertTrue(app.screen.has_unsaved_edits())
                self.assertTrue(field.blocked,
                                "a pending edit must block the immediate write")
                self.assertIn("(save or revert pending edits first)",
                              field.render().plain)
        self._run(go())

    def test_enter_while_blocked_opens_nothing_and_warns(self):
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                field = await self._open(app, pilot)
                await self._dirty(app, pilot)

                app.notify = MagicMock()
                depth = len(app.screen_stack)
                app.set_focus(field)
                await pilot.press("enter")
                await self._settle(pilot)

                self.assertEqual(len(app.screen_stack), depth,
                                 "the picker must NOT open while dirty")
                self.assertTrue(app.notify.called, "the user must be told why")
                self.assertEqual(app.notify.call_args.kwargs.get("severity"),
                                 "warning")
                self.assertIn("Save or revert", app.notify.call_args.args[0])
        self._run(go())

    def test_saving_unblocks_the_row_again(self):
        """The other edge of the toggle. A guard that latched on would pass the
        test above and still be broken."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                field = await self._open(app, pilot)
                await self._dirty(app, pilot)
                self.assertTrue(field.blocked)

                app.screen.save_changes()
                await self._settle(pilot)

                self.assertFalse(app.screen.has_unsaved_edits())
                self.assertFalse(field.blocked,
                                 "saving must release the guard")
                self.assertIn("(enter to change)", field.render().plain)

                depth = len(app.screen_stack)
                app.set_focus(field)
                await pilot.press("enter")
                await self._settle(pilot)
                self.assertEqual(len(app.screen_stack), depth + 1,
                                 "and the picker must open again")
        self._run(go())

    def test_update_save_button_tolerates_a_screen_with_no_row(self):
        """`query`, not `query_one`: a read-only screen whose task carries no
        kind mounts no field at all, and the hook must not raise there."""
        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                app.push_screen(self.TaskDetailScreen(
                    self._task(app, PLAIN), app.manager, read_only=True))
                await self._settle(pilot)
                self.assertIsNone(self._field(app))
                app.screen._update_save_button()      # must not raise
        self._run(go())

    def test_dirty_guard_assertion_is_not_vacuous(self):
        """[dirty_guard_negative_control] — the plan's post-phase mitigation.

        The guard is the answer to a silent data-loss defect, so its test must
        be falsifiable. Neuter `set_blocked` and require the blocked-Enter
        assertion to FAIL — i.e. the picker opens and the pending edit would be
        lost. A control that stays green means the assertion never depended on
        the guard at all.
        """
        opened = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                field = await self._open(app, pilot)
                with patch.object(self.FollowupKindField, "set_blocked",
                                  lambda self, blocked: None):
                    await self._dirty(app, pilot)
                    opened["blocked"] = field.blocked
                    depth = len(app.screen_stack)
                    app.set_focus(field)
                    await pilot.press("enter")
                    await self._settle(pilot)
                    opened["depth_delta"] = len(app.screen_stack) - depth

        self._run(go())
        self.assertFalse(opened["blocked"],
                         "control setup: the neutered hook must leave the flag "
                         "unset, or the mutation did not take")
        self.assertEqual(
            opened["depth_delta"], 1,
            "NEGATIVE CONTROL FAILED: with `set_blocked` neutered the picker "
            "STILL did not open, so `test_enter_while_blocked_opens_nothing_"
            "and_warns` is not actually testing the guard")


# --- 4. the picker ----------------------------------------------------------


class FollowupKindPickerTests(_DetailFollowupBase, unittest.TestCase):

    def _open(self, current_kind: str, keys=()):
        """Push the picker over a bare board, optionally press keys, and report
        the focused widget plus the dismiss result."""
        out = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                app.push_screen(
                    self.FollowupKindPickerScreen("t9101", current_kind),
                    lambda result: out.__setitem__("result", result))
                await self._settle(pilot)
                out["focused"] = app.focused
                out["rows"] = list(app.screen.query(self.FollowupKindPickerItem))
                out["title"] = app.screen.query_one(
                    "#dep_picker_title").render().plain
                for key in keys:
                    await pilot.press(key)
                    await self._settle(pilot)

        self._run(go())
        return out

    def test_rows_are_the_clear_row_then_the_canonical_vocabulary(self):
        """Drift guard: adding a kind to `followup_kinds.py` without it
        appearing here fails, and the order is the module's declaration order."""
        out = self._open("")
        kinds = [row.kind for row in out["rows"]]
        self.assertEqual(kinds, [""] + list(self.FOLLOWUP_KINDS))
        self.assertEqual(len(kinds), len(self.FOLLOWUP_KINDS) + 1)

    def test_the_current_kind_takes_focus(self):
        out = self._open("docs_gap")
        self.assertIsInstance(out["focused"], self.FollowupKindPickerItem)
        self.assertEqual(out["focused"].kind, "docs_gap")
        self.assertTrue(out["focused"].current)

    def test_an_unset_task_focuses_the_clear_row_which_is_a_no_op(self):
        """Enter there dismisses with "", which `_edit`'s
        `new_kind == self.kind` guard drops without a write."""
        out = self._open("")
        self.assertIsInstance(out["focused"], self.FollowupKindPickerItem)
        self.assertEqual(out["focused"].kind, "")
        self.assertTrue(out["focused"].current)

    def test_enter_on_a_kind_row_dismisses_with_that_kind(self):
        out = self._open("", keys=("down", "down", "enter"))
        self.assertEqual(out["result"], "risk_mitigation")

    def test_enter_on_the_clear_row_dismisses_with_empty_string(self):
        # `manual_verification` is the FIRST vocabulary row, so the clear row
        # directly above it is exactly one `up` away from the focused current.
        out = self._open("manual_verification", keys=("up", "enter"))
        self.assertEqual(out["result"], "",
                         "the clear row must dismiss with '' — the value that "
                         "makes aitask_update.sh REMOVE the key")

    def test_escape_dismisses_with_none_not_empty_string(self):
        """`""` and `None` are not interchangeable: a cancel that returned `""`
        would clear the field on every Escape."""
        out = self._open("risk_mitigation", keys=("escape",))
        self.assertIsNone(out["result"])

    def test_the_cancel_button_dismisses_with_none(self):
        out = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                app.push_screen(
                    self.FollowupKindPickerScreen("t9101", "risk_mitigation"),
                    lambda result: out.__setitem__("result", result))
                await self._settle(pilot)
                app.screen.query_one("#btn_dep_cancel").press()
                await self._settle(pilot)

        self._run(go())
        self.assertIsNone(out["result"])

    # -- the unrecognised-value case (destructive-default guard) --

    def test_an_unrecognised_value_focuses_cancel_not_the_clear_row(self):
        out = self._open("risk_mitgation")
        self.assertEqual(getattr(out["focused"], "id", None), "btn_dep_cancel",
                         "an unrecognised kind matches no row, so the clear row "
                         "would otherwise take default focus and one Enter "
                         "would delete the value being diagnosed")

    def test_an_unrecognised_value_is_named_in_the_title(self):
        out = self._open("risk_mitgation")
        self.assertIn("risk_mitgation", out["title"])
        self.assertIn("not a recognised kind", out["title"])

    def test_a_reflexive_enter_on_an_unrecognised_value_changes_nothing(self):
        """The interaction, not just the focus target: opening the picker on a
        bad value and pressing Enter must dismiss with `None`, which `_edit`
        drops without calling `_apply`."""
        out = self._open("risk_mitgation", keys=("enter",))
        self.assertIsNone(out["result"],
                          "Enter on the safe default must cancel, never clear")

    def test_a_recognised_value_leaves_the_title_clean(self):
        """Negative control for the diagnostic — it must not fire for a value
        that is perfectly fine."""
        out = self._open("risk_mitigation")
        self.assertNotIn("not a recognised kind", out["title"])
        self.assertIn("t9101", out["title"])

    def test_a_markup_bearing_value_renders_verbatim_and_does_not_raise(self):
        """`current_kind` is hand-editable frontmatter landing in a `Label`,
        which parses Rich markup by default — `[bold]x` would be swallowed and
        an unbalanced tag would raise. The title is a `Text`, so it cannot."""
        out = self._open("[bold]x")
        self.assertIn("[bold]x", out["title"])
        out = self._open("[/]")           # unbalanced: would raise if parsed
        self.assertIn("[/]", out["title"])

    def test_the_current_marker_appears_on_exactly_one_row(self):
        out = self._open("docs_gap")
        marked = [r for r in out["rows"] if r.current]
        self.assertEqual(len(marked), 1)
        self.assertIn("✓", marked[0].render().plain)

    def test_no_row_is_marked_current_for_an_unrecognised_value(self):
        out = self._open("risk_mitgation")
        self.assertEqual([r for r in out["rows"] if r.current], [])

    def test_each_row_shows_glyph_label_and_raw_key(self):
        out = self._open("")
        by_kind = {r.kind: r.render().plain for r in out["rows"]}
        for kind, (glyph, _c, label) in self.FOLLOWUP_KINDS.items():
            with self.subTest(kind=kind):
                self.assertIn(glyph, by_kind[kind])
                self.assertIn(label, by_kind[kind])
                self.assertIn(kind, by_kind[kind])
        self.assertIn("not a follow-up", by_kind[""])


# --- 5. colour, against the widget's own CSS --------------------------------


class FollowupKindColourTests(_DetailFollowupBase, unittest.TestCase):
    """`.meta-ro` sets `color: $text-muted` on the whole row. The glyph's
    literal Rich style must beat it, or the kind is distinguishable by shape
    alone — which looks fine and silently loses half the acceptance criterion.

    The probe app reproduces exactly that one CSS rule so the competition is
    real but isolated; `test_fixture_facts` is the drift guard that the board's
    own CSS still sets it.
    """

    #: Literal HEXES, never read from `FOLLOWUP_KINDS` — a probe that took its
    #: colour from the module would move with the mutation in the negative
    #: control and the control would pass while proving nothing.
    #:
    #: Hexes rather than names on purpose: a NAME does not composite to one
    #: value (see `_followup_colour_hex`), so a named probe would itself be
    #: path-dependent and could not be compared across the card and the row.
    #: These are Textual's resolutions of `yellow` / `#808080` / `green`.
    PROBES = {"probe-yellow": "#ffff00",
              "probe-grey": "#808080",
              "probe-green": "#008000",
              "probe-plain": ""}

    def _painted_card(self, kind: str) -> dict:
        """The same glyph on a real `TaskCard` — the surface the detail row
        promises to match. Mirrors `test_board_followup_glyph.py:530-572`."""
        from textual.app import App

        card = self.ab.TaskCard(
            self.ab.Task.from_text(
                Path("t1_probe.md"),
                f"---\npriority: high\neffort: low\nstatus: Ready\n"
                f"followup_kind: {kind}\n---\n\nBody.\n"),
            None, column_id="c0")
        # A focused card auto-scrolls into view and pushed the probes off the
        # composited frame in the t1468_3 harness; focus cannot affect a
        # literal style.
        card.can_focus = False
        probes = self.PROBES
        SpanProbe = self._span_probe()

        class CardProbeApp(App):
            def compose(self):
                for text, colour in probes.items():
                    yield SpanProbe(text, colour)
                yield card

        out = {}

        async def go():
            app = CardProbeApp()
            async with app.run_test(size=(120, 24)) as pilot:
                await pilot.pause()
                out.update(self._painted(app))

        self._run(go())
        return out

    @staticmethod
    def _span_probe():
        from textual.widgets import Static
        from rich.text import Text as RichText

        class SpanProbe(Static):
            def __init__(self, label, colour):
                super().__init__()
                self._label, self._colour = label, colour

            def render(self):
                out = RichText("")
                if self._colour:
                    out.append(self._label, style=self._colour)
                else:
                    out.append(self._label)
                return out

        return SpanProbe

    def _painted_field(self, kind: str) -> dict:
        """Composite the real field beside literal-hex probes.

        A hex composites identically whether it arrives as a Rich base style or
        as a span, which is exactly why the production code pins one — so the
        probes are directly comparable to BOTH the row and the card.
        """
        from textual.app import App

        SpanProbe = self._span_probe()
        probes = self.PROBES
        field = self.FollowupKindField(kind, None, MagicMock(),
                                       classes="meta-ro")
        # Focus scrolls a focusable widget into view, which pushed the probes
        # off the composited frame in the t1468_3 harness. Focus cannot affect
        # a literal span style.
        field.can_focus = False

        class ProbeApp(App):
            # The one rule under test, copied verbatim from KanbanApp.CSS.
            CSS = ".meta-ro { height: 1; width: 100%; padding: 0 2; color: $text-muted; }"

            def compose(self):
                # Probes FIRST: a `Static` expands, and anything after it can be
                # pushed out of the frame. Order is layout only.
                for text, colour in probes.items():
                    yield SpanProbe(text, colour)
                yield field

        out = {}

        async def go():
            app = ProbeApp()
            async with app.run_test(size=(120, 24)) as pilot:
                await pilot.pause()
                out.update(self._painted(app))

        self._run(go())
        return out

    def test_fixture_facts(self):
        """Drift guard: the board really does paint this row muted, so the
        competition the probe app reproduces is the real one."""
        css = self.KanbanApp.CSS
        self.assertIn(".meta-ro", css)
        self.assertRegex(css, r"\.meta-ro\s*\{[^}]*color:\s*\$text-muted")
        painted = self._painted_field("risk_mitigation")
        for a, b in (("probe-yellow", "probe-grey"),
                     ("probe-yellow", "probe-green"),
                     ("probe-grey", "probe-green")):
            self.assertNotEqual(painted[a], painted[b],
                                f"{a} and {b} must resolve differently or the "
                                f"assertions below are untestable")

    def test_card_and_detail_row_paint_the_same_colour(self):
        """THE cross-surface promise, over the whole vocabulary.

        The docs say the detail row shows "the same glyph and colour as the
        card", and until `_followup_colour_hex` they did NOT match: a card
        applies the style as a Rich BASE style (`yellow` -> `#ffff00`) while
        the row appends it as a SPAN (`yellow` -> `#fd971f`). Comparing the row
        only against a probe could never have caught that — the comparison has
        to be against the card itself.
        """
        for kind, (glyph, _colour, _label) in self.FOLLOWUP_KINDS.items():
            with self.subTest(kind=kind):
                card = self._painted_card(kind)
                field = self._painted_field(kind)
                # Control: the two apps must agree on a fixed literal, or a
                # theme difference between them would explain any mismatch.
                self.assertEqual(card["probe-yellow"], field["probe-yellow"],
                                 "the two probe apps disagree on a literal hex")
                self.assertIn(glyph, card, f"{kind} did not paint on the card")
                self.assertIn(glyph, field, f"{kind} did not paint in the row")
                self.assertEqual(
                    card[glyph], field[glyph],
                    f"{kind}: the card paints {card[glyph]} but the task-detail "
                    f"row paints {field[glyph]} — the two surfaces promise the "
                    f"same colour, and a bare vocabulary name does not survive "
                    f"the base-style and span-style paths identically")

    def test_the_glyph_paints_in_its_kinds_colour(self):
        """Two kinds pinned against literal probes — one originally an ANSI
        name, one already a hex — so both vocabulary shapes are covered."""
        risk = self._painted_field("risk_mitigation")
        self.assertEqual(risk["▲"], risk["probe-yellow"],
                         "the risk_mitigation glyph must paint in `yellow`")
        docs = self._painted_field("docs_gap")
        self.assertEqual(docs["▤"], docs["probe-grey"],
                         "the docs_gap glyph must paint in its grey")

    def test_the_resolution_matches_textual_not_rich(self):
        """Pins WHICH resolution is canonical.

        Rich's `get_truecolor()` answers `#808000` for `yellow`; Textual's CSS
        palette answers `#ffff00`. The cards have always painted the latter, so
        adopting Rich's would have silently restyled every existing card while
        making this module's cross-surface test pass.
        """
        from rich.color import Color as RichColor
        for kind, (_g, colour, _l) in self.FOLLOWUP_KINDS.items():
            with self.subTest(kind=kind):
                resolved = self.ab._followup_colour_hex(colour)
                self.assertEqual(resolved.lower(),
                                 self.ab.TextualColor.parse(colour).hex.lower())
                if colour.startswith("#"):
                    continue      # a hex is identical under both libraries
                self.assertNotEqual(
                    resolved.lower(),
                    RichColor.parse(colour).get_truecolor().hex.lower(),
                    f"{kind}: resolving through Rich would change the colour "
                    f"the cards already paint")

    def test_an_unparseable_colour_degrades_to_the_raw_name(self):
        """`_followup_colour_hex` must never raise into a render pass — the
        board would go down on a single bad vocabulary entry.

        The real-world instance of this class is the Rich palette name that
        Textual rejects, which is exactly what `docs_gap` shipped with in
        t1468_3 (see the comment on its entry in `lib/followup_kinds.py`). That
        spelling is deliberately NOT used as a literal here:
        `tests/test_textual_markup_colours.py` scans string constants for
        precisely such tokens and would flag this file, and the behaviour under
        test is the `except ColorParseError` branch — which any unparseable
        token reaches identically.
        """
        for bad in ("not_a_colour", "definitely-not-a-colour", "puce_17"):
            with self.subTest(bad=bad):
                self.assertEqual(self.ab._followup_colour_hex(bad), bad)

    def test_the_glyph_is_not_muted_by_the_row_css(self):
        """THE claim, over the whole vocabulary. `Follow-up:` in the same row
        takes the widget's `$text-muted`; the glyph must not."""
        for kind in self.FOLLOWUP_KINDS:
            with self.subTest(kind=kind):
                painted = self._painted_field(kind)
                glyph = self.FOLLOWUP_KINDS[kind][0]
                self.assertIn(
                    glyph, painted,
                    f"{kind}'s glyph carries no explicit colour at all — its "
                    f"style {self.FOLLOWUP_KINDS[kind][1]!r} did not resolve")
                self.assertNotEqual(
                    painted[glyph], painted["Follow-up:"],
                    f"{kind}'s glyph paints in the row's muted CSS colour — "
                    f"its literal style {self.FOLLOWUP_KINDS[kind][1]!r} lost "
                    f"to `.meta-ro {{ color: $text-muted }}`")

    def test_every_kind_paints_a_distinct_colour_from_plain_row_text(self):
        """Render-level form of the defect `docs_gap` shipped with (t1468_3): a
        style Textual cannot parse degrades to the row's own colour, so the
        glyph paints exactly like the text beside it and half the acceptance
        criterion is silently lost."""
        for kind in self.FOLLOWUP_KINDS:
            with self.subTest(kind=kind):
                painted = self._painted_field(kind)
                self.assertNotEqual(painted[self.FOLLOWUP_KINDS[kind][0]],
                                    painted["probe-grey"] if
                                    self.FOLLOWUP_KINDS[kind][1] != "#808080"
                                    else painted["probe-green"],
                                    f"{kind} collided with an unrelated probe "
                                    f"colour — its style did not resolve")

    def test_the_unknown_fallback_claims_no_colour_of_its_own(self):
        """The paired half: an unrecognised kind has NO severity family, so it
        must borrow none. It carries no explicit style at all, so it never
        reaches the strip walk — exactly like the plain label text beside it,
        and it therefore inherits the row's own colour at paint time."""
        painted = self._painted_field("risk_mitgation")
        self.assertNotIn("·", painted,
                         "the unknown fallback must carry NO explicit colour — "
                         "an unrecognised kind has no severity family to signal")
        self.assertIn("Follow-up:", painted,
                      "control: the row did render, so the absence above is "
                      "about the glyph and not about an empty frame")
        self.assertIn("·", self._render_plain("risk_mitgation"),
                      "and it must still be VISIBLE — a bad value that silently "
                      "vanishes is indistinguishable from 'not a follow-up'")

    def _render_plain(self, kind):
        return self.FollowupKindField(kind, None, MagicMock()).render().plain

    def test_colour_assertion_is_not_vacuous(self):
        """[colour_over_widget_css_negative_control] — post-phase mitigation.

        This is the first test to read colour off a row that competes with its
        own CSS, so the extraction could easily pass while proving nothing.
        Mutate exactly one entry's colour and require the same comparison to
        FAIL.
        """
        kinds = self.ab.FOLLOWUP_KINDS
        original = kinds["risk_mitigation"]
        self.assertEqual(original[1], "yellow", "control: baseline colour")
        try:
            kinds["risk_mitigation"] = (original[0], "green", original[2])
            painted = self._painted_field("risk_mitigation")
            self.assertNotEqual(
                painted["▲"], painted["probe-yellow"],
                "NEGATIVE CONTROL FAILED: the glyph still reads as `yellow` "
                "after the vocabulary was mutated to `green` — the assertion "
                "is not reading colour off the composited frame at all")
            self.assertEqual(painted["▲"], painted["probe-green"])
        finally:
            kinds["risk_mitigation"] = original
        self.assertEqual(self.ab.FOLLOWUP_KINDS["risk_mitigation"], original,
                         "the vocabulary must be restored byte-identical")
        restored = self._painted_field("risk_mitigation")
        self.assertEqual(restored["▲"], restored["probe-yellow"],
                         "and the original assertion must be GREEN again")


# --- 6. narrow width --------------------------------------------------------


class FollowupKindNarrowWidthTests(_DetailFollowupBase, unittest.TestCase):
    """`render().plain` stays fully populated even when the parent clips the
    widget to nothing, so only a composited strip can see a clipped glyph
    (`MarkNarrowWidthTests`, `tests/test_board_marking.py:538-551`)."""

    def _screen_at(self, width, filename=RISK):
        out = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(width, 40)) as pilot:
                await self._settle(pilot)
                app.push_screen(self.TaskDetailScreen(
                    self._task(app, filename), app.manager))
                await self._settle(pilot)
                out["text"] = self._screen_text(app)

        self._run(go())
        return out["text"]

    def test_the_glyph_survives_a_wide_terminal(self):
        self.assertIn("▲", self._screen_at(160))

    def test_the_glyph_survives_a_narrow_terminal(self):
        """The label may truncate; the glyph is the leading cell of the value
        and must not be the thing that is dropped."""
        for width in (80, 60, 44):
            with self.subTest(width=width):
                text = self._screen_at(width)
                self.assertIn("Follow-up", text,
                              f"the row itself vanished at width {width}")
                self.assertIn("▲", text,
                              f"the glyph was clipped away at width {width}")


# --- 7. the subprocess seam -------------------------------------------------


class FollowupKindApplyTests(_DetailFollowupBase, unittest.TestCase):
    """The write itself, with no board boot and no real script.

    The CLI-side semantics — durability across an unrelated update, invalid-kind
    rejection, the manual_verification invariant in both directions — are
    already pinned by `tests/test_followup_kind_roundtrip.sh` (t1468_1) and are
    deliberately NOT duplicated here. What this class owns is the board's half:
    the exact argv, and what happens to the two exit statuses.
    """

    #: The real message `lib/followup_kinds_sh.sh` dies with.
    MV_ERROR = ("followup_kind 'manual_verification' requires issue_type "
                "'manual_verification' (resulting issue_type would be "
                "'feature'). Set both together, or choose a different "
                "followup_kind.")

    def _apply(self, new_kind, *, returncode=0, stderr="", stdout=""):
        task = self.ab.Task.from_text(
            Path("aitasks/t9101_risk.md"),
            "---\nstatus: Ready\nfollowup_kind: risk_mitigation\n---\nbody\n")
        field = self.FollowupKindField("risk_mitigation", MagicMock(), task)
        app = MagicMock()
        completed = subprocess.CompletedProcess(
            args=[], returncode=returncode, stdout=stdout, stderr=stderr)
        with patch.object(self.FollowupKindField, "app",
                          new_callable=PropertyMock, return_value=app), \
             patch.object(self.ab, "subprocess") as sp, \
             patch.object(self.ab, "_reload_detail_screen") as reload_:
            sp.run.return_value = completed
            field._apply("9101", new_kind)
            return {"argv": sp.run.call_args.args[0] if sp.run.call_args else None,
                    "kwargs": sp.run.call_args.kwargs if sp.run.call_args else {},
                    "app": app, "reload": reload_}

    def test_setting_a_kind_uses_the_exact_batch_argv(self):
        out = self._apply("qa_test_gap")
        self.assertEqual(out["argv"], [
            "./.aitask-scripts/aitask_update.sh", "--batch", "9101",
            "--followup-kind", "qa_test_gap", "--silent"])
        self.assertTrue(out["kwargs"].get("capture_output"))
        self.assertEqual(out["kwargs"].get("timeout"), 15)

    def test_clearing_passes_an_empty_string_not_a_sentinel(self):
        """The single most important argv in this module. `"none"` — or
        omitting the flag — would leave the key in place or write a value that
        reads back as an unrecognised kind."""
        out = self._apply("")
        self.assertEqual(out["argv"], [
            "./.aitask-scripts/aitask_update.sh", "--batch", "9101",
            "--followup-kind", "", "--silent"])
        self.assertEqual(out["argv"][4], "",
                         "the clear value must be the empty string")
        self.assertNotIn("none", out["argv"])

    def test_success_reloads_the_detail_screen(self):
        out = self._apply("qa_test_gap", returncode=0)
        self.assertEqual(out["reload"].call_count, 1)
        self.assertFalse(out["app"].notify.called)

    def test_a_rejection_surfaces_stderr_verbatim_and_does_not_reload(self):
        """Driven with the real invariant message: the board is the only place
        the user can see why `manual_verification` was refused."""
        out = self._apply("manual_verification", returncode=1,
                          stderr=self.MV_ERROR)
        self.assertFalse(out["reload"].called,
                         "a failed write must not reload the screen")
        self.assertTrue(out["app"].notify.called)
        msg, kwargs = out["app"].notify.call_args.args[0], \
            out["app"].notify.call_args.kwargs
        self.assertEqual(msg, self.MV_ERROR)
        self.assertEqual(kwargs.get("severity"), "error")
        self.assertIn("Set both together", msg,
                      "the remedy must reach the user, not just the refusal")

    def test_stdout_is_used_when_stderr_is_empty(self):
        out = self._apply("qa_test_gap", returncode=1, stdout="boom")
        self.assertEqual(out["app"].notify.call_args.args[0], "boom")

    def test_a_silent_failure_still_notifies(self):
        out = self._apply("qa_test_gap", returncode=2)
        self.assertEqual(out["app"].notify.call_args.args[0],
                         "followup_kind update failed")


class FollowupKindEditGuardTests(_DetailFollowupBase, unittest.TestCase):
    """`_edit`'s result callback — where `None` and `""` must not be conflated."""

    def _field(self, kind="risk_mitigation"):
        task = self.ab.Task.from_text(Path("aitasks/t9101_risk.md"),
                                      "---\nstatus: Ready\n---\nbody\n")
        return self.FollowupKindField(kind, MagicMock(), task)

    def _callback(self, field):
        """Drive `_edit` and capture the callback it handed to push_screen."""
        app = MagicMock()
        with patch.object(self.FollowupKindField, "app",
                          new_callable=PropertyMock, return_value=app):
            field._edit()
            return app.push_screen.call_args.args[1]

    def test_cancel_does_not_write(self):
        field = self._field()
        with patch.object(field, "_apply") as apply_:
            self._callback(field)(None)
        self.assertFalse(apply_.called, "Escape must never write")

    def test_clearing_does_write(self):
        field = self._field()
        with patch.object(field, "_apply") as apply_:
            self._callback(field)("")
        apply_.assert_called_once_with("9101", "")

    def test_choosing_the_current_kind_is_a_no_op(self):
        """Avoids a pointless `updated_at` bump and screen reload."""
        field = self._field("risk_mitigation")
        with patch.object(field, "_apply") as apply_:
            self._callback(field)("risk_mitigation")
        self.assertFalse(apply_.called)

    def test_clearing_an_already_unset_field_is_a_no_op(self):
        """The clear row is the default focus for an unset task, so a reflexive
        Enter there must not shell out."""
        field = self._field("")
        with patch.object(field, "_apply") as apply_:
            self._callback(field)("")
        self.assertFalse(apply_.called)

    def test_a_new_kind_writes(self):
        field = self._field("risk_mitigation")
        with patch.object(field, "_apply") as apply_:
            self._callback(field)("docs_gap")
        apply_.assert_called_once_with("9101", "docs_gap")


# --- 8. the live round-trip -------------------------------------------------


def _frontmatter_lines(path: Path) -> list:
    """The frontmatter block only.

    Scoped rather than scanning the whole file: `followup_kind:` is a plausible
    string in a task body, and a body hit would make the key look PRESENT after
    a clear that correctly removed it.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return []
    out = []
    for line in lines[1:]:
        if line == "---":
            break
        out.append(line)
    return out


def _has_key(path: Path, key: str) -> bool:
    """PRESENT/ABSENT for the key itself.

    A value probe cannot tell an absent key from one whose value is empty, and
    the clear semantics of this field are exactly 'the line is gone' — so
    absence needs its own probe. Mirrors `has_field` in
    `tests/test_followup_kind_roundtrip.sh:58`.
    """
    return any(line.startswith(f"{key}:") for line in _frontmatter_lines(path))


def _value(path: Path, key: str) -> str:
    for line in _frontmatter_lines(path):
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return ""


class FollowupKindLiveRoundTripTests(_DetailFollowupBase, bf.PristineTreeMixin,
                                     unittest.TestCase):
    """set -> repaint -> clear -> repaint, through the REAL `aitask_update.sh`.

    The positive control comes FIRST on purpose. Asserting only that the key is
    absent at the end would pass even if the set had silently persisted
    nothing — which is the whole of goal item 2.

    Under a fixture tree the board's relative `./.aitask-scripts/...` helpers do
    not exist, so this class symlinks the real ones in. Every other class in
    this module patches `subprocess.run` instead.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        link = cls.tree / ".aitask-scripts"
        if not link.exists():
            link.symlink_to(REPO_ROOT / ".aitask-scripts")
        cls._snapshot_pristine()

    def _path(self):
        return self.tasks_dir / RISK

    def _card_glyph(self, app, filename):
        """The glyph on ONE card, or None.

        Scoped deliberately: a whole-screen sweep would also collect the OTHER
        fixture tasks' glyphs, and the clear assertion would then never be able
        to go green.
        """
        for card in app.query(self.ab.TaskCard):
            if card.task_data.filename != filename:
                continue
            labels = card.query(".task-followup-glyph")
            return labels.first().render().plain if labels else None
        return None

    def test_fixture_facts(self):
        """Preconditions: the real script is reachable from the fixture cwd and
        the seeded task carries the kind this test starts from."""
        self.assertTrue(Path("./.aitask-scripts/aitask_update.sh").exists(),
                        "the symlink must make the real script reachable")
        self.assertTrue(_has_key(self._path(), "followup_kind"))
        self.assertEqual(_value(self._path(), "followup_kind"),
                         "risk_mitigation")
        self.assertNotIn(
            "qa_test_gap",
            [t.extra.get("followup_kind") if t.extra else None
             for t in DETAIL_TOPOLOGY],
            "the round-trip writes qa_test_gap; no other fixture may carry it, "
            "or its glyph could not be attributed to this task")

    def test_set_then_clear_round_trip_and_the_card_tracks_it(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                task = self._task(app, RISK)
                field = self.FollowupKindField(
                    task.metadata.get("followup_kind"), app.manager, task)

                def apply(kind):
                    with patch.object(self.FollowupKindField, "app",
                                      new_callable=PropertyMock,
                                      return_value=app), \
                         patch.object(self.ab, "_reload_detail_screen"):
                        field._apply("9101", kind)

                # -- set (positive control) --
                apply("qa_test_gap")
                seen["set_present"] = _has_key(self._path(), "followup_kind")
                seen["set_value"] = _value(self._path(), "followup_kind")

                app.manager.reload_task(RISK)
                app.refresh_board()
                await self._settle(pilot)
                seen["glyph_after_set"] = self._card_glyph(app, RISK)

                # -- clear --
                apply("")
                seen["clear_present"] = _has_key(self._path(), "followup_kind")

                app.manager.reload_task(RISK)
                app.refresh_board()
                await self._settle(pilot)
                seen["glyph_after_clear"] = self._card_glyph(app, RISK)

        self._run(go())

        # 1. the set actually persisted — without this the clear assertion
        #    below would pass vacuously.
        self.assertTrue(seen["set_present"],
                        "the real script did not write followup_kind at all")
        self.assertEqual(seen["set_value"], "qa_test_gap",
                         "the exact value must reach the frontmatter")
        # 2. and the card repainted.
        self.assertEqual(seen["glyph_after_set"],
                         self.FOLLOWUP_KINDS["qa_test_gap"][0],
                         "the card glyph must track the write")
        # 3. clearing REMOVES the key — not present-and-empty.
        self.assertFalse(seen["clear_present"],
                         "clearing must delete the `followup_kind:` line; a "
                         "present-but-empty key reads back as an unrecognised "
                         "kind and paints `·` on every cleared task")
        # 4. and the glyph is gone — no widget at all, not a blank one.
        self.assertIsNone(seen["glyph_after_clear"],
                          "the card must drop the glyph widget entirely")

    def test_an_invalid_kind_is_rejected_and_leaves_the_file_untouched(self):
        """The board offers all nine kinds and lets the shell refuse — so the
        refusal path must genuinely be non-destructive."""
        before = self._path().read_text(encoding="utf-8")
        app = MagicMock()
        task = self.ab.Task.from_text(self._path(),
                                      self._path().read_text(encoding="utf-8"))
        field = self.FollowupKindField("risk_mitigation", MagicMock(), task)
        with patch.object(self.FollowupKindField, "app",
                          new_callable=PropertyMock, return_value=app), \
             patch.object(self.ab, "_reload_detail_screen") as reload_:
            field._apply("9101", "not_a_real_kind")

        self.assertTrue(app.notify.called, "the refusal must be surfaced")
        self.assertEqual(app.notify.call_args.kwargs.get("severity"), "error")
        self.assertFalse(reload_.called)
        self.assertEqual(self._path().read_text(encoding="utf-8"), before,
                         "a rejected write must leave the file byte-identical")


if __name__ == "__main__":
    unittest.main()
