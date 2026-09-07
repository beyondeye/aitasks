"""Unit tests for the freeze engine (t1705_4).

No tmux and no store file: :class:`_FakeTmux` records every gateway call and
replays scripted answers, and :func:`agent_freeze._store` is replaced by a fake
wrapper that drives a real in-memory :class:`agent_sessions.SessionsFile`
through the SAME transition functions the wrapper would. That keeps the state
machine honest — a refusal here is a real ``TransitionRefused``, not a string a
stub decided to return — while leaving the process boundary out of it.

Two things this file owns that the live suite deliberately does not:

* **the stale-nonce guard.** ``freeze_commit`` validates STATE BEFORE NONCE
  (``_require_state`` then ``_require_nonce``), so a stale-nonce commit against
  a record that reconcile has already put back to ``live`` returns
  ``TRANSITION_REFUSED`` and never reaches the nonce check — a test written that
  way would pass while proving nothing. The only state in which the nonce guard
  is reachable is ``freezing``, which ``lease_take``'s injectable ``now=`` /
  ``pid_alive=`` produce directly. ``NonceGuardTests`` drives exactly that, and
  ships the negative control that motivated the move.
* **the failure-injection rollbacks**, at the level of "which store verb and
  which tmux call did each stage actually make", which a live run can only
  infer from the resulting state.

Run: python3 tests/test_agent_freeze.py
"""

from __future__ import annotations

import copy
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import agent_sessions  # noqa: E402
import agent_freeze  # noqa: E402

AGENT_PANE = "%1"
AGENT_PID = 4242
STANDIN_PID = 8888


def _reaped_pid() -> int:
    """A pid that is provably gone: spawned, exited, and reaped."""
    proc = subprocess.Popen([sys.executable, "-c", ""])
    proc.wait()
    return proc.pid


class _FakeTmux:
    """Records gateway argv and answers `display-message` from a pane model.

    The pane model is a plain dict so a test can mutate it between calls —
    which is what makes "read the location AFTER the respawn" observable rather
    than assumed.
    """

    def __init__(self, panes: dict[str, dict[str, str]]) -> None:
        self.panes = panes
        self.calls: list[list[str]] = []
        self.capture_text = "line one\nline two\n"
        self.respawn_ok = True
        self.set_option_ok = True
        self.capture_rc = 0

    # -- the TmuxClient surface agent_freeze uses --------------------------
    def run(self, args, timeout=None):
        self.calls.append(list(args))
        verb = args[0] if args else ""
        if verb == "display-message":
            return self._display(args)
        if verb == "capture-pane":
            return (self.capture_rc, self.capture_text if self.capture_rc == 0
                    else "")
        if verb == "set-option":
            return self._set_option(args)
        if verb == "respawn-pane":
            return self._respawn(args)
        if verb == "list-panes":
            return 0, ""
        return 0, ""

    # -- helpers ------------------------------------------------------------
    def _target(self, args):
        return args[args.index("-t") + 1] if "-t" in args else ""

    def _display(self, args):
        pane = self.panes.get(self._target(args))
        if pane is None:
            return 1, ""
        fmt = args[-1]
        fields = []
        for spec in fmt.split("\t"):
            key = spec.strip("#{}")
            fields.append(str(pane.get(key, "")))
        return 0, "\t".join(fields) + "\n"

    def _set_option(self, args):
        if not self.set_option_ok:
            return 1, ""
        pane = self.panes.get(self._target(args))
        if pane is None:
            return 1, ""
        if "-pu" in args:
            pane[args[-1]] = ""
        else:
            pane[args[-2]] = args[-1]
        return 0, ""

    def _respawn(self, args):
        if not self.respawn_ok:
            return 1, ""
        pane = self.panes.get(self._target(args))
        if pane is None:
            return 1, ""
        # `respawn-pane -k` replaces the PROCESS and keeps the pane id and every
        # pane-scoped option — the fact the whole design rests on (t1705_1).
        pane["pane_pid"] = str(STANDIN_PID)
        pane["pane_dead"] = "0"
        return 0, ""

    def calls_of(self, verb: str) -> list[list[str]]:
        return [c for c in self.calls if c and c[0] == verb]


