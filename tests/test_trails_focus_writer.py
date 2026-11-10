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


# --- The task-carrying request (t2211_10) --------------------------------------


class TrailsTargetParseTests(unittest.TestCase):
    """`parse_trails_focus_target`: the bare-handle form AND the task form;
    anything else is malformed whole (the value is untrusted)."""

    def test_parse(self):
        cases = {
            "": None,
            None: None,
            f"{REQ} {HANDLE}": (REQ, (HANDLE, None)),
            f"{REQ}  {HANDLE} ": (REQ, (HANDLE, None)),
            f"{REQ} {HANDLE} 12": (REQ, (HANDLE, "12")),
            f"{REQ} {HANDLE} 2211_10": (REQ, (HANDLE, "2211_10")),
            f"{REQ}": (REQ, None),
            f"{REQ} {HANDLE} t12": (REQ, None),
            f"{REQ} {HANDLE} 12 extra": (REQ, None),
            f"{REQ} {HANDLE} 12_": (REQ, None),
            f"{REQ} {HANDLE} 12;rm": (REQ, None),
            f"{REQ} {HANDLE}  12": (REQ, None),
            f"{REQ} art:Bad 12": (REQ, None),
            f"{REQ} 12": (REQ, None),
            f"XYZ {HANDLE} 12": ("XYZ", None),
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(alu.parse_trails_focus_target(value), expected)

    def test_the_old_parser_still_refuses_the_task_form(self):
        # What an OLDER TrailsApp runs: why the task form is sent only to a
        # receiver that advertises it.
        self.assertEqual(alu.parse_trails_focus_request(f"{REQ} {HANDLE} 12"),
                         (REQ, None))

    def test_the_target_grammar_is_the_handle_and_task_id_grammars(self):
        from artifact_manifest import HANDLE_RE
        handles = ["art:a", "art:trail-x.y_z", "art:" + "a" * 128, "art:" + "a" * 129,
                   "art:", "art:A", "art:-a", "art:a b", "trail"]
        tasks = ["1", "12", "12_3", "0", "t12", "12_", "_3", "12_3_4", "", "1\n", "١٢"]
        # The one deliberate difference: HANDLE_RE's `$` also matches before a
        # trailing newline; the request grammar ends in `\Z` and refuses it.
        self.assertTrue(HANDLE_RE.match("art:a\n"))
        self.assertIsNone(alu._TRAILS_TARGET_RE.match("art:a\n"))
        for h in handles:
            with self.subTest(handle=h):
                self.assertEqual(bool(alu._TRAILS_TARGET_RE.match(h)),
                                 bool(HANDLE_RE.match(h)))
            for t in tasks:
                if not HANDLE_RE.match(h) or not t:
                    continue
                with self.subTest(handle=h, task=t):
                    self.assertEqual(bool(alu._TRAILS_TARGET_RE.match(f"{h} {t}")),
                                     bool(alu.BOARD_TASK_ID_RE.match(t)))


class ReceiverCapabilityTests(unittest.TestCase):
    LIVE = str(os.getpid())

    def setUp(self):
        self.gw = _Gateway(self)

    def test_the_read_argv(self):
        self.gw.answers["display-message"] = (0, f"%4\t{self.LIVE}\t{self.LIVE}\n")
        self.assertTrue(alu._trails_receiver_takes_task("%4"))
        self.assertEqual(self.gw.calls, [[
            "display-message", "-p", "-t", "%4",
            "#{pane_id}\t#{@aitask_trails_app}\t#{@aitask_trails_card_focus}"]])

    def test_only_a_capability_naming_the_receivers_pid_counts(self):
        cases = {
            (0, "%4\t123\t123\n"): True,
            (0, "%4\t123\t124\n"): False,       # stale: another process's
            (0, "%4\t123\t\n"): False,          # an older app: no capability
            (0, "%4\t\t123\n"): False,          # no receiver stamp
            (0, "%4\tx\tx\n"): False,
            (0, "%5\t123\t123\n"): False,       # another pane answered
            (0, "\n"): False,                   # missing pane
            (0, "%4\t123\n"): False,
            (1, "%4\t123\t123\n"): False,
        }
        for answer, expected in cases.items():
            with self.subTest(answer=answer):
                self.gw.answers["display-message"] = answer
                self.assertIs(alu._trails_receiver_takes_task("%4"), expected)

    def test_stamp_argv(self):
        self.assertTrue(alu.mark_trails_card_focus("%4"))
        self.assertTrue(alu.unmark_trails_card_focus("%4"))
        self.assertEqual(self.gw.calls, [
            ["set-option", "-p", "-t", "%4", "@aitask_trails_card_focus",
             str(os.getpid())],
            ["set-option", "-p", "-u", "-t", "%4", "@aitask_trails_card_focus"]])


class LaunchWithTaskTests(unittest.TestCase):
    LIVE = str(os.getpid())

    def setUp(self):
        self.gw = _Gateway(self)
        self.root = Path("/srv/projB")
        self.gw.answers["list-panes"] = (0, f"%2 @2 {self.LIVE}\n")

    def _request(self):
        sets = [c for c in self.gw.calls
                if c[0] == "set-option" and c[4] == "@aitask_trails_focus"]
        self.assertEqual(len(sets), 1, self.gw.calls)
        self.assertEqual(sets[0][3], "%2")
        return sets[0][5].split(" ", 1)[1]

    def test_a_capable_receiver_gets_the_task_form(self):
        self.gw.answers["display-message"] = (0, f"%2\t{self.LIVE}\t{self.LIVE}\n")
        self.assertEqual(
            alu.launch_or_focus_trails("projB", self.root, HANDLE, "2211_10"),
            (True, None))
        self.assertEqual(self._request(), f"{HANDLE} 2211_10")
        self.assertEqual(self.gw.calls[-2:], [["select-window", "-t", "@2"],
                                              ["select-pane", "-t", "%2"]])

    def test_an_older_receiver_gets_the_bare_handle_and_a_warning(self):
        for answer in ((0, f"%2\t{self.LIVE}\t\n"), (0, f"%2\t{self.LIVE}\t1\n"),
                       (1, "")):
            with self.subTest(answer=answer):
                self.gw.calls.clear()
                self.gw.answers["display-message"] = answer
                ok, msg = alu.launch_or_focus_trails("projB", self.root, HANDLE, "12")
                self.assertTrue(ok)
                self.assertIn("cannot focus a card", msg)
                self.assertIn("t12", msg)
                self.assertEqual(self._request(), HANDLE)
                # What the older app runs: it accepts this request.
                self.assertEqual(alu.parse_trails_focus_request(f"{REQ} {HANDLE}"),
                                 (REQ, HANDLE))

    def test_a_failed_delivery_to_an_older_receiver_is_an_error(self):
        self.gw.answers["set-option"] = (1, "")
        self.assertEqual(
            alu.launch_or_focus_trails("projB", self.root, HANDLE, "12"),
            (False, "tmux set-option failed"))

    def test_without_a_task_the_calls_are_unchanged(self):
        alu.launch_or_focus_trails("projB", self.root, HANDLE)
        self.assertEqual(self.gw.verbs(), ["list-panes", "set-option",
                                           "select-window", "select-pane"])
        self.assertEqual(self._request(), HANDLE)

    def test_the_cold_path_passes_task_when_supported(self):
        self.gw.answers["list-panes"] = (0, "")
        with patch.object(alu, "trails_supports_task_focus", return_value=True):
            self.assertEqual(
                alu.launch_or_focus_trails("projB", self.root, HANDLE, "12_3"),
                (True, None))
        self.assertEqual(self.gw.calls[-1], [
            "new-window", "-t", "=projB:", "-c", "/srv/projB", "-n", "trails",
            "./ait", "trails", "--trail", HANDLE, "--task", "12_3"])

    def test_the_cold_path_without_support_opens_the_trail_and_warns(self):
        self.gw.answers["list-panes"] = (0, "")
        with patch.object(alu, "trails_supports_task_focus", return_value=False):
            ok, msg = alu.launch_or_focus_trails("projB", self.root, HANDLE, "12")
        self.assertTrue(ok)
        self.assertIn("cannot focus a card", msg)
        self.assertEqual(self.gw.calls[-1], [
            "new-window", "-t", "=projB:", "-c", "/srv/projB", "-n", "trails",
            "./ait", "trails", "--trail", HANDLE])

    def test_a_malformed_task_id_is_refused_before_tmux(self):
        for bad in ("", "t12", "12_", "12 13", "12;rm -rf ~", "-1", "١٢"):
            with self.subTest(bad=bad):
                ok, err = alu.launch_or_focus_trails("projB", self.root, HANDLE, bad)
                self.assertFalse(ok)
                self.assertIn("invalid task id", err)
        self.assertEqual(self.gw.calls, [])


class TaskFocusProbeTests(unittest.TestCase):
    def test_the_probe_reads_the_projects_trails_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertFalse(alu.trails_supports_task_focus(root))   # missing
            app = root / ".aitask-scripts" / "board" / "trails_app.py"
            app.parent.mkdir(parents=True)
            app.write_text('parser.add_argument("--tasks-dir")\n'
                           'parser.add_argument("--trail")\n', encoding="utf-8")
            self.assertFalse(alu.trails_supports_task_focus(root),
                             "--tasks-dir must not read as --task")
            app.write_text('parser.add_argument("--task", metavar="ID")\n',
                           encoding="utf-8")
            self.assertTrue(alu.trails_supports_task_focus(root))

    def test_this_checkout_supports_it(self):
        self.assertTrue(alu.trails_supports_task_focus(REPO_ROOT))


if __name__ == "__main__":
    unittest.main()
