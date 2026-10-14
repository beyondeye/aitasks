"""The stand-alone `ait trails` TUI (t1794_6): `board/trails_app.py`.

What is pinned, and why each pin is a *keyboard* pin rather than a call:

* **Boot → selector → lanes → detail / summary / refresh / drift**, driven by
  key presses only. No test here ever calls `card.focus()`: the defect this
  App had to design around is that Textual hands focus to a scroll container
  (or to nothing) after a modal closes, so `enter` / `T` stay gated off until a
  click. A test that focuses a card by hand would hide exactly that.
* **Card-focus rescue** — the predicate discrimination test sets up its own
  precondition (a focused `TrailColumn`) and shows the App's predicate moves
  focus to a card while the original "nothing focused" predicate leaves the
  column focused. The resume-hook scenario rebuilds the lanes under an open
  modal and shows focus lands on a card with no key press.
* **Read-only boot** — constructing the App on a tree with no board config
  creates neither `board_config.json` nor `board_config.local.json` (the
  default `TaskManager` does: that is the control).
* **`T` policy** (C10) — live member → one launch with `op_args == ["<id>"]`;
  ghost / nothing focused → no launch, one notify.
* **One owner for the trail keys** (C10) — every `TrailsApp` binding but the
  two mixin rows has an identical `(action, key, description)` twin on
  `KanbanApp`; a `shortcuts.board.*` override rebinds BOTH Apps; an override
  under a hypothetical `trails` scope changes nothing.
* **Declared-but-hidden `M` / `S`** — present in `BINDINGS`, `check_action`
  False, absent from `active_bindings`, and a spy records zero calls after the
  default key and after a remapped one. `m` / `z` are not declared at all.
* **CSS single-sourcing** (C7) and the **no-`aitask_board`-import** contract
  (C1), the latter in a fresh interpreter.

Reaches the board only as `self.ab` and the trails app only through
`bf.load_trails_app()` / `bf.make_trails_app()` — never a canonical import.

Run: bash tests/run_all_python_tests.sh
  or: ~/.aitask/venv/bin/python -m pytest tests/test_trails_app.py -q
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402
import keybinding_registry  # noqa: E402
from test_board_bytrail_view import (  # noqa: E402
    GatedCalls, NoteRecorder, _wave_doc, _xdep_doc, linked_scan, linked_trail,
)
from trail_discovery import TrailInfo  # noqa: E402

HANDLE = "art:trail-standalone"
GHOST_REF = "99999"


def _rule_lines(css: str) -> list[str]:
    return [line.strip() for line in css.splitlines()
            if "{" in line and not line.strip().startswith("/*")]


class TrailsAppTestBase(bf.FixtureBoardTestBase, unittest.TestCase):
    """One fixture tree per class; a trail over its first two parents plus a
    ghost, served by a patched `discover_trails` on `board_trail_screen`."""

    def _run(self, coro):
        return asyncio.run(coro)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ta = bf.load_trails_app()
        cls.ts = cls.ab.board_trail_screen
        names = sorted(p.name for p in cls.tasks_dir_of().glob("t*.md"))
        cls.member_files = names[:2]
        cls.member_ids = [n.split("_")[0][1:] for n in cls.member_files]

    @classmethod
    def tasks_dir_of(cls) -> Path:
        return cls.tree / "aitasks"

    def _info(self, doc=None):
        return TrailInfo(handle=HANDLE, owner_id=self.member_ids[0],
                         owner_archived=False, owner_folded=False,
                         name="Standalone",
                         doc=doc or _wave_doc([*self.member_ids, GHOST_REF]))

    def _patches(self, drift=("CURRENT", [])):
        return [
            patch.object(self.ts, "discover_trails",
                         lambda: ([self._info()], [])),
            patch.object(self.ts, "run_trail_drift", lambda handle: drift),
        ]

    async def _settle(self, app, pilot):
        """Let every thread worker (discovery, drift, reload) finish, its UI
        callback land, and the re-mount that callback queues complete.

        The drift callback re-mounts the lanes and queues a refocus; a key
        pressed between the callback and the re-mount would land on a card the
        re-mount is about to remove. So beyond the workers, wait until the
        rendered card set and the focused widget are stable across two
        consecutive pauses (bounded — a loaded worker pool stretches this)."""
        for _ in range(3):
            await app.workers.wait_for_complete()
            await pilot.pause()
        previous = None
        for _ in range(40):
            # `call_after_refresh` callbacks (the queued refocus and rescue) run
            # on the NEXT refresh; headless, none may be pending, so the next
            # key press would be the refresh that fires them — after the key
            # moved focus. Force one so they fire here instead.
            app.screen.refresh(layout=True)
            await pilot.pause()
            state = (tuple(id(c) for c in app.query(self.ab.TaskCard)),
                     id(app.screen.focused), type(app.screen).__name__)
            if state == previous:
                break
            previous = state

    async def _boot_and_select(self, app, pilot):
        """Boot into the selector and choose the fixture trail with `enter`."""
        await self._settle(app, pilot)
        self.assertIsInstance(app.screen, self.ab.board_trail_view.TrailSelectScreen)
        await pilot.press("enter")
        await self._settle(app, pilot)
        self.assertIsInstance(app.screen, self.ta.TrailsScreen)

    async def _wait_screen(self, app, pilot, cls, tries: int = 40):
        """Pause until `app.screen` is a `cls` — latency-tolerant, never
        re-presses a key, and fails if the screen never arrives."""
        for _ in range(tries):
            if isinstance(app.screen, cls):
                return
            await pilot.pause()
        self.fail(f"expected {cls.__name__}, screen is {type(app.screen).__name__}")

    async def _wait_until(self, pilot, predicate, tries: int = 40):
        """Pause until `predicate()` holds; latency-tolerant, never re-presses."""
        for _ in range(tries):
            if predicate():
                return
            await pilot.pause()
        self.fail("condition never became true")

    def _focused_filename(self, app):
        card = app._focused_card()
        return card.task_data.filename if card is not None else None


# --- keyboard-only flows -------------------------------------------------------


class KeyboardFlowTests(TrailsAppTestBase):

    def test_boot_selects_navigates_and_opens_the_modals_by_keys_alone(self):
        async def go():
            app = bf.make_trails_app()
            with self._patches()[0], self._patches()[1]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    # Lanes rendered; focus landed on a card with no click.
                    cards = list(app.query(self.ab.TaskCard))
                    self.assertEqual(
                        [type(c).__name__ for c in cards],
                        ["TrailTaskCard", "TrailTaskCard", "TrailGhostCard"])
                    self.assertEqual(self._focused_filename(app),
                                     self.member_files[0])
                    self.assertIn("By-Trail:", app.sub_title)
                    # Arrows walk the wave.
                    await pilot.press("down")
                    await self._wait_until(
                        pilot, lambda: self._focused_filename(app) == self.member_files[1])
                    await pilot.press("up")
                    await self._wait_until(
                        pilot, lambda: self._focused_filename(app) == self.member_files[0])
                    # enter → detail, escape → a card is focused again.
                    await pilot.press("enter")
                    await self._wait_screen(
                        app, pilot, self.ab.board_trail_view.TrailDetailScreen)
                    await pilot.press("escape")
                    await self._settle(app, pilot)
                    self.assertIsNotNone(app._focused_card())
                    # v → summary (the fixture doc has narrative text).
                    await pilot.press("v")
                    await self._wait_screen(
                        app, pilot, self.ab.board_trail_view.TrailSummaryScreen)
                    await pilot.press("escape")
                    await self._settle(app, pilot)
                    self.assertIsNotNone(app._focused_card())
                    # r → local refresh keeps the view and the focus.
                    await pilot.press("r")
                    await self._settle(app, pilot)
                    self.assertEqual(len(app.query(self.ab.TaskCard)), 3)
                    self.assertIsNotNone(app._focused_card())
                    # d → drift re-run through the patched checker.
                    with patch.object(self.ts, "load_trail_blob",
                                      lambda h: (self._info().doc, "", [])), \
                            patch.object(self.ts, "run_trail_drift",
                                         lambda h: ("STALE", [
                                             ("status_changed",
                                              f"aitasks#{self.member_ids[0]}",
                                              "Ready -> Done")])):
                        await pilot.press("d")
                        await self._settle(app, pilot)
                    self.assertEqual(app._trail_drift[0], "STALE")
                    self.assertIn("stale", app.sub_title)
                    self.assertIsNotNone(app._focused_card())
                    await self._settle(app, pilot)
                    self.assertNoLiveWorkers(app)
        self._run(go())

    def test_lateral_navigation_crosses_waves(self):
        doc = _wave_doc([self.member_ids[0]])
        doc["waves"].append(
            _wave_doc([self.member_ids[1]], ordinal=2)["waves"][0])

        async def go():
            app = bf.make_trails_app()
            with patch.object(self.ts, "discover_trails",
                              lambda: ([self._info(doc)], [])), \
                    patch.object(self.ts, "run_trail_drift",
                                 lambda h: ("CURRENT", [])):
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    self.assertEqual(len(app.query(self.ta.TrailColumn)), 2)
                    self.assertEqual(self._focused_filename(app),
                                     self.member_files[0])
                    await pilot.press("right")
                    await self._wait_until(
                        pilot, lambda: self._focused_filename(app) == self.member_files[1])
                    await pilot.press("left")
                    await self._wait_until(
                        pilot, lambda: self._focused_filename(app) == self.member_files[0])
                    await self._settle(app, pilot)
        self._run(go())

    def test_no_trail_selected_has_its_own_subtitle(self):
        async def go():
            app = bf.make_trails_app()
            with self._patches()[0], self._patches()[1]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._settle(app, pilot)
                    await pilot.press("escape")      # cancel the selector
                    await self._settle(app, pilot)
                    self.assertIsNone(app.active_trail_handle)
                    self.assertNotIn("Auto-refresh", app.sub_title)
                    self.assertIn("no trail selected", app.sub_title)
        self._run(go())


# --- card-focus rescue -----------------------------------------------------------


class FocusRescueTests(TrailsAppTestBase):

    async def _active_app(self, app, pilot):
        await self._boot_and_select(app, pilot)
        self.assertIsNotNone(app._focused_card())

    def test_rescue_predicate_moves_focus_off_a_focused_column(self):
        """Own precondition: a `TrailColumn` (a focusable VerticalScroll) holds
        focus. The App's predicate ("no TaskCard focused") rescues; the
        original "nothing focused" predicate does not — the negative control."""
        async def go():
            app = bf.make_trails_app()
            with self._patches()[0], self._patches()[1]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._active_app(app, pilot)
                    column = app.query(self.ta.TrailColumn).first()

                    async def focus_column():
                        column.focus()
                        await pilot.pause()
                        self.assertIs(app.screen.focused, column)

                    await focus_column()
                    app.apply_filter()
                    await pilot.pause()
                    self.assertIsInstance(app.screen.focused, self.ab.TaskCard)

                    # Negative control: the pre-t1794_6 predicate.
                    await focus_column()
                    with patch.object(
                            type(app), "_focused_card",
                            lambda self_: (None if self_.screen.focused is None
                                           else self_.screen.focused)):
                        app.apply_filter()
                        await pilot.pause()
                    self.assertIs(app.screen.focused, column)
                    await self._settle(app, pilot)
        self._run(go())

    def test_rescue_predicate_moves_focus_off_a_detached_card(self):
        """The second precondition the rescue exists for: `screen.focused` still
        names a card a lane re-render REMOVED (found as a flake in this very
        suite — the binding chain of a detached widget reaches nothing, so every
        key is dead). Own precondition: remove the focused card and hand focus
        back to the detached object. The App's predicate rescues; the
        "any TaskCard" predicate — attachment unchecked — is the negative
        control and leaves the dead card focused."""
        async def go():
            app = bf.make_trails_app()
            with self._patches()[0], self._patches()[1]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._active_app(app, pilot)

                    async def focus_detached():
                        card = app._focused_card()
                        await card.remove()
                        await pilot.pause()
                        app.screen.set_focus(card)
                        await pilot.pause()
                        self.assertIs(app.screen.focused, card)
                        self.assertFalse(card.is_attached)
                        return card

                    dead = await focus_detached()
                    app.apply_filter()
                    await pilot.pause()
                    live = app.screen.focused
                    self.assertIsInstance(live, self.ab.TaskCard)
                    self.assertTrue(live.is_attached)
                    self.assertIsNot(live, dead)

                    dead = await focus_detached()
                    with patch.object(
                            type(app), "_focused_card",
                            lambda self_: (self_.screen.focused
                                           if isinstance(self_.screen.focused,
                                                         self.ab.TaskCard)
                                           else None)):
                        app.apply_filter()
                        await pilot.pause()
                    self.assertIs(app.screen.focused, dead)
                    await self._settle(app, pilot)
        self._run(go())

    def test_resume_hook_reanchors_focus_after_lanes_change_under_a_modal(self):
        async def scenario(app, pilot, hook_live: bool):
            await self._active_app(app, pilot)
            await pilot.press("v")
            await self._wait_screen(
                app, pilot, self.ab.board_trail_view.TrailSummaryScreen)
            # The lanes are rebuilt underneath the open dialog (the shape of a
            # drift / reload callback landing while a modal is up); the card
            # Textual remembered for the base screen no longer exists.
            if hook_live:
                app.refresh_board()
            else:
                # Control: the same rebuild with BOTH rescues out of the way —
                # the resume hook and the post-render one.
                with patch.object(self.ta.TrailsScreen, "on_screen_resume",
                                  lambda s: None), \
                        patch.object(type(app), "apply_filter",
                                     lambda s, cols=None: None):
                    app.refresh_board()
                    await pilot.pause()
                    await pilot.press("escape")
                    await self._settle(app, pilot)
                return
            await pilot.pause()
            await pilot.press("escape")
            await self._settle(app, pilot)

        async def go():
            for hook_live in (True, False):
                app = bf.make_trails_app()
                with self._patches()[0], self._patches()[1]:
                    async with app.run_test(size=(200, 48)) as pilot:
                        await scenario(app, pilot, hook_live)
                        self.assertIsInstance(app.screen, self.ta.TrailsScreen)
                        if hook_live:
                            self.assertIsNotNone(
                                app._focused_card(),
                                "the resume hook must re-anchor focus on a card")
                        else:
                            self.assertIsNone(
                                app._focused_card(),
                                "control: with both rescues disabled no card "
                                "is focused after the modal closes")
                        await self._settle(app, pilot)
        self._run(go())


# --- read-only boot --------------------------------------------------------------


class ReadOnlyBootTests(unittest.TestCase):
    """A tree with no board configuration: the trails app writes nothing."""

    CONFIGS = ("board_config.json", "board_config.local.json")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="trails_readonly_")
        self.addCleanup(self.tmp.cleanup)
        self.tree = bf.build_fixture_tree(Path(self.tmp.name), bf.DEFAULT_TOPOLOGY)
        self.tasks = self.tree / "aitasks"
        for name in self.CONFIGS:
            (self.tasks / "metadata" / name).unlink(missing_ok=True)
        self.ta = bf.load_trails_app()

    def _configs_present(self) -> list[str]:
        return [n for n in self.CONFIGS if (self.tasks / "metadata" / n).exists()]

    def _app(self):
        return self.ta.TrailsApp(
            tasks_dir=self.tasks,
            metadata_file=self.tasks / "metadata" / "board_config.json",
            gates_registry_file=self.tasks / "metadata" / "gates.yaml")

    def test_boot_and_selection_leave_the_tree_untouched(self):
        import board_trail_screen as ts_canonical  # the same module the App binds
        before = bf.snapshot(self.tree)
        ids = sorted(p.name.split("_")[0][1:] for p in self.tasks.glob("t*.md"))[:2]
        info = TrailInfo(handle=HANDLE, owner_id=ids[0], owner_archived=False,
                         owner_folded=False, name="ro", doc=_wave_doc(ids))

        async def go():
            app = self._app()
            with patch.object(ts_canonical, "discover_trails",
                              lambda: ([info], [])), \
                    patch.object(ts_canonical, "run_trail_drift",
                                 lambda h: ("CURRENT", [])):
                async with app.run_test(size=(200, 48)) as pilot:
                    for _ in range(3):
                        await app.workers.wait_for_complete()
                        await pilot.pause()
                    await pilot.press("enter")
                    for _ in range(3):
                        await app.workers.wait_for_complete()
                        await pilot.pause()
                    self.assertEqual(len(app.query(self.ta.TaskCard)), 2)
        asyncio.run(go())
        self.assertEqual(self._configs_present(), [])
        self.assertEqual(bf.diff_snapshots(before, bf.snapshot(self.tree)),
                         {"added": set(), "removed": set(), "changed": set()})

    def test_control_the_default_manager_first_ships_the_config(self):
        import board_task_manager as btm
        self.assertEqual(self._configs_present(), [])
        btm.TaskManager(tasks_dir=self.tasks,
                        metadata_file=self.tasks / "metadata" / "board_config.json",
                        gates_registry_file=self.tasks / "metadata" / "gates.yaml")
        self.assertEqual(self._configs_present(), list(self.CONFIGS))


# --- the T policy ----------------------------------------------------------------


class TrailTaskPolicyTests(TrailsAppTestBase):

    def _seam(self, app):
        launches = []

        class FakeScreen:
            def __init__(self, title, full_command, prompt_str, **kwargs):
                launches.append({"prompt_str": prompt_str, **kwargs})
                self.full_command = full_command

        notes = []
        patches = [
            patch.object(self.ts, "AgentCommandScreen", FakeScreen),
            patch.object(self.ts, "resolve_dry_run_command",
                         lambda root, op, *a, **k: f"CMD {op}"),
            patch.object(self.ts, "resolve_agent_string",
                         lambda root, op: "claudecode/test"),
            patch.object(app, "push_screen", lambda screen, cb=None: None),
            patch.object(app, "notify",
                         lambda message, *a, **k: notes.append(message)),
        ]
        return launches, notes, patches

    def test_live_member_ghost_and_nothing_focused(self):
        async def go():
            app = bf.make_trails_app()
            with self._patches()[0], self._patches()[1]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    launches, notes, patches = self._seam(app)
                    for ctx in patches:
                        ctx.start()
                    try:
                        # Live local member under focus → exactly one launch.
                        self.assertEqual(self._focused_filename(app),
                                         self.member_files[0])
                        self.assertTrue(app.check_action("trail_task", ()))
                        await pilot.press("T")
                        await self._wait_until(pilot, lambda: launches or notes)
                        self.assertEqual(
                            [l["operation_args"] for l in launches],
                            [[self.member_ids[0]]])
                        self.assertEqual(notes, [])
                        # Ghost card → no launch, one visible refusal.
                        await pilot.press("down")
                        await pilot.press("down")
                        await self._wait_until(
                            pilot, lambda: getattr(app._focused_card(),
                                                   "is_ghost", False))
                        await pilot.press("T")
                        await self._wait_until(pilot, lambda: notes)
                        for _ in range(3):
                            await pilot.pause()
                        self.assertEqual(len(launches), 1)
                        self.assertEqual(len(notes), 1)
                        self.assertIn("live local task", notes[0])
                        # Nothing focused → the key is not even advertised, and
                        # the policy itself refuses.
                        app.screen.set_focus(None)
                        await pilot.pause()
                        self.assertFalse(app.check_action("trail_task", ()))
                        self.assertIsNone(app._trail_task_target())
                        self.assertEqual(len(launches), 1)
                    finally:
                        for ctx in patches:
                            ctx.stop()
                    await self._settle(app, pilot)
        self._run(go())


# --- the p policy (t1946) --------------------------------------------------------


OVERRIDE = "opencode run --model x '/aitask-pick 1'"


class _PickScreen:
    """A real-shaped dialog result: only `full_command` is read back."""

    def __init__(self, full_command="cmd --go"):
        self.full_command = full_command


class PickPolicyTests(TrailsAppTestBase):
    """`p` on the focused member: the same `/aitask-pick` dialog as the board
    for a live local member; hidden and refused on a ghost or with no focus."""

    def _seam(self, app, *, focused_existing=False, resolved=True):
        built, notes, pushed, runs = [], [], [], []

        def _build(root, task_id, narrow=False):
            built.append((root, task_id, narrow))
            return _PickScreen() if resolved else None

        patches = [
            patch.object(self.ta, "build_pick_screen", _build),
            patch.object(self.ta, "focus_existing_agent_window",
                         lambda task_id, root: focused_existing),
            patch.object(app, "push_screen",
                         lambda screen, cb=None: pushed.append((screen, cb))),
            patch.object(app, "notify",
                         lambda message, *a, **k: notes.append(
                             (message, k.get("severity", "information")))),
            patch.object(app, "run_dialog_command",
                         lambda cmd, **k: runs.append((cmd, k))),
        ]
        return built, notes, pushed, runs, patches

    def _go(self, body, **seam_kw):
        async def go():
            app = bf.make_trails_app()
            with self._patches()[0], self._patches()[1]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    built, notes, pushed, runs, patches = self._seam(app, **seam_kw)
                    for ctx in patches:
                        ctx.start()
                    try:
                        await body(app, pilot, built, notes, pushed, runs)
                    finally:
                        for ctx in patches:
                            ctx.stop()
        self._run(go())

    def test_live_member_opens_the_pick_dialog(self):
        async def body(app, pilot, built, notes, pushed, runs):
            self.assertEqual(self._focused_filename(app), self.member_files[0])
            self.assertTrue(app.check_action("pick_task", ()))
            active = {b.binding.action for b in app.screen.active_bindings.values()}
            self.assertIn("pick_task", active)
            await pilot.press("p")
            await self._wait_until(pilot, lambda: pushed or notes)
            self.assertEqual(built, [(Path("."), self.member_ids[0], False)])
            self.assertEqual(len(pushed), 1)
            self.assertIsInstance(pushed[0][0], _PickScreen)
            self.assertEqual(notes, [])
        self._go(body)

    def test_ghost_and_no_focus_hide_p_and_refuse_visibly(self):
        async def body(app, pilot, built, notes, pushed, runs):
            await pilot.press("down")
            await pilot.press("down")
            await self._wait_until(
                pilot, lambda: getattr(app._focused_card(), "is_ghost", False))
            self.assertFalse(app.check_action("pick_task", ()))
            active = {b.binding.action for b in app.screen.active_bindings.values()}
            self.assertNotIn("pick_task", active)
            await pilot.press("p")          # hidden: not dispatched at all
            for _ in range(3):
                await pilot.pause()
            self.assertEqual((built, notes, pushed), ([], [], []))
            # A remapped key / the command palette reach the action itself.
            app.action_pick_task()
            self.assertEqual(notes, [("Pick needs a live local task under focus",
                                      "warning")])
            app.screen.set_focus(None)
            await pilot.pause()
            self.assertFalse(app.check_action("pick_task", ()))
            app.action_pick_task()
            self.assertEqual(len(notes), 2)
            self.assertEqual((built, pushed, runs), ([], [], []))
        self._go(body)

    def test_running_agent_window_is_focused_instead_of_a_second_launch(self):
        async def body(app, pilot, built, notes, pushed, runs):
            await pilot.press("p")
            await self._wait_until(pilot, lambda: notes)
            self.assertEqual(notes, [(
                f"Switched to existing agent window for t{self.member_ids[0]}",
                "information")])
            self.assertEqual((built, pushed, runs), ([], [], []))
        self._go(body, focused_existing=True)

    def test_unresolved_command_launches_directly(self):
        async def body(app, pilot, built, notes, pushed, runs):
            await pilot.press("p")
            await self._wait_until(pilot, lambda: runs)
            self.assertEqual(pushed, [])
            self.assertEqual(notes[0][0],
                             "Could not resolve agent command — launching directly")
            self.assertEqual(runs, [(
                f".aitask-scripts/aitask_codeagent.sh invoke pick {self.member_ids[0]}",
                {"refocus_filename": self.member_files[0]})])
        self._go(body, resolved=False)


class PickCallbackTests(TrailsAppTestBase):
    """The trails dialog-result policy, driven through the captured callback on
    a stub host (the policy is this host's own — not the board's)."""

    FILE = "t1_alpha.md"

    def _open(self):
        host = SimpleNamespace(
            log=[], notes=[], pushed=[],
            _modal_is_active=lambda: False,
            _live_member_id=lambda: "1",
            _focused_card=lambda: SimpleNamespace(
                task_data=SimpleNamespace(filename=self.FILE)),
        )
        host.notify = lambda msg, severity="information", **k: (
            host.notes.append((msg, severity)), host.log.append(("notify", msg)))
        host.push_screen = lambda screen, cb=None: host.pushed.append((screen, cb))
        host.run_dialog_command = lambda cmd, **k: host.log.append(("run", cmd, k))
        host.refresh_board = lambda **k: host.log.append(("refresh", k))
        self.launch_result = (1234, None)

        def _launch(cmd, cfg):
            host.log.append(("launch", cmd, cfg))
            return self.launch_result

        for name, stub in (
                ("build_pick_screen", lambda root, tid, narrow=False: _PickScreen()),
                ("focus_existing_agent_window", lambda tid, root: False),
                ("launch_in_tmux", _launch),
                ("maybe_spawn_minimonitor",
                 lambda sess, win: host.log.append(("spawn", sess, win)))):
            p = patch.object(self.ta, name, stub)
            p.start()
            self.addCleanup(p.stop)
        self.ta.TrailsApp.action_pick_task(host)
        self.assertEqual(len(host.pushed), 1)
        screen, callback = host.pushed[0]
        screen.full_command = OVERRIDE      # an in-dialog edit
        host.log.clear()
        return host, callback

    def _cfg(self, new_window):
        return self.ta.TmuxLaunchConfig(session="s", window="agent-pick-1",
                                        new_session=False, new_window=new_window)

    def test_run_dispatches_the_edited_command(self):
        host, callback = self._open()
        callback("run")
        self.assertEqual(host.log, [
            ("run", OVERRIDE, {"refocus_filename": self.FILE})])

    def test_new_window_launch_spawns_the_companion_then_rerenders(self):
        host, callback = self._open()
        cfg = self._cfg(new_window=True)
        callback(cfg)
        self.assertEqual(host.log, [
            ("launch", OVERRIDE, cfg), ("spawn", "s", "agent-pick-1"),
            ("refresh", {"refocus_filename": self.FILE})])

    def test_existing_window_launch_spawns_no_companion(self):
        host, callback = self._open()
        cfg = self._cfg(new_window=False)
        callback(cfg)
        self.assertEqual(host.log, [
            ("launch", OVERRIDE, cfg),
            ("refresh", {"refocus_filename": self.FILE})])

    def test_launch_error_notifies_only(self):
        host, callback = self._open()
        self.launch_result = (None, "tmux new-window failed")
        cfg = self._cfg(new_window=True)
        callback(cfg)
        self.assertEqual(host.log, [("launch", OVERRIDE, cfg),
                                    ("notify", "tmux new-window failed")])
        self.assertEqual(host.notes, [("tmux new-window failed", "error")])

    def test_cancel_changes_nothing(self):
        host, callback = self._open()
        callback(None)
        self.assertEqual(host.log, [])


# --- one owner for the trail keys (C10) ----------------------------------------


MIXIN_ACTIONS = {"tui_switcher", "open_shortcuts_editor"}


def _rows(bindings) -> dict[str, tuple[str, str]]:
    out = {}
    for b in bindings:
        out.setdefault(b.action, (b.key, b.description))
    return out


class BindingOwnershipTests(TrailsAppTestBase):

    def test_every_trails_row_has_an_identical_board_twin(self):
        board = _rows(self.ab.KanbanApp.BINDINGS)
        tab_actions = {b.action for b in self.ta.TRAIL_TAB_BINDINGS}
        for b in self.ta.TrailsApp.BINDINGS:
            if b.action in MIXIN_ACTIONS or b.action in tab_actions:
                continue
            with self.subTest(action=b.action):
                self.assertIn(b.action, board)
                self.assertEqual((b.key, b.description), board[b.action])

    def test_the_tab_rows_are_trails_only_and_collide_with_no_board_row(self):
        """The tab keys (t1895) are this App's own `board`-scope rows: the board
        declares none of their actions and binds none of their keys, so they
        can neither shadow nor be shadowed by a Kanban row."""
        tab_rows = self.ta.TRAIL_TAB_BINDINGS
        self.assertTrue(tab_rows)
        board_actions = {b.action for b in self.ab.KanbanApp.BINDINGS}
        board_keys = {k for b in self.ab.KanbanApp.BINDINGS
                      for k in b.key.split(",")}
        for b in tab_rows:
            with self.subTest(action=b.action):
                self.assertIn(b, self.ta.TrailsApp.BINDINGS)
                self.assertNotIn(b.action, board_actions)
                self.assertNotIn(b.key, board_keys)

    def test_the_pick_binding_is_one_object_in_both_apps(self):
        """`p` (t1946): the board's row and the trails row are the SAME Binding,
        so a `shortcuts.board.pick_task` override cannot split them."""
        trails = [b for b in self.ta.TrailsApp.BINDINGS if b.action == "pick_task"]
        board = [b for b in self.ab.KanbanApp.BINDINGS if b.action == "pick_task"]
        self.assertEqual(len(trails), 1)
        self.assertEqual(len(board), 1)
        self.assertIs(trails[0], self.ts.PICK_BINDING)
        self.assertIs(board[0], self.ts.PICK_BINDING)

    def test_the_trail_binding_objects_are_shared_by_identity(self):
        declared = [b for b in self.ta.TrailsApp.BINDINGS
                    if b.action in self.ts.TRAIL_BINDING]
        self.assertEqual(len(declared), len(self.ts.TRAIL_BINDINGS))
        for b in declared:
            self.assertIs(b, self.ts.TRAIL_BINDING[b.action])

    def test_the_scope_is_board_and_m_z_are_not_declared(self):
        self.assertEqual(self.ta.TrailsApp._shortcuts_scope, "board")
        actions = {b.action for b in self.ta.TrailsApp.BINDINGS}
        self.assertNotIn("move_to_column", actions)
        self.assertNotIn("view_bytrail", actions)
        keys = {b.key for b in self.ta.TrailsApp.BINDINGS}
        self.assertNotIn("m", keys)
        self.assertNotIn("z", keys)
        self.assertIn("trail_move_wave", actions)
        self.assertIn("trail_sync", actions)


class OverridePropagationTests(TrailsAppTestBase):
    """A `shortcuts.board.*` override rebinds both Apps; a `trails` scope is inert.

    The override file is the fixture tree's `userconfig.yaml` (cwd-relative, as
    the registry resolves it). The registry cache is dropped around every case
    so each App construction re-reads the file."""

    def _userconfig(self) -> Path:
        return self.tasks_dir / "metadata" / "userconfig.yaml"

    def _with_override(self, text: str):
        path = self._userconfig()
        path.write_text(text, encoding="utf-8")
        keybinding_registry.refresh()
        self.addCleanup(keybinding_registry.refresh)
        self.addCleanup(path.unlink, missing_ok=True)

    def _key_for(self, app, action: str) -> str:
        return next(b.key for b in app.BINDINGS if b.action == action)

    async def _x_opens_selector(self, app, pilot, expect: bool):
        await self._settle(app, pilot)
        await pilot.press("escape")          # close the boot-time selector
        await self._settle(app, pilot)
        await pilot.press("x")
        await self._settle(app, pilot)
        opened = isinstance(app.screen,
                            self.ab.board_trail_view.TrailSelectScreen)
        self.assertEqual(opened, expect)
        if opened:
            await pilot.press("escape")
            await self._settle(app, pilot)

    def test_a_board_scope_override_rebinds_both_apps(self):
        self._with_override("shortcuts:\n  board:\n    trail_select: x\n")
        trails = bf.make_trails_app()
        board = self.ab.KanbanApp()
        self.assertEqual(self._key_for(trails, "trail_select"), "x")
        self.assertEqual(self._key_for(board, "trail_select"), "x")

        async def go():
            with self._patches()[0], self._patches()[1]:
                async with trails.run_test(size=(200, 48)) as pilot:
                    await self._x_opens_selector(trails, pilot, expect=True)
        self._run(go())

    def test_a_board_scope_pick_override_rebinds_both_apps(self):
        self._with_override("shortcuts:\n  board:\n    pick_task: o\n")
        trails = bf.make_trails_app()
        board = self.ab.KanbanApp()
        self.assertEqual(self._key_for(trails, "pick_task"), "o")
        self.assertEqual(self._key_for(board, "pick_task"), "o")

    def test_a_trails_scope_override_changes_nothing(self):
        self._with_override("shortcuts:\n  trails:\n    trail_select: x\n")
        trails = bf.make_trails_app()
        board = self.ab.KanbanApp()
        self.assertEqual(self._key_for(trails, "trail_select"), "s")
        self.assertEqual(self._key_for(board, "trail_select"), "s")

        async def go():
            with self._patches()[0], self._patches()[1]:
                async with trails.run_test(size=(200, 48)) as pilot:
                    await self._x_opens_selector(trails, pilot, expect=False)
        self._run(go())


class DeclaredButHiddenTests(TrailsAppTestBase):

    async def _press_and_count(self, app, pilot, keys):
        calls = {"trail_move_wave": 0, "trail_sync": 0}

        def spy(name):
            def _spy(*a, **k):
                calls[name] += 1
            return _spy

        with patch.object(app, "action_trail_move_wave", spy("trail_move_wave")), \
                patch.object(app, "action_trail_sync", spy("trail_sync")):
            for key in keys:
                await pilot.press(key)
                await pilot.pause()
        return calls

    def test_m_and_s_are_declared_hidden_and_non_dispatching(self):
        async def go():
            app = bf.make_trails_app()
            with self._patches()[0], self._patches()[1]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    for action in ("trail_move_wave", "trail_sync"):
                        self.assertFalse(app.check_action(action, ()))
                        self.assertFalse(app._has_trail_capability(action))
                    active = {b.binding.action
                              for b in app.screen.active_bindings.values()}
                    self.assertNotIn("trail_move_wave", active)
                    self.assertNotIn("trail_sync", active)
                    self.assertIn("trail_task", active)
                    calls = await self._press_and_count(app, pilot, ["M", "S"])
                    self.assertEqual(calls, {"trail_move_wave": 0, "trail_sync": 0})
                    await self._settle(app, pilot)
        self._run(go())

    def test_a_remapped_key_does_not_reach_them_either(self):
        path = self.tasks_dir / "metadata" / "userconfig.yaml"
        path.write_text("shortcuts:\n  board:\n    trail_move_wave: k\n"
                        "    trail_sync: K\n", encoding="utf-8")
        keybinding_registry.refresh()
        self.addCleanup(keybinding_registry.refresh)
        self.addCleanup(path.unlink, missing_ok=True)

        async def go():
            app = bf.make_trails_app()
            self.assertEqual(
                next(b.key for b in app.BINDINGS if b.action == "trail_move_wave"),
                "k")
            with self._patches()[0], self._patches()[1]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    calls = await self._press_and_count(app, pilot, ["k", "K"])
                    self.assertEqual(calls, {"trail_move_wave": 0, "trail_sync": 0})
                    await self._settle(app, pilot)
        self._run(go())


# --- CSS single-sourcing and the import contract --------------------------------


class CssAndImportContractTests(TrailsAppTestBase):

    def test_trail_and_widget_css_are_in_both_apps(self):
        bw = self.ab.board_widgets
        bv = self.ab.board_trail_view
        for label, css in (("KanbanApp", self.ab.KanbanApp.CSS),
                           ("TrailsApp", self.ta.TrailsApp.CSS)):
            with self.subTest(app=label):
                self.assertIn(bv.TRAIL_CSS, css)
                self.assertIn(bw.WIDGET_CSS, css)
                self.assertTrue(css.startswith(bw.WIDGET_CSS),
                                "WIDGET_CSS must be PREPENDED (rule order)")

    def test_each_widget_rule_appears_exactly_once_in_the_board(self):
        rules = _rule_lines(self.ab.board_widgets.WIDGET_CSS)
        self.assertTrue(any(r.startswith("PickerItem {") for r in rules), rules)
        self.assertTrue(any(r.startswith(".task-title {") for r in rules), rules)
        for rule in rules:
            with self.subTest(rule=rule):
                self.assertEqual(self.ab.KanbanApp.CSS.count(rule), 1)

    #: Runs in a FRESH interpreter: a fixture tree, the trails app under Pilot,
    #: boot → cancel the selector → `?` (the shortcut editor, whose scope sweep
    #: is the one place a shared-scope App could execute the board) → print the
    #: loaded modules whose FILE is the board implementation or its task editor
    #: (board_detail_screen.py, t1794_7 — never pushed here). Checked by file
    #: path, not by `sys.modules` key: the sweep executes manifest modules under
    #: a probe name (`_shortcut_scopes_probe_aitask_board`), so a key check
    #: would pass while the whole board had just been executed.
    PROBE = """
