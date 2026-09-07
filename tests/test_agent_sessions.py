"""Store + serialization tests for the framework session primitive (t1705_2).

Covers `.aitask-scripts/lib/agent_sessions.py`'s schema, parse strictness,
atomic dump and path resolution with no tmux, no Textual and no event loop —
the module is deliberately free of those imports so this suite can exercise
persistence directly. The identity policy, lease, state machine, observation
protocol and purge each get their own module; this one is the foundation.

Two groups here are not routine round-trip coverage and must not be thinned:

  * `StoreModeTests` pins the 0600/0700 file modes under a PERMISSIVE umask.
    `atomic_write.target_mode()` defaults a not-yet-existing file to
    `0o666 & ~umask`, so a "simplification" that routes `dump()` through
    `atomic_write_text` lands the store world-readable — and it holds transcript
    paths and codeagent session ids. Setting umask to 000 is what makes the
    difference visible; at the default 022 a broken implementation still yields
    0644 and looks merely odd rather than wrong.
  * `IdentifierValidationTests` pins the 8-hex constraint on ids and nonces.
    Both escape into `capture_dir()` — whose `drop` DELETES the tree — and into
    `standin_command()`, whose output is handed to `respawn-pane` as a shell
    command string.
"""
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

import agent_sessions  # noqa: E402