class _FakeStore:
    """`aitask_agent_sessions.sh` without the process boundary.

    Verbs are dispatched to the REAL `agent_sessions` transition functions, so
    the exit codes and refusal lines below are produced by the store's own
    rules. Only the mutex and the JSON round trip are elided.
    """

    def __init__(self, sf: agent_sessions.SessionsFile) -> None:
        self.sf = sf
        self.calls: list[tuple[str, ...]] = []
        self.fail_verbs: dict[str, int] = {}   # verb -> exit code to force

    def __call__(self, *argv: str, timeout: float = 20.0):
        self.calls.append(tuple(argv))
        verb = argv[0]
        if verb in self.fail_verbs:
            code = self.fail_verbs[verb]
            return code, f"FORCED:{verb}"
        try:
            return self._dispatch(verb, argv[1:])
        except agent_sessions.TransitionRefused as exc:
            return agent_freeze.EXIT_TRANSITION_REFUSED, str(exc)
        except agent_sessions.NonceMismatch as exc:
            return agent_freeze.EXIT_NONCE_MISMATCH, str(exc)
        except agent_sessions.LeaseHeld as exc:
            return agent_freeze.EXIT_LEASE_HELD, str(exc)
        except (ValueError, KeyError) as exc:
            return 4, f"ERROR:{exc}"

    def _arg(self, argv, name, default=""):
        return argv[argv.index(name) + 1] if name in argv else default

    def _dispatch(self, verb, argv):
        if verb == "show":
            rec = self.sf.by_id(argv[0])
            if rec is None:
                return 4, f"ERROR:no such record: {argv[0]}"
            return 0, "\n".join(f"{k}:{v}" for k, v in vars(rec).items())
        if verb == "list":
            out = []
            for rec in self.sf.sessions:
                out.append(f"SESSION:{rec.id}|{rec.state}|{rec.root}|"
                           f"{rec.window}|{rec.pane_id}|{rec.task_id}|"
                           f"{rec.agent_string}|{rec.state_at}")
            return 0, "\n".join(out)
        if verb == "upsert":
            self.sf, line = agent_sessions.upsert(
                self.sf,
                root=self._arg(argv, "--root"),
                window=self._arg(argv, "--window"),
                pane=self._arg(argv, "--pane"),
                pane_pid=int(self._arg(argv, "--pane-pid", "0")),
                session_id=self._arg(argv, "--session-id"),
            )
            return 0, line
        if verb == "freeze-begin":
            self.sf, line = agent_sessions.freeze_begin(
                self.sf, argv[0],
                capture_ansi=self._arg(argv, "--capture-ansi"),
                capture_txt=self._arg(argv, "--capture-txt"),
                lines=int(self._arg(argv, "--lines", "0")),
                owner_pid=int(self._arg(argv, "--owner-pid", "0")),
            )
            return 0, line
        if verb == "freeze-commit":
            self.sf, line = agent_sessions.freeze_commit(
                self.sf, argv[0], nonce=self._arg(argv, "--nonce"),
                pane=self._arg(argv, "--pane"),
                pane_pid=int(self._arg(argv, "--pane-pid", "0")),
            )
            return 0, line
        if verb == "freeze-abort":
            self.sf, line = agent_sessions.freeze_abort(
                self.sf, argv[0], nonce=self._arg(argv, "--nonce"))
            return 0, line
        if verb == "restore-begin":
            self.sf, line = agent_sessions.restore_begin(
                self.sf, argv[0], mode=self._arg(argv, "--mode", "resume"),
                owner_pid=int(self._arg(argv, "--owner-pid", "0")))
            return 0, line
        if verb == "restore-launched":
            self.sf, line = agent_sessions.restore_launched(
                self.sf, argv[0], nonce=self._arg(argv, "--nonce"),
                pane=self._arg(argv, "--pane"),
                pane_pid=int(self._arg(argv, "--pane-pid", "0")))
            return 0, line
        if verb == "restore-confirm":
            self.sf, line = agent_sessions.restore_confirm(
                self.sf, argv[0], nonce=self._arg(argv, "--nonce"),
                pane=self._arg(argv, "--pane"),
                pane_pid=int(self._arg(argv, "--pane-pid", "0")))
            return 0, line
        if verb == "restore-abort":
            self.sf, line = agent_sessions.restore_abort(
                self.sf, argv[0], nonce=self._arg(argv, "--nonce"))
            return 0, line
        if verb == "standin-respawned":
            self.sf, line = agent_sessions.standin_respawned(
                self.sf, argv[0], nonce=self._arg(argv, "--nonce"),
                pane=self._arg(argv, "--pane"),
                pane_pid=int(self._arg(argv, "--pane-pid", "0")))
            return 0, line
        if verb == "lease-take":
            self.sf, line = agent_sessions.lease_take(
                self.sf, argv[0],
                owner_pid=int(self._arg(argv, "--owner-pid", "0")))
            return 0, line
        if verb == "drop":
            self.sf, line = agent_sessions.drop(self.sf, argv[0])
            return 0, line
        if verb == "purge":
            return 0, "PURGED:0"
        return 2, f"unknown verb: {verb}"

    def verbs(self) -> list[str]:
        return [c[0] for c in self.calls]


class _FixedLease:
    """A `_Lease` stand-in that hands out a nonce already known to the test.

    It also RECORDS whether it was called, which is the assertion that keeps
    reconcile's lazy-lease rule honest: a row that takes no action must not
    lease, because `lease-take` writes and nothing clears the lease afterwards.
    """

    def __init__(self, nonce: str) -> None:
        self.nonce = nonce
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        return self.nonce


