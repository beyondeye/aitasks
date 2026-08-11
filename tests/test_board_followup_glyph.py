"""Follow-up provenance glyph on board cards (t1468_3).

A task auto-spawned as a follow-up carries `followup_kind:` (t1468_1). The board
renders it as a leading gutter glyph so a follow-up is identifiable **at a
glance by colour and shape** — the user's explicit acceptance criterion.

Four things here are load-bearing and each is easy to break silently:

* **Per surface.** The three `TaskCard` subclasses fully override `compose` with
  no `super()` call, so a glyph added to `TaskCard` alone leaves follow-ups
  invisible in In-Flight and By-Trail. `FollowupGlyphSurfaceTests` asserts on
  each surface separately, and `TrailGhostCard`'s *absence* of a glyph is a
  tested decision, not an omission.
* **Colour.** `render().plain` cannot see colour, and `render().spans` cannot
  see an unresolved one. Only a composited strip proves the colour from
  `FOLLOWUP_KINDS` reached the screen — `FollowupGlyphColourTests`. This is the
  first board test to read colour off a strip; the segment walk is lifted from
  `tests/test_monitor_session_divider.py:475-486`.
* **Absent vs unknown.** `followup_kinds.glyph_for()` answers `·` for an absent
  kind just as for an unknown one, so calling it directly would paint a marker
  on every ordinary task. `_followup_marker` is the boundary that splits them,
  and `FollowupMarkerBoundaryTests` pins both halves plus totality over the junk
  `lib/task_yaml.py` deliberately lets through.
* **Collapsed groups.** A collapsed group mounts no member cards at all, so the
  `GroupHeader` roll-up is the ONLY place the provenance can surface there.

Narrow-width and colour-mutation controls live in `FollowupGlyphNarrowWidthTests`
and `test_colour_assertion_is_not_vacuous` — both are the plan's post-phase risk
mitigations, not incidental extras.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402

# One task per interesting case, spread across columns so no two share a card
# stack. `extra=` is dict.update-ed over the base frontmatter, which is how an
# arbitrary key like `followup_kind` reaches a fixture file.
PLAIN = "t9000_plain.md"          # no followup_kind at all — the control
RISK = "t9001_risk.md"            # risk_mitigation -> yellow ▲
DOCS = "t9002_docs.md"            # docs_gap -> #808080 grey ▤
TYPO = "t9003_typo.md"            # unrecognised value -> uncoloured ·

GLYPH_TOPOLOGY = (
    bf.FixtureTask(task_id="9000", col="c0", idx=10, slug="plain"),
    bf.FixtureTask(task_id="9001", col="c0", idx=20, slug="risk",
                   extra={"followup_kind": "risk_mitigation"}),
    bf.FixtureTask(task_id="9002", col="c1", idx=10, slug="docs",
                   extra={"followup_kind": "docs_gap"}),
    bf.FixtureTask(task_id="9003", col="c1", idx=20, slug="typo",
                   extra={"followup_kind": "risk_mitgation"}),  # sic: typo
)


def _manager(ab):
    """Bare TaskManager built from the *fixture-bound* board module.

    `ab` is threaded in rather than imported: under the harness the board is
    loaded under a synthetic module name, so a local `import aitask_board` would
    reach a different module object than the one under test. Copied from
    `tests/test_board_inflight_view.py:21-43`.
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


def _body(kind: str = "", status: str = "Implementing") -> str:
    fk = f"followup_kind: {kind}\n" if kind else ""
    return f"---\npriority: high\neffort: low\nstatus: {status}\n{fk}---\n\nBody.\n"


