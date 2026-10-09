"""Session → project-root resolution (t1922).

One pane whose cwd wandered into another aitasks repo used to re-root the whole
tmux session: discovery took the FIRST pane that walked up to a project, and
read the explicit registration only when no pane resolved. These cases pin the
rule that replaced it, over the pluggable ``run`` / ``read_registry`` seam of
``_collect_live_roots`` and through the sync / checked / async entry points:

1. a valid ``@aitask_project_root`` session stamp is authoritative — no pane
   is consulted;
2. otherwise a pane vote, ties to the smallest realpath, so pane ORDER never
   decides;
3. otherwise the legacy ``AITASKS_PROJECT_<s>`` global, read only then.

Run: python3 tests/test_session_root_resolution.py
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


def _project(tmp: Path, name: str) -> Path:
    root = tmp / name
    (root / "aitasks" / "metadata").mkdir(parents=True)
    (root / "aitasks" / "metadata" / "project_config.yaml").write_text("x: 1\n")
    return root


class _Server:
    """A fake tmux server: sessions with an optional stamp, panes, legacy globals.

    Records every call so tests can assert which queries a rule may skip.
    """

    def __init__(self, sessions, panes=None, legacy=None):
        self.sessions = sessions          # [(name, stamp_value)]
        self.panes = panes or {}          # name -> [path]
        self.legacy = legacy or {}        # name -> root str
        self.calls = []

    def _answer(self, args):
        self.calls.append(tuple(args))
        cmd = args[0]
        if cmd == "list-sessions":
            fmt = args[args.index("-F") + 1]
            assert fmt == alu._SESSION_LIST_FORMAT, fmt
            body = "".join(f"{n}\t{v}\n" for n, v in self.sessions)
            return TmuxResult("ok", 0, body, "")
        if cmd == "list-panes":
            session = args[args.index("-t") + 1].lstrip("=").rstrip(":")
            body = "".join(p + "\n" for p in self.panes.get(session, []))
            return TmuxResult("ok", 0, body, "")
        if cmd == "show-environment":
            var = args[-1]
            session = var.replace("AITASKS_PROJECT_", "")
            if session in self.legacy:
                return TmuxResult("ok", 0, f"{var}={self.legacy[session]}\n", "")
            return TmuxResult("failed", 1, "", f"unknown variable: {var}\n")
        raise AssertionError(f"unexpected tmux call {args}")

    # the gateway surface the three discovery entry points use
    def run(self, args, timeout=5.0):
        r = self._answer(args)
        return (r.rc, r.stdout)

    def run_checked(self, args, timeout=5.0):
        return self._answer(args)

    async def run_async(self, args, timeout=5.0):
        r = self._answer(args)
        return (r.rc, r.stdout)

    def cmds(self, name):
        return [c for c in self.calls if c[0] == name]


class _Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.a = _project(self.tmp, "repo_a")
        self.b = _project(self.tmp, "repo_b")
        self.plain = self.tmp / "plain"
        self.plain.mkdir()
        self._saved = alu._TMUX
        self._saved_index = os.environ.get("AITASKS_PROJECTS_INDEX")
        os.environ["AITASKS_PROJECTS_INDEX"] = str(self.tmp / "none.yaml")

    def tearDown(self):
        alu._TMUX = self._saved
        if self._saved_index is None:
            os.environ.pop("AITASKS_PROJECTS_INDEX", None)
        else:
            os.environ["AITASKS_PROJECTS_INDEX"] = self._saved_index
        self._td.cleanup()

    # -- helpers ---------------------------------------------------------

    def _seam(self, server):
        """``_collect_live_roots`` over the bare seam, as {session: realpath}."""
        def read_registry(session):
            rc, out = server.run(["show-environment", "-g", f"AITASKS_PROJECT_{session}"])
            return alu._registry_entry_from_output(out) if rc == 0 else None
        roots = alu._collect_live_roots(server.run, read_registry)
        return {s: os.path.realpath(p) for s, p in roots}

    def _everywhere(self, server):
        """{session: realpath} from sync, checked and async discovery — all equal."""
        alu._TMUX = server
        sync = {s.session: os.path.realpath(s.project_root)
                for s in alu.discover_aitasks_sessions()}
        checked, complete = alu.discover_aitasks_sessions_checked()
        checked = {s.session: os.path.realpath(s.project_root) for s in checked}
        async_ = {s.session: os.path.realpath(s.project_root)
                  for s in asyncio.run(alu.discover_aitasks_sessions_async())}
        self.assertEqual(sync, checked, "checked differs from sync")
        self.assertEqual(sync, async_, "async differs from sync")
        self.assertTrue(complete)
        return sync

    def R(self, p):
        return os.path.realpath(p)


class ResolutionTests(_Base):
    # -- rule 1: the stamp is authoritative --------------------------------

    def test_stamp_beats_one_wandering_pane(self):
        """The task's regression: registered A, one pane in B listed FIRST."""
        server = _Server([("s", str(self.a))],
                         {"s": [str(self.b), str(self.a), str(self.a)]})
        self.assertEqual(self._seam(server), {"s": self.R(self.a)})
        self.assertEqual(self._everywhere(server), {"s": self.R(self.a)})

    def test_stamp_beats_every_pane(self):
        """Registration is ownership: even with every pane elsewhere it holds."""
        server = _Server([("s", str(self.a))], {"s": [str(self.b), str(self.b)]})
        self.assertEqual(self._everywhere(server), {"s": self.R(self.a)})

    def test_stamped_session_issues_no_further_query(self):
        server = _Server([("s", str(self.a))], {"s": [str(self.b)]},
                         legacy={"s": str(self.b)})
        self._everywhere(server)
        self.assertEqual(server.cmds("list-panes"), [])
        self.assertEqual(server.cmds("show-environment"), [])

    def test_stamp_with_trailing_whitespace_is_kept_exactly(self):
        """A project path may end in whitespace; stripping it would void the
        stamp and hand the session back to the pane vote."""
        ws = _project(self.tmp, "repo_ws ")
        server = _Server([("s", str(ws))], {"s": [str(self.b), str(self.b)]})
        self.assertEqual(self._everywhere(server), {"s": self.R(ws)})

    def test_stamp_without_marker_falls_to_the_vote(self):
        server = _Server([("s", str(self.plain))], {"s": [str(self.b)]})
        self.assertEqual(self._everywhere(server), {"s": self.R(self.b)})

    # -- rule 2: the pane vote --------------------------------------------

    def test_pane_order_never_decides(self):
        first = _Server([("s", "")], {"s": [str(self.b), str(self.a), str(self.a)]})
        last = _Server([("s", "")], {"s": [str(self.a), str(self.a), str(self.b)]})
        self.assertEqual(self._everywhere(first), {"s": self.R(self.a)})
        self.assertEqual(self._everywhere(last), {"s": self.R(self.a)})

    def test_majority_wins(self):
        server = _Server([("s", "")], {"s": [str(self.b)] + [str(self.a)] * 3})
        self.assertEqual(self._everywhere(server), {"s": self.R(self.a)})

    def test_tie_goes_to_smallest_realpath_in_both_orders(self):
        want = min(self.R(self.a), self.R(self.b))
        ab = _Server([("s", "")], {"s": [str(self.a), str(self.b)]})
        ba = _Server([("s", "")], {"s": [str(self.b), str(self.a)]})
        self.assertEqual(self._everywhere(ab), {"s": want})
        self.assertEqual(self._everywhere(ba), {"s": want})

    def test_subdirectories_vote_for_their_project(self):
        server = _Server([("s", "")], {"s": [
            str(self.b), str(self.a / "aitasks"), str(self.a / "aitasks" / "metadata")]})
        self.assertEqual(self._everywhere(server), {"s": self.R(self.a)})

    def test_unanimous_panes_skip_the_legacy_read(self):
        server = _Server([("s", "")], {"s": [str(self.a)]}, legacy={"s": str(self.b)})
        self.assertEqual(self._everywhere(server), {"s": self.R(self.a)})
        self.assertEqual(server.cmds("show-environment"), [])

    # -- rule 3: the legacy global ----------------------------------------

    def test_legacy_global_only_when_no_pane_resolves(self):
        server = _Server([("s", "")], {"s": [str(self.plain)]},
                         legacy={"s": str(self.b)})
        self.assertEqual(self._everywhere(server), {"s": self.R(self.b)})

    def test_invalid_legacy_global_excludes_the_session(self):
        server = _Server([("s", ""), ("t", "")],
                         {"s": [str(self.plain)], "t": [str(self.a)]},
                         legacy={"s": str(self.plain)})
        self.assertEqual(self._everywhere(server), {"t": self.R(self.a)})

    # -- parsing ----------------------------------------------------------

    def test_bare_names_parse_as_unregistered(self):
        self.assertEqual(alu._parse_session_list("s1\ns2\t\ns3\t/x\t/y\n"),
                         [("s1", ""), ("s2", ""), ("s3", "/x\t/y")])