class _FreezeTestCase(unittest.TestCase):
    """Wires the fakes and a private frozen/capture root."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

        self.root = self.tmp / "project"
        (self.root / "aitasks" / "metadata").mkdir(parents=True)
        (self.root / "aitasks" / "metadata" / "project_config.yaml").write_text(
            "# no frozen: section — the default cap is the normal path\n"
        )

        os.environ[agent_sessions.FROZEN_DIR_ENV] = str(self.tmp / "frozen")
        self.addCleanup(os.environ.pop, agent_sessions.FROZEN_DIR_ENV, None)
        os.environ["AITASKS_TEST_MODE"] = "1"
        self.addCleanup(os.environ.pop, "AITASKS_TEST_MODE", None)
        os.environ["AITASKS_FROZEN_STANDIN_CMD"] = "true"
        self.addCleanup(os.environ.pop, "AITASKS_FROZEN_STANDIN_CMD", None)
        for var in ("AITASKS_FREEZE_FAIL_AT", "AITASKS_FROZEN_PAUSE_AT"):
            os.environ.pop(var, None)
            self.addCleanup(os.environ.pop, var, None)

        self.sf = agent_sessions.SessionsFile()
        self.sf, line = agent_sessions.upsert(
            self.sf, root=str(self.root), window="agent-pick-1705",
            pane=AGENT_PANE, pane_pid=AGENT_PID, pane_alive=lambda pid: True,
        )
        self.rid = line.split(":")[1].split("|")[0]

        self.panes = {
            AGENT_PANE: {
                "session_name": "aitasks",
                "window_name": "agent-pick-1705",
                "pane_id": AGENT_PANE,
                "pane_pid": str(AGENT_PID),
                "pane_dead": "0",
                "pane_current_path": str(self.root),
                agent_freeze.RECORD_OPTION: self.rid,
                agent_freeze.FROZEN_OPTION: "",
                agent_freeze.STANDIN_READY_OPTION: "",
                agent_freeze.AGENT_SESSION_OPTION: "sess-abc",
            }
        }
        self.tmux = _FakeTmux(self.panes)
        self.store = _FakeStore(self.sf)
        self._install(self.tmux, self.store)

    def _install(self, tmux, store) -> None:
        prev_tmux = agent_freeze._TMUX
        prev_store = agent_freeze._store
        agent_freeze._TMUX = tmux
        agent_freeze._store = store
        self.addCleanup(setattr, agent_freeze, "_TMUX", prev_tmux)
        self.addCleanup(setattr, agent_freeze, "_store", prev_store)

    def rec(self):
        return self.store.sf.by_id(self.rid)


class HappyPathTests(_FreezeTestCase):
    def test_freeze_walks_the_six_stages_in_order(self):
        result = agent_freeze.freeze_pane(AGENT_PANE)
        self.assertTrue(result.ok, result.line)
        self.assertEqual(result.line, f"FROZEN:{self.rid}")
        self.assertEqual(
            [v for v in self.store.verbs() if v != "show"],
            ["freeze-begin", "freeze-commit"],
            "an already-recorded pane must NOT be upserted again",
        )
        self.assertEqual(self.rec().state, agent_sessions.STATE_FROZEN)

    def test_the_standin_pid_is_read_after_the_respawn(self):
        """`respawn-pane` keeps the pane id, so only the pid proves the swap."""
        agent_freeze.freeze_pane(AGENT_PANE)
        rec = self.rec()
        self.assertEqual(rec.standin_pid, STANDIN_PID)
        self.assertNotEqual(rec.standin_pid, AGENT_PID,
                            "recording the AGENT's pid would make reconcile "
                            "mistake a live agent for a mounted viewer")
        self.assertEqual(rec.pane_id, AGENT_PANE)

    def test_capture_files_are_written_0600_with_the_right_line_count(self):
        agent_freeze.freeze_pane(AGENT_PANE)
        rec = self.rec()
        for path in (rec.capture_ansi, rec.capture_txt):
            self.assertTrue(os.path.isfile(path), path)
            mode = os.stat(path).st_mode & 0o777
            self.assertEqual(mode, 0o600,
                             f"{path} holds a verbatim session transcript")
        self.assertEqual(rec.capture_lines, 2)
        self.assertEqual(Path(rec.capture_txt).read_text(),
                         self.tmux.capture_text)

    def test_the_pane_is_stamped_and_the_stale_ready_mark_cleared(self):
        # A ready mark left by an EARLIER cycle: pane options survive
        # `respawn-pane`, so this is a real shape, not a contrived one.
        self.panes[AGENT_PANE][agent_freeze.STANDIN_READY_OPTION] = "deadbeef"
        agent_freeze.freeze_pane(AGENT_PANE)
        self.assertEqual(self.panes[AGENT_PANE][agent_freeze.FROZEN_OPTION],
                         self.rid)
        self.assertEqual(
            self.panes[AGENT_PANE][agent_freeze.STANDIN_READY_OPTION], "",
            "a stale ready mark would make reconcile commit a freeze whose "
            "viewer never mounted",
        )

    def test_the_lease_owner_is_this_process_not_a_subshell(self):
        """A7: a defaulted/ephemeral owner pid degrades the lease to a timer.

        The coordinator is the process that must OUTLIVE the respawn, so the
        owner pid has to be this one. Recording an ephemeral helper's pid
        instead reads as dead immediately, and the lease's
        `grace AND owner dead` test collapses to a bare 60 s timer that lets a
        later reconcile seize a freeze still in flight.
        """
        agent_freeze.freeze_pane(AGENT_PANE)
        begin = next(c for c in self.store.calls if c[0] == "freeze-begin")
        self.assertEqual(begin[begin.index("--owner-pid") + 1],
                         str(os.getpid()))
        self.assertEqual(self.store.sf.by_id(self.rid).op_owner_pid, 0,
                         "a committed freeze clears the lease entirely")

    def test_an_already_frozen_pane_is_skipped_without_touching_it(self):
        self.panes[AGENT_PANE][agent_freeze.FROZEN_OPTION] = self.rid
        result = agent_freeze.freeze_pane(AGENT_PANE)
        self.assertFalse(result.ok)
        self.assertIn("FREEZE_SKIPPED", result.line)
        self.assertEqual(self.tmux.calls_of("respawn-pane"), [])


class RecordResolutionTests(_FreezeTestCase):
    def test_an_unstamped_pane_is_upserted_and_then_stamped(self):
        """The fallback path (A8): the hook never fired for this agent."""
        self.panes[AGENT_PANE][agent_freeze.RECORD_OPTION] = ""
        result = agent_freeze.freeze_pane(AGENT_PANE)
        self.assertTrue(result.ok, result.line)
        self.assertIn("upsert", self.store.verbs())
        stamped = self.panes[AGENT_PANE][agent_freeze.RECORD_OPTION]
        self.assertTrue(agent_sessions.valid_id(stamped))
        self.assertEqual(stamped, result.record_id,
                         "the stamp must name the record that was created")

    def test_a_dangling_stamp_falls_back_to_upsert(self):
        """A stamped id the store does not know is a dangling join.

        Reusing it would `freeze-begin` a record that does not exist; creating
        one is the only recoverable move.
        """
        self.panes[AGENT_PANE][agent_freeze.RECORD_OPTION] = "deadbeef"
        result = agent_freeze.freeze_pane(AGENT_PANE)
        self.assertTrue(result.ok, result.line)
        self.assertIn("upsert", self.store.verbs())
        self.assertNotEqual(result.record_id, "deadbeef")

    def test_the_upsert_root_walks_up_to_the_project(self):
        self.panes[AGENT_PANE][agent_freeze.RECORD_OPTION] = ""
        deep = self.root / "a" / "b"
        deep.mkdir(parents=True)
        self.panes[AGENT_PANE]["pane_current_path"] = str(deep)
        agent_freeze.freeze_pane(AGENT_PANE)
        upsert = next(c for c in self.store.calls if c[0] == "upsert")
        self.assertEqual(upsert[upsert.index("--root") + 1],
                         os.path.realpath(str(self.root)))

    def test_a_missing_pane_fails_at_resolve_and_writes_nothing(self):
        result = agent_freeze.freeze_pane("%404")
        self.assertFalse(result.ok)
        self.assertTrue(result.line.startswith("FREEZE_FAILED:resolve"))
        self.assertEqual(self.store.calls, [])


class FailureInjectionTests(_FreezeTestCase):
    """One case per `AITASKS_FREEZE_FAIL_AT` stage, asserting the §C rollback."""

    def _fail_at(self, stage: str):
        os.environ["AITASKS_FREEZE_FAIL_AT"] = stage
        return agent_freeze.freeze_pane(AGENT_PANE)

    def test_capture_failure_leaves_the_agent_running_and_the_record_live(self):
        result = self._fail_at("capture")
        self.assertFalse(result.ok)
        self.assertEqual(result.stage, "capture")
        self.assertEqual(self.rec().state, agent_sessions.STATE_LIVE)
        self.assertEqual(self.tmux.calls_of("respawn-pane"), [])
        self.assertEqual(self.panes[AGENT_PANE][agent_freeze.FROZEN_OPTION], "")
        self.assertFalse(
            (Path(os.environ[agent_sessions.FROZEN_DIR_ENV]) / self.rid).exists(),
            "a failed capture must leave no capture directory behind",
        )

    def test_begin_failure_removes_the_capture_files(self):
        result = self._fail_at("begin")
        self.assertEqual(result.stage, "begin")
        self.assertEqual(self.rec().state, agent_sessions.STATE_LIVE)
        self.assertNotIn("freeze-begin", self.store.verbs())
        self.assertFalse(
            (Path(os.environ[agent_sessions.FROZEN_DIR_ENV]) / self.rid).exists())

    def test_stamp_failure_aborts_and_leaves_the_agent_running(self):
        result = self._fail_at("stamp")
        self.assertEqual(result.stage, "stamp")
        self.assertIn("freeze-abort", self.store.verbs())
        self.assertEqual(self.rec().state, agent_sessions.STATE_LIVE)
        self.assertEqual(self.tmux.calls_of("respawn-pane"), [],
                         "the agent must NOT have been respawned away")
        self.assertEqual(self.panes[AGENT_PANE][agent_freeze.FROZEN_OPTION], "")

    def test_respawn_failure_unstamps_both_options_and_aborts(self):
        result = self._fail_at("respawn")
        self.assertEqual(result.stage, "respawn")
        self.assertIn("freeze-abort", self.store.verbs())
        self.assertEqual(self.rec().state, agent_sessions.STATE_LIVE)
        self.assertEqual(self.panes[AGENT_PANE][agent_freeze.FROZEN_OPTION], "")
        self.assertEqual(
            self.panes[AGENT_PANE][agent_freeze.STANDIN_READY_OPTION], "")
        self.assertEqual(self.panes[AGENT_PANE]["pane_pid"], str(AGENT_PID),
                         "the agent process must be untouched")

    def test_a_real_respawn_refusal_takes_the_same_path(self):
        """The injected seam must not be the only way to reach the rollback."""
        self.tmux.respawn_ok = False
        result = agent_freeze.freeze_pane(AGENT_PANE)
        self.assertEqual(result.stage, "respawn")
        self.assertEqual(self.rec().state, agent_sessions.STATE_LIVE)

    def test_commit_failure_leaves_the_record_freezing_for_reconcile(self):
        """No rollback here, deliberately: the agent is already gone.

        Aborting at this point would put the record back to `live` with no agent
        behind it. `freezing` is the honest state, and reconcile finishes it.
        """
        result = self._fail_at("commit")
        self.assertEqual(result.stage, "commit")
        self.assertEqual(self.rec().state, agent_sessions.STATE_FREEZING)
        self.assertNotIn("freeze-abort", self.store.verbs())

    def test_a_busy_store_at_commit_also_leaves_it_freezing(self):
        self.store.fail_verbs["freeze-commit"] = agent_freeze.EXIT_LOCK_BUSY
        result = agent_freeze.freeze_pane(AGENT_PANE)
        self.assertFalse(result.ok)
        self.assertEqual(self.rec().state, agent_sessions.STATE_FREEZING)

    def test_a_nonce_mismatch_at_commit_touches_nothing(self):
        """reconcile already settled it — the pane is no longer ours.

        "Touches nothing" is about what happens AFTER the refusal: the respawn
        in step 5 has already run, so the assertion is that the coordinator adds
        no further tmux call — no unstamp, no second respawn — on top of it.
        Whatever settled the record owns the pane's state now, and a second
        actor writing there is exactly what the nonce guard exists to prevent.
        """
        self.store.fail_verbs["freeze-commit"] = agent_freeze.EXIT_NONCE_MISMATCH
        result = agent_freeze.freeze_pane(AGENT_PANE)
        self.assertEqual(result.line, f"NONCE_MISMATCH:{self.rid}")
        self.assertNotIn("freeze-abort", self.store.verbs())
        self.assertEqual(len(self.tmux.calls_of("respawn-pane")), 1,
                         "step 5's respawn only — never a second one")
        self.assertEqual(self.panes[AGENT_PANE][agent_freeze.FROZEN_OPTION],
                         self.rid,
                         "the stamp must be left exactly as it was")
        # The LAST tmux call is the post-respawn location read; nothing follows.
        self.assertEqual(self.tmux.calls[-1][0], "display-message")

    def test_the_seams_are_inert_without_test_mode(self):
        """A stray env var must never reconfigure a production freeze."""
        os.environ.pop("AITASKS_TEST_MODE")
        os.environ["AITASKS_FREEZE_FAIL_AT"] = "stamp"
        result = agent_freeze.freeze_pane(AGENT_PANE)
        self.assertTrue(result.ok, result.line)


class NonceGuardTests(unittest.TestCase):
    """Stale-nonce safety, driven against the STORE, with its negative control.

    Why this is not a live test: `_lease_stale` requires the owner to be DEAD,
    and a dead coordinator issues no further verbs — so for a correct
    coordinator a live `NONCE_MISMATCH` at commit is unreachable by
    construction. The one path that reaches it is the A7 anti-pattern (recording
    an ephemeral subshell's pid as the owner), which needs a seam that does not
    exist. The guard is therefore pinned here, where `lease_take`'s injectable
    `now=` / `pid_alive=` reach the state directly.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name)
        os.environ[agent_sessions.FROZEN_DIR_ENV] = str(tmp / "frozen")
        self.addCleanup(os.environ.pop, agent_sessions.FROZEN_DIR_ENV, None)
        self.now = time.time()
        self.sf = agent_sessions.SessionsFile()
        self.sf, line = agent_sessions.upsert(
            self.sf, root=str(tmp), window="agent-pick-1705",
            pane=AGENT_PANE, pane_pid=AGENT_PID,
            pane_alive=lambda pid: True, now=self.now,
        )
        self.rid = line.split(":")[1].split("|")[0]
        self.sf, begin = agent_sessions.freeze_begin(
            self.sf, self.rid, capture_ansi="/a", capture_txt="/b", lines=1,
            owner_pid=_reaped_pid(), now=self.now,
        )
        self.n1 = begin.split("|")[1]

    def test_a_stale_nonce_is_refused_on_a_freezing_record(self):
        """The guard, reached in the ONLY state where it is reachable.

        `lease_take` rotates the nonce and rewrites only the lease fields — the
        record stays `freezing`, which is exactly what `freeze_commit` requires,
        so `_require_state` passes and `_require_nonce` is what refuses.
        """
        self.sf, leased = agent_sessions.lease_take(
            self.sf, self.rid, owner_pid=999,
            now=self.now + agent_sessions.STALE_OP_GRACE_DEFAULT + 1,
            pid_alive=lambda _pid: False,
        )
        n2 = leased.split("|")[1]
        self.assertNotEqual(n2, self.n1)
        self.assertEqual(self.sf.by_id(self.rid).state,
                         agent_sessions.STATE_FREEZING,
                         "precondition: the state guard must NOT be what fires")

        before = copy.deepcopy(self.sf.by_id(self.rid))
        with self.assertRaises(agent_sessions.NonceMismatch):
            agent_sessions.freeze_commit(
                self.sf, self.rid, nonce=self.n1, pane=AGENT_PANE,
                pane_pid=STANDIN_PID, now=self.now,
            )
        self.assertEqual(vars(self.sf.by_id(self.rid)), vars(before),
                         "a refused commit must write NOTHING")

    def test_negative_control_a_live_record_refuses_on_STATE_not_nonce(self):
        """The reason this case moved out of the live suite.

        After a takeover that ends in `freeze-abort` the record is `live`, and
        `freeze_commit` checks state BEFORE nonce — so the same stale-nonce call
        raises `TransitionRefused`, never `NonceMismatch`. A live test written
        that way would have passed while pinning the wrong guard.
        """
        self.sf, _ = agent_sessions.freeze_abort(
            self.sf, self.rid, nonce=self.n1, now=self.now)
        self.assertEqual(self.sf.by_id(self.rid).state,
                         agent_sessions.STATE_LIVE)
        with self.assertRaises(agent_sessions.TransitionRefused):
            agent_sessions.freeze_commit(
                self.sf, self.rid, nonce=self.n1, pane=AGENT_PANE,
                pane_pid=STANDIN_PID, now=self.now,
            )