import asyncio, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, {tests_lib!r}); sys.path.insert(0, {board!r}); sys.path.insert(0, {lib!r})
import board_fixture as bf
tmp = tempfile.TemporaryDirectory(); tree = bf.build_fixture_tree(Path(tmp.name), bf.DEFAULT_TOPOLOGY)
os.chdir(tree)
ta = bf.load_trails_app()
import board_trail_screen as ts
ts.discover_trails = lambda: ([], [])
def board_files():
    return sorted(k for k, m in list(sys.modules.items())
                  if str(getattr(m, "__file__", "") or "").endswith(
                      ("board/aitask_board.py", "board/board_detail_screen.py")))
async def go():
    app = bf.make_trails_app()
    async with app.run_test(size=(200, 48)) as pilot:
        for _ in range(3):
            await app.workers.wait_for_complete(); await pilot.pause()
        print("after_boot", board_files())
        await pilot.press("question_mark")
        for _ in range(3):
            await pilot.pause()
        print("editor", type(app.screen).__name__)
        print("after_editor", board_files())
        await pilot.press("escape"); await pilot.pause()
asyncio.run(go())
"""

    def _probe(self) -> dict[str, str]:
        script = self.PROBE.format(
            tests_lib=str(REPO_ROOT / "tests" / "lib"),
            board=str(REPO_ROOT / ".aitask-scripts" / "board"),
            lib=str(REPO_ROOT / ".aitask-scripts" / "lib"))
        out = subprocess.run([sys.executable, "-c", script], capture_output=True,
                             text=True, cwd=str(REPO_ROOT), timeout=180)
        self.assertEqual(out.returncode, 0, out.stderr)
        return dict(line.split(" ", 1) for line in out.stdout.strip().splitlines())

    def test_neither_boot_nor_the_shortcut_editor_loads_the_board(self):
        got = self._probe()
        self.assertEqual(got["after_boot"], "[]")
        self.assertEqual(got["editor"], "ShortcutEditorModal",
                         "the probe must actually have opened the editor")
        self.assertEqual(got["after_editor"], "[]",
                         "pressing ? executed the board implementation")

    def test_the_probe_sees_a_board_load(self):
        """Negative control: with the exclusion removed, the same probe reports
        the board executed under the sweep's probe name."""
        script = self.PROBE.replace(
            "ts.discover_trails = lambda: ([], [])",
            "ts.discover_trails = lambda: ([], []); "
            "ta.TrailsApp._shortcuts_exclude_sources = ()")
        script = script.format(
            tests_lib=str(REPO_ROOT / "tests" / "lib"),
            board=str(REPO_ROOT / ".aitask-scripts" / "board"),
            lib=str(REPO_ROOT / ".aitask-scripts" / "lib"))
        out = subprocess.run([sys.executable, "-c", script], capture_output=True,
                             text=True, cwd=str(REPO_ROOT), timeout=180)
        self.assertEqual(out.returncode, 0, out.stderr)
        got = dict(line.split(" ", 1) for line in out.stdout.strip().splitlines())
        self.assertEqual(got["after_boot"], "[]")
        self.assertIn("_shortcut_scopes_probe_aitask_board", got["after_editor"])



