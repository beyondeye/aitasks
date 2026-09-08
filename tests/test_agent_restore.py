"""Unit tests for the restore coordinator (`lib/agent_restore.py`, t1705_5).

No tmux, no real store, no agent binaries: the store wrapper and the tmux
gateway are swapped in place on the SHARED module (`lib/agent_frozen_ops.py`,
t1738) exactly as `tests/test_agent_frozen_ops.py` documents —
``agent_frozen_ops.store = fake`` / ``agent_frozen_ops._TMUX = fake``. That is
also why nothing here may import those names directly: an import-time alias
binds the original object and silently bypasses the swap.

The `restore_ack_grace` block below is **written before the accessor exists**
(the `assert_grace_seam_effective` pre-phase mitigation). It is the guard for a
defect that already happened once in planning: the live suite's most important
negative assertion — "on a session mismatch the 20 s liveness fallback must NOT
fire" — was specified against a grace that no test could shorten, because
`RESTORE_ACK_GRACE` was a hardcoded module constant with no config and no env
override. That assertion would have passed **vacuously**, testing nothing, while
reading like coverage. Pinning the precedence here is what makes the live
assertion mean something.

Run: python3 tests/test_agent_restore.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import agent_frozen_ops as ops  # noqa: E402

#: The shipped default, duplicated from the contract rather than read back from
#: the module — importing the constant to assert against itself would pin
#: nothing. If this ever legitimately changes, this line must change too.
DEFAULT_GRACE = 20.0


class _EnvGuard:
    """Set/clear env vars for one block and restore them exactly afterwards."""

    def __init__(self, **values: str | None) -> None:
        self._values = values
        self._saved: dict[str, str | None] = {}

    def __enter__(self):
        for key, value in self._values.items():
            self._saved[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        return self

    def __exit__(self, *exc):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        return False


def _root_with_config(tmp: str, body: str | None) -> str:
    """A project root whose `project_config.yaml` holds `body` (or has none)."""
    meta = Path(tmp) / "aitasks" / "metadata"
    meta.mkdir(parents=True, exist_ok=True)
    if body is not None:
        (meta / "project_config.yaml").write_text(body, encoding="utf-8")
    return tmp


class TestRestoreAckGracePrecedence(unittest.TestCase):
    """`restore_ack_grace()` — env seam > project config > default.

    The env seam is gated on `AITASKS_TEST_MODE=1` for the same reason
    `agent_sessions._stale_op_grace` is: a stray `AITASKS_RESTORE_ACK_GRACE` in
    a developer's shell must never reconfigure a real coordinator's ack window.
    """

    def test_default_when_nothing_is_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _root_with_config(tmp, None)
            with _EnvGuard(AITASKS_TEST_MODE=None, AITASKS_RESTORE_ACK_GRACE=None):
                self.assertEqual(DEFAULT_GRACE, ops.restore_ack_grace(root))

    def test_config_value_is_used_when_no_env_seam(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _root_with_config(tmp, "frozen:\n  restore_ack_grace: 7.5\n")
            with _EnvGuard(AITASKS_TEST_MODE=None, AITASKS_RESTORE_ACK_GRACE=None):
                self.assertEqual(7.5, ops.restore_ack_grace(root))

    def test_env_seam_wins_over_config_under_test_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _root_with_config(tmp, "frozen:\n  restore_ack_grace: 7.5\n")
            with _EnvGuard(AITASKS_TEST_MODE="1", AITASKS_RESTORE_ACK_GRACE="3"):
                self.assertEqual(3.0, ops.restore_ack_grace(root))

    def test_env_seam_is_IGNORED_without_test_mode(self):
        """The gate is the whole point: without it a stray shell var reconfigures
        a live coordinator, and reconcile could liveness-confirm a restore the
        coordinator is still polling for."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _root_with_config(tmp, None)
            with _EnvGuard(AITASKS_TEST_MODE=None, AITASKS_RESTORE_ACK_GRACE="3"):
                self.assertEqual(DEFAULT_GRACE, ops.restore_ack_grace(root))
            with _EnvGuard(AITASKS_TEST_MODE="0", AITASKS_RESTORE_ACK_GRACE="3"):
                self.assertEqual(DEFAULT_GRACE, ops.restore_ack_grace(root))

    def test_non_positive_env_falls_back_to_default(self):
        """0 would make every restore liveness-confirm instantly — the one value
        a test could set by accident and never notice."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _root_with_config(tmp, None)
            for bad in ("0", "-1", "-0.5"):
                with self.subTest(value=bad):
                    with _EnvGuard(AITASKS_TEST_MODE="1", AITASKS_RESTORE_ACK_GRACE=bad):
                        self.assertEqual(DEFAULT_GRACE, ops.restore_ack_grace(root))

    def test_unparseable_env_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _root_with_config(tmp, None)
            for bad in ("", "abc", "3s"):
                with self.subTest(value=bad):
                    with _EnvGuard(AITASKS_TEST_MODE="1", AITASKS_RESTORE_ACK_GRACE=bad):
                        self.assertEqual(DEFAULT_GRACE, ops.restore_ack_grace(root))

    def test_non_positive_and_unparseable_config_fall_back_to_default(self):
        for body in (
            "frozen:\n  restore_ack_grace: 0\n",
            "frozen:\n  restore_ack_grace: -4\n",
            "frozen:\n  restore_ack_grace: nope\n",
            "frozen:\n  capture_max_lines: 10\n",   # section present, key absent
            "verify_build: true\n",                  # no frozen section at all
        ):
            with self.subTest(body=body):
                with tempfile.TemporaryDirectory() as tmp:
                    root = _root_with_config(tmp, body)
                    with _EnvGuard(AITASKS_TEST_MODE=None, AITASKS_RESTORE_ACK_GRACE=None):
                        self.assertEqual(DEFAULT_GRACE, ops.restore_ack_grace(root))

    def test_unreadable_config_degrades_to_default_rather_than_raising(self):
        """This runs mid-restore. A malformed project config must not abort a
        transaction that has already respawned the user's agent pane."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _root_with_config(tmp, "frozen: [this is not a mapping\n")
            with _EnvGuard(AITASKS_TEST_MODE=None, AITASKS_RESTORE_ACK_GRACE=None):
                self.assertEqual(DEFAULT_GRACE, ops.restore_ack_grace(root))