class _StoreTestCase(unittest.TestCase):
    """Gives each test an isolated store path and frozen dir under a temp dir."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.store = self.tmp / "agent_sessions.json"
        self.frozen = self.tmp / "frozen"
        os.environ[agent_sessions.FROZEN_DIR_ENV] = str(self.frozen)
        self.addCleanup(os.environ.pop, agent_sessions.FROZEN_DIR_ENV, None)
        self.addCleanup(self._tmp.cleanup)

    def seeded(self, *, window="agent-pick-1", root=None, **kw):
        """A store holding one live record, plus that record."""
        sf = agent_sessions.load(self.store)
        sf, line = agent_sessions.upsert(
            sf,
            root=root or str(self.tmp),
            window=window,
            pane="%1",
            pane_pid=4242,
            pane_alive=lambda pid: True,
            **kw,
        )
        rid = line.split(":")[1].split("|")[0]
        return sf, sf.by_id(rid)


class PathResolutionTests(_StoreTestCase):
    def test_env_override_wins_over_default(self):
        os.environ[agent_sessions.SESSIONS_ENV] = str(self.store)
        self.addCleanup(os.environ.pop, agent_sessions.SESSIONS_ENV, None)
        self.assertEqual(agent_sessions.sessions_path(), self.store)

    def test_explicit_arg_wins_over_env(self):
        os.environ[agent_sessions.SESSIONS_ENV] = "/nowhere/x.json"
        self.addCleanup(os.environ.pop, agent_sessions.SESSIONS_ENV, None)
        self.assertEqual(agent_sessions.sessions_path(self.store), self.store)

    def test_default_is_under_config_aitasks(self):
        os.environ.pop(agent_sessions.SESSIONS_ENV, None)
        self.assertEqual(
            agent_sessions.sessions_path(),
            Path(os.path.expanduser("~/.config/aitasks/agent_sessions.json")),
        )

    def test_frozen_root_follows_env(self):
        self.assertEqual(agent_sessions.frozen_root(), self.frozen)


class RoundTripTests(_StoreTestCase):
    def test_missing_file_is_an_empty_store(self):
        sf = agent_sessions.load(self.store)
        self.assertEqual(sf.sessions, [])
        self.assertEqual(sf.version, agent_sessions.SCHEMA_VERSION)

    def test_empty_file_is_an_empty_store(self):
        self.store.write_text("   \n", encoding="utf-8")
        self.assertEqual(agent_sessions.load(self.store).sessions, [])

    def test_every_field_survives_a_round_trip(self):
        sf, rec = self.seeded(
            session="aitasks",
            session_id="abc-123",
            transcript="/t/x.jsonl",
            agent_string="claudecode/opus5",
            operation="pick",
            task_id="1705_2",
        )
        agent_sessions.dump(sf, self.store)
        back = agent_sessions.load(self.store).by_id(rec.id)
        self.assertEqual(vars(back), vars(rec))

    def test_dump_sorts_by_root_window_slot(self):
        sf = agent_sessions.load(self.store)
        for window in ("agent-c", "agent-a", "agent-b"):
            sf, _ = agent_sessions.upsert(
                sf, root=str(self.tmp), window=window, pane=f"%{window}",
                pane_pid=1, pane_alive=lambda pid: True,
            )
        agent_sessions.dump(sf, self.store)
        payload = json.loads(self.store.read_text(encoding="utf-8"))
        windows = [s["window"] for s in payload["sessions"]]
        self.assertEqual(windows, sorted(windows))

    def test_symlinked_root_matches_a_resolved_lookup(self):
        """realpath on BOTH sides — the classic two-spellings-one-repo trap."""
        real = self.tmp / "real"
        real.mkdir()
        link = self.tmp / "link"
        link.symlink_to(real)
        sf, rec = self.seeded(root=str(link))
        self.assertEqual(rec.root, os.path.realpath(str(real)))
        agent_sessions.dump(sf, self.store)
        self.assertEqual(
            agent_sessions.load(self.store).sessions[0].root,
            os.path.realpath(str(real)),
        )


class ParseRejectionTests(_StoreTestCase):
    def _write(self, payload) -> None:
        self.store.write_text(json.dumps(payload), encoding="utf-8")

    def _record(self, **overrides):
        base = {"id": "aabbccdd", "root": "/r", "window": "w"}
        base.update(overrides)
        return {"version": 1, "sessions": [base]}

    def test_invalid_json(self):
        self.store.write_text("{not json", encoding="utf-8")
        with self.assertRaises(agent_sessions.MalformedSessionsError):
            agent_sessions.load(self.store)

    def test_top_level_not_an_object(self):
        self._write([])
        with self.assertRaises(agent_sessions.MalformedSessionsError):
            agent_sessions.load(self.store)

    def test_missing_version(self):
        self._write({"sessions": []})
        with self.assertRaises(agent_sessions.MalformedSessionsError):
            agent_sessions.load(self.store)

    def test_version_from_the_future_is_refused_not_truncated(self):
        self._write({"version": agent_sessions.SCHEMA_VERSION + 1, "sessions": []})
        with self.assertRaises(agent_sessions.MalformedSessionsError):
            agent_sessions.load(self.store)

    def test_sessions_not_a_list(self):
        self._write({"version": 1, "sessions": {}})
        with self.assertRaises(agent_sessions.MalformedSessionsError):
            agent_sessions.load(self.store)

    def test_unknown_state_is_corruption_not_a_default(self):
        """A silent default would move a frozen agent back into the live pool."""
        self._write(self._record(state="thawing"))
        with self.assertRaises(agent_sessions.MalformedSessionsError):
            agent_sessions.load(self.store)

    def test_empty_root_and_window_rejected(self):
        for field in ("root", "window"):
            with self.subTest(field=field):
                self._write(self._record(**{field: ""}))
                with self.assertRaises(agent_sessions.MalformedSessionsError):
                    agent_sessions.load(self.store)

    def test_non_int_field_rejected(self):
        self._write(self._record(pane_pid="41233"))
        with self.assertRaises(agent_sessions.MalformedSessionsError):
            agent_sessions.load(self.store)

    def test_bad_restore_mode_rejected(self):
        self._write(self._record(restore_mode="rewind"))
        with self.assertRaises(agent_sessions.MalformedSessionsError):
            agent_sessions.load(self.store)

    def test_duplicate_id_first_wins(self):
        self._write({
            "version": 1,
            "sessions": [
                {"id": "aabbccdd", "root": "/r", "window": "first"},
                {"id": "aabbccdd", "root": "/r", "window": "second"},
            ],
        })
        sf = agent_sessions.load(self.store)
        self.assertEqual([r.window for r in sf.sessions], ["first"])

    def test_load_safe_never_raises(self):
        self.store.write_text("{not json", encoding="utf-8")
        self.assertEqual(agent_sessions.load_safe(self.store).sessions, [])

    def test_load_safe_on_a_directory(self):
        d = self.tmp / "adir"
        d.mkdir()
        self.assertEqual(agent_sessions.load_safe(d).sessions, [])


class IdentifierValidationTests(_StoreTestCase):
    """8-hex ids/nonces — the guard on `capture_dir` and `standin_command`."""

    def test_valid_id_shape(self):
        self.assertTrue(agent_sessions.valid_id("7f3a2c1d"))
        for bad in ("", "7F3A2C1D", "7f3a2c1", "7f3a2c1dd", "../../etc", "7f3a2c1g"):
            with self.subTest(bad=bad):
                self.assertFalse(agent_sessions.valid_id(bad))

    def test_traversal_id_in_the_store_fails_to_load(self):
        self.store.write_text(
            json.dumps({
                "version": 1,
                "sessions": [{"id": "../../etc", "root": "/r", "window": "w"}],
            }),
            encoding="utf-8",
        )
        with self.assertRaises(agent_sessions.MalformedSessionsError):
            agent_sessions.load(self.store)

    def test_non_canonical_nonce_in_the_store_fails_to_load(self):
        self.store.write_text(
            json.dumps({
                "version": 1,
                "sessions": [
                    {"id": "aabbccdd", "root": "/r", "window": "w", "op_nonce": "zz"}
                ],
            }),
            encoding="utf-8",
        )
        with self.assertRaises(agent_sessions.MalformedSessionsError):
            agent_sessions.load(self.store)

    def test_empty_nonce_is_legal_it_means_no_lease(self):
        self.store.write_text(
            json.dumps({
                "version": 1,
                "sessions": [
                    {"id": "aabbccdd", "root": "/r", "window": "w", "op_nonce": ""}
                ],
            }),
            encoding="utf-8",
        )
        self.assertEqual(agent_sessions.load(self.store).sessions[0].op_nonce, "")

    def test_capture_dir_rejects_a_traversal_id(self):
        with self.assertRaises(ValueError):
            agent_sessions.capture_dir("../../etc")

    def test_capture_dir_stays_under_the_frozen_root(self):
        d = agent_sessions.capture_dir("7f3a2c1d")
        self.assertTrue(
            str(os.path.realpath(d)).startswith(
                str(os.path.realpath(self.frozen)) + os.sep
            )
        )

    def test_standin_command_rejects_a_non_canonical_id(self):
        """The output is handed to respawn-pane as a SHELL COMMAND STRING."""
        with self.assertRaises(ValueError):
            agent_sessions.standin_command("a'; rm -rf /; echo '")

    def test_standin_command_round_trips_a_hex_id(self):
        self.assertEqual(
            agent_sessions.standin_command("7f3a2c1d"),
            "ait frozenagent --record 7f3a2c1d",
        )

    def test_standin_command_test_seam(self):
        os.environ[agent_sessions.STANDIN_CMD_ENV] = "sleep 999"
        self.addCleanup(os.environ.pop, agent_sessions.STANDIN_CMD_ENV, None)
        self.assertEqual(agent_sessions.standin_command("7f3a2c1d"), "sleep 999")


class StoreModeTests(_StoreTestCase):
    """File/dir modes under a PERMISSIVE umask. See this module's docstring."""

    def setUp(self) -> None:
        super().setUp()
        old = os.umask(0)
        self.addCleanup(os.umask, old)

    def _mode(self, path) -> int:
        return stat.S_IMODE(os.stat(path).st_mode)

    def test_first_ever_dump_lands_0600_under_umask_000(self):
        sf, _ = self.seeded()
        agent_sessions.dump(sf, self.store)
        self.assertEqual(self._mode(self.store), 0o600)

    def test_an_existing_mode_is_preserved(self):
        sf, _ = self.seeded()
        agent_sessions.dump(sf, self.store)
        os.chmod(self.store, 0o640)
        agent_sessions.dump(sf, self.store)
        self.assertEqual(self._mode(self.store), 0o640)

    def test_capture_dir_lands_0700_under_umask_000(self):
        d = agent_sessions.ensure_capture_dir("7f3a2c1d")
        self.assertEqual(self._mode(d), 0o700)

    def test_dump_follows_a_symlinked_store_rather_than_replacing_it(self):
        """os.replace on the link itself would orphan the backing file."""
        real = self.tmp / "real.json"
        link = self.tmp / "link.json"
        real.write_text("", encoding="utf-8")
        link.symlink_to(real)
        sf, rec = self.seeded()
        agent_sessions.dump(sf, link)
        self.assertTrue(link.is_symlink())
        self.assertEqual(agent_sessions.load(real).by_id(rec.id).id, rec.id)


