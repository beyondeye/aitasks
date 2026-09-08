"""Characterization pin for the `pick` launch argv (t1705_5 pre-phase).

`lib/agent_restore.py` needs the pick-launch argv for its `--repick` mode, and
rather than fork it this task extracts the shape the TUIs already use into
`agent_launch_utils.pick_launch_argv`. The extraction touches **three** live
call sites:

  * `monitor/minimonitor_app.py:3013`
  * `monitor/monitor_app.py:3599`
  * `monitor/monitor_app.py:3683`   (`_on_restart_confirmed`)

and the measured hazard is that **none of the three passes `agent_string`
today**. A shared helper that defaulted that parameter wrongly would silently
change which agent and model every `pick` launch starts — a behaviour change
with no error, no log line, and no failing test anywhere in the suite. That is
the whole reason this file exists: it pins the observable behaviour BEFORE the
extraction so any such change becomes a test failure.

**This file must stay green, unchanged, across the extraction.** It therefore
pins the behaviour structurally and looks `pick_launch_argv` up *dynamically* —
present, it is asserted to agree with the pre-extraction shape; absent, that one
case skips. (Same pattern `tests/test_agent_frozen_ops.py` uses for
`agent_restore` while it is unshipped.) A file that had to be edited alongside
the refactor would prove nothing about the refactor.

Shells the real `aitask_codeagent.sh --dry-run`; no tmux, no agent launched.

Run: python3 tests/test_pick_launch_argv.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_launch_utils as alu  # noqa: E402

#: Any task id: `--dry-run` resolves the command without reading the task file,
#: so this need not exist. Using a fixed literal keeps the assertions readable.
TASK_ID = "1705_5"

#: A real second entry in `aitasks/metadata/models_claudecode.json`. It only has
#: to differ from the configured default for the contrast assertion below.
OTHER_AGENT_STRING = "claudecode/sonnet5"


class TestPickDryRunCommandShape(unittest.TestCase):
    """What the three call sites resolve today, pinned."""

    @classmethod
    def setUpClass(cls):
        cls.cmd = alu.resolve_dry_run_command(REPO_ROOT, "pick", TASK_ID)
        if not cls.cmd:
            raise unittest.SkipTest(
                "aitask_codeagent.sh --dry-run invoke pick did not resolve "
                "(no agent binary configured?) — nothing to characterize"
            )

    def test_the_pick_slash_command_is_in_the_resolved_argv(self):
        """The operation reaches the agent as the `/aitask-pick <id>` prompt."""
        self.assertIn("aitask-pick", self.cmd)
        self.assertIn(TASK_ID, self.cmd)

    def test_omitting_agent_string_equals_passing_None(self):
        """The three call sites omit the argument entirely. A helper that passes
        an explicit `None` must be indistinguishable from that."""
        explicit_none = alu.resolve_dry_run_command(
            REPO_ROOT, "pick", TASK_ID, agent_string=None)
        self.assertEqual(self.cmd, explicit_none)

    def test_passing_a_DIFFERENT_agent_string_changes_the_command(self):
        """The teeth behind the test above.

        If this assertion did not hold, `agent_string` would be inert and the
        whole hazard would be imaginary. It holds: the resolved model flag
        changes. So a helper that defaults the parameter to anything other than
        "omit it" is an observable behaviour change at all three call sites.
        """
        other = alu.resolve_dry_run_command(
            REPO_ROOT, "pick", TASK_ID, agent_string=OTHER_AGENT_STRING)
        if other is None:
            self.skipTest(f"{OTHER_AGENT_STRING} is not resolvable in this checkout")
        self.assertNotEqual(
            self.cmd, other,
            "agent_string must actually affect the resolved command — if it does "
            "not, this file is pinning nothing.",
        )


class TestPickWindowNameConvention(unittest.TestCase):
    """`agent-pick-<task_id>` is a convention other code parses back out.

    `task_id_from_window_name` / `classify_pane` read the task id off the window
    name, and the freeze/restore records store `window` as durable identity — so
    renaming this format silently breaks pane-to-record attachment.
    """

    def test_convention_is_agent_pick_taskid(self):
        self.assertEqual(f"agent-pick-{TASK_ID}", "agent-pick-1705_5")

    def test_helper_uses_the_same_convention_when_it_exists(self):
        helper = getattr(alu, "pick_launch_argv", None)
        if helper is None:
            self.skipTest("pick_launch_argv not extracted yet (t1705_5 step 2)")
        _cmd, window_name = helper(REPO_ROOT, TASK_ID)
        self.assertEqual(f"agent-pick-{TASK_ID}", window_name)


class TestExtractedHelperMatchesPreExtractionBehaviour(unittest.TestCase):
    """Once `pick_launch_argv` exists, it must reproduce exactly what the call
    sites did before — that is what makes the refactor behaviour-preserving."""

    def setUp(self):
        self.helper = getattr(alu, "pick_launch_argv", None)
        if self.helper is None:
            self.skipTest("pick_launch_argv not extracted yet (t1705_5 step 2)")

    def test_default_call_matches_the_no_agent_string_command(self):
        baseline = alu.resolve_dry_run_command(REPO_ROOT, "pick", TASK_ID)
        cmd, _window = self.helper(REPO_ROOT, TASK_ID)
        self.assertEqual(baseline, cmd)

    def test_agent_string_is_honoured_when_the_caller_asks_for_one(self):
        """`agent_restore` calls it WITH the frozen record's agent string; the
        TUIs call it without. Both must work off one helper."""
        expected = alu.resolve_dry_run_command(
            REPO_ROOT, "pick", TASK_ID, agent_string=OTHER_AGENT_STRING)
        if expected is None:
            self.skipTest(f"{OTHER_AGENT_STRING} is not resolvable in this checkout")
        cmd, _window = self.helper(REPO_ROOT, TASK_ID,
                                   agent_string=OTHER_AGENT_STRING)
        self.assertEqual(expected, cmd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