class _GlyphTestBase(bf.FixtureBoardTestBase):
    FIXTURE_TASKS = GLYPH_TOPOLOGY

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KanbanApp = cls.ab.KanbanApp
        cls.TaskCard = cls.ab.TaskCard
        cls.FOLLOWUP_KINDS = cls.ab.FOLLOWUP_KINDS
        cls.UNKNOWN_GLYPH = cls.ab.UNKNOWN_GLYPH

    def _run(self, coro):
        return asyncio.run(coro)

    def _card(self, app, filename):
        for card in app.query(self.TaskCard):
            if card.task_data.filename == filename:
                return card
        return None

    @staticmethod
    def _glyph_label(card):
        labels = card.query(".task-followup-glyph")
        return labels.first() if labels else None

    @staticmethod
    async def _settle(pilot, times=5):
        """Drain deferred work AND scheduled animations.

        Copied from `tests/test_board_bytrail_view.py:134-144`: focus scroll is
        both deferred and animated, so an assertion that runs too early observes
        the pre-scroll frame.
        """
        for _ in range(times):
            await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

    @staticmethod
    def _painted(app) -> dict:
        """`{text: colour-hex}` for every styled run composited to the screen.

        The only way to prove a colour reached the terminal: `render().plain`
        cannot see colour at all, and `render().spans` reports a colour that may
        never have resolved. Segment walk lifted from
        `tests/test_monitor_session_divider.py:475-486`.

        The value is the RESOLVED truecolor hex, not a name: Textual keeps ANSI
        colours symbolic (`Color.parse("ansi_yellow").hex` is literally
        `"ansi_yellow"`) until they are mapped through the running app's theme,
        so there is no static hex to pin and `seg.style.color.name` is already
        the resolved hex by the time it reaches a strip. Ground truth therefore
        comes from a probe rendered in the SAME app — see `_probe`.
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


# --- 1. the boundary --------------------------------------------------------


class FollowupMarkerBoundaryTests(_GlyphTestBase, unittest.TestCase):
    """`_followup_marker` — app-free, and the only place the raw value is read."""

    def setUp(self):
        self.marker = self.ab._followup_marker

    def test_fixture_facts(self):
        """The vocabulary this whole module is written against."""
        self.assertEqual(self.FOLLOWUP_KINDS["risk_mitigation"][:2],
                         ("▲", "yellow"))
        self.assertEqual(self.FOLLOWUP_KINDS["docs_gap"][:2],
                         ("▤", "#808080"))
        self.assertEqual(self.UNKNOWN_GLYPH, "·")

    def test_every_valid_kind_maps_to_its_own_glyph_and_colour(self):
        for kind, (glyph, colour, _label) in self.FOLLOWUP_KINDS.items():
            with self.subTest(kind=kind):
                self.assertEqual(self.marker({"followup_kind": kind}),
                                 (glyph, colour))

    def test_absent_is_not_a_followup(self):
        """The case that makes `glyph_for()` unusable here: it would answer `·`."""
        self.assertIsNone(self.marker({}))
        self.assertIsNone(self.marker(None))
        self.assertIsNone(self.marker({"priority": "high"}))

    def test_junk_values_are_total_and_silent(self):
        """`lib/task_yaml.py` leaves values type-honest, so all of these arrive."""
        for junk in (None, "", "   ", [], {}, 0, 1, True, False, ["a"], {"a": 1}):
            with self.subTest(junk=junk):
                self.assertIsNone(self.marker({"followup_kind": junk}))

    def test_unknown_string_renders_the_uncoloured_fallback(self):
        """A typo must stay VISIBLE — silently vanishing reads as 'not a
        follow-up', which is the one thing it is not."""
        self.assertEqual(self.marker({"followup_kind": "risk_mitgation"}),
                         ("·", None))
        self.assertEqual(self.marker({"followup_kind": "kind_from_the_future"}),
                         ("·", None))

    def test_a_value_is_never_normalised(self):
        """`followup_kind` is an identity key — trailing space is a real edit,
        not noise, so it must NOT silently match the stripped kind."""
        self.assertEqual(self.marker({"followup_kind": "risk_mitigation "}),
                         ("·", None))


# --- 2. vocabulary properties the rendering depends on ----------------------


