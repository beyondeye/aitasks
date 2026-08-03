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

from monitor.monitor_core import (  # noqa: E402
    _COMPANION_MEMO_TTL,
    PaneCategory,
    TmuxMonitor,
)

_COMPANION_PID = 4242
_AGENT_PID = 1111
_SHELL_PID = 2222


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
) -> str:
    """One scripted `list-panes` line in `_LIST_PANES_FORMAT` order (9 fields)."""
    return "\t".join([
        window_index, window_name, pane_index, pane_id, str(pane_pid),
        command, "80", "24", shadow_target,
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
