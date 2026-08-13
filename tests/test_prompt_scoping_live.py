"""Per-agent prompt scoping is wired end-to-end through real tmux (t1467).

The unit tests in `test_prompt_detection.py` drive `classify_content` correctly
— but `classify_content` can be perfectly correct while one of the five call
sites in `monitor_core.py` never passes `agent=`, and every unit test stays
green. Only a run through the real capture path exercises the wiring.

So this drives `TmuxMonitor` against a live tmux server holding two panes whose
`pane_current_command` really is `claude` and `codex`, writes each agent's
prompt text onto the OTHER agent's pane, and asserts from the resulting
snapshots that neither claims the foreign kind while each still detects its own.

It also covers the measured wrapper shape — a pane whose command is `node` with
a `codex` child — which is how Codex actually appears on a machine with an npm
install, and which rung 2 of `agent_keys.agent_key_from_pane` exists to resolve.

Skip vs fail: `SkipTest` is for environment unavailability only (no tmux, or a
pane that never came into existence). Once the panes exist, a wrong kind is the
regression this test exists to catch and fails.

Run:
  python3 tests/test_prompt_scoping_live.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from monitor.monitor_core import PaneCategory, TmuxMonitor  # noqa: E402

SOCKET = f"ait_t1467_scope_{os.getpid()}"
SESSION = "t1467_scoping"
PANE_W, PANE_H = 120, 24
SETTLE_TIMEOUT_S = 20.0
POLL_S = 0.25

# Bodies that unambiguously match one agent's pattern and no other's.
CLAUDE_BODY = "Esc to cancel · Tab to amend"            # claude_help_bar
CODEX_BODY = "  Press enter to confirm or esc to cancel"  # codex_permission


def _tmux(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["tmux", "-L", SOCKET, *args],
                          capture_output=True, text=True, check=False)


@unittest.skipUnless(shutil.which("tmux"), "tmux not available")
@unittest.skipUnless(shutil.which("pgrep"), "pgrep not available")
class PromptScopingLiveTests(unittest.TestCase):

    tmpdir: str = ""

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix="t1467-scope-")
        sleep_bin = shutil.which("sleep") or "/bin/sleep"

        def fake(name: str) -> str:
            dest = os.path.join(cls.tmpdir, name)
            shutil.copy2(sleep_bin, dest)
            os.chmod(dest, 0o755)
            return dest

        cls.claude_bin = fake("claude")
        cls.codex_bin = fake("codex")

        # Window names must carry the `agent-` prefix: PaneCategory.AGENT comes
        # from the window name, and prompt matching runs only for AGENT panes.
        res = _tmux("new-session", "-d", "-s", SESSION, "-n", "agent-claude",
                    "-x", str(PANE_W), "-y", str(PANE_H),
                    f"{cls.claude_bin} 300")
        if res.returncode != 0:
            raise unittest.SkipTest(f"could not start tmux session: {res.stderr}")
        _tmux("new-window", "-t", SESSION, "-n", "agent-codex",
              f"{cls.codex_bin} 300")
        # The measured wrapper shape: sh forks a child named `codex`, so the
        # pane command is NOT codex but its direct child is.
        _tmux("new-window", "-t", SESSION, "-n", "agent-wrapped",
              f'sh -c \'"$0" 300 & wait\' {cls.codex_bin}')

    @classmethod
    def tearDownClass(cls):
        _tmux("kill-server")
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    # -- helpers ----------------------------------------------------------

    def _panes(self) -> dict[str, object]:
        """Poll until the panes exist AND their commands have settled.

        tmux runs a command containing spaces through `sh -c`, so for the first
        moments after creation `pane_current_command` is `sh`, not the target
        binary. Waiting only for the panes to *exist* made the first test in the
        class read `sh` and the later ones read `claude` — an order-dependent
        flake that looked like a scoping bug. Wait for the value under test.
        """
        mon = TmuxMonitor(session=SESSION, idle_threshold=0.05)
        os.environ["AITASKS_TMUX_SOCKET"] = SOCKET
        deadline = time.monotonic() + SETTLE_TIMEOUT_S
        last: dict[str, object] = {}
        while time.monotonic() < deadline:
            last = self._capture(mon)
            settled = (
                last.get("agent-claude", ("", "", 0))[1] == "claude"
                and last.get("agent-codex", ("", "", 0))[1] == "codex"
                and "agent-wrapped" in last
            )
            if settled:
                return last
            time.sleep(POLL_S)
        self.fail(f"panes never settled to their target commands: {last}")

    def _capture(self, mon) -> dict[str, object]:
        out = _tmux("list-panes", "-a", "-F",
                    "#{window_name}\t#{pane_id}\t#{pane_current_command}\t#{pane_pid}")
        found = {}
        for line in out.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) != 4:
                continue
            window, pane_id, cmd, pid = parts
            found[window] = (pane_id, cmd, int(pid))
        return found

    def _classify(self, window: str, body: str):
        """Run the REAL monitor finalize path for one pane."""
        panes = self._panes()
        if window not in panes:
            self.fail(f"pane {window} missing: {sorted(panes)}")
        pane_id, cmd, pid = panes[window]
        from monitor.monitor_core import TmuxPaneInfo
        info = TmuxPaneInfo(
            window_index="0", window_name=window, pane_index="0",
            pane_id=pane_id, pane_pid=pid, current_command=cmd,
            width=PANE_W, height=PANE_H, category=PaneCategory.AGENT,
            session_name=SESSION,
        )
        mon = TmuxMonitor(session=SESSION, idle_threshold=0.05)
        return cmd, mon._finalize_capture(info, body)

    # -- the proof --------------------------------------------------------

    def test_pane_commands_are_what_the_fixture_intends(self):
        """Guards the fixture itself: if these are not the real commands, every
        assertion below would pass vacuously."""
        panes = self._panes()
        self.assertEqual(panes["agent-claude"][1], "claude")
        self.assertEqual(panes["agent-codex"][1], "codex")
        self.assertIn(panes["agent-wrapped"][1], ("sh", "dash", "bash"))

    def test_each_agent_detects_its_own_prompt(self):
        """Positive control — without it the negatives below prove nothing."""
        _, claude = self._classify("agent-claude", CLAUDE_BODY)
        self.assertEqual(claude.awaiting_input_kind, "claude_help_bar")
        self.assertTrue(claude.scoped)
        self.assertEqual(claude.agent_key, "claude")

        _, codex = self._classify("agent-codex", CODEX_BODY)
        self.assertEqual(codex.awaiting_input_kind, "codex_permission")
        self.assertEqual(codex.agent_key, "codex")

    def test_neither_pane_claims_the_other_agents_prompt(self):
        """The regression a missed `agent=` at any call site would produce."""
        _, claude = self._classify("agent-claude", CODEX_BODY)
        self.assertEqual(claude.awaiting_input_kind, "",
                         "a claude pane must not report a codex kind")
        self.assertFalse(claude.awaiting_input)

        _, codex = self._classify("agent-codex", CLAUDE_BODY)
        self.assertEqual(codex.awaiting_input_kind, "",
                         "a codex pane must not report a claude kind")
        self.assertFalse(codex.awaiting_input)

    def test_wrapper_pane_resolves_through_its_child(self):
        """The measured `node` → `codex` shape, through the real process table."""
        cmd, snap = self._classify("agent-wrapped", CODEX_BODY)
        self.assertNotIn(cmd, ("codex",), "fixture must not resolve at rung 1")
        self.assertEqual(snap.agent_key, "codex",
                         f"rung 2 must resolve a {cmd!r} pane with a codex child")
        self.assertTrue(snap.scoped)
        self.assertEqual(snap.awaiting_input_kind, "codex_permission")


if __name__ == "__main__":
    unittest.main()
