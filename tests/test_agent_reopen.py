"""Unit tests for the reopen coordinator (`lib/agent_reopen.py`, t1847).

No tmux and no real store. Both seams are swapped IN PLACE on the shared module
(``agent_frozen_ops.store`` / ``agent_frozen_ops._TMUX``), as
`tests/test_agent_frozen_ops.py` documents — never import-aliased.

The tmux fake here is a small STATEFUL world (panes, windows, pane options)
that evaluates the ``if-shell -F '#{==:#{X},V}'`` guards the module dispatches.
The protocol under test is a sequence of guarded dispatches whose correctness
depends on what the previous one did — a scripted one-answer-per-call fake
could not tell a guard that fired from one that should not have.

Run: python3 tests/test_agent_reopen.py
"""

from __future__ import annotations

import os
import re
import sys
import types
import unittest
import unittest.mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import agent_frozen_ops as ops  # noqa: E402
import agent_reopen  # noqa: E402
import agent_restore  # noqa: E402

RID = "7f3a2c1d"
OTHER = "0badc0de"
NONCE = "a1b2c3d4"
ROOT = "/proj"
FROZEN = "@aitask_frozen"
READY = "@aitask_standin_ready"


# --- the fake tmux world -----------------------------------------------------


class World:
    """A tmux server: panes keyed by id, each carrying its window and options."""

    SERVER_PID = "4242"

    def __init__(self) -> None:
        self.panes: dict[str, dict] = {}
        self.calls: list[list[str]] = []
        self.unreachable = False
        self.fail_new_window = False
        self.new_window_output = None   # None -> real "%id\tpid"
        self._next = 500
        self._next_win = 50

    # -- construction --------------------------------------------------------
    def add(self, session: str, window: str, *, frozen: str = "", ready: str = "",
            dead: bool = False, pane_id: str | None = None) -> str:
        if pane_id is None:
            pane_id = f"%{self._next}"
            self._next += 1
        self._next_win += 1
        self.panes[pane_id] = {
            "pane_id": pane_id, "pane_pid": str(10000 + int(pane_id[1:])),
            "session_name": session, "window_name": window,
            "window_id": f"@{self._next_win}", "pane_dead": "1" if dead else "0",
            FROZEN: frozen, READY: ready,
        }
        return pane_id

    def in_session(self, session: str) -> list[dict]:
        return [p for p in self.panes.values() if p["session_name"] == session]

    # -- format rendering ----------------------------------------------------
    def _render(self, fmt: str, pane: dict | None) -> str:
        def sub(m):
            key = m.group(1)
            if key == "pid":
                return self.SERVER_PID
            return (pane or {}).get(key, "")
        return re.sub(r"#\{([@a-z_]+)\}", sub, fmt)

    def _cond(self, cond: str, pane: dict) -> bool:
        m = re.fullmatch(r"#\{==:#\{([@a-z_]+)\},(.*)\}", cond)
        assert m, f"unsupported condition {cond!r}"
        return pane.get(m.group(1), "") == m.group(2)

    @staticmethod
    def _unquote(s: str) -> str:
        if s.startswith('"') and s.endswith('"'):
            return s[1:-1].replace('\\"', '"').replace("\\$", "$").replace("\\\\", "\\")
        return s

    def _exec(self, cmd: str) -> None:
        verb, _, rest = cmd.partition(" ")
        if verb == "set-option":
            # set-option -p -t %N OPT VAL
            parts = rest.split()
            pane = self.panes.get(parts[2])
            if pane is not None:
                pane[parts[3]] = parts[4]
        elif verb == "kill-window":
            pane = self.panes.get(rest.split()[1])
            if pane is not None:
                wid = pane["window_id"]
                for pid in [k for k, p in self.panes.items() if p["window_id"] == wid]:
                    del self.panes[pid]
        elif verb == "rename-window":
            _, target, name = rest.split(" ", 2)
            pane = self.panes.get(target)
            if pane is not None:
                for p in self.panes.values():
                    if p["window_id"] == pane["window_id"]:
                        p["window_name"] = self._unquote(name)
        elif verb == "move-window":
            parts = rest.split(" ")
            pane = self.panes.get(parts[1])
            dest = self._unquote(parts[3])
            session = dest[1:].rstrip(":")
            if pane is not None:
                for p in self.panes.values():
                    if p["window_id"] == pane["window_id"]:
                        p["session_name"] = session
        else:
            raise AssertionError(f"unsupported if-shell branch {cmd!r}")

    @staticmethod
    def _session_scope(target: str) -> str:
        """A bare ``=S`` resolves as a WINDOW first on real tmux (measured,
        3.7c): the code must send ``=S:``, so this fake refuses anything else."""
        assert target.startswith("=") and target.endswith(":"), (
            f"ambiguous session target {target!r}: use '=<session>:'")
        return target[1:-1]

    # -- the gateway ---------------------------------------------------------
    def run(self, args, timeout=None):
        args = list(args)
        self.calls.append(args)
        if self.unreachable:
            return -1, ""
        verb = args[0]
        if verb == "display-message":
            pane = self.panes.get(args[3])
            return 0, self._render(args[4], pane)
        if verb == "list-panes":
            fmt = args[-1]
            if "-a" in args:
                rows = list(self.panes.values())
            else:
                rows = self.in_session(self._session_scope(args[args.index("-t") + 1]))
            return 0, "\n".join(self._render(fmt, p) for p in rows)
        if verb == "list-windows":
            session = self._session_scope(args[args.index("-t") + 1])
            seen, rows = set(), []
            for p in self.in_session(session):
                if p["window_id"] not in seen:
                    seen.add(p["window_id"])
                    rows.append(self._render(args[-1], p))
            return 0, "\n".join(rows)
        if verb == "new-window":
            if self.fail_new_window:
                return 1, ""
            session = args[args.index("-t") + 1].lstrip("=").rstrip(":")
            name = args[args.index("-n") + 1]
            pane_id = self.add(session, name)
            if self.new_window_output is not None:
                return 0, self.new_window_output
            return 0, f"{pane_id}\t{self.panes[pane_id]['pane_pid']}"
        if verb == "if-shell":
            pane = self.panes.get(args[3])
            if pane is not None and self._cond(args[4], pane):
                self._exec(args[5])
            return 0, ""
        raise AssertionError(f"unsupported tmux call {args}")

    def verbs(self) -> list[str]:
        return [c[0] for c in self.calls]

    def branches(self) -> list[str]:
        return [c[5] for c in self.calls if c[0] == "if-shell"]