class TestGraceIsSharedWithReconcile(unittest.TestCase):
    """Coordinator and reconcile must not be able to disagree about the grace.

    If they did, reconcile could liveness-confirm a restore whose coordinator is
    still polling — the record moves to `live` behind the coordinator's back and
    its next verb fails `NONCE_MISMATCH`.
    """

    def test_agent_freeze_reads_the_shared_accessor_not_a_local_constant(self):
        import agent_freeze

        self.assertFalse(
            hasattr(agent_freeze, "RESTORE_ACK_GRACE"),
            "agent_freeze must not keep a local RESTORE_ACK_GRACE constant — the "
            "grace moved to agent_frozen_ops (B6) so agent_restore need not import "
            "the repair module. A surviving local constant means the call site was "
            "not switched and the two engines can drift.",
        )

    def test_accessor_is_reachable_through_the_shared_module(self):
        self.assertTrue(
            callable(getattr(ops, "restore_ack_grace", None)),
            "restore_ack_grace must live on agent_frozen_ops so BOTH engines can "
            "reach it without importing each other.",
        )


class _RecordingStore:
    """Stands in for the `aitask_agent_sessions.sh` wrapper invocation."""

    def __init__(self, answers=None, rc: int = 0, out: str = "") -> None:
        self.calls: list[tuple[str, ...]] = []
        self.answers = answers or {}
        self.rc = rc
        self.out = out

    def __call__(self, *argv: str, timeout: float = 20.0):
        self.calls.append(tuple(argv))
        verb = argv[0] if argv else ""
        if verb in self.answers:
            return self.answers[verb]
        return self.rc, self.out

    def verbs(self) -> list[str]:
        return [c[0] for c in self.calls if c]


