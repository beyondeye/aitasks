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


class _ScriptedTmux:
    """Records gateway argv and answers by the ARITY of the requested format.

    `_FakeTmux` replays one answer for every call, which stops working the
    moment more than one `display-message` shape is in play — and three of them
    are: `pane_facts` asks for 10 fields, `probe_pane` for 3, `pane_location`
    for 2, and `respawn_if_stamped` for 1 (the server pid) then 4 (its
    after-read). A fake that dispatched on the SUBCOMMAND would hand every one
    of them the same string, and each parser validates field count, so four of
    the five would read as "gone" and silently divert the test into a branch it
    was not written for.

    Arity is the right key precisely because it is what the real parsers
    validate; it also needs no new module constants, so this fake keeps working
    against code that predates them.

    ``answers`` maps arity -> ``(rc, out)`` or a list of them consumed in order
    (the last one repeats). ``{token}`` in an ``out`` is replaced with the
    per-call token this fake scraped from the most recent `if-shell` command,
    which is the only way a test can spell the success case: the token is minted
    inside the helper.
    """

    #: Everything not covered by `answers`.
    DEFAULT = (0, "")

    def __init__(self, answers=None) -> None:
        self.calls: list[list[str]] = []
        self.answers = dict(answers or {})
        self.last_token = ""

    def _arity(self, args) -> int:
        if not args or args[0] != "display-message":
            return -1
        return len(args[-1].split("\t"))

    def run(self, args, timeout=None):
        self.calls.append(list(args))
        if args and args[0] == "if-shell":
            marker = "@aitask_respawn_token "
            tail = args[-1]
            if marker in tail:
                self.last_token = tail.split(marker, 1)[1].split()[0].strip("'\"")
        answer = self.answers.get(self._arity(args), self.DEFAULT)
        if isinstance(answer, list):
            answer = answer[0] if len(answer) == 1 else answer.pop(0)
        rc, out = answer
        return rc, out.replace("{token}", self.last_token)

    # --- readers used by the assertions ------------------------------------

    def verbs(self) -> list[str]:
        return [c[0] for c in self.calls if c]

    def destructive(self) -> list[list[str]]:
        """Every call that could replace what is running in a pane."""
        return [c for c in self.calls if c and c[0] in ("respawn-pane", "if-shell")]


#: A `probe_pane` answer: present, and stamped with `_rec()`'s own record id.
_PROBE_OURS = (0, "%104\t7f3a2c1d\t0")
#: Present, but the `%N` was recycled and now carries somebody else's stamp.
_PROBE_STRANGER = (0, "%104\tf00dfeed\t0")
#: `pane_facts` (10 fields) for the poll loop, and `pane_location` (2 fields).
_FACTS_10 = (0, "aitasks\tagent-pick-1705\t%900\t51000\t0\t/tmp\t7f3a2c1d\t7f3a2c1d\t\tsess-abc")
_LOCATION_NEW = (0, "%900\t51000")



#: The `_ScriptedTmux` answer set for "the recorded stand-in is ours and alive,
#: and the atomic dispatch fires" — the happy path every pre-t1773 fixture was
#: written against when a single 2-field answer still served every read.
_TMUX_OURS_AND_FIRES = {
    3: _PROBE_OURS,                              # probe_pane: present, ours
    1: (0, "9999"),                              # respawn_if_stamped: server pid
    4: (0, "{token}\t%104\t51000\t9999"),       # after-read: our token, new pid
    2: (0, "%104\t51000"),                       # pane_location
    10: (0, "aitasks\tagent-pick-1705\t%104\t51000\t0\t/tmp"
            "\t7f3a2c1d\t7f3a2c1d\t\tsess-abc"),  # pane_facts
}