class FollowupVocabularyTests(_GlyphTestBase, unittest.TestCase):
    """Properties of `FOLLOWUP_KINDS` itself that make it renderable.

    The board owns no second map, so there is no two-map drift guard to write
    (and a key-equality assertion against the module would be vacuous — it would
    compare the module to itself). What CAN drift is the module gaining a kind
    whose glyph collides or is too wide to sit in a one-cell gutter.
    """

    def test_glyphs_are_unique(self):
        glyphs = [g for g, _c, _l in self.FOLLOWUP_KINDS.values()]
        self.assertEqual(len(set(glyphs)), len(glyphs),
                         "two kinds sharing a glyph are indistinguishable")
        self.assertNotIn(self.UNKNOWN_GLYPH, glyphs,
                         "the unknown fallback must not collide with a real kind")

    def test_every_glyph_occupies_exactly_one_cell(self):
        from rich.cells import cell_len
        for kind, (glyph, _c, _l) in self.FOLLOWUP_KINDS.items():
            with self.subTest(kind=kind):
                self.assertEqual(cell_len(glyph), 1,
                                 f"{kind}'s glyph would misalign the gutter")
        self.assertEqual(cell_len(self.UNKNOWN_GLYPH), 1)

    def test_every_kind_names_a_colour(self):
        for kind, (_g, colour, _l) in self.FOLLOWUP_KINDS.items():
            with self.subTest(kind=kind):
                self.assertTrue(colour, f"{kind} has no colour to render")

    def test_every_colour_is_parseable_by_textual(self):
        """The guard for the defect this task found: `bright_black` is a valid
        RICH colour that Textual cannot parse, and Textual does not raise on a
        style it fails to parse — it silently falls back to the default
        foreground, so the glyph rendered pixel-identical to ordinary card text.

        A name-level check, because it is the cheapest place to catch it: the
        render-level consequence (`test_no_kind_paints_as_plain_text`) needs a
        booted app per kind, while this fails the instant the vocabulary gains
        an unparseable colour.
        """
        from textual.color import Color, ColorParseError
        for kind, (_g, colour, _l) in self.FOLLOWUP_KINDS.items():
            with self.subTest(kind=kind):
                try:
                    Color.parse(colour)
                except ColorParseError as exc:
                    self.fail(f"{kind}'s colour {colour!r} is not parseable by "
                              f"Textual, so it will silently render as the "
                              f"default foreground: {exc}")

    def test_every_colour_is_parseable_by_rich(self):
        """The other half: the glyph is applied as a literal RICH style, so a
        Textual-only spelling (`ansi_bright_black`) would fail on the other
        side. Only a value both libraries accept is safe.
        """
        from rich.style import Style
        from rich.errors import StyleSyntaxError
        for kind, (_g, colour, _l) in self.FOLLOWUP_KINDS.items():
            with self.subTest(kind=kind):
                try:
                    self.assertIsNotNone(Style.parse(colour).color)
                except (StyleSyntaxError, ValueError) as exc:
                    self.fail(f"{kind}'s colour {colour!r} is not a valid Rich "
                              f"style: {exc}")


# --- 3. the surfaces --------------------------------------------------------