class StaleOpGraceSeamTests(unittest.TestCase):
    """`AITASKS_STALE_OP_GRACE` (t1705_4 step 4a) — timer half only."""

    def setUp(self) -> None:
        for var in ("AITASKS_TEST_MODE", "AITASKS_STALE_OP_GRACE"):
            os.environ.pop(var, None)
            self.addCleanup(os.environ.pop, var, None)

    def test_the_default_applies_without_test_mode(self):
        os.environ["AITASKS_STALE_OP_GRACE"] = "1"
        self.assertEqual(agent_sessions._stale_op_grace(),
                         agent_sessions.STALE_OP_GRACE_DEFAULT,
                         "a stray env var must never reconfigure production")

    def test_test_mode_honours_a_positive_override(self):
        os.environ["AITASKS_TEST_MODE"] = "1"
        os.environ["AITASKS_STALE_OP_GRACE"] = "1.5"
        self.assertEqual(agent_sessions._stale_op_grace(), 1.5)

    def test_a_non_positive_or_malformed_override_falls_back(self):
        os.environ["AITASKS_TEST_MODE"] = "1"
        for bad in ("0", "-5", "abc", ""):
            with self.subTest(value=bad):
                os.environ["AITASKS_STALE_OP_GRACE"] = bad
                self.assertEqual(agent_sessions._stale_op_grace(),
                                 agent_sessions.STALE_OP_GRACE_DEFAULT)

    def test_the_seam_never_shortens_the_LIVENESS_half(self):
        """`grace AND owner dead` — a live owner holds its lease forever.

        This is the assertion a grace-only implementation fails, and it is why
        the seam may be shortened at all: it makes the takeover races fast
        without making them permissive.
        """
        os.environ["AITASKS_TEST_MODE"] = "1"
        os.environ["AITASKS_STALE_OP_GRACE"] = "0.001"
        rec = agent_sessions.SessionRecord(
            id="7f3a2c1d", root="/tmp", window="w",
            op_nonce="aabbccdd", op_owner_pid=os.getpid(),
            op_started_at="2000-01-01T00:00:00Z",
        )
        self.assertFalse(
            agent_sessions._lease_stale(rec, now=time.time()),
            "a LIVE owner's lease must never be takeable, however old",
        )
        rec.op_owner_pid = _reaped_pid()
        self.assertTrue(agent_sessions._lease_stale(rec, now=time.time()))


