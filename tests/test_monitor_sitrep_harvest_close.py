#!/usr/bin/env python3
"""Harvest-and-close (`h`) and the sitrep key (`S`) in the monitor TUIs (t2175_5).

The contract under test, in order:

* capture first, then confirm: a failed capture or harvest never offers a
  close (no affirmative button, and the confirm callback re-checks the report);
* live sitrep windows are never captured or harvested;
* only AGENT cards are acted on;
* what is closed is the agent RUN that was harvested: its identity is read
  before and after the harvest, a frozen record must still match at confirm
  time, and a live close is the guarded run kill (the real-server half of that
  is `tests/test_kill_agent_run_guarded.sh`; the whole live flow, real capture
  and real harvest included, is `tests/test_monitor_harvest_close_live.sh`);
* the harvest runs in its own process group, killed as a group on timeout AND
  on cancellation;
* the maintenance `harvest all` pass runs before the sitrep refresh.

No test lets a real Textual worker outlive its `run_test` block: the dispatch
seams are stubbed (`aidocs/framework/testing_conventions.md`).

Run: python3 tests/test_monitor_sitrep_harvest_close.py
"""

from __future__ import annotations

import asyncio
import inspect
import os
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from textual.app import App  # noqa: E402

import agent_marks  # noqa: E402
import sitrep_cli  # noqa: E402
from monitor import monitor_core as mc  # noqa: E402
from monitor import sitrep_close as sc  # noqa: E402
from monitor.minimonitor_app import MiniMonitorApp  # noqa: E402
from monitor.monitor_app import MonitorApp  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    PaneCategory, PaneSnapshot, RunIdentity, TmuxPaneInfo,
)
from monitor.monitor_shared import AgentMarksMixin  # noqa: E402

SESSION = "demo"


def snapshot(window="agent-pick-42", pane_id="%1", *, frozen=False,
             record="", category=PaneCategory.AGENT, window_index="1",
             is_idle=True) -> PaneSnapshot:
    snap = PaneSnapshot(
        pane=TmuxPaneInfo(
            window_index=window_index, window_name=window, pane_index="0",
            pane_id=pane_id, pane_pid=4242, current_command="node",
            width=80, height=24, category=category, session_name=SESSION,
            frozen_record=record if frozen else ""),
        content="x", timestamp=0.0, idle_seconds=1.0, is_idle=is_idle,
        frozen=frozen, frozen_record_id=record if frozen else "",
    )
    return snap


def ident_line(pane="%1", pid="4242", server="99", frozen="", tui=""):
    """One `RUN_IDENTITY_FORMAT` answer (5 fields since t2211_2's TUI stamp)."""
    return f"{pane}\t{pid}\t{server}\t{frozen}\t{tui}"


# -- the report parser --------------------------------------------------------

class ParseHarvestOutputTests(unittest.TestCase):
    def test_harvested_with_items_and_warnings(self):
        out = ("HARVEST_ITEM:abcd1234|c12|added|task|t42_1\n"
               "HARVEST_ITEM:abcd1234|c13|exists|watch|art:trail-x\n"
               "HARVEST_WARN:abcd1234|banner_incomplete:t42\n"
               "HARVESTED:abcd1234|added=1|existing=1\n")
        r = sc.parse_harvest_output(0, out)
        self.assertTrue(r.ok)
        self.assertEqual(r.final_kind, "HARVESTED")
        self.assertEqual((r.added, r.existing), (1, 1))
        self.assertEqual([i.cid for i in r.items], ["c12", "c13"])
        self.assertEqual(r.items[1].ref, "art:trail-x")
        self.assertEqual(r.warns, ("banner_incomplete:t42",))

    def test_none_is_ok_and_names_its_reason(self):
        r = sc.parse_harvest_output(0, "HARVEST_NONE:capture|nothing_found\n")
        self.assertTrue(r.ok)
        self.assertEqual(r.reason, "nothing_found")

    def test_failed_is_not_ok(self):
        r = sc.parse_harvest_output(1, "HARVEST_FAILED:capture|harvest_lock_busy\n")
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, "harvest_lock_busy")

    def test_the_last_final_line_wins(self):
        r = sc.parse_harvest_output(
            1, "HARVESTED:a|added=1|existing=0\nHARVEST_FAILED:b|writer:timeout\n")
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, "writer:timeout")

    def test_a_missing_final_line_is_not_ok(self):
        r = sc.parse_harvest_output(0, "HARVEST_ITEM:a|c1|added|task|t1\n")
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, "no_result")

    def test_a_success_line_under_a_nonzero_exit_is_not_ok(self):
        r = sc.parse_harvest_output(1, "HARVESTED:a|added=1|existing=0\n")
        self.assertFalse(r.ok)
        self.assertEqual(r.reason, "exit 1")

    def test_a_preserved_review_is_ok_and_named(self):
        # t2175_6: uncertain output kept verbatim with a review item IS a
        # successful harvest (the receipt was written after the case), and the
        # verdict must say so -- distinct from both a plain harvest and a
        # failure.
        out = ("HARVEST_ITEM:abcd1234|c3|added|question|-\n"
               "HARVEST_REVIEW:abcd1234|c3|added|case=0123456789abcdef|banner_unparsed\n"
               "HARVESTED:abcd1234|added=1|existing=0|review=c3\n")
        r = sc.parse_harvest_output(0, out)
        self.assertTrue(r.ok)
        self.assertEqual((r.added, r.existing), (1, 0))
        self.assertEqual(r.reviews, (sc.HarvestReview("c3", "added", "0123456789abcdef",
                                                      "banner_unparsed"),))
        self.assertIn("kept for sitrep review (c3)", r.verdict())
        plain = sc.parse_harvest_output(0, "HARVESTED:a|added=1|existing=0\n")
        self.assertNotIn("review", plain.verdict())

    def test_a_cached_result_still_names_its_review(self):
        # An earlier automatic harvest already certified the capture: the
        # cached result must still say the output is kept for review.
        out = ("HARVEST_REVIEW:abcd1234|c3|exists|case=0123456789abcdef|banner_incomplete\n"
               "HARVEST_NONE:abcd1234|already_harvested\n")
        r = sc.parse_harvest_output(0, out)
        self.assertTrue(r.ok)
        self.assertEqual(r.verdict(), "Nothing new to harvest (already_harvested) — "
                                      "output kept for sitrep review (c3)")
        plain = sc.parse_harvest_output(0, "HARVEST_NONE:a|already_harvested\n")
        self.assertEqual(plain.verdict(), "Nothing to harvest (already_harvested)")

    def test_a_review_line_under_a_failure_is_still_a_failure(self):
        out = ("HARVEST_REVIEW:a|c3|added|case=0123456789abcdef|x\n"
               "HARVEST_FAILED:a|fault:receipt\n")
        r = sc.parse_harvest_output(1, out)
        self.assertFalse(r.ok)
        self.assertTrue(r.verdict().startswith("HARVEST FAILED"))

    def test_a_runner_error_is_not_ok(self):
        r = sc.parse_harvest_output(
            1, "ERROR:aitask_sitrep_harvest.sh timed out after 150s")
        self.assertFalse(r.ok)
        self.assertIn("timed out", r.reason)

    def test_skipped_is_ok_and_failed_is_not(self):
        self.assertTrue(sc.HarvestReport.skipped("sitrep_agent").ok)
        self.assertFalse(sc.HarvestReport.failed("capture_failed").ok)
        self.assertIn("HARVEST FAILED", sc.HarvestReport.failed("x").verdict())