class AgentKindTests(unittest.TestCase):
    def test_prefix_of_a_well_formed_agent_string(self):
        self.assertEqual(agent_sessions.agent_kind_of("claudecode/opus5"), "claudecode")

    def test_malformed_is_empty_never_fatal(self):
        """A new agent must not make the store reject a record."""
        for bad in ("", None, "claudecode", "Claude/Opus5", "a/b/c"):
            with self.subTest(bad=bad):
                self.assertEqual(agent_sessions.agent_kind_of(bad), "")

    def test_unknown_but_well_formed_agent_is_accepted(self):
        self.assertEqual(agent_sessions.agent_kind_of("newagent/m1"), "newagent")


class CliPersistenceTests(_StoreTestCase):
    """Does the CLI actually WRITE what the transitions decided?

    The transition tests exercise pure functions and assert against the
    in-memory store, so they cannot see a CLI layer that computes the right
    result and then fails to persist it. That gap was real: the exception
    handler returned the exit code for every refusal without dumping, which
    silently discarded the ONE refusal that is required to persist —
    `SessionMismatch`. The unit test passed; the wire behaviour was wrong.

    So these drive `main()` and read the file back.
    """

    def run_cli(self, *argv):
        import agent_sessions as mod
        return mod.main(["--file", str(self.store), *argv])

    def _frozen_record(self, session_id="real-sid"):
        rc = self.run_cli(
            "upsert", "--root", str(self.tmp), "--window", "w",
            "--pane", "%1", "--pane-pid", "1", "--session-id", session_id,
        )
        self.assertEqual(rc, 0)
        rid = agent_sessions.load(self.store).sessions[0].id
        rec = agent_sessions.load(self.store)
        sf, line = agent_sessions.freeze_begin(
            rec, rid, capture_ansi="/a", capture_txt="/b", lines=1,
            owner_pid=os.getpid(),
        )
        nonce = line.split("|")[1]
        sf, _ = agent_sessions.freeze_commit(
            sf, rid, nonce=nonce, pane="%1", pane_pid=1
        )
        agent_sessions.dump(sf, self.store)
        return rid

    def test_a_session_mismatch_PERSISTS_last_error(self):
        """§A/§D: the record is the coordinator's only channel from the hook.

        Losing this write is not a cosmetic miss — the coordinator polls for it,
        times out, and takes the LIVENESS branch instead, confirming a pane that
        is running a different session than the one being restored.
        """
        rid = self._frozen_record(session_id="real-sid")
        sf = agent_sessions.load(self.store)
        sf, line = agent_sessions.restore_begin(
            sf, rid, mode="resume", owner_pid=os.getpid()
        )
        nonce = line.split("|")[1]
        agent_sessions.dump(sf, self.store)

        rc = self.run_cli(
            "upsert", "--root", str(self.tmp), "--window", "w",
            "--pane", "%2", "--pane-pid", "2",
            "--restore-of", rid, "--nonce", nonce, "--session-id", "WRONG",
        )
        self.assertEqual(rc, 7)
        # Read it back off DISK — the whole point of this class.
        rec = agent_sessions.load(self.store).by_id(rid)
        self.assertEqual(rec.last_error, f"{nonce}:session_mismatch")
        self.assertEqual(rec.state, agent_sessions.STATE_RESTORING)

    def test_a_transition_refusal_persists_NOTHING(self):
        rid = self._frozen_record()
        before = self.store.read_bytes()
        rc = self.run_cli(
            "freeze-commit", rid, "--nonce", "aabbccdd", "--pane", "%9",
            "--pane-pid", "9",
        )
        self.assertEqual(rc, 5)
        self.assertEqual(self.store.read_bytes(), before)

    def test_a_nonce_mismatch_persists_NOTHING(self):
        rid = self._frozen_record()
        sf = agent_sessions.load(self.store)
        sf, _ = agent_sessions.restore_begin(
            sf, rid, mode="resume", owner_pid=os.getpid()
        )
        agent_sessions.dump(sf, self.store)
        before = self.store.read_bytes()
        rc = self.run_cli(
            "restore-launched", rid, "--nonce", "deadbeef", "--pane", "%9",
            "--pane-pid", "9",
        )
        self.assertEqual(rc, 6)
        self.assertEqual(self.store.read_bytes(), before)

    def test_a_successful_transition_is_persisted(self):
        rid = self._frozen_record()
        rc = self.run_cli("drop", rid)
        self.assertEqual(rc, 0)
        self.assertEqual(agent_sessions.load(self.store).sessions, [])

    def test_a_usage_error_persists_nothing_and_exits_2(self):
        rid = self._frozen_record()
        before = self.store.read_bytes()
        self.assertEqual(self.run_cli("lease-take", rid), 2)  # no --owner-pid
        self.assertEqual(self.run_cli("drop", "../../etc"), 2)
        self.assertEqual(self.store.read_bytes(), before)

    def test_a_bare_file_flag_is_a_usage_error_not_a_traceback(self):
        """`--file` is parsed ABOVE the try block, so it must bounds-check.

        Automation calling the documented direct CLI path deserves the stated
        exit 2, not an IndexError traceback.
        """
        import agent_sessions as mod
        self.assertEqual(mod.main(["--file"]), 2)