class CaptureCapTests(_FreezeTestCase):
    def test_the_default_cap_applies_without_a_frozen_section(self):
        self.assertEqual(agent_freeze.capture_max_lines(self.root),
                         agent_freeze.DEFAULT_CAPTURE_MAX_LINES)

    def test_a_configured_cap_is_read_with_the_yaml_parser(self):
        cfg = self.root / "aitasks" / "metadata" / "project_config.yaml"
        cfg.write_text("frozen:\n  capture_max_lines: 1234\n")
        self.assertEqual(agent_freeze.capture_max_lines(self.root), 1234)

    def test_a_non_positive_cap_falls_back(self):
        """A cap of 0 would capture nothing and make every freeze silently lossy."""
        cfg = self.root / "aitasks" / "metadata" / "project_config.yaml"
        cfg.write_text("frozen:\n  capture_max_lines: 0\n")
        self.assertEqual(agent_freeze.capture_max_lines(self.root),
                         agent_freeze.DEFAULT_CAPTURE_MAX_LINES)

    def test_the_cap_reaches_the_capture_pane_argv(self):
        cfg = self.root / "aitasks" / "metadata" / "project_config.yaml"
        cfg.write_text("frozen:\n  capture_max_lines: 77\n")
        agent_freeze.freeze_pane(AGENT_PANE)
        capture = self.tmux.calls_of("capture-pane")[0]
        self.assertIn("-77", capture)
        for flag in ("-p", "-e", "-J"):
            self.assertIn(flag, capture)