# --- tabbed multi-trail sessions (t1895) -----------------------------------------


HANDLE_A = "art:trail-alpha"
HANDLE_B = "art:trail-beta"
#: A non-live member only trail A has — so nothing B renders resolves it. It is
#: projected through the archive lookup (`find_task_including_archived`).
GHOST_A = "99997"


def _titled(doc: dict, title: str, mark: str) -> dict:
    """`doc` retitled, with a distinct summary token for the pane."""
    doc = dict(doc)
    doc["title"] = title
    doc["narrative"] = {"problem_statement": "ps",
                        "recommendation_summary": mark}
    return doc


class TabbedSessionTests(TrailsAppTestBase):
    """Several explicitly opened trails, one tab each, switched from memory.

    The subprocess seams (`discover_trails`, `load_trail_blob`,
    `run_trail_drift`) are patched with COUNTING fakes so "a switch is pure
    in-memory" is asserted, not assumed."""

    def _doc_a(self):
        return _titled(_wave_doc([*self.member_ids, GHOST_A]),
                       "Alpha trail", "ALPHAMARK")

    def _doc_b(self):
        return _titled(_wave_doc([self.member_ids[1], GHOST_REF]),
                       "Beta trail", "BETAMARK")

    def _info_for(self, handle, doc):
        return TrailInfo(handle=handle, owner_id=self.member_ids[0],
                         owner_archived=False, owner_folded=False,
                         name=doc["title"], doc=doc)

    def _counting(self, infos=None, drift=("CURRENT", [])):
        """Patches + a call log. `infos` is a list the test may mutate."""
        calls = {"discover": 0, "drift": [], "load": []}
        infos = infos if infos is not None else [
            self._info_for(HANDLE_A, self._doc_a()),
            self._info_for(HANDLE_B, self._doc_b())]

        def discover():
            calls["discover"] += 1
            return [TrailInfo(**{**vars(i)}) for i in infos], []

        def run_drift(handle):
            calls["drift"].append(handle)
            return drift

        def load(handle):
            calls["load"].append(handle)
            info = next(i for i in infos if i.handle == handle)
            return info.doc, "", []

        stack = [patch.object(self.ts, "discover_trails", discover),
                 patch.object(self.ts, "run_trail_drift", run_drift),
                 patch.object(self.ts, "load_trail_blob", load)]
        return calls, stack

    async def _open_second(self, app, pilot):
        """From one open tab: `s`, move to the second row, `enter`."""
        await pilot.press("s")
        await self._wait_screen(app, pilot,
                                self.ab.board_trail_view.TrailSelectScreen)
        await pilot.press("down")
        await pilot.press("enter")
        await self._settle(app, pilot)

    def _pane(self, app) -> str:
        return str(app.query_one("#trail_summary_body").render())

    def _strip(self, app) -> str:
        return str(app.query_one("#trail_tabs").render())

    def _card_ids(self, app):
        return [id(c) for c in app.query(self.ab.TaskCard)]

    def test_second_trail_opens_a_tab_from_the_cache(self):
        async def go():
            calls, stack = self._counting()
            app = bf.make_trails_app()
            with stack[0], stack[1], stack[2]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    self.assertEqual(calls["discover"], 1)
                    await pilot.press("s")
                    await self._wait_screen(
                        app, pilot, self.ab.board_trail_view.TrailSelectScreen)
                    self.assertEqual(calls["discover"], 1, "s re-scanned")
                    rows = [str(i.render()) for i in app.screen.query(
                        self.ab.board_trail_view.TrailSelectItem)]
                    self.assertIn("● open", rows[0])
                    self.assertNotIn("● open", rows[1])
                    await pilot.press("down")
                    await pilot.press("enter")
                    await self._settle(app, pilot)
                    self.assertEqual(list(app._trail_sessions),
                                     [HANDLE_A, HANDLE_B])
                    self.assertEqual(app.active_trail_handle, HANDLE_B)
                    strip = self._strip(app)
                    self.assertIn("1 Alpha trail", strip)
                    self.assertIn("2 Beta trail", strip)
                    self.assertIn("BETAMARK", self._pane(app))
        self._run(go())

    def test_switching_is_in_memory_and_restores_focus(self):
        async def go():
            calls, stack = self._counting()
            app = bf.make_trails_app()
            with stack[0], stack[1], stack[2]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    await pilot.press("down")       # A: second member
                    await self._wait_until(
                        pilot, lambda: self._focused_filename(app)
                        == self.member_files[1])
                    await self._open_second(app, pilot)
                    before = (calls["discover"], len(calls["drift"]),
                              len(calls["load"]))
                    # Beyond the three seams: no archive read (A's own ghost
                    # member is projected through the archive lookup, whose
                    # cache the B activation's task reload cleared, and B never
                    # resolves it) and no process at all.
                    archive_reads, spawned = [], []
                    real_load = app.manager._load_archived_task
                    real_popen = subprocess.Popen
                    app.manager._load_archived_task = (
                        lambda tid: (archive_reads.append(tid),
                                     real_load(tid))[1])

                    def popen(*args, **kwargs):
                        spawned.append(args[0] if args else kwargs.get("args"))
                        return real_popen(*args, **kwargs)

                    popen_patch = patch.object(subprocess, "Popen", popen)
                    popen_patch.start()
                    self.addCleanup(popen_patch.stop)

                    await pilot.press("[")
                    await self._settle(app, pilot)
                    self.assertEqual(app.active_trail_handle, HANDLE_A)
                    self.assertIn("Alpha trail", app.sub_title)
                    self.assertIn("ALPHAMARK", self._pane(app))
                    self.assertEqual(self._focused_filename(app),
                                     self.member_files[1],
                                     "A's focused card was not restored")
                    await pilot.press("]")
                    await self._settle(app, pilot)
                    self.assertEqual(app.active_trail_handle, HANDLE_B)
                    self.assertIn("Beta trail", app.sub_title)
                    self.assertIn("BETAMARK", self._pane(app))
                    await pilot.press("]")          # wraps
                    await self._settle(app, pilot)
                    self.assertEqual(app.active_trail_handle, HANDLE_A)
                    await pilot.press("2")
                    await self._settle(app, pilot)
                    self.assertEqual(app.active_trail_handle, HANDLE_B)
                    await pilot.press("1")
                    await self._settle(app, pilot)
                    self.assertEqual(app.active_trail_handle, HANDLE_A)
                    self.assertEqual((calls["discover"], len(calls["drift"]),
                                      len(calls["load"])), before,
                                     "a tab switch ran a subprocess seam")
                    popen_patch.stop()
                    self.assertEqual(archive_reads, [],
                                     "a tab switch read the task archive")
                    self.assertEqual(spawned, [],
                                     "a tab switch spawned a process")
        self._run(go())

    def test_a_reload_resolves_every_tab_archive_members(self):
        """The precondition the switch test relies on, pinned directly: opening
        B (a task reload) re-resolves A's non-live members, so the archive
        lookup for A's ghost is a cache hit by the time A is shown again."""
        async def go():
            calls, stack = self._counting()
            app = bf.make_trails_app()
            with stack[0], stack[1], stack[2]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    await self._open_second(app, pilot)
                    self.assertIn(GHOST_A, app.manager.archived_task_cache)
        self._run(go())

    def test_a_stale_selector_key_pops_nothing(self):
        """`TrailSelectScreen` is a guarded modal: an `r` (or `Esc`) dispatched
        to it after it closed neither raises nor pops the screen above."""
        async def go():
            calls, stack = self._counting()
            app = bf.make_trails_app()
            with stack[0], stack[1], stack[2]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    await pilot.press("s")
                    await self._wait_screen(
                        app, pilot, self.ab.board_trail_view.TrailSelectScreen)
                    selector = app.screen
                    await pilot.press("escape")
                    await self._settle(app, pilot)
                    selector.action_rescan()          # base screen on top
                    selector.action_cancel()
                    await self._settle(app, pilot)
                    self.assertIsInstance(app.screen, self.ta.TrailsScreen)
                    await pilot.press("v")            # a replacement modal
                    await self._wait_screen(
                        app, pilot, self.ab.board_trail_view.TrailSummaryScreen)
                    selector.action_rescan()
                    await self._settle(app, pilot)
                    self.assertIsInstance(
                        app.screen, self.ab.board_trail_view.TrailSummaryScreen)
                    self.assertEqual(calls["discover"], 1)
                    await pilot.press("escape")
                    await self._settle(app, pilot)
        self._run(go())

    def test_choosing_an_open_trail_switches_without_a_duplicate(self):
        async def go():
            calls, stack = self._counting()
            app = bf.make_trails_app()
            with stack[0], stack[1], stack[2]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    await self._open_second(app, pilot)
                    drift_before = len(calls["drift"])
                    await pilot.press("s")
                    await self._wait_screen(
                        app, pilot, self.ab.board_trail_view.TrailSelectScreen)
                    await pilot.press("enter")      # A, already open
                    await self._settle(app, pilot)
                    self.assertEqual(app.active_trail_handle, HANDLE_A)
                    self.assertEqual(list(app._trail_sessions),
                                     [HANDLE_A, HANDLE_B])
                    self.assertEqual(len(calls["drift"]), drift_before)
        self._run(go())

    def test_background_drift_updates_only_its_tab(self):
        async def go():
            calls, stack = self._counting()
            app = bf.make_trails_app()
            with stack[0], stack[1], stack[2]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    await self._open_second(app, pilot)
                    await pilot.press("1")
                    await self._settle(app, pilot)
                    session_b = app._trail_session(HANDLE_B)
                    cards = self._card_ids(app)
                    app._on_trail_drift(session_b.drift_gen, HANDLE_B, "STALE",
                                        [("status_changed", "-", "d")])
                    await self._settle(app, pilot)
                    self.assertEqual(session_b.drift[0], "STALE")
                    self.assertTrue(session_b.updated)
                    self.assertEqual(self._card_ids(app), cards,
                                     "the active tab was re-rendered")
                    self.assertEqual(app._trail_drift[0], "CURRENT")
                    self.assertIn("2 Beta trail ⚠ •", self._strip(app))
                    await pilot.press("2")
                    await self._settle(app, pilot)
                    self.assertFalse(session_b.updated)
                    self.assertNotIn("•", self._strip(app))
                    self.assertIn("stale", app.sub_title)
        self._run(go())

    def test_watch_survives_a_switch_reloads_its_own_trail_and_dies_on_close(self):
        async def go():
            calls, stack = self._counting()
            app = bf.make_trails_app()
            with stack[0], stack[1], stack[2]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    await self._open_second(app, pilot)
                    await pilot.press("1")
                    await self._settle(app, pilot)
                    spawned = []
                    app._trail_watch_worker = (
                        lambda gen, handle: spawned.append(handle))
                    app._install_trail_watch(HANDLE_A, ["v1"])
                    await pilot.press("2")          # A goes to the background
                    await self._settle(app, pilot)
                    self.assertIsNotNone(app._trail_watch_timer)
                    app._trail_watch_tick()
                    self.assertEqual(spawned, [HANDLE_A])
                    # A version change for background A reloads A, not B.
                    app._on_trail_watch(app._trail_watch_gen, HANDLE_A, ["v2"])
                    await self._settle(app, pilot)
                    self.assertEqual(calls["load"], [HANDLE_A])
                    self.assertEqual(app.active_trail_handle, HANDLE_B)
                    # Closing A's tab is what stops a watch on A.
                    app._install_trail_watch(HANDLE_A, ["v2"])
                    await pilot.press("1")
                    await self._settle(app, pilot)
                    self.assertIsNotNone(app._trail_watch_timer)
                    await pilot.press("ctrl+w")
                    await self._settle(app, pilot)
                    self.assertIsNone(app._trail_watch_timer)
                    self.assertEqual(list(app._trail_sessions), [HANDLE_B])
                    self.assertEqual(app.active_trail_handle, HANDLE_B)
        self._run(go())

    def test_closing_the_last_tab_shows_the_empty_state(self):
        async def go():
            calls, stack = self._counting()
            app = bf.make_trails_app()
            with stack[0], stack[1], stack[2]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    self.assertIs(app.check_action("trail_tab_close", None),
                                  True)
                    await pilot.press("ctrl+w")
                    await self._settle(app, pilot)
                    self.assertIsNone(app.active_trail_handle)
                    self.assertEqual(app._trail_sessions, {})
                    hint = " ".join(str(w.render())
                                    for w in app.query(".trail-empty"))
                    self.assertIn("No trail selected", hint)
                    self.assertIn("no trail selected — press s", app.sub_title)
                    self.assertFalse(app.query_one("#trail_tabs").display)
                    for action in ("trail_tab_close", "trail_tab_prev",
                                   "trail_tab_next", "trail_tab_1"):
                        self.assertIs(app.check_action(action, None), False,
                                      action)
        self._run(go())

    def test_r_in_the_selector_rescans(self):
        async def go():
            calls, stack = self._counting()
            app = bf.make_trails_app()
            with stack[0], stack[1], stack[2]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    await pilot.press("s")
                    await self._wait_screen(
                        app, pilot, self.ab.board_trail_view.TrailSelectScreen)
                    self.assertEqual(calls["discover"], 1)
                    await pilot.press("r")
                    await self._settle(app, pilot)
                    self.assertEqual(calls["discover"], 2)
                    self.assertIsInstance(
                        app.screen, self.ab.board_trail_view.TrailSelectScreen)
                    await pilot.press("escape")
                    await self._settle(app, pilot)
        self._run(go())

    def test_an_empty_scan_is_not_a_dead_end(self):
        """A successful zero-trail scan caches `[]`; `s` must still re-scan, or
        a trail created afterwards could never be found without a restart."""
        async def go():
            available = []
            calls, stack = self._counting(infos=available)
            app = bf.make_trails_app()
            with stack[0], stack[1], stack[2]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._settle(app, pilot)
                    self.assertEqual(calls["discover"], 1)
                    self.assertEqual(app._trail_infos, [])
                    self.assertIsInstance(app.screen, self.ta.TrailsScreen)
                    available.append(self._info_for(HANDLE_A, self._doc_a()))
                    await pilot.press("s")
                    await self._wait_screen(
                        app, pilot, self.ab.board_trail_view.TrailSelectScreen)
                    self.assertEqual(calls["discover"], 2)
                    await pilot.press("enter")
                    await self._settle(app, pilot)
                    self.assertEqual(list(app._trail_sessions), [HANDLE_A])
        self._run(go())

    def test_a_click_on_a_tab_switches_to_it(self):
        async def go():
            calls, stack = self._counting()
            app = bf.make_trails_app()
            with stack[0], stack[1], stack[2]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    await self._open_second(app, pilot)
                    strip = app.query_one("#trail_tabs")
                    start, _end, handle = strip._spans[0]
                    self.assertEqual(handle, HANDLE_A)
                    await pilot.click("#trail_tabs", offset=(start + 2, 0))
                    await self._settle(app, pilot)
                    self.assertEqual(app.active_trail_handle, HANDLE_A)
        self._run(go())

    # --- discovery vs. reload ---------------------------------------------------

    def _sequenced_pair(self, rev1, rev2):
        """Two real fetch-ordered reads of HANDLE_A over a store that moves
        from rev1 to rev2: `((rev1 result, seq), (rev2 result, seq))`."""
        from trail_discovery import sequenced_trail_read
        store = {"doc": rev1}
        older = sequenced_trail_read(HANDLE_A,
                                     lambda h: (store["doc"], "", []))
        store["doc"] = rev2
        newer = sequenced_trail_read(HANDLE_A,
                                     lambda h: (store["doc"], "", []))
        return older, newer

    def _reconcile_once(self, reload_fetched_newer: bool,
                        reload_lands_first: bool):
        rev1 = _titled(self._doc_a(), "Alpha rev1", "REV1MARK")
        rev2 = _titled(self._doc_a(), "Alpha rev2", "REV2MARK")
        (old_res, old_seq), (new_res, new_seq) = self._sequenced_pair(rev1, rev2)
        if reload_fetched_newer:
            reload_res, reload_seq, disc_res, disc_seq = (
                new_res, new_seq, old_res, old_seq)
        else:
            reload_res, reload_seq, disc_res, disc_seq = (
                old_res, old_seq, new_res, new_seq)

        async def go():
            calls, stack = self._counting()
            app = bf.make_trails_app()
            with stack[0], stack[1], stack[2]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    session = app._trail_session(HANDLE_A)
                    # Both requests in flight: a reload of A and a scan.
                    app._trail_reload_worker = lambda gen, handle: None
                    app._reload_active_trail()
                    reload_gen = session.reload_gen
                    app._trail_discovery_gen = app._bump_trail_gen()
                    scan_gen = app._trail_discovery_gen
                    scanned = self._info_for(HANDLE_A, disc_res[0])
                    scanned.read_seq = disc_seq

                    def land_reload():
                        app._on_trail_reload(reload_gen, HANDLE_A,
                                             *reload_res, reload_seq)

                    def land_scan():
                        app._on_trail_discovery(scan_gen, [scanned], [], None)

                    for land in ((land_reload, land_scan) if reload_lands_first
                                 else (land_scan, land_reload)):
                        land()
                        await self._settle(app, pilot)
                    if isinstance(app.screen,
                                  self.ab.board_trail_view.TrailSelectScreen):
                        await pilot.press("escape")
                        await self._settle(app, pilot)

                    self.assertEqual(session.doc["title"], "Alpha rev2")
                    cached = next(i for i in app._trail_infos
                                  if i.handle == HANDLE_A)
                    self.assertEqual(cached.doc["title"], "Alpha rev2")
                    self.assertIn("REV2MARK", self._pane(app))

                    # Identical content again: no redraw, no drift subprocess.
                    cards, drifts = self._card_ids(app), len(calls["drift"])
                    again = self._info_for(HANDLE_A, rev2)
                    again.read_seq = max(old_seq, new_seq) + 1000
                    app._trail_discovery_gen = app._bump_trail_gen()
                    app._on_trail_discovery(app._trail_discovery_gen, [again],
                                            [], None)
                    await self._settle(app, pilot)
                    await pilot.press("escape")
                    await self._settle(app, pilot)
                    self.assertEqual(self._card_ids(app), cards)
                    self.assertEqual(len(calls["drift"]), drifts)

                    # Close A and reopen it from the cache: still rev2.
                    await pilot.press("ctrl+w")
                    await self._settle(app, pilot)
                    discovered = calls["discover"]
                    await pilot.press("s")
                    await self._wait_screen(
                        app, pilot, self.ab.board_trail_view.TrailSelectScreen)
                    self.assertEqual(calls["discover"], discovered)
                    await pilot.press("enter")
                    await self._settle(app, pilot)
                    self.assertEqual(app._trail_doc["title"], "Alpha rev2")
                    self.assertIn("REV2MARK", self._pane(app))
        self._run(go())

    def test_discovery_and_reload_converge_on_the_newer_fetch_in_any_order(self):
        for reload_fetched_newer in (True, False):
            for reload_lands_first in (True, False):
                with self.subTest(reload_fetched_newer=reload_fetched_newer,
                                  reload_lands_first=reload_lands_first):
                    self._reconcile_once(reload_fetched_newer,
                                         reload_lands_first)

    def test_a_new_failing_revision_reaches_the_tab_and_the_cache(self):
        """Same load error, new recorded versions: the error card lists them.
        Before the fix only `doc`/`error` were compared, so the session kept the
        old versions while `read_seq` advanced past them."""
        from trail_discovery import sequenced_trail_read
        error = "artifact unresolved: no manifest"
        broken = TrailInfo(handle=HANDLE_A, owner_id=self.member_ids[0],
                           owner_archived=False, owner_folded=False,
                           name="Broken", doc=None, load_error=error,
                           versions=["* sha256:v1"])

        async def go():
            calls, stack = self._counting(infos=[broken])
            app = bf.make_trails_app()
            with stack[0], stack[1], stack[2]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    session = app._trail_session(HANDLE_A)
                    # A reload that fetched a newer failing revision.
                    app._trail_reload_worker = lambda gen, handle: None
                    app._reload_active_trail()
                    (_res, seq) = sequenced_trail_read(
                        HANDLE_A, lambda h: None)
                    app._on_trail_reload(session.reload_gen, HANDLE_A, None,
                                         error, ["* sha256:v2", "* sha256:v1"],
                                         seq)
                    await self._settle(app, pilot)
                    self.assertEqual(session.versions_fallback,
                                     ["* sha256:v2", "* sha256:v1"])
                    card = " ".join(str(w.render())
                                    for w in app.query(".trail-error"))
                    self.assertIn("sha256:v2", card)
                    self.assertEqual(app._trail_infos[0].versions,
                                     ["* sha256:v2", "* sha256:v1"])
                    # A later scan with yet another failing revision.
                    (_res, newer) = sequenced_trail_read(
                        HANDLE_A, lambda h: None)
                    scanned = TrailInfo(**{**vars(broken),
                                           "versions": ["* sha256:v3"],
                                           "read_seq": newer})
                    app._on_trail_discovery(app._trail_discovery_gen,
                                            [scanned], [], None)
                    await self._settle(app, pilot)
                    await pilot.press("escape")
                    await self._settle(app, pilot)
                    self.assertEqual(session.versions_fallback, ["* sha256:v3"])
                    card = " ".join(str(w.render())
                                    for w in app.query(".trail-error"))
                    self.assertIn("sha256:v3", card)
        self._run(go())

    def test_a_scan_moves_an_open_tab_onto_its_new_owner(self):
        """Ownership comes from task frontmatter, not the artifact: a scan that
        finds a new (archived) owner updates the open tab's banner even when
        the trail document is unchanged and the sequence is no newer."""
        async def go():
            calls, stack = self._counting()
            app = bf.make_trails_app()
            with stack[0], stack[1], stack[2]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    session = app._trail_session(HANDLE_A)
                    self.assertFalse(session.owner_archived)
                    moved = TrailInfo(handle=HANDLE_A, owner_id="9001",
                                      owner_archived=True, owner_folded=False,
                                      name="Alpha trail", doc=session.doc,
                                      read_seq=session.read_seq)
                    app._on_trail_discovery(app._trail_discovery_gen, [moved],
                                            [], None)
                    await self._settle(app, pilot)
                    await pilot.press("escape")
                    await self._settle(app, pilot)
                    self.assertEqual((session.owner_id, session.owner_archived),
                                     ("9001", True))
                    self.assertIn("owner t9001 archived", app.sub_title)
        self._run(go())

    # --- deferred focus restore ---------------------------------------------------

    def test_a_stale_restore_from_an_earlier_switch_does_not_land(self):
        """A→B→A with the restores held back: B's restore (shared member X)
        lands LATE, after A's own restore, and must not move focus. The
        negative control runs the same stale restore unguarded and lands on X."""
        x_file, y_file = self.member_files[1], self.member_files[0]

        async def run(guarded: bool):
            calls, stack = self._counting()
            app = bf.make_trails_app()
            with stack[0], stack[1], stack[2]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)  # A, Y focused
                    self.assertEqual(self._focused_filename(app), y_file)
                    await self._open_second(app, pilot)      # B, X focused
                    self.assertEqual(self._focused_filename(app), x_file)
                    await pilot.press("1")
                    await self._settle(app, pilot)
                    self.assertEqual(self._focused_filename(app), y_file)

                    held = []
                    real = app.call_after_refresh

                    def capture(callback, *args, **kwargs):
                        if getattr(callback, "__name__", "") == "_refocus":
                            held.append(args)
                            return True
                        return real(callback, *args, **kwargs)

                    app.call_after_refresh = capture
                    await pilot.press("]")       # → B
                    await pilot.press("[")       # → A, without settling
                    app.call_after_refresh = real
                    await self._settle(app, pilot)
                    self.assertEqual(app.active_trail_handle, HANDLE_A)
                    self.assertEqual(len(held), 2, held)
                    stale, current = held
                    self.assertEqual(stale[0], x_file)
                    app._refocus(*current)
                    await pilot.pause()
                    if guarded:
                        app._refocus(*stale)
                    else:
                        app._refocus(stale[0], stale[1], stale[2], None)
                    await pilot.pause()
                    await pilot.pause()
                    return self._focused_filename(app)

        self.assertEqual(asyncio.run(run(guarded=True)), y_file)
        self.assertEqual(asyncio.run(run(guarded=False)), x_file,
                         "negative control: an unguarded stale restore must "
                         "land on the shared member, or this test proves nothing")