# -- the owned-group runner ---------------------------------------------------

def _gone(pid: int) -> bool:
    """Exited, or a zombie awaiting its reaper. Alive when state is unknown.

    The zombie check reads `/proc` where it exists and asks `ps` otherwise
    (macOS has no `/proc`); a failure of both leaves the process ALIVE — an
    unreadable state must never pass a "the group was killed" assertion.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    try:
        with open(f"/proc/{pid}/stat") as fh:
            return fh.read().split(")")[-1].split()[0] == "Z"
    except OSError:
        pass
    try:
        import subprocess
        r = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    if r.returncode != 0:
        return False          # the process exists (kill -0 said so); unknown state
    return r.stdout.strip().startswith("Z")


def _wait_gone(pid: int, budget: float = 5.0) -> bool:
    end = time.monotonic() + budget
    while time.monotonic() < end:
        if _gone(pid):
            return True
        time.sleep(0.05)
    return _gone(pid)


class GoneProbeTests(unittest.TestCase):
    """The cleanup assertions' own probe must not read "unknown" as "gone"."""

    def test_a_live_process_is_alive_without_proc(self):
        from unittest import mock
        real_open = open

        def no_proc(path, *a, **k):
            if str(path).startswith("/proc/"):
                raise FileNotFoundError(path)
            return real_open(path, *a, **k)

        with mock.patch("builtins.open", no_proc):
            self.assertFalse(_gone(os.getpid()))

    def test_without_proc_or_ps_a_live_process_is_alive(self):
        from unittest import mock
        real_open = open

        def no_proc(path, *a, **k):
            if str(path).startswith("/proc/"):
                raise FileNotFoundError(path)
            return real_open(path, *a, **k)

        with mock.patch("builtins.open", no_proc), \
                mock.patch("subprocess.run", side_effect=OSError("no ps")):
            self.assertFalse(_gone(os.getpid()))

    def test_an_exited_process_is_gone(self):
        import subprocess
        p = subprocess.Popen(["true"])
        p.wait()
        self.assertTrue(_gone(p.pid))


class RunOwnedGroupTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.script = self.dir / "fake.sh"
        # The child records its pid, starts a grandchild that records ITS pid
        # and sleeps, copies stdin, then waits — like the harvest wrapper, whose
        # Python children hold the store mutex.
        self.script.write_text(
            "#!/bin/sh\n"
            'D="$1"\n'
            "echo $$ > \"$D/child\"\n"
            "sh -c 'echo $$ > \"$1/grand\"; exec sleep 60' _ \"$D\" "
            ">/dev/null 2>&1 &\n"
            'cat > "$D/stdin"\n'
            'if [ "$2" = "fast" ]; then echo DONE; exit 0; fi\n'
            "wait\n")
        self.script.chmod(self.script.stat().st_mode | stat.S_IXUSR)

    def _pids(self):
        return (int((self.dir / "child").read_text()),
                int((self.dir / "grand").read_text()))

    def test_stdin_is_delivered_and_output_returned(self):
        async def go():
            return await sc.run_owned_group(
                [str(self.script), str(self.dir), "fast"],
                stdin=b"captured text\n", timeout=10)
        rc, out = asyncio.run(go())
        self.assertEqual((rc, out), (0, "DONE"))
        self.assertEqual((self.dir / "stdin").read_text(), "captured text\n")
        # The fast path exits without waiting for its background grandchild;
        # reap the fixture's sleeper once it has recorded itself.
        end = time.monotonic() + 5
        while not (self.dir / "grand").exists() and time.monotonic() < end:
            time.sleep(0.05)
        _child, grand = self._pids()
        os.kill(grand, 9)

    def test_a_timeout_kills_the_whole_group(self):
        async def go():
            return await sc.run_owned_group(
                [str(self.script), str(self.dir)], stdin=b"", timeout=1.0)
        rc, out = asyncio.run(go())
        self.assertEqual(rc, 1)
        self.assertIn("timed out", out)
        child, grand = self._pids()
        self.assertTrue(_wait_gone(child), "the child survived the timeout")
        self.assertTrue(_wait_gone(grand), "the grandchild survived the timeout")

    def test_cancellation_kills_the_whole_group_and_propagates(self):
        async def go():
            task = asyncio.ensure_future(sc.run_owned_group(
                [str(self.script), str(self.dir)], stdin=b"", timeout=60))
            end = time.monotonic() + 10
            while not ((self.dir / "child").exists()
                       and (self.dir / "grand").exists()):
                if time.monotonic() > end:
                    self.fail("the fixture never started")
                await asyncio.sleep(0.05)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        asyncio.run(go())
        child, grand = self._pids()
        self.assertTrue(_wait_gone(child), "the child outlived the cancel")
        self.assertTrue(_wait_gone(grand), "the grandchild outlived the cancel")

    def test_a_missing_script_is_an_error_result(self):
        rc, out = asyncio.run(sc.run_owned_group(
            [str(self.dir / "nope.sh")], timeout=5))
        self.assertEqual(rc, 1)
        self.assertTrue(out.startswith("ERROR:cannot run"))