class ReconcileTableTests(_FreezeTestCase):
    """The §C rows, driven through the fakes.

    Each case puts the record into a state and the pane into an observation, and
    asserts the transition (or, for the indeterminate rows, the ABSENCE of one).
    """

    def _observed(self, **overrides):
        pane = dict(
            session="aitasks", window="agent-pick-1705", pane_id=AGENT_PANE,
            pane_pid=AGENT_PID, pane_dead=False, path=str(self.root),
            frozen="", standin_ready="", record=self.rid,
        )
        pane.update(overrides)
        return agent_freeze._Observed(**pane)

    def _freezing(self):
        self.store.sf, line = agent_sessions.freeze_begin(
            self.store.sf, self.rid, capture_ansi="/a", capture_txt="/b",
            lines=1, owner_pid=os.getpid(),
        )
        return _FixedLease(line.split("|")[1])

    def test_stamped_and_ready_commits(self):
        lease = self._freezing()
        line = agent_freeze._reconcile_freezing(
            {"id": self.rid, "pane_pid": AGENT_PID},
            self._observed(frozen=self.rid, standin_ready=self.rid,
                           pane_pid=STANDIN_PID),
            lease,
        )
        self.assertEqual(line, f"FROZEN:{self.rid}")
        self.assertEqual(self.rec().state, agent_sessions.STATE_FROZEN)
        self.assertEqual(self.rec().standin_pid, STANDIN_PID)

    def test_agent_alive_and_no_ready_mark_aborts_back_to_live(self):
        lease = self._freezing()
        self.panes[AGENT_PANE][agent_freeze.FROZEN_OPTION] = self.rid
        line = agent_freeze._reconcile_freezing(
            {"id": self.rid, "pane_pid": AGENT_PID},
            self._observed(frozen=self.rid, pane_pid=AGENT_PID),
            lease,
        )
        self.assertEqual(line, f"LIVE:{self.rid}")
        self.assertEqual(self.rec().state, agent_sessions.STATE_LIVE)
        self.assertEqual(self.panes[AGENT_PANE][agent_freeze.FROZEN_OPTION], "",
                         "both options must be unstamped on the abort path")

    def test_the_indeterminate_row_makes_NO_transition(self):
        """Stamped, no ready mark, neither the agent's nor the viewer's pid.

        The viewer may simply still be booting. Transitioning here would abort a
        freeze that is about to succeed. Asserted TWICE — a single pass could
        pass by accident on an implementation that transitions on the second.
        """
        lease = self._freezing()
        observation = self._observed(frozen=self.rid, pane_pid=999999)
        for attempt in (1, 2):
            line = agent_freeze._reconcile_freezing(
                {"id": self.rid, "pane_pid": AGENT_PID}, observation, lease)
            self.assertEqual(line, f"INDETERMINATE:{self.rid}|freezing",
                             f"pass {attempt}")
            self.assertEqual(self.rec().state, agent_sessions.STATE_FREEZING,
                             f"pass {attempt}: the state must be unchanged")
        self.assertEqual(lease.calls, 0,
                         "an indeterminate row takes NO action, so it must not "
                         "lease either — lease-take writes, and nothing clears "
                         "the lease afterwards")

    def test_a_dead_standin_pane_is_respawned(self):
        lease = self._freezing()
        line = agent_freeze._reconcile_freezing(
            {"id": self.rid, "pane_pid": AGENT_PID},
            self._observed(frozen=self.rid, pane_dead=True, pane_pid=999999),
            lease,
        )
        self.assertEqual(line, f"STANDIN:{self.rid}")
        self.assertEqual(len(self.tmux.calls_of("respawn-pane")), 1)

    def test_a_gone_pane_commits_with_the_gone_pane_pair(self):
        lease = self._freezing()
        line = agent_freeze._reconcile_freezing(
            {"id": self.rid, "pane_pid": AGENT_PID}, None, lease)
        self.assertEqual(line, f"FROZEN:{self.rid}|pane_gone")
        commit = next(c for c in self.store.calls if c[0] == "freeze-commit")
        self.assertEqual(commit[commit.index("--pane") + 1], "")
        self.assertEqual(commit[commit.index("--pane-pid") + 1], "0")

    def test_a_frozen_record_with_a_gone_pane_is_kept(self):
        """It stays restorable into a NEW window — never dropped here."""
        lease = _FixedLease("aabbccdd")
        line = agent_freeze._reconcile_frozen({"id": self.rid}, None, lease)
        self.assertEqual(line, f"KEEP:{self.rid}|pane_gone")
        self.assertEqual(lease.calls, 0, "a KEEP row must not lease")

    def test_a_healthy_frozen_record_is_never_leased(self):
        """The lazy-lease rule, stated where it matters most.

        `frozen` is the steady state: most records are in it, reconcile runs
        every 600 s, and `lease-take` both writes the record and leaves it
        leased by a pid that is about to exit. A real coordinator needing a
        nonce for that record would then be refused until the grace elapsed —
        reconcile locking out the work it exists to enable.
        """
        lease = _FixedLease("aabbccdd")
        line = agent_freeze._reconcile_frozen(
            {"id": self.rid},
            self._observed(frozen=self.rid, standin_ready=self.rid,
                           pane_pid=STANDIN_PID),
            lease,
        )
        self.assertEqual(line, f"KEEP:{self.rid}|frozen")
        self.assertEqual(lease.calls, 0)

    def test_the_ready_mark_is_cleared_BEFORE_every_respawn(self):
        """Otherwise the previous viewer's mark reads as the new one's proof."""
        lease = self._freezing()
        self.panes[AGENT_PANE][agent_freeze.STANDIN_READY_OPTION] = "deadbeef"
        agent_freeze._respawn_standin(AGENT_PANE, self.rid, lease)
        order = [c[0] for c in self.tmux.calls
                 if c[0] in ("set-option", "respawn-pane")]
        self.assertEqual(order[0], "set-option")
        self.assertLess(order.index("set-option"), order.index("respawn-pane"))
        self.assertEqual(
            self.panes[AGENT_PANE][agent_freeze.STANDIN_READY_OPTION], "")


