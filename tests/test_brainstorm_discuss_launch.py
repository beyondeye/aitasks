"""Discuss node operation launch path in the brainstorm TUI (t1823_4).

Boots a real `BrainstormApp` over a temp session, then drives the Operations
dialog's result callback (`_on_node_action_result`) with ``"discuss"`` and
asserts the launch contract:

* the op opens `AgentCommandScreen`, never the Actions wizard, and dispatches
  no crew operation;
* the argv is ``<task_num> <sorted marked set>`` (or the cursor alone), filtered
  to nodes that still exist — and a vanished *unmarked* cursor does not block a
  discuss of marked nodes that survive;
* every dialog result dispatches the dialog's finalized ``screen.full_command``
  verbatim (the t1225 regression: rebuilding the default wrapper argv would
  discard a changed model / temporary profile);
* the default wrapper argv is rebuilt ONLY when no dialog was available.

`push_screen` is replaced by a recorder, so these tests do not exercise the
dialog's own screen-stack behaviour — that is covered by
`SharedLaunchDialogGuardTests` in `test_brainstorm_guarded_dismiss.py`.
"""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agentcrew.agentcrew_utils as ac_mod  # noqa: E402
import brainstorm.brainstorm_app as bapp  # noqa: E402
import brainstorm.brainstorm_session as bs_mod  # noqa: E402

from agent_command_screen import AgentCommandScreen  # noqa: E402
from agent_launch_utils import TmuxLaunchConfig  # noqa: E402
from brainstorm.brainstorm_app import ActionsWizardScreen, BrainstormApp  # noqa: E402

DEFAULT_CMD = "codex -m default-model '$aitask-brainstorm-discuss 99002 n001'"
EDITED_CMD = (
    "codex -m other-model "
    "'/aitask-brainstorm-discuss --profile default 99002 n001'"
)
WRAPPER = str(bapp._REPO_ROOT / ".aitask-scripts" / "aitask_codeagent.sh")


