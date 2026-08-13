"""By-Trail board view tests (t1210_4).

Covers the pure trail-projection model (build_trail_lanes, overlaps,
fold-aware discovery dedup, glyph pin against the schema enum), render-level
card assertions, Pilot behavior (view switch, footer gating, ghost
navigation, subtitle restore), the keyboard-vs-timer refresh split, the
worker supersession guard, launch-argument construction spies, and the
read-only negative control (only drift/get/versions verbs are ever spawned).

Trail example docs under aidocs/implementation_trail_examples/ are never
mutated — tests operate on deep copies.

Harness: every app boot runs against a **fixture** task tree via
``tests/lib/board_fixture.py`` (t1354_1). These tests used to boot against the
live ``aitasks/`` tree at 2.44s per boot; the fixture costs 0.19s, which took
this file from 227s to under 30s. Two consequences worth knowing before adding
a test here: the fixture deliberately carries no ``artifacts:`` frontmatter (so
``discover_trails`` returns [] by construction) and it DOES carry a
``project_config.yaml``, without which every ``aitasks#<id>`` trail ref would
silently render as a cross-repo ghost — see ``TrailRefResolutionTests``.
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_command_screen as acs  # noqa: E402
import board_fixture as bf  # noqa: E402
import task_yaml  # noqa: E402

FIXTURE_PATH = (REPO_ROOT / "aidocs" / "implementation_trail_examples"
                / "gate_framework.json")


class FakeClock:
    """Monotonic-clock stand-in so the t1279 debounce tests never sleep."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _ghost_doc() -> dict:
    """Minimal two-wave doc whose members are all foreign (ghost-only)."""
    waves = []
    for i in (1, 2):
        waves.append({
            "wave_id": f"w{i}", "ordinal": i, "title": f"Wave {i}",
            "purpose": "p", "entries": [{
                "entry_id": f"e{i}", "task": f"otherproj#{i}",
                "topic": "otherproj#1", "position": 1,
                "classification": "core", "confidence": "high",
                "rationale": "r", "snapshot": {"status": "Ready"},
            }],
        })
    return {"title": "Ghost trail", "trail_id": "trail-ghost", "waves": waves,
            "narrative": {"problem_statement": "ps",
                          "recommendation_summary": "rs"}}


class ByTrailTestBase(bf.FixtureBoardTestBase, unittest.TestCase):
    """Boots the real KanbanApp against a fixture task tree (t1354_1).

    Before t1354_1 this chdir'd to REPO_ROOT and imported `aitask_board`
    canonically, so all ~57 app boots in this file loaded the **live** aitasks/
    tree — 2.44s per boot against 0.19s on the fixture. The harness owns the
    tree, the chdir and its restore; see tests/lib/board_fixture.py.

    The fixture carries no `artifacts:` frontmatter, so `discover_trails`
    returns [] by construction — the live repo's incidental emptiness used to be
    the implicit "no-trails fixture", and it is now explicit. It DOES carry a
    `project_config.yaml` naming the project `aitasks`, without which every
    `aitasks#<id>` trail ref would silently resolve as a cross-repo ghost.
    """

    def _run(self, coro):
        return asyncio.run(coro)

    @staticmethod
    def _screen_rows(app) -> list[str]:
        """Composited frame text, row by row.

        Deliberately NOT app.sub_title / widget.region / widget.display: an
        occluded widget reports display=True with a correct region and still
        appears in the compositor's visible_widgets, which is exactly how the
        freshness banner shipped invisible behind the docked filter row
        (t1273 item #3 -> t1278). Only the composited frame proves a row
        reaches the screen."""
        return [strip.text for strip
                in app.screen._compositor.render_strips(app.screen.size)]

    @staticmethod
    def _dialog_text(app, widget) -> str:
        """Composited frame sliced to `widget`'s columns, chrome stripped.

        Whole-screen flattening cannot be used for a *centred modal*: every
        screen row also carries the board rendered to the left and right of the
        dialog, so a phrase that wraps inside the dialog comes out with board
        text spliced into the middle of it ("Enter open · t9000 parent Esc
        cancel") and no assertion can match it. Slicing to the widget's own
        column range first, then collapsing the block-drawing border glyphs, is
        what makes a wrapped dialog phrase assertable (t1366)."""
        region = widget.region
        rows = [strip.text for strip
                in app.screen._compositor.render_strips(app.screen.size)]
        raw = " ".join(row[region.x:region.right]
                       for row in rows[region.y:region.bottom])
        return " ".join(
            "".join(" " if "▀" <= ch <= "▟" else ch
                    for ch in raw).split())

    @staticmethod
    async def _settle(pilot, times=5):
        """Drain deferred work AND scheduled animations.

        Scroll-into-view on focus is both deferred (`Screen.set_focus` ->
        `call_later`) and animated, so a render assertion that runs too early
        observes the pre-scroll frame."""
        for _ in range(times):
            await pilot.pause()
        await pilot.wait_for_scheduled_animations()
        await pilot.pause()

    def _mk_trail_info(self, handle: str, title: str) -> object:
        """A minimal discovered-trail row for the selection modal."""
        return self.ab.TrailInfo(
            handle=handle, owner_id="9000", owner_archived=False,
            owner_folded=False, name=title,
            doc={"title": title, "scope": {"kind": "repo"},
                 "generation": {"generated_at": "2026-08-01"},
                 "freshness": {"state": "current"}})

    @staticmethod
    def _footer_actions(app) -> set[str]:
        return {
            active.binding.action
            for active in app.screen.active_bindings.values()
        }

    def _mk_task(self, filename: str, status: str = "Ready") -> object:
        return self.ab.Task.from_text(
            Path(filename),
            f"---\nstatus: {status}\npriority: medium\n---\nbody\n")

    async def _enter_synthetic_bytrail(self, app, pilot, doc,
                                       handle="art:trail-test"):
        """Drive the app into By-Trail with a pre-loaded synthetic trail
        (drift worker stubbed out — no subprocess)."""
        app.active_trail_handle = handle
        app._trail_infos = []
        app._trail_doc = doc
        app._trail_error = ""
        app._start_trail_drift = lambda: None
        app._set_base_filter("bytrail")
        await pilot.pause()
        await pilot.pause()


class TrailModelTests(ByTrailTestBase):
    """Pure-function projection tests (no widgets)."""

    def test_glyph_map_pins_schema_classification_enum(self):
        ab = self.ab
        schema = ab.trail_schema.load_schema()
        enum = schema["$defs"]["entry"]["properties"]["classification"]["enum"]
        self.assertEqual(set(ab.TRAIL_CLASSIFICATION_GLYPHS), set(enum))
        # Wireframe-pinned glyphs (RFC §15).
        self.assertEqual(ab.TRAIL_CLASSIFICATION_GLYPHS["hard_prerequisite"],
                         "◆")
        self.assertEqual(ab.TRAIL_CLASSIFICATION_GLYPHS["core"], "●")
        # All glyphs distinct.
        self.assertEqual(len(set(ab.TRAIL_CLASSIFICATION_GLYPHS.values())),
                         len(ab.TRAIL_CLASSIFICATION_GLYPHS))

    def test_lanes_wave_and_position_order(self):
        ab = self.ab
        doc = copy.deepcopy(_load_fixture())
        # Shuffle wave array order and entry order: ordinal/position must win.
        doc["waves"].reverse()
        for wave in doc["waves"]:
            wave["entries"].reverse()
        lanes = ab.build_trail_lanes(doc, {}, "aitasks", lambda _id: None)
        ordinals = [lane.wave["ordinal"] for lane in lanes]
        self.assertEqual(ordinals, sorted(ordinals))
        for lane in lanes:
            positions = [v.entry["position"] for v in lane.entries]
            self.assertEqual(positions, sorted(positions))

    def test_entry_resolution_live_archived_missing_cross_repo(self):
        ab = self.ab
        doc = copy.deepcopy(_load_fixture())
        refs = sorted(ab.trail_entry_refs(doc))
        self.assertTrue(refs and all(r.startswith("aitasks#") for r in refs))
        live_id = refs[0].split("#", 1)[1]
        archived_id = refs[1].split("#", 1)[1]
        tasks_by_id = {live_id: self._mk_task(f"t{live_id}_live.md",
                                              status="Done")}
        archived_done = self._mk_task(f"t{archived_id}_arch.md", status="Done")

        def archived_lookup(task_id):
            return archived_done if task_id == archived_id else None

        lanes = ab.build_trail_lanes(doc, tasks_by_id, "aitasks",
                                     archived_lookup)
        views = [v for lane in lanes for v in lane.entries]
        by_ref = {str(v.entry["task"]): v for v in views}

        live = by_ref[f"aitasks#{live_id}"]
        self.assertIsNotNone(live.task)
        self.assertEqual(live.ghost_kind, "")
        self.assertTrue(live.landed)  # live status Done → strike-through

        arch = by_ref[f"aitasks#{archived_id}"]
        self.assertIsNone(arch.task)
        self.assertEqual(arch.ghost_kind, "archived")
        self.assertTrue(arch.landed)

        missing = [v for v in views if v.ghost_kind == "missing"]
        self.assertTrue(missing)  # every other ref has no live/archived task

        # Foreign project name → everything is a cross-repo ghost.
        foreign = ab.build_trail_lanes(doc, tasks_by_id, "otherproj",
                                       archived_lookup)
        for lane in foreign:
            for v in lane.entries:
                self.assertEqual(v.ghost_kind, "cross_repo")

        # Unknown local project name (unavailable config) → same, no crash.
        blank = ab.build_trail_lanes(doc, tasks_by_id, "", archived_lookup)
        for lane in blank:
            for v in lane.entries:
                self.assertEqual(v.ghost_kind, "cross_repo")

    def test_compute_trail_overlaps(self):
        ab = self.ab
        doc_a = copy.deepcopy(_load_fixture())
        shared_ref = sorted(ab.trail_entry_refs(doc_a))[0]
        doc_b = _ghost_doc()
        doc_b["title"] = "Other trail"
        doc_b["waves"][0]["entries"][0]["task"] = shared_ref
        info_a = ab.TrailInfo(handle="art:trail-a", owner_id="1",
                              owner_archived=False, owner_folded=False,
                              doc=doc_a)
        info_b = ab.TrailInfo(handle="art:trail-b", owner_id="2",
                              owner_archived=False, owner_folded=False,
                              doc=doc_b)
        overlaps = ab.compute_trail_overlaps([info_a, info_b])
        self.assertIn((shared_ref, "Other trail"), overlaps["art:trail-a"])
        self.assertIn((shared_ref, doc_a["title"]), overlaps["art:trail-b"])

    def test_fold_dedup_precedence(self):
        ab = self.ab

        def rec(owner, archived=False, folded=False, handle="art:trail-x"):
            return ab.TrailInfo(handle=handle, owner_id=owner,
                                owner_archived=archived, owner_folded=folded)

        # Active primary vs active folded owner (post-fold, pre-archival):
        # exactly one row, the non-folded primary wins — in both input orders.
        for records in ([rec("9"), rec("3", folded=True)],
                        [rec("3", folded=True), rec("9")]):
            deduped = ab.dedupe_trail_records(records)
            self.assertEqual(len(deduped), 1)
            self.assertEqual(deduped[0].owner_id, "9")
            self.assertFalse(deduped[0].owner_folded)

        # Active (even folded) beats archived.
        deduped = ab.dedupe_trail_records(
            [rec("5", archived=True), rec("7", folded=True)])
        self.assertEqual(deduped[0].owner_id, "7")

        # Same state → lowest owner id.
        deduped = ab.dedupe_trail_records([rec("12"), rec("4")])
        self.assertEqual(deduped[0].owner_id, "4")

        # Distinct handles both survive, first-seen order preserved.
        deduped = ab.dedupe_trail_records(
            [rec("1", handle="art:trail-b"), rec("2", handle="art:trail-a")])
        self.assertEqual([d.handle for d in deduped],
                         ["art:trail-b", "art:trail-a"])

    def test_drift_by_ref_grouping_and_trail_level_drop(self):
        """t1268: reasons are keyed on the RAW entry ref so ghosts match."""
        ab = self.ab
        reasons = [
            ("status_changed", "aitasks#1", "status 'Ready' -> 'Done'"),
            ("gate_state_changed", "aitasks#1", "pending gates now []"),
            ("task_completed", "otherproj#9", "completed and archived"),
            # Trail-level: no owning card.
            ("input_missing", "-", "plan input unreadable"),
            ("other", "", "unattributable digest mismatch"),
        ]
        by_ref = ab.trail_drift_by_ref(reasons)
        self.assertEqual(set(by_ref), {"aitasks#1", "otherproj#9"})
        self.assertEqual(len(by_ref["aitasks#1"]), 2)
        self.assertNotIn("-", by_ref)
        self.assertEqual(ab.trail_drift_by_ref([]), {})
        self.assertEqual(ab.trail_drift_by_ref(None), {})

    def test_drift_text_bounds_and_truncation(self):
        ab = self.ab
        self.assertEqual(ab._trail_drift_text([]), "")
        one = [("status_changed", "aitasks#1", "status 'Ready' -> 'Done'")]
        text = ab._trail_drift_text(one)
        self.assertIn("status_changed", text)
        self.assertIn("Done", text)
        self.assertNotIn("more", text)
        # Past max_shown, the remainder is summarised rather than dropped.
        many = [("c%d" % i, "aitasks#1", "d%d" % i) for i in range(5)]
        text = ab._trail_drift_text(many, max_shown=2)
        self.assertIn("c0", text)
        self.assertIn("c1", text)
        self.assertNotIn("c2", text)
        self.assertIn("(+3 more)", text)
        # A long detail is truncated, not wrapped into the card unbounded.
        long_one = [("plan_changed", "aitasks#1", "x" * 300)]
        text = ab._trail_drift_text(long_one, max_detail=20)
        self.assertLess(len(text), 80)
        self.assertIn("…", text)
        # Newlines in a detail can never break the single-line marker.
        multi = [("other", "aitasks#1", "line one\nline two")]
        self.assertNotIn("\n", ab._trail_drift_text(multi))

    def test_drift_matches_the_t_prefixed_ref_spelling(self):
        """The trail may store `aitasks#t42`; trail_gather always emits drift
        reasons against the canonical `aitasks#42` (its `inp.canonical`). Both
        sides must be keyed the same way or the owning card renders nothing."""
        ab = self.ab
        self.assertEqual(ab.canonical_trail_ref("aitasks#t42"), "aitasks#42")
        self.assertEqual(ab.canonical_trail_ref("aitasks#42"), "aitasks#42")
        self.assertEqual(ab.canonical_trail_ref("aitasks#t635_3"),
                         "aitasks#635_3")
        # Unparseable refs keep their raw text rather than vanishing.
        self.assertEqual(ab.canonical_trail_ref("garbage"), "garbage")
        self.assertEqual(ab.canonical_trail_ref(None), "")

        doc = _ghost_doc()
        doc["waves"][0]["entries"][0]["task"] = "aitasks#t42"   # tolerated
        task = self._mk_task("t42_demo.md")
        # …while the gatherer reports the canonical spelling.
        by_ref = ab.trail_drift_by_ref([
            ("status_changed", "aitasks#42", "status 'Ready' -> 'Implementing'"),
        ])
        lanes = ab.build_trail_lanes(
            doc, {"42": task}, "aitasks", lambda _id: None, by_ref)
        entry = lanes[0].entries[0]
        self.assertEqual(entry.ghost_kind, "", "t-prefixed ref did not resolve")
        self.assertEqual([r[0] for r in entry.drift_reasons],
                         ["status_changed"],
                         "drift reason did not attach to the t-spelled member")
        # And the mirror case: trail stores canonical, gatherer says `t`.
        doc2 = _ghost_doc()
        doc2["waves"][0]["entries"][0]["task"] = "aitasks#42"
        by_ref2 = ab.trail_drift_by_ref([
            ("status_changed", "aitasks#t42", "status 'Ready' -> 'Done'"),
        ])
        lanes2 = ab.build_trail_lanes(
            doc2, {"42": task}, "aitasks", lambda _id: None, by_ref2)
        self.assertEqual([r[0] for r in lanes2[0].entries[0].drift_reasons],
                         ["status_changed"])

    def test_build_trail_lanes_threads_drift_to_entries(self):
        """Ghost and live entries alike receive their own reasons."""
        ab = self.ab
        doc = _ghost_doc()
        doc["waves"][0]["entries"][0]["task"] = "aitasks#42"
        task = self._mk_task("t42_demo.md")
        by_ref = ab.trail_drift_by_ref([
            ("status_changed", "aitasks#42", "status 'Ready' -> 'Done'"),
            ("task_completed", "otherproj#2", "completed and archived"),
        ])
        lanes = ab.build_trail_lanes(
            doc, {"42": task}, "aitasks", lambda _id: None, by_ref)
        live = lanes[0].entries[0]
        ghost = lanes[1].entries[0]
        self.assertEqual(live.ghost_kind, "")
        self.assertEqual([r[0] for r in live.drift_reasons], ["status_changed"])
        self.assertEqual(ghost.ghost_kind, "cross_repo")
        self.assertEqual([r[0] for r in ghost.drift_reasons], ["task_completed"])
        # Omitting the map keeps every entry clean (back-compatible signature).
        lanes = ab.build_trail_lanes(
            doc, {"42": task}, "aitasks", lambda _id: None)
        self.assertEqual(lanes[0].entries[0].drift_reasons, [])


