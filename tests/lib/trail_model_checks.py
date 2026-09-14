"""Pure projection checks for the By-Trail model (t1794_3).

The seven assertions that exercise the extracted trail model — glyph map,
lane ordering, entry resolution, drift grouping / text / ref spelling /
threading — are written ONCE here and run twice:

* ``TrailModelTests`` in tests/test_board_bytrail_view.py mixes them in with
  ``tv`` = the fixture-loaded board (``self.ab``), i.e. through the board's
  re-exports, exactly as they always ran;
* ``HeadlessTrailModelTests`` in the same file runs them in a fresh
  interpreter with ``tv`` = ``board_trail_view`` imported directly and no
  board loaded — the headless pure core the extraction exists to enable.

Two seams, both supplied by the host TestCase: ``tv`` (the module under test)
and ``_mk_task(filename, status="Ready")`` (a task exposing ``filename`` and
``metadata``; ``ByTrailTestBase`` already provides it). This module imports no
board module and not ``board_fixture``, so the headless run can prove neither
got loaded.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import trail_discovery
import trail_schema

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (REPO_ROOT / "aidocs" / "implementation_trail_examples"
                / "gate_framework.json")


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def ghost_doc() -> dict:
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


class TrailModelChecks:
    """Mixin — the host supplies ``tv`` and ``_mk_task`` (module docstring)."""

    tv = None

    def test_glyph_map_pins_schema_classification_enum(self):
        tv = self.tv
        schema = trail_schema.load_schema()
        enum = schema["$defs"]["entry"]["properties"]["classification"]["enum"]
        self.assertEqual(set(tv.TRAIL_CLASSIFICATION_GLYPHS), set(enum))
        # Wireframe-pinned glyphs (RFC §15).
        self.assertEqual(tv.TRAIL_CLASSIFICATION_GLYPHS["hard_prerequisite"],
                         "◆")
        self.assertEqual(tv.TRAIL_CLASSIFICATION_GLYPHS["core"], "●")
        # All glyphs distinct.
        self.assertEqual(len(set(tv.TRAIL_CLASSIFICATION_GLYPHS.values())),
                         len(tv.TRAIL_CLASSIFICATION_GLYPHS))

    def test_lanes_wave_and_position_order(self):
        tv = self.tv
        doc = copy.deepcopy(load_fixture())
        # Shuffle wave array order and entry order: ordinal/position must win.
        doc["waves"].reverse()
        for wave in doc["waves"]:
            wave["entries"].reverse()
        lanes = tv.build_trail_lanes(doc, {}, "aitasks", lambda _id: None)
        ordinals = [lane.wave["ordinal"] for lane in lanes]
        self.assertEqual(ordinals, sorted(ordinals))
        for lane in lanes:
            positions = [v.entry["position"] for v in lane.entries]
            self.assertEqual(positions, sorted(positions))

    def test_entry_resolution_live_archived_missing_cross_repo(self):
        tv = self.tv
        doc = copy.deepcopy(load_fixture())
        refs = sorted(trail_discovery.trail_entry_refs(doc))
        self.assertTrue(refs and all(r.startswith("aitasks#") for r in refs))
        live_id = refs[0].split("#", 1)[1]
        archived_id = refs[1].split("#", 1)[1]
        tasks_by_id = {live_id: self._mk_task(f"t{live_id}_live.md",
                                              status="Done")}
        archived_done = self._mk_task(f"t{archived_id}_arch.md", status="Done")

        def archived_lookup(task_id):
            return archived_done if task_id == archived_id else None

        lanes = tv.build_trail_lanes(doc, tasks_by_id, "aitasks",
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
        foreign = tv.build_trail_lanes(doc, tasks_by_id, "otherproj",
                                       archived_lookup)
        for lane in foreign:
            for v in lane.entries:
                self.assertEqual(v.ghost_kind, "cross_repo")

        # Unknown local project name (unavailable config) → same, no crash.
        blank = tv.build_trail_lanes(doc, tasks_by_id, "", archived_lookup)
        for lane in blank:
            for v in lane.entries:
                self.assertEqual(v.ghost_kind, "cross_repo")

    def test_drift_by_ref_grouping_and_trail_level_drop(self):
        """t1268: reasons are keyed on the RAW entry ref so ghosts match."""
        tv = self.tv
        reasons = [
            ("status_changed", "aitasks#1", "status 'Ready' -> 'Done'"),
            ("gate_state_changed", "aitasks#1", "pending gates now []"),
            ("task_completed", "otherproj#9", "completed and archived"),
            # Trail-level: no owning card.
            ("input_missing", "-", "plan input unreadable"),
            ("other", "", "unattributable digest mismatch"),
        ]
        by_ref = tv.trail_drift_by_ref(reasons)
        self.assertEqual(set(by_ref), {"aitasks#1", "otherproj#9"})
        self.assertEqual(len(by_ref["aitasks#1"]), 2)
        self.assertNotIn("-", by_ref)
        self.assertEqual(tv.trail_drift_by_ref([]), {})
        self.assertEqual(tv.trail_drift_by_ref(None), {})

    def test_drift_text_bounds_and_truncation(self):
        tv = self.tv
        self.assertEqual(tv._trail_drift_text([]), "")
        one = [("status_changed", "aitasks#1", "status 'Ready' -> 'Done'")]
        text = tv._trail_drift_text(one)
        self.assertIn("status_changed", text)
        self.assertIn("Done", text)
        self.assertNotIn("more", text)
        # Past max_shown, the remainder is summarised rather than dropped.
        many = [("c%d" % i, "aitasks#1", "d%d" % i) for i in range(5)]
        text = tv._trail_drift_text(many, max_shown=2)
        self.assertIn("c0", text)
        self.assertIn("c1", text)
        self.assertNotIn("c2", text)
        self.assertIn("(+3 more)", text)
        # A long detail is truncated, not wrapped into the card unbounded.
        long_one = [("plan_changed", "aitasks#1", "x" * 300)]
        text = tv._trail_drift_text(long_one, max_detail=20)
        self.assertLess(len(text), 80)
        self.assertIn("…", text)
        # Newlines in a detail can never break the single-line marker.
        multi = [("other", "aitasks#1", "line one\nline two")]
        self.assertNotIn("\n", tv._trail_drift_text(multi))

    def test_drift_matches_the_t_prefixed_ref_spelling(self):
        """The trail may store `aitasks#t42`; trail_gather always emits drift
        reasons against the canonical `aitasks#42` (its `inp.canonical`). Both
        sides must be keyed the same way or the owning card renders nothing."""
        tv = self.tv
        self.assertEqual(tv.canonical_trail_ref("aitasks#t42"), "aitasks#42")
        self.assertEqual(tv.canonical_trail_ref("aitasks#42"), "aitasks#42")
        self.assertEqual(tv.canonical_trail_ref("aitasks#t635_3"),
                         "aitasks#635_3")
        # Unparseable refs keep their raw text rather than vanishing.
        self.assertEqual(tv.canonical_trail_ref("garbage"), "garbage")
        self.assertEqual(tv.canonical_trail_ref(None), "")

        doc = ghost_doc()
        doc["waves"][0]["entries"][0]["task"] = "aitasks#t42"   # tolerated
        task = self._mk_task("t42_demo.md")
        # …while the gatherer reports the canonical spelling.
        by_ref = tv.trail_drift_by_ref([
            ("status_changed", "aitasks#42", "status 'Ready' -> 'Implementing'"),
        ])
        lanes = tv.build_trail_lanes(
            doc, {"42": task}, "aitasks", lambda _id: None, by_ref)
        entry = lanes[0].entries[0]
        self.assertEqual(entry.ghost_kind, "", "t-prefixed ref did not resolve")
        self.assertEqual([r[0] for r in entry.drift_reasons],
                         ["status_changed"],
                         "drift reason did not attach to the t-spelled member")
        # And the mirror case: trail stores canonical, gatherer says `t`.
        doc2 = ghost_doc()
        doc2["waves"][0]["entries"][0]["task"] = "aitasks#42"
        by_ref2 = tv.trail_drift_by_ref([
            ("status_changed", "aitasks#t42", "status 'Ready' -> 'Done'"),
        ])
        lanes2 = tv.build_trail_lanes(
            doc2, {"42": task}, "aitasks", lambda _id: None, by_ref2)
        self.assertEqual([r[0] for r in lanes2[0].entries[0].drift_reasons],
                         ["status_changed"])

    def test_build_trail_lanes_threads_drift_to_entries(self):
        """Ghost and live entries alike receive their own reasons."""
        tv = self.tv
        doc = ghost_doc()
        doc["waves"][0]["entries"][0]["task"] = "aitasks#42"
        task = self._mk_task("t42_demo.md")
        by_ref = tv.trail_drift_by_ref([
            ("status_changed", "aitasks#42", "status 'Ready' -> 'Done'"),
            ("task_completed", "otherproj#2", "completed and archived"),
        ])
        lanes = tv.build_trail_lanes(
            doc, {"42": task}, "aitasks", lambda _id: None, by_ref)
        live = lanes[0].entries[0]
        ghost = lanes[1].entries[0]
        self.assertEqual(live.ghost_kind, "")
        self.assertEqual([r[0] for r in live.drift_reasons], ["status_changed"])
        self.assertEqual(ghost.ghost_kind, "cross_repo")
        self.assertEqual([r[0] for r in ghost.drift_reasons], ["task_completed"])
        # Omitting the map keeps every entry clean (back-compatible signature).
        lanes = tv.build_trail_lanes(
            doc, {"42": task}, "aitasks", lambda _id: None)
        self.assertEqual(lanes[0].entries[0].drift_reasons, [])