class PanePairTests(_StoreTestCase):
    """`--pane` / `--pane-pid` must be a COHERENT pair, not merely both present.

    Exactly two shapes are legal: a real pane (`%N` + positive pid), or the
    gone-pane pair (`""` + `0`) that reconcile commits when the pane vanished.
    A mixed pair persists a location that cannot exist — a live pid at no pane,
    or a pane with no process. `freeze_commit` writes `pane_id`, `pane_pid` AND
    `standin_pid` from it, so once stored, reconcile can never match the record
    against a real pane again and it is stranded in `frozen` with no way back.
    """

    def run_cli(self, *argv):
        import agent_sessions as mod
        return mod.main(["--file", str(self.store), *argv])

    def _freezing(self):
        self.assertEqual(
            self.run_cli("upsert", "--root", str(self.tmp), "--window", "w",
                         "--pane", "%1", "--pane-pid", "1"), 0)
        rid = agent_sessions.load(self.store).sessions[0].id
        sf, line = agent_sessions.freeze_begin(
            agent_sessions.load(self.store), rid, capture_ansi="/a",
            capture_txt="/b", lines=1, owner_pid=os.getpid(),
        )
        agent_sessions.dump(sf, self.store)
        return rid, line.split("|")[1]

    def test_empty_pane_with_a_live_pid_is_refused(self):
        """THE reported shape: `--pane '' --pane-pid 123`."""
        rid, nonce = self._freezing()
        before = self.store.read_bytes()
        rc = self.run_cli("freeze-commit", rid, "--nonce", nonce,
                          "--pane", "", "--pane-pid", "123")
        self.assertEqual(rc, 2)
        self.assertEqual(self.store.read_bytes(), before)

    def test_a_real_pane_with_pid_zero_is_refused(self):
        rid, nonce = self._freezing()
        rc = self.run_cli("freeze-commit", rid, "--nonce", nonce,
                          "--pane", "%5", "--pane-pid", "0")
        self.assertEqual(rc, 2)

    def test_a_negative_pid_is_refused(self):
        rid, nonce = self._freezing()
        rc = self.run_cli("freeze-commit", rid, "--nonce", nonce,
                          "--pane", "%5", "--pane-pid", "-1")
        self.assertEqual(rc, 2)

    def test_the_gone_pane_pair_is_accepted(self):
        """CONTROL: reconcile's legitimate commit for a vanished pane."""
        rid, nonce = self._freezing()
        rc = self.run_cli("freeze-commit", rid, "--nonce", nonce,
                          "--pane", "", "--pane-pid", "0")
        self.assertEqual(rc, 0)
        rec = agent_sessions.load(self.store).by_id(rid)
        self.assertEqual((rec.pane_id, rec.pane_pid, rec.standin_pid), ("", 0, 0))

    def test_a_real_pane_pair_is_accepted(self):
        """CONTROL: the ordinary commit must not be caught by the new rule."""
        rid, nonce = self._freezing()
        rc = self.run_cli("freeze-commit", rid, "--nonce", nonce,
                          "--pane", "%7", "--pane-pid", "777")
        self.assertEqual(rc, 0)
        rec = agent_sessions.load(self.store).by_id(rid)
        self.assertEqual((rec.pane_id, rec.pane_pid, rec.standin_pid), ("%7", 777, 777))