# --- cross-repo status probe (t1957_1) --------------------------------------------

#: A foreign member of trail A — a `cross_repo` ghost whose live status the
#: session probes. Trail B has no cross-repo refs, so it never starts a probe.
XREF = "otherproj#3"


class XdepSessionTests(TrailsAppTestBase):
    """The per-session cross-repo status worker: supersession, coverage and
    the zero-subprocess paths. `probe_xdep_status` is a counting fake, or the
    worker itself is replaced by a recorder so a result never lands unless the
    test delivers it."""

    def _doc_a(self, *extra):
        return _titled(_xdep_doc(self.member_ids, [XREF, *extra]),
                       "Alpha trail", "ALPHAMARK")

    def _doc_b(self):
        return _titled(_wave_doc([self.member_ids[1]]), "Beta trail", "BETAMARK")

    def _info_for(self, handle, doc):
        return TrailInfo(handle=handle, owner_id=self.member_ids[0],
                         owner_archived=False, owner_folded=False,
                         name=doc["title"], doc=doc)

    def _patches(self, probes: list, status="Done"):
        infos = [self._info_for(HANDLE_A, self._doc_a()),
                 self._info_for(HANDLE_B, self._doc_b())]

        def probe(repo, task_id):
            probes.append(f"{repo}#{task_id}")
            return status

        return [patch.object(self.ts, "discover_trails",
                             lambda: ([TrailInfo(**vars(i)) for i in infos], [])),
                patch.object(self.ts, "run_trail_drift",
                             lambda handle: ("CURRENT", [])),
                patch.object(self.ts, "load_trail_blob",
                             lambda handle: (next(i.doc for i in infos
                                                  if i.handle == handle), "", [])),
                patch.object(self.ts, "probe_xdep_status", probe)]

    @staticmethod
    def _no_drift_redraw(app) -> None:
        """Drift's callback re-renders the lanes, which would repaint over a
        stale first paint within a pause; in real use it can take 15s. Keep
        it out so a test sees the first paint only."""
        app._trail_drift_worker = lambda gen, handle: None

    @staticmethod
    def _recorder(app) -> list:
        """Replace the worker: record (gen, handle, refs), never deliver."""
        started = []
        app._trail_xdep_worker = (
            lambda gen, handle, refs: started.append((gen, handle, set(refs))))
        return started

    def _remote(self, app, ref=XREF) -> str:
        for card in app.query(self.ab.TrailGhostCard):
            if card.trail_entry.get("task") == ref:
                labels = card.query(".trail-remote-status")
                return str(labels.first().render()) if labels else ""
        return "<no card>"

    async def _open_second(self, app, pilot):
        await pilot.press("s")
        await self._wait_screen(app, pilot,
                                self.ab.board_trail_view.TrailSelectScreen)
        await pilot.press("down")
        await pilot.press("enter")
        await self._settle(app, pilot)

    def _card_ids(self, app):
        return [id(c) for c in app.query(self.ab.TaskCard)]

    def test_probe_result_reaches_the_ghost_card(self):
        async def go():
            probes = []
            app = bf.make_trails_app()
            p = self._patches(probes)
            with p[0], p[1], p[2], p[3]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    self.assertEqual(probes, [XREF])
                    self.assertEqual(self._remote(app), "📋 Done")
                    session = app._trail_session(HANDLE_A)
                    self.assertEqual(session.xdep, {XREF: "Done"})
                    self.assertEqual(session.xdep_inflight, frozenset())
                    ghost = next(c for c in app.query(self.ab.TrailGhostCard)
                                 if c.trail_entry.get("task") == XREF)
                    self.assertTrue(ghost.trail_view.landed)
        self._run(go())

    def test_activation_first_render_reads_checking(self):
        """Start-before-render: the first paint already shows the probe."""
        async def go():
            probes = []
            app = bf.make_trails_app()
            started = self._recorder(app)
            self._no_drift_redraw(app)
            p = self._patches(probes)
            with p[0], p[1], p[2], p[3]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    self.assertEqual([s[2] for s in started], [{XREF}])
                    self.assertEqual(self._remote(app), "🌐 (checking…)")
        self._run(go())

    def test_first_render_after_content_change_reads_checking(self):
        """A reload that adds a foreign member renders it as being checked on
        its very first paint — never as unreachable or unprobed — while the
        cached result for the old member stays shown."""
        async def go():
            probes = []
            app = bf.make_trails_app()
            p = self._patches(probes)
            with p[0], p[1], p[2], p[3]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    self.assertEqual(self._remote(app), "📋 Done")
                    started = self._recorder(app)
                    self._no_drift_redraw(app)
                    session = app._trail_session(HANDLE_A)
                    seen = []
                    real_rerender = app._rerender_trail

                    def spy(refocus_filename=""):
                        real_rerender(refocus_filename)
                        seen.append(None)

                    app._rerender_trail = spy
                    app._on_trail_reload(
                        session.reload_gen, HANDLE_A,
                        self._doc_a("otherproj#9"), "", [],
                        session.read_seq + 100)
                    self.assertEqual(len(seen), 1)
                    await pilot.pause()
                    self.assertEqual([s[2] for s in started],
                                     [{XREF, "otherproj#9"}])
                    self.assertEqual(self._remote(app, "otherproj#9"),
                                     "🌐 (checking…)")
                    self.assertEqual(self._remote(app), "📋 Done")
        self._run(go())

    def test_older_result_never_fails_an_unprobed_ref(self):
        async def go():
            probes = []
            app = bf.make_trails_app()
            started = self._recorder(app)
            p = self._patches(probes)
            with p[0], p[1], p[2], p[3]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    session = app._trail_session(HANDLE_A)
                    old_gen = session.xdep_gen
                    app._start_session_xdep(session)
                    new_gen = session.xdep_gen
                    self.assertGreater(new_gen, old_gen)
                    # The superseded probe reports a failure: dropped.
                    app._on_trail_xdep(old_gen, HANDLE_A, {XREF: ""})
                    await self._settle(app, pilot)
                    self.assertEqual(session.xdep, {})
                    self.assertEqual(self._remote(app), "🌐 (checking…)")
                    # The current probe lands without covering XREF: unprobed,
                    # not a failure.
                    app._on_trail_xdep(new_gen, HANDLE_A, {})
                    await self._settle(app, pilot)
                    self.assertEqual(self._remote(app), "🌐 (not checked)")
                    self.assertEqual(len(started), 2)
        self._run(go())

    def test_background_result_marks_only_its_tab_and_a_b_a(self):
        async def go():
            probes = []
            app = bf.make_trails_app()
            started = self._recorder(app)
            p = self._patches(probes)
            with p[0], p[1], p[2], p[3]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)     # A
                    await self._open_second(app, pilot)         # B active
                    self.assertEqual(app.active_trail_handle, HANDLE_B)
                    session_a = app._trail_session(HANDLE_A)
                    cards = self._card_ids(app)
                    app._on_trail_xdep(session_a.xdep_gen, HANDLE_A,
                                       {XREF: "Implementing"})
                    await self._settle(app, pilot)
                    self.assertTrue(session_a.updated)
                    self.assertFalse(app._trail_session(HANDLE_B).updated)
                    self.assertEqual(self._card_ids(app), cards,
                                     "the active tab was re-rendered")
                    await pilot.press("1")                      # back to A
                    await self._settle(app, pilot)
                    self.assertEqual(self._remote(app), "📋 Implementing")
                    self.assertEqual(probes, [])
                    self.assertEqual(len(started), 1, "a switch re-probed")
        self._run(go())

    def test_result_for_a_closed_tab_is_dropped(self):
        async def go():
            probes = []
            app = bf.make_trails_app()
            self._recorder(app)
            p = self._patches(probes)
            with p[0], p[1], p[2], p[3]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    await self._open_second(app, pilot)
                    gen = app._trail_session(HANDLE_A).xdep_gen
                    app._close_trail_session(HANDLE_A)
                    await self._settle(app, pilot)
                    app._on_trail_xdep(gen, HANDLE_A, {XREF: "Done"})
                    await self._settle(app, pilot)
                    self.assertIsNone(app._trail_session(HANDLE_A))
                    self.assertEqual(app.active_trail_handle, HANDLE_B)
        self._run(go())

    def test_supersession_releases_in_flight_coverage(self):
        async def go():
            probes = []
            app = bf.make_trails_app()
            self._recorder(app)
            p = self._patches(probes)
            with p[0], p[1], p[2], p[3]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    session = app._trail_session(HANDLE_A)
                    gen = session.xdep_gen
                    self.assertEqual(session.xdep_inflight, {XREF})
                    app._supersede_trail_workers()
                    self.assertEqual(session.xdep_inflight, frozenset())
                    app._on_trail_xdep(gen, HANDLE_A, {XREF: "Done"})
                    app._rerender_trail()
                    await self._settle(app, pilot)
                    self.assertEqual(self._remote(app), "🌐 (not checked)")
        self._run(go())

    def test_local_refresh_and_tab_switch_never_probe(self):
        async def go():
            probes = []
            app = bf.make_trails_app()
            p = self._patches(probes)
            with p[0], p[1], p[2], p[3]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    await self._open_second(app, pilot)
                    self.assertEqual(probes, [XREF])
                    for key in ("1", "r", "2", "1", "r"):
                        await pilot.press(key)
                        await self._settle(app, pilot)
                    self.assertEqual(probes, [XREF])
                    self.assertEqual(self._remote(app), "📋 Done")
        self._run(go())


