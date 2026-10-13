"""The `ait trails` focus mailbox, tmux side (t1957_2): `agent_launch_utils`.

* **Server identity** — `pane_on_gateway_server(pane, tmux_env)` trusts a pane
  id only when the gateway server answering for it is the server `tmux_env`
  names (`#{socket_path}` vs the `$TMUX` socket, through symlinks): pane ids are
  per-server, so `%0` from the user's personal tmux names an unrelated pane on
  the ait server. Same rule as `current_tmux_session`, which now shares it.
* **Reads** — `read_trails_focus_request` tells "no request" (`""`) from "the
  read failed" (None) by the pane id the answer echoes; a missing pane is
  answered with rc 0 and nothing, so the rc alone cannot.
* **Parsing** — untrusted values: a malformed request still yields its id (so it
  is recorded and never retried) but no handle.
* **Writer** — `launch_or_focus_trails` targets ONE live receiver (first in
  window/pane order; dead-pid and non-pid stamps skipped), overwrites its
  request option and selects it; with none, a `trails` window running
  `./ait trails --trail <handle>` in argv form. Asserted on the argv the stubbed
  gateway receives — nothing reaches a real tmux server.

Run: bash tests/run_all_python_tests.sh
  or: ~/.aitask/venv/bin/python -m pytest tests/test_trails_focus_writer.py -q
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_launch_utils as alu  # noqa: E402

HANDLE = "art:trail-alpha"
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


class ServerIdentityTests(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ait_t1957_2_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.sock = self.tmp / "ait"
        self.sock.write_text("")
        self.gw = _Gateway(self)
        self.gw.answers["display-message"] = (0, f"{self.sock}\tprojA\n")

    def test_the_gateway_server_is_accepted(self):
        self.assertTrue(alu.pane_on_gateway_server("%3", f"{self.sock},1,0"))
        self.assertEqual(self.gw.calls, [[
            "display-message", "-p", "-t", "%3",
            "#{socket_path}\t#{session_name}"]])

    def test_the_same_socket_through_a_symlink_is_accepted(self):
        link = self.tmp / "link"
        link.symlink_to(self.tmp, target_is_directory=True)
        self.assertTrue(
            alu.pane_on_gateway_server("%3", f"{link / 'ait'},1,0"))

    def test_the_same_pane_id_on_another_server_is_refused(self):
        # The gateway HAS a `%3`; this process's $TMUX names another server.
        self.assertFalse(alu.pane_on_gateway_server(
            "%3", f"{self.tmp / 'default'},1,0"))

    def test_no_tmux_env_or_pane_refuses_without_probing(self):
        self.assertFalse(alu.pane_on_gateway_server("%3", ""))
        self.assertFalse(alu.pane_on_gateway_server("", f"{self.sock},1,0"))
        self.assertEqual(self.gw.calls, [])

    def test_failed_or_empty_answers_are_refused(self):
        for answer in ((1, ""), (-1, ""), (0, ""), (0, f"{self.sock}\t\n")):
            with self.subTest(answer=answer):
                self.gw.answers["display-message"] = answer
                self.assertFalse(
                    alu.pane_on_gateway_server("%3", f"{self.sock},1,0"))

    def test_current_tmux_session_keeps_its_answer(self):
        with patch.dict(os.environ, {"TMUX": f"{self.sock},1,0",
                                     "TMUX_PANE": "%3"}):
            self.assertEqual(alu.current_tmux_session(), "projA")
        with patch.dict(os.environ, {"TMUX": f"{self.tmp / 'x'},1,0",
                                     "TMUX_PANE": "%3"}):
            self.assertIsNone(alu.current_tmux_session())


class ReadAndParseTests(unittest.TestCase):

    def setUp(self):
        self.gw = _Gateway(self)

    def test_a_request_is_read_from_the_named_pane(self):
        self.gw.answers["display-message"] = (0, f"%4\t{REQ} {HANDLE}\n")
        self.assertEqual(alu.read_trails_focus_request("%4"),
                         f"{REQ} {HANDLE}")
        self.assertEqual(self.gw.calls, [[
            "display-message", "-p", "-t", "%4",
            "#{pane_id}\t#{@aitask_trails_focus}"]])

    def test_no_request_is_empty_not_a_failure(self):
        self.gw.answers["display-message"] = (0, "%4\t\n")
        self.assertEqual(alu.read_trails_focus_request("%4"), "")

    def test_a_missing_pane_or_failed_read_is_none(self):
        # tmux answers a missing pane with rc 0 and an empty line.
        for answer in ((0, "\n"), (0, ""), (1, ""), (-1, ""),
                       (0, f"%5\t{REQ} {HANDLE}\n")):
            with self.subTest(answer=answer):
                self.gw.answers["display-message"] = answer
                self.assertIsNone(alu.read_trails_focus_request("%4"))

    def test_parse(self):
        cases = {
            "": None,
            "   ": None,
            None: None,
            f"{REQ} {HANDLE}": (REQ, HANDLE),
            f"{REQ}  {HANDLE} ": (REQ, HANDLE),
            f"{REQ}": (REQ, None),
            f"{REQ} not-a-handle": (REQ, None),
            f"{REQ} art:Bad": (REQ, None),
            f"{REQ} {HANDLE} extra": (REQ, None),
            f"XYZ {HANDLE}": ("XYZ", None),
            f"{REQ.upper()} {HANDLE}": (REQ.upper(), None),
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(alu.parse_trails_focus_request(value),
                                 expected)

    def test_stamp_and_unstamp_argv(self):
        self.assertTrue(alu.mark_trails_receiver("%4"))
        self.assertTrue(alu.unmark_trails_receiver("%4"))
        self.assertEqual(self.gw.calls, [
            ["set-option", "-p", "-t", "%4", "@aitask_trails_app",
             str(os.getpid())],
            ["set-option", "-p", "-u", "-t", "%4", "@aitask_trails_app"]])
        self.gw.answers["set-option"] = (1, "")
        self.assertFalse(alu.mark_trails_receiver("%4"))


class LaunchOrFocusTrailsTests(unittest.TestCase):

    LIVE = str(os.getpid())

    def setUp(self):
        self.gw = _Gateway(self)
        self.root = Path("/srv/projB")
        dead = patch.object(alu, "_process_exists",
                            lambda pid: pid != 999_999)
        dead.start()
        self.addCleanup(dead.stop)

    def _panes(self, *rows):
        self.gw.answers["list-panes"] = (0, "".join(f"{r}\n" for r in rows))

    def _request_value(self):
        sets = [c for c in self.gw.calls if c[0] == "set-option"]
        self.assertEqual(len(sets), 1, self.gw.calls)
        self.assertEqual(sets[0][:5],
                         ["set-option", "-p", "-t", sets[0][3],
                          "@aitask_trails_focus"])
        return sets[0][3], sets[0][5]

    def test_one_receiver_gets_the_request_and_is_selected(self):
        self._panes("%1 @1 ", f"%2 @2 {self.LIVE}")
        self.assertEqual(
            alu.launch_or_focus_trails("projB", self.root, HANDLE),
            (True, None))
        self.assertEqual(self.gw.calls[0], [
            "list-panes", "-s", "-t", "=projB:",
            "-F", "#{pane_id} #{window_id} #{@aitask_trails_app}"])
        pane, value = self._request_value()
        self.assertEqual(pane, "%2")
        request_id, _, handle = value.partition(" ")
        self.assertRegex(request_id, r"^[0-9a-f]{32}$")
        self.assertEqual(handle, HANDLE)
        self.assertEqual(alu.parse_trails_focus_request(value),
                         (request_id, HANDLE))
        self.assertEqual(self.gw.calls[-2:], [["select-window", "-t", "@2"],
                                              ["select-pane", "-t", "%2"]])
        self.assertNotIn("new-window", self.gw.verbs())
        self.assertNotIn("switch-client", self.gw.verbs())

    def test_two_receivers_target_only_the_first(self):
        self._panes(f"%5 @3 {self.LIVE}", f"%6 @4 {self.LIVE}")
        alu.launch_or_focus_trails("projB", self.root, HANDLE)
        pane, _value = self._request_value()
        self.assertEqual(pane, "%5")
        self.assertNotIn("%6", [a for c in self.gw.calls for a in c])

    def test_each_request_carries_a_fresh_id(self):
        self._panes(f"%5 @3 {self.LIVE}")
        alu.launch_or_focus_trails("projB", self.root, HANDLE)
        _p, first = self._request_value()
        self.gw.calls.clear()
        alu.launch_or_focus_trails("projB", self.root, HANDLE)
        _p, second = self._request_value()
        self.assertNotEqual(first.split()[0], second.split()[0])

    def test_dead_and_unparseable_stamps_are_not_receivers(self):
        self._panes("%1 @1 999999", "%2 @1 garbage", "%3 @2 12:34",
                    f"%4 @2 {self.LIVE}")
        alu.launch_or_focus_trails("projB", self.root, HANDLE)
        pane, _value = self._request_value()
        self.assertEqual(pane, "%4")

    def test_malformed_and_out_of_range_stamps_are_skipped_safely(self):
        # `²` passes str.isdigit() but not int(); the huge one overflows the
        # C int os.kill() takes. Neither may raise — the lookup continues.
        stamps = ["²", "٣", "99999999999999999999", str(2**31), "0", "-5",
                  "+12"]
        for stamp in stamps:
            with self.subTest(stamp=stamp, then="next receiver"):
                self.gw.calls.clear()
                self._panes(f"%1 @1 {stamp}", f"%2 @2 {self.LIVE}")
                self.assertEqual(
                    alu.launch_or_focus_trails("projB", self.root, HANDLE),
                    (True, None))
                pane, _value = self._request_value()
                self.assertEqual(pane, "%2")
            with self.subTest(stamp=stamp, then="cold launch"):
                self.gw.calls.clear()
                self._panes(f"%1 @1 {stamp}")
                self.assertEqual(
                    alu.launch_or_focus_trails("projB", self.root, HANDLE),
                    (True, None))
                self.assertEqual(self.gw.verbs()[-1], "new-window")
                self.assertNotIn("set-option", self.gw.verbs())

    def test_no_receiver_opens_a_trails_window_in_argv_form(self):
        self._panes("%1 @1 ", "%2 @2 999999")
        self.assertEqual(
            alu.launch_or_focus_trails("projB", self.root, HANDLE),
            (True, None))
        self.assertEqual(self.gw.calls[-1], [
            "new-window", "-t", "=projB:", "-c", "/srv/projB", "-n", "trails",
            "./ait", "trails", "--trail", HANDLE])
        self.assertNotIn("set-option", self.gw.verbs())

    def test_a_malformed_handle_is_refused_before_tmux(self):
        for bad in ("", "trail", "art:", "art:a b", "art:x; rm -rf ~"):
            with self.subTest(bad=bad):
                ok, err = alu.launch_or_focus_trails("projB", self.root, bad)
                self.assertFalse(ok)
                self.assertIn("invalid trail handle", err)
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
                self.assertEqual(
                    alu.launch_or_focus_trails("projB", self.root, HANDLE),
                    (False, message))
        self.gw.answers = {}
        self._panes()
        self.gw.answers["new-window"] = (1, "")
        self.assertEqual(
            alu.launch_or_focus_trails("projB", self.root, HANDLE),
            (False, "tmux new-window failed"))


if __name__ == "__main__":
    unittest.main()
