"""TUI launches carry the agent string a real `invoke` exports (t1850).

Every TUI starts an agent by LAUNCHING the command
`aitask_codeagent.sh --dry-run` printed, and the dry-run returns before the
wrapper's `export AITASK_AGENT_STRING`. Without that variable the SessionStart
hook records a blank agent string, and a frozen agent restores on the project
default model. `resolve_dry_run_command` now asks for the export back
(`--with-agent-env`), which prefixes the command with `env AITASK_AGENT_STRING=…`.

The live case pins the constraint that prefix must keep: `env` EXECS into the
command, so the tmux pane's pid is still the agent's. The task-lock liveness
anchor depends on that (t1465). A wrapper that outlived the agent would keep a
dead agent's lock looking alive.

Shells the real `aitask_codeagent.sh --dry-run`; no agent is launched.

Run: python3 tests/test_launch_agent_string_env.py
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_launch_utils as alu  # noqa: E402
from tmux_exec import TmuxClient  # noqa: E402

TASK_ID = "1850"
PREFIX = "env AITASK_AGENT_STRING="
#: A real second entry in `aitasks/metadata/models_claudecode.json`.
OTHER_AGENT_STRING = "claudecode/sonnet5"

#: `--dry-run` needs only jq and this repo's own metadata; it never looks for
#: the agent binary. So jq is the ONE dependency whose absence may skip, and a
#: None from the resolver with jq present is a defect (a bad wrapper flag, broken
#: output parsing) that must fail, not skip.
HAVE_JQ = shutil.which("jq") is not None


def _model_is_configured(agent_string: str) -> bool:
    """Whether ``agent_string`` names an entry in this repo's models JSON."""
    agent, _, name = agent_string.partition("/")
    path = REPO_ROOT / "aitasks" / "metadata" / f"models_{agent}.json"
    try:
        models = json.loads(path.read_text())["models"]
    except (OSError, ValueError, KeyError):
        return False
    return any(m.get("name") == name for m in models)


def _resolve(*args, **kwargs) -> str:
    cmd = alu.resolve_dry_run_command(REPO_ROOT, *args, **kwargs)
    if cmd is None:
        raise AssertionError(
            f"resolve_dry_run_command{args} returned None with jq present — "
            "the wrapper rejected the call or its output did not parse")
    return cmd


def _prefix_value(cmd: str) -> str:
    """The AITASK_AGENT_STRING value carried by an `env` launch prefix."""
    argv = shlex.split(cmd)
    assert argv[0] == "env", cmd
    name, _, value = argv[1].partition("=")
    assert name == "AITASK_AGENT_STRING", cmd
    return value


@unittest.skipUnless(HAVE_JQ, "jq not installed (the wrapper requires it)")
class TestResolvedCommandCarriesTheAgentString(unittest.TestCase):

    def setUp(self):
        self.cmd = _resolve("pick", TASK_ID)

    def test_prefix_names_the_configured_agent_string(self):
        self.assertTrue(self.cmd.startswith(PREFIX), self.cmd)
        expected = alu.resolve_agent_string(REPO_ROOT, "pick")
        self.assertEqual(expected, _prefix_value(self.cmd))

    def test_an_explicit_agent_string_is_the_one_exported(self):
        if not _model_is_configured(OTHER_AGENT_STRING):
            self.skipTest(f"{OTHER_AGENT_STRING} is not in the models JSON")
        other = _resolve("pick", TASK_ID, agent_string=OTHER_AGENT_STRING)
        self.assertEqual(OTHER_AGENT_STRING, _prefix_value(other))

    def test_pick_launch_argv_carries_the_prefix(self):
        cmd, _window = alu.pick_launch_argv(REPO_ROOT, TASK_ID)
        self.assertEqual(self.cmd, cmd)
        self.assertTrue(cmd.startswith(PREFIX), cmd)


@unittest.skipUnless(HAVE_JQ, "jq not installed (the wrapper requires it)")
@unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
@unittest.skipUnless(Path("/proc/self/environ").exists(), "needs /proc")
class TestPanePidAnchorLive(unittest.TestCase):
    """[pane_pid_anchor_live_check] The env prefix execs; the pane pid is the command."""

    def setUp(self):
        self.socket = f"ait-t1850-{uuid.uuid4().hex[:8]}"
        self.session = "t1850probe"
        self.client = TmuxClient(["-L", self.socket])
        # A private socket only, whatever the pane this runs in says: an
        # inherited $TMUX must never steer a probe at the live server.
        env = {k: v for k, v in os.environ.items() if k != "TMUX"}
        env["AIT_NO_SYSTEMD_RUN"] = "1"
        patches = [
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(alu, "_TMUX", self.client),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self._kill_session)

    def _kill_session(self):
        # kill-session, never kill-server; on a private socket its last
        # session ending takes the server with it.
        self.client.run(["kill-session", "-t", f"={self.session}"])
        tmpdir = os.environ.get("TMUX_TMPDIR") or "/tmp"
        sock = Path(tmpdir, f"tmux-{os.getuid()}", self.socket)
        try:
            sock.unlink()
        except OSError:
            pass

    def test_env_prefixed_launch_execs_and_carries_the_variable(self):
        value = _prefix_value(_resolve("pick", TASK_ID))
        # The prefix exactly as launches build it, in front of a harmless
        # stand-in for the agent binary.
        command = f"{PREFIX}{shlex.quote(value)} sleep 30"
        config = alu.TmuxLaunchConfig(
            session=self.session, window="probe",
            new_session=True, new_window=False)
        pane_pid, error = alu.launch_in_tmux(command, config)
        self.assertIsNone(error)
        self.assertTrue(pane_pid, "launch returned no pane pid")

        cmdline = environ = b""
        for _ in range(50):
            try:
                cmdline = Path(f"/proc/{pane_pid}/cmdline").read_bytes()
                environ = Path(f"/proc/{pane_pid}/environ").read_bytes()
            except OSError:
                cmdline = environ = b""
            if cmdline.split(b"\0")[0].endswith(b"sleep"):
                break
            time.sleep(0.1)
        argv0 = os.path.basename(cmdline.split(b"\0")[0].decode())
        self.assertEqual("sleep", argv0,
                         "pane pid is not the launched command: the prefix "
                         "did not exec, so a lock would outlive its agent")
        self.assertIn(f"AITASK_AGENT_STRING={value}".encode(),
                      environ.split(b"\0"))


if __name__ == "__main__":
    unittest.main()
