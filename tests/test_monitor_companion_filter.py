"""Tests for the unconditional companion-pane filter (t1382).

``_parse_list_panes`` used to consult ``_is_companion_process`` only for panes
already classified ``AGENT`` by window-name prefix::

    category = self.classify_pane(window_name)
    if category == PaneCategory.AGENT and _is_companion_process(pane_pid):
        continue

so renaming an agent window off the ``agent-`` prefix flipped every pane in it
to ``OTHER`` and the companion minimonitor/monitor pane stopped being filtered —
surfacing as a second card for the renamed window in ``ait monitor``. The filter
is now unconditional, like the shadow-helper filter a few lines above it.

The second half covers ``_is_companion_pane``, the memo added so the widened
filter does not probe every pane on every 3 s refresh. Its load-bearing property
is an asymmetry: **positive verdicts are cached, negative ones never are.** The
launch chain execs in place — ``ait`` → ``aitask_monitor.sh`` →
``exec python monitor/monitor_app.py`` — so one pid spans a cmdline that flips
from a non-matching string to a matching one. A cached negative would keep a
companion listed for as long as the pane lived.

No live tmux: ``_parse_list_panes`` is fed a scripted ``list-panes`` string and
``_is_companion_process`` is patched. The TTL is driven through the injected
``_monotonic`` seam, never by sleeping (per
``aidocs/framework/testing_conventions.md``).

Run: python3 tests/test_monitor_companion_filter.py
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

# The suite may run inside a live agent pane; scrub the ambient tmux env so
# TmuxMonitor does not adopt this pane as `exclude_pane` and silently drop a
# fixture row (t1240).
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import subprocess  # noqa: E402

from monitor.monitor_core import (  # noqa: E402
    _COMPANION_MEMO_TTL,
    PaneCategory,
    TmuxPaneInfo,
    TmuxMonitor,
)
from monitor_marker import monitor_marker_state  # noqa: E402

_COMPANION_PID = 4242
_AGENT_PID = 1111
_SHELL_PID = 2222

# --- Real pids for the marker rung (t1686) -----------------------------------
#
# `monitor_marker_alive` is deliberately NOT patched anywhere below: the whole
# point of the change is that discovery calls the canonical rule, so the tests
# drive it with pids whose liveness is real.
_LIVE_PID = os.getpid()


def _reaped_pid() -> int:
    """A pid that is provably gone: spawned, exited, and reaped."""
    proc = subprocess.Popen([sys.executable, "-c", ""])
    proc.wait()
    return proc.pid


_DEAD_PID = _reaped_pid()


def _marker(pid: int, kind: str = "minimonitor") -> str:
    return f"{kind}:{pid}"


def _make_monitor(session: str = "demo") -> TmuxMonitor:
    return TmuxMonitor(
        session=session, multi_session=False, agent_prefixes=["agent-"],
        exclude_pane="",
    )


def _row(
    *,
    window_index: str = "7",
    window_name: str,
    pane_index: str = "1",
    pane_id: str,
    pane_pid: int,
    command: str = "python",
    shadow_target: str = "",
    history_size: str = "0",
    monitor_kind: str = "",
) -> str:
    """One scripted `list-panes` line in `_LIST_PANES_FORMAT` order (11 fields).

    11 is the current arity (t1686 appended `@aitask_monitor_kind`). A builder
    left at an older count is silently dropped by `_parse_list_panes`, so every
    assertion below it would pass vacuously — see `ArityToleranceTests`.
    """
    return "\t".join([
        window_index, window_name, pane_index, pane_id, str(pane_pid),
        command, "80", "24", shadow_target, history_size, monitor_kind,
    ])


class _CompanionSpy:
    """Stand-in for `_is_companion_process` that counts calls per pid."""

    def __init__(self, companion_pids: set[int]) -> None:
        self.companion_pids = set(companion_pids)
        self.calls: list[int] = []

    def __call__(self, pid: int) -> bool:
        self.calls.append(pid)
        return pid in self.companion_pids

    def count_for(self, pid: int) -> int:
        return sum(1 for p in self.calls if p == pid)


class UnconditionalCompanionFilterTests(unittest.TestCase):
    """The filter must key on the process, never on the window name."""

    def test_companion_in_renamed_window_is_filtered(self):
        """The reported defect: `noam_bugs(2)` must not survive discovery.

        This is the case that fails against the pre-t1382 code — the pane is
        classified OTHER, so the `category == AGENT` conjunct short-circuited
        and `_is_companion_process` was never consulted.
        """
        mon = _make_monitor()
        stdout = "\n".join([
            _row(window_name="noam_bugs", pane_index="0", pane_id="%1",
                 pane_pid=_AGENT_PID),
            _row(window_name="noam_bugs", pane_index="1", pane_id="%2",
                 pane_pid=_COMPANION_PID),
        ])
        with patch("monitor.monitor_core._is_companion_process",
                   _CompanionSpy({_COMPANION_PID})):
            panes, shadows = mon._parse_list_panes(stdout, "demo")

        self.assertEqual([p.pane_id for p in panes], ["%1"])
        self.assertEqual(shadows, [])
        self.assertEqual(panes[0].category, PaneCategory.OTHER)
        # Cache-boundary: the filtered companion never enters `_pane_cache`.
        self.assertNotIn("%2", mon._pane_cache)

    def test_companion_in_agent_window_still_filtered(self):
        """No regression on the case that already worked."""
        mon = _make_monitor()
        stdout = "\n".join([
            _row(window_name="agent-pick-42", pane_index="0", pane_id="%1",
                 pane_pid=_AGENT_PID),
            _row(window_name="agent-pick-42", pane_index="1", pane_id="%2",
                 pane_pid=_COMPANION_PID),
        ])
        with patch("monitor.monitor_core._is_companion_process",
                   _CompanionSpy({_COMPANION_PID})):
            panes, _shadows = mon._parse_list_panes(stdout, "demo")

        self.assertEqual([p.pane_id for p in panes], ["%1"])
        self.assertEqual(panes[0].category, PaneCategory.AGENT)

    def test_non_companion_in_renamed_window_survives_as_other(self):
        """Negative control: the filter discriminates on process, not name.

        If it dropped every pane in a non-`agent-` window (or every pane whose
        pid it probed), the renamed window would disappear instead of moving to
        the OTHER section — which is the *other* half of the reported bug.
        """
        mon = _make_monitor()
        stdout = _row(window_name="noam_bugs", pane_id="%1", pane_pid=_SHELL_PID,
                      command="bash")
        with patch("monitor.monitor_core._is_companion_process",
                   _CompanionSpy({_COMPANION_PID})):
            panes, _shadows = mon._parse_list_panes(stdout, "demo")

        self.assertEqual([p.pane_id for p in panes], ["%1"])
        self.assertEqual(panes[0].category, PaneCategory.OTHER)

    def test_shadow_marker_still_wins_over_companion_check(self):
        """A shadow pane is routed to `shadows`, not silently companion-filtered.

        The shadow branch returns before the companion check, and must keep
        doing so: a shadow IS a coding-agent CLI and needs prompt/idle
        bookkeeping.
        """
        mon = _make_monitor()
        stdout = _row(window_name="noam_bugs", pane_id="%9", pane_pid=_AGENT_PID,
                      shadow_target="%1")
        with patch("monitor.monitor_core._is_companion_process",
                   _CompanionSpy({_COMPANION_PID})):
            panes, shadows = mon._parse_list_panes(stdout, "demo")

        self.assertEqual(panes, [])
        self.assertEqual([p.pane_id for p in shadows], ["%9"])
        self.assertEqual(shadows[0].category, PaneCategory.AGENT)
        self.assertNotIn("%9", mon._pane_cache)


class CompanionMemoTests(unittest.TestCase):
    """`_is_companion_pane`: cache positives, never negatives."""

    def _parse(self, mon, stdout, spy, session="demo"):
        with patch("monitor.monitor_core._is_companion_process", spy):
            return mon._parse_list_panes(stdout, session)

    def test_same_pid_exec_transition_is_seen_on_the_next_pass(self):
        """The case a cached negative would break — no tick of exposure.

        One pane, one unchanged pid, verdict flipping False → True (the
        `bash …/aitask_monitor.sh` → `python …/monitor/monitor_app.py` exec).
        The pane must be filtered on the *very next* parse, with no clock
        advance: the TTL must not be what rescues this.

        Negative control: make `_is_companion_pane` cache negatives too and this
        assertion fails, so the test discriminates.
        """
        mon = _make_monitor()
        stdout = _row(window_name="agent-pick-42", pane_id="%2",
                      pane_pid=_COMPANION_PID)

        launching = _CompanionSpy(set())            # still the launcher shell
        panes, _ = self._parse(mon, stdout, launching)
        self.assertEqual([p.pane_id for p in panes], ["%2"],
                         "pre-exec pane should still be listed")
        # Snapshot the memo HERE: after the flip below the pane is a confirmed
        # companion and an entry for it is correct, so the structural rule can
        # only be asserted against this moment.
        memo_after_negative = dict(mon._companion_memo)

        # Behaviour first, so the negative control trips on the user-visible
        # consequence (a companion pane left listed) rather than only on the
        # structural rule below.
        execed = _CompanionSpy({_COMPANION_PID})    # exec'd into monitor_app
        panes, _ = self._parse(mon, stdout, execed)
        self.assertEqual(panes, [],
                         "companion must be filtered on the next pass")
        self.assertEqual(execed.count_for(_COMPANION_PID), 1,
                         "the negative must have been re-probed, not served "
                         "from the memo")
        # …then the rule that guarantees it, pinned as structure.
        self.assertNotIn("%2", memo_after_negative,
                         "a negative verdict must never be memoized")

    def test_positive_verdict_is_memoized(self):
        mon = _make_monitor()
        stdout = _row(window_name="agent-pick-42", pane_id="%2",
                      pane_pid=_COMPANION_PID)
        spy = _CompanionSpy({_COMPANION_PID})

        for _ in range(3):
            panes, _ = self._parse(mon, stdout, spy)
            self.assertEqual(panes, [])

        self.assertEqual(spy.count_for(_COMPANION_PID), 1,
                         "a confirmed companion should be probed once")
        self.assertIn("%2", mon._companion_memo)

    def test_pid_change_reprobes(self):
        """A new process in the same pane is a different process instance."""
        mon = _make_monitor()
        spy = _CompanionSpy({_COMPANION_PID})
        self._parse(mon, _row(window_name="agent-pick-42", pane_id="%2",
                              pane_pid=_COMPANION_PID), spy)
        self.assertEqual(spy.count_for(_COMPANION_PID), 1)

        # Same pane id, different pid, and this one is not a companion.
        panes, _ = self._parse(
            mon,
            _row(window_name="agent-pick-42", pane_id="%2", pane_pid=_AGENT_PID),
            spy,
        )
        self.assertEqual([p.pane_id for p in panes], ["%2"])
        self.assertEqual(spy.count_for(_AGENT_PID), 1)
        self.assertNotIn("%2", mon._companion_memo)

    def test_ttl_expiry_reprobes(self):
        """The self-healing backstop: no verdict is cached forever."""
        mon = _make_monitor()
        clock = {"t": 1000.0}
        mon._monotonic = lambda: clock["t"]
        stdout = _row(window_name="agent-pick-42", pane_id="%2",
                      pane_pid=_COMPANION_PID)
        spy = _CompanionSpy({_COMPANION_PID})

        self._parse(mon, stdout, spy)
        clock["t"] += _COMPANION_MEMO_TTL - 1.0
        self._parse(mon, stdout, spy)
        self.assertEqual(spy.count_for(_COMPANION_PID), 1,
                         "inside the TTL the memo should still serve")

        clock["t"] += 2.0                            # now past the TTL
        panes, _ = self._parse(mon, stdout, spy)
        self.assertEqual(panes, [])
        self.assertEqual(spy.count_for(_COMPANION_PID), 2,
                         "past the TTL the verdict must be re-probed")

    def test_absent_pane_is_evicted(self):
        mon = _make_monitor()
        spy = _CompanionSpy({_COMPANION_PID})
        self._parse(mon, _row(window_name="agent-pick-42", pane_id="%2",
                              pane_pid=_COMPANION_PID), spy)
        self.assertIn("%2", mon._companion_memo)

        # Next tick: the companion pane is gone from this session's output.
        self._parse(mon, _row(window_name="agent-pick-42", pane_id="%1",
                              pane_pid=_AGENT_PID), spy)
        self.assertNotIn("%2", mon._companion_memo)

    def test_eviction_is_session_scoped(self):
        """`_parse_list_panes` runs once per session per tick in multi mode.

        An unscoped sweep would evict the other sessions' live entries on every
        pass, defeating the memo entirely.
        """
        mon = _make_monitor()
        spy = _CompanionSpy({_COMPANION_PID})
        self._parse(mon, _row(window_name="agent-pick-42", pane_id="%2",
                              pane_pid=_COMPANION_PID), spy, session="alpha")
        self.assertIn("%2", mon._companion_memo)

        # A different session's pass must leave alpha's entry alone.
        self._parse(mon, _row(window_name="agent-pick-9", pane_id="%7",
                              pane_pid=_AGENT_PID), spy, session="beta")
        self.assertIn("%2", mon._companion_memo)
        self.assertEqual(mon._companion_memo["%2"][1], "alpha")


class MarkerCompanionFilterTests(unittest.TestCase):
    """The `@aitask_monitor_kind` rung (t1686).

    `#{pane_pid}` is the pane's TOP-LEVEL process. A companion launched as the
    pane's start command is that process and the cmdline match works; one
    restarted from an interactive shell inside the pane is a child of `-bash`,
    so the cmdline rung can never see it and the companion surfaced as a second
    AGENT card sharing its agent's window name.
    """

    def setUp(self):
        # Fixture guard: if `_DEAD_PID` were recycled between spawn and now, the
        # stale-marker test would silently become a live-marker test. Fail here
        # instead, where the cause is legible.
        self.assertEqual(
            monitor_marker_state(_marker(_DEAD_PID)), "stale",
            f"pid {_DEAD_PID} is not provably gone — fixture is unusable",
        )
        self.assertEqual(monitor_marker_state(_marker(_LIVE_PID)), "present")

    def test_shell_hosted_companion_is_filtered_by_marker(self):
        """The reported defect. `_is_companion_process` says False for `-bash`.

        Fails against pre-t1686 code: the pane survives discovery and is
        rendered as a duplicate AGENT card for `agent-pick-1677`.
        """
        mon = _make_monitor()
        stdout = "\n".join([
            _row(window_name="agent-pick-1677", pane_index="0", pane_id="%1",
                 pane_pid=_AGENT_PID),
            _row(window_name="agent-pick-1677", pane_index="1", pane_id="%2",
                 pane_pid=_SHELL_PID, command="bash",
                 monitor_kind=_marker(_LIVE_PID)),
        ])
        with patch("monitor.monitor_core._is_companion_process",
                   _CompanionSpy(set())):
            panes, shadows = mon._parse_list_panes(stdout, "demo")

        self.assertEqual([p.pane_id for p in panes], ["%1"])
        self.assertEqual(shadows, [])
        # Cache-boundary: a marker-filtered companion never enters `_pane_cache`.
        self.assertNotIn("%2", mon._pane_cache)

    def test_marker_is_primary_cmdline_not_consulted(self):
        """A live marker settles it — the /proc read must not even be attempted."""
        mon = _make_monitor()
        stdout = _row(window_name="agent-pick-1677", pane_id="%2",
                      pane_pid=_SHELL_PID, command="bash",
                      monitor_kind=_marker(_LIVE_PID))
        spy = _CompanionSpy({_SHELL_PID})
        with patch("monitor.monitor_core._is_companion_process", spy):
            panes, _ = mon._parse_list_panes(stdout, "demo")

        self.assertEqual(panes, [])
        self.assertEqual(spy.count_for(_SHELL_PID), 0,
                         "the marker is primary: the cmdline rung must not run")

    def test_unmarked_companion_still_filtered_by_cmdline(self):
        """Negative control: the fallback rung is reachable, not dead code.

        `App.run_test()` mounts pass `mark_pane=False`, and panes predating
        t1451 were never stamped, so an unmarked companion must still be caught.
        """
        mon = _make_monitor()
        stdout = _row(window_name="agent-pick-42", pane_id="%2",
                      pane_pid=_COMPANION_PID, monitor_kind="")
        spy = _CompanionSpy({_COMPANION_PID})
        with patch("monitor.monitor_core._is_companion_process", spy):
            panes, _ = mon._parse_list_panes(stdout, "demo")

        self.assertEqual(panes, [])
        self.assertEqual(spy.count_for(_COMPANION_PID), 1,
                         "with no marker the cmdline rung MUST be consulted")

    def test_stale_marker_is_not_a_companion(self):
        """`monitor_marker`'s stale verdict is reused, not re-derived.

        A shell pane left behind by an exited minimonitor is an ordinary pane
        again; treating a stale marker as a companion would hide it forever.
        """
        mon = _make_monitor()
        stdout = _row(window_name="agent-pick-1677", pane_id="%2",
                      pane_pid=_SHELL_PID, command="bash",
                      monitor_kind=_marker(_DEAD_PID))
        with patch("monitor.monitor_core._is_companion_process",
                   _CompanionSpy(set())):
            panes, _ = mon._parse_list_panes(stdout, "demo")

        self.assertEqual([p.pane_id for p in panes], ["%2"])

    def test_unparseable_marker_counts_as_present(self):
        """"Unverifiable is not absence" — `monitor_marker`'s documented rule.

        Pinned here because reusing that verdict is the AC; a local
        re-derivation would most naturally treat "cannot parse" as "no marker".
        """
        mon = _make_monitor()
        stdout = _row(window_name="agent-pick-1677", pane_id="%2",
                      pane_pid=_SHELL_PID, command="bash",
                      monitor_kind="garbage:not-a-pid")
        with patch("monitor.monitor_core._is_companion_process",
                   _CompanionSpy(set())):
            panes, _ = mon._parse_list_panes(stdout, "demo")

        self.assertEqual(panes, [])

    def test_marker_verdict_is_not_memoized(self):
        """A companion that exits must reappear on the NEXT tick, not after the TTL.

        Same pane id, same pid, marker present then gone. The memo bounds the
        cost of the cmdline probe only; caching the marker verdict would hide
        the surviving shell pane for the rest of `_COMPANION_MEMO_TTL`.

        Negative control: memoize the marker verdict in `_is_companion_pane`
        (store into `_companion_memo` on the marker branch) and this fails.
        """
        mon = _make_monitor()
        clock = {"t": 1000.0}
        mon._monotonic = lambda: clock["t"]          # no clock advance below
        spy = _CompanionSpy(set())

        marked = _row(window_name="agent-pick-1677", pane_id="%2",
                      pane_pid=_SHELL_PID, command="bash",
                      monitor_kind=_marker(_LIVE_PID))
        with patch("monitor.monitor_core._is_companion_process", spy):
            panes, _ = mon._parse_list_panes(marked, "demo")
        self.assertEqual(panes, [], "live marker should filter the pane")

        unmarked = _row(window_name="agent-pick-1677", pane_id="%2",
                        pane_pid=_SHELL_PID, command="bash", monitor_kind="")
        with patch("monitor.monitor_core._is_companion_process", spy):
            panes, _ = mon._parse_list_panes(unmarked, "demo")
        self.assertEqual([p.pane_id for p in panes], ["%2"],
                         "the pane must come back immediately once the marker "
                         "is gone — no TTL wait")


class ArityToleranceTests(unittest.TestCase):
    """`_LIST_PANES_ARITIES` is a CLOSED set.

    A record outside it is dropped whole. That is the desired failure mode — a
    drifted stub disappears loudly rather than being reinterpreted field by
    field — but it is also what makes a stale stub pass vacuously, so the
    boundary is pinned here rather than left open.
    """

    def _parse(self, stdout):
        mon = _make_monitor()
        with patch("monitor.monitor_core._is_companion_process",
                   _CompanionSpy(set())):
            panes, _ = mon._parse_list_panes(stdout, "demo")
        return [p.pane_id for p in panes]

    def test_current_arity_parses(self):
        row = _row(window_name="agent-pick-42", pane_id="%1", pane_pid=_AGENT_PID)
        self.assertEqual(len(row.split("\t")), 11)
        self.assertEqual(self._parse(row), ["%1"])

    def test_legacy_arities_still_parse(self):
        """9 and 10 remain accepted (t1159_2 / pre-t1686 records)."""
        base = ["7", "agent-pick-42", "1", "%1", str(_AGENT_PID), "node",
                "80", "24", ""]
        self.assertEqual(self._parse("\t".join(base)), ["%1"])
        self.assertEqual(self._parse("\t".join(base + ["500"])), ["%1"])

    def test_over_and_under_length_rows_are_rejected(self):
        """The guard against a stub that drifts out of the accepted set."""
        row = _row(window_name="agent-pick-42", pane_id="%1", pane_pid=_AGENT_PID)
        parts = row.split("\t")
        self.assertEqual(self._parse("\t".join(parts + ["extra"])), [],
                         "a 12-field record must be rejected, not truncated")
        self.assertEqual(self._parse("\t".join(parts[:8])), [],
                         "an 8-field record must be rejected")

    def test_trailing_empty_marker_survives_on_the_last_record(self):
        """No `strip()` on the buffer: the last row's empty marker is a field.

        tmux emits `…\\t\\n` for an unmarked final pane; a whole-buffer strip
        would eat that tab and drop the record.
        """
        stdout = "".join([
            _row(window_name="agent-pick-42", pane_index="0", pane_id="%1",
                 pane_pid=_AGENT_PID) + "\n",
            _row(window_name="agent-pick-42", pane_index="1", pane_id="%2",
                 pane_pid=_AGENT_PID) + "\n",
        ])
        self.assertTrue(stdout.endswith("\t\n"))
        self.assertEqual(self._parse(stdout), ["%1", "%2"])


class _TmuxStub:
    """Records `tmux_run` argv and replays a scripted `(rc, stdout)`."""

    def __init__(self, stdout: str, rc: int = 0) -> None:
        self.stdout = stdout
        self.rc = rc
        self.calls: list[list[str]] = []

    def __call__(self, args, *rest, **kw):
        self.calls.append(list(args))
        if args and args[0] == "list-panes":
            return self.rc, self.stdout
        return 0, ""


class FindCompanionPaneIdTests(unittest.TestCase):
    """`find_companion_pane_id` — the `prefer_companion` jump target."""

    #: `#{pane_id}\t#{pane_pid}\t#{@aitask_monitor_kind}`
    @staticmethod
    def _line(pane_id: str, pid: int, monitor_kind: str = "") -> str:
        return f"{pane_id}\t{pid}\t{monitor_kind}"

    def _find(self, stdout: str, companion_pids: set[int]):
        mon = _make_monitor()
        stub = _TmuxStub(stdout)
        mon.tmux_run = stub
        with patch("monitor.monitor_core._is_companion_process",
                   _CompanionSpy(companion_pids)):
            return mon.find_companion_pane_id("7", "demo"), stub

    def test_resolves_a_shell_hosted_companion(self):
        """AC 3: marker-only companion, invisible to the cmdline rung."""
        stdout = "\n".join([
            self._line("%1", _AGENT_PID),
            self._line("%2", _SHELL_PID, _marker(_LIVE_PID)),
        ]) + "\n"
        found, stub = self._find(stdout, set())
        self.assertEqual(found, "%2")
        self.assertTrue(
            any("#{@aitask_monitor_kind}" in part
                for call in stub.calls for part in call),
            "the marker must be requested in the same round trip",
        )

    def test_reads_an_unmarked_last_record(self):
        """The record most easily lost: last row, empty trailing field.

        Fails against `stdout.strip().splitlines()` — the final `\\t` is eaten,
        the row is short a field, and the companion never reaches the cmdline
        rung.
        """
        stdout = "\n".join([
            self._line("%1", _AGENT_PID),
            self._line("%2", _COMPANION_PID),   # unmarked companion, listed LAST
        ]) + "\n"
        found, _ = self._find(stdout, {_COMPANION_PID})
        self.assertEqual(found, "%2")

    def test_stale_marker_falls_through_to_the_cmdline_rung(self):
        stdout = self._line("%2", _COMPANION_PID, _marker(_DEAD_PID)) + "\n"
        self.assertEqual(self._find(stdout, {_COMPANION_PID})[0], "%2")
        self.assertIsNone(self._find(stdout, set())[0])

    def test_malformed_pid_does_not_suppress_a_valid_marker(self):
        stdout = f"%2\tnot-a-pid\t{_marker(_LIVE_PID)}\n"
        self.assertEqual(self._find(stdout, set())[0], "%2")

    def test_no_companion_returns_none(self):
        stdout = self._line("%1", _AGENT_PID) + "\n"
        self.assertIsNone(self._find(stdout, set())[0])


class KillAgentPaneSmartTests(unittest.TestCase):
    """`kill_agent_pane_smart` — window-vs-pane, the behavioural half."""

    #: `#{pane_id}\t#{pane_pid}\t#{@aitask_shadow_target}\t#{@aitask_monitor_kind}`
    @staticmethod
    def _line(pane_id: str, pid: int, shadow: str = "",
              monitor_kind: str = "") -> str:
        return f"{pane_id}\t{pid}\t{shadow}\t{monitor_kind}"

    def _kill(self, stdout: str, companion_pids: set[int], target="%1"):
        mon = _make_monitor()
        mon._pane_cache[target] = TmuxPaneInfo(
            window_index="7", window_name="agent-pick-1677", pane_index="0",
            pane_id=target, pane_pid=_AGENT_PID, current_command="node",
            width=80, height=24, category=PaneCategory.AGENT,
            session_name="demo",
        )
        mon.tmux_run = _TmuxStub(stdout)
        killed: list[str] = []
        mon.kill_window = lambda pid_: (killed.append("window"), True)[1]
        mon.kill_pane = lambda pid_: (killed.append("pane"), True)[1]
        with patch("monitor.monitor_core._is_companion_process",
                   _CompanionSpy(companion_pids)):
            ok, killed_window = mon.kill_agent_pane_smart(target)
        return killed, ok, killed_window

    def test_collapses_window_for_shell_hosted_companion(self):
        """AC 2: a marker-carrying companion is a helper, so the window dies."""
        stdout = "\n".join([
            self._line("%1", _AGENT_PID),
            self._line("%2", _SHELL_PID, monitor_kind=_marker(_LIVE_PID)),
        ]) + "\n"
        killed, ok, killed_window = self._kill(stdout, set())
        self.assertEqual(killed, ["window"])
        self.assertTrue(ok)
        self.assertTrue(killed_window)

    def test_negative_control_unmarked_sibling_downgrades_to_pane(self):
        """The same fixture WITHOUT the marker keeps the window alive.

        This is what proves the assertion above tracks the marker rather than
        the fixture shape: `%2` is then an ordinary sibling agent.
        """
        stdout = "\n".join([
            self._line("%1", _AGENT_PID),
            self._line("%2", _SHELL_PID),
        ]) + "\n"
        killed, _ok, killed_window = self._kill(stdout, set())
        self.assertEqual(killed, ["pane"])
        self.assertFalse(killed_window)

    def test_counts_an_unmarked_last_real_agent(self):
        """The pre-existing defect: the LAST record's empty trailing field.

        Under `stdout.strip().splitlines()` the final row loses a field, is
        dropped, `count_other_real_agents` returns 0, and the whole window is
        killed with a live agent still in it. `test_kill_agent_pane_smart.sh`
        cannot see this: its fixture lists the COMPANION last, where dropping a
        helper changes no count.
        """
        stdout = "\n".join([
            self._line("%1", _AGENT_PID),
            self._line("%3", _COMPANION_PID, monitor_kind=_marker(_LIVE_PID)),
            self._line("%2", _SHELL_PID),      # real sibling agent, listed LAST
        ]) + "\n"
        killed, _ok, killed_window = self._kill(stdout, set())
        self.assertEqual(killed, ["pane"],
                         "the last-listed real agent must still be counted")
        self.assertFalse(killed_window)

    def test_last_record_dropped_would_kill_the_window(self):
        """Pins the consequence: with that sibling truly absent, the window dies.

        Paired with the test above, this shows the difference is the surviving
        record and not something else about the fixture.
        """
        stdout = "\n".join([
            self._line("%1", _AGENT_PID),
            self._line("%3", _COMPANION_PID, monitor_kind=_marker(_LIVE_PID)),
        ]) + "\n"
        killed, _ok, killed_window = self._kill(stdout, set())
        self.assertEqual(killed, ["window"])
        self.assertTrue(killed_window)

    def test_shadow_marker_still_marks_a_helper(self):
        """No regression on the shadow rung it shares the loop with."""
        stdout = "\n".join([
            self._line("%1", _AGENT_PID),
            self._line("%9", _AGENT_PID, shadow="%1"),
        ]) + "\n"
        killed, _ok, _kw = self._kill(stdout, set())
        self.assertEqual(killed, ["window"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
