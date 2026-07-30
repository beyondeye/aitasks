"""Generation safety for the mark purge's discovery facts (t1326).

The purge decides deletions from two facts — which sessions were enumerated and
which agent windows exist. Both are recorded at discovery time and published by
`commit_snapshots` on its winning-generation branch, so they can never be paired
with a different tick's snapshots.

That pairing is the hazard worth pinning. `capture_all_classified_async` reserves
its generation BEFORE awaiting discovery, and refreshes overlap, so a superseded
older capture can finish discovery after a newer one has committed. If the facts
were a bare attribute assigned inside discovery, the older batch would overwrite
the newer one's view and the purge would delete live marks.

NEGATIVE CONTROL: make `_record_discovery_facts` assign
`self._enumerated_sessions` / `self._discovered_agents` directly instead of
stashing under `gen` -> `test_superseded_generation_never_publishes` fails.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from monitor.monitor_core import (  # noqa: E402
    PaneCategory, TmuxMonitor, TmuxPaneInfo,
)


def pane(session: str, window: str, pane_id: str,
         category: PaneCategory = PaneCategory.AGENT) -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index="1", window_name=window, pane_index="0", pane_id=pane_id,
        pane_pid=4242, current_command="node", width=80, height=24,
        category=category, session_name=session,
    )


def _monitor() -> TmuxMonitor:
    return TmuxMonitor(session="demo", multi_session=False)


class DiscoveryFactRecordingTests(unittest.TestCase):
    def test_facts_are_not_visible_until_the_commit_publishes_them(self):
        mon = _monitor()
        mon._record_discovery_facts(1, [pane("demo", "agent-a", "%1")], [])
        self.assertEqual(mon.last_enumerated_sessions(), frozenset())
        self.assertEqual(mon.last_discovered_agents(), frozenset())
        mon._publish_discovery_facts(1)
        self.assertEqual(mon.last_enumerated_sessions(), {"demo"})
        self.assertEqual(mon.last_discovered_agents(), {("demo", "agent-a")})

    def test_non_agent_panes_enumerate_the_session_without_being_agents(self):
        """A session running only a TUI is enumerated — so it is sweepable and
        its departed agents' marks can be reaped — but contributes no agent."""
        mon = _monitor()
        mon._record_discovery_facts(
            1, [pane("demo", "board", "%1", PaneCategory.TUI)], []
        )
        mon._publish_discovery_facts(1)
        self.assertEqual(mon.last_enumerated_sessions(), {"demo"})
        self.assertEqual(mon.last_discovered_agents(), frozenset())

    def test_shadow_panes_enumerate_their_session(self):
        mon = _monitor()
        mon._record_discovery_facts(1, [], [pane("demo", "agent-a", "%9")])
        mon._publish_discovery_facts(1)
        self.assertEqual(mon.last_enumerated_sessions(), {"demo"})


class GenerationInterleavingTests(unittest.TestCase):
    def test_superseded_generation_never_publishes(self):
        """Older discovery finishing AFTER a newer commit must be inert."""
        mon = _monitor()
        # gen 1 reserves and discovers session A.
        mon._record_discovery_facts(1, [pane("sA", "agent-old", "%1")], [])
        # gen 2 reserves, discovers session B, and commits first.
        mon._record_discovery_facts(2, [pane("sB", "agent-new", "%2")], [])
        mon._publish_discovery_facts(2)
        self.assertEqual(mon.last_enumerated_sessions(), {"sB"})

        # The superseded gen-1 batch now tries to commit. It must publish
        # nothing — its facts were pruned when the newer generation registered.
        mon._publish_discovery_facts(1)
        self.assertEqual(
            mon.last_enumerated_sessions(), {"sB"},
            "a superseded generation overwrote the winner's facts",
        )
        self.assertEqual(mon.last_discovered_agents(), {("sB", "agent-new")})

    def test_newer_registration_prunes_older_pending_facts(self):
        mon = _monitor()
        mon._record_discovery_facts(1, [pane("sA", "agent-a", "%1")], [])
        self.assertIn(1, mon._discovery_facts)
        mon._record_discovery_facts(2, [pane("sB", "agent-b", "%2")], [])
        self.assertNotIn(1, mon._discovery_facts, "stale generation not pruned")
        self.assertIn(2, mon._discovery_facts)

    def test_publishing_an_unknown_generation_is_a_no_op(self):
        mon = _monitor()
        mon._record_discovery_facts(5, [pane("sA", "agent-a", "%1")], [])
        mon._publish_discovery_facts(5)
        mon._publish_discovery_facts(5)  # already popped
        self.assertEqual(mon.last_enumerated_sessions(), {"sA"})