# -- the flow, through a recording host ---------------------------------------

class _Mon:
    def __init__(self, identities, capture=(0, "Task Complete\n")):
        self.identities = list(identities)
        self.capture = capture
        self.calls = []
        self.guarded = []
        self.smart = []
        self.kill_result = ("killed", False)
        self.option = (True, "")
        self.session = SESSION

    async def _tmux_async(self, args, timeout=5.0):
        self.calls.append(list(args))
        if args[0] == "display-message":
            line = (self.identities.pop(0) if len(self.identities) > 1
                    else self.identities[0])
            return (0, line) if line is not None else (1, "")
        if args[0] == "capture-pane":
            return self.capture
        return 1, ""

    def kill_agent_run_guarded(self, identity):
        self.guarded.append(identity)
        return self.kill_result

    def kill_agent_pane_smart(self, pane_id, **kw):
        self.smart.append(pane_id)
        return True, False

    def get_pane_option_sync(self, pane_id, option, timeout=2.0):
        return self.option


class _Host(sc.SitrepCloseMixin):
    def __init__(self, snap, *, state="live", root="/repo", identities=None,
                 harvest=(0, "HARVESTED:capture|added=1|existing=0\n"),
                 capture=(0, "Task Complete\n")):
        self.snap = snap
        self.state = state
        self.root = root
        self._monitor = _Mon(identities or [ident_line()], capture)
        self._snapshots = {snap.pane.pane_id: snap} if snap else {}
        self.harvest_result = harvest
        self.notes, self.pushed, self.harvests = [], [], []
        self.dispatched, self.dropped, self.closed, self.opened = [], [], [], []
        self._task_cache = None

    # host surface
    def _current_agent_snapshot(self):
        return self.snap

    def _kill_target_state(self, pane_id):
        return self.state

    def _strict_root_for_snap(self, snap):
        return self.root

    def notify(self, msg, **kw):
        self.notes.append((msg, kw.get("severity")))

    def push_screen(self, screen, callback=None):
        self.pushed.append((screen, callback))

    def run_worker(self, coro, **kw):
        coro.close()
        raise AssertionError("tests must stub the dispatch seam")

    async def _run_sitrep_harvest(self, args, *, stdin=None, timeout):
        self.harvests.append((list(args), stdin))
        return self.harvest_result

    def _drop_frozen(self, snap):
        self.dropped.append(snap)

    def _close_live_after_harvest(self, identity):
        self.closed.append(identity)


class _DispatchHost(_Host):
    def _dispatch_harvest_close(self, snap, state, root):
        self.dispatched.append((snap.pane.pane_id, state, root))

    def _dispatch_sitrep_open(self, root, session):
        self.opened.append((root, session))


class ActionGuardTests(unittest.TestCase):
    def test_a_live_agent_card_is_dispatched(self):
        h = _DispatchHost(snapshot())
        h.action_harvest_close()
        self.assertEqual(h.dispatched, [("%1", "live", "/repo")])

    def test_other_and_tui_cards_are_never_harvested(self):
        for cat in (PaneCategory.OTHER, PaneCategory.TUI):
            with self.subTest(category=cat):
                h = _DispatchHost(snapshot(window="zsh", category=cat))
                h.action_harvest_close()
                self.assertEqual(h.dispatched, [])
                self.assertEqual(h.harvests, [])
                self.assertEqual(h._monitor.calls, [])
                self.assertIn("agent cards only", h.notes[-1][0])

    def test_an_unverified_state_or_unknown_root_runs_nothing(self):
        h = _DispatchHost(snapshot(), state="unverified")
        h.action_harvest_close()
        h2 = _DispatchHost(snapshot(), root=None)
        h2.action_harvest_close()
        self.assertEqual(h.dispatched + h2.dispatched, [])

    def test_no_selection_and_inflight_are_refused(self):
        h = _DispatchHost(None)
        h.action_harvest_close()
        self.assertEqual(h.dispatched, [])
        h2 = _DispatchHost(snapshot())
        h2._harvest_close_inflight = True
        h2.action_harvest_close()
        self.assertEqual(h2.dispatched, [])


