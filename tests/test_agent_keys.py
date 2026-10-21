"""Unit test for the canonical pane→agent resolver (t1467).

Covers `lib/agent_keys.py`:
  1. Rung 1 — the pane's tmux command, exact-match only.
  2. Rung 2 — the pane process's OWN comm (t2096): a native Claude install is a
     symlink to a version-named binary, so tmux reports `2.1.306` while `ps`
     reports the invoked name `claude`. Tested against a real symlink.
  3. Rung 3 — one level of child processes, against a REAL process tree rather
     than a mock, because the thing under test is precisely whether the
     pgrep/ps pair reads a real tree correctly. Not reached when an earlier
     rung already answered.
  4. Ambiguity (children resolving to different agents) suppresses to "".
  5. Depth is bounded at one level — a grandchild does not resolve.
  6. Every failure path (no pgrep on PATH, no children) returns "".
  7. Positive results are cached: each subprocess runs once per (pane_pid, cmd),
     and the own-comm lookup sits behind the caches like the child lookup.
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
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

import agent_keys as ak  # noqa: E402
from fake_agent_binary import (  # noqa: E402
    FakeAgentBinaryUnavailable, fake_agent_binary)


def _fake_agent_binary(tmpdir: str, name: str) -> str:
    """An executable named `name`, so its `comm` IS `name`.

    `allow_symlink=True`: this module reads the process name through
    `ps -o comm=` (`agent_keys._child_commands`), which reports the *invoked*
    path, so a symlink's basename is still the agent name. A tmux-based reader
    would not be — see `tests/lib/fake_agent_binary.py`, which also explains why
    the old `shutil.copy2` of `/bin/sleep` cannot work on macOS (t1729).
    """
    return fake_agent_binary(tmpdir, name, allow_symlink=True)


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
        original_own = getattr(ak, "_own_command", None)
        ak._child_commands = lambda pid: (_ for _ in ()).throw(
            AssertionError("the child rung must not run when the command resolves"))
        ak._own_command = lambda pid: (_ for _ in ()).throw(
            AssertionError("the own-comm rung must not run when the command resolves"))
        try:
            self.assertEqual(ak.agent_key_from_pane("codex", 12345), "codex")
        finally:
            ak._child_commands = original
            ak._own_command = original_own


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


class OwnCommandRungTest(unittest.TestCase):
    """Rung 2: the pane process's own comm (t2096).

    The measured shape: a native Claude install links `~/.local/bin/claude` to
    `~/.local/share/claude/versions/2.1.306`. tmux names the RESOLVED executable
    (`2.1.306`), `ps -o comm=` the INVOKED path (`claude`), and the agent has no
    agent-named child — so neither the command nor the child rung resolves it.
    """

    def setUp(self):
        ak._PANE_KEY_CACHE.clear()
        ak._PANE_MISS_CACHE.clear()
        self.original_children = ak._child_commands
        self.original_own = getattr(ak, "_own_command", None)
        self.tmp = tempfile.mkdtemp(prefix="t2096-owncomm-")
        self.procs: list[subprocess.Popen] = []

    def tearDown(self):
        ak._child_commands = self.original_children
        ak._own_command = self.original_own
        ak._PANE_KEY_CACHE.clear()
        ak._PANE_MISS_CACHE.clear()
        for proc in self.procs:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _stub(self, own: str, children: list[str] | None = None) -> None:
        ak._own_command = lambda pid: own
        if children is None:
            ak._child_commands = lambda pid: (_ for _ in ()).throw(
                AssertionError("children must not be consulted"))
        else:
            ak._child_commands = lambda pid: list(children)

    def _spawn(self, path: str) -> int:
        proc = subprocess.Popen([path, "30"], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        self.procs.append(proc)
        return proc.pid

    def test_version_string_command_with_claude_comm_resolves(self):
        """THE regression: tmux says `2.1.306`, the process is `claude`."""
        self._stub("claude", children=[])
        self.assertEqual(ak.agent_key_from_pane("2.1.306", 4242, "%4"), "claude")

    def test_own_comm_outranks_children(self):
        self._stub("claude")   # children stub raises if consulted
        self.assertEqual(ak.agent_key_from_pane("2.1.306", 4242, "%4"), "claude")

    def test_full_path_comm_resolves(self):
        self._stub("/Users/x/.local/bin/claude", children=[])
        self.assertEqual(ak.agent_key_from_pane("2.1.306", 4242, "%4"), "claude")

    def test_unresolved_own_comm_falls_through_to_children(self):
        self._stub("node", children=["codex"])
        self.assertEqual(ak.agent_key_from_pane("node", 4242, "%1"), "codex")
        ak._PANE_KEY_CACHE.clear()
        ak._PANE_MISS_CACHE.clear()
        self._stub("node", children=["codex", "claude"])
        self.assertEqual(ak.agent_key_from_pane("node", 4242, "%2"), "",
                         "ambiguity among children still suppresses")

    def test_real_process_own_comm(self):
        """The real `ps` path, end to end. NOT a symlink test: the helper's
        copy and compile rungs come before its opt-in symlink fallback."""
        try:
            claude = _fake_agent_binary(self.tmp, "claude")
        except FakeAgentBinaryUnavailable as exc:
            self.skipTest(f"no runnable agent-named binary: {exc}")
        pid = self._spawn(claude)
        self.assertEqual(ak.agent_key_from_pane("2.1.306", pid, "%r"), "claude")

    def test_real_symlink_invoked_name_resolves(self):
        """The production shape: an agent-named SYMLINK to a version-named
        binary. `ps` must report the invoked name, not the target's."""
        try:
            target = fake_agent_binary(self.tmp, "2.1.306")
        except FakeAgentBinaryUnavailable as exc:
            self.skipTest(f"no runnable binary: {exc}")
        self.assertFalse(os.path.islink(target), "premise: the target is a file")
        os.makedirs(os.path.join(self.tmp, "bin"))
        link = os.path.join(self.tmp, "bin", "claude")
        os.symlink(target, link)
        self.assertTrue(os.path.islink(link), "premise: launched through a symlink")
        pid = self._spawn(link)
        deadline = time.monotonic() + 5.0
        comm = ""
        while time.monotonic() < deadline:
            comm = ak._own_command(pid)
            if comm:
                break
            time.sleep(0.05)
        self.assertEqual(os.path.basename(comm), "claude",
                         f"ps should report the invoked name, got {comm!r}")
        self.assertEqual(ak.agent_key_from_pane("2.1.306", pid, "%t"), "claude")

    def test_own_comm_missing_ps_returns_empty(self):
        saved = os.environ.get("PATH", "")
        os.environ["PATH"] = ""
        try:
            self.assertEqual(ak._own_command(os.getpid()), "")
        finally:
            os.environ["PATH"] = saved

    def test_own_comm_no_pid_returns_empty(self):
        self.assertEqual(ak._own_command(0), "")
        self.assertEqual(ak._own_command(-1), "")