class _FakeTmux:
    """Records gateway argv and replays one scripted answer."""

    def __init__(self, rc: int = 0, out: str = "") -> None:
        self.calls: list[list[str]] = []
        self.rc = rc
        self.out = out

    def run(self, args, timeout=None):
        self.calls.append(list(args))
        return self.rc, self.out


class _SwapMixin:
    """Install the seams the SHARED module documents.

    ``agent_frozen_ops.store`` and ``agent_frozen_ops._TMUX`` are swapped in
    place; `agent_restore` reaches both through the module, so one swap
    redirects it too. If a future edit import-aliased either name, these swaps
    would silently stop applying — `tests/test_agent_frozen_ops.py` fails on
    exactly that, for this module by name.
    """

    def swap_store(self, fake):
        prev = ops.store
        ops.store = fake
        self.addCleanup(setattr, ops, "store", prev)
        return fake

    def swap_tmux(self, fake):
        prev = ops._TMUX
        ops._TMUX = fake
        self.addCleanup(setattr, ops, "_TMUX", prev)
        return fake


import agent_restore  # noqa: E402  (after the seam helpers, for readability)


def _rec(**overrides) -> dict:
    """A `frozen` record as `store show` returns it (all values are strings)."""
    base = {
        "id": "7f3a2c1d",
        "root": str(REPO_ROOT),
        "window": "agent-pick-1705",
        "pane_id": "%104",
        "pane_pid": "41233",
        "session": "aitasks",
        "operation": "pick",
        "task_id": "1705",
        "agent_string": "claudecode/opus5",
        "agent_kind": "claudecode",
        "codeagent_session_id": "sess-abc",
        "transcript_path": "",
        "state": "frozen",
        "state_at": "2026-09-08T10:00:00Z",
        "op_nonce": "",
        "op_owner_pid": "0",
        "launch_pid": "0",
        "standin_pid": "9999",
        "restore_attempts": "0",
        "restore_mode": "",
        "ack": "",
        "last_error": "",
    }
    base.update({k: str(v) for k, v in overrides.items()})
    return base


class TestPreflightsWriteNothing(_SwapMixin, unittest.TestCase):
    """The two preflight refusals must not touch the store.

    Both are reachable by a user pressing a key on a record that simply cannot
    be resumed. If either wrote, the record would leave `frozen` — bumping
    `restore_attempts`, minting a lease, and (worst) putting a record into
    `restoring` with nothing ever launched, which reconcile then has to unwind.
    Doing nothing is the correct outcome: the capture stays, the stand-in stays.
    """

    def test_no_session_writes_nothing_and_issues_no_tmux(self):
        store = self.swap_store(_RecordingStore())
        tmux = self.swap_tmux(_FakeTmux())
        rec = _rec(codeagent_session_id="")
        with unittest.mock.patch.object(agent_restore, "_reread", return_value=rec):
            result = agent_restore.restore("7f3a2c1d")
        self.assertFalse(result.ok)
        self.assertEqual("no_session", result.outcome)
        self.assertEqual("RESTORE_FAILED:7f3a2c1d|no_session", result.line)
        self.assertEqual([], store.calls, "no_session must write NOTHING to the store")
        self.assertEqual([], tmux.calls, "no_session must issue no tmux command")

    def test_unresolvable_binary_writes_nothing(self):
        """A failed `--dry-run` probe IS the binary check — there is no second
        `shutil.which` path to keep in sync with the wrapper."""
        store = self.swap_store(_RecordingStore())
        tmux = self.swap_tmux(_FakeTmux())
        rec = _rec()
        with unittest.mock.patch.object(agent_restore, "_reread", return_value=rec), \
             unittest.mock.patch.object(agent_restore, "build_resume_argv",
                                        return_value=None):
            result = agent_restore.restore("7f3a2c1d")
        self.assertFalse(result.ok)
        self.assertEqual("binary", result.outcome)
        self.assertEqual([], store.calls, "binary preflight must write NOTHING")
        self.assertEqual([], tmux.calls)

    def test_opencode_resume_is_refused_before_any_write(self):
        store = self.swap_store(_RecordingStore())
        rec = _rec(agent_kind="opencode", agent_string="opencode/openai_gpt_5_2")
        with unittest.mock.patch.object(agent_restore, "_reread", return_value=rec):
            result = agent_restore.restore("7f3a2c1d")
        self.assertFalse(result.ok)
        self.assertEqual("resume_unsupported", result.outcome)
        self.assertEqual([], store.calls)

    def test_repick_without_a_task_id_writes_nothing(self):
        store = self.swap_store(_RecordingStore())
        rec = _rec(task_id="")
        with unittest.mock.patch.object(agent_restore, "_reread", return_value=rec):
            result = agent_restore.restore("7f3a2c1d", repick=True)
        self.assertFalse(result.ok)
        self.assertEqual("no_task_id", result.outcome)
        self.assertEqual([], store.calls)