class AttributionTests(_Base):
    """``unregistered_session_attribution`` — the bash claim's ownership evidence."""

    def test_attribution_ignores_the_stamp_and_votes(self):
        server = _Server([("s", str(self.b))], {"s": [str(self.a), str(self.a), str(self.b)]})
        alu._TMUX = server
        root, complete = alu.unregistered_session_attribution("s")
        self.assertEqual(self.R(root), self.R(self.a))
        self.assertTrue(complete)

    def test_attribution_falls_to_the_legacy_global(self):
        server = _Server([("s", "")], {"s": [str(self.plain)]}, legacy={"s": str(self.a)})
        alu._TMUX = server
        root, complete = alu.unregistered_session_attribution("s")
        self.assertEqual(self.R(root), self.R(self.a))
        self.assertTrue(complete)

    def test_attribution_nothing_resolves(self):
        server = _Server([("s", "")], {"s": [str(self.plain)]})
        alu._TMUX = server
        self.assertEqual(alu.unregistered_session_attribution("s"), (None, True))

    def test_attribution_failed_pane_read_is_incomplete(self):
        server = _Server([("s", "")], legacy={"s": str(self.a)})
        orig = server._answer

        def answer(args):
            if args[0] == "list-panes":
                server.calls.append(tuple(args))
                return TmuxResult("failed", 1, "", "server exited unexpectedly\n")
            return orig(args)
        server._answer = answer
        alu._TMUX = server
        _root, complete = alu.unregistered_session_attribution("s")
        self.assertFalse(complete)

    def test_attribution_failed_legacy_read_is_incomplete(self):
        server = _Server([("s", "")], {"s": [str(self.plain)]})
        orig = server._answer

        def answer(args):
            if args[0] == "show-environment":
                server.calls.append(tuple(args))
                return TmuxResult("failed", 1, "", "lost server\n")
            return orig(args)
        server._answer = answer
        alu._TMUX = server
        self.assertEqual(alu.unregistered_session_attribution("s"), (None, False))


if __name__ == "__main__":
    unittest.main()
