"""Startup-focus contract for the codebrowser (t1495).

`CodeBrowserApp` set no `AUTO_FOCUS`, so it inherited Textual's
``App.AUTO_FOCUS = "*"`` — applied in ``Screen._compose``, before ``on_mount``.
Which widget that picks depends on which branch ``compose()`` took:

* inside a git repo the first focusable is ``RecentFilesList#recent_files``,
  which is harmless — a scroll container binds arrows, not letters;
* in the ``RuntimeError`` fallback (``get_project_root()`` raised, i.e. not a
  git repo) the sidebar is a bare ``Container`` holding one ``Static``, neither
  focusable, so the winner was ``Input#file_search_input``.

**That second branch no longer mounts the Input at all (t1500).** The box was
inert there — nothing seeds its file list without a ``ProjectFileTree``, and
opening a hit needs the ``_project_root`` that branch does not have — while
still being the first focusable widget and, after t1495 removed the accidental
auto-focus, unreachable by Tab. ``compose()`` now skips it, leaving the code
viewer as the sole focus target. Descriptions of the Input's role below are
therefore **history**: they explain the defect this module was written for, not
what the branch renders today.

In that second branch every non-``priority`` letter binding — ``q`` (Quit)
included — arrived as *search text*, so a codebrowser launched outside a git
repo could not be quit. Measured live in a tmux pane: the trace showed
auto-focus landing on the Input, and after a bare ``q`` the pane was still in
the interpreter with a literal ``q`` sitting in the search box. Same defect the
board carried in t1491.

The fix has two layers and this module pins **both**, one test each:

* ``CodeBrowserScreen.AUTO_FOCUS = ""`` stops the Input taking focus at compose
  — pinned by ``test_the_screen_resolves_to_no_auto_focus_selector``;
* ``CodeBrowserApp._claim_startup_focus`` then anchors focus on a real browse
  target — pinned by the two ``..._startup_focus_is_...`` tests.

**Why the layer-2 pins assert "not None".** With ``AUTO_FOCUS = ""`` in place
but the claim deleted, the screen is simply *unfocused*, and an unfocused
screen routes keys straight to the App bindings — so ``q`` still quits and any
behavioural quit test passes. Only the explicit not-``None`` assertion fails.
That is also why the live pin (``tests/test_codebrowser_startup_focus_live.py``)
can only fail when *both* layers are absent, and why each layer is pinned here
instead.

**Headless is sufficient for both layers here, unlike t1491.** On the board,
``App.run_test`` picked a different widget than a real terminal did, so the
defect was headless-invisible. Measured on this app at Textual 8.2.7 — while
the non-git branch still mounted the box — that branch had so few focusable
widgets that ``run_test`` picked ``Input#file_search_input`` too, identically
to the pty. The live module still ships: the real terminal is the ground truth
and the task asks for a live pin.

Both compose branches are exercised from **one** test class, iterating the two
fixtures with ``subTest``, rather than from a shared base with two subclasses:
a same-module base that defines ``test_*`` methods makes every subclass
re-collect them (``tests/test_collection_structure.py`` enforces this).

**Coverage boundary — the focus mechanism has two entry routes, and only one
is testable here.** ``CodeBrowserApp(initial_focus=…)`` (the cold-launch
``--focus`` flag) is covered below. The *hot handoff* —
``AITASK_CODEBROWSER_FOCUS`` on the tmux session, polled by
``_consume_and_apply_focus`` — cannot be: ``_consume_codebrowser_focus``
returns ``None`` whenever ``self._tmux_session`` is unset, so without a real
tmux session every test here would exercise an early return and pass
vacuously. Stubbing it would test the stub. It is covered end-to-end against a
real session in ``tests/test_codebrowser_startup_focus_live.py`` instead. Both
routes matter to t1495 because both are queued from ``on_mount`` on the same
refresh as the startup claim.

Run: python3 -m pytest tests/test_codebrowser_startup_focus.py -v
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "codebrowser"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from textual.widgets import Input  # noqa: E402

from code_viewer import CodeViewer  # noqa: E402
from codebrowser_app import CodeBrowserApp, CodeBrowserScreen  # noqa: E402
from file_search import FileSearchWidget  # noqa: E402
from file_tree import (  # noqa: E402
    ProjectFileTree,
    RecentFileItem,
    RecentFilesList,
)

#: Matches `RECENT_FILES_HISTORY` in file_tree.py. Seeded explicitly so the git
#: fixture's anchor is deterministically a `RecentFileItem` — accepting "either
#: a RecentFileItem or the RecentFilesList container" would let the anchor
#: silently change without failing anything.
RECENT_FILES_HISTORY = ".aitask-history/recently_opened_files.json"

APP_SIZE = (160, 48)

#: Sampled per `pilot.pause()` cycle rather than only at settle: Textual's
#: auto-focus fires several message-pump cycles before `on_mount`'s deferred
#: claim, so an app that merely *corrects* focus afterwards still swallows
#: keystrokes in between.
BOOT_CYCLES = 8

#: `src/alpha.py` in the git fixture. Eight lines, so a requested line in the
#: middle is a real assertion rather than a coincidence.
ALPHA_SOURCE = (
    "def alpha():\n"
    "    a = 1\n"
    "    b = 2\n"
    "    c = 3\n"
    "    d = 4\n"
    "    e = 5\n"
    "    return a + b + c + d + e\n"
    "# trailing\n"
)
ALPHA_LINES = 8

#: `_apply_focus` defers the cursor/selection write by a real 0.15s timer
#: (`set_timer`), which `pilot.pause()` cannot advance — it pumps messages, not
#: the clock. Tests that assert the landed line must sleep in wall time.
FOCUS_RANGE_TIMER_S = 0.15


def _build_tree(root: Path, want_git: bool) -> Path:
    """A project tree that drives one of `compose()`'s two branches.

    `get_project_root()` resolves via git, so a tree without a repository is
    what drives the `RuntimeError` fallback — the branch carrying the defect.
    """
    root.mkdir(parents=True)
    if not want_git:
        return root

    (root / "src").mkdir()
    # Long enough that a requested line is neither the default (1) nor the last
    # one, so "the range callback ran" is distinguishable from "the file just
    # opened" and from an off-by-one clamp to EOF.
    (root / "src" / "alpha.py").write_text(ALPHA_SOURCE, encoding="utf-8")
    (root / "src" / "beta.py").write_text(
        "def beta():\n    return 2\n", encoding="utf-8")
    for args in (["init", "-q"],
                 ["config", "user.email", "t1495@example.invalid"],
                 ["config", "user.name", "t1495"],
                 ["add", "-A"],
                 ["commit", "-qm", "fixture"]):
        subprocess.run(["git", "-C", str(root), *args],
                       check=True, capture_output=True)
    history = root / RECENT_FILES_HISTORY
    history.parent.mkdir(parents=True, exist_ok=True)
    history.write_text(
        json.dumps([{"path": "src/alpha.py", "timestamp": "2026-01-01"}]),
        encoding="utf-8")
    return root


class CodeBrowserStartupFocusTest(unittest.IsolatedAsyncioTestCase):
    """Startup focus and the Tab cycle, in both of `compose()`'s branches."""

    git_tree: Path
    nogit_tree: Path

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        tmp = tempfile.TemporaryDirectory(prefix="aitask_t1495_cb_")
        cls.addClassCleanup(tmp.cleanup)
        base = Path(tmp.name).resolve()
        cls.git_tree = _build_tree(base / "with_git", want_git=True)
        cls.nogit_tree = _build_tree(base / "without_git", want_git=False)

    def _branches(self):
        return (("git", self.git_tree), ("non-git", self.nogit_tree))

    @contextlib.asynccontextmanager
    async def _booted(self, tree: Path, settle: int = 4, **kwargs):
        """Boot the app with `tree` as cwd, settled, and restore cwd after."""
        old = os.getcwd()
        os.chdir(tree)
        try:
            app = CodeBrowserApp(**kwargs)
            async with app.run_test(size=APP_SIZE) as pilot:
                for _ in range(settle):
                    await pilot.pause()
                yield app, pilot
        finally:
            os.chdir(old)

    @staticmethod
    async def _settle(pilot, times=4):
        for _ in range(times):
            await pilot.pause()

    @staticmethod
    def _name(widget) -> str:
        if widget is None:
            return "None"
        return f"{type(widget).__name__}#{getattr(widget, 'id', None)}"

    # --- layer 1: auto-focus is disabled on the default screen --------------

    async def test_the_screen_resolves_to_no_auto_focus_selector(self):
        """The selector Textual will apply must be falsy, in both branches.

        Asserted through the resolution rule `Screen._update_auto_focus` uses —
        ``app.AUTO_FOCUS if screen.AUTO_FOCUS is None else screen.AUTO_FOCUS``
        — rather than against the literal ``""``. Two ways of re-enabling the
        defect are then both caught: setting `CodeBrowserScreen.AUTO_FOCUS =
        None` (which *inherits* `App.AUTO_FOCUS`, disabling nothing), and
        changing `App.AUTO_FOCUS` under a screen that inherits it.
        """
        for label, tree in self._branches():
            with self.subTest(branch=label):
                async with self._booted(tree) as (app, _pilot):
                    screen = app.screen
                    self.assertIsInstance(screen, CodeBrowserScreen)
                    resolved = (app.AUTO_FOCUS if screen.AUTO_FOCUS is None
                                else screen.AUTO_FOCUS)
                    self.assertFalse(
                        resolved,
                        f"the codebrowser screen would auto-focus {resolved!r}; "
                        "the startup anchor must come from "
                        "`_claim_startup_focus`, not from whichever widget "
                        "happens to be first in the DOM")

    async def test_the_search_input_never_holds_focus_during_boot(self):
        """`#file_search_input` must not own the keyboard at ANY point.

        Since t1500 the **git** leg carries this contract on its own: the
        non-git branch no longer mounts the box, so its leg passes by
        construction. It is still iterated — the day that branch mounts a text
        Input again, this is one of the tests that must see it.
        """
        for label, tree in self._branches():
            with self.subTest(branch=label):
                async with self._booted(tree, settle=0) as (app, pilot):
                    seen = []
                    for _ in range(BOOT_CYCLES):
                        focused = app.screen.focused
                        seen.append(self._name(focused))
                        self.assertNotIsInstance(
                            focused, Input,
                            f"the search box held focus mid-boot; "
                            f"sequence: {seen}")
                        await pilot.pause()

    # --- layer 2: the positive claim ----------------------------------------

    async def test_startup_focus_is_the_recent_file_row_in_a_git_repo(self):
        """Focus is the seeded recent-file row — and is not None.

        The not-``None`` assertion is the load-bearing half: delete
        `_claim_startup_focus` and focus stays `None`, which an
        `assertNotIsInstance(..., Input)` check would happily accept.
        """
        async with self._booted(self.git_tree) as (app, _pilot):
            focused = app.screen.focused
            self.assertIsNotNone(
                focused,
                "nothing holds focus after boot — the startup claim did not run")
            self.assertIsInstance(
                focused, RecentFileItem,
                f"startup focus is {self._name(focused)}, not the seeded "
                "recent-file row")

    async def test_startup_focus_is_the_code_viewer_without_a_sidebar(self):
        """With no sidebar the only anchor left is the code viewer."""
        async with self._booted(self.nogit_tree) as (app, _pilot):
            focused = app.screen.focused
            self.assertIsNotNone(
                focused,
                "nothing holds focus after boot — the startup claim did not run")
            self.assertIsInstance(
                focused, CodeViewer,
                f"startup focus is {self._name(focused)}, not the code viewer")

    async def test_the_non_git_branch_mounts_no_sidebar_focus_target(self):
        """The premise of the whole defect: this branch mounts no sidebar.

        Without this, a future change that restores a focusable sidebar widget
        here would leave the sibling tests passing for a different reason than
        the one they document.

        The search input is asserted **absent** (t1500). It used to be mounted
        — which is exactly what made it the first focusable widget and gave
        t1495 its defect — but it could never work in this branch: its file
        list is seeded from the tree that does not exist here, and opening a
        hit resolves against a `_project_root` that is `None`. `compose()` now
        skips it, which is what leaves the code viewer as the sole focus
        target.
        """
        async with self._booted(self.nogit_tree) as (app, _pilot):
            self.assertEqual(len(app.query(RecentFilesList)), 0)
            self.assertEqual(len(app.query(ProjectFileTree)), 0)
            self.assertEqual(
                len(app.query("#file_search_input")), 0,
                "the search input is mounted in the non-git branch again — it "
                "is inert here (no tracked-file source, no project root) and "
                "unreachable by Tab, so mounting it only re-creates the "
                "dead-end t1500 removed")

    # --- the Tab cycle, which differs per branch ----------------------------

    async def test_tab_cycle_still_reaches_the_search_box_in_a_git_repo(self):
        """Claiming startup focus must not break the Tab affordance.

        The documented cycle is `recent_files → file_tree → search →
        code_viewer → detail`, so from the recent-files anchor it takes **two**
        presses to reach the search box — not one. (One is the board's number,
        where the anchor is a card.)
        """
        async with self._booted(self.git_tree) as (app, pilot):
            self.assertIsInstance(app.screen.focused, RecentFileItem)

            await pilot.press("tab")
            await self._settle(pilot)
            self.assertIsInstance(
                app.screen.focused, ProjectFileTree,
                f"first Tab landed on {self._name(app.screen.focused)}")

            await pilot.press("tab")
            await self._settle(pilot)
            search = app.query_one("#file_search_input", Input)
            self.assertTrue(
                search.has_focus,
                f"second Tab landed on {self._name(app.screen.focused)}, "
                "not the search box")

            # Escape only intercepts when the input has focus AND a value.
            await pilot.press("x")
            await self._settle(pilot)
            self.assertEqual(search.value, "x")
            await pilot.press("escape")
            await self._settle(pilot)
            self.assertEqual(
                search.value, "",
                "Escape did not clear a non-empty search box")

    async def test_tab_is_a_self_loop_without_a_sidebar(self):
        """The cycle degenerates to one widget here — and that is correct.

        `action_toggle_focus` falls through to `_focus_recent_or_tree(None,
        None, code_viewer)` when neither sidebar target is mounted, which
        re-focuses the code viewer.

        Until t1500 that was a **dead-end**, not a degenerate cycle: the
        (inert, unseedable) `#file_search_input` was mounted alongside the
        viewer and Tab could not reach it. t1500 stopped mounting it, so the
        viewer is now genuinely the only focus target and looping back to it is
        the right answer — which is why the fix is `compose()` and not the
        focus cycle. `_focus_recent_or_tree` and `action_toggle_focus` are
        deliberately unchanged.

        The second assertion is what keeps the first honest: a self-loop is
        only correct while nothing else is mounted to reach.
        """
        async with self._booted(self.nogit_tree) as (app, pilot):
            self.assertIsInstance(app.screen.focused, CodeViewer)
            await pilot.press("tab")
            await self._settle(pilot)
            self.assertIsInstance(
                app.screen.focused, CodeViewer,
                f"Tab reached {self._name(app.screen.focused)} — the non-git "
                "focus cycle changed; update this pin and the note that goes "
                "with it")
            reachable = [w for w in app.screen.query("*")
                         if w.can_focus and w.display]
            self.assertEqual(
                [self._name(w) for w in reachable], [self._name(app.screen.focused)],
                "another focusable widget is mounted in the non-git branch, so "
                "the self-loop is a dead-end again rather than a degenerate "
                "cycle — give the cycle a target or stop mounting the widget")

    # --- the fuzzy-search index ---------------------------------------------
    #
    # `_seed_search_index` has TWO callers — `on_mount` and the
    # `TrackedFilesRefreshed` handler — so it gets two pins. One covering only
    # boot would let a mistaken event delegation, or a refresh that leaves
    # `_all_files` stale, pass every other assertion in this module (t1500).

    #: What `git ls-files` reports for a freshly built git fixture. The recent-
    #: files history `_build_tree` writes afterwards is never `git add`ed, so it
    #: is deliberately absent.
    FIXTURE_TRACKED = ["src/alpha.py", "src/beta.py"]

    async def test_the_git_branch_seeds_the_search_index_at_boot(self):
        """`on_mount` feeds the fuzzy box the tree's git-tracked file list.

        The exact list, not "non-empty": seeding it from the wrong source (the
        recent-files history, say, or an unfiltered directory walk) would
        satisfy a truthiness check while breaking the feature.

        Only the git branch is asserted. The non-git branch mounts no
        `FileSearchWidget` at all (t1500) — that absence is pinned by
        `test_the_non_git_branch_mounts_no_sidebar_focus_target`, and there is
        no index there to have an opinion about.
        """
        async with self._booted(self.git_tree) as (app, _pilot):
            search = app.query_one("#file_search", FileSearchWidget)
            self.assertEqual(
                search._all_files, self.FIXTURE_TRACKED,
                "the search index was not seeded from the tree's tracked files")

    async def test_a_tracked_file_refresh_reseeds_the_search_index(self):
        """A refresh reaches the index — driven through the REAL producer.

        `refresh_tracked_files()` is what re-runs `git ls-files` and posts
        `TrackedFilesRefreshed`; hand-posting the message instead would test the
        handler while leaving the wiring between them unproven.

        `git ls-files` reports staged paths, so `git add` alone moves the
        tracked set — no commit needed.

        **Its own fixture tree.** This test mutates the repository, and
        `cls.git_tree` is class-scoped and shared with every other test here.
        """
        tmp = tempfile.TemporaryDirectory(prefix="aitask_t1500_refresh_")
        self.addCleanup(tmp.cleanup)
        tree = _build_tree(Path(tmp.name).resolve() / "with_git", want_git=True)

        async with self._booted(tree) as (app, pilot):
            search = app.query_one("#file_search", FileSearchWidget)
            # Precondition, so the post-refresh assertion below is a real
            # transition rather than a list that happened to contain gamma.
            self.assertEqual(
                search._all_files, self.FIXTURE_TRACKED,
                "precondition failed: the boot seeding did not run")

            (tree / "src" / "gamma.py").write_text(
                "def gamma():\n    return 3\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(tree), "add", "src/gamma.py"],
                           check=True, capture_output=True)

            app.query_one("#file_tree", ProjectFileTree).refresh_tracked_files()
            await self._settle(pilot)

            self.assertEqual(
                search._all_files, [*self.FIXTURE_TRACKED, "src/gamma.py"],
                "the tracked-file refresh never reached the search index")

    # --- the claim must not displace an explicit focus request --------------

    async def _settle_focus_range(self, pilot):
        """Let `_apply_focus`'s 0.15s `set_timer` fire, then drain its work."""
        await asyncio.sleep(FOCUS_RANGE_TIMER_S * 3)
        await self._settle(pilot, times=6)

    async def test_initial_focus_request_keeps_both_the_file_and_an_anchor(self):
        """`initial_focus` lands its file AND line, and boot still has an anchor.

        `_claim_startup_focus` is queued *before* `_apply_focus` so anything
        that does touch focus later wins, while the anchor Textual's auto-focus
        used to supply on this path is preserved. Skipping the claim when
        `initial_focus` is set would leave this path with no focus at all —
        which is what an earlier draft of the fix did.

        The **line** is asserted, not just the filename: the cursor write lands
        in `_apply_focus_range` behind a `set_timer`, a second deferred callback
        the claim could in principle disturb. Checking only the file would pass
        with that callback broken.
        """
        async with self._booted(self.git_tree, settle=12,
                                initial_focus="src/alpha.py:4") as (app, pilot):
            await self._settle_focus_range(pilot)

            self.assertIsNotNone(
                app._current_file_path,
                "the requested initial_focus file was never opened")
            self.assertEqual(
                Path(app._current_file_path).name, "alpha.py",
                f"opened {app._current_file_path}, not the requested file")

            viewer = app.query_one("#code_viewer", CodeViewer)
            self.assertEqual(viewer._total_lines, ALPHA_LINES)
            # `_apply_focus_range` stores 0-based: line 4 -> index 3. Neither the
            # default (0) nor a clamp to EOF (7).
            self.assertEqual(
                viewer._cursor_line, 3,
                f"cursor is on line {viewer._cursor_line + 1}, not the "
                "requested line 4")
            self.assertFalse(
                viewer._selection_active,
                "a single-line request must not leave a selection")

            self.assertIsNotNone(
                app.screen.focused,
                "the --focus path booted with nothing focused")
            self.assertNotIsInstance(app.screen.focused, Input)

    async def test_initial_focus_request_applies_a_line_range(self):
        """A `N-M` request lands as a selection, not just a cursor move.

        The range arm of `_apply_focus_range` is a separate branch from the
        single-line arm above; a regression that dropped the selection write
        would otherwise be invisible.
        """
        async with self._booted(self.git_tree, settle=12,
                                initial_focus="src/alpha.py:2-5") as (app, pilot):
            await self._settle_focus_range(pilot)

            viewer = app.query_one("#code_viewer", CodeViewer)
            self.assertTrue(
                viewer._selection_active,
                "a range request left no active selection")
            # 0-based, inclusive: lines 2..5 -> indices 1..4.
            self.assertEqual((viewer._selection_start, viewer._selection_end),
                             (1, 4))
            self.assertEqual(viewer._cursor_line, 4)


if __name__ == "__main__":
    unittest.main()
