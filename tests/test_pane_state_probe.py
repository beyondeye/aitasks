"""Unit tests for lib/pane_state_probe.py (t1725_4).

The probe answers the sync sweep's "is this holder parked on a prompt?" question
and gates `aitask_sync.sh --require-waiting`. Covered here, with no tmux server:

  1. The classifier: an AskUserQuestion screen is `waiting_claude_askuserquestion`,
     ordinary output is `active`.
  2. Scoping is live, not vacuous: the same `opencode_palette` body answers
     `active` on a `claude` pane and `waiting_opencode_palette` on an unresolved
     one. A probe that ignored the agent would give the second answer both times.
  3. Failure is `""` and never an exception: a failed display-message or
     capture-pane, and a malformed pane id, which makes ZERO tmux calls.
  4. The write-site grammar check: a registry pattern named outside
     `[a-z0-9_]+` yields `""`, never a state the wire parser would reject.
  5. The CLI, run through the shipping file as its own process: one stdout line,
     exit 0, in every case.
  6. The import bootstrap, through that same entry point. Launched from `lib/`,
     only `lib/` is on sys.path, so without the bootstrap `monitor.*` fails to
     import and every answer silently becomes `""`. The pin is an EMPTY stderr
     on a well-formed call. Its negative control runs a lone copy of the probe,
     with no framework beside it, and requires the import error on stderr, so
     the pin is shown to be able to fail.

The live half (a real pane on an isolated server) is
tests/test_sync_holder_pane_live.sh.

Run:
  python3 tests/test_pane_state_probe.py
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / ".aitask-scripts"
PROBE = SCRIPTS / "lib" / "pane_state_probe.py"

sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "lib"))

import pane_state_probe as psp  # noqa: E402
from monitor.prompt_patterns import PromptPattern  # noqa: E402

# The characterization bodies test_prompt_detection.py pins per pattern.
ASK_BODY = "Enter to select · ↑/↓ to navigate · Esc to cancel\n"
PALETTE_BODY = "Commands  esc\n"
PLAIN_BODY = "running the suite...\n  12 passed, 0 failed\n$ \n"
# An absent pid, so agent resolution never lands on a real process's children.
NO_PID = "999999"


class StubClient:
    """Scripted TmuxClient stand-in: one (rc, stdout) per tmux verb."""

    def __init__(self, responses: dict[str, tuple[int, str]]):
        self.responses = responses
        self.calls: list[list[str]] = []

    def run(self, args, timeout=5.0):
        self.calls.append(list(args))
        return self.responses.get(args[0], (1, ""))


def _pane(command: str, body: str) -> StubClient:
    return StubClient({
        "display-message": (0, f"{command}\t{NO_PID}\n"),
        "capture-pane": (0, body),
    })


class ClassifierTests(unittest.TestCase):
    def test_askuserquestion_is_waiting(self):
        c = _pane("claude", "some transcript\n" + ASK_BODY)
        self.assertEqual(psp.probe("%5", client=c), "waiting_claude_askuserquestion")

    def test_plain_output_is_active(self):
        self.assertEqual(psp.probe("%5", client=_pane("claude", PLAIN_BODY)), "active")

    def test_probe_captures_the_pane_it_was_given(self):
        c = _pane("claude", PLAIN_BODY)
        psp.probe("%17", client=c)
        self.assertEqual([call[0] for call in c.calls], ["display-message", "capture-pane"])
        for call in c.calls:
            self.assertEqual(call[call.index("-t") + 1], "%17")

    def test_scoping_is_live(self):
        # Same body, two agents. `claude` scoping drops opencode's patterns.
        self.assertEqual(psp.classify_text(PALETTE_BODY, "claude"), "active")
        # Unresolved agent: the monitor's unscoped fallback, which matches.
        self.assertEqual(psp.classify_text(PALETTE_BODY, ""), "waiting_opencode_palette")


class FailClosedTests(unittest.TestCase):
    def test_capture_failure_is_empty(self):
        c = StubClient({"display-message": (0, f"claude\t{NO_PID}\n"),
                        "capture-pane": (1, "")})
        self.assertEqual(psp.probe("%5", client=c), "")

    def test_display_failure_is_empty_and_skips_capture(self):
        c = StubClient({"display-message": (1, ""), "capture-pane": (0, ASK_BODY)})
        self.assertEqual(psp.probe("%5", client=c), "")
        self.assertEqual([call[0] for call in c.calls], ["display-message"])

    def test_malformed_ids_make_no_tmux_calls(self):
        for bad in ("aitasks:1.1", "%x", "", "%", "5", "%5 ", "%5\n"):
            with self.subTest(pane_id=bad):
                c = _pane("claude", ASK_BODY)
                self.assertEqual(psp.probe(bad, client=c), "")
                self.assertEqual(c.calls, [])

    def test_out_of_grammar_pattern_name_fails_closed(self):
        bad = [PromptPattern("Bad-Name", re.compile("XYZZY"))]
        with mock.patch.object(psp, "all_patterns", lambda: bad):
            self.assertEqual(psp.classify_text("XYZZY\n", ""), "")
        # Control: the same shape with a grammatical name is answered.
        good = [PromptPattern("good_name", re.compile("XYZZY"))]
        with mock.patch.object(psp, "all_patterns", lambda: good):
            self.assertEqual(psp.classify_text("XYZZY\n", ""), "waiting_good_name")


class CliTests(unittest.TestCase):
    """The shipping file, launched the way aitask_sync.sh launches it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="psp_cli_")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        env = {k: v for k, v in os.environ.items()
               if k not in ("TMUX", "TMUX_PANE", "PYTHONPATH")}
        # A private tmpdir and a socket name nothing serves: the probe can never
        # reach the user's tmux server, and "no server" is the deterministic
        # answer to every well-formed id.
        env["TMUX_TMPDIR"] = self.tmp
        env["AITASKS_TMUX_SOCKET"] = f"ait_psp_nosrv_{os.getpid()}"
        self.env = env

    def _run(self, script: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(script), *args],
            cwd=self.tmp, env=self.env, capture_output=True, text=True, timeout=30,
        )

    def test_one_line_exit_zero_in_every_shape(self):
        for args in (("%1",), (), ("%1", "%2"), ("not-a-pane",)):
            with self.subTest(args=args):
                r = self._run(PROBE, *args)
                self.assertEqual(r.returncode, 0)
                self.assertEqual(r.stdout, "\n")

    def test_bootstrap_imports_resolve_from_outside_the_repo(self):
        # Well-formed id, no server: "" on stdout. That answer alone cannot tell a
        # missing server from a failed import, so the pin is stderr. The imports
        # run at module top, and a failure would be reported here.
        r = self._run(PROBE, "%1")
        self.assertEqual(r.stdout, "\n")
        self.assertEqual(r.stderr, "")

    def test_bootstrap_pin_can_fail(self):
        # Negative control: the same file with no framework beside it.
        lone = Path(self.tmp) / "lib" / "pane_state_probe.py"
        lone.parent.mkdir()
        shutil.copy(PROBE, lone)
        r = self._run(lone, "%1")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "\n")
        self.assertIn("ModuleNotFoundError", r.stderr)


if __name__ == "__main__":
    unittest.main()