class FollowupGlyphSurfaceTests(_GlyphTestBase, unittest.TestCase):
    """One test per card class. A `TaskCard`-only suite would pass while
    follow-ups stayed invisible in In-Flight and By-Trail."""

    def _render_card(self, card, selector):
        """Per-card `CardApp` — no board boot. Returns the renderable (not
        `.plain`) so `.spans` stays reachable.
        `tests/test_board_bytrail_view.py:411-429`."""
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
                labels = card.query(selector)
                found["label"] = labels.first(Label).render() if labels else None

        self._run(go())
        return found["label"]

    def _inflight_card(self, kind: str):
        """An `InFlightItem` is never constructed directly — it comes out of the
        production classifier over a real task file."""
        with tempfile.TemporaryDirectory() as td:
            mgr = _manager(self.ab)
            path = Path(td) / "t1_card.md"
            body = _body(kind)
            path.write_text(body, encoding="utf-8")
            task = self.ab.Task.from_text(path, body)
            mgr.task_datas[task.filename] = task
            item = mgr.get_inflight_items()[0]
            return self.ab.InFlightTaskCard(item, mgr, column_id="inflight-agent")

    def _trail_card(self, kind: str, *, ghost=False, landed=False):
        body = _body(kind, status="Ready")
        task = self.ab.Task.from_text(Path("t42_demo.md"), body)
        entry = {"task": "aitasks#42", "position": 1,
                 "classification": "core", "confidence": "high"}
        view = self.ab.TrailEntryView(entry, None if ghost else task, "",
                                      landed=landed)
        if ghost:
            return self.ab.TrailGhostCard(view, {"ordinal": 1}, "trail-w1")
        return self.ab.TrailTaskCard(view, {"ordinal": 1}, None, "trail-w1")

    # -- TaskCard (kanban / topic / child) --

    def test_taskcard_shows_the_glyph_and_a_plain_task_shows_none(self):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                seen["risk"] = self._glyph_label(self._card(app, RISK))
                seen["docs"] = self._glyph_label(self._card(app, DOCS))
                seen["typo"] = self._glyph_label(self._card(app, TYPO))
                seen["plain"] = self._glyph_label(self._card(app, PLAIN))

        self._run(go())
        self.assertIsNotNone(seen["risk"], "a follow-up must carry a glyph label")
        self.assertEqual(seen["risk"].render().plain, "▲")
        self.assertEqual(seen["docs"].render().plain, "▤")
        self.assertEqual(seen["typo"].render().plain, "·")
        self.assertIsNone(seen["plain"],
                          "an ordinary task must yield NO glyph widget at all — "
                          "not a blank one")

    def test_the_glyph_sits_between_the_mark_and_the_number(self):
        """Order is the whole point of a gutter: mark, provenance, number."""
        order = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                card = self._card(app, RISK)
                classes = []
                for label in card.query(".task-mark, .task-followup-glyph, "
                                        ".task-number"):
                    for wanted in ("task-mark", "task-followup-glyph",
                                   "task-number"):
                        if wanted in label.classes:
                            classes.append(wanted)
                            break
                order["classes"] = classes

        self._run(go())
        self.assertEqual(order["classes"],
                         ["task-mark", "task-followup-glyph", "task-number"])

    def test_a_topic_lane_card_has_no_mark_but_still_shows_the_glyph(self):
        """`markable=True` is set only in `KanbanColumn.task_block`, so the glyph
        must not hang off the mark — a TopicColumn card has no mark at all."""
        card = self.ab.TaskCard(
            self.ab.Task.from_text(Path("t9001_risk.md"),
                                   _body("risk_mitigation")),
            None, column_id="topic-x")
        rendered = self._render_card(card, ".task-followup-glyph")
        self.assertIsNotNone(rendered)
        self.assertEqual(rendered.plain, "▲")

    # -- InFlightTaskCard --

    def test_inflight_card_shows_the_glyph(self):
        rendered = self._render_card(self._inflight_card("risk_mitigation"),
                                     ".task-followup-glyph")
        self.assertIsNotNone(rendered, "In-Flight cards must show provenance too")
        self.assertEqual(rendered.plain, "▲")

    def test_inflight_card_without_a_kind_shows_nothing(self):
        self.assertIsNone(self._render_card(self._inflight_card(""),
                                            ".task-followup-glyph"))

    # -- TrailTaskCard --

    def test_trail_card_prepends_the_glyph_into_the_title(self):
        """By-Trail has no `.task-title-row` Horizontal — the glyph lives inside
        the title `Text`, so it is asserted there rather than as a gutter."""
        rendered = self._render_card(self._trail_card("risk_mitigation"),
                                     ".task-title")
        self.assertTrue(rendered.plain.startswith("▲ "),
                        f"expected a leading glyph, got {rendered.plain!r}")
        self.assertIn("t42", rendered.plain)

    def test_trail_card_glyph_precedes_the_landed_check(self):
        rendered = self._render_card(
            self._trail_card("risk_mitigation", landed=True), ".task-title")
        self.assertTrue(rendered.plain.startswith("▲ ✔"),
                        f"provenance must lead, got {rendered.plain!r}")

    def test_trail_card_reads_frontmatter_not_the_trail_entry(self):
        """The independence from t1468_5: the trail *snapshot* is irrelevant
        here, so an entry that says nothing still yields the frontmatter glyph.
        """
        card = self._trail_card("docs_gap")
        self.assertNotIn("followup_kind", card.trail_entry)
        rendered = self._render_card(card, ".task-title")
        self.assertTrue(rendered.plain.startswith("▤ "))

    def test_trail_card_without_a_kind_has_a_bare_title(self):
        rendered = self._render_card(self._trail_card(""), ".task-title")
        self.assertFalse(rendered.plain.startswith(("▲", "▤", "·")),
                         f"unexpected leading glyph in {rendered.plain!r}")

    # -- TrailGhostCard: no glyph, BY DESIGN --

    def test_ghost_card_shows_no_glyph_and_does_not_raise(self):
        """A ghost is a referenced task with no local file — nothing to classify
        and nothing to pick. Tested because it is a decision, not an omission."""
        card = self._trail_card("", ghost=True)
        self.assertEqual(card.task_data.metadata, {})
        rendered = self._render_card(card, ".task-title")
        self.assertIsNotNone(rendered, "the ghost must still render its title")
        self.assertFalse(rendered.plain.startswith(("▲", "▤", "·")))
        # A fresh card: a widget already mounted by one `run_test` cannot be
        # remounted in a second app.
        self.assertIsNone(self._render_card(self._trail_card("", ghost=True),
                                            ".task-followup-glyph"))