class TrailCardRenderTests(ByTrailTestBase):
    """Render-level assertions on the trail card widgets."""

    def _render_card(self, card, queries: dict) -> dict:
        from textual.app import App
        from textual.widgets import Label

        results = {}

        class CardApp(App):
            def compose(self):
                yield card

        async def go():
            app = CardApp()
            async with app.run_test(size=(90, 24)):
                for key, selector in queries.items():
                    label = card.query_one(selector, Label)
                    results[key] = label.render()

        self._run(go())
        return results

    def test_trail_task_card_badges_and_strike(self):
        ab = self.ab
        task = self._mk_task("t42_demo.md", status="Done")
        entry = {"task": "aitasks#42", "position": 1,
                 "classification": "hard_prerequisite", "confidence": "high"}
        view = ab.TrailEntryView(entry, task, "", landed=True)
        card = ab.TrailTaskCard(view, {"ordinal": 1}, None, "trail-w1")
        rendered = self._render_card(card, {
            "title": ".task-title",
            "badges": ".trail-badges",
            "ops": ".trail-ops",
        })
        self.assertIn("✔", rendered["title"].plain)
        self.assertIn("t42", rendered["title"].plain)
        self.assertTrue(any("strike" in str(span.style)
                            for span in rendered["title"].spans))
        self.assertEqual(rendered["badges"].plain if hasattr(
            rendered["badges"], "plain") else str(rendered["badges"]),
            "◆ hard_prerequisite · conf: high")
        # markup=False negative control: literal bracketed hints survive.
        ops = rendered["ops"]
        ops_text = ops.plain if hasattr(ops, "plain") else str(ops)
        self.assertIn("[enter details]", ops_text)

    def test_hint_line_names_only_card_scoped_keys(self):
        """t1268 AC6: the per-card hint must not contradict the footer.

        `r` and `s` are view-scoped and now carry truthful By-Trail labels in
        the footer; `s` in particular used to read "select" on the card while
        the footer said "Sync"."""
        ab = self.ab
        task = self._mk_task("t42_demo.md")
        entry = {"task": "aitasks#42", "position": 1,
                 "classification": "core", "confidence": "high"}
        view = ab.TrailEntryView(entry, task, "", landed=False)
        card = ab.TrailTaskCard(view, {"ordinal": 1}, None, "trail-w1")
        rendered = self._render_card(card, {"ops": ".trail-ops"})
        ops = rendered["ops"]
        ops_text = ops.plain if hasattr(ops, "plain") else str(ops)
        self.assertIn("[enter details]", ops_text)
        self.assertNotIn("refresh", ops_text)
        self.assertNotIn("select", ops_text)

    def test_drift_marker_renders_code_and_detail(self):
        """t1268 AC3: the owning card shows the reason, detail included."""
        ab = self.ab
        task = self._mk_task("t42_demo.md")
        entry = {"task": "aitasks#42", "position": 1,
                 "classification": "core", "confidence": "high"}
        reasons = [("status_changed", "aitasks#42",
                    "status 'Ready' -> 'Implementing'")]
        view = ab.TrailEntryView(entry, task, "", False, reasons)
        card = ab.TrailTaskCard(view, {"ordinal": 1}, None, "trail-w1")
        rendered = self._render_card(card, {"drift": ".trail-drift"})
        drift = rendered["drift"]
        text = drift.plain if hasattr(drift, "plain") else str(drift)
        self.assertIn("status_changed", text)
        # The detail is what makes the marker actionable — not codes alone.
        self.assertIn("Implementing", text)

    def test_ghost_card_renders_its_own_drift_marker(self):
        """t1268 AC3: a drift reason may name an archived / cross-repo member."""
        ab = self.ab
        entry = {"task": "otherproj#7", "position": 1,
                 "classification": "optional", "confidence": "low"}
        reasons = [("task_completed", "otherproj#7",
                    "otherproj#7 completed and archived")]
        view = ab.TrailEntryView(entry, None, "cross_repo", False, reasons)
        card = ab.TrailGhostCard(view, {"ordinal": 1}, "trail-w1")
        rendered = self._render_card(card, {"drift": ".trail-drift"})
        drift = rendered["drift"]
        text = drift.plain if hasattr(drift, "plain") else str(drift)
        self.assertIn("task_completed", text)

    def test_no_drift_marker_when_entry_is_clean(self):
        ab = self.ab
        task = self._mk_task("t42_demo.md")
        entry = {"task": "aitasks#42", "position": 1,
                 "classification": "core", "confidence": "high"}
        view = ab.TrailEntryView(entry, task, "", landed=False)
        card = ab.TrailTaskCard(view, {"ordinal": 1}, None, "trail-w1")
        from textual.app import App

        found = {}

        class CardApp(App):
            def compose(self):
                yield card

        async def go():
            app = CardApp()
            async with app.run_test(size=(90, 24)):
                found["n"] = len(card.query(".trail-drift"))

        self._run(go())
        self.assertEqual(found["n"], 0)

    def test_ghost_card_kind_and_badges(self):
        ab = self.ab
        entry = {"task": "otherproj#7", "position": 1,
                 "classification": "optional", "confidence": "low"}
        view = ab.TrailEntryView(entry, None, "cross_repo", landed=False)
        card = ab.TrailGhostCard(view, {"ordinal": 1}, "trail-w1")
        rendered = self._render_card(card, {
            "title": ".task-title",
            "info": ".task-info",
        })
        self.assertIn("otherproj#7", rendered["title"].plain)
        info = rendered["info"]
        info_text = info.plain if hasattr(info, "plain") else str(info)
        self.assertIn("cross-repo member", info_text)
        self.assertIn("read-only", info_text)
        self.assertTrue(card.is_ghost)
        # Stable refocus key + defensively complete stub.
        self.assertTrue(card.task_data.filename.startswith("trail-ghost-"))
        self.assertEqual(card.task_data.metadata, {})
        self.assertIsInstance(card.task_data.filepath, Path)