class HarvestFlowTests(unittest.TestCase):
    def run_flow(self, host, state="live"):
        asyncio.run(host._harvest_close(host.snap, state, host.root))
        self.assertFalse(host._harvest_close_inflight)
        self.assertEqual(len(host.pushed), 1)
        return host.pushed[0]

    def test_frozen_runs_record_force_on_the_bound_record(self):
        snap = snapshot(frozen=True, record="abcd1234")
        h = _Host(snap, state="frozen",
                  identities=[ident_line(frozen="abcd1234")],
                  harvest=(0, "HARVEST_NONE:abcd1234|nothing_found\n"))
        dialog, _cb = self.run_flow(h, "frozen")
        self.assertEqual(h.harvests, [(["record", "abcd1234", "--force"], None)])
        self.assertTrue(dialog._report.ok)

    def test_live_captures_then_feeds_capture_with_the_text(self):
        h = _Host(snapshot(window="agent-pick-42"),
                  capture=(0, "the wrap-up\n"))
        self.run_flow(h)
        self.assertIn(["capture-pane", "-p", "-J", "-t", "%1",
                       "-S", f"-{sc.HARVEST_CAPTURE_LINES}"], h._monitor.calls)
        args, stdin = h.harvests[0]
        self.assertEqual(args, ["capture", "--root", "/repo",
                                "--agent", "agent-pick-42",
                                "--task", "42", "--operation", "pick"])
        self.assertEqual(stdin, b"the wrap-up\n")

    def test_live_sitrep_windows_are_never_captured_or_harvested(self):
        for window in ("agent-sitrep", "agent-sitrep-2"):
            with self.subTest(window=window):
                h = _Host(snapshot(window=window))
                dialog, _ = self.run_flow(h)
                self.assertEqual(h.harvests, [])
                self.assertFalse(any(c[0] == "capture-pane"
                                     for c in h._monitor.calls))
                self.assertEqual(dialog._report.final_kind, "skipped")

    def test_a_near_miss_sitrep_name_is_harvested(self):
        h = _Host(snapshot(window="agent-sitrepx"))
        self.run_flow(h)
        self.assertEqual(len(h.harvests), 1)

    def test_a_failed_capture_never_harvests_and_is_not_ok(self):
        for capture in ((1, ""), (0, "   \n")):
            with self.subTest(capture=capture):
                h = _Host(snapshot(), capture=capture)
                dialog, _ = self.run_flow(h)
                self.assertEqual(h.harvests, [])
                self.assertFalse(dialog._report.ok)
                self.assertEqual(dialog._report.reason, "capture_failed")

    def test_a_process_change_during_the_harvest_fails_it(self):
        h = _Host(snapshot(), identities=[ident_line(pid="4242"),
                                          ident_line(pid="5555")])
        dialog, _ = self.run_flow(h)
        self.assertFalse(dialog._report.ok)
        self.assertEqual(dialog._report.reason, "agent_changed_during_harvest")

    def test_a_frozen_record_that_is_not_the_snapshots_fails_it(self):
        snap = snapshot(frozen=True, record="abcd1234")
        h = _Host(snap, state="frozen",
                  identities=[ident_line(frozen="ffff0000")])
        dialog, _ = self.run_flow(h, "frozen")
        self.assertEqual(h.harvests, [])
        self.assertEqual(dialog._report.reason, "record_changed")

    def test_an_unreadable_identity_fails_before_anything_runs(self):
        h = _Host(snapshot(), identities=[None])
        dialog, _ = self.run_flow(h)
        self.assertEqual(h.harvests, [])
        self.assertFalse(dialog._report.ok)


class ConfirmCallbackTests(unittest.TestCase):
    IDENT = RunIdentity("%1", "4242", "99", "")

    def test_a_failed_report_never_closes_even_when_confirmed(self):
        h = _Host(snapshot())
        h._on_harvest_close_confirmed(True, sc.HarvestReport.failed("x"),
                                      self.IDENT, "live")
        h._on_harvest_close_confirmed(
            True, sc.parse_harvest_output(1, "HARVESTED:a|added=1|existing=0"),
            self.IDENT, "live")
        self.assertEqual((h.closed, h.dropped), ([], []))

    def test_an_ok_live_report_closes_the_bound_identity(self):
        h = _Host(snapshot())
        # Focus moved to another card while the dialog was open (t2065): the
        # close must still name the run that was harvested.
        h._focused_pane_id = "%9"
        report = sc.parse_harvest_output(0, "HARVESTED:capture|added=0|existing=1")
        h._on_harvest_close_confirmed(True, report, self.IDENT, "live")
        self.assertEqual(h.closed, [self.IDENT])

    def test_keep_closes_nothing(self):
        h = _Host(snapshot())
        report = sc.parse_harvest_output(0, "HARVEST_NONE:capture|nothing_found")
        h._on_harvest_close_confirmed(False, report, self.IDENT, "live")
        self.assertEqual(h.closed, [])

    def test_an_ok_frozen_report_drops_only_the_same_record(self):
        snap = snapshot(frozen=True, record="abcd1234")
        ident = RunIdentity("%1", "4242", "99", "abcd1234")
        report = sc.parse_harvest_output(0, "HARVEST_NONE:abcd1234|already_harvested")
        h = _Host(snap, state="frozen")
        h._monitor.option = (True, "abcd1234")
        h._on_harvest_close_confirmed(True, report, ident, "frozen")
        self.assertEqual(h.dropped, [snap])

    def test_a_refrozen_record_is_not_dropped(self):
        """Restored and frozen again between harvest and confirm: another record."""
        snap = snapshot(frozen=True, record="beef0001")
        ident = RunIdentity("%1", "4242", "99", "abcd1234")
        report = sc.parse_harvest_output(0, "HARVEST_NONE:abcd1234|nothing_found")
        h = _Host(snap, state="frozen")
        h._monitor.option = (True, "beef0001")
        h._on_harvest_close_confirmed(True, report, ident, "frozen")
        self.assertEqual(h.dropped, [])
        self.assertIn("changed since the harvest", h.notes[-1][0])

    def test_a_live_option_that_disagrees_with_the_snapshot_is_not_dropped(self):
        snap = snapshot(frozen=True, record="abcd1234")
        ident = RunIdentity("%1", "4242", "99", "abcd1234")
        report = sc.parse_harvest_output(0, "HARVEST_NONE:abcd1234|nothing_found")
        h = _Host(snap, state="frozen")
        h._monitor.option = (True, "beef0001")
        h._on_harvest_close_confirmed(True, report, ident, "frozen")
        self.assertEqual(h.dropped, [])


class GuardedCloseTests(unittest.TestCase):
    IDENT = RunIdentity("%1", "4242", "99", "")

    def test_the_kill_is_the_guarded_run_kill_with_the_bound_identity(self):
        h = _Host(snapshot())
        status, _ = h._guarded_close(self.IDENT)
        self.assertEqual(status, "killed")
        self.assertEqual(h._monitor.guarded, [self.IDENT])
        self.assertEqual(h._monitor.smart, [])

    def test_a_pane_that_is_no_longer_live_is_not_killed(self):
        for state in ("frozen", "unverified"):
            with self.subTest(state=state):
                h = _Host(snapshot(), state=state)
                status, _ = h._guarded_close(self.IDENT)
                self.assertEqual(status, "not_live")
                self.assertEqual(h._monitor.guarded, [])

    def test_a_changed_run_is_reported_not_claimed(self):
        h = _Host(snapshot())
        h._monitor.kill_result = ("changed", False)
        status, _ = h._guarded_close(self.IDENT)
        self.assertEqual(status, "changed")
        self.assertIn("changed since the harvest", h.notes[-1][0])


