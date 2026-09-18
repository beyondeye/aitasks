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
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import board_fixture as bf  # noqa: E402
import keybinding_registry  # noqa: E402
from test_board_bytrail_view import _wave_doc  # noqa: E402
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
        for b in self.ta.TrailsApp.BINDINGS:
            if b.action in MIXIN_ACTIONS:
                continue
            with self.subTest(action=b.action):
                self.assertIn(b.action, board)
                self.assertEqual((b.key, b.description), board[b.action])

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
    #: loaded modules whose FILE is the board implementation. Checked by file
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
                  if str(getattr(m, "__file__", "") or "").endswith("board/aitask_board.py"))
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


if __name__ == "__main__":
    unittest.main()