def _dispatch_argv(tmux) -> list[str]:
    """The single `if-shell` this restore issued; fails loudly if there is not one."""
    dispatches = [c for c in tmux.calls if c and c[0] == "if-shell"]
    assert len(dispatches) == 1, f"expected exactly one if-shell, got {len(dispatches)}"
    return dispatches[0]

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
        tmux = self.swap_tmux(_ScriptedTmux(_TMUX_OURS_AND_FIRES))
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
        self.assertEqual(
            1, len([c for c in tmux.calls if c and c[0] == "if-shell"]),
            "exactly the ONE launch dispatch — a rollback respawn here would kill "
            "whatever the settling process put in the pane")


class TestRestoreEnvDelivery(_SwapMixin, unittest.TestCase):
    """All four identity variables reach the replacement, via `-e`."""

    def test_four_e_flags_are_passed_to_respawn(self):
        self.swap_store(_RecordingStore(answers={
            "restore-begin": (0, "RESTORING:7f3a2c1d|deadbeef"),
            "restore-launched": (0, "LAUNCHED:7f3a2c1d"),
            "restore-confirm": (0, "LIVE:7f3a2c1d|liveness"),
        }))
        tmux = self.swap_tmux(_ScriptedTmux(_TMUX_OURS_AND_FIRES))
        rec = _rec()
        with unittest.mock.patch.object(agent_restore, "_reread", return_value=rec), \
             unittest.mock.patch.object(agent_restore, "build_resume_argv",
                                        return_value="claude --resume sess-abc"), \
             unittest.mock.patch.object(ops, "restore_ack_grace", return_value=0):
            agent_restore.restore("7f3a2c1d")

        # The `-e` flags now ride INSIDE the `if-shell` branch (t1773) rather
        # than on a bare `respawn-pane` argv. Measured on tmux 3.6a: repeated
        # `-e` survives the wrapping, which is what this assertion protects.
        branch = _dispatch_argv(tmux)[-1]
        for name, value in (
            ("AITASK_RESTORE_RECORD", "7f3a2c1d"),
            ("AITASK_RESTORE_NONCE", "deadbeef"),
            ("AITASK_RESTORE_MODE", "resume"),
            ("AITASK_RESTORE_EXPECT_SESSION", "sess-abc"),
        ):
            self.assertIn(f"-e {name}={value}", branch,
                          f"{name} must reach the replacement agent on its own flag")
        self.assertEqual(4, branch.count(" -e "),
                         "one -e flag per variable (spike Case 3c measured four)")
        self.assertIn("respawn-pane -k ", branch,
                      "the stand-in must be killed by the respawn")


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
        tmux = self.swap_tmux(_ScriptedTmux(_TMUX_OURS_AND_FIRES))

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
        self.assertEqual(1, len([c for c in tmux.calls if c and c[0] == "if-shell"]),
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


class TestRecordedPaneIsOnlyAHint(_SwapMixin, unittest.TestCase):
    """The recorded `pane_id` is resolved against the server before it is used.

    A retained `frozen` record keeps its old `%N` forever — `_reconcile_frozen`
    returns `KEEP:<id>|pane_gone` and writes nothing — so branching on the
    RECORDED id respawns a corpse and the record can never be restored again
    (t1773). And because pane ids are monotonic within a server but restart at
    `%0` on a new one, that same `%N` can come back owned by a live stranger,
    where `respawn-pane -k` would kill their agent.
    """

    def _run(self, tmux_answers, *, store_answers=None, launch=("%900", 51000, "")):
        store = self.swap_store(_RecordingStore(answers=store_answers or {
            "restore-begin": (0, "RESTORING:7f3a2c1d|deadbeef"),
            "restore-launched": (0, "LAUNCHED:7f3a2c1d"),
            "restore-confirm": (0, "LIVE:7f3a2c1d|liveness"),
        }))
        tmux = self.swap_tmux(_ScriptedTmux(tmux_answers))
        launched = unittest.mock.Mock(return_value=launch)
        with unittest.mock.patch.object(agent_restore, "_reread", return_value=_rec()), \
             unittest.mock.patch.object(agent_restore, "build_resume_argv",
                                        return_value="claude --resume sess-abc"), \
             unittest.mock.patch.object(agent_restore, "_launch_into_new_window", launched), \
             unittest.mock.patch.object(ops, "restore_ack_grace", return_value=0):
            result = agent_restore.restore("7f3a2c1d")
        return result, store, tmux, launched

    def test_a_gone_pane_routes_to_a_new_window(self):
        _, _, tmux, launched = self._run({
            3: (1, ""),                    # probe: the pane is gone
            10: _FACTS_10, 2: _LOCATION_NEW,
        })
        self.assertTrue(launched.called,
                        "a record whose pane is gone must restore into a NEW window "
                        "— this is the t1773 defect")
        self.assertEqual([], tmux.destructive(),
                         "nothing may be respawned: that pane does not exist")

    def test_our_own_stamped_pane_is_reused_atomically(self):
        _, _, tmux, launched = self._run({
            3: _PROBE_OURS, 1: (0, "9999"),
            4: (0, "{token}\t%104\t51000\t9999"),
            10: _FACTS_10, 2: (0, "%104\t51000"),
        })
        self.assertFalse(launched.called,
                         "our own live stand-in must be reused, not abandoned")
        dispatches = [c for c in tmux.calls if c and c[0] == "if-shell"]
        self.assertEqual(1, len(dispatches),
                         "the stamp check and the respawn must travel as ONE dispatch")
        self.assertIn("%104", dispatches[0],
                      "the dispatch must target the recorded pane")
        self.assertEqual([], [c for c in tmux.calls if c and c[0] == "respawn-pane"],
                         "a bare respawn-pane is the unguarded form this replaces")

    def test_a_recycled_pane_is_never_touched(self):
        _, _, tmux, launched = self._run({
            3: _PROBE_STRANGER,
            10: _FACTS_10, 2: _LOCATION_NEW,
        })
        self.assertTrue(launched.called,
                        "a `%N` carrying somebody else's stamp is not ours")
        self.assertEqual([], tmux.destructive(),
                         "respawn-pane -k on a recycled pane kills a stranger's agent")

    def test_an_unreachable_tmux_fails_closed_before_any_write(self):
        result, store, tmux, launched = self._run({3: (-1, "")})
        self.assertFalse(result.ok)
        self.assertEqual("RESTORE_FAILED:7f3a2c1d|preflight:tmux unreachable",
                         result.line)
        self.assertEqual([], store.verbs(),
                         "an unreachable tmux must not mint a lease or move the record")
        self.assertFalse(launched.called)
        self.assertEqual([], tmux.destructive())

    def test_a_restart_between_the_read_and_the_dispatch_adopts_nothing(self):
        """The transition case no steady-state test reaches.

        The probe says present-and-ours; then the server restarts and the
        recorded `%N` comes back as a stranger. `if-shell` correctly rejects the
        missing stamp — but the pane's pid HAS changed, so an implementation
        that inferred "fired" from a pid delta would record the stranger's pid
        as `launch_pid` and later liveness-confirm their agent as ours.
        """
        _, store, _, launched = self._run({
            3: _PROBE_OURS, 1: (0, "9999"),
            4: (0, "\t%104\t77777\t12345"),   # no token; new pid; NEW server
            10: _FACTS_10, 2: _LOCATION_NEW,
        })
        self.assertTrue(launched.called,
                        "the recorded pane is no longer ours — go to a new window")
        launched_calls = [c for c in store.calls if c and c[0] == "restore-launched"]
        self.assertEqual(1, len(launched_calls))
        flat = " ".join(launched_calls[0])
        self.assertIn("%900", flat, "the NEW window's pane must be recorded")
        self.assertNotIn("77777", flat,
                         "the stranger's pid must never become launch_pid")

    def test_a_lost_stamp_without_a_restart_routes_the_same_way(self):
        _, store, _, launched = self._run({
            3: _PROBE_OURS, 1: (0, "9999"),
            4: (0, "\t%104\t77777\t9999"),    # no token; same server generation
            10: _FACTS_10, 2: _LOCATION_NEW,
        })
        self.assertTrue(launched.called)
        flat = " ".join(" ".join(c) for c in store.calls if c and c[0] == "restore-launched")
        self.assertNotIn("77777", flat)


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