class LeaseCoherenceTests(_StoreTestCase):
    """The lease triple is written and cleared as a unit; half of one is corrupt.

    `_lease_stale` is `grace elapsed AND owner dead`. A zero `op_owner_pid` is
    never alive, and an empty `op_started_at` epochs to 0.0 so the grace is
    always long past — so EITHER broken half makes a genuinely leased record
    read as free, and reconcile steals the operation from a live coordinator.
    That is the A7 failure reached through a hand-edited store instead of
    through the wrapper, so the store fails closed on it too.
    """

    def _write(self, **lease):
        rec = {"id": "aabbccdd", "root": "/r", "window": "w", "state": "freezing"}
        rec.update(lease)
        self.store.write_text(
            json.dumps({"version": 1, "sessions": [rec]}), encoding="utf-8"
        )

    def test_a_nonce_without_an_owner_pid_is_corruption(self):
        self._write(op_nonce="11223344", op_owner_pid=0,
                    op_started_at="2026-01-01T00:00:00Z")
        with self.assertRaises(agent_sessions.MalformedSessionsError):
            agent_sessions.load(self.store)

    def test_a_nonce_without_a_start_time_is_corruption(self):
        self._write(op_nonce="11223344", op_owner_pid=99, op_started_at="")
        with self.assertRaises(agent_sessions.MalformedSessionsError):
            agent_sessions.load(self.store)

    def test_an_owner_pid_without_a_nonce_is_corruption(self):
        self._write(op_nonce="", op_owner_pid=99, op_started_at="")
        with self.assertRaises(agent_sessions.MalformedSessionsError):
            agent_sessions.load(self.store)

    def test_a_malformed_op_started_at_is_corruption(self):
        """CONTROL. "Non-empty" is not enough — it must PARSE.

        `_epoch` maps an unparseable stamp to 0.0, so a lease with a valid nonce
        and a live owner pid but `op_started_at='not-a-timestamp'` reads as
        stale on the very first check: a grace measured from epoch 0 has always
        elapsed. Reconcile then takes over an operation a live coordinator still
        owns — the same fail-open outcome as a zero owner pid, reached through a
        different field.
        """
        self._write(op_nonce="11223344", op_owner_pid=99,
                    op_started_at="not-a-timestamp")
        with self.assertRaises(agent_sessions.MalformedSessionsError):
            agent_sessions.load(self.store)

    def test_a_plausible_but_non_canonical_stamp_is_corruption(self):
        """Near-misses are the realistic hand-edit, not obvious garbage."""
        for bad in ("2026-01-01 00:00:00", "2026-01-01T00:00:00",
                    "2026-01-01T00:00:00+00:00", "2026-13-01T00:00:00Z"):
            with self.subTest(stamp=bad):
                self._write(op_nonce="11223344", op_owner_pid=99,
                            op_started_at=bad)
                with self.assertRaises(agent_sessions.MalformedSessionsError):
                    agent_sessions.load(self.store)

    def test_every_timestamp_field_is_validated(self):
        """Not just the load-bearing one.

        All four are written by `_iso()`, which emits nothing else, so any other
        value is a hand-edit. `state_at` in particular feeds the restore-ack
        grace in the coordinator (§C/§D), so "display only" is not a stable
        category to carve out.
        """
        for field_name in ("op_started_at", "state_at", "started_at", "frozen_at"):
            with self.subTest(field=field_name):
                lease = {"op_nonce": "11223344", "op_owner_pid": 99,
                         "op_started_at": "2026-01-01T00:00:00Z"}
                lease[field_name] = "not-a-timestamp"
                self._write(**lease)
                with self.assertRaises(agent_sessions.MalformedSessionsError):
                    agent_sessions.load(self.store)

    def test_an_empty_timestamp_stays_legal(self):
        """CONTROL — most records carry empty `frozen_at` / `op_started_at`."""
        self._write(frozen_at="", op_started_at="", op_nonce="", op_owner_pid=0)
        rec = agent_sessions.load(self.store).sessions[0]
        self.assertEqual((rec.frozen_at, rec.op_started_at), ("", ""))

    def test_a_complete_lease_loads(self):
        """CONTROL — the rule must not reject a legitimately leased record."""
        self._write(op_nonce="11223344", op_owner_pid=99,
                    op_started_at="2026-01-01T00:00:00Z")
        rec = agent_sessions.load(self.store).sessions[0]
        self.assertEqual((rec.op_nonce, rec.op_owner_pid), ("11223344", 99))

    def test_no_lease_at_all_loads(self):
        """CONTROL — the overwhelmingly common shape."""
        self._write()
        self.assertEqual(agent_sessions.load(self.store).sessions[0].op_nonce, "")

    def test_every_lease_clearing_transition_leaves_a_loadable_store(self):
        """The invariant holds through the real transitions, not just on paper."""
        sf, rec = self.seeded()
        sf, line = agent_sessions.freeze_begin(
            sf, rec.id, capture_ansi="/a", capture_txt="/b", lines=1,
            owner_pid=os.getpid(),
        )
        nonce = line.split("|")[1]
        agent_sessions.dump(sf, self.store)
        agent_sessions.load(self.store)  # leased: coherent
        sf, _ = agent_sessions.freeze_abort(sf, rec.id, nonce=nonce)
        agent_sessions.dump(sf, self.store)
        agent_sessions.load(self.store)  # cleared: coherent