class ByTrailPilotTests(ByTrailTestBase):
    """Live-tree Pilot tests for view switch, gating, and navigation."""

    def test_z_enters_bytrail_empty_state(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                # The live repo has no artifacts: frontmatter — that IS the
                # no-trails fixture. Stub discovery so the worker is instant.
                with patch.object(ab, "discover_trails",
                                  lambda: ([], [])):
                    await pilot.press("z")
                    await pilot.pause()
                    await pilot.pause()
                    self.assertEqual(app.base_filter, "bytrail")
                    # Give the thread worker time to land its callback.
                    for _ in range(20):
                        if app._trail_infos is not None:
                            break
                        await asyncio.sleep(0.05)
                        await pilot.pause()
                    self.assertEqual(app._trail_infos, [])
                # The discovery busy overlay must not linger once the scan
                # callback has landed.
                self.assertNotIsInstance(app.screen, ab.LoadingOverlay)
                empties = list(app.query(".trail-empty"))
                self.assertTrue(empties)

        self._run(go())

    def test_archived_owner_noted_on_banner(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                archived_info = ab.TrailInfo(
                    handle="art:trail-arch", owner_id="99",
                    owner_archived=True, owner_folded=False,
                    doc=_ghost_doc())
                active_info = ab.TrailInfo(
                    handle="art:trail-test", owner_id="7",
                    owner_archived=False, owner_folded=False,
                    doc=_ghost_doc())
                app._trail_infos = [archived_info, active_info]
                # §9.2: selecting an archived-owned trail notes it on the
                # banner; a live-owned trail does not.
                app._activate_trail("art:trail-arch")
                await pilot.pause()
                self.assertIn("owner t99 archived", str(app.sub_title))
                app._activate_trail("art:trail-test")
                await pilot.pause()
                self.assertNotIn("archived", str(app.sub_title))

        self._run(go())

    def test_footer_gating_in_bytrail(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                hidden = ("move_task_right", "move_task_left", "move_task_up",
                          "move_task_down", "move_col_right", "move_col_left",
                          "toggle_column_collapsed", "toggle_children",
                          "work_report", "sort_topic", "trail_task",
                          # t1268: `C` is repo-wide, and the generic `r`/`s`
                          # yield their keys to the By-Trail actions.
                          "commit_all", "refresh_board", "sync_remote")
                actions = self._footer_actions(app)
                for action in hidden:
                    self.assertIs(app.check_action(action, None), False,
                                  f"{action} must be hidden in bytrail")
                    self.assertNotIn(action, actions)

        self._run(go())

    def test_trail_task_gate_per_view(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                cards = list(app.query(ab.TaskCard))
                self.assertTrue(cards, "fixture tree rendered no task cards")
                cards[0].focus()
                await pilot.pause()
                self.assertTrue(app.check_action("trail_task", None))
                self.assertIn("trail_task", self._footer_actions(app))
                app.base_filter = "inflight"
                self.assertIs(app.check_action("trail_task", None), False)
                app.base_filter = "bytrail"
                self.assertIs(app.check_action("trail_task", None), False)

        self._run(go())

    def test_ghost_navigation_and_detail(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(220, 60)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                cols = list(app.query(ab.TrailColumn))
                self.assertEqual(len(cols), 2)
                self.assertEqual(app._get_visible_col_ids(),
                                 ["trail-w1", "trail-w2"])
                # Keyboard reaches the ghost-only column.
                app.action_focus_board()
                await pilot.pause()
                focused = app._focused_card()
                self.assertIsNotNone(focused)
                self.assertTrue(getattr(focused, "is_ghost", False))
                self.assertEqual(focused.column_id, "trail-w1")
                # Lateral nav crosses into the second ghost-only wave.
                await pilot.press("right")
                await pilot.pause()
                focused = app._focused_card()
                self.assertEqual(focused.column_id, "trail-w2")
                # Enter on a focused ghost opens the trail detail modal.
                await pilot.press("enter")
                await pilot.pause()
                self.assertIsInstance(app.screen, ab.TrailDetailScreen)
                await pilot.press("escape")
                await pilot.pause()

        self._run(go())

    def test_focused_ghost_footer_regression(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(220, 60)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                app.action_focus_board()
                await pilot.pause()
                focused = app._focused_card()
                self.assertTrue(getattr(focused, "is_ghost", False))
                # Footer evaluation drives check_action across ALL bindings —
                # must not raise with a ghost focused.
                actions = self._footer_actions(app)
                for action in ("commit_selected", "pick_task",
                               "brainstorm_task", "open_cross_repo",
                               "toggle_children", "trail_task"):
                    self.assertIs(app.check_action(action, None), False)
                    self.assertNotIn(action, actions)
                self.assertIn("view_details", actions)

        self._run(go())

    def test_subtitle_restore_on_view_exit(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                baseline = app.sub_title
                self.assertTrue(str(baseline).startswith("Auto-refresh:"))
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                self.assertIn("By-Trail:", str(app.sub_title))
                self.assertIn("Ghost trail", str(app.sub_title))
                await pilot.press("a")
                await pilot.pause()
                self.assertEqual(str(app.sub_title), str(baseline))

        self._run(go())

    # --- Trail-selection modal: focus visibility + overflow (t1366) ---------
    #
    # All four assert at RENDER level (the composited frame), never on
    # `.classes` or `app.focused`. That distinction is the whole defect: before
    # the fix, `down` moved focus AND applied `dep-item-focused` while the frame
    # stayed byte-identical, so a property-level test passed against code the
    # user experienced as completely dead.

    def test_trail_select_focus_is_visible_in_frame(self):
        """A `down` press must CHANGE the composited frame (t1366).

        Also pins the multi-line half of the fix: the shared focus rule cannot
        assume `height: 1`, so a row carrying "also references" sub-lines must
        still render every line while focused.
        """
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                infos = [self._mk_trail_info(f"art:t{i}",
                                             f"Trail number {i:02d} long title")
                         for i in range(3)]
                overlaps = {"art:t0": [("t42", "Another trail")]}
                app.push_screen(ab.TrailSelectScreen(infos, overlaps))
                await self._settle(pilot)
                items = list(app.screen.query(ab.TrailSelectItem))
                self.assertEqual(len(items), 3)

                before = self._screen_rows(app)
                await pilot.press("down")
                await self._settle(pilot)

                # Focus really moved — otherwise a frame change would prove
                # nothing about the highlight.
                self.assertTrue(items[1].has_focus)
                self.assertNotEqual(
                    before, self._screen_rows(app),
                    "focus moved but the composited frame is unchanged: the "
                    "highlight never reaches the terminal")

                # Ground truth for "visibly distinct": the focused row's
                # background differs from an unfocused sibling's, and blurring
                # restores it.
                idle = items[0].styles.background
                self.assertNotEqual(
                    items[1].styles.background, idle,
                    "focused row shares the unfocused background")
                items[0].focus()
                await self._settle(pilot)
                self.assertEqual(items[1].styles.background, idle,
                                 "blurring must restore the idle background")

                # Multi-line row renders fully (no `height: 1` assumption).
                dialog = app.screen.query_one("#dep_picker_dialog")
                self.assertIn("also references",
                              self._dialog_text(app, dialog))

        self._run(go())

    def test_trail_select_dialog_scrolls_and_cancel_is_reachable(self):
        """No focusable widget may sit outside the rendered region (t1366).

        Pre-fix the dialog was a plain non-scrolling `Container`, so with enough
        trails the tail of the list and the Cancel button were focusable but
        unreachable — arrow keys wrapped through invisible rows.
        """
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                infos = [self._mk_trail_info(f"art:t{i}",
                                             f"Trail number {i:02d} long title")
                         for i in range(10)]
                app.push_screen(ab.TrailSelectScreen(infos, {}))
                await self._settle(pilot)

                dialog = app.screen.query_one("#dep_picker_dialog")
                self.assertTrue(
                    dialog.allow_vertical_scroll,
                    "dialog content overflows but the container cannot scroll")

                items = list(app.screen.query(ab.TrailSelectItem))
                items[-1].focus()
                await self._settle(pilot)
                self.assertTrue(
                    app.screen.can_view_entire(items[-1]),
                    "focusing the last row did not scroll it into view")

                cancel = app.screen.query_one("#btn_dep_cancel")
                cancel.focus()
                await self._settle(pilot)
                self.assertTrue(app.screen.can_view_entire(cancel),
                                "Cancel button is focusable but off-screen")
                self.assertIn("Cancel", self._dialog_text(app, dialog))

        self._run(go())

    def test_trail_select_hint_fits_80_cols(self):
        """The hint names the arrow keys and is not truncated at 80 cols.

        `Label` defaults to `width: auto`, so the hint used to overflow the
        dialog's 42-column content box and clip mid-word to "Esc to c" — while
        never mentioning the keys that actually move the selection.
        """
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                infos = [self._mk_trail_info(f"art:t{i}", f"Trail {i:02d}")
                         for i in range(10)]
                app.push_screen(ab.TrailSelectScreen(infos, {}))
                await self._settle(pilot)

                dialog = app.screen.query_one("#dep_picker_dialog")
                self.assertIn(
                    "Select trail — ↑/↓ move · Enter open · Esc cancel",
                    self._dialog_text(app, dialog),
                    "hint is truncated or does not mention ↑/↓ at 80 columns")

                # Still legible once the list has scrolled under it.
                await pilot.press("down")
                await pilot.press("down")
                await self._settle(pilot)
                self.assertIn("↑/↓ move", self._dialog_text(app, dialog),
                              "hint scrolled out of view")

        self._run(go())

    def test_gate_choice_focus_is_visible_in_frame(self):
        """The fix landed at the shared sink, not on the trail path (t1366).

        `GateChoiceScreen` is a sibling picker built on the same
        `#dep_picker_dialog` container and the same `dep-item-focused` class;
        it was equally unstyled before the fix.
        """
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                app.push_screen(ab.GateChoiceScreen(
                    "t9001", ["plan_approved", "review_approved"], "sign off"))
                await self._settle(pilot)
                items = list(app.screen.query(ab.GateChoiceItem))
                self.assertEqual(len(items), 2)

                before = self._screen_rows(app)
                await pilot.press("down")
                await self._settle(pilot)
                self.assertTrue(items[1].has_focus)
                self.assertNotEqual(
                    before, self._screen_rows(app),
                    "sibling picker still has an invisible focus highlight")

        self._run(go())


class RefreshSplitAndSupersessionTests(ByTrailTestBase):
    """Keyboard-vs-timer refresh split and worker supersession guards."""

    def test_auto_refresh_tick_never_launches_in_bytrail(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                app.manager.settings = dict(app.manager.settings,
                                            sync_on_refresh=False)
                calls = {"data": 0, "local": 0}
                launches = []
                app._refresh_board_data = (
                    lambda: calls.__setitem__("data", calls["data"] + 1))
                real_local = app.action_trail_refresh_local
                app.action_trail_refresh_local = (
                    lambda: calls.__setitem__("local", calls["local"] + 1))
                app._launch_trail = (
                    lambda args, suffix, watch_handle="", **_kw:
                        launches.append(list(args)))
                # Timer tick → passive data refresh, no dialog.
                app._auto_refresh_tick()
                self.assertEqual(calls["data"], 1)
                self.assertEqual(launches, [])
                # `r` in By-Trail is the LOCAL recompute (t1268) — it must not
                # launch an agent, and it no longer routes through
                # _refresh_board_data (which spawns git/lock subprocesses).
                app.action_trail_refresh_local()
                self.assertEqual(calls["local"], 1)
                self.assertEqual(calls["data"], 1)
                self.assertEqual(launches, [])
                app.action_trail_refresh_local = real_local
                # Only the dedicated agent key launches.
                app.action_trail_refresh_agent()
                self.assertEqual(calls["data"], 1)
                self.assertEqual(launches,
                                 [["--refresh", "art:trail-test"]])

        self._run(go())

    def test_stale_drift_result_discarded(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                subtitle = str(app.sub_title)
                # Stale generation token → discarded.
                app._on_trail_drift(app._trail_gen - 1, "art:trail-test",
                                    "STALE", [("status_changed", "-", "d")])
                self.assertIsNone(app._trail_drift)
                self.assertEqual(str(app.sub_title), subtitle)
                # Different handle (trail switched mid-check) → discarded.
                app._on_trail_drift(app._trail_gen, "art:trail-other",
                                    "STALE", [])
                self.assertIsNone(app._trail_drift)
                # Fresh token + matching handle → applied.
                app._on_trail_drift(app._trail_gen, "art:trail-test",
                                    "STALE", [("status_changed", "-", "d")])
                self.assertEqual(app._trail_drift[0], "STALE")
                self.assertIn("⚠ stale: 1", str(app.sub_title))
                # After leaving the view, a late result must not mutate state.
                app._set_base_filter("all")
                await pilot.pause()
                drift_before = app._trail_drift
                app._on_trail_drift(app._trail_gen, "art:trail-test",
                                    "CURRENT", [])
                self.assertEqual(app._trail_drift, drift_before)

        self._run(go())


class TrailLaunchConstructionTests(ByTrailTestBase):
    """Construction spies on the agent-launch seam (no real screens/agents)."""

    def _spy_launch(self, app):
        ab = self.ab
        calls = []

        class FakeScreen:
            def __init__(self, title, full_command, prompt_str, **kwargs):
                calls.append({"title": title, "full_command": full_command,
                              "prompt_str": prompt_str, **kwargs})
                self.full_command = full_command

        patches = [
            patch.object(ab, "AgentCommandScreen", FakeScreen),
            patch.object(ab, "resolve_dry_run_command",
                         lambda root, op, *args, **kw: f"CMD {op}"),
            patch.object(ab, "resolve_agent_string",
                         lambda root, op: "claudecode/test"),
            patch.object(app, "push_screen", lambda screen, cb=None: None),
        ]
        return calls, patches

    def test_trail_task_launch_args(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                cards = list(app.query(ab.TaskCard))
                self.assertTrue(cards, "fixture tree rendered no task cards")
                cards[0].focus()
                await pilot.pause()
                task_num, _ = ab.TaskCard._parse_filename(
                    cards[0].task_data.filename)
                num = task_num.lstrip("t")
                calls, patches = self._spy_launch(app)
                with patches[0], patches[1], patches[2], patches[3]:
                    app.action_trail_task()
                self.assertEqual(len(calls), 1)
                call = calls[0]
                self.assertEqual(call["operation"], "trail")
                self.assertEqual(call["operation_args"], [num])
                self.assertEqual(call["skill_name"], "trail")
                self.assertEqual(call["default_window_name"],
                                 f"agent-trail-{num}")
                self.assertEqual(call["prompt_str"], f"/aitask-trail {num}")

        self._run(go())

    def test_refresh_launch_args(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(
                    app, pilot, _ghost_doc(), handle="art:trail-demo")
                calls, patches = self._spy_launch(app)
                with patches[0], patches[1], patches[2], patches[3]:
                    # The agent refresh lives on its own key (t1268).
                    app.action_trail_refresh_agent()
                self.assertEqual(len(calls), 1)
                call = calls[0]
                self.assertEqual(call["operation"], "trail")
                self.assertEqual(call["operation_args"],
                                 ["--refresh", "art:trail-demo"])
                self.assertEqual(call["default_window_name"],
                                 "agent-trail-trail-demo")
                self.assertEqual(call["prompt_str"],
                                 "/aitask-trail --refresh art:trail-demo")
                # The local refresh key launches nothing.
                with patches[0], patches[1], patches[2], patches[3]:
                    app.action_trail_refresh_local()
                self.assertEqual(len(calls), 1)

        self._run(go())


class ReadOnlyNegativeControlTests(ByTrailTestBase):
    """The board's trail plumbing only ever spawns read verbs and never
    modifies the artifact bytes (RFC §8.2 passive observation)."""

    def test_load_and_drift_spawn_only_read_verbs(self):
        ab = self.ab
        fixture_bytes = FIXTURE_PATH.read_bytes()
        seen: list[list[str]] = []

        def fake_run(argv, **kwargs):
            argv = [str(a) for a in argv]
            seen.append(argv)
            if argv[0].endswith("aitask_artifact.sh") and argv[1] == "get":
                out = argv[argv.index("--out") + 1]
                Path(out).write_bytes(fixture_bytes)
                return subprocess.CompletedProcess(argv, 0, "", "")
            if argv[0].endswith("aitask_trail_gather.sh"):
                return subprocess.CompletedProcess(
                    argv, 0, "CURRENT\nDIGEST:abcdef0123456789\n", "")
            return subprocess.CompletedProcess(argv, 0, "", "")

        with patch("subprocess.run", side_effect=fake_run):
            doc, error, versions = ab.load_trail_blob("art:trail-x")
            verdict, reasons = ab.run_trail_drift("art:trail-x")

        self.assertEqual(error, "")
        self.assertIsNotNone(doc)
        self.assertEqual(verdict, "CURRENT")
        self.assertEqual(reasons, [])
        self.assertTrue(seen)
        for argv in seen:
            script = Path(argv[0]).name
            verb = argv[1] if len(argv) > 1 else ""
            self.assertIn(
                (script, verb),
                {("aitask_artifact.sh", "get"),
                 ("aitask_artifact.sh", "versions"),
                 ("aitask_trail_gather.sh", "drift")},
                f"unexpected subprocess: {argv}")
        # The fixture on disk is untouched.
        self.assertEqual(FIXTURE_PATH.read_bytes(), fixture_bytes)

    def test_load_failure_is_fail_closed_with_versions_fallback(self):
        ab = self.ab

        def fake_run(argv, **kwargs):
            argv = [str(a) for a in argv]
            if argv[0].endswith("aitask_artifact.sh") and argv[1] == "get":
                return subprocess.CompletedProcess(
                    argv, 1, "", "Error: no manifest for art:trail-x\n")
            if argv[0].endswith("aitask_artifact.sh") and argv[1] == "versions":
                return subprocess.CompletedProcess(
                    argv, 0, "* sha256:abc 2026-07-01\n", "")
            return subprocess.CompletedProcess(argv, 0, "", "")

        with patch("subprocess.run", side_effect=fake_run):
            doc, error, versions = ab.load_trail_blob("art:trail-x")
        self.assertIsNone(doc)
        self.assertIn("artifact unresolved", error)
        self.assertEqual(versions, ["* sha256:abc 2026-07-01"])

    def test_invalid_document_is_fail_closed(self):
        ab = self.ab

        def fake_run(argv, **kwargs):
            argv = [str(a) for a in argv]
            if argv[0].endswith("aitask_artifact.sh") and argv[1] == "get":
                out = argv[argv.index("--out") + 1]
                Path(out).write_text('{"schema_version": "0.0.1"}')
                return subprocess.CompletedProcess(argv, 0, "", "")
            return subprocess.CompletedProcess(argv, 0, "", "")

        with patch("subprocess.run", side_effect=fake_run):
            doc, error, versions = ab.load_trail_blob("art:trail-x")
        self.assertIsNone(doc)
        self.assertIn("invalid trail document", error)

    def test_error_state_renders_error_card_with_fallback(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                app.active_trail_handle = "art:trail-broken"
                app._trail_infos = []
                app._trail_doc = None
                app._trail_error = "artifact unresolved: no manifest"
                app._trail_versions_fallback = ["* sha256:abc 2026-07-01"]
                app._start_trail_drift = lambda: None
                app._set_base_filter("bytrail")
                await pilot.pause()
                await pilot.pause()
                errors = list(app.query(".trail-error"))
                self.assertTrue(errors)
                text = str(errors[0].render())
                self.assertIn("fail-closed", text)
                self.assertIn("artifact unresolved", text)
                self.assertIn("sha256:abc", text)
                self.assertIn("trail unavailable", str(app.sub_title))

        self._run(go())


class LocalRefreshTests(ByTrailTestBase):
    """t1268: `r` in By-Trail is a zero-subprocess local recompute."""

    def test_local_refresh_spawns_no_subprocess(self):
        """Negative control — the REAL action, nothing stubbed.

        Discrimination: routing this action through _refresh_board_data (the
        generic refresh_board path) makes `git status` and aitask_lock.sh
        appear in `seen` and fails this test.
        """
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                launches = []
                app._launch_trail = (
                    lambda args, suffix, watch_handle="", **_kw:
                        launches.append(list(args)))
                seen = []

                def fake_run(argv, **kwargs):
                    seen.append([str(a) for a in argv])
                    return subprocess.CompletedProcess(argv, 0, "", "")

                # Patch AFTER mount/view-entry so only the action is measured.
                with patch("subprocess.run", side_effect=fake_run):
                    app.action_trail_refresh_local()
                    await pilot.pause()
                    await pilot.pause()
                self.assertEqual(seen, [], f"unexpected subprocess: {seen}")
                self.assertEqual(launches, [])

        self._run(go())

    def test_drift_callback_spawns_no_subprocess(self):
        """The async drift callback must not re-enter the git/lock path."""
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                seen = []

                def fake_run(argv, **kwargs):
                    seen.append([str(a) for a in argv])
                    return subprocess.CompletedProcess(argv, 0, "", "")

                reasons = [("task_completed", "otherproj#1",
                            "otherproj#1 completed and archived")]
                with patch("subprocess.run", side_effect=fake_run):
                    app._on_trail_drift(app._trail_gen, "art:trail-test",
                                        "STALE", reasons)
                    await pilot.pause()
                    await pilot.pause()
                self.assertEqual(seen, [], f"unexpected subprocess: {seen}")
                # The marker reached the owning ghost card.
                markers = [str(w.render()) for w in app.query(".trail-drift")]
                self.assertTrue(any("task_completed" in m for m in markers),
                                f"no drift marker rendered: {markers}")

        self._run(go())


class OnDiskRefreshTests(unittest.TestCase):
    """t1268 AC1: `r` picks up a frontmatter status changed ON DISK.

    Uses the TASK_DIR seam (config_utils.task_dir) so the board resolves its
    module-load constants against a temp tree — the same idiom as
    tests/test_board_archived_relation_lookup.py.
    """

    #: Its own single-task tree: this test MUTATES the task file mid-run, so it
    #: cannot share the class-level fixture other classes reuse.
    TASKS = (bf.FixtureTask(task_id="42", col="c0", idx=10, slug="demo",
                            extra={"issue_type": "bug"}),)

    def setUp(self):
        self.tree, self._board = bf.enter_fixture_tree(
            self.addCleanup, tasks_spec=self.TASKS, tag="ondisk")
        self.task_dir = self.tree / "aitasks"

    def _write_task(self, status: str):
        (self.task_dir / "t42_demo.md").write_text(
            f"---\npriority: medium\neffort: low\nstatus: {status}\n"
            "issue_type: bug\n---\n\n## Demo\n\nbody\n",
            encoding="utf-8")

    def _load_board(self):
        return self._board

    def _doc(self):
        return {
            "title": "Disk trail", "trail_id": "trail-disk",
            "narrative": {"problem_statement": "p",
                          "recommendation_summary": "r"},
            "waves": [{
                "wave_id": "w1", "ordinal": 1, "title": "Wave 1",
                "purpose": "p", "entries": [{
                    "entry_id": "e1", "task": "aitasks#42", "topic": "aitasks#42",
                    "position": 1, "classification": "core",
                    "confidence": "high", "rationale": "r",
                    "snapshot": {"status": "Ready"},
                }],
            }],
        }

    def test_local_refresh_picks_up_on_disk_status_change(self):
        """Discrimination: dropping manager.load_tasks() from the action
        makes this fail — the in-memory Task would still say Ready."""
        self._write_task("Ready")
        ab = self._load_board()

        def statuses(app):
            return [str(w.render()) for w in app.query(".task-info")]

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                app.active_trail_handle = "art:trail-disk"
                app._trail_infos = []
                app._trail_doc = self._doc()
                app._trail_error = ""
                app._start_trail_drift = lambda: None
                app._set_base_filter("bytrail")
                await pilot.pause()
                await pilot.pause()
                cards = list(app.query(ab.TrailTaskCard))
                self.assertEqual(len(cards), 1,
                                 "trail member did not resolve to a live card")
                self.assertTrue(any("📋 Ready" in s for s in statuses(app)),
                                statuses(app))

                # Change the status ON DISK, exactly as another agent would.
                self._write_task("Implementing")

                app.action_trail_refresh_local()
                await pilot.pause()
                await pilot.pause()
                after = statuses(app)
                self.assertTrue(any("📋 Implementing" in s for s in after),
                                after)
                self.assertFalse(any("📋 Ready" in s for s in after), after)

        asyncio.run(go())


class BindingContractTests(ByTrailTestBase):
    """t1268 AC6: per-view footer labels via duplicate-key bindings."""

    @staticmethod
    def _labels(app) -> dict:
        return {
            active.binding.action: active.binding.description
            for active in app.screen.active_bindings.values()
        }

    def test_bytrail_footer_labels(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                # Default view: the generic pair owns r/s.
                labels = self._labels(app)
                self.assertEqual(labels.get("refresh_board"), "Refresh")
                self.assertEqual(labels.get("sync_remote"), "Sync")
                for action in ("trail_refresh_local", "trail_refresh_drift",
                               "trail_refresh_agent", "trail_select",
                               "trail_sync"):
                    self.assertNotIn(action, labels)

                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                labels = self._labels(app)
                # The By-Trail half takes over, each with a truthful label.
                self.assertEqual(labels.get("trail_refresh_local"), "Refresh")
                self.assertEqual(labels.get("trail_refresh_drift"), "Freshness")
                self.assertEqual(labels.get("trail_refresh_agent"),
                                 "Agent Refresh")
                self.assertEqual(labels.get("trail_select"), "Select Trail")
                self.assertEqual(labels.get("trail_sync"), "Sync")
                for action in ("refresh_board", "sync_remote", "commit_all"):
                    self.assertNotIn(action, labels)

        self._run(go())

    def test_duplicate_key_dispatch_falls_through(self):
        """The one Textual-internal behaviour this design depends on.

        A repeated key must dispatch to whichever binding check_action leaves
        enabled. If a future Textual changes duplicate-key resolution, this
        test finds out — not a user pressing `r` and launching an agent.
        """
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                fired = []
                for name in ("action_refresh_board", "action_sync_remote",
                             "action_trail_refresh_local",
                             "action_trail_select"):
                    setattr(app, name,
                            (lambda n=name: fired.append(n)))

                # Default view → the generic actions.
                await pilot.press("r")
                await pilot.pause()
                self.assertEqual(fired, ["action_refresh_board"])
                fired.clear()
                await pilot.press("s")
                await pilot.pause()
                self.assertEqual(fired, ["action_sync_remote"])
                fired.clear()

                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                # By-Trail → the trail actions, same keys.
                await pilot.press("r")
                await pilot.pause()
                self.assertEqual(fired, ["action_trail_refresh_local"])
                fired.clear()
                await pilot.press("s")
                await pilot.pause()
                self.assertEqual(fired, ["action_trail_select"])

        self._run(go())

    def test_commit_all_hidden_in_bytrail_even_when_modified(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                # Force a non-empty modified set so the generic guard passes.
                app.manager.get_modified_tasks = lambda: [object()]
                self.assertIsNot(app.check_action("commit_all", None), False)
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                self.assertIs(app.check_action("commit_all", None), False)

        self._run(go())


class TrailWatchTests(ByTrailTestBase):
    """t1268 AC5: the artifact-version watch that picks up an agent refresh
    which finished long after its launch dialog closed."""

    def _capture_launch(self, app):
        """Capture _launch_trail's result callback without creating a screen."""
        ab = self.ab
        box = {}

        class FakeScreen:
            def __init__(self, title, full_command, prompt_str, **kwargs):
                self.full_command = full_command

        patches = [
            patch.object(ab, "AgentCommandScreen", FakeScreen),
            patch.object(ab, "resolve_dry_run_command",
                         lambda root, op, *a, **k: f"CMD {op}"),
            patch.object(ab, "resolve_agent_string",
                         lambda root, op: "claudecode/test"),
            patch.object(app, "push_screen",
                         lambda screen, cb=None: box.__setitem__("cb", cb)),
        ]
        return box, patches

    def _launch_env(self, app, versions, tmux_result=(123, None)):
        """Patch every outward call the result callback can make."""
        ab = self.ab
        events = []

        class FakeTmux:
            new_window = True
            session = "s"
            window = "w"

        patches = [
            patch.object(ab, "_trail_versions",
                         lambda h: (events.append("versions"), versions)[1]),
            patch.object(app, "run_dialog_command",
                         lambda cmd: events.append("run")),
            # The baseline read is normally a thread worker; run it inline so
            # the launch sequence is deterministic. The REAL worker boundary
            # is exercised by ThreadWorkerTests.
            patch.object(ab, "launch_in_tmux",
                         lambda cmd, cfg: (events.append("tmux"),
                                           tmux_result)[1]),
            patch.object(ab, "maybe_spawn_minimonitor", lambda s, w: None),
            patch.object(ab, "TmuxLaunchConfig", FakeTmux),
            patch.object(app, "_reload_active_trail",
                         lambda: events.append("reload")),
            patch.object(app, "notify", lambda *a, **k: events.append("notify")),
            patch.object(app, "_trail_baseline_worker",
                         lambda handle, then: then(ab._trail_versions(handle))),
        ]
        return events, patches, FakeTmux

    async def _get_callback(self, app, pilot):
        box, patches = self._capture_launch(app)
        with patches[0], patches[1], patches[2], patches[3]:
            app.action_trail_refresh_agent()
        await pilot.pause()
        return box["cb"]

    def _watch_state(self, app):
        return (app._trail_watch_handle, app._trail_watch_baseline,
                app._trail_watch_timer)

    # --- launch lifecycle -------------------------------------------------

    def test_opening_dialog_installs_no_watch(self):
        """Baseline is NOT captured while the confirmation dialog is open."""
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                seen = []
                with patch.object(ab, "_trail_versions",
                                  lambda h: (seen.append(h), ["v1"])[1]):
                    await self._get_callback(app, pilot)
                self.assertEqual(seen, [])
                self.assertIsNone(app._trail_watch_timer)

        self._run(go())

    def test_run_result_captures_baseline_before_launch(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                cb = await self._get_callback(app, pilot)
                events, patches, _ = self._launch_env(app, ["v1"])
                with patches[0], patches[1], patches[2], patches[3], \
                        patches[4], patches[5], patches[6], patches[7]:
                    cb("run")
                # Baseline read BEFORE the agent could possibly write.
                self.assertEqual(events[:2], ["versions", "run"])
                self.assertEqual(app._trail_watch_handle, "art:trail-test")
                self.assertEqual(app._trail_watch_baseline, ["v1"])
                self.assertIsNotNone(app._trail_watch_timer)
                app._stop_trail_watch()

        self._run(go())

    def test_tmux_success_installs_watch(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                cb = await self._get_callback(app, pilot)
                events, patches, FakeTmux = self._launch_env(app, ["v1"])
                with patches[0], patches[1], patches[2], patches[3], \
                        patches[4], patches[5], patches[6], patches[7]:
                    cb(FakeTmux())
                self.assertEqual(events[:2], ["versions", "tmux"])
                self.assertEqual(app._trail_watch_baseline, ["v1"])
                self.assertIsNotNone(app._trail_watch_timer)
                app._stop_trail_watch()

        self._run(go())

    def test_tmux_failure_installs_no_watch_and_does_not_reload(self):
        """A failed launch must not leave an orphan poller, nor re-fetch."""
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                # An earlier refresh is already being watched.
                app._install_trail_watch("art:trail-test", ["old"])
                before = self._watch_state(app)
                cb = await self._get_callback(app, pilot)
                events, patches, FakeTmux = self._launch_env(
                    app, ["new"], tmux_result=(None, "boom"))
                with patches[0], patches[1], patches[2], patches[3], \
                        patches[4], patches[5], patches[6], patches[7]:
                    cb(FakeTmux())
                self.assertIn("notify", events)
                self.assertNotIn("reload", events)
                self.assertEqual(self._watch_state(app), before)
                app._stop_trail_watch()

        self._run(go())

    def test_cancel_preserves_existing_watch_and_skips_reload(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                app._install_trail_watch("art:trail-test", ["old"])
                before = self._watch_state(app)
                cb = await self._get_callback(app, pilot)
                events, patches, _ = self._launch_env(app, ["new"])
                with patches[0], patches[1], patches[2], patches[3], \
                        patches[4], patches[5], patches[6], patches[7]:
                    cb(None)
                self.assertNotIn("reload", events)
                self.assertEqual(self._watch_state(app), before,
                                 "cancelling a dialog killed an unrelated "
                                 "in-flight agent's watch")
                app._stop_trail_watch()

        self._run(go())

    def test_failed_baseline_preserves_active_watcher(self):
        """Negative control for teardown-before-validate ordering."""
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                app._install_trail_watch("art:trail-test", ["old"])
                before = self._watch_state(app)
                stops = []
                real_stop = app._stop_trail_watch
                app._stop_trail_watch = lambda: stops.append(1)
                # A SUCCESSFUL launch whose baseline read fails ([]).
                app._install_trail_watch("art:trail-test", [])
                app._stop_trail_watch = real_stop
                self.assertEqual(stops, [],
                                 "an unreadable baseline tore down a valid "
                                 "watch and installed nothing")
                self.assertEqual(self._watch_state(app), before)
                app._stop_trail_watch()

        self._run(go())

    def test_install_twice_leaves_one_timer(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                app._install_trail_watch("art:trail-test", ["a"])
                first = app._trail_watch_timer
                app._install_trail_watch("art:trail-test", ["b"])
                second = app._trail_watch_timer
                self.assertIsNot(first, second)
                self.assertEqual(app._trail_watch_baseline, ["b"])
                app._stop_trail_watch()

        self._run(go())

    # --- supersession -----------------------------------------------------

    def test_stale_worker_callback_discarded_on_same_handle_restart(self):
        """The hazard a handle/view guard alone cannot catch.

        Re-arming for the SAME handle leaves handle and base_filter identical,
        so only a dedicated watch token retires the earlier worker.
        """
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                spawned = []
                app._trail_watch_worker = (
                    lambda gen, handle: spawned.append((gen, handle)))
                reloads = []
                app._reload_active_trail = lambda: reloads.append(1)

                app._install_trail_watch("art:trail-test", ["v1"])
                app._trail_watch_tick()
                self.assertEqual(len(spawned), 1)
                stale_gen = spawned[0][0]
                self.assertTrue(app._trail_watch_busy)

                # Re-arm for the same handle while that worker is in flight.
                app._install_trail_watch("art:trail-test", ["v2"])
                self.assertFalse(app._trail_watch_busy)

                # The first worker now reports — with a listing that DIFFERS
                # from the new baseline, so a missing guard would reload.
                app._on_trail_watch(stale_gen, "art:trail-test", ["v9"])
                self.assertEqual(reloads, [])
                self.assertFalse(app._trail_watch_busy,
                                 "stale callback cleared the new watch's "
                                 "busy flag")
                self.assertEqual(app._trail_watch_baseline, ["v2"])
                app._stop_trail_watch()

        self._run(go())

    def test_callback_after_stop_is_discarded(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                reloads = []
                app._reload_active_trail = lambda: reloads.append(1)
                app._install_trail_watch("art:trail-test", ["v1"])
                gen = app._trail_watch_gen
                app._stop_trail_watch()
                app._on_trail_watch(gen, "art:trail-test", ["v2"])
                self.assertEqual(reloads, [])

        self._run(go())

    def test_reload_active_trail_does_not_disarm_watch(self):
        """Negative control: the watch must not key off _trail_gen.

        The post-launch reload bumps _trail_gen while the agent is still
        running; keying the watch off it would silently stop the poller.
        """
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                app._install_trail_watch("art:trail-test", ["v1"])
                before = self._watch_state(app)
                app._trail_reload_worker = lambda gen, handle: None
                app._reload_active_trail()
                self.assertEqual(self._watch_state(app), before)
                app._stop_trail_watch()

        self._run(go())

    def test_busy_tick_spawns_no_second_worker(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                spawned = []
                app._trail_watch_worker = (
                    lambda gen, handle: spawned.append(gen))
                app._install_trail_watch("art:trail-test", ["v1"])
                app._trail_watch_tick()
                app._trail_watch_tick()
                app._trail_watch_tick()
                self.assertEqual(len(spawned), 1)
                app._stop_trail_watch()

        self._run(go())

    # --- polling semantics ------------------------------------------------

    def test_transient_versions_failure_is_a_retry_not_a_change(self):
        """_trail_versions returns [] for EVERY failure — never a 'change'."""
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                reloads = []
                app._reload_active_trail = lambda: reloads.append(1)
                app._install_trail_watch("art:trail-test", ["v1"])
                gen = app._trail_watch_gen
                app._on_trail_watch(gen, "art:trail-test", [])
                self.assertEqual(reloads, [])
                self.assertIsNotNone(app._trail_watch_timer)
                self.assertEqual(app._trail_watch_gen, gen,
                                 "a transient failure stopped the watch")
                app._stop_trail_watch()

        self._run(go())

    def test_unchanged_versions_keep_watching_changed_reloads(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                reloads = []
                notes = []
                app._reload_active_trail = lambda: reloads.append(1)
                app.notify = lambda *a, **k: notes.append(a)
                app._install_trail_watch("art:trail-test", ["v1"])

                app._on_trail_watch(app._trail_watch_gen, "art:trail-test",
                                    ["v1"])
                self.assertEqual(reloads, [])
                self.assertIsNotNone(app._trail_watch_timer)

                app._on_trail_watch(app._trail_watch_gen, "art:trail-test",
                                    ["v2", "v1"])
                self.assertEqual(len(reloads), 1)
                self.assertIsNone(app._trail_watch_timer,
                                  "watch kept polling after the reload")
                self.assertTrue(notes)

        self._run(go())

    def test_foreign_handle_and_view_change_stop_the_watch(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                reloads = []
                app._reload_active_trail = lambda: reloads.append(1)

                app._install_trail_watch("art:trail-test", ["v1"])
                app._on_trail_watch(app._trail_watch_gen, "art:other", ["v2"])
                self.assertEqual(reloads, [])
                self.assertIsNone(app._trail_watch_timer)

                # Leaving By-Trail stops it.
                app._install_trail_watch("art:trail-test", ["v1"])
                self.assertIsNotNone(app._trail_watch_timer)
                app._set_base_filter("all")
                await pilot.pause()
                self.assertIsNone(app._trail_watch_timer)

        self._run(go())

    def test_activating_another_trail_stops_the_watch(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                app._install_trail_watch("art:trail-test", ["v1"])
                app._activate_trail("art:trail-other")
                await pilot.pause()
                self.assertIsNone(app._trail_watch_timer)
                self.assertEqual(app._trail_watch_handle, "")

        self._run(go())

    def test_tick_ceiling_stops_the_watch(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                app._trail_watch_worker = lambda gen, handle: None
                app._install_trail_watch("art:trail-test", ["v1"])
                for _ in range(ab.TRAIL_WATCH_MAX_TICKS):
                    app._trail_watch_busy = False
                    app._trail_watch_tick()
                self.assertIsNotNone(app._trail_watch_timer)
                app._trail_watch_busy = False
                app._trail_watch_tick()          # one past the ceiling
                self.assertIsNone(app._trail_watch_timer)

        self._run(go())


class ThreadWorkerTests(ByTrailTestBase):
    """The REAL @work(thread=True) boundary for the t1268 workers.

    Every other watch test stubs the worker to stay deterministic; these drive
    the actual thread hop. Walks the axes of
    aidocs/framework/testing_conventions.md that apply to a Textual thread
    worker + set_interval timer:

      1. Lifecycle      — start idempotency, start-after-stop, stop
                          idempotency, stop with pending work.
      2. Concurrency    — 50 concurrent real workers; exactly one reload wins.
      4. Failure recov. — the versions read fails; next poll is clean, no raise.
      5. Resource bound.— artifact script absent → clean [] fallback, watch
                          survives.
      6. Cleanup        — bounded thread use: repeated runs do not grow the
                          thread set. NOTE the guarantee is deliberately
                          weaker than "threads are joined / enumerate()
                          returns to the pre-run baseline": Textual dispatches
                          thread workers onto a pool, so the first run adds a
                          thread that legitimately persists. What is asserted
                          is no growth across subsequent runs, measured from a
                          warmed baseline.

    Not applicable, deliberately: axis 3 (mixed contexts / sync caller inside a
    running loop on another thread) — no asyncio bridge is introduced here;
    Textual owns the loop and `call_from_thread` is its sanctioned hop. Axis 7
    (behaviour parity old vs new) — these are new code paths with no
    predecessor to compare against.
    """

    async def _wait(self, pilot, pred, tries=100, delay=0.05):
        for _ in range(tries):
            if pred():
                return True
            await asyncio.sleep(delay)
            await pilot.pause()
        return pred()

    def test_real_watch_worker_delivers_on_the_main_thread(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                seen = {}
                app._reload_active_trail = (
                    lambda: seen.update(thread=threading.current_thread()))
                with patch.object(ab, "_trail_versions", lambda h: ["v2"]):
                    app._install_trail_watch("art:trail-test", ["v1"])
                    app._trail_watch_tick()          # REAL thread worker
                    ok = await self._wait(pilot, lambda: "thread" in seen)
                self.assertTrue(ok, "real worker never delivered its callback")
                self.assertIs(seen["thread"], threading.main_thread(),
                              "callback did not hop back to the UI thread")
                self.assertIsNone(app._trail_watch_timer)

        self._run(go())

    def test_real_reload_worker_replaces_the_document(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                fresh = _ghost_doc()
                fresh["title"] = "Reloaded trail"
                with patch.object(ab, "load_trail_blob",
                                  lambda h: (fresh, "", [])):
                    app._reload_active_trail()       # REAL thread worker
                    ok = await self._wait(
                        pilot,
                        lambda: (app._trail_doc or {}).get("title")
                        == "Reloaded trail")
                self.assertTrue(ok, "reload worker never applied the document")
                # The stale discovery cache was invalidated with it.
                self.assertIsNone(app._trail_infos)

        self._run(go())

    def test_fifty_concurrent_real_workers_produce_one_reload(self):
        """Axis 2. The token must hold under genuine thread concurrency."""
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                reloads = []
                threads = []
                app._reload_active_trail = lambda: reloads.append(1)
                app.notify = lambda *a, **k: None

                def versions(_handle):
                    threads.append(threading.current_thread())
                    return ["v2"]                   # always "changed"

                with patch.object(ab, "_trail_versions", versions):
                    app._install_trail_watch("art:trail-test", ["v1"])
                    gen = app._trail_watch_gen
                    for _ in range(50):
                        app._trail_watch_worker(gen, "art:trail-test")
                    await self._wait(pilot, lambda: len(threads) >= 50)
                    await self._wait(pilot, lambda: reloads, tries=20)
                self.assertEqual(
                    len(reloads), 1,
                    f"expected exactly one reload, got {len(reloads)}")
                self.assertIsNone(app._trail_watch_timer)
                # They really did run off the UI thread.
                self.assertTrue(
                    any(t is not threading.main_thread() for t in threads))

        self._run(go())

    def test_missing_artifact_script_is_a_clean_retry(self):
        """Axes 4 + 5: the binary is absent — no raise, watch survives."""
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                reloads = []
                app._reload_active_trail = lambda: reloads.append(1)
                landed = []
                real_cb = app._on_trail_watch

                def spy(gen, handle, versions):
                    landed.append(versions)
                    return real_cb(gen, handle, versions)

                app._on_trail_watch = spy
                missing = Path("/nonexistent/aitask_artifact.sh")
                with patch.object(ab, "ARTIFACT_SCRIPT", missing):
                    app._install_trail_watch("art:trail-test", ["v1"])
                    app._trail_watch_tick()          # REAL worker + real subprocess call
                    ok = await self._wait(pilot, lambda: landed)
                self.assertTrue(ok, "worker never reported")
                # _trail_versions swallows FileNotFoundError → [] → retry.
                self.assertEqual(landed[0], [])
                self.assertEqual(reloads, [])
                self.assertIsNotNone(app._trail_watch_timer,
                                     "a missing binary stopped the watch")
                app._stop_trail_watch()

        self._run(go())

    def test_worker_threads_do_not_leak_per_invocation(self):
        """Axis 6: repeated real worker runs must not grow the thread set.

        Textual runs thread workers on a pooled thread, so the FIRST run
        legitimately adds one and keeps it. The leak signal is therefore
        growth across subsequent runs, measured from a warmed baseline — an
        absolute count taken before any worker ran would flag pool reuse as a
        leak.
        """
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                app._reload_active_trail = lambda: None
                done = []
                with patch.object(
                        ab, "_trail_versions",
                        lambda h: (done.append(1), ["v1"])[1]):
                    app._install_trail_watch("art:trail-test", ["v1"])
                    # Warm the pool with one run, THEN take the baseline.
                    app._trail_watch_tick()
                    await self._wait(pilot, lambda: len(done) >= 1)
                    baseline = threading.active_count()
                    for i in range(12):
                        app._trail_watch_busy = False
                        app._trail_watch_tick()
                        await self._wait(pilot, lambda n=i: len(done) > n + 1)
                    settled = await self._wait(
                        pilot,
                        lambda: threading.active_count() <= baseline,
                        tries=60)
                self.assertEqual(len(done), 13)
                self.assertTrue(
                    settled,
                    f"threads grew across runs: warmed baseline={baseline} "
                    f"now={threading.active_count()}")
                app._stop_trail_watch()

        self._run(go())

    def test_stop_idempotent_and_start_after_stop(self):
        """Axis 1: stop twice is safe, and a watch can be re-armed after."""
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                app._stop_trail_watch()
                app._stop_trail_watch()              # idempotent
                self.assertIsNone(app._trail_watch_timer)

                app._install_trail_watch("art:trail-test", ["v1"])
                self.assertIsNotNone(app._trail_watch_timer)
                app._stop_trail_watch()
                self.assertIsNone(app._trail_watch_timer)

                # start-after-stop works and gets a fresh token.
                gen_before = app._trail_watch_gen
                app._install_trail_watch("art:trail-test", ["v2"])
                self.assertIsNotNone(app._trail_watch_timer)
                self.assertGreater(app._trail_watch_gen, gen_before)
                self.assertEqual(app._trail_watch_baseline, ["v2"])
                app._stop_trail_watch()

        self._run(go())


class LaunchFallbackTests(ByTrailTestBase):
    """t1268: the direct-launch fallback honours the same AC5 contract."""

    def test_direct_launch_fallback_installs_watch_and_reloads(self):
        """resolve_dry_run_command returning nothing must not opt the
        fallback out of the version watch / post-launch pickup."""
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                events = []
                patches = [
                    patch.object(ab, "resolve_dry_run_command",
                                 lambda root, op, *a, **k: ""),
                    patch.object(ab, "_trail_versions",
                                 lambda h: (events.append("versions"),
                                            ["v1"])[1]),
                    patch.object(app, "run_dialog_command",
                                 lambda cmd: events.append("run")),
                    patch.object(app, "_reload_active_trail",
                                 lambda: events.append("reload")),
                    patch.object(app, "notify", lambda *a, **k: None),
                    patch.object(app, "_trail_baseline_worker",
                                 lambda handle, then:
                                     then(ab._trail_versions(handle))),
                ]
                with patches[0], patches[1], patches[2], patches[3], \
                        patches[4], patches[5]:
                    app.action_trail_refresh_agent()
                # Baseline before launch, watch installed, pickup requested.
                self.assertEqual(events, ["versions", "run", "reload"])
                self.assertEqual(app._trail_watch_handle, "art:trail-test")
                self.assertEqual(app._trail_watch_baseline, ["v1"])
                self.assertIsNotNone(app._trail_watch_timer)
                app._stop_trail_watch()

        self._run(go())

    def test_baseline_read_is_off_the_ui_thread(self):
        """The read shells out with a 15s timeout; it must not run inline on
        the screen-result callback."""
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                where = {}
                got = []
                with patch.object(
                        ab, "_trail_versions",
                        lambda h: (where.update(
                            thread=threading.current_thread()), ["v1"])[1]):
                    app._with_trail_baseline(
                        "art:trail-test", lambda b: got.append(b))
                    ok = await self._wait(pilot, lambda: got)
                self.assertTrue(ok, "baseline callback never arrived")
                self.assertEqual(got, [["v1"]])
                self.assertIsNot(where["thread"], threading.main_thread(),
                                 "baseline read ran on the UI thread")

        self._run(go())

    async def _wait(self, pilot, pred, tries=100, delay=0.05):
        for _ in range(tries):
            if pred():
                return True
            await asyncio.sleep(delay)
            await pilot.pause()
        return pred()

    def test_repeated_R_during_an_in_flight_baseline_launches_once(self):
        """The baseline read can take up to 15s with the dialog already
        closed; a second confirmed `R` in that window must not spawn a second
        refresh agent."""
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                pending = []
                launches = []
                # Hold the baseline in flight: capture `then`, never call it.
                app._trail_baseline_worker = (
                    lambda handle, then: pending.append(then))
                app._launch_trail = (
                    lambda args, suffix, watch_handle="", **_kw:
                        (launches.append(list(args)),
                         app._with_trail_baseline(
                             watch_handle, lambda b: None))[0])

                app.action_trail_refresh_agent()
                await pilot.pause()
                self.assertEqual(len(launches), 1)
                self.assertTrue(app._trail_launch_pending)
                # Footer stops advertising it while the launch is pending.
                self.assertIs(
                    app.check_action("trail_refresh_agent", None), False)
                self.assertNotIn("trail_refresh_agent",
                                 self._footer_actions(app))

                # A second press during the window is a no-op.
                app.action_trail_refresh_agent()
                app.action_trail_refresh_agent()
                self.assertEqual(len(launches), 1,
                                 "a second agent was launched while the "
                                 "first baseline was still in flight")

                # Once the baseline lands the guard clears and `R` works again.
                app._finish_trail_launch(["v1"], "", lambda: True)
                self.assertFalse(app._trail_launch_pending)
                self.assertIsNot(
                    app.check_action("trail_refresh_agent", None), False)
                app.action_trail_refresh_agent()
                self.assertEqual(len(launches), 2)

        self._run(go())

    def test_pending_guard_updates_the_rendered_footer(self):
        """AC6 at the RENDERED level, not just active_bindings.

        Textual's mounted Footer recomposes only on the bindings_updated
        signal, so a check_action change without refresh_bindings() leaves the
        FooterKey widget on screen advertising a key that has become a no-op.
        Asserting on active_bindings alone cannot see that.
        """
        ab = self.ab
        from textual.widgets import Footer
        from textual.widgets._footer import FooterKey

        def footer_keys(app) -> dict:
            return {k.key: k.description
                    for k in app.query_one(Footer).query(FooterKey)}

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(200, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                await pilot.pause()

                # BEFORE: the key is rendered in the footer.
                before = footer_keys(app)
                self.assertEqual(before.get("R"), "Agent Refresh", before)

                pending = []
                app._trail_baseline_worker = (
                    lambda handle, then: pending.append(then))
                app._launch_trail = (
                    lambda args, suffix, watch_handle="", **_kw:
                        app._with_trail_baseline(watch_handle, lambda b: None))
                app.action_trail_refresh_agent()
                await pilot.pause()
                await pilot.pause()

                # DURING: it must be gone from the rendered footer too.
                during = footer_keys(app)
                self.assertNotIn(
                    "R", during,
                    "R Agent Refresh stayed rendered while it was a no-op")
                # The rendered text no longer mentions it either.
                rendered = " ".join(
                    str(k.render()) for k in
                    app.query_one(Footer).query(FooterKey))
                self.assertNotIn("Agent Refresh", rendered)

                # AFTER: clearing the guard restores it on screen.
                app._finish_trail_launch(["v1"], "", lambda: True)
                await pilot.pause()
                await pilot.pause()
                after = footer_keys(app)
                self.assertEqual(after.get("R"), "Agent Refresh", after)

        self._run(go())

    def test_failed_launch_clears_the_pending_guard(self):
        """A launch that never started must not wedge `R` permanently."""
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                app._reload_active_trail = lambda: None
                app._trail_launch_pending = True
                app._finish_trail_launch(["v1"], "art:trail-test",
                                         lambda: False)
                self.assertFalse(app._trail_launch_pending)
                self.assertIsNone(app._trail_watch_timer)

        self._run(go())

    def test_no_watch_requested_stays_synchronous(self):
        """The create-trail path (no watch_handle) is unchanged."""
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                got = []
                called = []
                with patch.object(ab, "_trail_versions",
                                  lambda h: called.append(h)):
                    app._with_trail_baseline("", lambda b: got.append(b))
                # Resolved inline, no worker, no versions read.
                self.assertEqual(got, [None])
                self.assertEqual(called, [])

        self._run(go())


class FreshnessGatingTests(ByTrailTestBase):
    """t1268: no refresh key may advertise itself without a trail to act on."""

    def test_refresh_keys_hidden_until_a_trail_is_active(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                # Enter By-Trail with NO active trail (selector cancelled).
                app._trail_infos = []
                app._open_trail_select = lambda rescan=False: None
                app._set_base_filter("bytrail")
                await pilot.pause()
                await pilot.pause()
                self.assertIsNone(app.active_trail_handle)
                actions = self._footer_actions(app)
                for action in ("trail_refresh_local", "trail_refresh_drift",
                               "trail_refresh_agent"):
                    self.assertIs(app.check_action(action, None), False,
                                  f"{action} advertised with no active trail")
                    self.assertNotIn(action, actions)
                # Selecting and syncing remain available and meaningful.
                self.assertIsNot(app.check_action("trail_select", None), False)
                self.assertIsNot(app.check_action("trail_sync", None), False)
                self.assertIn("trail_select", actions)

                # With a trail active they all come back.
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                actions = self._footer_actions(app)
                for action in ("trail_refresh_local", "trail_refresh_drift",
                               "trail_refresh_agent"):
                    self.assertIn(action, actions)

        self._run(go())


# A trail title long enough to swallow the header row on its own. The clipping
# this pins is a function of title length, so it must not be a short fixture.
_LONG_TRAIL_TITLE = ("Cross-repo gate framework landing order and verifier "
                     "registry consolidation")


class BannerRenderTests(ByTrailTestBase):
    """t1278: the freshness banner must reach the SCREEN, not just sub_title.

    Every pre-existing banner assertion in this file reads `app.sub_title`,
    which was correct the whole time the banner was invisible. These tests
    assert on the composited frame instead, and each one was confirmed to fail
    against the pre-fix source (docked #filter_area / unbudgeted banner).
    """

    @staticmethod
    def _doc(title: str) -> dict:
        doc = copy.deepcopy(_load_fixture())
        doc["title"] = title
        return doc

    async def _enter_live_bytrail(self, app, pilot, doc):
        """Enter By-Trail WITHOUT stubbing _start_trail_drift.

        _enter_synthetic_bytrail no-ops the drift kick, which is right for
        tests about other things but would sever the very chain these tests
        exist to exercise."""
        app.active_trail_handle = "art:trail-test"
        app._trail_infos = []
        app._trail_doc = doc
        app._trail_error = ""
        app._set_base_filter("bytrail")
        await pilot.pause()
        await pilot.pause()

    def test_d_key_drives_checking_then_stale_onto_the_header_row(self):
        """The reported flow, end to end, through the real key and workers.

        Only the two module-level subprocess seams are replaced. The key
        press, action dispatch, worker launch, thread hop and callback
        ordering are all the production ones, so a regression in any of them
        fails here — which a test that injected _trail_drift and called
        _refresh_subtitle() directly could not detect.
        """
        ab = self.ab

        async def go():
            # Gate the reload worker so the intermediate "checking" frame is
            # observed deterministically instead of raced for.
            gate = threading.Event()

            def fake_load(handle):
                gate.wait(timeout=5)
                return (self._doc("Gate framework landing order"), "", ["v1"])

            def fake_drift(handle):
                return ("STALE", [("stale_status", "aitasks#1", "d1"),
                                  ("stale_status", "aitasks#2", "d2")])

            with patch.object(ab, "load_trail_blob", fake_load), \
                    patch.object(ab, "run_trail_drift", fake_drift):
                app = ab.KanbanApp()
                async with app.run_test(size=(160, 40)) as pilot:
                    await pilot.pause()
                    await self._enter_live_bytrail(
                        app, pilot, self._doc("Gate framework landing order"))
                    await app.workers.wait_for_complete()
                    await pilot.pause()
                    self.assertIn("⚠ stale: 2", self._screen_rows(app)[0])

                    await pilot.press("d")
                    # Two beats, not one: _reload_active_trail writes the
                    # subtitle synchronously but the frame still has to
                    # composite. Safe to over-wait — the reload worker is
                    # gated, so the "checking" state cannot elapse.
                    await pilot.pause()
                    await pilot.pause()
                    try:
                        self.assertIn("⟳ checking freshness…",
                                      self._screen_rows(app)[0])
                    finally:
                        # Release the worker even when the assertion above
                        # fails: an unreleased gate parks the thread until its
                        # 5s timeout, making a failing test a slow noisy one.
                        gate.set()
                        await app.workers.wait_for_complete()
                    await pilot.pause()
                    await app.workers.wait_for_complete()
                    await pilot.pause()
                    self.assertIn("⚠ stale: 2", self._screen_rows(app)[0])

        self._run(go())

    def test_marker_survives_narrow_terminals_and_long_titles(self):
        """The marker is the TAIL, so it is what HeaderTitle clips first.

        Asserts the presence of each COMPLETE status substring. That is both
        necessary and sufficient: clipping destroys the substring being
        matched ("(⚠ s…" does not contain "⚠ stale: 3"). Deliberately no
        generic "row 0 has no ellipsis" rule — the checking marker ends in one
        by design, and the elided-title rungs render one inside the quotes.
        """
        ab = self.ab

        async def check(width, verdict, expected):
            def fake_drift(handle):
                return (verdict, [("stale_status", f"aitasks#{i}", "d")
                                  for i in range(3)])

            with patch.object(ab, "run_trail_drift", fake_drift):
                app = ab.KanbanApp()
                async with app.run_test(size=(width, 30)) as pilot:
                    await pilot.pause()
                    await self._enter_live_bytrail(
                        app, pilot, self._doc(_LONG_TRAIL_TITLE))
                    await app.workers.wait_for_complete()
                    await pilot.pause()
                    row0 = self._screen_rows(app)[0]
                    self.assertIn(expected, row0,
                                  f"width={width}: {expected!r} clipped off "
                                  f"the header row: {row0.strip()!r}")

        async def go():
            # 80 is an ordinary terminal and is where the unbudgeted banner
            # clipped even a SHORT title; 60 forces the title off entirely.
            for width in (160, 120, 100, 80, 60):
                await check(width, "STALE", "⚠ stale: 3")

        self._run(go())

    def test_checking_marker_survives_down_to_its_declared_floor(self):
        """Pins the bound rather than claiming the ladder is width-proof.

        The shed can drop the trail title but not the app title, which
        HeaderTitle owns — so each marker has a hard floor. Measured:
        "⟳ checking freshness…" needs >=55 columns, "⚠ stale: N" needs >=44.
        Tested AT the bound; below it the banner degrades by clipping, which
        is the documented behaviour, not a crash.
        """
        ab = self.ab

        async def go():
            gate = threading.Event()

            def fake_drift(handle):
                gate.wait(timeout=5)
                return ("STALE", [("stale_status", "aitasks#1", "d")])

            with patch.object(ab, "run_trail_drift", fake_drift):
                app = ab.KanbanApp()
                async with app.run_test(size=(60, 30)) as pilot:
                    await pilot.pause()
                    await self._enter_live_bytrail(
                        app, pilot, self._doc(_LONG_TRAIL_TITLE))
                    # Gated drift worker: the "checking" frame cannot elapse,
                    # so an extra beat is free insurance under load.
                    await pilot.pause()
                    try:
                        self.assertIn("⟳ checking freshness…",
                                      self._screen_rows(app)[0])
                    finally:
                        gate.set()
                        await app.workers.wait_for_complete()

        self._run(go())

        async def stale_floor():
            def fake_drift(handle):
                return ("STALE", [("stale_status", "aitasks#1", "d")] * 3)

            with patch.object(ab, "run_trail_drift", fake_drift):
                app = ab.KanbanApp()
                async with app.run_test(size=(44, 30)) as pilot:
                    await pilot.pause()
                    await self._enter_live_bytrail(
                        app, pilot, self._doc(_LONG_TRAIL_TITLE))
                    await app.workers.wait_for_complete()
                    await pilot.pause()
                    self.assertIn("⚠ stale: 3", self._screen_rows(app)[0])

        self._run(stale_floor())

    def test_autorefresh_status_renders_without_a_trail(self):
        """The board-wide half: sub_title was invisible outside By-Trail too.

        Pins that the fix is not By-Trail-specific — the same occluded header
        hid the auto-refresh state for every user in every view.
        """
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                self.assertIn("Auto-refresh", self._screen_rows(app)[0])

        self._run(go())

    def test_header_row_costs_no_board_height_and_keeps_a_separator(self):
        """Undocking bought the header row from the redundant bottom margin.

        Pins both halves of that trade so a later CSS edit cannot silently
        take a row from the lanes, nor collapse the filter/lane boundary.
        """
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(120, 20)) as pilot:
                await pilot.pause()
                board = app.query_one("#board_container")
                self.assertEqual((board.region.x, board.region.y), (0, 4),
                                 "lanes moved: the header row was paid for "
                                 "out of board height, not the old margin")
                rows = self._screen_rows(app)
                # Row 3 separates the filter row from the lanes. The search
                # Input's bottom border sits on its right; the left must stay
                # clear so the boundary reads as a boundary.
                self.assertEqual(rows[3][:40].strip(), "",
                                 f"filter/lane separator lost: {rows[3]!r}")

        self._run(go())


class RefreshDoubleTapTests(ByTrailTestBase):
    """t1279: a double-tapped `R` must not confirm the launch dialog.

    `R` opens AgentCommandScreen, which binds `R -> run`, so the second press
    was consumed by the modal and confirmed it — launching a real agent the
    user never reviewed (t1273 item #5).

    These tests drive the REAL dialog through real key dispatch. The existing
    TrailWatchTests / LaunchFallbackTests call action_trail_refresh_agent()
    directly against a FakeScreen and therefore cannot see this bug.
    """

    def _env(self, app, clock, *, tmux: bool):
        """Patch the launch surface, the dialog's tmux shape, and the clock."""
        ab = self.ab
        launches = []

        return launches, [
            patch.object(acs, "_monotonic", clock),
            patch.object(acs, "is_tmux_available", lambda: tmux),
            patch.object(acs, "get_tmux_sessions", lambda: ["work"]),
            patch.object(acs, "get_tmux_windows", lambda s: [("0", "main")]),
            patch.object(acs, "load_tmux_defaults", lambda root: {
                "default_split": "vertical",
                "default_session": "work",
                "prefer_tmux": tmux,
            }),
            patch.object(ab, "resolve_dry_run_command",
                         lambda root, op, *a, **k: f"CMD {op}"),
            patch.object(ab, "resolve_agent_string",
                         lambda root, op: "claudecode/test"),
            patch.object(ab, "_trail_versions", lambda h: ["v1"]),
            patch.object(app, "_trail_baseline_worker",
                         lambda handle, then: then(["v1"])),
            patch.object(ab, "maybe_spawn_minimonitor", lambda s, w: None),
            # The two ways a confirmed dialog reaches a real agent.
            patch.object(app, "run_dialog_command",
                         lambda cmd: launches.append(("terminal", cmd))),
            patch.object(ab, "launch_in_tmux",
                         lambda cmd, cfg: (launches.append(("tmux", cmd)),
                                           (123, None))[1]),
        ]

    def _double_tap(self, tmux: bool):
        ab = self.ab
        clock = FakeClock()

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                launches, patches = self._env(app, clock, tmux=tmux)
                for ctx in patches:
                    ctx.start()
                try:
                    # _press_keys interleaves wait_for_idle between keys, so
                    # this is a genuine double-tap, not two isolated presses.
                    await pilot.press("R", "R")
                    await pilot.pause()
                    self.assertIsInstance(app.screen, ab.AgentCommandScreen,
                                          "the dialog was dismissed by the "
                                          "second R")
                    self.assertEqual(launches, [],
                                     "an agent was launched without review")

                    # ...and the dialog is not left crippled: past the window
                    # the same key runs normally.
                    clock.advance(acs.OPENING_DEBOUNCE_SECONDS + 0.05)
                    await pilot.press("R")
                    await pilot.pause()
                    self.assertEqual(len(launches), 1, launches)
                    self.assertEqual(launches[0][0],
                                     "tmux" if tmux else "terminal")
                finally:
                    for ctx in reversed(patches):
                        ctx.stop()

        self._run(go())

    def test_double_tap_does_not_launch_in_terminal_mode(self):
        self._double_tap(tmux=False)

    def test_double_tap_does_not_launch_in_tmux_mode(self):
        """The realistic case: inside tmux the dialog opens on the tmux tab,
        so an unreviewed confirm spawns a background agent window."""
        self._double_tap(tmux=True)

    def test_board_threads_the_resolved_key_through_normalisation(self):
        """A remapped launch key must still reach the guard.

        resolve_key() returns the literal from the shortcut editor ("#");
        event.key and BindingsMap use Textual's normalised name.
        """
        ab = self.ab
        clock = FakeClock()

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                _launches, patches = self._env(app, clock, tmux=False)
                patches.append(patch.object(
                    ab, "resolve_key", lambda scope, action, default=None: "#"))
                for ctx in patches:
                    ctx.start()
                try:
                    await pilot.press("R")
                    await pilot.pause()
                    self.assertIsInstance(app.screen, ab.AgentCommandScreen)
                    self.assertEqual(app.screen._debounce_key, "number_sign")
                finally:
                    for ctx in reversed(patches):
                        ctx.stop()

        self._run(go())


class TrailRefResolutionTests(ByTrailTestBase):
    """t1354_1: fixture trail refs must resolve to REAL cards, not ghosts.

    `load_local_project_name` returns "" when the fixture has no
    `project_config.yaml`, `trail_ref_to_local_id` then returns None, and every
    `aitasks#<id>` member renders as an unresolvable cross-repo ghost. Nothing
    raises — the whole By-Trail suite would simply assert against ghosts and
    pass vacuously. This pins the resolution for a parent AND a child ref, and
    the negative control below proves the assertion discriminates.
    """

    @staticmethod
    def _resolving_doc():
        refs = ["aitasks#9000", "aitasks#9000_1"]   # parent + child
        return {
            "title": "Resolving trail", "trail_id": "trail-resolve",
            "narrative": {"problem_statement": "p",
                          "recommendation_summary": "r"},
            "waves": [{
                "wave_id": "w1", "ordinal": 1, "title": "Wave 1", "purpose": "p",
                "entries": [{
                    "entry_id": f"e{i}", "task": ref, "topic": ref,
                    "position": i + 1, "classification": "core",
                    "confidence": "high", "rationale": "r",
                    "snapshot": {"status": "Ready"},
                } for i, ref in enumerate(refs)],
            }],
        }

    async def _counts(self, ab, pilot, app):
        await self._enter_synthetic_bytrail(app, pilot, self._resolving_doc(),
                                            handle="art:trail-resolve")
        return (len(app.query(ab.TrailTaskCard)),
                len(app.query(ab.TrailGhostCard)))

    def test_parent_and_child_refs_render_as_real_cards(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                self.assertEqual(ab.load_local_project_name(), "aitasks")
                real, ghosts = await self._counts(ab, pilot, app)
                self.assertEqual((real, ghosts), (2, 0),
                                 "both the parent and the child trail ref must "
                                 "resolve to live TrailTaskCards")

        self._run(go())

    def test_without_project_config_the_same_refs_become_ghosts(self):
        """Negative control: proves the assertion above is not vacuous."""
        _tree, ab = bf.enter_fixture_tree(
            self.addCleanup, tag="noproject", project_name=None)

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                self.assertEqual(ab.load_local_project_name(), "")
                real, ghosts = await self._counts(ab, pilot, app)
                self.assertEqual((real, ghosts), (0, 2),
                                 "without project_config.yaml every ref must "
                                 "degrade to a cross-repo ghost")

        self._run(go())


class FixtureCwdDependencyTests(ByTrailTestBase):
    """t1354_1: pin which cwd-relative helpers a By-Trail boot actually spawns.

    Under `cwd=<fixture tree>` every `./.aitask-scripts/...` helper is absent,
    and each call site swallows `FileNotFoundError`. That silence is the hazard:
    a future change that routes this path through a new helper would degrade
    invisibly and a test could pass through the fallback instead of the branch
    it names. Pinning the spawn set turns that into a visible failure here.
    """

    @staticmethod
    def _names(spawns) -> set[str]:
        return {Path(argv[0]).name for argv in spawns}

    def _assert_git_probe_only(self, spawns, phase: str):
        for argv in spawns:
            if Path(argv[0]).name != "git":
                continue
            # Branch mode routes through `git -C .aitask-data`, which is exactly
            # the production topology the fixture reproduces.
            self.assertIn("status", argv, f"unexpected git use in {phase}: {argv}")
            self.assertIn("--porcelain", argv, f"unexpected git use in {phase}: {argv}")

    def test_boot_and_bytrail_phases_spawn_only_expected_helpers(self):
        """Both phases are pinned, and the boot set is asserted before it is reset.

        `KanbanApp.on_mount` calls `refresh_board(refresh_locks=True)` during the
        very first `pilot.pause()`, so anything the boot shells out to is already
        spent by the time the By-Trail phase starts. Clearing the spy before
        asserting would leave the boot path — the one every test in this file
        runs — completely unguarded.
        """
        ab = self.ab
        boot: list[list[str]] = []
        later: list[list[str]] = []
        phase = {"sink": boot}
        real_run = subprocess.run

        def spy(argv, **kwargs):
            try:
                phase["sink"].append([str(a) for a in argv])
            except TypeError:                      # shell=True string form
                phase["sink"].append([str(argv)])
            return real_run(argv, **kwargs)

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()

                # --- boot phase, asserted BEFORE the sink is switched ---
                self.assertEqual(
                    self._names(boot), {"git", "aitask_lock.sh"},
                    f"unexpected cwd-relative helper spawned during boot: {boot}")
                self._assert_git_probe_only(boot, "boot")
                # `./.aitask-scripts/aitask_lock.sh` does NOT exist under the
                # fixture cwd. It is *meant* to degrade here — the harness
                # deliberately does not symlink .aitask-scripts into the tree,
                # because re-enabling that subprocess costs ~0.43s per boot. Pin
                # the consequence, so a test that ever needs real lock state
                # fails loudly instead of quietly asserting against an empty map.
                self.assertEqual(app.manager.lock_map, {},
                                 "the absent lock helper must degrade to an "
                                 "empty lock map, not raise or half-populate")

                phase["sink"] = later
                await self._enter_synthetic_bytrail(app, pilot, _ghost_doc())
                app.action_trail_refresh_local()
                await pilot.pause()

        with patch("subprocess.run", side_effect=spy):
            self._run(go())

        # --- By-Trail entry + local refresh: the git probe and nothing else ---
        self.assertEqual(
            self._names(later), {"git"},
            f"unexpected cwd-relative helper spawned after boot: {later}")
        self._assert_git_probe_only(later, "bytrail+local-refresh")


class TrailDiscoveryFreshnessTests(unittest.TestCase):
    """t1365: discovery reads task frontmatter from DISK.

    The bug: `_iter_trail_frontmatter_records` took active tasks from
    `TaskManager.task_datas`, a board-STARTUP snapshot, so a trail whose owning
    task gained its `artifacts:` frontmatter while the board was running was
    invisible until a restart. Archived owners were already read from disk;
    only the active half was stale.

    Its own per-test tree (not the class-level fixture): every case MUTATES
    task files mid-run. It goes through `board_fixture` rather than patching
    `TASKS_DIR` because `TaskManager.__init__` resolves `METADATA_FILE` at
    import time — a bare `TASKS_DIR` patch would read and *write* the live
    repo's `aitasks/metadata/board_config.json`.
    """

    TASKS = (
        bf.FixtureTask(task_id="42", col="c0", idx=10, slug="alpha"),
        bf.FixtureTask(task_id="43", col="c0", idx=20, slug="beta"),
        bf.FixtureTask(task_id="42_1", col="c0", idx=30, slug="child"),
    )

    def setUp(self):
        self.tree, self.ab = bf.enter_fixture_tree(
            self.addCleanup, tasks_spec=self.TASKS, tag="trailfresh")
        self.tasks_dir = self.tree / "aitasks"

    # --- helpers ---------------------------------------------------------

    @staticmethod
    def _trail(handle: str, name: str = "Trail") -> dict:
        return {"handle": handle, "kind": "implementation_trail", "name": name}

    def _write_task(self, relpath: str, *, artifacts=None, status="Ready",
                    root=None):
        meta = {"priority": "medium", "effort": "low", "issue_type": "chore",
                "status": status}
        if artifacts is not None:
            meta["artifacts"] = artifacts
        meta["boardcol"] = "c0"
        meta["boardidx"] = 10
        path = (root or self.tasks_dir) / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            task_yaml.serialize_frontmatter(
                meta, "\n## Context\n\nbody\n",
                ["priority", "effort", "issue_type", "status"]),
            encoding="utf-8")
        return path

    @staticmethod
    def _owns(tasks, handle: str) -> list:
        """Tasks whose in-memory metadata carries `handle` — the exact
        expression the pre-fix discovery consumed, read off live objects."""
        return [t for t in tasks
                if any(isinstance(r, dict) and r.get("handle") == handle
                       for r in (t.metadata.get("artifacts") or []))]

    @staticmethod
    def _snapshot(manager) -> list:
        return (list(manager.task_datas.values())
                + list(manager.child_task_datas.values()))

    def _discover(self):
        """Run real discovery with only the blob subprocess stubbed."""
        with patch.object(self.ab, "load_trail_blob",
                          lambda handle: ({"trail_id": handle}, "", [])):
            return self.ab.discover_trails()

    # --- the acceptance case ---------------------------------------------

    def test_discovery_sees_frontmatter_written_after_the_manager_was_built(self):
        """The reported symptom, at the discovery layer."""
        ab = self.ab
        # Built BEFORE the mutation: this real object IS the pre-fix source.
        manager = ab.TaskManager()

        self._write_task("t43_beta.md", artifacts=[self._trail("art:trail-x")])

        infos, unreadable = self._discover()

        self.assertEqual(unreadable, [])
        found = [i for i in infos if i.handle == "art:trail-x"]
        self.assertEqual(len(found), 1, [i.handle for i in infos])
        # A missing ARTIFACT_SCRIPT would still yield a record carrying the
        # handle, only with load_error set — that must not fake the pass.
        self.assertEqual(found[0].load_error, "")
        self.assertEqual(found[0].owner_id, "43")
        self.assertFalse(found[0].owner_archived)

        # Negative control: the manager snapshot still knows nothing about it,
        # so the handle provably did not come from there.
        self.assertEqual(self._owns(self._snapshot(manager), "art:trail-x"), [],
                         "manager snapshot already carried the handle — this "
                         "test cannot discriminate")

        # Recovery control: kills the vacuous pass where the frontmatter was
        # written wrong and NOBODY could have seen it.
        manager.load_tasks()
        self.assertTrue(self._owns(self._snapshot(manager), "art:trail-x"))

    def test_child_and_archived_owners_are_discovered(self):
        """The `t*/t*_*.md` glob, and the merged active/archived emit block."""
        self._write_task("t42/t42_1_child.md",
                         artifacts=[self._trail("art:trail-kid")])
        self._write_task("t9100_old.md",
                         artifacts=[self._trail("art:trail-old")],
                         root=self.tasks_dir / "archived")

        infos, unreadable = self._discover()

        self.assertEqual(unreadable, [])
        by_handle = {i.handle: i for i in infos}
        self.assertIn("art:trail-kid", by_handle)
        self.assertEqual(by_handle["art:trail-kid"].owner_id, "42_1")
        self.assertFalse(by_handle["art:trail-kid"].owner_archived)
        self.assertIn("art:trail-old", by_handle)
        self.assertEqual(by_handle["art:trail-old"].owner_id, "9100")
        self.assertTrue(by_handle["art:trail-old"].owner_archived)

    # --- torn reads ------------------------------------------------------

    def test_malformed_frontmatter_skips_only_that_file(self):
        """`parse_frontmatter` RAISES on malformed YAML and the consumer is a
        thread worker with exit_on_error=True — an escaped exception would kill
        the board rather than lose one file."""
        self._write_task("t42_alpha.md", artifacts=[self._trail("art:trail-a")])
        self._write_task("t43_beta.md", artifacts=[self._trail("art:trail-b")])
        (self.tasks_dir / "t44_broken.md").write_text(
            "---\npriority: medium\nartifacts: [{handle: art:trail-torn\n"
            "---\n\nbody\n", encoding="utf-8")

        infos, unreadable = self._discover()   # must not raise

        self.assertEqual(unreadable, ["t44_broken.md"])
        self.assertEqual(sorted(i.handle for i in infos),
                         ["art:trail-a", "art:trail-b"])

    def test_truncated_rewrite_windows_are_reported_not_silently_dropped(self):
        """`open(path, "w")` truncates BEFORE writing, so the likeliest instant
        to catch a task file in is empty or cut at the delimiter — and
        `parse_frontmatter` returns None for both rather than raising. Reported
        as unreadable, or a torn read announces "no trails"."""
        self._write_task("t42_alpha.md", artifacts=[self._trail("art:trail-a")])
        # Truncated to zero bytes — the first instant of every rewrite.
        (self.tasks_dir / "t45_empty.md").write_text("", encoding="utf-8")
        # Opening delimiter written, closing one not yet.
        (self.tasks_dir / "t46_partial.md").write_text(
            "---\npriority: medium\nstatus: Ready\n", encoding="utf-8")

        infos, unreadable = self._discover()

        self.assertEqual(sorted(unreadable), ["t45_empty.md", "t46_partial.md"])
        self.assertEqual([i.handle for i in infos], ["art:trail-a"])

    def test_a_non_task_document_is_not_reported_as_unreadable(self):
        """Discrimination for the case above: without the task-named qualifier
        an ordinary document under the task dir would warn on every scan."""
        self._write_task("t42_alpha.md", artifacts=[self._trail("art:trail-a")])
        (self.tasks_dir / "README.md").write_text(
            "# Notes\n\nNo frontmatter here.\n", encoding="utf-8")
        (self.tasks_dir / "t_unparseable.md").write_text(
            "# Not a task id\n", encoding="utf-8")

        infos, unreadable = self._discover()

        self.assertEqual(unreadable, [])
        self.assertEqual([i.handle for i in infos], ["art:trail-a"])

    def test_unreadable_file_skips_only_that_file(self):
        if os.geteuid() == 0:
            self.skipTest("root bypasses the permission bit")
        self._write_task("t42_alpha.md", artifacts=[self._trail("art:trail-a")])
        bad = self._write_task("t43_beta.md",
                               artifacts=[self._trail("art:trail-b")])
        bad.chmod(0o000)
        self.addCleanup(bad.chmod, 0o644)

        infos, unreadable = self._discover()

        self.assertEqual(unreadable, ["t43_beta.md"])
        self.assertEqual([i.handle for i in infos], ["art:trail-a"])


class TrailDiscoveryErrorReportingTests(ByTrailTestBase):
    """t1365: an unreadable file must not masquerade as "no trails"."""

    @staticmethod
    def _warnings(app, records):
        original = app.notify

        def spy(message, **kwargs):
            records.append((message, kwargs.get("severity")))
            return original(message, **kwargs)

        return spy

    def _info(self, handle="art:trail-stale"):
        return self.ab.TrailInfo(handle=handle, owner_id="1", owner_archived=False,
                                 owner_folded=False, name="Stale")

    async def _settle(self, app, pilot, tries=20):
        for _ in range(tries):
            if app._trail_infos is not None:
                return
            await asyncio.sleep(0.05)
            await pilot.pause()

    def test_clean_empty_scan_stays_authoritative(self):
        """Control for the two tests below: with nothing unreadable, an empty
        result IS the answer and keeps its definitive hint."""
        ab = self.ab
        notes = []

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                app.notify = self._warnings(app, notes)
                with patch.object(ab, "discover_trails", lambda: ([], [])):
                    app._set_base_filter("bytrail")
                    await pilot.pause()
                    await self._settle(app, pilot)
                self.assertEqual(app._trail_infos, [])
                rows = "\n".join(self._screen_rows(app))
                self.assertIn("No implementation trails found", rows)
                self.assertFalse([m for m, sev in notes if sev == "warning"],
                                 notes)

        self._run(go())

    def test_errored_empty_scan_is_not_authoritative(self):
        ab = self.ab
        notes = []

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                with patch.object(ab, "discover_trails", lambda: ([], [])):
                    app._set_base_filter("bytrail")
                    await pilot.pause()
                    await self._settle(app, pilot)
                app.notify = self._warnings(app, notes)

                app._on_trail_discovery(app._trail_gen, [], ["t44_broken.md"],
                                        None)
                await pilot.pause()
                await pilot.pause()

                self.assertIsNone(app._trail_infos,
                                  "an errored scan must leave the cache unset "
                                  "so the next open re-scans")
                warned = [m for m, sev in notes if sev == "warning"]
                self.assertTrue(warned, notes)
                self.assertIn("t44_broken.md", warned[0])
                rows = "\n".join(self._screen_rows(app))
                self.assertNotIn("No implementation trails found", rows)
                self.assertIn("No trail selected", rows)

        self._run(go())

    def test_errored_empty_scan_drops_previously_cached_handles(self):
        """The case that separates `_trail_infos = None` from a bare `return`:
        `_open_trail_select` does not clear the cache before a rescan, so a
        retryable read failure would otherwise leave stale handles live."""
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                with patch.object(ab, "discover_trails", lambda: ([], [])):
                    app._set_base_filter("bytrail")
                    await pilot.pause()
                    await self._settle(app, pilot)

                # A prior successful scan's result.
                app._trail_infos = [self._info()]
                app.notify = lambda *a, **k: None

                app._on_trail_discovery(app._trail_gen, [], ["t44_broken.md"],
                                        None)
                await pilot.pause()

                self.assertIsNone(app._trail_infos)

        self._run(go())


class TrailSelectorLifecycleTests(unittest.TestCase):
    """t1365: view re-entry rescans; cancelling the selector disturbs nothing;
    activating a trail refreshes the projection."""

    TASKS = (
        bf.FixtureTask(task_id="42", col="c0", idx=10, slug="alpha"),
    )

    def setUp(self):
        self.tree, self.ab = bf.enter_fixture_tree(
            self.addCleanup, tasks_spec=self.TASKS, tag="traillife")
        self.tasks_dir = self.tree / "aitasks"

    def _doc(self, task_ref="aitasks#42", trail_id="trail-life"):
        return {
            "title": "Life trail", "trail_id": trail_id,
            "narrative": {"problem_statement": "p",
                          "recommendation_summary": "r"},
            "waves": [{
                "wave_id": "w1", "ordinal": 1, "title": "Wave 1",
                "purpose": "p", "entries": [{
                    "entry_id": "e1", "task": task_ref, "topic": task_ref,
                    "position": 1, "classification": "core",
                    "confidence": "high", "rationale": "r",
                    "snapshot": {"status": "Ready"},
                }],
            }],
        }

    def _info(self, handle, doc=None):
        return self.ab.TrailInfo(handle=handle, owner_id="42",
                                 owner_archived=False, owner_folded=False,
                                 name="Life", doc=doc or self._doc())

    def test_reentering_the_view_invalidates_the_discovery_cache(self):
        """The t1365 symptom reached WITHOUT pressing `s`: open the selector,
        cancel, leave and come back — the auto-open passes rescan=False."""
        ab = self.ab
        calls = []

        def fake_discover():
            calls.append(1)
            return [self._info("art:trail-fresh")], []

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                app._start_trail_drift = lambda: None
                with patch.object(ab, "discover_trails", fake_discover):
                    app._set_base_filter("bytrail")
                    await pilot.pause()
                    await pilot.pause()
                    for _ in range(20):
                        if calls:
                            break
                        await asyncio.sleep(0.05)
                        await pilot.pause()
                    self.assertEqual(len(calls), 1)
                    # Cancel the selector, then leave and re-enter.
                    if isinstance(app.screen, ab.TrailSelectScreen):
                        app.screen.dismiss(None)
                        await pilot.pause()
                    app._trail_infos = [self._info("art:trail-stale")]
                    app._set_base_filter("all")
                    await pilot.pause()
                    app._set_base_filter("bytrail")
                    await pilot.pause()
                    await pilot.pause()
                    for _ in range(20):
                        if len(calls) > 1:
                            break
                        await asyncio.sleep(0.05)
                        await pilot.pause()

                self.assertEqual(len(calls), 2,
                                 "re-entry served the stale cache instead of "
                                 "re-scanning")
                self.assertEqual([i.handle for i in (app._trail_infos or [])],
                                 ["art:trail-fresh"])

        asyncio.run(go())

    def test_cancelling_the_selector_leaves_the_board_untouched(self):
        """Pins why manager.load_tasks() lives in _activate_trail and NOT in
        the discovery callback: replacing Task objects while the modal is open
        would strand the rendered cards, and `_focused_card()` is empty behind
        a modal so no refocus target could be recovered."""
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                app.active_trail_handle = "art:trail-life"
                app._trail_doc = self._doc()
                app._trail_error = ""
                app._start_trail_drift = lambda: None
                app._set_base_filter("bytrail")
                await pilot.pause()
                await pilot.pause()

                card = next(iter(app.query(ab.TrailTaskCard)), None)
                self.assertIsNotNone(card, "no trail member card rendered")
                card.focus()
                await pilot.pause()
                before = app.manager.task_datas["t42_alpha.md"]

                with patch.object(ab, "discover_trails",
                                  lambda: ([self._info("art:trail-life")], [])):
                    await pilot.press("s")
                    await pilot.pause()
                    for _ in range(20):
                        if isinstance(app.screen, ab.TrailSelectScreen):
                            break
                        await asyncio.sleep(0.05)
                        await pilot.pause()
                    self.assertIsInstance(app.screen, ab.TrailSelectScreen)
                    app.screen.dismiss(None)
                    await pilot.pause()
                    await pilot.pause()

                self.assertIs(app.manager.task_datas["t42_alpha.md"], before,
                              "cancelling a scan reloaded the manager and "
                              "replaced the Task objects the cards hold")
                self.assertIs(app.focused, card,
                              "cancelling the selector dropped card focus")

        asyncio.run(go())

    def test_activating_a_trail_refreshes_the_projection(self):
        """Listing the trail is not enough: its members are created after the
        board started too, so without the reload they render as ghosts."""
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                app._start_trail_drift = lambda: None
                with patch.object(ab, "discover_trails", lambda: ([], [])):
                    app._set_base_filter("bytrail")
                    await pilot.pause()
                    await pilot.pause()

                # A member that did not exist when the manager was built.
                (self.tasks_dir / "t77_late.md").write_text(
                    "---\npriority: medium\neffort: low\nissue_type: chore\n"
                    "status: Ready\nboardcol: c0\nboardidx: 10\n---\n\nbody\n",
                    encoding="utf-8")
                self.assertNotIn("t77_late.md", app.manager.task_datas)

                info = self._info("art:trail-late",
                                  doc=self._doc(task_ref="aitasks#77"))
                app._trail_infos = [info]
                app._activate_trail("art:trail-late")
                await pilot.pause()
                await pilot.pause()

                self.assertIn("t77_late.md", app.manager.task_datas)
                self.assertEqual(len(list(app.query(ab.TrailTaskCard))), 1,
                                 "member rendered as a ghost — the projection "
                                 "still used the startup snapshot")
                self.assertEqual(len(list(app.query(ab.TrailGhostCard))), 0)

        asyncio.run(go())


class TrailDiscoveryPilotTests(unittest.TestCase):
    """t1365 AC1 is a RUNNING-board claim — drive the real key."""

    TASKS = (
        bf.FixtureTask(task_id="42", col="c0", idx=10, slug="alpha"),
        bf.FixtureTask(task_id="43", col="c0", idx=20, slug="beta"),
    )

    def setUp(self):
        self.tree, self.ab = bf.enter_fixture_tree(
            self.addCleanup, tasks_spec=self.TASKS, tag="trailpilot")
        self.tasks_dir = self.tree / "aitasks"

    def test_s_lists_a_trail_created_while_the_board_was_running(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                app._start_trail_drift = lambda: None
                # Enter the view with nothing to find — the state the user is
                # in when the trail gets created elsewhere.
                with patch.object(ab, "discover_trails", lambda: ([], [])):
                    app._set_base_filter("bytrail")
                    await pilot.pause()
                    for _ in range(20):
                        if app._trail_infos is not None:
                            break
                        await asyncio.sleep(0.05)
                        await pilot.pause()
                    self.assertEqual(app._trail_infos, [])

                # /aitask-trail patches the owning task's frontmatter on disk.
                (self.tasks_dir / "t43_beta.md").write_text(
                    "---\npriority: medium\neffort: low\nissue_type: chore\n"
                    "status: Ready\n"
                    "artifacts: [{handle: 'art:trail-live', "
                    "kind: implementation_trail, name: Live}]\n"
                    "boardcol: c0\nboardidx: 20\n---\n\nbody\n",
                    encoding="utf-8")

                # Real discovery this time; only the blob subprocess is stubbed.
                with patch.object(ab, "load_trail_blob",
                                  lambda h: ({"trail_id": h}, "", [])):
                    await pilot.press("s")
                    await pilot.pause()
                    for _ in range(40):
                        if isinstance(app.screen, ab.TrailSelectScreen):
                            break
                        await asyncio.sleep(0.05)
                        await pilot.pause()

                    self.assertIsInstance(app.screen, ab.TrailSelectScreen)
                    self.assertIn("art:trail-live",
                                  [i.handle for i in app.screen.infos])
                    # Control: the listing came from the disk read, not from
                    # something having reloaded the manager behind our back.
                    self.assertIsNone(
                        app.manager.task_datas["t43_beta.md"]
                        .metadata.get("artifacts"))

        asyncio.run(go())


class ComposeLayoutCharacterizationTests(ByTrailTestBase):
    """t1505_1 pre-phase: pin the composited BOTTOM of the By-Trail screen.

    Characterization, written and confirmed green against the board *before*
    the summary pane was added, so that mounting a new flow child into
    ``KanbanApp.compose`` fails loudly here rather than silently.

    The failure being guarded is t1278's, recorded in the board's own CSS at
    ``aitask_board.py`` (#filter_area): Textual places two same-edge docked
    siblings at the SAME offset, so one paints over the other while BOTH still
    report ``display=True``, ``visible=True`` and a correct region. Textual's
    ``Footer`` sets ``dock: bottom`` and ``MultiRowFooter`` overrides only
    ``layout``/``height`` — it never unsets the dock — so a summary pane that
    docked bottom too would land on the footer and erase it. No
    ``display``/``visible``/``region`` assertion can see that; only the
    composited frame can, which is why every assertion here goes through
    ``_screen_rows``.
    """

    def _bytrail_frame(self, size):
        """Boot the board into By-Trail at `size`; return (rows, board, footer)."""
        ab = self.ab
        captured = {}

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=size) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(
                    app, pilot, copy.deepcopy(_load_fixture()))
                captured["rows"] = self._screen_rows(app)
                captured["board"] = app.query_one("#board_container").region
                captured["footer"] = app.query_one(ab.MultiRowFooter).region

        self._run(go())
        return captured["rows"], captured["board"], captured["footer"]

    def test_footer_rows_are_composited_in_bytrail(self):
        """The footer's own rows carry its key labels on the real frame.

        This is the assertion a docked sibling breaks: the footer would still
        report a correct region while rendering nothing to those rows.
        """
        rows, _board, footer = self._bytrail_frame((120, 20))

        self.assertGreater(footer.height, 0, "footer collapsed to zero height")
        self.assertLessEqual(footer.bottom, len(rows),
                             "footer region falls outside the frame")

        footer_text = " ".join(rows[footer.y:footer.bottom])
        self.assertNotEqual(
            footer_text.strip(), "",
            f"footer rows composited blank — painted over? {rows[footer.y:footer.bottom]!r}")
        # A real binding label, not just "some ink": proves these rows belong
        # to the footer rather than to whatever overlapped it.
        self.assertIn("Quit", footer_text,
                      f"footer key labels missing from the frame: {footer_text!r}")

    def test_board_container_does_not_overlap_the_footer(self):
        """The lanes stop above the footer — the two never share a row."""
        rows, board, footer = self._bytrail_frame((120, 20))

        self.assertEqual((board.x, board.y), (0, 4),
                         "lanes moved: something took height from the board")
        self.assertLessEqual(
            board.bottom, footer.y,
            f"board container overlaps the footer: board={board} footer={footer}")
        self.assertLessEqual(footer.bottom, len(rows))

    def test_footer_survives_a_narrow_terminal(self):
        """Same guarantee at a width where the footer must reflow to survive."""
        rows, board, footer = self._bytrail_frame((80, 24))

        footer_text = " ".join(rows[footer.y:footer.bottom])
        self.assertNotEqual(footer_text.strip(), "",
                            "footer composited blank at 80 columns")
        self.assertLessEqual(board.bottom, footer.y)


class TrailSummaryResolverTests(ByTrailTestBase):
    """t1505_1: the pure resolver behind the By-Trail summary pane."""

    def test_overview_is_preferred_over_recommendation_summary(self):
        self.assertEqual(
            self.ab.trail_summary_text(
                {"narrative": {"overview": "the overview",
                               "recommendation_summary": "the fallback"}}),
            "the overview")

    def test_falls_back_to_recommendation_summary(self):
        """The only live path until t1505_3 adds `narrative.overview`."""
        self.assertEqual(
            self.ab.trail_summary_text(
                {"narrative": {"recommendation_summary": "the fallback"}}),
            "the fallback")

    def test_blank_overview_falls_through_rather_than_winning(self):
        """Whitespace-only is empty at EVERY level — a doc carrying a blank
        `overview` must still show its recommendation_summary, not nothing."""
        self.assertEqual(
            self.ab.trail_summary_text(
                {"narrative": {"overview": "   \n  ",
                               "recommendation_summary": "the fallback"}}),
            "the fallback")

    def test_empty_when_neither_field_carries_text(self):
        for doc in ({}, {"narrative": {}},
                    {"narrative": {"recommendation_summary": "  "}},
                    {"narrative": None}, None,
                    {"narrative": {"recommendation_summary": 123}}):
            with self.subTest(doc=doc):
                self.assertEqual(self.ab.trail_summary_text(doc), "")

    def test_result_is_stripped(self):
        self.assertEqual(
            self.ab.trail_summary_text(
                {"narrative": {"recommendation_summary": "  padded  "}}),
            "padded")


class TrailSummaryPaneTests(ByTrailTestBase):
    """t1505_1: the By-Trail summary pane on the composited frame."""

    SUMMARY_A = "ALPHAMARK first trail summary prose."
    SUMMARY_B = "BETAMARK second trail summary prose."

    @staticmethod
    def _doc(summary: str, *, field: str = "recommendation_summary",
             title: str = "T", hints: dict | None = None) -> dict:
        doc = copy.deepcopy(_load_fixture())
        doc["title"] = title
        doc["narrative"]["recommendation_summary"] = "unused fallback"
        doc["narrative"].pop("overview", None)
        doc["narrative"][field] = summary
        if hints is not None:
            doc["rendering_hints"] = hints
        return doc

    def _pane_rows(self, app, rows) -> str:
        region = app.query_one("#trail_summary").region
        return " ".join(rows[region.y:region.bottom])

    def test_pane_is_visible_in_bytrail_and_shows_the_summary(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(120, 24)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(
                    app, pilot, self._doc(self.SUMMARY_A))
                self.assertTrue(app.query_one("#trail_summary").display)
                self.assertIn("ALPHAMARK",
                              self._pane_rows(app, self._screen_rows(app)))

        self._run(go())

    def test_pane_does_not_overlap_the_footer(self):
        """The docked-sibling guard, on the surface that actually loses.

        Confirmed falsifiable: adding `dock: bottom` to #trail_summary makes
        this fail. Note WHICH widget is the victim — the footer is docked and
        wins the paint, so a docked pane does not eat the footer, it silently
        loses its own last rows to it while still reporting a correct region
        and display=True (t1278). Asserting only that the footer survives
        therefore passes under the very fault this guards.
        """
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(120, 20)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(
                    app, pilot, self._doc(self.SUMMARY_A))
                pane = app.query_one("#trail_summary").region
                footer = app.query_one(ab.MultiRowFooter).region
                self.assertLessEqual(
                    pane.bottom, footer.y,
                    f"summary pane overlaps the footer: pane={pane} "
                    f"footer={footer} — is it docked?")
                # Render-level half: no footer key label may appear on a row
                # the pane owns.
                self.assertNotIn(
                    "Quit", self._pane_rows(app, self._screen_rows(app)),
                    "footer keys composited inside the pane's own rows")

        self._run(go())

    def test_pane_is_absent_outside_bytrail_and_restores_board_height(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(120, 24)) as pilot:
                await pilot.pause()
                tall = app.query_one("#board_container").region.height
                await self._enter_synthetic_bytrail(
                    app, pilot, self._doc(self.SUMMARY_A))
                self.assertTrue(app.query_one("#trail_summary").display)
                shrunk = app.query_one("#board_container").region.height
                self.assertLess(shrunk, tall, "pane took no height from lanes")

                for view in ("all", "bytopic"):
                    app._set_base_filter(view)
                    await pilot.pause()
                    await pilot.pause()
                    self.assertFalse(
                        app.query_one("#trail_summary").display,
                        f"pane still displayed in the {view} view")
                    self.assertNotIn(
                        "ALPHAMARK",
                        "\n".join(self._screen_rows(app)),
                        f"summary text still composited in the {view} view")

                # Back to the view the baseline was measured in — the other
                # views carry different filter-row chrome, so only `all` is a
                # like-for-like comparison.
                app._set_base_filter("all")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(
                    app.query_one("#board_container").region.height, tall,
                    "leaving By-Trail did not restore the full column height")

        self._run(go())

    def test_pane_hidden_when_the_trail_has_no_summary(self):
        """An empty summary hides the pane rather than mounting a blank frame."""
        ab = self.ab

        async def go():
            doc = copy.deepcopy(_load_fixture())
            doc["narrative"]["recommendation_summary"] = "   "
            doc["narrative"].pop("overview", None)
            app = ab.KanbanApp()
            async with app.run_test(size=(120, 24)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, doc)
                self.assertFalse(app.query_one("#trail_summary").display)

        self._run(go())

    def test_bracketed_prose_is_rendered_literally_not_as_markup(self):
        """Trail prose is FREE-FORM: brackets in it are text, not Rich markup.

        Textual's Static defaults to markup=True, and its Content parser
        silently *deletes* an unrecognised tag — `[blocked]` and
        `[risk_mitigation]` (a real followup_kind in this repo) vanish from the
        rendered prose, losing content with no error anywhere. Rendering the
        body through a Text() instead is what keeps it literal.
        """
        ab = self.ab
        summary = ("MARKMARK [blocked] and [risk_mitigation] must survive "
                   "verbatim.")

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(140, 24)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(
                    app, pilot, self._doc(summary))
                pane_text = self._pane_rows(app, self._screen_rows(app))
                self.assertIn("MARKMARK", pane_text)
                self.assertIn("[blocked]", pane_text,
                              "bracketed text eaten as Rich markup")
                self.assertIn("[risk_mitigation]", pane_text,
                              "bracketed text eaten as Rich markup")

        self._run(go())

    def test_markup_like_prose_does_not_raise_on_trail_selection(self):
        """A bracketed URL raises MarkupError in Textual's Content parser.

        The pane body is written from `_refresh_trail_summary`, which
        `_refresh_subtitle` drives — so an unlucky artifact would take down the
        banner and the whole By-Trail refresh, not just the pane, at the moment
        the user selects that trail.
        """
        ab = self.ab
        summary = "See [link=https://example.dev]the docs[/link] for context."

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(140, 24)) as pilot:
                await pilot.pause()
                # Must not raise.
                await self._enter_synthetic_bytrail(
                    app, pilot, self._doc(summary))
                pane_text = self._pane_rows(app, self._screen_rows(app))
                self.assertIn("example.dev", pane_text)
                # The banner still refreshed — the exception did not escape
                # into _refresh_subtitle.
                self.assertIn("By-Trail", app.sub_title)

        self._run(go())

    def _mk_info(self, handle: str, doc: dict) -> object:
        return self.ab.TrailInfo(handle=handle, owner_id="9000",
                                 owner_archived=False, owner_folded=False,
                                 name=doc.get("title", ""), doc=doc)

    def test_switching_trails_replaces_the_summary(self):
        """A→B through `_activate_trail`, the `s` selection seam.

        The assertion that matters is that A's text is GONE: a pane that
        appended, or never repainted, still contains B's text and would pass a
        presence-only check.
        """
        ab = self.ab

        async def go():
            doc_a = self._doc(self.SUMMARY_A, title="Trail A")
            doc_b = self._doc(self.SUMMARY_B, title="Trail B")
            app = ab.KanbanApp()
            async with app.run_test(size=(120, 24)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, doc_a)
                self.assertIn("ALPHAMARK",
                              self._pane_rows(app, self._screen_rows(app)))

                app._trail_infos = [self._mk_info("art:trail-b", doc_b)]
                app._activate_trail("art:trail-b")
                await pilot.pause()
                await pilot.pause()

                pane_text = self._pane_rows(app, self._screen_rows(app))
                self.assertIn("BETAMARK", pane_text)
                self.assertNotIn("ALPHAMARK", pane_text,
                                 "pane still shows the previous trail")

        self._run(go())

    def test_reloading_the_trail_replaces_the_summary(self):
        """The other doc-rewrite seam: `_on_trail_reload` (the `d`/watch path)."""
        ab = self.ab

        async def go():
            doc_a = self._doc(self.SUMMARY_A)
            doc_b = self._doc(self.SUMMARY_B)
            app = ab.KanbanApp()
            async with app.run_test(size=(120, 24)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(
                    app, pilot, doc_a, handle="art:trail-test")
                app._on_trail_reload(app._trail_gen, "art:trail-test",
                                     doc_b, "", ["v2"])
                await pilot.pause()
                await pilot.pause()

                pane_text = self._pane_rows(app, self._screen_rows(app))
                self.assertIn("BETAMARK", pane_text)
                self.assertNotIn("ALPHAMARK", pane_text,
                                 "pane kept the pre-reload summary")

        self._run(go())

    def test_switch_observes_the_overview_preference_end_to_end(self):
        """A carries only recommendation_summary; B carries an overview."""
        ab = self.ab

        async def go():
            doc_a = self._doc(self.SUMMARY_A, title="Trail A")
            doc_b = self._doc(self.SUMMARY_B, field="overview", title="Trail B")
            app = ab.KanbanApp()
            async with app.run_test(size=(120, 24)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, doc_a)
                app._trail_infos = [self._mk_info("art:trail-b", doc_b)]
                app._activate_trail("art:trail-b")
                await pilot.pause()
                await pilot.pause()

                pane_text = self._pane_rows(app, self._screen_rows(app))
                self.assertIn("BETAMARK", pane_text)
                self.assertNotIn("unused fallback", pane_text,
                                 "fell back despite an overview being present")

        self._run(go())


class TrailSummaryExpandTests(ByTrailTestBase):
    """t1505_1: the `v` expand key, its gate and its action guard."""

    @staticmethod
    def _doc(summary="EXPANDMARK the whole summary prose."):
        doc = copy.deepcopy(_load_fixture())
        doc["narrative"]["recommendation_summary"] = summary
        doc["narrative"].pop("overview", None)
        return doc

    def test_v_opens_the_summary_modal_in_bytrail(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, self._doc())
                app.action_focus_board()
                await pilot.pause()
                await pilot.press("v")
                await pilot.pause()
                self.assertIsInstance(app.screen, ab.TrailSummaryScreen)
                self.assertIn(
                    "EXPANDMARK",
                    self._dialog_text(app,
                                      app.screen.query_one("#trail_summary_dialog")))
                await pilot.press("escape")
                await pilot.pause()
                self.assertNotIsInstance(app.screen, ab.TrailSummaryScreen)

        self._run(go())

    def test_modal_shows_the_same_trail_as_the_pane_after_a_switch(self):
        """The modal is built from the resolver's single resolved value, so it
        cannot disagree with the pane about which trail is on screen."""
        ab = self.ab

        async def go():
            doc_b = self._doc("BETAMARK second trail prose.")
            app = ab.KanbanApp()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(
                    app, pilot, self._doc("ALPHAMARK first trail prose."))
                app._trail_infos = [ab.TrailInfo(
                    handle="art:trail-b", owner_id="9000", owner_archived=False,
                    owner_folded=False, name="B", doc=doc_b)]
                app._activate_trail("art:trail-b")
                await pilot.pause()

                app.action_trail_summary_expand()
                await pilot.pause()
                body = self._dialog_text(
                    app, app.screen.query_one("#trail_summary_dialog"))
                self.assertIn("BETAMARK", body)
                self.assertNotIn("ALPHAMARK", body)

        self._run(go())

    def test_modal_renders_bracketed_prose_literally(self):
        """The modal's half of the free-form-prose contract (see the pane test
        of the same name): brackets are content, not Rich markup."""
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(140, 30)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(
                    app, pilot,
                    self._doc("MARKMARK [blocked] stays verbatim here."))
                app.action_trail_summary_expand()
                await pilot.pause()
                body = self._dialog_text(
                    app, app.screen.query_one("#trail_summary_dialog"))
                self.assertIn("MARKMARK", body)
                self.assertIn("[blocked]", body,
                              "modal ate bracketed text as Rich markup")

        self._run(go())

    def test_v_is_gated_and_the_action_guards_itself_outside_bytrail(self):
        """Negative control, both halves.

        `check_action` hides the key; the ACTION must refuse independently,
        because it stays reachable via the command palette, a remap, or a race
        with a view switch — a binding gate is not an action guard.
        """
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                # `all` view: not gated in, and the action is inert.
                self.assertIs(app.check_action("trail_summary_expand", None),
                              False)
                self.assertNotIn("trail_summary_expand",
                                 self._footer_actions(app))
                await pilot.press("v")
                await pilot.pause()
                self.assertNotIsInstance(app.screen, ab.TrailSummaryScreen)

                app.action_trail_summary_expand()
                await pilot.pause()
                self.assertNotIsInstance(
                    app.screen, ab.TrailSummaryScreen,
                    "action fired outside By-Trail despite the guard")

        self._run(go())

    def test_v_is_gated_out_when_the_trail_has_no_summary(self):
        ab = self.ab

        async def go():
            doc = self._doc("   ")
            app = ab.KanbanApp()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, doc)
                self.assertIs(app.check_action("trail_summary_expand", None),
                              False)
                app.action_trail_summary_expand()
                await pilot.pause()
                self.assertNotIsInstance(app.screen, ab.TrailSummaryScreen)

        self._run(go())


class TrailDepthLabelTests(ByTrailTestBase):
    """t1505_1 label_trail_depth: the banner's advisory depth marker."""

    @staticmethod
    def _doc(depth=None):
        doc = copy.deepcopy(_load_fixture())
        doc["title"] = "Depth trail"
        if depth is not None:
            doc["rendering_hints"] = {"depth": depth}
        else:
            doc.pop("rendering_hints", None)
        return doc

    def _banner(self, doc, size=(160, 30)):
        ab = self.ab
        captured = {}

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=size) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot, doc)
                captured["sub"] = app.sub_title
                captured["row0"] = self._screen_rows(app)[0]

        self._run(go())
        return captured

    def test_lite_depth_is_labelled(self):
        got = self._banner(self._doc("lite"))
        self.assertIn("· lite", got["sub"])
        self.assertIn("· lite", got["row0"], "depth never reached the screen")

    def test_deep_depth_is_labelled(self):
        self.assertIn("· deep", self._banner(self._doc("deep"))["sub"])

    def test_absent_hint_renders_nothing_and_never_deep(self):
        """The load-bearing case: every trail written before t1505_4 has no
        hint, so defaulting to "deep" would state a falsehood about all of
        them. Assert the ABSENCE explicitly — "no crash" is not the claim."""
        sub = self._banner(self._doc(None))["sub"]
        self.assertNotIn("deep", sub)
        self.assertNotIn("lite", sub)
        self.assertNotIn(" · ", sub.replace(" · owner", ""))

    def test_unrecognised_depth_is_ignored_not_echoed(self):
        sub = self._banner(self._doc("gigantic-unknown-value"))["sub"]
        self.assertNotIn("gigantic-unknown-value", sub)

    def test_depth_is_dropped_before_the_freshness_marker(self):
        """Narrow-width shed order: depth goes, the volatile marker stays."""
        ab = self.ab
        captured = {}

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(60, 24)) as pilot:
                await pilot.pause()
                await self._enter_synthetic_bytrail(app, pilot,
                                                    self._doc("lite"))
                app._trail_drift = ("STALE", [("stale_status", "aitasks#1", "d")])
                app._refresh_subtitle()
                await pilot.pause()
                captured["sub"] = app.sub_title

        self._run(go())
        self.assertIn("⚠ stale", captured["sub"],
                      "freshness marker lost — it must outlive the depth note")
        self.assertNotIn("· lite", captured["sub"],
                         "depth note survived past its budget")

    def test_banner_is_unchanged_when_no_hint_is_present(self):
        """No-regression control: with no depth hint the banner text must be
        byte-identical to what the pre-t1505_1 ladder produced, at every width.
        This is what proves the change cannot regress the trails that carry no
        hint — which today is all of them."""
        ab = self.ab
        for width in (160, 120, 100, 80, 60, 44):
            with self.subTest(width=width):
                captured = {}

                async def go():
                    app = ab.KanbanApp()
                    async with app.run_test(size=(width, 24)) as pilot:
                        await pilot.pause()
                        await self._enter_synthetic_bytrail(
                            app, pilot, self._doc(None))
                        app._trail_drift = ("STALE",
                                            [("stale_status", "aitasks#1", "d")])
                        # The reference: the exact ladder, called with no depth.
                        captured["ref"] = app._trail_banner(
                            "Depth trail", " (⚠ stale: 1)", "")
                        app._refresh_subtitle()
                        await pilot.pause()
                        captured["live"] = app.sub_title

                self._run(go())
                self.assertEqual(captured["live"], captured["ref"])


if __name__ == "__main__":
    unittest.main()