class ReconcileRestoringTests(_FreezeTestCase):
    """The `restoring` rows of the §C table.

    Nothing can PRODUCE a `restoring` record until t1705_5 ships
    `restore-begin`'s caller, so these rows are unreachable in a live run today
    and the live suite cannot cover them. They are implemented and tested here
    because reconcile owns the whole table: a record left `restoring` by a dead
    coordinator has to be settled by something, and reconcile is the only thing
    that runs.

    Every giving-up branch ends the same way — `restore-abort` (→ `aborting`),
    then the stand-in back and `standin-respawned` (→ `frozen`) — so the record
    stays restorable and THE CAPTURE SURVIVES. A failed restore must never cost
    the user the session it was trying to bring back.
    """

    def _restoring(self, *, mode="resume"):
        """Put the record into `restoring` and return (nonce, record dict)."""
        self.store.sf, line = agent_sessions.freeze_begin(
            self.store.sf, self.rid, capture_ansi="/a", capture_txt="/b",
            lines=1, owner_pid=os.getpid())
        n = line.split("|")[1]
        self.store.sf, _ = agent_sessions.freeze_commit(
            self.store.sf, self.rid, nonce=n, pane=AGENT_PANE,
            pane_pid=STANDIN_PID)
        self.store.sf, line = agent_sessions.restore_begin(
            self.store.sf, self.rid, mode=mode, owner_pid=os.getpid())
        return line.split("|")[1]

    def _lease_for(self, nonce):
        return _FixedLease(nonce)

    def _rec(self):
        return {k: str(v) for k, v in vars(self.store.sf.by_id(self.rid)).items()}

    def _observed(self, **overrides):
        pane = dict(
            session="aitasks", window="agent-pick-1705", pane_id=AGENT_PANE,
            pane_pid=AGENT_PID, pane_dead=False, path=str(self.root),
            frozen=self.rid, standin_ready="", record=self.rid,
        )
        pane.update(overrides)
        return agent_freeze._Observed(**pane)

    def test_a_session_mismatch_aborts_and_restores_the_standin(self):
        """The hook's report IS the coordinator's return channel — obey it."""
        nonce = self._restoring()
        rec = self._rec()
        rec["last_error"] = f"{nonce}:session_mismatch"
        rec["op_nonce"] = nonce
        line = agent_freeze._reconcile_restoring(
            rec, self._observed(pane_pid=12345), _FixedLease(nonce), time.time())
        self.assertEqual(line, f"STANDIN:{self.rid}")
        self.assertEqual(self.rec().state, agent_sessions.STATE_FROZEN)
        self.assertIn("restore-abort", self.store.verbs())
        self.assertNotIn("restore-confirm", self.store.verbs(),
                         "a reported mismatch must NEVER be liveness-confirmed")

    def test_the_capture_survives_a_failed_restore(self):
        nonce = self._restoring()
        agent_sessions.ensure_capture_dir(self.rid)
        agent_freeze._reconcile_restoring(
            self._rec(), self._observed(pane_dead=True), _FixedLease(nonce), time.time())
        self.assertTrue(
            (Path(os.environ[agent_sessions.FROZEN_DIR_ENV]) / self.rid).exists(),
            "the capture is the only copy of the session being restored",
        )

    def test_the_viewer_still_in_the_pane_means_the_respawn_never_happened(self):
        nonce = self._restoring()
        line = agent_freeze._reconcile_restoring(
            self._rec(), self._observed(pane_pid=STANDIN_PID),
            _FixedLease(nonce), time.time())
        self.assertEqual(line, f"STANDIN:{self.rid}")
        self.assertEqual(self.rec().state, agent_sessions.STATE_FROZEN)

    def test_a_dead_pane_aborts_back_to_frozen(self):
        nonce = self._restoring()
        line = agent_freeze._reconcile_restoring(
            self._rec(), self._observed(pane_dead=True, pane_pid=999999),
            _FixedLease(nonce), time.time())
        self.assertEqual(line, f"STANDIN:{self.rid}")
        self.assertEqual(self.rec().state, agent_sessions.STATE_FROZEN)

    def test_a_gone_pane_aborts_with_the_gone_pane_pair(self):
        nonce = self._restoring()
        line = agent_freeze._reconcile_restoring(
            self._rec(), None, _FixedLease(nonce), time.time())
        self.assertEqual(line, f"STANDIN:{self.rid}|pane_gone")
        rec = self.rec()
        self.assertEqual(rec.state, agent_sessions.STATE_FROZEN)
        self.assertEqual(rec.pane_id, "")

    def test_the_replacement_is_confirmed_only_after_the_ack_grace(self):
        """The hook ack is stronger evidence, so do not race it."""
        nonce = self._restoring()
        self.store.sf, _ = agent_sessions.restore_launched(
            self.store.sf, self.rid, nonce=nonce, pane=AGENT_PANE,
            pane_pid=7777)
        rec = self._rec()
        observed = self._observed(pane_pid=7777)

        line = agent_freeze._reconcile_restoring(rec, observed,
                                                 _FixedLease(nonce), time.time())
        self.assertEqual(line, f"INDETERMINATE:{self.rid}|restoring_ack_grace")
        self.assertEqual(self.rec().state, agent_sessions.STATE_RESTORING)

        later = time.time() + agent_freeze.RESTORE_ACK_GRACE + 1
        line = agent_freeze._reconcile_restoring(rec, observed, _FixedLease(nonce), later)
        self.assertEqual(line, f"LIVE:{self.rid}|liveness")
        confirmed = self.rec()
        self.assertEqual(confirmed.state, agent_sessions.STATE_LIVE)
        self.assertEqual(confirmed.ack, "liveness")

    def test_a_liveness_confirm_KEEPS_the_captures(self):
        """`ack=liveness` is weaker evidence, so the only copy is retained."""
        nonce = self._restoring()
        agent_sessions.ensure_capture_dir(self.rid)
        self.store.sf, _ = agent_sessions.restore_launched(
            self.store.sf, self.rid, nonce=nonce, pane=AGENT_PANE,
            pane_pid=7777)
        agent_freeze._reconcile_restoring(
            self._rec(), self._observed(pane_pid=7777), _FixedLease(nonce),
            time.time() + agent_freeze.RESTORE_ACK_GRACE + 1)
        self.assertEqual(self.rec().ack, "liveness")
        self.assertTrue(
            (Path(os.environ[agent_sessions.FROZEN_DIR_ENV]) / self.rid).exists())

    def test_an_unrecognised_pane_is_indeterminate_until_twice_the_grace(self):
        """`launch_pid == 0`: the respawn may be mid-flight."""
        nonce = self._restoring()
        rec = self._rec()
        observed = self._observed(pane_pid=424242)

        line = agent_freeze._reconcile_restoring(rec, observed,
                                                 _FixedLease(nonce), time.time())
        self.assertEqual(line, f"INDETERMINATE:{self.rid}|restoring")
        self.assertEqual(self.rec().state, agent_sessions.STATE_RESTORING,
                         "an indeterminate row must make NO transition")

        later = time.time() + 2 * agent_sessions.STALE_OP_GRACE_DEFAULT + 1
        line = agent_freeze._reconcile_restoring(rec, observed, _FixedLease(nonce), later)
        self.assertEqual(line, f"STANDIN:{self.rid}")
        self.assertEqual(self.rec().state, agent_sessions.STATE_FROZEN)