# --- open by name: `--trail` and the pane mailbox (t1957_2) ---------------------

HANDLE_C = "art:trail-gamma"
HANDLE_LATE = "art:trail-late"


class _PaneStore:
    """The tmux side of the mailbox: per-pane options on ONE fake gateway server.

    Patched over the names `trails_app` imports, so the App's real worker code
    runs against it. `gateway` lists the panes that verify as the gateway
    server's; a pane outside it is "the same id on another server"."""

    def __init__(self, gateway=("%1", "%2")):
        import threading
        self.opts: dict[str, dict[str, str]] = {}
        self.log: list[tuple[str, str]] = []
        self.gateway = set(gateway)
        self.fail_reads = False
        self.on_read = None          # one-shot hook run after a read is taken
        self._lock = threading.Lock()

    def verify(self, pane, tmux_env):
        self.log.append(("verify", pane))
        return pane in self.gateway

    def read(self, pane):
        with self._lock:
            self.log.append(("read", pane))
            if self.fail_reads:
                return None
            value = self.opts.get(pane, {}).get("focus", "")
            hook, self.on_read = self.on_read, None
        if hook is not None:
            hook(pane)
        return value

    def mark(self, pane):
        self.log.append(("mark", pane))
        self.opts.setdefault(pane, {})["stamp"] = "1"
        return True

    def unmark(self, pane):
        self.log.append(("unmark", pane))
        self.opts.get(pane, {}).pop("stamp", None)
        return True

    def write(self, pane, handle, request_id=None):
        """What `launch_or_focus_trails` does to the chosen pane: overwrite."""
        import uuid
        request_id = request_id or uuid.uuid4().hex
        self.opts.setdefault(pane, {})["focus"] = f"{request_id} {handle}"
        return request_id

    def verbs(self, pane):
        return [verb for verb, p in self.log if p == pane]

    def patches(self, ta):
        return [patch.object(ta, "pane_on_gateway_server", self.verify),
                patch.object(ta, "read_trails_focus_request", self.read),
                patch.object(ta, "mark_trails_receiver", self.mark),
                patch.object(ta, "unmark_trails_receiver", self.unmark),
                # Polls are driven by the test, never by the timer.
                patch.object(ta, "TRAIL_FOCUS_POLL_SECONDS", 3600)]