# --- the fake store ----------------------------------------------------------


class Store:
    def __init__(self, *records: dict) -> None:
        self.records = {r["id"]: dict(r) for r in records}
        self.calls: list[tuple] = []
        self.lease_rc = 0
        self.commit_rc = 0
        self.on_lease = None      # callable run just before a lease is granted

    def __call__(self, *argv, timeout: float = 20.0):
        self.calls.append(tuple(argv))
        verb = argv[0]
        if verb == "list":
            rows = []
            for r in self.records.values():
                if r["state"] != "frozen" or r["root"] != argv[argv.index("--root") + 1]:
                    continue
                rows.append("SESSION:" + "|".join(
                    [r["id"], r["state"], r["root"], r["window"], r["pane_id"],
                     r["task_id"], "", ""]))
            return 0, "\n".join(rows)
        if verb == "show":
            r = self.records.get(argv[1])
            if r is None:
                return 3, "ERROR:no record"
            return 0, "\n".join(f"{k}:{v}" for k, v in r.items())
        if verb == "lease-take":
            if self.lease_rc:
                return self.lease_rc, "LEASE_HELD"
            if argv[1] in self.records:
                self.records[argv[1]]["op_nonce"] = NONCE
            if self.on_lease is not None:
                self.on_lease()
            return 0, f"LEASED:{argv[1]}|{NONCE}"
        if verb == "lease-release":
            if argv[1] in self.records:
                self.records[argv[1]]["op_nonce"] = ""
            return 0, f"RELEASED:{argv[1]}"
        if verb == "standin-respawned":
            if self.commit_rc:
                return self.commit_rc, "ERROR:refused"
            r = self.records[argv[1]]
            r["pane_id"] = argv[argv.index("--pane") + 1]
            r["pane_pid"] = argv[argv.index("--pane-pid") + 1]
            r["op_nonce"] = ""
            return 0, f"STANDIN:{argv[1]}"
        raise AssertionError(f"unexpected store verb {argv}")

    def verbs(self) -> list[str]:
        return [c[0] for c in self.calls]