class RealDiscoveryEnumerationTests(unittest.TestCase):
    """The enumerated-session set must come from `list-panes` rc, not from what
    survives filtering — driven through the REAL discovery path.

    `_parse_list_panes` drops a companion pane sitting in an agent-named window
    (`monitor_core.py`: `category == AGENT and _is_companion_process(pid)`). So
    the moment an agent exits and only its minimonitor split remains, the whole
    session parses to ZERO panes. Inferring enumeration from surviving panes
    would then declare the session unobservable, leave it un-sweepable, and
    strand the departed agent's mark until TTL — the exact case this feature
    exists to handle promptly.
    """

    _FIELDS = 9  # _LIST_PANES_FORMAT is 9 tab-separated fields

    def _row(self, window: str, pid: int) -> str:
        return "\t".join(
            ["1", window, "0", "%1", str(pid), "node", "80", "24", ""]
        )

    def _monitor_with(self, stdout: str, *, companion: bool):
        import monitor.monitor_core as mc

        mon = TmuxMonitor(session="demo", multi_session=False)

        async def fake_tmux(args, timeout=5.0):
            return 0, stdout

        mon._tmux_async = fake_tmux
        self._patch = getattr(mc, "_is_companion_process")
        mc._is_companion_process = lambda pid: companion
        self.addCleanup(setattr, mc, "_is_companion_process", self._patch)
        return mon

    def test_session_with_only_the_excluded_companion_is_still_enumerated(self):
        import asyncio

        mon = self._monitor_with(
            self._row("agent-t42", 4242) + "\n", companion=True
        )
        sink: list = []
        panes, shadows = asyncio.run(
            mon.discover_panes_with_shadows_async(enum_sink=sink)
        )
        self.assertEqual(panes, [], "companion pane should be filtered out")
        self.assertEqual(
            sink[0], frozenset({"demo"}),
            "a session that enumerated cleanly must be reported even when "
            "every pane it returned was filtered away",
        )

    def test_a_normal_session_is_enumerated(self):
        import asyncio

        mon = self._monitor_with(
            self._row("agent-t42", 4242) + "\n", companion=False
        )
        sink: list = []
        panes, _ = asyncio.run(
            mon.discover_panes_with_shadows_async(enum_sink=sink)
        )
        self.assertEqual(len(panes), 1)
        self.assertEqual(sink[0], frozenset({"demo"}))

    def test_failed_list_panes_is_not_enumerated(self):
        import asyncio

        mon = TmuxMonitor(session="demo", multi_session=False)

        async def failing(args, timeout=5.0):
            return 1, ""

        mon._tmux_async = failing
        sink: list = []
        panes, _ = asyncio.run(
            mon.discover_panes_with_shadows_async(enum_sink=sink)
        )
        self.assertEqual(panes, [])
        self.assertEqual(
            sink[0], frozenset(),
            "a session we could not list must never be treated as observed",
        )

    def test_companion_only_session_reaches_the_published_facts(self):
        """End-to-end through the generation-guarded commit."""
        import asyncio

        mon = self._monitor_with(
            self._row("agent-t42", 4242) + "\n", companion=True
        )

        async def go():
            gen, classified = await mon.capture_all_classified_async()
            mon.commit_snapshots(gen, classified)

        asyncio.run(go())
        self.assertEqual(
            mon.last_enumerated_sessions(), {"demo"},
            "the sweep would not reap the departed agent's mark",
        )
        self.assertEqual(mon.last_discovered_agents(), frozenset())


class CommitGuardTests(unittest.TestCase):
    def test_commit_snapshots_publishes_only_past_the_generation_guard(self):
        mon = _monitor()
        gen = mon._next_generation()
        mon._record_discovery_facts(gen, [pane("demo", "agent-a", "%1")], [])
        # Supersede it before committing.
        mon._next_generation()
        self.assertIsNone(mon.commit_snapshots(gen, []))
        self.assertEqual(
            mon.last_enumerated_sessions(), frozenset(),
            "a superseded commit published its facts anyway",
        )

    def test_commit_snapshots_publishes_on_the_winning_generation(self):
        mon = _monitor()
        gen = mon._next_generation()
        mon._record_discovery_facts(gen, [pane("demo", "agent-a", "%1")], [])
        self.assertIsNotNone(mon.commit_snapshots(gen, []))
        self.assertEqual(mon.last_enumerated_sessions(), {"demo"})
        self.assertEqual(mon.last_discovered_agents(), {("demo", "agent-a")})


if __name__ == "__main__":
    unittest.main(verbosity=1)