def _app_shell(cls, snap):
    app = cls.__new__(cls)
    app._monitor = _Mon([ident_line()])
    app._snapshots = {snap.pane.pane_id: snap}
    app._focused_pane_id = snap.pane.pane_id
    app.notes = []
    app.notify = lambda msg, **kw: app.notes.append(msg)
    app.call_later = lambda *a, **k: None
    app._kill_target_state = lambda pane_id: "live"
    return app


class AppLiveCloseTests(unittest.TestCase):
    """Both apps' live close must be the guarded run kill, never the smart one."""

    IDENT = RunIdentity("%1", "4242", "99", "")

    def test_both_apps_use_the_guarded_kill(self):
        for cls in (MonitorApp, MiniMonitorApp):
            with self.subTest(app=cls.__name__):
                app = _app_shell(cls, snapshot())
                app._close_live_after_harvest(self.IDENT)
                self.assertEqual(app._monitor.guarded, [self.IDENT])
                self.assertEqual(app._monitor.smart, [])
                self.assertIn("Closed agent-pick-42", app.notes)

    def test_a_changed_run_keeps_the_pane_and_focus(self):
        for cls in (MonitorApp, MiniMonitorApp):
            with self.subTest(app=cls.__name__):
                app = _app_shell(cls, snapshot())
                app._monitor.kill_result = ("changed", False)
                app._close_live_after_harvest(self.IDENT)
                self.assertEqual(app._focused_pane_id, "%1")
                self.assertNotIn("Closed agent-pick-42", app.notes)


# -- the guarded run kill, against a fake gateway -----------------------------

def fa_row(pane_id: str, pid: str, shadow: str = "") -> str:
    """One `FROZEN_AWARE_PANE_FORMAT` record rendered from the format itself, so
    a field appended to it cannot silently drop the row (t2211_2)."""
    values = {"#{pane_id}": pane_id, "#{pane_pid}": pid, "#{pane_dead}": "0",
              f"#{{{mc.SHADOW_TARGET_OPTION}}}": shadow}
    return "\t".join(values.get(spec, "")
                     for spec in mc.FROZEN_AWARE_PANE_FORMAT.split("\t")) + "\n"


class _FakeTmux:
    """The guarded kill's reads: the pane's live window, that window's panes,
    the read-back after the dispatch, and the helper sweep's listing."""

    OTHER_AGENT = fa_row("%7", "4242") + fa_row("%8", "5555")
    ALONE = fa_row("%7", "4242") + fa_row("%9", "6666", shadow="%7")

    def __init__(self, readback, window=(0, "%7\t@3"), listing=(0, OTHER_AGENT)):
        self.readback = readback
        self.window = window
        self.listing = listing
        self.calls = []

    def __call__(self, args, timeout=5.0):
        self.calls.append(list(args))
        if args[0] == "display-message":
            return self.window if "window_id" in args[-1] else self.readback
        if args[0] == "list-panes":
            return (0, "") if args[1] == "-a" else self.listing
        return 0, ""


def _core_monitor(readback, **kw):
    m = mc.TmuxMonitor.__new__(mc.TmuxMonitor)
    m._pane_cache, m._last_content, m._last_change_time = {}, {}, {}
    m.session = SESSION
    m.tmux_run = _FakeTmux(readback, **kw)
    return m


class GuardedRunKillTests(unittest.TestCase):
    IDENT = RunIdentity("%7", "4242", "99", "")

    def _kills(self, m):
        return [c for c in m.tmux_run.calls
                if c[0] in ("kill-pane", "kill-window", "if-shell")]

    def test_the_only_kill_is_one_if_shell_carrying_pid_and_server(self):
        m = _core_monitor((0, "\t99"))
        self.assertEqual(m.kill_agent_run_guarded(self.IDENT), ("killed", False))
        kills = self._kills(m)
        self.assertEqual(len(kills), 1)
        verb, flag, t, target, cond, branch = kills[0]
        self.assertEqual((verb, flag, t, target), ("if-shell", "-F", "-t", "%7"))
        self.assertIn("#{==:#{pane_pid},4242}", cond)
        self.assertIn("#{==:#{pid},99}", cond)
        self.assertIn(f"#{{==:#{{{mc.FROZEN_OPTION}}},}}", cond)
        self.assertEqual(branch, "kill-pane -t %7")

    def test_a_pane_still_present_is_changed(self):
        m = _core_monitor((0, "%7\t99"))
        self.assertEqual(m.kill_agent_run_guarded(self.IDENT), ("changed", False))
        self.assertFalse(any(c[:2] == ["list-panes", "-a"]
                             for c in m.tmux_run.calls),
                         "a refused kill must not sweep helpers")

    def test_a_failed_or_foreign_readback_is_unknown(self):
        for rb in ((1, ""), (0, "\t12345"), (0, "%9\t99")):
            with self.subTest(readback=rb):
                m = _core_monitor(rb)
                self.assertEqual(m.kill_agent_run_guarded(self.IDENT)[0],
                                 "unknown")

    def test_a_malformed_identity_sends_nothing(self):
        m = _core_monitor((0, "\t99"))
        bad = RunIdentity("%7", "1;kill-server", "99", "")
        self.assertEqual(m.kill_agent_run_guarded(bad), ("failed", False))
        self.assertEqual(self._kills(m), [])

    def test_never_a_window_kill_even_when_the_pane_is_alone_with_helpers(self):
        """A window kill would also take the window's other occupants, whose
        identity no `if-shell` condition (evaluated in the TARGET pane's
        context) can prove — one `swap-pane` after a listing hands it an
        unrelated agent. So the run kill is pane-only, whatever the window
        holds, and the window is never even listed."""
        m = _core_monitor((0, "\t99"), listing=(0, _FakeTmux.ALONE))
        m._pane_cache["%7"] = TmuxPaneInfo(
            window_index="1", window_name="agent-pick-42", pane_index="0",
            pane_id="%7", pane_pid=4242, current_command="node", width=80,
            height=24, category=PaneCategory.AGENT, session_name=SESSION)
        self.assertEqual(m.kill_agent_run_guarded(self.IDENT), ("killed", False))
        (*_rest, branch), = self._kills(m)
        self.assertEqual(branch, "kill-pane -t %7")
        flat = " ".join(" ".join(c) for c in m.tmux_run.calls)
        self.assertNotIn("kill-window", flat)
        self.assertFalse([c for c in m.tmux_run.calls
                          if c[0] == "list-panes" and c[1] == "-t"])

    def test_the_condition_shares_the_helper_sweeps_grammar(self):
        import helper_panes as hp
        cond = hp.run_identity_condition("4242", "99", mc.FROZEN_OPTION)
        self.assertEqual(cond, hp.all_of([
            f"#{{==:#{{{mc.FROZEN_OPTION}}},}}",
            "#{==:#{pane_pid},4242}", "#{==:#{pid},99}"]))