def rec(record_id: str = RID, **kw) -> dict:
    base = {
        "id": record_id, "state": "frozen", "root": ROOT,
        "window": "agent-pick-1847", "pane_id": "%1", "pane_pid": "111",
        "task_id": "1847", "agent_string": "claudecode/opus5",
        "agent_kind": "claudecode", "codeagent_session_id": "sess-1",
        "frozen_at": "2026-09-21T22:40:00Z", "op_nonce": "",
    }
    base.update(kw)
    return base


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.store = Store(rec())
        for name, value in (("store", self.store), ("_TMUX", self.world)):
            prev = getattr(ops, name)
            setattr(ops, name, value)
            self.addCleanup(setattr, ops, name, prev)
        self.companions: list[tuple] = []
        p1 = unittest.mock.patch.object(
            agent_restore, "_spawn_companion",
            side_effect=lambda *a: self.companions.append(a))
        p1.start()
        self.addCleanup(p1.stop)
        self.targets: dict[str | None, str] = {None: "aitasks", "aitasks": "aitasks",
                                               "B": "B", "-n": "-n"}

        def resolve(root, session=None):
            if session is not None and session not in self.targets:
                return None, f"session_not_for_root:{session}"
            return types.SimpleNamespace(session=self.targets[session]), ""

        p2 = unittest.mock.patch.object(agent_restore, "_resolve_target_session",
                                        side_effect=resolve)
        p2.start()
        self.addCleanup(p2.stop)
        env = unittest.mock.patch.dict(os.environ, {"AITASKS_TEST_MODE": "1"})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(agent_reopen.FAIL_ENV, None)

    def seam(self, value: str) -> None:
        os.environ[agent_reopen.FAIL_ENV] = value

    def record(self) -> dict:
        return self.store.records[RID]

    def windows_named(self, name: str) -> list[dict]:
        return [p for p in self.world.panes.values() if p["window_name"] == name]


# --- classification ----------------------------------------------------------


class TestClassification(_Base):
    def kind(self):
        claims = agent_reopen._claimed_panes()
        return agent_reopen.classify_record(self.record(), claims.get(RID, []))[0]

    def test_no_claim_is_gone(self):
        self.assertEqual("gone", self.kind())

    def test_own_pane_with_stamp_is_tracked(self):
        self.world.add("aitasks", "agent-pick-1847", frozen=RID, pane_id="%1")
        self.assertEqual("tracked", self.kind())

    def test_own_pane_dead_is_still_tracked(self):
        """A dead stamped stand-in is reconcile's to respawn, not ours to duplicate."""
        self.world.add("aitasks", "x", frozen=RID, pane_id="%1", dead=True)
        self.assertEqual("tracked", self.kind())

    def test_foreign_stamp_on_recorded_pane_is_gone(self):
        self.world.add("aitasks", "x", frozen=OTHER, pane_id="%1")
        self.assertEqual("gone", self.kind())

    def test_stamp_elsewhere_is_stranded(self):
        self.world.add("aitasks", "agent-pick-1847", frozen=RID)
        self.assertEqual("stranded", self.kind())

    def test_ready_mark_only_is_stranded(self):
        self.world.add("aitasks", "whatever", ready=RID)
        self.assertEqual("stranded", self.kind())

    def test_attempt_name_only_is_stranded(self):
        """The retry-before-self-stamp case: only the window name says whose it is."""
        self.world.add("aitasks", agent_reopen.attempt_name(RID, "deadbeef"))
        self.assertEqual("stranded", self.kind())

    def test_another_records_attempt_name_is_not_a_claim(self):
        self.world.add("aitasks", agent_reopen.attempt_name(OTHER, "deadbeef"))
        self.assertEqual("gone", self.kind())

    def test_dead_stranded_pane_is_ignored(self):
        self.world.add("aitasks", "x", frozen=RID, dead=True)
        self.assertEqual("gone", self.kind())

    def test_unreachable_tmux_fails_closed(self):
        self.world.unreachable = True
        self.assertEqual(([], [f"GONE_ERROR:{RID}|tmux_unreachable"]),
                         agent_reopen.classify(ROOT))

    def test_classify_scopes_the_store_list_to_the_root(self):
        agent_reopen.classify(ROOT)
        self.assertIn(("list", "--state", "frozen", "--root", ROOT), self.store.calls)

    def test_gone_line_carries_both_blockers(self):
        r = rec(codeagent_session_id="", task_id="")
        self.assertEqual(
            f"GONE:{RID}|gone|agent-pick-1847||2026-09-21T22:40:00Z|no_session|no_task_id",
            agent_reopen.gone_line(r, "gone"))
        self.assertEqual(
            f"GONE:{RID}|stranded|agent-pick-1847|1847|2026-09-21T22:40:00Z|ok|ok",
            agent_reopen.gone_line(rec(), "stranded"))


