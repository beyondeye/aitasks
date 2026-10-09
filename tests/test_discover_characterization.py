"""Characterization of session→project-root discovery (t1922 pre-phase).

Pins the ``(session, project_root)`` answer of the three discovery entry points
— sync, async and checked — for the session shapes whose outcome t1922 must NOT
change:

* every pane walks up to one project;
* no pane resolves, the legacy ``AITASKS_PROJECT_<s>`` global names a project;
* nothing resolves at all (the session is excluded).

The fake answers ``list-sessions`` whatever its ``-F`` format string and keys
everything else on the subcommand, so this file pins RESULTS, never the tmux
call sequence — it must stay green, unchanged, across the resolver rewrite.

Run: python3 tests/test_discover_characterization.py
"""
import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".aitask-scripts", "lib"))

import agent_launch_utils as alu  # noqa: E402
from tmux_exec import TmuxResult  # noqa: E402


class _FakeTmux:
    """Answers by subcommand: sessions, per-session pane paths, legacy globals."""

    def __init__(self, sessions, panes, env):
        self.sessions = sessions        # [name]
        self.panes = panes              # name -> [path]
        self.env = env                  # name -> root str

    def _answer(self, args):
        cmd = args[0]
        if cmd == "list-sessions":
            return TmuxResult("ok", 0, "".join(s + "\n" for s in self.sessions), "")
        if cmd == "list-panes":
            session = args[args.index("-t") + 1].lstrip("=").rstrip(":")
            paths = self.panes.get(session, [])
            return TmuxResult("ok", 0, "".join(p + "\n" for p in paths), "")
        if cmd == "show-environment":
            var = args[-1]
            session = var.replace("AITASKS_PROJECT_", "")
            if session in self.env:
                return TmuxResult("ok", 0, f"{var}={self.env[session]}\n", "")
            return TmuxResult("failed", 1, "", f"unknown variable: {var}\n")
        raise AssertionError(f"unexpected tmux call {args}")

    def run(self, args, timeout=5.0):
        r = self._answer(args)
        return (r.rc, r.stdout)

    def run_checked(self, args, timeout=5.0):
        return self._answer(args)

    async def run_async(self, args, timeout=5.0):
        r = self._answer(args)
        return (r.rc, r.stdout)

    async def run_checked_async(self, args, timeout=5.0):
        return self._answer(args)


def _project(tmp: Path, name: str) -> Path:
    root = tmp / name
    (root / "aitasks" / "metadata").mkdir(parents=True)
    (root / "aitasks" / "metadata" / "project_config.yaml").write_text("x: 1\n")
    return root


class DiscoveryCharacterization(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.alpha = _project(self.tmp, "alpha")
        self.beta = _project(self.tmp, "beta")
        (self.tmp / "plain").mkdir()
        self._saved = alu._TMUX
        self._saved_index = os.environ.pop("AITASKS_PROJECTS_INDEX", None)
        os.environ["AITASKS_PROJECTS_INDEX"] = str(self.tmp / "no_registry.yaml")

    def tearDown(self):
        alu._TMUX = self._saved
        os.environ.pop("AITASKS_PROJECTS_INDEX", None)
        if self._saved_index is not None:
            os.environ["AITASKS_PROJECTS_INDEX"] = self._saved_index
        self._td.cleanup()

    def _all_three(self, fake):
        alu._TMUX = fake
        sync = alu.discover_aitasks_sessions()
        async_ = asyncio.run(alu.discover_aitasks_sessions_async())
        checked, complete = alu.discover_aitasks_sessions_checked()
        return sync, async_, checked, complete

    @staticmethod
    def _pairs(sessions):
        return [(s.session, os.path.realpath(s.project_root)) for s in sessions]

    def _assert_everywhere(self, fake, expected):
        sync, async_, checked, complete = self._all_three(fake)
        want = [(s, os.path.realpath(p)) for s, p in expected]
        self.assertEqual(self._pairs(sync), want, "sync")
        self.assertEqual(self._pairs(async_), want, "async")
        self.assertEqual(self._pairs(checked), want, "checked")
        self.assertTrue(complete, "checked discovery must be complete")

    def test_unanimous_panes(self):
        fake = _FakeTmux(
            ["s1"],
            {"s1": [str(self.alpha), str(self.alpha / "aitasks"), str(self.alpha)]},
            {},
        )
        self._assert_everywhere(fake, [("s1", self.alpha)])

    def test_registry_only(self):
        fake = _FakeTmux(
            ["s1"], {"s1": [str(self.tmp / "plain")]}, {"s1": str(self.beta)})
        self._assert_everywhere(fake, [("s1", self.beta)])

    def test_no_match_is_excluded(self):
        fake = _FakeTmux(
            ["s1", "s2"],
            {"s1": [str(self.tmp / "plain")], "s2": [str(self.alpha)]},
            {"s1": str(self.tmp / "plain")},
        )
        self._assert_everywhere(fake, [("s2", self.alpha)])

    def test_two_unanimous_sessions_sorted(self):
        fake = _FakeTmux(
            ["zz", "aa"],
            {"zz": [str(self.alpha)], "aa": [str(self.beta)]},
            {},
        )
        self._assert_everywhere(fake, [("aa", self.beta), ("zz", self.alpha)])


if __name__ == "__main__":
    unittest.main()