class SessionsViewTests(_StoreTestCase):
    def test_refresh_is_gated_and_reloads_on_change(self):
        sf, rec = self.seeded()
        agent_sessions.dump(sf, self.store)
        view = agent_sessions.SessionsView(self.store)
        self.assertTrue(view.refresh())
        self.assertFalse(view.refresh())
        self.assertEqual([r.id for r in view.records()], [rec.id])

    def test_invalidate_forces_a_reread(self):
        sf, _ = self.seeded()
        agent_sessions.dump(sf, self.store)
        view = agent_sessions.SessionsView(self.store)
        view.refresh()
        view.invalidate()
        self.assertTrue(view.refresh())

    def test_inode_change_is_detected_even_at_equal_size_and_mtime(self):
        """The reason st_ino is in the stamp: os.replace always changes it."""
        sf, rec = self.seeded(window="agent-aaaa")
        agent_sessions.dump(sf, self.store)
        view = agent_sessions.SessionsView(self.store)
        view.refresh()
        before = os.stat(self.store)
        # An equal-length rewrite: same field widths, different content.
        rec.window = "agent-bbbb"
        agent_sessions.dump(sf, self.store)
        os.utime(self.store, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(os.stat(self.store).st_size, before.st_size)
        self.assertEqual(os.stat(self.store).st_mtime_ns, before.st_mtime_ns)
        self.assertTrue(view.refresh())
        self.assertEqual(view.records()[0].window, "agent-bbbb")

    def test_frozen_and_by_id_helpers(self):
        sf, rec = self.seeded()
        rec.state = agent_sessions.STATE_FROZEN
        agent_sessions.dump(sf, self.store)
        view = agent_sessions.SessionsView(self.store)
        self.assertEqual([r.id for r in view.frozen()], [rec.id])
        self.assertIsNotNone(view.by_id(rec.id))
        self.assertIsNone(view.by_id("00000000"))

    def test_missing_store_reads_as_empty(self):
        view = agent_sessions.SessionsView(self.tmp / "nope.json")
        self.assertEqual(view.records(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