class DiscussLaunchTests(unittest.TestCase):

    TASK_NUM = "99002"

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_discuss_launch_")
        self._orig_dir = ac_mod.AGENTCREW_DIR
        ac_mod.AGENTCREW_DIR = str(Path(self.tmpdir) / "crews")
        bs_mod.AGENTCREW_DIR = ac_mod.AGENTCREW_DIR
        wt = bs_mod.crew_worktree(self.TASK_NUM)
        wt.mkdir(parents=True)
        bs_mod.init_session(
            self.TASK_NUM, "aitasks/fake.md", "tester@example.com",
            "Initial spec for the discuss launch test session.",
        )

    def tearDown(self):
        ac_mod.AGENTCREW_DIR = self._orig_dir
        bs_mod.AGENTCREW_DIR = self._orig_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------ #
    # Harness
    # ------------------------------------------------------------------ #
    def _drive(self, body, *, nodes, dry_run=DEFAULT_CMD, binary="codex",
               which="/usr/bin/codex", terminal="xterm"):
        """Boot the app, then run ``body(app, env)`` synchronously with every
        launch side effect stubbed. ``nodes`` is what `list_nodes` reports as
        existing at callback time."""

        async def runner():
            app = BrainstormApp(self.TASK_NUM)
            async with app.run_test(size=(160, 50)) as pilot:
                for _ in range(5):
                    await pilot.pause()
                env = mock.Mock()
                env.pushed = []
                env.notices = []
                app.push_screen = lambda screen, callback=None, **kw: (
                    env.pushed.append((screen, callback))
                )
                app.notify = lambda msg, **kw: env.notices.append(
                    (msg, kw.get("severity", "information"))
                )
                app.suspend = contextlib.nullcontext
                app._execute_design_op = env.execute_design_op
                with contextlib.ExitStack() as stack:
                    def patch(name, **kw):
                        m = stack.enter_context(mock.patch.object(bapp, name, **kw))
                        setattr(env, name, m)

                    patch("list_nodes", return_value=list(nodes))
                    patch("resolve_agent_binary",
                          return_value=("codex", binary, None) if binary
                          else (None, None, "no agent configured"))
                    stack.enter_context(
                        mock.patch.object(bapp.shutil, "which", return_value=which))
                    patch("resolve_dry_run_command", return_value=dry_run)
                    patch("resolve_agent_string", return_value="codex/default")
                    patch("resolve_skill_profile", return_value="fast")
                    patch("launch_in_tmux", return_value=(4242, None))
                    patch("maybe_spawn_minimonitor")
                    patch("find_terminal", return_value=terminal)
                    patch("spawn_in_terminal")
                    env.call = stack.enter_context(
                        mock.patch.object(bapp.subprocess, "call", return_value=0))
                    body(app, env)

        asyncio.run(runner())

    def _errors(self, env):
        return [m for m, sev in env.notices if sev == "error"]

    def _only_dialog(self, env):
        self.assertEqual(len(env.pushed), 1, env.pushed)
        screen, callback = env.pushed[0]
        self.assertIsInstance(screen, AgentCommandScreen)
        return screen, callback

    def _assert_no_crew_op(self, env):
        for screen, _cb in env.pushed:
            self.assertNotIsInstance(screen, ActionsWizardScreen)
        env.execute_design_op.assert_not_called()

    # ------------------------------------------------------------------ #
    # Target resolution
    # ------------------------------------------------------------------ #
    def test_cursor_only_opens_dialog_not_wizard(self):
        def body(app, env):
            app._selection.marked.clear()
            app._selection.set_primary("n001")
            app._on_node_action_result("n001", "discuss")
            screen, _cb = self._only_dialog(env)
            self.assertEqual(screen.operation, "discuss")
            self.assertEqual(screen.operation_args, [self.TASK_NUM, "n001"])
            self.assertEqual(screen.default_window_name, f"agent-discuss-{self.TASK_NUM}")
            env.resolve_dry_run_command.assert_called_once_with(
                bapp._REPO_ROOT, "discuss", self.TASK_NUM, "n001")
            self._assert_no_crew_op(env)
            self.assertEqual(self._errors(env), [])

        self._drive(body, nodes=["n000_init", "n001"])

    def test_marked_set_is_sorted_argv(self):
        def body(app, env):
            app._selection.set_primary("n003")
            for n in ("n003", "n001"):
                app._selection.mark(n)
            app._on_node_action_result("n003", "discuss")
            screen, _cb = self._only_dialog(env)
            self.assertEqual(screen.operation_args, [self.TASK_NUM, "n001", "n003"])
            env.resolve_dry_run_command.assert_called_once_with(
                bapp._REPO_ROOT, "discuss", self.TASK_NUM, "n001", "n003")
            self._assert_no_crew_op(env)

        self._drive(body, nodes=["n001", "n003"])

    def test_all_targets_vanished_notifies_and_launches_nothing(self):
        def body(app, env):
            app._selection.mark("n001")
            app._selection.mark("n002")
            app._on_node_action_result("n001", "discuss")
            self.assertEqual(env.pushed, [])
            self.assertEqual(self._errors(env), ["Selected node(s) no longer exist."])
            env.resolve_dry_run_command.assert_not_called()
            env.spawn_in_terminal.assert_not_called()

        self._drive(body, nodes=["n000_init"])

    def test_vanished_unmarked_cursor_does_not_block_marked_targets(self):
        def body(app, env):
            app._selection.mark("n001")
            app._selection.mark("n002")
            app._selection.set_primary("n009")
            app._on_node_action_result("n009", "discuss")
            screen, _cb = self._only_dialog(env)
            self.assertEqual(screen.operation_args, [self.TASK_NUM, "n001", "n002"])
            self.assertEqual(self._errors(env), [])
            self.assertEqual(
                [m for m, sev in env.notices if sev == "warning"], [])

        self._drive(body, nodes=["n001", "n002"])

    def test_vanished_cursor_still_blocks_other_ops(self):
        # Control: the cursor guard is unchanged for every non-discuss op.
        def body(app, env):
            app._selection.mark("n001")
            app._selection.mark("n002")
            app._selection.set_primary("n009")
            app._on_node_action_result("n009", "explore")
            self.assertEqual(env.pushed, [])
            self.assertEqual(self._errors(env), ["Node 'n009' no longer exists."])

        self._drive(body, nodes=["n001", "n002"])

    def test_partly_vanished_marked_set_warns_and_launches_survivors(self):
        def body(app, env):
            app._selection.mark("n001")
            app._selection.mark("n002")
            app._on_node_action_result("n001", "discuss")
            screen, _cb = self._only_dialog(env)
            self.assertEqual(screen.operation_args, [self.TASK_NUM, "n001"])
            warnings = [m for m, sev in env.notices if sev == "warning"]
            self.assertEqual(len(warnings), 1)
            self.assertIn("n002", warnings[0])

        self._drive(body, nodes=["n001"])

    def test_missing_binary_notifies_and_launches_nothing(self):
        def body(app, env):
            app._selection.marked.clear()
            app._selection.set_primary("n001")
            app._on_node_action_result("n001", "discuss")
            self.assertEqual(env.pushed, [])
            self.assertEqual(len(self._errors(env)), 1)
            self.assertIn("not found in PATH", self._errors(env)[0])
            env.resolve_dry_run_command.assert_not_called()
            env.spawn_in_terminal.assert_not_called()

        self._drive(body, nodes=["n001"], which=None)

    # ------------------------------------------------------------------ #
    # Finalized-command dispatch (t1225 regression)
    # ------------------------------------------------------------------ #
    def _open_and_edit(self, app, env):
        app._selection.marked.clear()
        app._selection.set_primary("n001")
        app._on_node_action_result("n001", "discuss")
        screen, callback = self._only_dialog(env)
        # What the agent/model picker + temporary profile + manual edit leave.
        screen.full_command = EDITED_CMD
        return screen, callback

    def _assert_edited_verbatim(self, argv):
        self.assertEqual(argv, ["sh", "-c", EDITED_CMD])
        self.assertNotIn("default-model", " ".join(argv))
        self.assertNotIn(WRAPPER, argv)

    def test_run_in_terminal_dispatches_finalized_command(self):
        def body(app, env):
            _screen, callback = self._open_and_edit(app, env)
            callback("run")
            env.spawn_in_terminal.assert_called_once()
            terminal, argv = env.spawn_in_terminal.call_args.args
            self.assertEqual(terminal, "xterm")
            self._assert_edited_verbatim(argv)
            env.launch_in_tmux.assert_not_called()

        self._drive(body, nodes=["n001"])

    def test_run_without_terminal_suspends_with_finalized_command(self):
        def body(app, env):
            _screen, callback = self._open_and_edit(app, env)
            callback("run")
            env.spawn_in_terminal.assert_not_called()
            env.call.assert_called_once()
            self._assert_edited_verbatim(env.call.call_args.args[0])

        self._drive(body, nodes=["n001"], terminal=None)

    def test_tmux_new_window_dispatches_finalized_command(self):
        def body(app, env):
            _screen, callback = self._open_and_edit(app, env)
            cfg = TmuxLaunchConfig(
                session="s", window="agent-discuss-99002",
                new_session=False, new_window=True,
            )
            callback(cfg)
            env.launch_in_tmux.assert_called_once_with(EDITED_CMD, cfg)
            env.maybe_spawn_minimonitor.assert_called_once_with(
                "s", "agent-discuss-99002")
            env.spawn_in_terminal.assert_not_called()

        self._drive(body, nodes=["n001"])

    def test_tmux_error_notifies_without_minimonitor(self):
        def body(app, env):
            _screen, callback = self._open_and_edit(app, env)
            env.launch_in_tmux.return_value = (None, "tmux exploded")
            callback(TmuxLaunchConfig(
                session="s", window="w", new_session=False, new_window=True))
            self.assertEqual(self._errors(env), ["tmux exploded"])
            env.maybe_spawn_minimonitor.assert_not_called()

        self._drive(body, nodes=["n001"])

    def test_cancel_launches_nothing(self):
        def body(app, env):
            _screen, callback = self._open_and_edit(app, env)
            callback(None)
            env.launch_in_tmux.assert_not_called()
            env.spawn_in_terminal.assert_not_called()
            env.call.assert_not_called()

        self._drive(body, nodes=["n001"])

    # ------------------------------------------------------------------ #
    # Default reconstruction — only without a dialog
    # ------------------------------------------------------------------ #
    def test_default_argv_only_when_dry_run_unavailable(self):
        def body(app, env):
            app._selection.marked.clear()
            app._selection.set_primary("n001")
            app._on_node_action_result("n001", "discuss")
            self.assertEqual(env.pushed, [])
            env.spawn_in_terminal.assert_called_once()
            _terminal, argv = env.spawn_in_terminal.call_args.args
            self.assertEqual(argv, [WRAPPER, "invoke", "discuss", self.TASK_NUM, "n001"])

        self._drive(body, nodes=["n001"], dry_run=None)


if __name__ == "__main__":
    unittest.main()