class RunIdentityParseTests(unittest.TestCase):
    def test_parses_and_refuses(self):
        ok = mc.parse_run_identity(0, ident_line(frozen="ab12"), "%1")
        self.assertEqual(ok, RunIdentity("%1", "4242", "99", "ab12"))
        self.assertIsNone(mc.parse_run_identity(1, ident_line(), "%1"))
        self.assertIsNone(mc.parse_run_identity(0, ident_line(pane=""), "%1"))
        self.assertIsNone(mc.parse_run_identity(0, ident_line(pane="%2"), "%1"))
        self.assertIsNone(mc.parse_run_identity(0, ident_line(pid="x"), "%1"))
        self.assertIsNone(mc.parse_run_identity(0, "%1\t4242", "%1"))
        # t2211_2: the sitrep TUI stamp is the fifth field; a 4-field answer
        # (the pre-TUI format) is not a complete identity.
        self.assertEqual(mc.parse_run_identity(0, ident_line(tui="/repo"), "%1"),
                         RunIdentity("%1", "4242", "99", "", "/repo"))
        self.assertIsNone(mc.parse_run_identity(0, "%1\t4242\t99\t", "%1"))


# -- maintenance --------------------------------------------------------------

class _MaintHost(AgentMarksMixin):
    def __init__(self):
        self.order = []
        self._sitrep_harvest_inflight = False
        self._sitrep_harvest_due_at = 0.0

    async def _run_sitrep_harvest(self, args, *, stdin=None, timeout):
        self.order.append(("harvest", tuple(args), timeout))
        return 0, "HARVEST_NONE:x|already_harvested"


class MaintenanceTests(unittest.TestCase):
    def test_harvest_all_runs_before_the_refresh_in_one_pass(self):
        host = _MaintHost()

        async def rec(name):
            host.order.append(name)

        host._maybe_offer_concerns = lambda: rec("concerns")
        host._maybe_purge_marks = lambda: rec("marks")
        host._maybe_purge_sessions = lambda: rec("sessions")
        host._maybe_refresh_sitrep = lambda: rec("refresh")
        coros = []
        host.run_worker = lambda coro, **kw: coros.append(coro)
        host._dispatch_refresh_maintenance()
        asyncio.run(coros[0])
        names = [o if isinstance(o, str) else o[0] for o in host.order]
        self.assertEqual(names, ["concerns", "marks", "sessions", "harvest",
                                 "refresh"])
        self.assertEqual(host.order[3][1], ("all",))

    def test_not_stacked_and_flag_cleared_after_a_raise(self):
        host = _MaintHost()
        host._sitrep_harvest_inflight = True
        asyncio.run(host._maybe_harvest_sitrep())
        self.assertEqual(host.order, [])

        async def boom(args, *, stdin=None, timeout):
            raise RuntimeError("x")

        host = _MaintHost()
        host._run_sitrep_harvest = boom
        asyncio.run(host._maybe_harvest_sitrep())
        self.assertFalse(host._sitrep_harvest_inflight)
        self.assertGreater(host._sitrep_harvest_due_at, time.monotonic())

    def test_not_due_runs_nothing(self):
        host = _MaintHost()
        host._sitrep_harvest_due_at = time.monotonic() + 100
        asyncio.run(host._maybe_harvest_sitrep())
        self.assertEqual(host.order, [])

    def test_class_level_floors(self):
        host = AgentMarksMixin.__new__(AgentMarksMixin)
        self.assertFalse(host._sitrep_harvest_inflight)
        self.assertEqual(host._sitrep_harvest_due_at, 0.0)

    def test_source_order_pin(self):
        src = inspect.getsource(AgentMarksMixin._dispatch_refresh_maintenance)
        self.assertLess(src.index("_maybe_harvest_sitrep()"),
                        src.index("_maybe_refresh_sitrep()"))


# -- the indicator ------------------------------------------------------------

class SitrepNowCounterTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = os.path.realpath(self._tmp.name)

    def _write(self, items):
        import sitrep_todo as st
        store = st.TodoStore()
        for n, (group, state) in enumerate(items, 1):
            store.items[n] = st.Item(n, 1, "task", state, group, "never",
                                     f"t{n}", "script", "", f"item {n}")
        d = os.path.join(self.root, ".aitask-sitrep")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "todo.md"), "w") as fh:
            fh.write(st.render_todo(store))

    def test_counts_open_now_items_and_reparses_only_on_change(self):
        self._write([("now", "open"), ("now", "done"), ("next", "open"),
                     ("now", "open")])
        c = sc.SitrepNowCounter()
        self.assertEqual(c.count(self.root), 2)
        self.assertEqual(c.count(self.root), 2)
        self.assertEqual(c.parses, 1, "unchanged content was reparsed")
        self._write([("now", "open")])
        self.assertEqual(c.count(self.root), 1)
        self.assertEqual(c.parses, 2)

    def test_no_store_or_a_damaged_one_is_none(self):
        c = sc.SitrepNowCounter()
        self.assertIsNone(c.count(self.root))
        d = os.path.join(self.root, ".aitask-sitrep")
        os.makedirs(d)
        with open(os.path.join(d, "todo.md"), "w") as fh:
            fh.write("not a todo file\n")
        self.assertIsNone(c.count(self.root))

    def test_term(self):
        self.assertEqual(sc.format_sitrep_term(None), "")
        self.assertEqual(sc.format_sitrep_term(0), "")
        self.assertEqual(sc.format_sitrep_term(3), "sitrep 3 now")