class FollowupEveryKindRendersTests(_GlyphTestBase, unittest.TestCase):
    """The guard that actually matters now that the board owns no second map:
    a kind added to `followup_kinds.py` must reach the screen. This fails the
    moment the vocabulary grows and a render path hardcodes a subset."""

    def test_every_kind_in_the_vocabulary_renders_its_glyph(self):
        from textual.app import App
        from textual.widgets import Label

        results = {}

        async def go():
            for kind in self.FOLLOWUP_KINDS:
                card = self.ab.TaskCard(
                    self.ab.Task.from_text(Path(f"t1_{kind}.md"), _body(kind)),
                    None, column_id="c0")

                class CardApp(App):
                    def compose(self):
                        yield card

                app = CardApp()
                async with app.run_test(size=(90, 24)) as pilot:
                    await pilot.pause()
                    label = card.query_one(".task-followup-glyph", Label)
                    results[kind] = label.render().plain

        self._run(go())
        self.assertEqual(
            results,
            {kind: glyph for kind, (glyph, _c, _l) in self.FOLLOWUP_KINDS.items()})


# --- 4. colour, on the composited screen ------------------------------------


class FollowupGlyphColourTests(_GlyphTestBase, unittest.TestCase):
    """Half the acceptance criterion is COLOUR, and neither `render().plain` nor
    `render().spans` can prove it: `.plain` drops style entirely, and `.spans`
    reports a colour name that may never have resolved. Only the composited
    frame is evidence.

    Asserted on the colour NAME rather than a hex: Rich's standalone `cyan` is
    `#008080` while Textual's palette resolves it to `#00ffff`, and the name is
    what `FOLLOWUP_KINDS` actually pins.
    """

    #: Probe colours are written as LITERALS here, never read from
    #: `FOLLOWUP_KINDS`. If the probe took its colour from the module, mutating
    #: the module would move probe and glyph together and the negative control
    #: below would pass while proving nothing.
    #: `probe-plain` is deliberately UNSTYLED — it is the default foreground,
    #: i.e. the ground truth for "this glyph has no colour at all".
    PROBES = {"probe-yellow": "yellow",
              "probe-grey": "#808080",
              "probe-green": "green",
              "probe-plain": ""}

    def _painted(self, kind: str) -> dict:
        """Composite one card of `kind` alongside the literal-colour probes.

        Ground truth is the probe rendered in the SAME app under the SAME theme,
        which is what makes the assertion palette-agnostic: we never claim to
        know that `yellow` is `#ffff00`, only that the glyph paints in whatever
        `yellow` paints as right here.
        """
        from textual.app import App
        from textual.widgets import Label
        from rich.text import Text as RichText

        probes = self.PROBES
        card = self.ab.TaskCard(
            self.ab.Task.from_text(Path("t1_probe.md"), _body(kind)),
            None, column_id="c0")
        # A `TaskCard` is focusable, and Textual scrolls the focused widget into
        # view — which pushed the probes to y=-1, off the composited frame, so
        # every lookup KeyError'd. Focus changes the card's BORDER colour only;
        # the glyph's own literal style is unaffected.
        card.can_focus = False
        out = {}

        class ProbeApp(App):
            def compose(self):
                # Probes FIRST, deliberately: a bare App has no CSS, so the
                # card (a `Static`) expands to fill the screen and would push
                # anything below it out of the composited frame — the probes
                # would then be silently missing and every lookup would
                # KeyError. Order is layout only; it cannot affect colour.
                for text, colour in probes.items():
                    yield Label(RichText(text, style=colour) if colour
                                else RichText(text))
                yield card

        async def go():
            app = ProbeApp()
            async with app.run_test(size=(90, 24)) as pilot:
                await pilot.pause()
                out.update(_GlyphTestBase._painted(app))

        self._run(go())
        return out

    def test_fixture_facts(self):
        """Preconditions: the two kinds carry the colours this class asserts on,
        and those colours are genuinely distinguishable once resolved."""
        self.assertEqual(self.FOLLOWUP_KINDS["risk_mitigation"][1], "yellow")
        self.assertEqual(self.FOLLOWUP_KINDS["docs_gap"][1], "#808080")
        painted = self._painted("risk_mitigation")
        self.assertNotEqual(painted["probe-yellow"], painted["probe-grey"],
                            "the two probe colours must resolve differently, or "
                            "every assertion below is untestable")
        self.assertNotEqual(painted["probe-yellow"], painted["probe-green"])

    def test_each_glyph_is_painted_in_its_own_colour(self):
        risk = self._painted("risk_mitigation")
        self.assertEqual(risk["▲"], risk["probe-yellow"],
                         "the risk_mitigation glyph must paint in `yellow`")
        docs = self._painted("docs_gap")
        self.assertEqual(docs["▤"], docs["probe-grey"],
                         "the docs_gap glyph must paint in its grey")

    def test_no_kind_paints_as_plain_text(self):
        """Every kind must be distinguishable by COLOUR, not shape alone.

        This is the render-level form of the defect `docs_gap` shipped with: a
        colour Textual cannot parse degrades to the default foreground, so the
        glyph paints exactly like the card title beside it and half the
        acceptance criterion is silently lost. `probe-plain` carries no style at
        all, so it IS the default foreground — ground truth for "uncoloured".
        """
        for kind in self.FOLLOWUP_KINDS:
            with self.subTest(kind=kind):
                painted = self._painted(kind)
                glyph = self.FOLLOWUP_KINDS[kind][0]
                self.assertIn(glyph, painted, f"{kind}'s glyph did not paint")
                self.assertNotEqual(
                    painted[glyph], painted["probe-plain"],
                    f"{kind}'s glyph paints in the default foreground — its "
                    f"colour {self.FOLLOWUP_KINDS[kind][1]!r} did not resolve")

    def test_the_unknown_fallback_claims_no_severity_colour(self):
        """An unrecognised kind has no severity family, so it must not borrow
        one — it may inherit the card's own text colour, but never a kind's."""
        painted = self._painted("not_a_real_kind")
        self.assertIn("·", painted, "the fallback must still paint")
        self.assertNotEqual(painted["·"], painted["probe-yellow"])
        self.assertNotEqual(painted["·"], painted["probe-grey"])

    def test_colour_assertion_is_not_vacuous(self):
        """[colour_assertion_negative_control] — the plan's post-phase mitigation.

        There is no board precedent for reading colour off a strip, so the
        assertion above could easily pass while proving nothing. Mutate exactly
        one entry's colour and require the same comparison to FAIL. A control
        that stays green means the extraction is wrong, not the code right.
        """
        kinds = self.ab.FOLLOWUP_KINDS
        original = kinds["risk_mitigation"]
        self.assertEqual(original[1], "yellow", "control: baseline colour")
        try:
            kinds["risk_mitigation"] = (original[0], "green", original[2])
            painted = self._painted("risk_mitigation")
            self.assertNotEqual(
                painted["▲"], painted["probe-yellow"],
                "NEGATIVE CONTROL FAILED: the glyph still reads as `yellow` "
                "after the vocabulary was mutated to `green` — the assertion "
                "is not reading colour off the composited frame at all")
            self.assertEqual(painted["▲"], painted["probe-green"],
                             "the mutated colour must be what actually paints")
        finally:
            kinds["risk_mitigation"] = original
        self.assertEqual(self.ab.FOLLOWUP_KINDS["risk_mitigation"], original,
                         "the vocabulary must be restored byte-identical")
        restored = self._painted("risk_mitigation")
        self.assertEqual(restored["▲"], restored["probe-yellow"],
                         "and the original assertion must be GREEN again")