# --- the fresh transaction ---------------------------------------------------


class TestFresh(_Base):
    def test_happy_path_order_and_result(self):
        line = agent_reopen.reopen_one(RID, session="aitasks")
        self.assertTrue(line.startswith(f"REOPENED:{RID}|fresh|aitasks:agent-pick-1847|%"), line)
        pane = self.record()["pane_id"]
        self.assertEqual(RID, self.world.panes[pane][FROZEN])
        self.assertEqual("agent-pick-1847", self.world.panes[pane]["window_name"])
        self.assertEqual(self.world.panes[pane]["pane_pid"], self.record()["pane_pid"])
        self.assertEqual("", self.record()["op_nonce"])
        # new-window (detached, attempt name) → name-guarded stamp → guarded rename
        nw = next(c for c in self.world.calls if c[0] == "new-window")
        self.assertIn("-d", nw)
        self.assertEqual(agent_reopen.attempt_name(RID, NONCE), nw[nw.index("-n") + 1])
        stamp, rename = [c for c in self.world.calls if c[0] == "if-shell"]
        self.assertIn("#{window_name}", stamp[4])
        self.assertIn(FROZEN, rename[4])
        self.assertEqual(["lease-take", "standin-respawned"],
                         [v for v in self.store.verbs() if v in ("lease-take", "standin-respawned",
                                                                  "lease-release")])
        self.assertEqual(1, len(self.companions))

    def test_second_run_is_a_noop(self):
        agent_reopen.reopen_one(RID, session="aitasks")
        self.assertEqual(f"REOPEN_SKIPPED:{RID}|pane_present",
                         agent_reopen.reopen_one(RID, session="aitasks"))

    def test_lost_output_is_identified_by_name(self):
        self.seam("identify")
        line = agent_reopen.reopen_one(RID, session="aitasks")
        self.assertTrue(line.startswith(f"REOPENED:{RID}|fresh"), line)

    def test_nonzero_rc_with_the_window_present_continues(self):
        """An rc of -1 after the server created the window is a partial launch."""
        self.seam("launch_uncertain")
        line = agent_reopen.reopen_one(RID, session="aitasks")
        self.assertTrue(line.startswith(f"REOPENED:{RID}|fresh"), line)
        self.assertEqual(1, len(self.world.panes))

    def test_nonzero_rc_and_no_window_is_a_plain_failure(self):
        self.world.fail_new_window = True
        line = agent_reopen.reopen_one(RID, session="aitasks")
        self.assertEqual(f"REOPEN_FAILED:{RID}|launch:rc=1", line)
        self.assertEqual("", self.record()["op_nonce"], "the lease must be released")

    def test_uncertain_lookup_reports_uncertain_and_the_rerun_adopts(self):
        self.seam("launch_uncertain,lookup")
        line = agent_reopen.reopen_one(RID, session="aitasks")
        self.assertEqual(f"REOPEN_FAILED:{RID}|launch:uncertain", line)
        self.assertEqual("", self.record()["op_nonce"])
        # The window the server did create is unstamped — only its name claims it.
        self.seam("")
        line = agent_reopen.reopen_one(RID, session="aitasks")
        self.assertTrue(line.startswith(f"REOPENED:{RID}|adopted|"), line)
        self.assertEqual(1, len(self.world.panes), "no second window")
        pane = self.record()["pane_id"]
        self.assertEqual("agent-pick-1847", self.world.panes[pane]["window_name"])

    def test_stamp_failure_kills_by_name_and_commits_nothing(self):
        self.seam("stamp")
        line = agent_reopen.reopen_one(RID, session="aitasks")
        self.assertEqual(f"REOPEN_FAILED:{RID}|stamp", line)
        self.assertEqual({}, self.world.panes)
        self.assertNotIn("standin-respawned", self.store.verbs())
        self.assertIn("kill-window", self.world.branches()[-1])

    def test_rename_failure_kills_by_stamp(self):
        self.seam("rename")
        line = agent_reopen.reopen_one(RID, session="aitasks")
        self.assertEqual(f"REOPEN_FAILED:{RID}|rename", line)
        self.assertEqual({}, self.world.panes)
        self.assertNotIn("standin-respawned", self.store.verbs())

    def test_store_failure_kills_by_stamp_and_never_unstamps(self):
        self.store.commit_rc = 5
        line = agent_reopen.reopen_one(RID, session="aitasks")
        self.assertTrue(line.startswith(f"REOPEN_FAILED:{RID}|store:"), line)
        self.assertEqual({}, self.world.panes)
        self.assertFalse([c for c in self.world.calls if c[0] == "set-option"
                          and "-pu" in c], "must never unstamp")
        self.assertEqual("", self.record()["op_nonce"])

    def test_store_failure_with_failed_cleanup_leaves_a_named_stamped_survivor(self):
        self.store.commit_rc = 5
        self.seam("cleanup")
        line = agent_reopen.reopen_one(RID, session="aitasks")
        self.assertIn("|cleanup:present:seam|pane:", line)
        (survivor,) = self.world.panes.values()
        self.assertEqual(RID, survivor[FROZEN])
        self.assertEqual("agent-pick-1847", survivor["window_name"],
                         "the rename precedes the commit")
        # The next run adopts it — no second window, no suffix, no rename.
        self.store.commit_rc = 0
        self.seam("")
        n_before = len(self.world.calls)
        line = agent_reopen.reopen_one(RID, session="aitasks")
        self.assertTrue(line.startswith(f"REOPENED:{RID}|adopted|aitasks:agent-pick-1847|"), line)
        self.assertEqual(1, len(self.world.panes))
        self.assertFalse([c for c in self.world.calls[n_before:]
                          if c[0] == "if-shell" and "rename-window" in c[5]])

    def test_suffix_is_stable_across_an_adoption(self):
        self.world.add("aitasks", "agent-pick-1847")      # an unrelated holder
        self.store.commit_rc = 5
        self.seam("cleanup")
        agent_reopen.reopen_one(RID, session="aitasks")
        self.assertEqual(1, len(self.windows_named("agent-pick-1847-2")))
        self.store.commit_rc = 0
        self.seam("")
        line = agent_reopen.reopen_one(RID, session="aitasks")
        self.assertIn("|aitasks:agent-pick-1847-2|", line)
        self.assertEqual([], self.windows_named("agent-pick-1847-3"))

    def test_a_viewer_committed_before_our_lease_is_not_duplicated(self):
        """Both runs saw `gone`; the other one committed, then we got a lease.

        The pre-check reading is stale by then, so the decision must come from
        a re-read under the lease.
        """
        def other_run_committed():
            pane = self.world.add("aitasks", "agent-pick-1847", frozen=RID)
            self.record()["pane_id"] = pane
        self.store.on_lease = other_run_committed
        line = agent_reopen.reopen_one(RID, session="aitasks")
        self.assertEqual(f"REOPEN_SKIPPED:{RID}|pane_present", line)
        self.assertNotIn("new-window", self.world.verbs())
        self.assertEqual(1, len(self.world.panes))
        self.assertIn("lease-release", self.store.verbs())

    def test_a_survivor_appearing_before_our_lease_is_adopted_not_duplicated(self):
        def survivor_appeared():
            self.world.add("aitasks", "agent-pick-1847", frozen=RID)
        self.store.on_lease = survivor_appeared
        line = agent_reopen.reopen_one(RID, session="aitasks")
        self.assertTrue(line.startswith(f"REOPENED:{RID}|adopted|"), line)
        self.assertNotIn("new-window", self.world.verbs())

    def test_a_record_that_left_frozen_before_our_lease_is_skipped(self):
        def restored_meanwhile():
            self.record()["state"] = "live"
        self.store.on_lease = restored_meanwhile
        self.assertEqual(f"REOPEN_SKIPPED:{RID}|state:live",
                         agent_reopen.reopen_one(RID, session="aitasks"))
        self.assertNotIn("new-window", self.world.verbs())

    def test_an_unreadable_reread_under_the_lease_is_a_failure(self):
        """`store_show` answers {} for an unreadable store too: never a skip."""
        def store_became_unreadable():
            self.store.records.pop(RID)
        self.store.on_lease = store_became_unreadable
        line = agent_reopen.reopen_one(RID, session="aitasks")
        self.assertEqual(f"REOPEN_FAILED:{RID}|reread:record unreadable", line)
        self.assertIn("lease-release", self.store.verbs())
        self.assertNotIn("new-window", self.world.verbs())

    def test_session_scoped_reads_use_an_unambiguous_target(self):
        """Every session-scoped read is `=S:` (the fake asserts it on each call)."""
        self.seam("identify")                     # forces the name lookup too
        agent_reopen.reopen_one(RID, session="aitasks")
        scoped = [c for c in self.world.calls
                  if c[0] in ("list-windows",) or (c[0] == "list-panes" and "-s" in c)]
        self.assertTrue(scoped, "anti-vacuity: session-scoped reads were issued")
        for call in scoped:
            self.assertEqual("=aitasks:", call[call.index("-t") + 1])

    def test_lease_held_is_skipped_without_launching(self):
        self.store.lease_rc = agent_reopen.EXIT_LEASE_HELD
        self.assertEqual(f"REOPEN_SKIPPED:{RID}|lease_held",
                         agent_reopen.reopen_one(RID, session="aitasks"))
        self.assertNotIn("new-window", self.world.verbs())

    def test_non_frozen_state_is_skipped(self):
        self.record()["state"] = "live"
        self.assertEqual(f"REOPEN_SKIPPED:{RID}|state:live",
                         agent_reopen.reopen_one(RID))

    def test_unattributed_session_fails_closed_before_any_window(self):
        line = agent_reopen.reopen_one(RID, session="C")
        self.assertEqual(f"REOPEN_FAILED:{RID}|session_not_for_root:C", line)
        self.assertNotIn("new-window", self.world.verbs())
        self.assertEqual("", self.record()["op_nonce"])

    def test_option_like_session_is_targeted(self):
        agent_reopen.reopen_one(RID, session="-n")
        nw = next(c for c in self.world.calls if c[0] == "new-window")
        self.assertEqual("=-n:", nw[nw.index("-t") + 1])


