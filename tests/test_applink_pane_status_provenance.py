"""The pane_status frame carries scoping provenance (t1467).

`awaiting_input_kind` alone cannot say whether prompt matching was scoped to the
pane's own agent or fell back to the unscoped flat list because the pane command
did not resolve — and on this machine the fallback is the common case (a Codex
pane reports `node`). Before t1467 both regimes produced byte-identical frames,
so a client had no way to tell.

Asserts on the SERIALIZED frame rather than on the snapshot fields: the fields
are only worth adding if something downstream actually differs.

Run:
  python3 tests/test_applink_pane_status_provenance.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts"))

from monitor.monitor_core import (  # noqa: E402
    PaneCategory,
    PaneSnapshot,
    TmuxPaneInfo,
)
from applink.pusher import PushScheduler  # noqa: E402


def _pane(current_command: str) -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index="1", window_name="agent-pick-1467", pane_index="0",
        pane_id="%1", pane_pid=4242, current_command=current_command,
        width=80, height=24, category=PaneCategory.AGENT, session_name="demo",
    )


def _snap(current_command: str, *, agent_key: str, scoped: bool) -> PaneSnapshot:
    return PaneSnapshot(
        pane=_pane(current_command), content="x", timestamp=0.0,
        idle_seconds=0.0, is_idle=False,
        awaiting_input=True, awaiting_input_kind="claude_help_bar",
        agent_key=agent_key, scoped=scoped,
    )


class _CapturingPusher(PushScheduler):
    """Drives the real frame builder, capturing what it would have sent."""

    def __init__(self):
        # Deliberately NOT calling super().__init__: this drives one method,
        # and the real constructor wants a live server/subscription graph.
        self.sent: list[str] = []
        self._tasks = None

    async def _send(self, data) -> bool:      # type: ignore[override]
        self.sent.append(data)
        return True

    def frame_for(self, snap) -> dict:
        asyncio.run(self._send_pane_status(snap))
        return json.loads(self.sent[-1])


class PaneStatusProvenanceTest(unittest.TestCase):
    def test_scoped_pane_reports_its_agent(self):
        frame = _CapturingPusher().frame_for(
            _snap("claude", agent_key="claude", scoped=True))
        payload = frame["payload"]
        self.assertIs(payload["awaiting_input_scoped"], True)
        self.assertEqual(payload["agent_key"], "claude")

    def test_unresolved_pane_is_reported_as_unscoped(self):
        """The measured `node` case — a Codex pane, which resolves to nothing
        at the classify stage and must not look like a scoped one."""
        frame = _CapturingPusher().frame_for(
            _snap("node", agent_key="", scoped=False))
        payload = frame["payload"]
        self.assertIs(payload["awaiting_input_scoped"], False)
        self.assertNotIn("agent_key", payload,
                         "an unresolved pane must not claim an agent")

    def test_the_two_regimes_produce_different_frames(self):
        """The whole point: identical kinds, distinguishable payloads."""
        scoped = _CapturingPusher().frame_for(
            _snap("claude", agent_key="claude", scoped=True))
        unscoped = _CapturingPusher().frame_for(
            _snap("node", agent_key="", scoped=False))
        self.assertEqual(scoped["payload"]["awaiting_input_kind"],
                         unscoped["payload"]["awaiting_input_kind"])
        self.assertNotEqual(scoped["payload"], unscoped["payload"])

    def test_protocol_version_is_not_bumped(self):
        """Additive optional fields only — clients ignore what they don't know
        (aidocs/applink/protocol.md "Versioning"), so `v` must stay 1."""
        for snap in (_snap("claude", agent_key="claude", scoped=True),
                     _snap("node", agent_key="", scoped=False)):
            frame = _CapturingPusher().frame_for(snap)
            self.assertEqual(frame["v"], 1)
            self.assertEqual(frame["verb"], "pane_status")

    def test_pre_existing_payload_keys_are_unchanged(self):
        """Guards the additive claim: no existing key may move or vanish."""
        frame = _CapturingPusher().frame_for(
            _snap("claude", agent_key="claude", scoped=True))
        for key in ("pane_id", "idle_seconds", "is_idle", "awaiting_input",
                    "awaiting_input_kind", "window_name", "category",
                    "session_name", "task_id"):
            self.assertIn(key, frame["payload"], key)


if __name__ == "__main__":
    unittest.main()