class CacheTest(unittest.TestCase):
    """The lookup sits on the per-tick refresh path; once per pane, not per tick."""

    def setUp(self):
        ak._PANE_KEY_CACHE.clear()
        ak._PANE_MISS_CACHE.clear()
        self.calls = 0
        self.original = ak._child_commands
        self.original_own = getattr(ak, "_own_command", None)

        def counting(pid):
            self.calls += 1
            return ["codex"]

        ak._child_commands = counting
        # Fake pids are real pids on the host: without this stub the own-comm
        # rung would `ps` whatever process holds 4242 — possibly a real claude.
        self.own = ""
        self.own_calls = 0

        def counting_own(pid):
            self.own_calls += 1
            return self.own

        ak._own_command = counting_own

    def tearDown(self):
        ak._child_commands = self.original
        ak._own_command = self.original_own
        ak._PANE_KEY_CACHE.clear()
        ak._PANE_MISS_CACHE.clear()

    def test_repeated_calls_hit_the_cache(self):
        for _ in range(10):
            self.assertEqual(ak.agent_key_from_pane("node", 4242, "%1"), "codex")
        self.assertEqual(self.calls, 1,
                         f"expected exactly one lookup, got {self.calls}")
        self.assertEqual(self.own_calls, 1,
                         f"expected exactly one own-comm lookup, got {self.own_calls}")

    def test_own_comm_positive_hit_is_looked_up_once(self):
        """The own-comm rung sits BEHIND the positive cache (t2096): placed
        before it, every refresh tick would run a `ps`."""
        self.own = "claude"
        for _ in range(10):
            self.assertEqual(ak.agent_key_from_pane("2.1.306", 4243, "%3"),
                             "claude")
        self.assertEqual(self.own_calls, 1,
                         f"expected exactly one own-comm lookup, got {self.own_calls}")
        self.assertEqual(self.calls, 0,
                         "children must not be consulted once own comm answers")

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
        self.original_own = getattr(ak, "_own_command", None)
        self.own = ""
        self.own_calls = 0

        def scripted_own(pid):
            self.own_calls += 1
            return self.own

        ak._own_command = scripted_own

    def tearDown(self):
        ak._child_commands = self.original
        ak._own_command = self.original_own
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
        own_before = self.own_calls
        self.clock[0] += 10_000
        for _ in range(5):
            self.assertEqual(ak.agent_key_from_pane("node", 778), "codex")
        self.assertEqual(self.calls, before,
                         "a positive answer must be cached for the pane's life")
        self.assertEqual(self.own_calls, own_before,
                         "the own-comm rung must not re-run on a cached hit")

    def test_backoff_bounds_the_lookup_rate(self):
        """A genuinely agent-less pane must not run a subprocess every tick."""
        for _ in range(20):
            self.clock[0] += 0.1          # ~20 ticks inside the first step
            ak.agent_key_from_pane("python", 779)
        self.assertLessEqual(self.calls, 3,
                             f"expected the backoff to bound lookups, got {self.calls}")
        self.assertLessEqual(self.own_calls, 3,
                             f"expected the backoff to bound own-comm lookups, "
                             f"got {self.own_calls}")
        self.assertEqual(self.own_calls, self.calls,
                         "the miss backoff must gate both pid-driven rungs equally")

    def test_own_comm_miss_inside_retry_interval_is_not_re_looked_up(self):
        self.assertEqual(ak.agent_key_from_pane("2.1.306", 781), "")
        for _ in range(5):
            self.clock[0] += ak._MISS_RETRY_SCHEDULE[0] / 10
            self.assertEqual(ak.agent_key_from_pane("2.1.306", 781), "")
        self.assertEqual(self.own_calls, 1,
                         f"a miss inside the retry interval must not re-run ps, "
                         f"got {self.own_calls}")
        self.own = "claude"
        self.clock[0] += ak._MISS_RETRY_SCHEDULE[0] + 0.01
        self.assertEqual(ak.agent_key_from_pane("2.1.306", 781), "claude")
        self.assertEqual(self.own_calls, 2)

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