# --- adoption ----------------------------------------------------------------


class TestAdopt(_Base):
    def test_ready_only_viewer_is_stamped_renamed_and_recorded(self):
        pane = self.world.add("aitasks", "odd-name", ready=RID)
        line = agent_reopen.reopen_one(RID, session="aitasks")
        self.assertEqual(f"REOPENED:{RID}|adopted|aitasks:agent-pick-1847|{pane}", line)
        self.assertEqual(RID, self.world.panes[pane][FROZEN])
        self.assertEqual(pane, self.record()["pane_id"])
        self.assertNotIn("new-window", self.world.verbs())

    def test_viewer_in_another_session_is_moved_into_the_selected_one(self):
        pane = self.world.add("A", "agent-pick-1847", frozen=RID)
        line = agent_reopen.reopen_one(RID, session="B")
        self.assertTrue(line.startswith(f"REOPENED:{RID}|adopted|B:"), line)
        self.assertEqual("B", self.world.panes[pane]["session_name"])

    def test_without_a_session_the_viewer_stays_where_it_is(self):
        pane = self.world.add("A", "agent-pick-1847", frozen=RID)
        agent_reopen.reopen_one(RID)
        self.assertEqual("A", self.world.panes[pane]["session_name"])

    def test_a_failed_move_touches_nothing_and_releases(self):
        pane = self.world.add("A", "agent-pick-1847", frozen=RID)
        self.seam("move")
        line = agent_reopen.reopen_one(RID, session="B")
        self.assertEqual(f"REOPEN_FAILED:{RID}|adopt:move|pane:{pane}", line)
        self.assertIn(pane, self.world.panes, "adoption never kills")
        self.assertNotIn("standin-respawned", self.store.verbs())
        self.assertEqual("", self.record()["op_nonce"])

    def test_a_failed_adopt_rename_keeps_the_pane_for_the_next_run(self):
        pane = self.world.add("aitasks", agent_reopen.attempt_name(RID, "deadbeef"),
                              frozen=RID)
        self.seam("rename")
        line = agent_reopen.reopen_one(RID, session="aitasks")
        self.assertEqual(f"REOPEN_FAILED:{RID}|adopt:rename|pane:{pane}", line)
        self.assertIn(pane, self.world.panes)
        self.seam("")
        line = agent_reopen.reopen_one(RID, session="aitasks")
        self.assertTrue(line.startswith(f"REOPENED:{RID}|adopted|aitasks:agent-pick-1847|"), line)