class TrailFocusTests(TrailsAppTestBase):
    """Opening a trail by name: the cold `--trail` path, and requests to a
    running App through its own pane's mailbox — each applied once, never
    cleared, latest wins, one receiver per request."""

    def _info_for(self, handle, title):
        doc = _titled(_wave_doc(list(self.member_ids)), title, title.upper())
        return TrailInfo(handle=handle, owner_id=self.member_ids[0],
                         owner_archived=False, owner_folded=False,
                         name=title, doc=doc)

    def _seams(self, extra_on_rescan=None, gate=None):
        """discover / drift / load patches. With `gate` (a threading.Event),
        every scan after the first waits on it and then also returns
        `extra_on_rescan` — a trail authored after boot."""
        infos = [self._info_for(HANDLE_A, "Alpha"),
                 self._info_for(HANDLE_B, "Beta"),
                 self._info_for(HANDLE_C, "Gamma")]
        calls = {"discover": 0}

        def discover():
            calls["discover"] += 1
            found = list(infos)
            if calls["discover"] > 1 and extra_on_rescan is not None:
                if gate is not None:
                    gate.wait(10)
                found.append(extra_on_rescan)
            return found, []

        def load(handle):
            return next(i for i in infos if i.handle == handle).doc, "", []

        return calls, [patch.object(self.ts, "discover_trails", discover),
                       patch.object(self.ts, "run_trail_drift",
                                    lambda h: ("CURRENT", [])),
                       patch.object(self.ts, "load_trail_blob", load)]

    def _activations(self, app):
        log = []
        original = app._activate_trail

        def spy(handle):
            log.append(handle)
            return original(handle)
        app._activate_trail = spy
        return log

    def _notices(self, app):
        log = []
        original = app.notify

        def spy(message, *args, **kwargs):
            log.append(str(message))
            return original(message, *args, **kwargs)
        app.notify = spy
        return log

    async def _poll(self, app, pilot):
        app._poll_trail_focus()
        await self._settle(app, pilot)

    def _run_app(self, body, *, store=None, seams=None, **app_kwargs):
        """Boot an App (patched seams + store) and run `body(app, pilot)`."""
        async def go():
            _calls, stack = seams or self._seams()
            patches = stack + (store.patches(self.ta) if store else [])
            app = bf.make_trails_app(**app_kwargs)
            app._t_activated = self._activations(app)
            app._t_notices = self._notices(app)
            with contextlib.ExitStack() as ctx:
                for p in patches:
                    ctx.enter_context(p)
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._settle(app, pilot)
                    await body(app, pilot)
                    await self._settle(app, pilot)
            return app
        return self._run(go())

    # --- main() ------------------------------------------------------------

    def test_main_rejects_a_malformed_handle(self):
        with patch.object(self.ta, "TrailsApp") as app_cls, \
                contextlib.redirect_stderr(io.StringIO()):
            for bad in ("trail-alpha", "art:", "art:Bad Handle", "art:a b"):
                with self.subTest(bad=bad), self.assertRaises(SystemExit):
                    self.ta.main(["--trail", bad])
        app_cls.assert_not_called()

    def test_main_passes_the_handle_and_the_pane_environment(self):
        with patch.object(self.ta, "TrailsApp") as app_cls, \
                patch.dict(os.environ, {"TMUX_PANE": "%7",
                                        "TMUX": "/tmp/s/ait,1,0"}):
            self.ta.main(["--trail", HANDLE_B])
        kwargs = app_cls.call_args.kwargs
        self.assertEqual(kwargs["initial_trail"], HANDLE_B)
        self.assertEqual(kwargs["focus_pane"], "%7")
        self.assertEqual(kwargs["focus_tmux_env"], "/tmp/s/ait,1,0")
        app_cls.return_value.run.assert_called_once()

    def test_main_outside_tmux_has_no_mailbox(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("TMUX", "TMUX_PANE")}
        with patch.object(self.ta, "TrailsApp") as app_cls, \
                patch.dict(os.environ, env, clear=True):
            self.ta.main([])
        self.assertIsNone(app_cls.call_args.kwargs["focus_pane"])
        self.assertIsNone(app_cls.call_args.kwargs["initial_trail"])

    # --- the cold path -----------------------------------------------------

    def test_cold_trail_opens_it_instead_of_the_selector(self):
        async def body(app, pilot):
            self.assertIsInstance(app.screen, self.ta.TrailsScreen)
            self.assertEqual(app.active_trail_handle, HANDLE_B)
            self.assertEqual(list(app._trail_sessions), [HANDLE_B])
            self.assertIsNotNone(app._trail_doc)
            self.assertEqual(calls["discover"], 1)
        calls, stack = self._seams()
        self._run_app(body, seams=(calls, stack), initial_trail=HANDLE_B)

    def test_cold_unknown_trail_offers_the_selector_with_a_notice(self):
        async def body(app, pilot):
            await self._wait_screen(app, pilot,
                                    self.ab.board_trail_view.TrailSelectScreen)
            self.assertIsNone(app.active_trail_handle)
        app = self._run_app(body, initial_trail="art:trail-nope")
        self.assertTrue(any("art:trail-nope" in n and "not found" in n
                            for n in app._t_notices), app._t_notices)
        self.assertEqual(app._t_activated, [])

    # --- registration ------------------------------------------------------

    def test_baseline_is_read_before_the_stamp_and_never_replayed(self):
        store = _PaneStore()
        left = store.write("%1", HANDLE_B)      # an earlier instance's request

        async def body(app, pilot):
            self.assertEqual(store.verbs("%1")[:3], ["verify", "read", "mark"])
            self.assertEqual(app._seen_focus_id, left)
            await self._poll(app, pilot)
            await self._poll(app, pilot)
            self.assertEqual(app.active_trail_handle, HANDLE_A)
            self.assertEqual(app._t_activated, [HANDLE_A])
        app = self._run_app(body, store=store, initial_trail=HANDLE_A,
                            focus_pane="%1")

    def test_a_failed_baseline_read_registers_nothing(self):
        store = _PaneStore()
        store.fail_reads = True

        async def body(app, pilot):
            self.assertEqual(store.verbs("%1"), ["verify", "read"])
            self.assertIsNone(app._focus_timer)
            self.assertFalse(app._focus_stamped)
        app = self._run_app(body, store=store, initial_trail=HANDLE_A,
                            focus_pane="%1")
        self.assertNotIn("unmark", store.verbs("%1"))

    def test_a_pane_of_another_server_is_never_touched(self):
        # `%9` exists on the gateway server too, but this process's $TMUX names
        # another server: the id there is somebody else's pane.
        store = _PaneStore(gateway=())
        store.write("%9", HANDLE_B)

        async def body(app, pilot):
            await self._poll(app, pilot)
            self.assertEqual(store.verbs("%9"), ["verify"])
            self.assertIsNone(app._focus_timer)
            self.assertEqual(app.active_trail_handle, HANDLE_A)
        app = self._run_app(body, store=store, initial_trail=HANDLE_A,
                            focus_pane="%9")
        self.assertEqual(store.verbs("%9"), ["verify"])
        self.assertNotIn("stamp", store.opts.get("%9", {}))

    def test_a_gateway_pane_registers_and_unstamps_on_exit(self):
        store = _PaneStore()

        async def body(app, pilot):
            self.assertEqual(store.opts["%1"]["stamp"], "1")
            self.assertIsNotNone(app._focus_timer)
        app = self._run_app(body, store=store, initial_trail=HANDLE_A,
                            focus_pane="%1")
        self.assertEqual(store.verbs("%1")[-1], "unmark")
        self.assertNotIn("stamp", store.opts["%1"])

    # --- consumption -------------------------------------------------------

    def test_a_request_applies_once_and_stays_in_the_mailbox(self):
        store = _PaneStore()

        async def body(app, pilot):
            rid = store.write("%1", HANDLE_B)
            await self._poll(app, pilot)
            self.assertEqual(app.active_trail_handle, HANDLE_B)
            self.assertEqual(store.opts["%1"]["focus"], f"{rid} {HANDLE_B}")
            app._switch_trail_session(HANDLE_A)
            await self._poll(app, pilot)
            self.assertEqual(app.active_trail_handle, HANDLE_A,
                             "the same request id was applied twice")
        app = self._run_app(body, store=store, initial_trail=HANDLE_A,
                            focus_pane="%1")
        self.assertEqual(app._t_activated, [HANDLE_A, HANDLE_B])

    def test_a_request_written_during_a_read_is_applied_next(self):
        store = _PaneStore()

        async def body(app, pilot):
            store.write("%1", HANDLE_B)
            store.on_read = lambda pane: store.write(pane, HANDLE_C)
            await self._poll(app, pilot)
            self.assertEqual(app.active_trail_handle, HANDLE_B)
            await self._poll(app, pilot)
            self.assertEqual(app.active_trail_handle, HANDLE_C)
        app = self._run_app(body, store=store, initial_trail=HANDLE_A,
                            focus_pane="%1")
        self.assertEqual(app._t_activated, [HANDLE_A, HANDLE_B, HANDLE_C])

    def test_two_requests_between_polls_apply_only_the_latest(self):
        store = _PaneStore()

        async def body(app, pilot):
            store.write("%1", HANDLE_B)
            store.write("%1", HANDLE_C)
            await self._poll(app, pilot)
            await self._poll(app, pilot)
        app = self._run_app(body, store=store, initial_trail=HANDLE_A,
                            focus_pane="%1")
        self.assertEqual(app._t_activated, [HANDLE_A, HANDLE_C])

    def test_a_malformed_request_is_ignored_and_not_retried(self):
        store = _PaneStore()

        async def body(app, pilot):
            for value in ("not-an-id art:trail-beta",
                          "0123456789abcdef0123456789abcdef no-handle",
                          "0123456789abcdef0123456789abcdee art:Bad"):
                store.opts["%1"]["focus"] = value
                await self._poll(app, pilot)
                await self._poll(app, pilot)
            self.assertEqual(app.active_trail_handle, HANDLE_A)
        app = self._run_app(body, store=store,
                             initial_trail=HANDLE_A, focus_pane="%1")
        self.assertEqual(app._t_activated, [HANDLE_A])
        self.assertEqual(
            sum("malformed" in n for n in app._t_notices), 3, app._t_notices)

    def test_only_the_addressed_instance_applies_a_request(self):
        store = _PaneStore()

        async def go():
            _c1, s1 = self._seams()
            patches = s1 + store.patches(self.ta)
            first = bf.make_trails_app(initial_trail=HANDLE_A,
                                       focus_pane="%1")
            second = bf.make_trails_app(initial_trail=HANDLE_A,
                                        focus_pane="%2")
            with contextlib.ExitStack() as ctx:
                for p in patches:
                    ctx.enter_context(p)
                async with first.run_test(size=(200, 48)) as p1, \
                        second.run_test(size=(200, 48)) as p2:
                    await self._settle(first, p1)
                    await self._settle(second, p2)
                    store.write("%2", HANDLE_B)
                    await self._poll(first, p1)
                    await self._poll(second, p2)
                    self.assertEqual(first.active_trail_handle, HANDLE_A)
                    self.assertEqual(second.active_trail_handle, HANDLE_B)
                    await self._settle(first, p1)
                    await self._settle(second, p2)
        self._run(go())
        # Each instance read its own pane only.
        reads = [p for verb, p in store.log if verb == "read"]
        self.assertIn("%1", reads)
        self.assertIn("%2", reads)
        self.assertNotIn("focus", store.opts.get("%1", {}))

    # --- delivery under modals and supersession ------------------------------

    def test_a_request_closes_the_open_selector(self):
        store = _PaneStore()

        async def body(app, pilot):
            await self._wait_screen(app, pilot,
                                    self.ab.board_trail_view.TrailSelectScreen)
            store.write("%1", HANDLE_C)
            await self._poll(app, pilot)
            self.assertIsInstance(app.screen, self.ta.TrailsScreen)
            self.assertEqual(app.active_trail_handle, HANDLE_C)
        app = self._run_app(body, store=store, focus_pane="%1")
        self.assertEqual(app._t_activated, [HANDLE_C])

    def test_a_request_under_a_dialog_waits_for_it_to_close(self):
        store = _PaneStore()

        async def body(app, pilot):
            await pilot.press("enter")
            await self._wait_screen(app, pilot,
                                    self.ab.board_trail_view.TrailDetailScreen)
            store.write("%1", HANDLE_B)
            await self._poll(app, pilot)
            self.assertIsInstance(app.screen,
                                  self.ab.board_trail_view.TrailDetailScreen)
            self.assertEqual(app.active_trail_handle, HANDLE_A)
            await pilot.press("escape")
            await self._settle(app, pilot)
            self.assertEqual(app.active_trail_handle, HANDLE_B)
        app = self._run_app(body, store=store, initial_trail=HANDLE_A,
                            focus_pane="%1")
        self.assertEqual(app._t_activated, [HANDLE_A, HANDLE_B])

    def test_a_newer_request_beats_one_a_dialog_held_back(self):
        store = _PaneStore()

        async def body(app, pilot):
            await pilot.press("enter")
            await self._wait_screen(app, pilot,
                                    self.ab.board_trail_view.TrailDetailScreen)
            store.write("%1", HANDLE_B)
            await self._poll(app, pilot)
            self.assertEqual(app._pending_trail_focus[1], HANDLE_B)
            # Close the dialog and accept C before the resume hook's queued
            # drain of B has run.
            app.pop_screen()
            app._on_trail_focus_value(store.write("%1", HANDLE_C) + " "
                                      + HANDLE_C)
            await self._settle(app, pilot)
            self.assertEqual(app.active_trail_handle, HANDLE_C)
        app = self._run_app(body, store=store, initial_trail=HANDLE_A,
                            focus_pane="%1")
        self.assertEqual(app._t_activated, [HANDLE_A, HANDLE_C])

    def test_an_unknown_trail_is_found_by_one_rescan(self):
        store = _PaneStore()
        seams = self._seams(extra_on_rescan=self._info_for(HANDLE_LATE,
                                                             "Late"))

        async def body(app, pilot):
            store.write("%1", HANDLE_LATE)
            await self._poll(app, pilot)
            self.assertEqual(app.active_trail_handle, HANDLE_LATE)
            self.assertEqual(seams[0]["discover"], 2)
        app = self._run_app(body, store=store, seams=seams,
                             initial_trail=HANDLE_A, focus_pane="%1")
        self.assertEqual(app._t_activated, [HANDLE_A, HANDLE_LATE])

    def test_a_superseded_rescan_activates_nothing(self):
        import threading
        store = _PaneStore()
        gate = threading.Event()
        seams = self._seams(
            extra_on_rescan=self._info_for(HANDLE_LATE, "Late"), gate=gate)

        async def body(app, pilot):
            store.write("%1", HANDLE_LATE)
            app._poll_trail_focus()
            # The poll's read lands, the rescan starts and blocks on `gate`.
            await self._wait_until(pilot, lambda: isinstance(
                app.screen, self.ts.LoadingOverlay))
            store.write("%1", HANDLE_C)
            app._poll_trail_focus()
            await self._wait_until(
                pilot, lambda: app._pending_trail_focus is not None
                and app._pending_trail_focus[1] == HANDLE_C)
            gate.set()
            await self._settle(app, pilot)
            self.assertEqual(app.active_trail_handle, HANDLE_C)
        try:
            app = self._run_app(body, store=store, seams=seams,
                                initial_trail=HANDLE_A, focus_pane="%1")
        finally:
            gate.set()
        self.assertEqual(app._t_activated, [HANDLE_A, HANDLE_C])