class ReconcileEnumerationTests(_FreezeTestCase):
    """The fail-closed observation rule (step 5).

    A `ROOT` row is an ASSERTION OF COVERAGE. `purge`'s `dead_window` rule drops
    every `live` record whose root is present but whose window is not, so a
    `ROOT` row for a root that was never successfully enumerated destroys other
    projects' records. These cases pin the rule that makes that unreachable.
    """

    def _read(self, path):
        return Path(path).read_text().splitlines()

    def test_a_failed_enumeration_suppresses_the_ROOT_row(self):
        path = agent_freeze._write_observation(
            {"/p/a": True, "/p/b": False},
            {"/p/a": [agent_freeze._Observed(
                "s", "agent-pick-1", "%1", 10, False, "/p/a", "", "", "")]},
        )
        self.addCleanup(os.unlink, path)
        rows = self._read(path)
        self.assertIn("ROOT\t/p/a", rows)
        self.assertNotIn("ROOT\t/p/b", rows,
                         "an unenumerated root must never be presented as "
                         "covered — purge would drop its live records")
        self.assertIn("INCOMPLETE", rows)

    def test_a_fully_enumerated_run_writes_no_INCOMPLETE(self):
        path = agent_freeze._write_observation(
            {"/p/a": True},
            {"/p/a": [agent_freeze._Observed(
                "s", "agent-pick-1", "%1", 10, False, "/p/a", "", "", "")]},
        )
        self.addCleanup(os.unlink, path)
        rows = self._read(path)
        self.assertNotIn("INCOMPLETE", rows)
        self.assertIn("WINDOW\t/p/a\tagent-pick-1", rows)
        self.assertIn("PANE\t/p/a\tagent-pick-1\t%1\t10\t0", rows)

    def test_pane_rows_carry_the_dead_flag(self):
        path = agent_freeze._write_observation(
            {"/p/a": True},
            {"/p/a": [agent_freeze._Observed(
                "s", "agent-pick-1", "%1", 10, True, "/p/a", "", "", "")]},
        )
        self.addCleanup(os.unlink, path)
        self.assertIn("PANE\t/p/a\tagent-pick-1\t%1\t10\t1", self._read(path))

    def test_a_root_covered_by_two_sessions_needs_BOTH_to_succeed(self):
        """`and` never upgrades a prior failure — the same fail-closed rule."""
        roots = {}
        for ok in (True, False):
            roots["/p/a"] = roots.get("/p/a", True) and ok
        self.assertFalse(roots["/p/a"])

    def test_the_enumeration_pass_is_explicitly_targeted(self):
        """`-t` is load-bearing: untargeted `list-panes -s` means the CURRENT
        session, and reconcile runs detached where that is arbitrary."""
        agent_freeze._enumerate_session("aitasks")
        call = self.tmux.calls_of("list-panes")[-1]
        self.assertIn("-t", call)
        self.assertEqual(call[call.index("-t") + 1], "=aitasks",
                         "the target must be the EXACT-match form")

    def test_a_failed_enumeration_reports_not_ok_and_no_panes(self):
        class _Failing(_FakeTmux):
            def run(self, args, timeout=None):
                self.calls.append(list(args))
                if args and args[0] == "list-panes":
                    return 1, ""
                return super().run(args, timeout)

        self._install(_Failing(self.panes), self.store)
        ok, panes = agent_freeze._enumerate_session("aitasks")
        self.assertFalse(ok)
        self.assertEqual(panes, [])


class FreezeAllSelectionTests(_FreezeTestCase):
    """Freeze-All must never act on a helper pane.

    `classify_pane` reads only the WINDOW NAME, so a companion minimonitor in an
    `agent-*` window classifies as AGENT. Selecting on the category alone would
    respawn every companion the freeze design exists to preserve. The live suite
    owns the tmux-level proof; this pins that the selection goes through
    `discover_panes()` at all.
    """

    def test_selection_uses_the_discovery_contract(self):
        seen = {}

        class _Monitor:
            def __init__(self, session, **kw):
                seen["session"] = session
                seen["kw"] = kw

            def discover_panes(self):
                seen["called"] = True
                return []

        prev = agent_freeze.TmuxMonitor
        agent_freeze.TmuxMonitor = _Monitor
        self.addCleanup(setattr, agent_freeze, "TmuxMonitor", prev)
        agent_freeze._agent_panes_for("aitasks")
        self.assertTrue(seen.get("called"),
                        "Freeze-All must call discover_panes(), never "
                        "list-panes + classify_pane")
        self.assertEqual(seen["session"], "aitasks")

    def test_already_frozen_and_non_agent_panes_are_skipped(self):
        from monitor.monitor_core import PaneCategory, TmuxPaneInfo

        def info(pane_id, category, frozen=""):
            return TmuxPaneInfo(
                window_index="1", window_name="agent-pick-1705", pane_index="0",
                pane_id=pane_id, pane_pid=1, current_command="node", width=80,
                height=24, category=category, session_name="aitasks",
                frozen_record=frozen,
            )

        panes = [
            info("%1", PaneCategory.AGENT),
            info("%2", PaneCategory.AGENT, frozen="deadbeef"),
            info("%3", PaneCategory.TUI),
        ]
        frozen_panes = []
        self.addCleanup(setattr, agent_freeze, "freeze_pane",
                        agent_freeze.freeze_pane)
        self.addCleanup(setattr, agent_freeze, "_agent_panes_for",
                        agent_freeze._agent_panes_for)
        self.addCleanup(setattr, agent_freeze, "discover_aitasks_sessions",
                        agent_freeze.discover_aitasks_sessions)

        class _Session:
            session = "aitasks"
            project_root = Path("/p")

        agent_freeze.discover_aitasks_sessions = lambda **kw: [_Session()]
        agent_freeze._agent_panes_for = lambda s: panes
        agent_freeze.freeze_pane = lambda pane_id, **kw: (
            frozen_panes.append(pane_id)
            or FakeResult(pane_id)
        )

        class FakeResult:
            def __init__(self, pane_id):
                self.ok = True
                self.line = f"FROZEN:{pane_id}"
                self.record_id = pane_id
                self.stage = "commit"

        agent_freeze.freeze_all()
        self.assertEqual(frozen_panes, ["%1"],
                         "only the live, unfrozen AGENT pane may be frozen")


if __name__ == "__main__":
    unittest.main(verbosity=2)
