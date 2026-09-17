"""Stale-screen dismiss guard for brainstorm modals (t1816).

Textual's ``Screen.dismiss`` unconditionally calls ``app.pop_screen()``, which
pops *whatever screen is on top*. A stale ``Esc`` still dispatched to an
already-closed modal therefore popped the screen beneath it: from the explore
wizard's config step, ``H`` then rapid ``Esc`` presses closed the help dialog,
then destroyed the wizard, then emptied the stack (``ScreenStackError`` → the
TUI died). ``lib/guarded_dismiss.GuardedModalScreen`` makes dismissing an
inactive screen a no-op, and every brainstorm screen derives from it.

``guarded_dismiss`` is imported inside the tests that need it, so the wizard red
proof runs (and fails) against the unfixed tree on its own.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import yaml  # noqa: E402

from textual.app import App, ComposeResult, ScreenStackError  # noqa: E402
from textual.await_complete import AwaitComplete  # noqa: E402
from textual.screen import ModalScreen, Screen  # noqa: E402
from textual.widgets import Label  # noqa: E402

from brainstorm.brainstorm_app import ActionsWizardScreen, BrainstormApp  # noqa: E402
from brainstorm.modals import (  # noqa: E402
    ImportProposalFilePicker,
    InitSessionModal,
    OperationHelpModal,
)
from brainstorm.utils import next_step_id  # noqa: E402

BRAINSTORM_DIR = REPO_ROOT / ".aitask-scripts" / "brainstorm"
DIFFVIEWER_DIR = REPO_ROOT / ".aitask-scripts" / "diffviewer"
SECTION_VIEWER = REPO_ROOT / ".aitask-scripts" / "lib" / "section_viewer.py"

PROPOSAL = """\
# Proposal

<!-- section: auth -->
""" + "Use JWT.\n" * 10 + """\
<!-- /section: auth -->

