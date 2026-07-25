"""By-Trail board view tests (t1210_4).

Covers the pure trail-projection model (build_trail_lanes, overlaps,
fold-aware discovery dedup, glyph pin against the schema enum), render-level
card assertions, live-tree Pilot behavior (view switch, footer gating, ghost
navigation, subtitle restore), the keyboard-vs-timer refresh split, the
worker supersession guard, launch-argument construction spies, and the
read-only negative control (only drift/get/versions verbs are ever spawned).

Fixture docs under aidocs/implementation_trail_examples/ are never mutated —
tests operate on deep copies.
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

FIXTURE_PATH = (REPO_ROOT / "aidocs" / "implementation_trail_examples"
                / "gate_framework.json")


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


class ByTrailTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig_cwd = os.getcwd()
        os.chdir(REPO_ROOT)
        import aitask_board as ab
        cls.ab = ab

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig_cwd)

    def _run(self, coro):
        return asyncio.run(coro)

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


class TrailCardRenderTests(ByTrailTestBase):
    """Render-level assertions on the trail card widgets."""

    def _render_card(self, card, queries: dict) -> dict:
        ab = self.ab
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
                                  lambda manager: []):
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
                          "work_report", "sort_topic", "trail_task")
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
                if not cards:
                    self.skipTest("live tree rendered no task cards")
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
                calls = {"data": 0}
                launches = []
                app._refresh_board_data = (
                    lambda: calls.__setitem__("data", calls["data"] + 1))
                app._launch_trail = (
                    lambda args, suffix: launches.append(list(args)))
                # Timer tick → passive data refresh, no dialog.
                app._auto_refresh_tick()
                self.assertEqual(calls["data"], 1)
                self.assertEqual(launches, [])
                # `r` keypress → the trail refresh launch instead.
                app.action_refresh_board()
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
                if not cards:
                    self.skipTest("live tree rendered no task cards")
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
                    app.action_refresh_board()
                self.assertEqual(len(calls), 1)
                call = calls[0]
                self.assertEqual(call["operation"], "trail")
                self.assertEqual(call["operation_args"],
                                 ["--refresh", "art:trail-demo"])
                self.assertEqual(call["default_window_name"],
                                 "agent-trail-trail-demo")
                self.assertEqual(call["prompt_str"],
                                 "/aitask-trail --refresh art:trail-demo")

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


if __name__ == "__main__":
    unittest.main()
