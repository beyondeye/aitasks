"""Footer binding-scope guard for the brainstorm retry-apply action (t1018_1,
t1039).

Boots a real ``BrainstormApp`` over a temp session and asserts that the
``ctrl+r`` ``retry_initializer_apply`` binding is gated to the (R)unning tab —
present in the footer there and ABSENT from it on every other tab.

The guard asserts the **rendered footer surface** — membership in
``screen.active_bindings`` (exactly what ``Footer.compose`` iterates) — not
``check_action``'s raw return value. That distinction is the whole point of
t1039: t1018_1's ``check_action`` returned ``None`` off the Running tab, which
*passed* a return-value assertion, yet Textual 8.2.7 keeps ``None`` bindings in
``active_bindings`` (``enabled=False``) and the footer renders them DIMMED — so
``ctrl+r`` still leaked (greyed) onto every tab and the live manual verification
failed. ``check_action`` now returns ``False``, which Textual drops from
``active_bindings`` entirely (``screen.py``: ``if action_state is False:
continue``). Asserting on ``active_bindings`` membership fails on the old
``None`` code, making this a real regression guard.

t1018_2 removed the ``retry_explorer_apply`` / ``retry_synthesizer_apply``
actions (and their undeliverable ``ctrl+shift+x`` / ``ctrl+shift+y`` chords),
re-homing that logic onto the Running-tab GroupRow ``S`` action — so only the
initializer action remains gated here. The GroupRow recovery actions are
covered by ``test_brainstorm_group_recovery.py``.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agentcrew.agentcrew_utils as ac_mod  # noqa: E402
import brainstorm.brainstorm_session as bs_mod  # noqa: E402

from textual.widgets import TabbedContent  # noqa: E402

from brainstorm.brainstorm_app import BrainstormApp  # noqa: E402


class RetryActionScopeTests(unittest.TestCase):

    TASK_NUM = "99201"

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_binding_scope_")
        self._orig_dir = ac_mod.AGENTCREW_DIR
        ac_mod.AGENTCREW_DIR = str(Path(self.tmpdir) / "crews")
        bs_mod.AGENTCREW_DIR = ac_mod.AGENTCREW_DIR
        wt = bs_mod.crew_worktree(self.TASK_NUM)
        wt.mkdir(parents=True)
        bs_mod.init_session(
            self.TASK_NUM, "aitasks/fake.md", "tester@example.com",
            "Initial spec for the binding-scope test session.",
        )

    def tearDown(self):
        ac_mod.AGENTCREW_DIR = self._orig_dir
        bs_mod.AGENTCREW_DIR = self._orig_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run(self, coro):
        return asyncio.run(coro)

    @staticmethod
    async def _settle(pilot, n=4):
        for _ in range(n):
            await pilot.pause()

    async def _activate_tab(self, app, pilot, tab_id):
        # Drive check_action's input (the active tab id) directly rather than
        # through the tab-switch keybinding, whose routing depends on the
        # currently-focused widget. check_action reads ``TabbedContent.active``,
        # so this exercises the real gating logic in isolation.
        app.query_one(TabbedContent).active = tab_id
        await self._settle(pilot)
        self.assertEqual(app.query_one(TabbedContent).active, tab_id)

    @staticmethod
    def _footer_binding(app, key):
        # ``active_bindings`` is what ``Footer.compose`` iterates — membership
        # here == visible in the footer. It is recomputed live on access (calls
        # check_action per binding), so reading it after a tab switch reflects
        # the current gating with no footer-recompose timing needed. Returns the
        # ActiveBinding for ``key`` (e.g. ``ctrl+r``) or None if absent/hidden.
        return app.screen.active_bindings.get(key)

    def test_retry_action_in_footer_only_on_running_tab(self):
        # The retry-apply binding key (``ctrl+r`` -> retry_initializer_apply).
        RETRY_KEY = "ctrl+r"

        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                await self._settle(pilot)

                # (R)unning tab — the owning surface: present in the footer and
                # enabled (not dimmed).
                await self._activate_tab(app, pilot, "tab_running")
                ab = self._footer_binding(app, RETRY_KEY)
                self.assertIsNotNone(
                    ab, f"{RETRY_KEY} should be in the footer on the Running tab"
                )
                self.assertEqual(ab.binding.action, "retry_initializer_apply")
                self.assertTrue(
                    ab.enabled,
                    f"{RETRY_KEY} should be enabled (not dimmed) on the Running tab",
                )
                # check_action contract: active on the owning surface.
                self.assertTrue(app.check_action("retry_initializer_apply", None))

                # (B)rowse / (S)ession tabs — ABSENT from the footer (the t1039
                # leak: the old `return None` left it present-but-dimmed here).
                for tab in ("tab_browse", "tab_session"):
                    await self._activate_tab(app, pilot, tab)
                    self.assertIsNone(
                        self._footer_binding(app, RETRY_KEY),
                        f"{RETRY_KEY} must not leak into the footer on {tab}",
                    )
                    # check_action returns False (removed), not None (dimmed).
                    self.assertIs(
                        app.check_action("retry_initializer_apply", None),
                        False,
                        f"check_action must return False (not None) on {tab}",
                    )

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