class FollowupGlyphNarrowWidthTests(_GlyphTestBase, unittest.TestCase):
    """[narrow_width_composited_probe] — the plan's second post-phase mitigation.

    The gutter adds 2 cells (glyph + margin) to a title row whose `.task-title`
    is `width: 1fr` inside a column with `min_width: 30`, and `TrailTaskCard`
    prepends into the title `Text` rather than a fixed-width gutter — so it
    clips on a different rule from every other surface.

    `Label.render().plain` stays fully populated even when the parent clips it to
    nothing (this is why `MarkNarrowWidthTests` exists), so only the composited
    frame can answer 'is it readable'.
    """

    def _screen_at(self, width, height=40):
        seen = {}

        async def go():
            app = self.KanbanApp()
            async with app.run_test(size=(width, height)) as pilot:
                await self._settle(pilot)
                seen["text"] = self._screen_text(app)
                seen["painted"] = self._painted(app)

        self._run(go())
        return seen

    def test_fixture_facts(self):
        """Control: at a comfortable width everything is on screen, so a failure
        at the narrow width below is about width and nothing else."""
        seen = self._screen_at(160)
        self.assertIn("▲", seen["text"])
        self.assertIn("▤", seen["text"])

    def test_the_glyph_survives_the_narrowest_usable_terminal(self):
        """One column is 30 cells at `min_width`; 44 fits a single column plus
        the board chrome — the narrowest terminal the board is usable in.

        Colour is asserted by comparing against the SAME glyph at a comfortable
        width rather than a hex literal: Textual resolves ANSI colours through
        the app theme, so the wide-width render is the only palette-independent
        ground truth available here.
        """
        narrow = self._screen_at(44)
        wide = self._screen_at(160)
        self.assertIn("▲", narrow["text"],
                      "the follow-up glyph is clipped off the screen at width 44")
        self.assertEqual(narrow["painted"].get("▲"), wide["painted"].get("▲"),
                         "the glyph paints at narrow width but loses its colour")

    def test_a_mixed_column_keeps_the_glyph_distinguishable(self):
        """Against a column of mixed follow-up and non-follow-up cards — a single
        card in isolation cannot show that the gutter stays aligned."""
        seen = self._screen_at(60)
        rows_with_glyph = [r for r in seen["text"].splitlines() if "▲" in r]
        self.assertTrue(rows_with_glyph, "no row carries the glyph at width 60")
        self.assertNotIn("▲", "".join(
            r for r in seen["text"].splitlines() if "plain" in r),
            "the glyph leaked onto the non-follow-up card")