class TestNonceMismatchIssuesNoTmux(_SwapMixin, unittest.TestCase):
    """`NONCE_MISMATCH` means reconcile already settled this record.

    Whatever is in that pane now belongs to whoever settled it. Issuing ANY tmux
    command from here — above all a rollback `respawn-pane -k` — would destroy
    it. Exit without touching the pane.
    """

    def test_mismatch_on_restore_launched_stops_without_tmux(self):
        store = self.swap_store(_RecordingStore(answers={
            "restore-begin": (0, "RESTORING:7f3a2c1d|deadbeef"),
            "restore-launched": (ops.EXIT_NONCE_MISMATCH, "NONCE_MISMATCH:7f3a2c1d"),
        }))
        tmux = self.swap_tmux(_FakeTmux(out="%104\t51000"))
        rec = _rec()
        with unittest.mock.patch.object(agent_restore, "_reread", return_value=rec), \
             unittest.mock.patch.object(agent_restore, "build_resume_argv",
                                        return_value="claude --resume sess-abc"):
            result = agent_restore.restore("7f3a2c1d")

        self.assertFalse(result.ok)
        self.assertEqual("nonce_mismatch", result.outcome)
        self.assertNotIn("restore-abort", store.verbs(),
                         "a mismatched coordinator must not abort — someone else owns it")
        self.assertNotIn("standin-respawned", store.verbs())
        respawns = [c for c in tmux.calls if c and c[0] == "respawn-pane"]
        self.assertEqual(
            1, len(respawns),
            "exactly the ONE launch respawn — a rollback respawn here would kill "
            "whatever the settling process put in the pane")


class TestRestoreEnvDelivery(_SwapMixin, unittest.TestCase):
    """All four identity variables reach the replacement, via `-e`."""

    def test_four_e_flags_are_passed_to_respawn(self):
        self.swap_store(_RecordingStore(answers={
            "restore-begin": (0, "RESTORING:7f3a2c1d|deadbeef"),
            "restore-launched": (0, "LAUNCHED:7f3a2c1d"),
            "restore-confirm": (0, "LIVE:7f3a2c1d|liveness"),
        }))
        tmux = self.swap_tmux(_FakeTmux(out="%104\t51000"))
        rec = _rec()
        with unittest.mock.patch.object(agent_restore, "_reread", return_value=rec), \
             unittest.mock.patch.object(agent_restore, "build_resume_argv",
                                        return_value="claude --resume sess-abc"), \
             unittest.mock.patch.object(ops, "restore_ack_grace", return_value=0):
            agent_restore.restore("7f3a2c1d")

        respawn = next(c for c in tmux.calls if c and c[0] == "respawn-pane")
        flat = " ".join(respawn)
        for name, value in (
            ("AITASK_RESTORE_RECORD", "7f3a2c1d"),
            ("AITASK_RESTORE_NONCE", "deadbeef"),
            ("AITASK_RESTORE_MODE", "resume"),
            ("AITASK_RESTORE_EXPECT_SESSION", "sess-abc"),
        ):
            self.assertIn(f"{name}={value}", flat,
                          f"{name} must reach the replacement agent")
        self.assertEqual(4, respawn.count("-e"),
                         "one -e flag per variable (spike Case 3c measured four)")
        self.assertIn("-k", respawn, "the stand-in must be killed by the respawn")


