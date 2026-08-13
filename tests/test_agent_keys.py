"""Unit test for the canonical pane→agent resolver (t1467).

Covers `lib/agent_keys.py`:
  1. Rung 1 — the pane's own command, exact-match only.
  2. Rung 2 — one level of child processes, against a REAL process tree rather
     than a mock, because the thing under test is precisely whether the
     pgrep/ps pair reads a real tree correctly.
  3. Rung 2 is not reached when rung 1 already answered.
  4. Ambiguity (children resolving to different agents) suppresses to "".
  5. Depth is bounded at one level — a grandchild does not resolve.
  6. Every failure path (no pgrep on PATH, no children) returns "".
  7. Positive results are cached: the subprocess runs once per (pane_pid, cmd).
  8. NEGATIVE results are only provisional — the wrapper's child appears
     asynchronously, so a first empty lookup must not pin the pane to "" for
     its lifetime. Retried on a backoff, with a terminal interval forever.

Run:
  python3 tests/test_agent_keys.py
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts" / "lib"))

import agent_keys as ak  # noqa: E402


def _fake_agent_binary(tmpdir: str, name: str) -> str:
    """A copy of /bin/sleep named `name`, so its `comm` IS `name`.

    A copy rather than a symlink: `ps -o comm=` reports the executable's name,
    and a symlink would report the target's on some platforms.
    """
    dest = os.path.join(tmpdir, name)
    shutil.copy2(shutil.which("sleep") or "/bin/sleep", dest)
    os.chmod(dest, 0o755)
    return dest


class _Tree:
    """A live `sh` parent with controlled children; the sh pid plays pane_pid."""

    def __init__(self, script: str, *args: str):
        self.proc = subprocess.Popen(
            ["sh", "-c", script, "sh", *args],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Give sh time to fork its children before anything inspects the tree.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if ak._child_commands(self.proc.pid):
                break
            time.sleep(0.05)

    @property
    def pid(self) -> int:
        return self.proc.pid

    def close(self) -> None:
        try:
            self.proc.kill()
            self.proc.wait(timeout=5)
        except Exception:
            pass


class RungOneTest(unittest.TestCase):
    def setUp(self):
        ak._PANE_KEY_CACHE.clear()
        ak._PANE_MISS_CACHE.clear()

    def test_known_commands_resolve(self):
        for cmd in ("claude", "codex", "opencode"):
            self.assertEqual(ak.agent_key_from_command(cmd), cmd)
        self.assertEqual(ak.agent_key_from_command("/usr/bin/claude"), "claude")
        self.assertEqual(ak.agent_key_from_command("  CLAUDE "), "claude")

    def test_unknown_commands_do_not_resolve(self):
        for cmd in ("node", "python", "bash", "", "   ", "claude-something-else",
                    "all"):
            self.assertEqual(ak.agent_key_from_command(cmd), "",
                             f"{cmd!r} must not resolve")

    def test_rung_two_is_not_reached_when_rung_one_answers(self):
        """Proven by making rung 2 explode: if it were consulted, this raises."""
        original = ak._child_commands
        ak._child_commands = lambda pid: (_ for _ in ()).throw(
            AssertionError("rung 2 must not run when the command resolves"))
        try:
            self.assertEqual(ak.agent_key_from_pane("codex", 12345), "codex")
        finally:
            ak._child_commands = original


class RungTwoTest(unittest.TestCase):
    """Against real process trees — the measured `node` → `codex` shape."""

    def setUp(self):
        ak._PANE_KEY_CACHE.clear()
        ak._PANE_MISS_CACHE.clear()
        self.tmp = tempfile.mkdtemp(prefix="t1467-agentkeys-")
        self.trees: list[_Tree] = []

    def tearDown(self):
        for tree in self.trees:
            tree.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _tree(self, script: str, *args: str) -> _Tree:
        tree = _Tree(script, *args)
        self.trees.append(tree)
        return tree

    def test_child_named_agent_resolves(self):
        codex = _fake_agent_binary(self.tmp, "codex")
        tree = self._tree('"$1" 30 & wait', codex)
        self.assertEqual(ak.agent_key_from_pane("node", tree.pid), "codex")

    def test_two_distinct_agents_suppress(self):
        codex = _fake_agent_binary(self.tmp, "codex")
        claude = _fake_agent_binary(self.tmp, "claude")
        tree = self._tree('"$1" 30 & "$2" 30 & wait', codex, claude)
        self.assertEqual(ak.agent_key_from_pane("node", tree.pid), "",
                         "two different agents among the children is ambiguous")

    def test_two_children_of_the_same_agent_resolve(self):
        """Several children of ONE agent is not ambiguity about identity."""
        codex = _fake_agent_binary(self.tmp, "codex")
        tree = self._tree('"$1" 30 & "$1" 30 & wait', codex)
        self.assertEqual(ak.agent_key_from_pane("node", tree.pid), "codex")

    def test_grandchild_does_not_resolve(self):
        """Depth is bounded at one: a real Codex runs codex-code-mode-host at
        depth 2, so a deeper walk would resolve a pane to what it spawned."""
        codex = _fake_agent_binary(self.tmp, "codex")
        tree = self._tree('sh -c \'"$1" 30 & wait\' sh "$1" & wait', codex)
        self.assertEqual(ak.agent_key_from_pane("node", tree.pid), "")

    def test_no_children_returns_empty(self):
        tree = self._tree('sleep 30')
        # `sh -c 'sleep 30'` usually execs directly, so there may be no child at
        # all; either way nothing resolves.
        self.assertEqual(ak.agent_key_from_pane("node", tree.pid), "")

    def test_missing_pgrep_returns_empty(self):
        """Driven through a real empty PATH, not a mock, so the actual
        `shutil.which` failure path is the one exercised."""
        codex = _fake_agent_binary(self.tmp, "codex")
        tree = self._tree('"$1" 30 & wait', codex)
        saved = os.environ.get("PATH", "")
        os.environ["PATH"] = ""
        try:
            ak._PANE_KEY_CACHE.clear()
            self.assertEqual(ak.agent_key_from_pane("node", tree.pid), "")
        finally:
            os.environ["PATH"] = saved

    def test_no_pane_pid_returns_empty(self):
        self.assertEqual(ak.agent_key_from_pane("node", None), "")
        self.assertEqual(ak.agent_key_from_pane("node", 0), "")


class CacheTest(unittest.TestCase):
    """The lookup sits on the per-tick refresh path; once per pane, not per tick."""

    def setUp(self):
        ak._PANE_KEY_CACHE.clear()
        ak._PANE_MISS_CACHE.clear()
        self.calls = 0
        self.original = ak._child_commands

        def counting(pid):
            self.calls += 1
            return ["codex"]

        ak._child_commands = counting

    def tearDown(self):
        ak._child_commands = self.original
        ak._PANE_KEY_CACHE.clear()
        ak._PANE_MISS_CACHE.clear()

    def test_repeated_calls_hit_the_cache(self):
        for _ in range(10):
            self.assertEqual(ak.agent_key_from_pane("node", 4242, "%1"), "codex")
        self.assertEqual(self.calls, 1,
                         f"expected exactly one lookup, got {self.calls}")

    def test_a_recycled_pid_does_not_inherit_the_dead_pane_answer(self):
        """pane_id is part of the cache identity (t1467 review).

        The OS recycles pids, and the recycled process is very often the SAME
        command — `node` is both the most common thing to find at a reused pid
        and exactly the command that reaches rung 2. Keyed on pid+command alone,
        a brand-new pane would inherit the dead one's `codex` answer and have
        its prompt matching scoped to the wrong agent, with no child check to
        correct it. Fails against a build that omits pane_id from the key.
        """
        self.assertEqual(ak.agent_key_from_pane("node", 5150, "%1"), "codex")
        first_calls = self.calls

        # Same pid, same command, DIFFERENT pane: must re-resolve, not inherit.
        ak._child_commands = lambda pid: ["python"]
        self.assertEqual(ak.agent_key_from_pane("node", 5150, "%2"), "",
                         "a different pane must not inherit the cached answer")
        self.assertGreater(self.calls if hasattr(self, "calls") else 0,
                           first_calls - 1)

    def test_same_pane_still_hits_the_cache(self):
        """The counterpart: adding pane_id must not defeat caching."""
        for _ in range(5):
            self.assertEqual(ak.agent_key_from_pane("node", 5151, "%7"), "codex")
        self.assertEqual(self.calls, 1)

    def test_a_changed_command_re_resolves(self):
        """The cache key includes the command, so a recycled pid running
        something else cannot inherit the dead pane's answer."""
        ak.agent_key_from_pane("node", 4242, "%1")
        ak.agent_key_from_pane("bun", 4242, "%1")
        self.assertEqual(self.calls, 2)