# --- 5. the collapsed-group roll-up -----------------------------------------


class FollowupGroupRollupTests(_GlyphTestBase, unittest.TestCase):
    """`▸ perf work (3) · ▲2 ◈1`.

    A collapsed group mounts NO member cards (`KanbanColumn.compose` `continue`s
    past `task_block`), so this header is the only surface that can carry the
    provenance there. App-free, per `GroupHeaderLabelTests`.
    """

    SLUG = "perf_work"

    def _header(self, *kinds, collapsed=True, count=None):
        members = [self.ab.Task.from_text(Path(f"t{i}_m.md"), _body(k))
                   for i, k in enumerate(kinds)]
        h = self.ab.GroupHeader("c0", self.SLUG, members, collapsed)
        if count is not None:
            h.set_match_count(count)
        return h

    def test_fixture_facts(self):
        """The baseline every case below perturbs — and the negative control:
        a group with no follow-ups gets NO roll-up."""
        self.assertEqual(self._header("", "").render().plain,
                         "▸ perf work (2)")

    def test_rollup_tallies_each_kind_with_its_glyph(self):
        h = self._header("risk_mitigation", "risk_mitigation", "review_finding")
        self.assertEqual(h.render().plain, "▸ perf work (3) · ▲2 ◈1")

    def test_rollup_order_is_the_vocabulary_order_not_the_member_order(self):
        """Determinism: the same group must read the same however it is sorted."""
        forward = self._header("review_finding", "risk_mitigation").render().plain
        reverse = self._header("risk_mitigation", "review_finding").render().plain
        self.assertEqual(forward, reverse)
        self.assertEqual(forward, "▸ perf work (2) · ▲1 ◈1",
                         "risk_mitigation precedes review_finding in "
                         "FOLLOWUP_KINDS, so it must lead here too")

    def test_partial_membership_counts_only_the_followups(self):
        h = self._header("risk_mitigation", "", "")
        self.assertEqual(h.render().plain, "▸ perf work (3) · ▲1")

    def test_unknown_kinds_tally_last_under_the_fallback(self):
        h = self._header("risk_mitigation", "not_a_real_kind")
        self.assertEqual(h.render().plain, "▸ perf work (2) · ▲1 ·1")

    def test_rollup_follows_the_match_badge(self):
        h = self._header("risk_mitigation", "", "", count=2)
        self.assertEqual(h.render().plain, "▸ perf work (3) · 2 match · ▲1")

    def test_collapse_flip_preserves_the_rollup(self):
        """The same trap `test_set_collapsed_repaint_preserves_the_badge` pins:
        a roll-up appended by whoever sets it — rather than built inside
        `_label()` — is silently erased by an unrelated glyph flip."""
        h = self._header("risk_mitigation", collapsed=False)
        self.assertEqual(h.render().plain, "▾ perf work (1) · ▲1")
        h.set_collapsed(True)
        self.assertEqual(h.render().plain, "▸ perf work (1) · ▲1")

    def test_match_count_repaint_preserves_the_rollup(self):
        h = self._header("risk_mitigation")
        h.set_match_count(1)
        self.assertEqual(h.render().plain, "▸ perf work (1) · 1 match · ▲1")
        h.set_match_count(None)
        self.assertEqual(h.render().plain, "▸ perf work (1) · ▲1")

    def test_the_group_title_is_never_markup_parsed(self):
        """A hand-edited `boardgroup` is user data. Assembling the label from
        literal parts (rather than an f-string a markup-enabled Static parses)
        is what keeps a `[/]` in a slug from corrupting the header."""
        h = self.ab.GroupHeader("c0", "a[/]b", [], True)
        self.assertIn("a[/]b", h.render().plain)


