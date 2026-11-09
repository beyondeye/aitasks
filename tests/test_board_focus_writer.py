"""The `ait board` focus mailbox, tmux side (t2211_3): `agent_launch_utils`.

`launch_or_focus_board` is the board twin of `launch_or_focus_trails` (whose own
pins live in `test_trails_focus_writer.py`): ONE live receiver -- the first in
window/pane order; dead-pid and non-pid stamps skipped -- gets a fresh request
in `@aitask_board_focus` and is selected. With no receiver, an existing `board`
window (an older board, or one outside a gateway pane) is selected with a
warning, so a second board is never started beside it; with no board at all, a
`board` window runs `./ait board --focus <id>` in argv form. Asserted on the
argv a stubbed gateway receives -- nothing reaches a real tmux server.

Run: ~/.aitask/venv/bin/python -m pytest tests/test_board_focus_writer.py -q
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_launch_utils as alu  # noqa: E402

REQ = "0123456789abcdef0123456789abcdef"


class _Gateway:
    """A stubbed `_TMUX.run`: records argv, answers from a per-verb table."""

    def __init__(self, testcase):
        self.calls: list[list[str]] = []
        self.answers: dict[str, tuple[int, str]] = {}
        p = patch.object(alu._TMUX, "run", self.run)
        p.start()
        testcase.addCleanup(p.stop)

    def run(self, args, timeout=5.0):
        self.calls.append(list(args))
        return self.answers.get(args[0], (0, ""))

    def verbs(self):
        return [c[0] for c in self.calls]


class ParseTests(unittest.TestCase):
    def test_parse(self):
        self.assertIsNone(alu.parse_board_focus_request(""))
        self.assertIsNone(alu.parse_board_focus_request(None))
        self.assertEqual(alu.parse_board_focus_request(f"{REQ} 12"), (REQ, "12"))
        self.assertEqual(alu.parse_board_focus_request(f"{REQ} 12_3"), (REQ, "12_3"))
        for bad in ("t12", "12_", "12_3_4", "12 13", "x", "", "-1", "12;rm"):
            with self.subTest(bad=bad):
                self.assertEqual(alu.parse_board_focus_request(f"{REQ} {bad}"),
                                 (REQ, None))
        self.assertEqual(alu.parse_board_focus_request("short 12"), ("short", None),
                         "a malformed id is still recorded, never retried")

    def test_read_and_stamp_use_the_board_options(self):
        gw = _Gateway(self)
        gw.answers["display-message"] = (0, f"%4\t{REQ} 7\n")
        self.assertEqual(alu.read_board_focus_request("%4"), f"{REQ} 7")
        self.assertEqual(gw.calls[0], ["display-message", "-p", "-t", "%4",
                                       "#{pane_id}\t#{@aitask_board_focus}"])
        gw.calls.clear()
        self.assertTrue(alu.mark_board_receiver("%4"))
        self.assertTrue(alu.unmark_board_receiver("%4"))
        self.assertEqual(gw.calls, [
            ["set-option", "-p", "-t", "%4", "@aitask_board_app", str(os.getpid())],
            ["set-option", "-p", "-u", "-t", "%4", "@aitask_board_app"]])

    def test_the_trails_mailbox_keeps_its_own_options(self):
        gw = _Gateway(self)
        gw.answers["display-message"] = (0, "%4\t\n")
        alu.read_trails_focus_request("%4")
        alu.mark_trails_receiver("%4")
        joined = " ".join(" ".join(c) for c in gw.calls)
        self.assertIn("@aitask_trails_focus", joined)
        self.assertIn("@aitask_trails_app", joined)
        self.assertNotIn("@aitask_board", joined)


class LaunchOrFocusBoardTests(unittest.TestCase):

    LIVE = str(os.getpid())

    def setUp(self):
        self.gw = _Gateway(self)
        self.root = Path("/srv/projB")
        dead = patch.object(alu, "_process_exists", lambda pid: pid != 999_999)
        dead.start()
        self.addCleanup(dead.stop)

    def _panes(self, *rows):
        self.gw.answers["list-panes"] = (0, "".join(f"{r}\n" for r in rows))

    def _windows(self, *rows):
        self.gw.answers["list-windows"] = (0, "".join(f"{r}\n" for r in rows))

    def _request_value(self):
        sets = [c for c in self.gw.calls if c[0] == "set-option"]
        self.assertEqual(len(sets), 1, self.gw.calls)
        self.assertEqual(sets[0][:5], ["set-option", "-p", "-t", sets[0][3],
                                       "@aitask_board_focus"])
        return sets[0][3], sets[0][5]

    def test_one_receiver_gets_the_request_and_is_selected(self):
        self._panes("%1 @1 ", f"%2 @2 {self.LIVE}")
        self.assertEqual(alu.launch_or_focus_board("projB", self.root, "12_3"),
                         (True, None))
        self.assertEqual(self.gw.calls[0], [
            "list-panes", "-s", "-t", "=projB:",
            "-F", "#{pane_id} #{window_id} #{@aitask_board_app}"])
        pane, value = self._request_value()
        self.assertEqual(pane, "%2")
        request_id, _, task_id = value.partition(" ")
        self.assertRegex(request_id, r"^[0-9a-f]{32}$")
        self.assertEqual(task_id, "12_3")
        self.assertEqual(alu.parse_board_focus_request(value), (request_id, "12_3"))
        self.assertEqual(self.gw.calls[-2:], [["select-window", "-t", "@2"],
                                              ["select-pane", "-t", "%2"]])
        for verb in ("new-window", "list-windows", "switch-client"):
            self.assertNotIn(verb, self.gw.verbs())

    def test_two_receivers_target_only_the_first(self):
        self._panes(f"%5 @3 {self.LIVE}", f"%6 @4 {self.LIVE}")
        alu.launch_or_focus_board("projB", self.root, "12")
        pane, _value = self._request_value()
        self.assertEqual(pane, "%5")
        self.assertNotIn("%6", [a for c in self.gw.calls for a in c])

    def test_each_request_carries_a_fresh_id(self):
        self._panes(f"%5 @3 {self.LIVE}")
        alu.launch_or_focus_board("projB", self.root, "12")
        _p, first = self._request_value()
        self.gw.calls.clear()
        alu.launch_or_focus_board("projB", self.root, "12")
        _p, second = self._request_value()
        self.assertNotEqual(first.split()[0], second.split()[0])

    def test_dead_and_unparseable_stamps_are_not_receivers(self):
        self._panes("%1 @1 999999", "%2 @1 garbage", f"%4 @2 {self.LIVE}")
        alu.launch_or_focus_board("projB", self.root, "12")
        pane, _value = self._request_value()
        self.assertEqual(pane, "%4")

    def test_a_trails_receiver_is_not_a_board_receiver(self):
        # The board lookup reads ITS stamp column only.
        self._panes("%1 @1 ")
        self._windows("@1 trails")
        alu.launch_or_focus_board("projB", self.root, "12")
        self.assertEqual(self.gw.calls[0][-1],
                         "#{pane_id} #{window_id} #{@aitask_board_app}")
        self.assertEqual(self.gw.verbs()[-1], "new-window")

    def test_a_board_window_without_a_receiver_is_selected_with_a_warning(self):
        self._panes("%1 @1 ")
        self._windows("@1 agent-pick-4", "@7 board", "@8 board-2")
        ok, warning = alu.launch_or_focus_board("projB", self.root, "12")
        self.assertTrue(ok)
        self.assertIn("cannot take focus requests", warning)
        self.assertEqual(self.gw.calls[1], ["list-windows", "-t", "=projB",
                                            "-F", "#{window_id} #{window_name}"])
        self.assertEqual(self.gw.calls[-1], ["select-window", "-t", "@7"])
        self.assertNotIn("new-window", self.gw.verbs(), "never a second board")
        self.assertNotIn("set-option", self.gw.verbs())

    def test_no_board_opens_one_in_argv_form(self):
        self._panes("%1 @1 ", "%2 @2 999999")
        self._windows("@1 monitor", "@2 boardroom")
        self.assertEqual(alu.launch_or_focus_board("projB", self.root, "12"),
                         (True, None))
        self.assertEqual(self.gw.calls[-1], [
            "new-window", "-t", "=projB:", "-c", "/srv/projB", "-n", "board",
            "./ait", "board", "--focus", "12"])

    def test_a_malformed_id_is_refused_before_tmux(self):
        for bad in ("", "t12", "12_", "12 13", "12;id", "-1", None):
            with self.subTest(bad=bad):
                ok, err = alu.launch_or_focus_board("projB", self.root, bad)
                self.assertFalse(ok)
                self.assertIn("invalid task id", err)
        self.assertEqual(self.gw.calls, [])

    def test_tmux_failures_are_reported(self):
        cases = [("list-panes", "tmux list-panes failed"),
                 ("set-option", "tmux set-option failed"),
                 ("select-window", "tmux select-window failed"),
                 ("select-pane", "tmux select-pane failed")]
        for verb, message in cases:
            with self.subTest(verb=verb):
                self.gw.answers = {}
                self._panes(f"%5 @3 {self.LIVE}")
                self.gw.answers[verb] = (1, "")
                self.assertEqual(alu.launch_or_focus_board("projB", self.root, "12"),
                                 (False, message))
        self.gw.answers = {}
        self._panes()
        self.gw.answers["list-windows"] = (1, "")
        self.assertEqual(alu.launch_or_focus_board("projB", self.root, "12"),
                         (False, "tmux list-windows failed"))
        self.gw.answers = {}
        self._panes()
        self.gw.answers["new-window"] = (1, "")
        self.assertEqual(alu.launch_or_focus_board("projB", self.root, "12"),
                         (False, "tmux new-window failed"))


if __name__ == "__main__":
    unittest.main()