class NegativeCacheRetryTest(unittest.TestCase):
    """A miss is provisional; a hit is not (t1467 review).

    The wrapper shape starts asynchronously — this file's own `_Tree` fixture has
    to POLL for the child to appear — so a monitor tick can land between the
    pane's exec and its child's. Caching that "" like a positive would pin the
    pane to ledger-only for its whole lifetime and quietly defeat rung 2.
    """

    def setUp(self):
        ak._PANE_KEY_CACHE.clear()
        ak._PANE_MISS_CACHE.clear()
        self.original = ak._child_commands
        self.original_now = ak._now
        self.clock = [1000.0]
        ak._now = lambda: self.clock[0]
        self.children: list[str] = []
        self.calls = 0

        def scripted(pid):
            self.calls += 1
            return list(self.children)

        ak._child_commands = scripted

    def tearDown(self):
        ak._child_commands = self.original
        ak._now = self.original_now
        ak._PANE_KEY_CACHE.clear()
        ak._PANE_MISS_CACHE.clear()

    def test_empty_first_lookup_then_child_appears(self):
        """THE case: first tick sees no children, a later tick sees codex."""
        self.assertEqual(ak.agent_key_from_pane("node", 777), "")
        # The child has now started.
        self.children = ["codex"]
        # Still inside the first backoff step — cheap, and still honest.
        self.assertEqual(ak.agent_key_from_pane("node", 777), "")
        # After the backoff, the retry finds it.
        self.clock[0] += ak._MISS_RETRY_SCHEDULE[0] + 0.01
        self.assertEqual(ak.agent_key_from_pane("node", 777), "codex",
                         "a provisional miss must be retried, not pinned")

    def test_a_resolved_pane_is_never_re_looked_up(self):
        self.children = ["codex"]
        self.assertEqual(ak.agent_key_from_pane("node", 778), "codex")
        before = self.calls
        self.clock[0] += 10_000
        for _ in range(5):
            self.assertEqual(ak.agent_key_from_pane("node", 778), "codex")
        self.assertEqual(self.calls, before,
                         "a positive answer must be cached for the pane's life")

    def test_backoff_bounds_the_lookup_rate(self):
        """A genuinely agent-less pane must not run a subprocess every tick."""
        for _ in range(20):
            self.clock[0] += 0.1          # ~20 ticks inside the first step
            ak.agent_key_from_pane("python", 779)
        self.assertLessEqual(self.calls, 3,
                             f"expected the backoff to bound lookups, got {self.calls}")

    def test_retries_continue_forever_at_the_terminal_interval(self):
        """The terminal step is load-bearing: a budget that STOPS would
        permanently poison a pane whose miss outlived it."""
        for _ in range(len(ak._MISS_RETRY_SCHEDULE) + 2):
            self.clock[0] += ak._MISS_RETRY_TERMINAL + 1
            ak.agent_key_from_pane("node", 780)
        calls_so_far = self.calls
        self.children = ["codex"]
        self.clock[0] += ak._MISS_RETRY_TERMINAL + 1
        self.assertEqual(ak.agent_key_from_pane("node", 780), "codex")
        self.assertGreater(self.calls, calls_so_far)


if __name__ == "__main__":
    unittest.main()