# --- Linked trails across tabs (t1957_4) -------------------------------------


class LinkedTrailsTabTests(TrailsAppTestBase):
    """`L` in the tabbed host: a search belongs to the trail — and the revision
    of it — it started from. Each scan is gated, so the test moves first and
    the result lands after; the board twin is `LinkedTrailsTests`.

    Between `L` and the release only `pilot.pause()` is used: `_settle` waits
    for every worker, including the gated scan."""

    _doc_a = TabbedSessionTests._doc_a
    _doc_b = TabbedSessionTests._doc_b
    _info_for = TabbedSessionTests._info_for
    _counting = TabbedSessionTests._counting
    _open_second = TabbedSessionTests._open_second

    async def _two_tabs(self, app, pilot):
        await self._boot_and_select(app, pilot)
        await self._open_second(app, pilot)
        self.assertEqual(list(app._trail_sessions), [HANDLE_A, HANDLE_B])
        app._switch_trail_session(HANDLE_A)
        await self._settle(app, pilot)
        self.assertEqual(app.active_trail_handle, HANDLE_A)

    async def _release(self, app, pilot, *gated):
        for g in gated:
            g.release_all()
        await app.workers.wait_for_complete()
        await self._settle(app, pilot)

    def _linked_screens(self, app):
        return [s for s in app.screen_stack
                if isinstance(s, self.ab.LinkedTrailsScreen)]

    def _tab_case(self, move):
        """Search on A, `move` while the scan is in flight, then release: the
        result must not show, and nothing is said about it."""
        async def go():
            calls, stack = self._counting()
            gated = GatedCalls()
            gated.add(linked_scan([linked_trail()]))
            app = bf.make_trails_app()
            with stack[0], stack[1], stack[2], \
                    patch.object(self.ts, "scan_linked_trails", gated):
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._two_tabs(app, pilot)
                    app.action_trail_linked()
                    await pilot.pause()
                    notes = NoteRecorder(app)
                    await move(app, pilot)
                    await self._release(app, pilot, gated)
                    self.assertEqual(len(gated.calls), 1)
                    self.assertEqual(self._linked_screens(app), [])
                    self.assertEqual(notes.texts(), [])
        self._run(go())

    def test_switching_tabs_drops_the_search(self):
        async def move(app, pilot):
            app._switch_trail_session(HANDLE_B)
            await pilot.pause()
        self._tab_case(move)

    def test_closing_the_origin_tab_drops_the_search(self):
        async def move(app, pilot):
            app._close_trail_session(HANDLE_A)
            await pilot.pause()
        self._tab_case(move)

    def test_a_to_b_to_a_drops_the_search(self):
        """Back on the same trail is not the same search: the result belongs
        to the moment it was asked for."""
        async def move(app, pilot):
            app._switch_trail_session(HANDLE_B)
            await pilot.pause()
            app._switch_trail_session(HANDLE_A)
            await pilot.pause()
        self._tab_case(move)

    def test_two_searches_show_only_the_newest_in_either_order(self):
        for order in ("newest_last", "newest_first"):
            with self.subTest(order=order):
                self._two_searches(order)

    def _two_searches(self, order):
        async def go():
            calls, stack = self._counting()
            gated = GatedCalls()
            old = gated.add(linked_scan([linked_trail(name="OLD trail")]))
            new = gated.add(linked_scan([linked_trail(name="NEW trail")]))
            app = bf.make_trails_app()
            with stack[0], stack[1], stack[2], \
                    patch.object(self.ts, "scan_linked_trails", gated):
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    app.action_trail_linked()
                    await pilot.pause()
                    app.action_trail_linked()
                    for _ in range(3):
                        await pilot.pause()
                    self.assertEqual(len(gated.calls), 2)
                    first, second = (old, new) if order == "newest_last" else (new, old)
                    first.set()
                    for _ in range(5):
                        await pilot.pause()
                    second.set()
                    await self._release(app, pilot, gated)
                    screens = self._linked_screens(app)
                    self.assertEqual(len(screens), 1)
                    self.assertEqual([l.name for l in screens[0].links],
                                     ["NEW trail"])
        self._run(go())

    def test_L_needs_a_loaded_trail(self):
        async def go():
            calls, stack = self._counting()
            app = bf.make_trails_app()
            with stack[0], stack[1], stack[2]:
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._settle(app, pilot)
                    self.assertIs(app.check_action("trail_linked", None), False)
                    await pilot.press("escape")
                    await self._settle(app, pilot)
                    self.assertIs(app.check_action("trail_linked", None), False)
                    await pilot.press("s")
                    await self._wait_screen(
                        app, pilot, self.ab.board_trail_view.TrailSelectScreen)
                    await pilot.press("enter")
                    await self._settle(app, pilot)
                    self.assertIs(app.check_action("trail_linked", None), True)
                    self.assertIn("trail_linked", {
                        a.binding.action
                        for a in app.screen.active_bindings.values()})
                    app._trail_error = "schema invalid"
                    self.assertIs(app.check_action("trail_linked", None), False)
        self._run(go())

    # -- source revision: the REAL reload path -----------------------------------

    def _revision_case(self, change, *, expect_modal):
        """Search, deliver `change(app, deliver)` through `_on_trail_reload`
        (the path an `R`/`d` reload or a watch takes), then release."""
        async def go():
            gated = GatedCalls()
            gated.add(linked_scan([linked_trail()]))
            app = bf.make_trails_app()
            patches = self._patches()
            with patches[0], patches[1], \
                    patch.object(self.ts, "scan_linked_trails", gated):
                async with app.run_test(size=(200, 48)) as pilot:
                    await self._boot_and_select(app, pilot)
                    original = app._trail_active.doc
                    app.action_trail_linked()
                    await pilot.pause()
                    notes = NoteRecorder(app)
                    gens = []
                    app._trail_reload_worker = lambda gen, handle: gens.append(gen)
                    app._reload_active_trail()
                    self.assertEqual(len(gens), 1)

                    def deliver(doc, error="", versions=(), seq=5):
                        app._on_trail_reload(gens[0], HANDLE, doc, error,
                                             list(versions), seq)

                    change(app, deliver, original)
                    await pilot.pause()
                    await self._release(app, pilot, gated)
                    if expect_modal:
                        self.assertEqual(len(self._linked_screens(app)), 1)
                        self.assertFalse(notes.has("changed during"))
                    else:
                        self.assertEqual(self._linked_screens(app), [])
                        self.assertTrue(notes.has(
                            f"Trail {HANDLE} changed during the linked-trail "
                            "search"))
        self._run(go())

    def test_a_reload_with_changed_members_drops_the_search(self):
        def change(app, deliver, original):
            deliver(_wave_doc([self.member_ids[0]]))
            self.assertNotEqual(app._trail_active.doc, original)
        self._revision_case(change, expect_modal=False)

    def test_a_reload_that_adopts_a_load_error_drops_the_search(self):
        def change(app, deliver, original):
            deliver(None, error="schema invalid", versions=["v2"])
            self.assertEqual(app._trail_active.error, "schema invalid")
        self._revision_case(change, expect_modal=False)

    def test_an_unchanged_reload_keeps_the_search(self):
        """Control. `restart_drift=True` replaces the document OBJECT even when
        it is equal, so an identity guard would wrongly drop this search."""
        def change(app, deliver, original):
            deliver(copy.deepcopy(original))
            self.assertIsNot(app._trail_active.doc, original)
            self.assertEqual(app._trail_active.doc, original)
        self._revision_case(change, expect_modal=True)

    def test_a_rescan_with_changed_content_drops_the_search(self):
        def change(app, deliver, original):
            info = TrailInfo(handle=HANDLE, owner_id=self.member_ids[0],
                             owner_archived=False, owner_folded=False,
                             name="Standalone",
                             doc=_wave_doc([self.member_ids[1]]), read_seq=9)
            app._reconcile_discovered_trails([info])
            self.assertNotEqual(app._trail_active.doc, original)
        self._revision_case(change, expect_modal=False)


if __name__ == "__main__":
    unittest.main()