<!-- section: storage -->
""" + "Postgres.\n" * 10 + """\
<!-- /section: storage -->
"""


# --------------------------------------------------------------------------- #
# Wizard harness (shape copied from test_brainstorm_wizard_nav_consolidation)
# --------------------------------------------------------------------------- #
class _Sec:
    def __init__(self, name, dims=None):
        self.name = name
        self.dimensions = dims or []


def _make_session(td: str, node_id: str) -> Path:
    session = Path(td)
    (session / "br_nodes").mkdir(parents=True, exist_ok=True)
    (session / "br_proposals").mkdir(parents=True, exist_ok=True)
    (session / "br_nodes" / f"{node_id}.yaml").write_text(
        yaml.safe_dump({"description": "n", "parents": [], "created_at": "2026-06-09 10:00"}),
        encoding="utf-8",
    )
    (session / "br_proposals" / f"{node_id}.md").write_text(PROPOSAL, encoding="utf-8")
    return session


class _WizardHost(App):
    task_num = "0"

    def __init__(self, session_path: Path) -> None:
        super().__init__()
        self.session_path = session_path
        self.read_only = False

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(
            ActionsWizardScreen(op_key="explore", node_id="n001", marked=[])
        )

    def _node_has_sections(self, node: str) -> bool:
        return True

    def _node_sections(self, node: str):
        return [_Sec("auth"), _Sec("storage")]


class WizardStaleEscapeTests(unittest.TestCase):
    async def _wizard_on_config_with_help(self, app, pilot):
        await pilot.pause()
        await pilot.pause()
        wizard = app.screen
        self.assertIsInstance(wizard, ActionsWizardScreen)
        self.assertEqual(wizard._wizard_step_id, "section_select")
        wizard._render_wizard_step(
            next_step_id(wizard._wizard_ctx(), "section_select")
        )
        await pilot.pause()
        self.assertEqual(wizard._wizard_step_id, "config")
        wizard.action_op_help()
        await pilot.pause()
        self.assertIsInstance(app.screen, OperationHelpModal)
        return wizard, app.screen

    def test_help_close_repeated_keeps_wizard(self):
        # Red proof: the 2nd close popped the wizard, the 3rd raised
        # ScreenStackError on the 1-deep stack.
        async def runner():
            app = _WizardHost(_make_session(tempfile.mkdtemp(), "n001"))
            async with app.run_test(size=(160, 48)) as pilot:
                wizard, help_modal = await self._wizard_on_config_with_help(app, pilot)
                step = wizard._wizard_step
                for _ in range(3):
                    help_modal.action_close()
                    await pilot.pause()
                self.assertIs(app.screen, wizard)
                self.assertEqual(wizard._wizard_step_id, "config")
                self.assertEqual(wizard._wizard_step, step)
                self.assertTrue(app.is_running)

        asyncio.run(runner())

    def test_escape_after_help_steps_wizard_back(self):
        async def runner():
            app = _WizardHost(_make_session(tempfile.mkdtemp(), "n001"))
            async with app.run_test(size=(160, 48)) as pilot:
                wizard, _ = await self._wizard_on_config_with_help(app, pilot)
                await pilot.press("escape")
                await pilot.pause()
                self.assertIs(app.screen, wizard)
                self.assertEqual(wizard._wizard_step_id, "config")
                await pilot.press("escape")
                await pilot.pause()
                self.assertIs(app.screen, wizard)
                self.assertEqual(wizard._wizard_step_id, "section_select")

        asyncio.run(runner())


# --------------------------------------------------------------------------- #
# Helper contract
# --------------------------------------------------------------------------- #
class _StackHost(App):
    def compose(self) -> ComposeResult:
        yield Label("base")


def _guarded_screen_cls():
    from guarded_dismiss import GuardedModalScreen

    class _Guarded(GuardedModalScreen):
        def compose(self) -> ComposeResult:
            yield Label("guarded")

    return _Guarded


class _Plain(ModalScreen):
    def compose(self) -> ComposeResult:
        yield Label("plain")


class GuardedDismissContractTests(unittest.TestCase):
    def test_active_dismiss_delivers_result(self):
        Guarded = _guarded_screen_cls()

        async def runner():
            app = _StackHost()
            got = []
            async with app.run_test() as pilot:
                screen = Guarded()
                app.push_screen(screen, callback=got.append)
                await pilot.pause()
                self.assertIs(app.screen, screen)
                screen.dismiss("x")
                await pilot.pause()
                self.assertEqual(got, ["x"])
                self.assertEqual(len(app.screen_stack), 1)

        asyncio.run(runner())

    def test_inactive_dismiss_is_noop_and_logs(self):
        Guarded = _guarded_screen_cls()

        async def runner():
            app = _StackHost()
            got = []
            async with app.run_test() as pilot:
                a, b = Guarded(), Guarded()
                app.push_screen(a, callback=got.append)
                app.push_screen(b)
                await pilot.pause()
                warnings = []
                # `app.log` is `app._logger`; `Logger.warning` is a read-only
                # property, so swap the logger itself for the one call.
                real_logger = app._logger
                app._logger = SimpleNamespace(
                    warning=lambda *args, **kw: warnings.append(args)
                )
                try:
                    ret = a.dismiss("a")
                finally:
                    app._logger = real_logger
                self.assertIsInstance(ret, AwaitComplete)
                self.assertTrue(ret.is_done)
                await ret
                await pilot.pause()
                self.assertIs(app.screen, b)
                self.assertIn(a, app.screen_stack)
                self.assertEqual(got, [])
                self.assertEqual(len(warnings), 1)

        asyncio.run(runner())

    def test_detached_dismiss_is_safe_noop(self):
        # `screen.log` resolves through `screen.app`, which raises
        # NoActiveAppError for a never-pushed screen — dismiss must not log there.
        Guarded = _guarded_screen_cls()

        async def runner():
            ret = Guarded().dismiss("x")
            self.assertIsInstance(ret, AwaitComplete)
            self.assertTrue(ret.is_done)
            await ret

        asyncio.run(runner())

    def test_is_active_screen_false_without_app(self):
        from guarded_dismiss import is_active_screen

        self.assertFalse(is_active_screen(_guarded_screen_cls()()))

    def test_is_active_screen_propagates_unexpected_errors(self):
        from guarded_dismiss import is_active_screen
        from textual.app import UnknownModeError

        for exc in (RuntimeError("boom"), UnknownModeError("no mode")):
            class _Broken:
                @property
                def app(self, _exc=exc):
                    raise _exc

            with self.assertRaises(type(exc)):
                is_active_screen(_Broken())

    def test_unguarded_control_still_raises(self):
        # Negative control: Textual itself still pops whatever is on top. If a
        # Textual upgrade adds its own guard this fails, and the helper can go.
        async def runner():
            app = _StackHost()
            async with app.run_test() as pilot:
                screen = _Plain()
                app.push_screen(screen)
                await pilot.pause()
                screen.dismiss(None)
                await pilot.pause()
                with self.assertRaises(ScreenStackError):
                    screen.dismiss(None)

        asyncio.run(runner())

    def test_parent_dismiss_from_child_result_callback(self):
        # A result callback runs via call_next after the child pops, so the
        # parent is the active screen again when it dismisses itself.
        async def runner():
            app = _StackHost()
            got = []
            async with app.run_test(size=(120, 40)) as pilot:
                init = InitSessionModal("0")
                app.push_screen(init, callback=got.append)
                await pilot.pause()
                init.on_import()
                await pilot.pause()
                picker = app.screen
                self.assertIsInstance(picker, ImportProposalFilePicker)
                picker.dismiss("/tmp/x.md")
                await pilot.pause()
                await pilot.pause()
                self.assertEqual(got, ["import:/tmp/x.md"])
                self.assertEqual(len(app.screen_stack), 1)

        asyncio.run(runner())


# --------------------------------------------------------------------------- #
# Source enforcement
# --------------------------------------------------------------------------- #
def _screen_source_files():
    """Brainstorm plus every overlay it can push: the section viewer and the
    diff viewer's screen set (DiffViewerScreen → SummaryScreen / MergeScreen →
    SaveMergeDialog; the plan manager lives in the same package)."""
    return (
        sorted(BRAINSTORM_DIR.glob("*.py"))
        + sorted(DIFFVIEWER_DIR.glob("*.py"))
        + [SECTION_VIEWER]
    )


def _base_name(base):
    if isinstance(base, ast.Subscript):
        base = base.value
    return base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", None)


class ScreensGuardedTests(unittest.TestCase):
    def test_no_unguarded_screen_bases(self):
        offenders = []
        for path in _screen_source_files():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                names = [_base_name(b) for b in node.bases]
                bare = [n for n in names if n in ("ModalScreen", "Screen")]
                if bare and "GuardedDismissMixin" not in names:
                    offenders.append(f"{path.name}:{node.lineno} {node.name}({bare[0]})")
        self.assertEqual(
            offenders, [],
            "screens must derive from GuardedModalScreen or mix in GuardedDismissMixin",
        )

    def test_no_direct_pop_screen(self):
        # app.pop_screen() pops whatever is on top — the same stale-key cascade
        # the guard exists to stop. Close a screen with self.dismiss() instead.
        offenders = []
        for path in _screen_source_files():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "pop_screen"
                ):
                    offenders.append(f"{path.name}:{node.lineno}")
        self.assertEqual(offenders, [])

    def test_screen_classes_are_guarded(self):
        from guarded_dismiss import GuardedDismissMixin
        import brainstorm.brainstorm_app as app_mod
        import brainstorm.modals as modals_mod
        import diffviewer.diff_viewer_screen as dvs_mod
        import diffviewer.merge_screen as merge_mod
        import diffviewer.plan_manager_screen as pm_mod
        import section_viewer as sv_mod

        checked = 0
        for mod in (modals_mod, app_mod, dvs_mod, merge_mod, pm_mod, sv_mod):
            for _, cls in inspect.getmembers(mod, inspect.isclass):
                if cls.__module__ != mod.__name__ or not issubclass(cls, Screen):
                    continue
                checked += 1
                self.assertTrue(
                    issubclass(cls, GuardedDismissMixin), f"{cls.__qualname__} is unguarded"
                )
        self.assertGreaterEqual(checked, 23)


# --------------------------------------------------------------------------- #
# Overlays pushed over a guarded brainstorm screen
# --------------------------------------------------------------------------- #
class StackedOverlayTests(unittest.TestCase):
    """A stale close on an overlay must not pop the guarded screen beneath it:
    the parent's guard cannot intercept another screen's pop."""

    async def _push_parent(self, app, pilot):
        parent = _guarded_screen_cls()()
        app.push_screen(parent)
        await pilot.pause()
        return parent

    def test_section_viewer_repeated_close_keeps_parent(self):
        from section_viewer import SectionViewerScreen

        async def runner():
            app = _StackHost()
            async with app.run_test(size=(120, 40)) as pilot:
                parent = await self._push_parent(app, pilot)
                viewer = SectionViewerScreen("# Title\n\nbody\n", title="t")
                app.push_screen(viewer)
                await pilot.pause()
                for _ in range(3):
                    viewer.action_close()
                    await pilot.pause()
                self.assertIs(app.screen, parent)
                self.assertTrue(app.is_running)

        asyncio.run(runner())

    def _plans(self):
        td = Path(tempfile.mkdtemp())
        a, b = td / "a.md", td / "b.md"
        a.write_text("# Plan\n\n## Step\n\nalpha\n", encoding="utf-8")
        b.write_text("# Plan\n\n## Step\n\nbeta\n", encoding="utf-8")
        return str(a), str(b)

    async def _push_diff_viewer(self, app, pilot):
        from diffviewer.diff_viewer_screen import DiffViewerScreen

        main, other = self._plans()
        viewer = DiffViewerScreen(main, [other], mode="classical")
        app.push_screen(viewer)
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        return viewer

    def test_diff_viewer_repeated_back_keeps_parent(self):
        async def runner():
            app = _StackHost()
            async with app.run_test(size=(120, 40)) as pilot:
                parent = await self._push_parent(app, pilot)
                viewer = await self._push_diff_viewer(app, pilot)
                for _ in range(3):
                    viewer.action_back()
                    await pilot.pause()
                self.assertIs(app.screen, parent)
                self.assertTrue(app.is_running)

        asyncio.run(runner())

    def test_diff_summary_repeated_close_keeps_viewer_and_parent(self):
        from diffviewer.diff_viewer_screen import SummaryScreen

        async def runner():
            app = _StackHost()
            async with app.run_test(size=(120, 40)) as pilot:
                parent = await self._push_parent(app, pilot)
                viewer = await self._push_diff_viewer(app, pilot)
                viewer.action_summary()
                await pilot.pause()
                summary = app.screen
                self.assertIsInstance(summary, SummaryScreen)
                for _ in range(3):
                    summary.action_dismiss_summary()
                    await pilot.pause()
                self.assertIs(app.screen, viewer)
                self.assertIn(parent, app.screen_stack)

        asyncio.run(runner())


# --------------------------------------------------------------------------- #
# Secondary defect: the 30s runtime-refresh timer stacked on every reload
# --------------------------------------------------------------------------- #
class _FakeTimer:
    def __init__(self) -> None:
        self.stops = 0

    def stop(self) -> None:
        self.stops += 1


class StatusRefreshTimerTests(unittest.TestCase):
    def test_status_refresh_timer_not_stacked(self):
        app = BrainstormApp.__new__(BrainstormApp)
        app._status_refresh_timer = None  # what __init__ sets; __new__ skips it
        made = []

        def fake_set_interval(interval, callback):
            made.append(_FakeTimer())
            return made[-1]

        app.set_interval = fake_set_interval
        app._restart_status_refresh_timer()
        self.assertIs(app._status_refresh_timer, made[0])
        app._restart_status_refresh_timer()
        self.assertEqual(made[0].stops, 1)
        self.assertEqual(made[1].stops, 0)
        self.assertIs(app._status_refresh_timer, made[1])


if __name__ == "__main__":
    unittest.main()