# --- batch + CLI -------------------------------------------------------------


class TestBatchAndCli(_Base):
    def test_reopen_all_covers_gone_and_stranded(self):
        self.store.records[OTHER] = rec(OTHER, window="agent-other", pane_id="%2")
        self.world.add("aitasks", "x", ready=OTHER)
        lines = agent_reopen.reopen_all(ROOT, session="aitasks")
        self.assertEqual("REOPEN_ALL:2/2", lines[-1])
        self.assertTrue(any(f"REOPENED:{RID}|fresh" in ln for ln in lines))
        self.assertTrue(any(f"REOPENED:{OTHER}|adopted" in ln for ln in lines))

    def test_seam_parses_a_comma_set_only_in_test_mode(self):
        self.seam("store, cleanup")
        self.assertTrue(agent_reopen._seam("store"))
        self.assertTrue(agent_reopen._seam("cleanup"))
        self.assertFalse(agent_reopen._seam("stamp"))
        with unittest.mock.patch.dict(os.environ, {"AITASKS_TEST_MODE": "0"}):
            self.assertFalse(agent_reopen._seam("store"))

    def _main(self, *argv):
        with unittest.mock.patch("sys.stdout"), unittest.mock.patch("sys.stderr"):
            return agent_reopen.main(list(argv))

    def test_cli_grammar(self):
        self.assertEqual(2, self._main())
        self.assertEqual(2, self._main("gone"))
        self.assertEqual(2, self._main("reopen", "--session"))
        self.assertEqual(2, self._main("reopen", RID, "--session", "a.b"))
        self.assertEqual(2, self._main("reopen", RID, "--session", "a:b"))
        self.assertEqual(2, self._main("reopen", "not-an-id"))
        self.assertEqual(2, self._main("gone", "--root", ROOT, "--session", "x"))
        self.assertEqual(0, self._main("gone", "--root", ROOT))
        self.assertEqual(0, self._main("reopen", RID, "--session", "-n"))