class FollowupGroupRollupLiveTests(_GlyphTestBase, unittest.TestCase):
    """The roll-up on a genuinely collapsed group in a booted board — the app-free
    class above cannot prove the header is what the user actually sees when the
    member cards are unmounted."""

    FIXTURE_TASKS = (
        bf.FixtureTask(task_id="9000", col="c0", idx=10, slug="plain",
                       extra={"boardgroup": "perf_work"}),
        bf.FixtureTask(task_id="9001", col="c0", idx=20, slug="risk",
                       extra={"boardgroup": "perf_work",
                              "followup_kind": "risk_mitigation"}),
    )

    def _label_and_cards(self, collapse):
        seen = {}

        async def go():
            app = self.KanbanApp()
            if collapse:
                app.collapsed_groups.add("c0/perf_work")
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                header = next((h for h in app.query(self.ab.GroupHeader)
                               if h.column_id == "c0" and h.slug == "perf_work"),
                              None)
                seen["label"] = header.render().plain if header else None
                seen["cards"] = len([c for c in app.query(self.TaskCard)
                                     if c.column_id == "c0"])

        self._run(go())
        return seen

    def test_fixture_facts(self):
        """Expanded: the member cards are mounted, so the glyph is visible on
        them — and the roll-up is present on the header regardless."""
        seen = self._label_and_cards(collapse=False)
        self.assertEqual(seen["cards"], 2)
        self.assertEqual(seen["label"], "▾ perf work (2) · ▲1")

    def test_collapsed_group_surfaces_the_rollup_with_no_member_cards(self):
        seen = self._label_and_cards(collapse=True)
        self.assertEqual(seen["cards"], 0,
                         "control: a collapsed group must mount no member cards")
        self.assertEqual(seen["label"], "▸ perf work (2) · ▲1",
                         "with no cards mounted the header is the ONLY place "
                         "the follow-up can surface")

    def test_the_rollup_glyph_is_painted_in_colour(self):
        """The roll-up reaches the screen through `Content.assemble`, a DIFFERENT
        API from the cards' Rich `Text` — and it is Textual's own style parser,
        the exact path t1453 documents as silently inert for a name it cannot
        resolve. Ground truth is the collapse glyph `▸` in the same header:
        unstyled, so it paints the header's default foreground.
        """
        painted = {}

        async def go():
            app = self.KanbanApp()
            app.collapsed_groups.add("c0/perf_work")
            async with app.run_test(size=(160, 48)) as pilot:
                await self._settle(pilot)
                painted.update(self._painted(app))

        self._run(go())
        self.assertIn("▲", painted, "the roll-up glyph never reached the screen")
        self.assertNotEqual(
            painted["▲"], painted.get("▸"),
            "the roll-up glyph paints in the header's default foreground — its "
            "colour did not resolve through Content.assemble")


if __name__ == "__main__":
    unittest.main()