# -- `ait sitrep open` wording ------------------------------------------------

class SitrepOpenMessageTests(unittest.TestCase):
    def test_each_wire_line(self):
        m = sitrep_cli.sitrep_open_message
        self.assertEqual(m(0, "SITREP_FOCUSED:%5"),
                         ("Switched to the sitrep window", "information"))
        self.assertEqual(m(0, "SITREP_SPAWNED:%6|s:agent-sitrep"),
                         ("Sitrep window opened", "information"))
        self.assertEqual(
            m(0, "SITREP_SPAWNED:%6|s:w\nSITREP_WARN:companion_not_spawned")[1],
            "warning")
        self.assertEqual(m(1, "SITREP_FOCUS_FAILED:%5")[1], "warning")
        self.assertEqual(m(1, "SITREP_REFUSED:lock_busy"),
                         ("Sitrep not opened: lock_busy", "error"))
        self.assertEqual(m(1, "ERROR:x timed out")[1], "error")
        self.assertEqual(m(3, ""), ("Sitrep not opened (exit 3)", "error"))

    def test_the_monitor_uses_the_shared_definition(self):
        self.assertIs(sc.sitrep_open_message, sitrep_cli.sitrep_open_message)

    def test_open_targets_the_selected_agents_root_and_session(self):
        h = _DispatchHost(snapshot())
        h.action_open_sitrep()
        self.assertEqual(h.opened, [("/repo", SESSION)])

    def test_open_without_an_agent_uses_the_apps_own_target(self):
        h = _DispatchHost(None)
        h._project_root = "/own"
        h.action_open_sitrep()
        self.assertEqual(h.opened, [("/own", SESSION)])


class SwitcherSitrepTests(unittest.TestCase):
    """The TUI switcher's `S` quick-jump acts on the SELECTED session."""

    def test_S_is_a_registered_quick_jump(self):
        import tui_switcher as ts
        keys = {b.key: b.action for b in ts._QUICK_JUMP_BINDINGS}
        self.assertEqual(keys.get("S"), "shortcut_sitrep")

        # The registry is process-global, and other modules' tests clear it
        # (keybinding_registry._reset_for_tests) without replaying
        # tui_switcher's import-time registration — so this assertion must not
        # depend on whatever state an earlier test left behind (t2225).
        # Snapshot, start clean with no user overrides, re-execute the module's
        # real registration through the sweep the `?` editor uses (it runs the
        # module body under a probe name, leaving `ts` untouched), then restore.
        import keybinding_registry as kr
        import shortcut_scopes
        saved_defaults = dict(kr._DEFAULTS)
        saved_overrides = kr._OVERRIDES_CACHE

        def _restore():
            kr._DEFAULTS.clear()
            kr._DEFAULTS.update(saved_defaults)
            kr._OVERRIDES_CACHE = saved_overrides
        self.addCleanup(_restore)

        kr._reset_for_tests()
        kr._OVERRIDES_CACHE = {}  # hermetic: ignore the real userconfig.yaml
        failed = shortcut_scopes.register_scope_bindings("shared.tui_switcher")
        self.assertEqual(failed, [], f"sweep import failures: {failed}")
        self.assertEqual(kr.resolve_key(ts._TUI_SWITCHER_SCOPE, "shortcut_sitrep"),
                         "S")

    def test_the_action_dispatches_the_selected_root_and_session(self):
        from unittest.mock import PropertyMock, patch
        import tui_switcher as ts
        ov = ts.TuiSwitcherOverlay.__new__(ts.TuiSwitcherOverlay)
        # `_session` is derived from the SELECTED entry, never the attached one.
        ov._selected_entry = lambda: None
        ov._selected_key = "other"
        ov._handle_stale_selection = lambda: False
        ov._ensure_session_live = lambda: True
        ov._selected_project_root = lambda: Path("/selected/repo")
        dismissed, sent = [], []
        ov.dismiss = lambda result=None: dismissed.append(result)
        ov._dispatch_sitrep_open = (
            lambda app, root, session: sent.append((app, root, session)))
        host = object()
        with patch.object(ts.TuiSwitcherOverlay, "app",
                          new_callable=PropertyMock, return_value=host):
            ov.action_shortcut_sitrep()
        self.assertEqual(sent, [(host, "/selected/repo", "other")])
        self.assertEqual(dismissed, [None])

    def test_a_stale_selection_dispatches_nothing(self):
        import tui_switcher as ts
        ov = ts.TuiSwitcherOverlay.__new__(ts.TuiSwitcherOverlay)
        ov._handle_stale_selection = lambda: True
        sent = []
        ov._dispatch_sitrep_open = lambda *a: sent.append(a)
        ov.action_shortcut_sitrep()
        self.assertEqual(sent, [])


# -- the dialog ---------------------------------------------------------------

class _DialogApp(App):
    def __init__(self, dialog):
        super().__init__()
        self._dialog = dialog
        self.results = []

    def on_mount(self):
        self.push_screen(self._dialog, self.results.append)