class TestRestoreHelpers(unittest.TestCase):
    """The shared eligibility and session-argument helpers in `agent_restore`."""

    def test_blockers(self):
        self.assertEqual("", agent_restore.resume_blocker(rec()))
        self.assertEqual("no_session",
                         agent_restore.resume_blocker(rec(codeagent_session_id="")))
        self.assertEqual("resume_unsupported:opencode",
                         agent_restore.resume_blocker(rec(agent_kind="opencode")))
        self.assertEqual("", agent_restore.repick_blocker(rec()))
        self.assertEqual("no_task_id", agent_restore.repick_blocker(rec(task_id="")))

    def test_take_session_arg(self):
        self.assertEqual((["x"], "-n", ""),
                         agent_restore.take_session_arg(["--session", "-n", "x"]))
        self.assertEqual((["x"], None, ""), agent_restore.take_session_arg(["x"]))
        self.assertTrue(agent_restore.take_session_arg(["--session"])[2])
        self.assertTrue(agent_restore.take_session_arg(["--session", ""])[2])
        self.assertTrue(agent_restore.take_session_arg(["--session", "a.b"])[2])
        self.assertTrue(agent_restore.take_session_arg(
            ["--session", "a", "--session", "b"])[2])


if __name__ == "__main__":
    unittest.main()