class TestHookWinsTheLaunchRace(_SwapMixin, unittest.TestCase):
    """The V12 regression guard, at unit level.

    `restore-launched` is state-guarded to `restoring`. When the replacement's
    hook acks first the record is already `live`, the verb is refused, and a
    coordinator that treated the refusal as failure would roll back and kill the
    agent it just restored.
    """

    def test_refused_launch_with_a_hook_ack_is_SUCCESS_and_no_rollback(self):
        store = self.swap_store(_RecordingStore(answers={
            "restore-begin": (0, "RESTORING:7f3a2c1d|deadbeef"),
            "restore-launched": (ops.EXIT_TRANSITION_REFUSED,
                                 "TRANSITION_REFUSED:7f3a2c1d|live|restore-launched"),
        }))
        tmux = self.swap_tmux(_FakeTmux(out="%104\t51000"))

        before = _rec()
        after = _rec(state="live", ack="hook")
        reads = iter([before, after, after, after])

        with unittest.mock.patch.object(agent_restore, "_reread",
                                        side_effect=lambda _id: next(reads)), \
             unittest.mock.patch.object(agent_restore, "build_resume_argv",
                                        return_value="claude --resume sess-abc"):
            result = agent_restore.restore("7f3a2c1d")

        self.assertTrue(result.ok, "a hook ack that beat restore-launched is SUCCESS")
        self.assertEqual("hook", result.outcome)
        self.assertEqual("RESTORED:7f3a2c1d|hook", result.line)
        self.assertNotIn("restore-abort", store.verbs(),
                         "rolling back here would kill a successfully restored agent")
        respawns = [c for c in tmux.calls if c and c[0] == "respawn-pane"]
        self.assertEqual(1, len(respawns),
                         "no rollback respawn — the agent in that pane is the user's")


class TestArgvBuilders(_SwapMixin, unittest.TestCase):
    """`build_resume_argv` / `build_repick_argv` against the real wrapper."""

    def test_resume_argv_carries_resume_session_as_a_GLOBAL_flag(self):
        cmd = agent_restore.build_resume_argv(_rec())
        if cmd is None:
            self.skipTest("wrapper could not resolve a command in this checkout")
        self.assertIn("--resume", cmd)
        self.assertIn("sess-abc", cmd)

    def test_resume_argv_is_None_without_a_session_id(self):
        self.assertIsNone(agent_restore.build_resume_argv(_rec(codeagent_session_id="")))

    def test_repick_argv_uses_the_shared_pick_helper(self):
        cmd = agent_restore.build_repick_argv(_rec())
        if cmd is None:
            self.skipTest("wrapper could not resolve a command in this checkout")
        self.assertIn("aitask-pick", cmd)
        self.assertIn("1705", cmd)

    def test_repick_argv_is_None_without_a_task_id(self):
        self.assertIsNone(agent_restore.build_repick_argv(_rec(task_id="")))

    def test_env_prefix_fallback_quotes_its_values(self):
        """The gone-pane branch has no `-e`, so values ride a command string."""
        out = agent_restore._env_prefixed("claude --resume x", {"A": "b c", "D": "e"})
        self.assertTrue(out.startswith("env "))
        self.assertIn("'b c'", out, "a value with a space must be quoted")
        self.assertTrue(out.endswith("claude --resume x"))


class TestSeamsAreBoundToThisEngine(unittest.TestCase):
    """The failure seam must not be shared with the freeze engine."""

    def test_fail_at_is_bound_to_AITASKS_RESTORE_FAIL_AT(self):
        self.assertEqual("AITASKS_RESTORE_FAIL_AT",
                         getattr(agent_restore._fail_at, "env_var", None))

    def test_a_freeze_injection_does_not_fire_in_the_restore_engine(self):
        with _EnvGuard(AITASKS_TEST_MODE="1", AITASKS_FREEZE_FAIL_AT="begin"):
            agent_restore._fail_at("begin")   # must NOT raise


if __name__ == "__main__":
    unittest.main(verbosity=2)