class HarvestResultDialogTests(unittest.TestCase):
    def _run(self, dialog, press=None, click=None):
        app = _DialogApp(dialog)
        seen = {}

        async def go():
            async with app.run_test(size=(60, 30)) as pilot:
                await pilot.pause()
                seen["buttons"] = [b.id for b in dialog.query("Button")]
                seen["labels"] = [str(b.label) for b in dialog.query("Button")]
                if press:
                    await pilot.press(press)
                if click:
                    await pilot.click(f"#{click}")
                await pilot.pause()
        asyncio.run(go())
        return seen, app.results

    def test_a_failed_report_offers_no_confirm(self):
        d = sc.HarvestResultDialog("agent-x", "live",
                                   sc.HarvestReport.failed("capture_failed"))
        seen, results = self._run(d, click="btn-cancel")
        self.assertEqual(seen["buttons"], ["btn-cancel"])
        self.assertEqual(results, [False])

    def test_an_ok_frozen_report_offers_drop(self):
        report = sc.parse_harvest_output(0, "HARVEST_NONE:ab|nothing_found")
        d = sc.HarvestResultDialog("agent-x", "frozen", report)
        seen, results = self._run(d, click="btn-confirm")
        self.assertEqual(seen["labels"], ["Drop", "Keep"])
        self.assertEqual(results, [True])

    def test_escape_keeps(self):
        report = sc.parse_harvest_output(0, "HARVEST_NONE:ab|nothing_found")
        d = sc.HarvestResultDialog("agent-x", "live", report)
        seen, results = self._run(d, press="escape")
        self.assertEqual(seen["labels"], ["Close agent", "Keep"])
        self.assertEqual(results, [False])

    def test_a_review_is_listed_in_the_body(self):
        report = sc.parse_harvest_output(
            0, "HARVEST_REVIEW:a|c3|exists|case=0123456789abcdef|bad_followup\n"
               "HARVESTED:a|added=0|existing=1|review=c3")
        d = sc.HarvestResultDialog("agent-x", "frozen", report)
        self.assertIn("review c3 (exists): bad_followup", d.body_text())
        seen, _results = self._run(d)
        self.assertEqual(seen["labels"], ["Drop", "Keep"])

    def test_markup_in_harvested_text_renders_literally(self):
        report = sc.parse_harvest_output(
            0, "HARVEST_ITEM:a|c1|added|task|[bold]t1[/]\nHARVESTED:a|added=1|existing=0")
        d = sc.HarvestResultDialog("agent-[red]x", "live", report,
                                   {"c1": "fix [/] the \\[thing]"})
        body = d.body_text()
        self.assertIn("[bold]t1[/]", body)
        self.assertIn("fix [/] the \\[thing]", body)
        self._run(d)    # renders without a markup error


# -- the real keys ------------------------------------------------------------

class _KeyMonitor:
    multi_session = False
    capture_generation = 0

    def __init__(self, root):
        self._mapping = {SESSION: root}
        self.session = SESSION

    def get_session_to_project_mapping(self): return self._mapping
    async def get_session_to_project_mapping_async(self): return self._mapping
    def get_compare_mode(self, pane_id): return "stripped"
    def is_compare_mode_overridden(self, pane_id): return False
    def get_shadow_snapshot(self, pane_id): return None
    def get_shadow_snapshots(self): return {}
    async def capture_all_classified_async(self): return (0, [])
    def commit_snapshots(self, gen, classified): return None
    async def capture_all_async(self): return None
    def invalidate_sessions_cache(self): pass
    def discover_window_panes(self, window_id): return (False, [])
    async def discover_window_panes_async(self, window_id): return (False, [])


class KeyDispatchTests(unittest.TestCase):
    """`h` and `S` reach the shared actions in BOTH apps (pressed, not called)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(os.path.realpath(self._tmp.name)) / "repo"
        self.root.mkdir()

    def _instrument(self, app, seen):
        if getattr(app, "_refresh_timer", None) is not None:
            app._refresh_timer.stop()
            app._refresh_timer = None
        app._monitor = _KeyMonitor(self.root)
        app._marks_view = agent_marks.MarksView(
            Path(self._tmp.name) / "marks.json")
        app._marks_purge_due_at = float("inf")
        app._set_session_root_map(app._monitor.get_session_to_project_mapping())
        app._snapshots = {"%1": snapshot(), "%2": snapshot(
            window="agent-pick-7", pane_id="%2", window_index="2")}
        app._session = SESSION
        app._own_window_index = "1"
        # `%1` is the followed agent: pane-id membership, confirmed (t2227).
        app._own_window_pane_ids = frozenset({"%1"})
        app._own_identity_confirmed = True
        app._kill_target_state = lambda pane_id: "live"
        app._dispatch_harvest_close = (
            lambda snap, state, root: seen.append(
                ("h", snap.pane.pane_id, state, root)))
        app._dispatch_sitrep_open = (
            lambda root, session: seen.append(("S", root, session)))

    def _press(self, cls, key, size, selector, rebuild):
        seen = []

        async def runner():
            app = cls(session=SESSION, project_root=self.root)
            async with app.run_test(size=size) as pilot:
                self._instrument(app, seen)
                r = rebuild(app)
                if inspect.isawaitable(r):
                    await r
                await pilot.pause()
                cards = list(app.query(selector))
                self.assertTrue(cards, f"no {selector} mounted")
                # The monitor focuses the card it acts on; the minimonitor acts
                # on its FOLLOWED agent (%1, excluded from its list) whatever
                # card is focused — so focus a card that is NOT %1 when one
                # exists, which also proves the minimonitor ignores focus.
                want = "%1" if cls is MonitorApp else "%2"
                target = next((c for c in cards
                               if getattr(c, "pane_id", None) == want), cards[0])
                target.focus()
                await pilot.pause()
                await pilot.press(key)
                await pilot.pause()
                self.assertEqual(len(app.workers), 0)

        asyncio.run(runner())
        return seen

    def test_monitor_h_and_S_act_on_the_focused_card(self):
        for key, want in (("h", ("h", "%1", "live", str(self.root))),
                          ("S", ("S", str(self.root), SESSION))):
            with self.subTest(key=key):
                seen = self._press(MonitorApp, key, (100, 30), "#pane-list PaneCard",
                                   lambda app: app._rebuild_pane_list())
                self.assertEqual(seen, [want])

    def test_minimonitor_h_and_S_act_on_the_followed_agent(self):
        for key, want in (("h", ("h", "%1", "live", str(self.root))),
                          ("S", ("S", str(self.root), SESSION))):
            with self.subTest(key=key):
                seen = self._press(
                    MiniMonitorApp, key, (40, 30),
                    "#mini-pane-list MiniPaneCard",
                    lambda app: app._rebuild_pane_list())
                self.assertEqual(seen, [want])


if __name__ == "__main__":
    unittest.main(verbosity=2)
