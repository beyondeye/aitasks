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
import re
import sys
import tempfile
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
    for 2, and `respawn_if_stamped` for 2 (its pre-read: pane id + server pid)
    then 5 (its after-read). Two reads sharing an arity are scripted as a LIST,
    consumed in call order. A fake that dispatched on the SUBCOMMAND would hand every one
    of them the same string, and each parser validates field count, so four of
    the five would read as "gone" and silently divert the test into a branch it
    was not written for.

    Arity is the right key precisely because it is what the real parsers
    validate; it also needs no new module constants, so this fake keeps working
    against code that predates them. For the same reason an UNSCRIPTED arity
    raises whenever ``answers`` is non-empty (t1783): a scripted fake that
    quietly answered ``(0, "")`` would send a helper whose read grew a field
    down its "gone" branch, and the test would pass for the wrong reason.

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
        arity = self._arity(args)
        if arity >= 0 and self.answers and arity not in self.answers:
            raise AssertionError(
                f"unscripted display-message arity {arity}: {args}")
        answer = self.answers.get(arity, self.DEFAULT)
        if isinstance(answer, list):
            answer = answer[0] if len(answer) == 1 else answer.pop(0)
        rc, out = answer
        return rc, out.replace("{token}", self.last_token)

    # --- readers used by the assertions ------------------------------------

    def verbs(self) -> list[str]:
        return [c[0] for c in self.calls if c]

    def destructive(self) -> list[list[str]]:
        """Every call that could replace or end what is running in a pane.

        An `if-shell` counts by its BRANCH: the guarded stamp / attempt-mark
        clears a successful restore issues (t1875) are `if-shell` dispatches too,
        but a `set-option -pu` cannot touch a pane's process.
        """
        return [c for c in self.calls if c and (
            c[0] in ("respawn-pane", "kill-pane", "kill-window")
            or (c[0] == "if-shell" and any(
                verb in c[-1] for verb in ("respawn-pane", "kill-pane", "kill-window"))))]


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
    2: (0, "%104\t9999"),                        # pre-read: pane present, server pid (t1783)
    5: (0, "{token}\t%104\t51000\t9999\t7f3a2c1d"),   # after-read: our token, new pid, our stamp
    10: (0, "aitasks\tagent-pick-1705\t%104\t51000\t0\t/tmp"
            "\t7f3a2c1d\t7f3a2c1d\t\tsess-abc"),  # pane_facts
}


def _dispatch_argv(tmux) -> list[str]:
    """The single RESPAWN `if-shell` this restore issued; fails loudly otherwise.

    A successful restore also issues guarded stamp/attempt-mark clears (t1875) —
    `if-shell` dispatches too, but ones that can never replace a pane's process —
    so the respawn is picked by its branch, not by being the only `if-shell`.
    """
    dispatches = [c for c in tmux.calls
                  if c and c[0] == "if-shell" and "respawn-pane" in c[-1]]
    assert len(dispatches) == 1, (
        f"expected exactly one respawn if-shell, got {len(dispatches)}")
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
    """The four identity variables and the agent string reach the replacement.

    `AITASK_AGENT_STRING` is the fifth (t1802). The replacement runs the bare
    agent command out of the wrapper's `--dry-run`, which returns BEFORE the
    wrapper's own export, so the coordinator is the only thing that can hand it
    over. Every delivery test covers resume AND re-pick: both modes share the
    one `env` dict, and a later conditional must not silently drop either.
    """

    _STORE = {
        "restore-begin": (0, "RESTORING:7f3a2c1d|deadbeef"),
        "restore-launched": (0, "LAUNCHED:7f3a2c1d"),
        "restore-confirm": (0, "LIVE:7f3a2c1d|liveness"),
    }
    _MODES = ((False, "resume"), (True, "repick"))

    def _restore(self, rec, tmux_answers, *, repick, launched=None):
        self.swap_store(_RecordingStore(answers=dict(self._STORE)))
        tmux = self.swap_tmux(_ScriptedTmux(tmux_answers))
        launched = launched or unittest.mock.Mock(return_value=("%900", 51000, ""))
        with unittest.mock.patch.object(agent_restore, "_reread", return_value=rec), \
             unittest.mock.patch.object(agent_restore, "build_resume_argv",
                                        return_value="claude --resume sess-abc"), \
             unittest.mock.patch.object(agent_restore, "build_repick_argv",
                                        return_value="claude '/aitask-pick 1705'"), \
             unittest.mock.patch.object(agent_restore, "_launch_into_new_window", launched), \
             unittest.mock.patch.object(ops, "restore_ack_grace", return_value=0):
            agent_restore.restore("7f3a2c1d", repick=repick)
        return tmux, launched

    def _respawn_branch(self, rec, *, repick=False) -> str:
        tmux, _ = self._restore(rec, _TMUX_OURS_AND_FIRES, repick=repick)
        # The `-e` flags now ride INSIDE the `if-shell` branch (t1773) rather
        # than on a bare `respawn-pane` argv. Measured on tmux 3.6a: repeated
        # `-e` survives the wrapping, which is what these assertions protect.
        return _dispatch_argv(tmux)[-1]

    def test_identity_and_agent_string_e_flags_are_passed_to_respawn(self):
        for repick, mode in self._MODES:
            with self.subTest(mode=mode):
                branch = self._respawn_branch(_rec(), repick=repick)
                for name, value in (
                    ("AITASK_RESTORE_RECORD", "7f3a2c1d"),
                    ("AITASK_RESTORE_NONCE", "deadbeef"),
                    ("AITASK_RESTORE_MODE", mode),
                    ("AITASK_RESTORE_EXPECT_SESSION", "sess-abc"),
                    ("AITASK_AGENT_STRING", "claudecode/opus5"),
                ):
                    self.assertIn(f"-e {name}={value}", branch,
                                  f"{name} must reach the replacement agent on its own flag")
                self.assertEqual(5, branch.count(" -e "), "one -e flag per variable")
                self.assertIn("respawn-pane -k ", branch,
                              "the stand-in must be killed by the respawn")

    def test_a_new_window_launch_carries_the_agent_string(self):
        """The gone-pane branch has no `-e`: the env rides `_env_prefixed`."""
        gone = {3: (1, ""), 10: _FACTS_10, 2: _LOCATION_NEW}
        for repick, mode in self._MODES:
            with self.subTest(mode=mode):
                _, launched = self._restore(_rec(), gone, repick=repick)
                self.assertTrue(launched.called, "a gone pane restores into a new window")
                env = launched.call_args.args[2]
                self.assertEqual("claudecode/opus5", env.get("AITASK_AGENT_STRING"))
                self.assertEqual(mode, env.get("AITASK_RESTORE_MODE"))

    def test_a_record_without_an_agent_string_delivers_only_the_four(self):
        branch = self._respawn_branch(_rec(agent_string="", agent_kind=""))
        self.assertNotIn("AITASK_AGENT_STRING", branch)
        self.assertEqual(4, branch.count(" -e "))

    def test_a_malformed_agent_string_is_never_spliced_into_the_branch(self):
        """The `-e NAME=value` flags are joined into the branch UNQUOTED."""
        branch = self._respawn_branch(_rec(agent_string="bad value;x"))
        self.assertNotIn("AITASK_AGENT_STRING", branch)
        self.assertNotIn("bad value;x", branch)


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
        self.assertEqual(1, len(tmux.destructive()),
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
            3: _PROBE_OURS,
            2: (0, "%104\t9999"),                 # pre-read: present, server 9999
            5: (0, "{token}\t%104\t51000\t9999\t7f3a2c1d"),
            10: _FACTS_10,
        })
        self.assertFalse(launched.called,
                         "our own live stand-in must be reused, not abandoned")
        dispatches = tmux.destructive()
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
            3: _PROBE_OURS,
            # pre-read: present on server 9999; then pane_location in the new window
            2: [(0, "%104\t9999"), _LOCATION_NEW],
            5: (0, "\t%104\t77777\t12345\tf00dfeed"),   # no token; new pid; NEW server; stranger's stamp
            10: _FACTS_10,
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
            3: _PROBE_OURS,
            2: [(0, "%104\t9999"), _LOCATION_NEW],   # same server generation as the after-read
            5: (0, "\t%104\t77777\t9999\tf00dfeed"),    # no token; same server generation; stranger's stamp
            10: _FACTS_10,
        })
        self.assertTrue(launched.called)
        flat = " ".join(" ".join(c) for c in store.calls if c and c[0] == "restore-launched")
        self.assertNotIn("77777", flat)


# ---------------------------------------------------------------------------
# t1784 — no tmux session exists for the record's root
# ---------------------------------------------------------------------------

import subprocess  # noqa: E402

from agent_launch_utils import AitasksSession  # noqa: E402

#: `_rec()`'s project root, exactly as `_launch_into_new_window` hands it on.
_ROOT = str(REPO_ROOT)


def _session(name: str = "aitasks", root: str | None = None) -> AitasksSession:
    path = Path(root or _ROOT)
    return AitasksSession(session=name, project_root=path, project_name=path.name)


class _Server:
    """A window-aware fake tmux server for the gone-pane launch (t1875).

    `_ScriptedTmux` answers by format arity, which cannot follow a window that is
    created, stamped, renamed and killed across a dozen calls. This one keeps
    real pane state and interprets the handful of commands the launch, the
    survivor guard and the rollback issue — including `if-shell -F` conditions,
    so a guard that does not match really declines. A branch is a `;`-joined
    sequence that ABORTS after a failing command, as tmux's does.

    Knobs: ``unreachable`` (every call is rc -1), ``new_window_answer`` (replace
    `new-window`'s answer AFTER it created the window — the lost-`-P` and
    rc -1 shapes), ``new_window_creates`` (False: tmux created nothing),
    ``respawn_fails`` (a `respawn-pane` inside a branch fails), ``after`` (a
    callback run after each call, for races).
    """

    SERVER_PID = "9999"

    def __init__(self, sessions=("aitasks",)) -> None:
        self.calls: list[list[str]] = []
        self.panes: dict[str, dict] = {}
        self.sessions = list(sessions)
        self._next, self._next_win, self._next_pid = 900, 50, 51000
        self.unreachable = False
        self.new_window_answer = None
        self.new_window_creates = True
        self.respawn_fails = False
        self.after = None

    # -- construction --------------------------------------------------------
    def add(self, session: str, window: str, *, pane_id: str | None = None,
            dead: bool = False, **options: str) -> str:
        if pane_id is None:
            pane_id = f"%{self._next}"
            self._next += 1
        self._next_win += 1
        self._next_pid += 1
        pane = {"pane_id": pane_id, "pane_pid": str(self._next_pid),
                "session_name": session, "window_name": window,
                "window_id": f"@{self._next_win}", "pane_dead": "1" if dead else "0",
                "pane_current_path": "/tmp", "start": ""}
        pane.update(options)
        self.panes[pane_id] = pane
        return pane_id

    def windows_named(self, name: str) -> list[str]:
        return [p["pane_id"] for p in self.panes.values() if p["window_name"] == name]

    # -- formats and conditions ----------------------------------------------
    def _render(self, fmt: str, pane: dict | None) -> str:
        def sub(m):
            key = m.group(1)
            if key == "pid":
                return self.SERVER_PID
            return (pane or {}).get(key, "")
        return re.sub(r"#\{([@a-z_]+)\}", sub, fmt)

    def _cond(self, cond: str, pane: dict) -> bool:
        m = re.fullmatch(r"#\{&&:#\{pane_dead\},(.*)\}", cond)
        if m:
            return pane.get("pane_dead") == "1" and self._cond(m.group(1), pane)
        m = re.fullmatch(r"#\{==:#\{([@a-z_]+)\},(.*)\}", cond)
        assert m, f"unsupported condition {cond!r}"
        return pane.get(m.group(1), "") == m.group(2)

    @staticmethod
    def _unquote(s: str) -> str:
        if s.startswith('"') and s.endswith('"'):
            return s[1:-1].replace('\\"', '"').replace("\\$", "$").replace("\\\\", "\\")
        return s

    def _kill_window(self, pane: dict) -> None:
        wid = pane["window_id"]
        for pid in [k for k, p in self.panes.items() if p["window_id"] == wid]:
            del self.panes[pid]

    def _exec(self, cmd: str) -> bool:
        verb, _, rest = cmd.partition(" ")
        parts = rest.split()
        if verb == "set-option":
            pane = self.panes.get(parts[2])
            if pane is None:
                return False
            if parts[0] == "-pu":
                pane.pop(parts[3], None)
            else:
                pane[parts[3]] = parts[4]
            return True
        if verb == "rename-window":
            _, target, name = rest.split(" ", 2)
            pane = self.panes.get(target)
            if pane is None:
                return False
            for p in self.panes.values():
                if p["window_id"] == pane["window_id"]:
                    p["window_name"] = self._unquote(name)
            return True
        if verb in ("kill-window", "kill-pane"):
            pane = self.panes.get(parts[1])
            if pane is None:
                return False
            self._kill_window(pane)
            return True
        if verb == "respawn-pane":
            if self.respawn_fails:
                return False
            pane = self.panes.get(parts[parts.index("-t") + 1])
            if pane is None:
                return False
            self._next_pid += 1
            pane["pane_pid"] = str(self._next_pid)
            pane["pane_dead"] = "0"
            pane["start"] = rest.split(" ", parts.index("-t") + 2)[-1]
            return True
        raise AssertionError(f"unsupported branch command {cmd!r}")

    # -- the gateway ---------------------------------------------------------
    def run(self, args, timeout=None):
        args = list(args)
        self.calls.append(args)
        try:
            return self._run(args)
        finally:
            if self.after is not None:
                self.after(self, args)

    def _run(self, args):
        if self.unreachable:
            return -1, ""
        verb = args[0]
        if verb == "display-message":
            pane = self.panes.get(args[3])
            if pane is None:
                return 1, ""
            return 0, self._render(args[4], pane)
        if verb == "list-panes":
            fmt = args[-1]
            if "-a" in args:
                rows = list(self.panes.values())
            else:
                target = args[args.index("-t") + 1]
                assert target.startswith("=") and target.endswith(":"), target
                rows = [p for p in self.panes.values()
                        if p["session_name"] == target[1:-1]]
            return 0, "\n".join(self._render(fmt, p) for p in rows)
        if verb == "list-windows":
            target = args[args.index("-t") + 1]
            assert target.startswith("=") and target.endswith(":"), target
            seen, rows = set(), []
            for p in self.panes.values():
                if p["session_name"] == target[1:-1] and p["window_id"] not in seen:
                    seen.add(p["window_id"])
                    rows.append(self._render(args[-1], p))
            return 0, "\n".join(rows)
        if verb == "new-window":
            target = args[args.index("-t") + 1]
            session = target.lstrip("=").rstrip(":")
            if not self.new_window_creates or session not in self.sessions:
                return 1, ""
            pane_id = self.add(session, args[args.index("-n") + 1])
            self.panes[pane_id]["start"] = args[-1]
            fmt = args[args.index("-F") + 1]
            if self.new_window_answer is not None:
                return self.new_window_answer
            return 0, self._render(fmt, self.panes[pane_id])
        if verb == "set-option":
            return (0, "") if self._exec(" ".join(args)) else (1, "")
        if verb == "if-shell":
            pane = self.panes.get(args[3])
            if pane is None or not self._cond(args[4], pane):
                return 0, ""
            for cmd in args[5].split(" ; "):
                if not self._exec(cmd):
                    break
            return 0, ""
        raise AssertionError(f"unsupported tmux call {args!r}")


#: `_rec()`'s id, and the nonce every `restore-begin` below mints.
_RID, _NONCE = "7f3a2c1d", "deadbeef"
_ATTEMPT = f"aitask-restore-{_RID}-{_NONCE}"
_MARK = f"{_RID}:{_NONCE}"
_ENV = {"AITASK_RESTORE_RECORD": _RID, "AITASK_RESTORE_NONCE": _NONCE}


class _LaunchHarness(_SwapMixin):
    """Drives `_launch_into_new_window` against a `_Server`."""

    def _launch(self, server=None, *, sessions=None, boot=("", "stale_path"),
                env=None, spawn_effect=None, discover=None):
        server = server or _Server()
        self.swap_tmux(server)
        self.spawn = unittest.mock.Mock(return_value="%999", side_effect=spawn_effect)
        found = [_session()] if sessions is None else sessions
        disc = discover or unittest.mock.Mock(return_value=found)
        self.bootstrap = unittest.mock.Mock(return_value=boot)
        with unittest.mock.patch.object(agent_restore, "discover_aitasks_sessions", disc), \
             unittest.mock.patch.object(agent_restore, "_bootstrap_project_session",
                                        self.bootstrap), \
             unittest.mock.patch.object(agent_restore, "maybe_spawn_minimonitor",
                                        self.spawn), \
             _EnvGuard(AITASKS_TEST_MODE="1", AITASKS_RESTORE_FAIL_AT=None):
            result = agent_restore._launch_into_new_window(
                _rec(), "claude --resume sess-abc", dict(env or _ENV))
        self.server = server
        return result

    def new_window_argv(self) -> list[str]:
        calls = [c for c in self.server.calls if c[0] == "new-window"]
        self.assertEqual(1, len(calls), "exactly one window is created per attempt")
        return calls[0]


class TestNoProjectSessionBootstrapsOne(_LaunchHarness, unittest.TestCase):
    """`_launch_into_new_window` when no tmux session exists for the root (t1784).

    After a tmux server restart nothing may be attributed to the record's
    project, so the restore creates the project's OWN session through the
    canonical bootstrap in `--create-only` mode.

    The ownership rule is the point of this class. The restore may use a session
    that discovery attributed to the root BEFORE anything changed, or one this
    call itself CREATED — never a session that merely turns up under the root
    after a create was refused. `discover_aitasks_sessions` falls back to the
    `AITASKS_PROJECT_<session>` registry, so a foreign session CAN be attributed
    to this root through it.
    """

    def _boot(self, lookups, boot=("", "")):
        discover = unittest.mock.Mock(side_effect=[list(x) for x in lookups])
        result = self._launch(discover=discover, boot=boot)
        return result, discover

    def test_an_attributed_session_is_used_without_bootstrapping(self):
        result, _ = self._boot([[_session()]])
        self.assertEqual("", result[2])
        self.assertFalse(self.bootstrap.called,
                         "a session already attributed to the root needs no bootstrap")
        argv = self.new_window_argv()
        self.assertEqual("=aitasks:", argv[argv.index("-t") + 1])

    def test_no_session_bootstraps_the_projects_own_and_launches_into_it(self):
        result, _ = self._boot([[], [_session()]], boot=("aitasks", ""))
        self.assertEqual("", result[2], "a project with no tmux session must still restore (t1784)")
        self.bootstrap.assert_called_once_with(_ROOT)
        argv = self.new_window_argv()
        self.assertEqual("=aitasks:", argv[argv.index("-t") + 1])
        self.assertEqual(_ROOT, argv[argv.index("-c") + 1])

    def test_a_taken_session_name_is_refused_and_named(self):
        result, discover = self._boot([[], [], []], boot=("", "session_name_taken:aitasks"))
        self.assertEqual(
            ("", 0, f"no_session_for_root:{_ROOT}|bootstrap:session_name_taken:aitasks"),
            result)
        self.assertEqual([], [c for c in self.server.calls if c[0] == "new-window"])
        self.assertEqual(1, discover.call_count,
                         "a refused create must not be followed by a second lookup")

    def test_ownership_not_attribution_after_a_refused_create(self):
        """The clobbered-registry shape: a foreign `aitasks` session re-attributed
        to this root must still be refused — this call did not create it."""
        result, _ = self._boot([[], [_session()]], boot=("", "session_name_taken:aitasks"))
        self.assertEqual([], [c for c in self.server.calls if c[0] == "new-window"])
        self.assertTrue(result[2].startswith(f"no_session_for_root:{_ROOT}|"))

    def test_a_created_session_attributed_elsewhere_is_not_used(self):
        result, _ = self._boot([[], [_session(root="/somewhere/else")]], boot=("aitasks", ""))
        self.assertEqual([], [c for c in self.server.calls if c[0] == "new-window"])
        self.assertEqual("", result[0])
        self.assertIn("|bootstrap:created aitasks", result[2])

    def test_a_stale_project_root_names_the_cause(self):
        result, _ = self._boot([[], []], boot=("", "stale_path"))
        self.assertEqual(
            ("", 0, f"no_session_for_root:{_ROOT}|bootstrap:stale_path"), result)

    def test_an_unreadable_default_session_is_refused_and_named(self):
        """t1811: no session under a guessed name; the shape reaches `last_error`."""
        result, discover = self._boot([[], []],
                                      boot=("", "default_session_unreadable:block_scalar"))
        self.assertEqual(
            ("", 0, f"no_session_for_root:{_ROOT}"
                    "|bootstrap:default_session_unreadable:block_scalar"),
            result)
        self.assertEqual(1, discover.call_count)


class TestNewWindowRestoreSpawnsCompanion(_LaunchHarness, unittest.TestCase):
    """A new-window restore gets the minimonitor companion a normal launch gets (t1851).

    The companion must follow the RESTORED agent by identity — the launched pane
    — not whichever pane is active when the helper looks. A same-pane restore
    keeps its window, and its companion, and spawns nothing.
    """

    def test_a_new_window_launch_spawns_the_companion_once(self):
        pane, pid, err = self._launch()
        self.assertEqual("", err)
        self.assertEqual(1, self.spawn.call_count,
                         "a restored agent must not come back alone (t1851)")
        self.assertEqual(("aitasks", "agent-pick-1705"), self.spawn.call_args.args,
                         "the companion goes into the agent's window, by its final name")
        self.assertEqual(pane, self.spawn.call_args.kwargs.get("agent_pane"),
                         "the companion must follow the restored pane, not the active one")
        self.assertEqual(Path(_ROOT), self.spawn.call_args.kwargs.get("project_root"),
                         "the detached restore's cwd is not the project")

    def test_no_companion_when_the_launch_fails(self):
        server = _Server()
        server.new_window_creates = False
        _, _, err = self._launch(server)
        self.assertEqual("launch:rc=1", err)
        self.assertFalse(self.spawn.called)

    def test_no_companion_when_no_session_is_usable(self):
        _, _, err = self._launch(sessions=[])
        self.assertTrue(err.startswith("no_session_for_root:"))
        self.assertFalse(self.spawn.called)

    def test_a_companion_failure_does_not_fail_the_restore(self):
        """The agent is already running: a companion error must not roll it back."""
        pane, pid, err = self._launch(spawn_effect=RuntimeError("boom"))
        self.assertTrue(self.spawn.called)
        self.assertEqual("", err)
        self.assertTrue(pane.startswith("%"))

    def test_a_same_pane_restore_spawns_no_companion(self):
        self.swap_store(_RecordingStore(answers={
            "restore-begin": (0, "RESTORING:7f3a2c1d|deadbeef"),
            "restore-launched": (0, "LAUNCHED:7f3a2c1d"),
            "restore-confirm": (0, "LIVE:7f3a2c1d|liveness"),
        }))
        self.swap_tmux(_ScriptedTmux(dict(_TMUX_OURS_AND_FIRES)))
        new_window = unittest.mock.Mock(wraps=agent_restore._launch_into_new_window)
        spawn = unittest.mock.Mock(return_value="%901")
        with unittest.mock.patch.object(agent_restore, "_reread", return_value=_rec()), \
             unittest.mock.patch.object(agent_restore, "build_resume_argv",
                                        return_value="claude --resume sess-abc"), \
             unittest.mock.patch.object(agent_restore, "_launch_into_new_window",
                                        new_window), \
             unittest.mock.patch.object(agent_restore, "maybe_spawn_minimonitor", spawn), \
             unittest.mock.patch.object(ops, "restore_ack_grace", return_value=0):
            agent_restore.restore("7f3a2c1d")
        self.assertFalse(new_window.called, "the stand-in's own pane was reused")
        self.assertFalse(spawn.called,
                         "a same-pane restore keeps its companion; a second one is a duplicate")


class TestNewWindowAttemptIdentity(_LaunchHarness, unittest.TestCase):
    """The gone-pane launch never leaves an agent window nobody can identify (t1875).

    Each partial-success shape — `-P` lost, rc -1 after the server acted, the
    stamp not taking — either RECORDS the window (returns its pane) or REMOVES
    it with a name-guarded kill, and a kill that is not verified is named.
    """

    def _seamed(self, stages: str, server=None):
        server = server or _Server()
        with _EnvGuard(AITASKS_TEST_MODE="1", AITASKS_RESTORE_FAIL_AT=stages):
            self.swap_tmux(server)
            self.spawn = unittest.mock.Mock(return_value="%999")
            with unittest.mock.patch.object(agent_restore, "discover_aitasks_sessions",
                                            return_value=[_session()]), \
                 unittest.mock.patch.object(agent_restore, "maybe_spawn_minimonitor",
                                            self.spawn):
                result = agent_restore._launch_into_new_window(
                    _rec(), "claude --resume sess-abc", dict(_ENV))
        self.server = server
        return result

    def test_a_clean_launch_is_created_under_the_attempt_name_then_marked_and_renamed(self):
        pane, pid, err = self._launch()
        self.assertEqual("", err)
        argv = self.new_window_argv()
        self.assertEqual(_ATTEMPT, argv[argv.index("-n") + 1],
                         "tmux must name the window atomically with its creation")
        self.assertNotIn("-d", argv, "the restored window is selected, as always")
        p = self.server.panes[pane]
        self.assertEqual(_RID, p.get("@aitask_frozen"), "stamped for the rollback")
        self.assertEqual(_MARK, p.get("@aitask_restore_attempt"),
                         "marked: the claim that survives the rename")
        self.assertEqual("agent-pick-1705", p["window_name"],
                         "renamed to the `agent-` name monitor and companion key on")
        self.assertEqual(int(p["pane_pid"]), pid)

    def test_lost_P_output_is_identified_by_name_and_recorded(self):
        server = _Server()
        server.new_window_answer = (0, "")
        pane, _, err = self._launch(server)
        self.assertEqual("", err, "the window exists: it is recorded, not rolled back")
        self.assertEqual([pane], server.windows_named("agent-pick-1705"))

    def test_an_uncertain_rc_after_the_server_acted_is_identified_by_name(self):
        server = _Server()
        server.new_window_answer = (-1, "")
        pane, _, err = self._launch(server)
        self.assertEqual("", err)
        self.assertEqual(1, len(server.panes), "one window, no duplicate")

    def test_an_uncertain_rc_with_nothing_created_is_a_plain_failure(self):
        server = _Server()
        server.new_window_creates = False
        self.assertEqual(("", 0, "launch:rc=1"), self._launch(server))

    def test_an_unanswerable_lookup_names_the_attempt(self):
        pane, pid, err = self._seamed("identify,lookup")
        self.assertEqual(("", 0), (pane, pid))
        self.assertEqual(f"launch_uncertain:{_ATTEMPT}", err,
                         "the window may exist: the error must name it, not pass as clean")
        self.assertEqual([next(iter(self.server.panes))],
                         self.server.windows_named(_ATTEMPT),
                         "and the survivor stays identifiable by its attempt name")

    def test_a_stamp_that_does_not_take_is_removed_by_name(self):
        pane, _, err = self._seamed("stamp")
        self.assertEqual(("", "stamp"), (pane, err))
        self.assertEqual({}, self.server.panes, "the unstamped window was killed")
        kills = [c for c in self.server.calls if c[0] == "if-shell" and "kill-window" in c[-1]]
        self.assertEqual([f"#{{==:#{{window_name}},{_ATTEMPT}}}"], [k[4] for k in kills],
                         "the kill is guarded on this attempt's own name")

    def test_a_kill_that_does_not_take_is_named(self):
        pane, _, err = self._seamed("stamp,cleanup")
        self.assertEqual("", pane)
        self.assertTrue(err.startswith("stamp|cleanup:present:seam|pane:%"), err)

    def test_a_failed_rename_is_cosmetic(self):
        server = _Server()
        orig = server._exec

        def no_rename(cmd):
            return False if cmd.startswith("rename-window") else orig(cmd)
        server._exec = no_rename
        pane, _, err = self._launch(server)
        self.assertEqual("", err, "the agent is tracked by pane and marks, not by name")
        self.assertEqual(_ATTEMPT, server.panes[pane]["window_name"])

    def test_abandon_leaves_the_crash_end_state(self):
        pane, _, err = self._seamed("abandon")
        self.assertEqual(("", "abandon"), (pane, err))
        (p,) = self.server.panes.values()
        self.assertEqual((_RID, _MARK, "agent-pick-1705"),
                         (p.get("@aitask_frozen"), p.get("@aitask_restore_attempt"),
                          p["window_name"]))


def _survivor(server, *, pane_id=None, ready="", dead=False, mark=_MARK,
              window="agent-pick-1705", stamp=_RID):
    opts = {"@aitask_frozen": stamp} if stamp else {}
    if mark:
        opts["@aitask_restore_attempt"] = mark
    if ready:
        opts["@aitask_standin_ready"] = ready
    return server.add("aitasks", window, pane_id=pane_id, dead=dead, **opts)


class TestRestoreSurvivorGuard(_SwapMixin, unittest.TestCase):
    """`restore()` refuses to launch past a restore survivor (t1875).

    A survivor is an agent an earlier gone-pane attempt left running with no
    record tracking it. It usually sits in ANOTHER pane — invisible to the
    recorded-pane probe — and after a server restart it can sit at the very `%N`
    the record remembers, stamped like the stand-in.
    """

    STORE = {
        "restore-begin": (0, f"RESTORING:{_RID}|{_NONCE}"),
        "restore-launched": (0, f"LAUNCHED:{_RID}"),
        "restore-confirm": (0, f"LIVE:{_RID}|liveness"),
        "restore-abort": (0, f"ABORTING:{_RID}"),
        "standin-respawned": (0, f"FROZEN:{_RID}"),
    }

    def _restore(self, server, rec=None, *, reread=None, store=None):
        self.store = self.swap_store(_RecordingStore(answers=dict(store or self.STORE)))
        self.swap_tmux(server)
        rec = rec or _rec(pane_id="%104")
        with unittest.mock.patch.object(agent_restore, "_reread",
                                        side_effect=reread or (lambda _id: rec)), \
             unittest.mock.patch.object(agent_restore, "build_resume_argv",
                                        return_value="claude --resume sess-abc"), \
             unittest.mock.patch.object(agent_restore, "discover_aitasks_sessions",
                                        return_value=[_session()]), \
             unittest.mock.patch.object(agent_restore, "maybe_spawn_minimonitor",
                                        return_value="%999"), \
             unittest.mock.patch.object(ops, "restore_ack_grace", return_value=0), \
             _EnvGuard(AITASKS_TEST_MODE="1", AITASKS_RESTORE_FAIL_AT=None):
            return agent_restore.restore(_RID)

    def _destructive(self, server):
        return [c for c in server.calls
                if c[0] in ("new-window", "respawn-pane")
                or (c[0] == "if-shell" and ("respawn-pane" in c[-1] or "kill" in c[-1]))]

    def test_a_live_survivor_in_another_pane_blocks_before_any_write(self):
        server = _Server()
        s = _survivor(server)
        result = self._restore(server, _rec(pane_id=""))
        self.assertEqual("restore_survivor", result.outcome)
        self.assertEqual(
            f"RESTORE_FAILED:{_RID}|restore_survivor:aitasks:agent-pick-1705|pane:{s}",
            result.line)
        self.assertEqual([], self.store.calls, "no lease, no state change")
        self.assertEqual([], self._destructive(server), "no second agent, no kill")

    def test_a_name_only_survivor_blocks(self):
        server = _Server()
        _survivor(server, mark="", stamp="", window=_ATTEMPT)
        self.assertEqual("restore_survivor", self._restore(server, _rec(pane_id="")).outcome)

    def test_an_equal_id_survivor_is_never_respawned_as_the_stand_in(self):
        """The recorded `%104` came back as a survivor: stamped R, marked, no ready."""
        server = _Server()
        _survivor(server, pane_id="%104")
        result = self._restore(server, _rec(pane_id="%104"))
        self.assertEqual("restore_survivor", result.outcome)
        self.assertEqual([], self._destructive(server),
                         "respawn-pane -k over a running agent is the bug")
        self.assertEqual([], self.store.calls)

    def test_a_settled_viewer_with_a_stale_mark_is_not_a_survivor(self):
        """`@aitask_standin_ready == R` is the pane's own proof it is the viewer."""
        server = _Server()
        _survivor(server, pane_id="%104", ready=_RID)
        result = self._restore(server, _rec(pane_id="%104"))
        self.assertNotEqual("restore_survivor", result.outcome)
        self.assertEqual(1, len([c for c in server.calls
                                 if c[0] == "if-shell" and "respawn-pane" in c[-1]]),
                         "the same-pane branch runs")

    def test_another_records_survivor_does_not_block(self):
        server = _Server()
        _survivor(server, mark="0badf00d:12345678", stamp="0badf00d")
        self.assertNotEqual("restore_survivor",
                            self._restore(server, _rec(pane_id="")).outcome)

    def test_a_dead_survivor_is_removed_and_does_not_block(self):
        server = _Server()
        s = _survivor(server, dead=True)
        result = self._restore(server, _rec(pane_id=""))
        self.assertNotEqual("restore_survivor", result.outcome)
        self.assertNotIn(s, server.panes, "the dead attempt window was removed")

    def test_an_unreadable_server_fails_closed(self):
        server = _Server()
        server.unreachable = True
        result = self._restore(server, _rec(pane_id=""))
        self.assertEqual(f"RESTORE_FAILED:{_RID}|preflight:tmux unreachable", result.line)
        self.assertEqual([], self.store.calls)

    def test_a_survivor_appearing_before_the_lease_is_caught_under_it(self):
        """A concurrent restore abandoned an attempt between the two scans."""
        server = _Server()
        state = {"scans": 0}

        def after(srv, args):
            if args[0] == "list-panes" and "-a" in args:
                state["scans"] += 1
                if state["scans"] == 1:
                    _survivor(srv)
        server.after = after
        result = self._restore(server, _rec(pane_id=""))
        self.assertEqual("restore_survivor", result.outcome)
        self.assertEqual([], [c for c in server.calls if c[0] == "new-window"])
        self.assertIn("restore-abort", self.store.verbs(), "the lease is given back")


class TestNewWindowRollback(_SwapMixin, unittest.TestCase):
    """A rolled-back new-window restore puts the stand-in into THAT window (t1875)."""

    STORE = TestRestoreSurvivorGuard.STORE

    def _restore(self, server, store_answers, reread):
        self.store = self.swap_store(_RecordingStore(answers=store_answers))
        self.swap_tmux(server)
        with unittest.mock.patch.object(agent_restore, "_reread", side_effect=reread), \
             unittest.mock.patch.object(agent_restore, "build_resume_argv",
                                        return_value="claude --resume sess-abc"), \
             unittest.mock.patch.object(agent_restore, "discover_aitasks_sessions",
                                        return_value=[_session()]), \
             unittest.mock.patch.object(agent_restore, "maybe_spawn_minimonitor",
                                        return_value="%999"), \
             unittest.mock.patch.object(ops, "restore_ack_grace", return_value=0), \
             unittest.mock.patch.object(agent_sessions_mod(), "standin_command",
                                        return_value="standin 7f3a2c1d"), \
             _EnvGuard(AITASKS_TEST_MODE="1", AITASKS_RESTORE_FAIL_AT=None):
            return agent_restore.restore(_RID)

    def _mismatch(self, server):
        """The hook reports a DIFFERENT session: a nonce-scoped `last_error`."""
        frozen = _rec(pane_id="")
        reads = iter([frozen])

        def reread(_id):
            try:
                return next(reads)
            except StopIteration:
                return _rec(pane_id="", state="restoring",
                            last_error=f"{_NONCE}:session_mismatch")
        store = dict(TestRestoreSurvivorGuard.STORE)
        return self._restore(server, store, reread)

    def _respawn_rows(self):
        return [c for c in self.store.calls if c and c[0] == "standin-respawned"]

    def test_a_mismatch_rolls_back_INTO_the_new_window(self):
        server = _Server()
        result = self._mismatch(server)
        self.assertEqual("session_mismatch", result.outcome)
        (pane_id,) = server.panes
        (row,) = self._respawn_rows()
        self.assertEqual(pane_id, row[row.index("--pane") + 1],
                         "the record must track the new window, not the gone pane")
        p = server.panes[pane_id]
        self.assertEqual("standin 7f3a2c1d", self._unquoted(p["start"]),
                         "the stand-in replaced the agent in that window")
        self.assertIsNone(p.get("@aitask_restore_attempt"),
                          "the verified stand-in no longer carries the attempt mark")

    def _unquoted(self, s):
        return s.strip('"')

    def test_a_respawn_that_fails_after_the_unsets_keeps_the_attempt_mark(self):
        """`respawn_if_stamped` runs its `unset` BEFORE `respawn-pane`. If the mark
        were one of them, a failed respawn would strip the only claim of a
        still-running agent; the rollback would then commit a gone-pane record."""
        server = _Server()
        server.respawn_fails = True
        self._mismatch(server)
        (pane_id,) = server.panes
        p = server.panes[pane_id]
        self.assertEqual(_MARK, p.get("@aitask_restore_attempt"),
                         "the survivor keeps its claim")
        (row,) = self._respawn_rows()
        self.assertEqual("", row[row.index("--pane") + 1])
        for c in server.calls:
            if c[0] == "if-shell" and "respawn-pane" in c[-1]:
                self.assertNotIn("@aitask_restore_attempt", c[-1],
                                 "the mark is never in the pre-respawn unset")
        # ...and a retry is refused rather than launching a second agent.
        before = len([c for c in server.calls if c[0] == "new-window"])
        server.respawn_fails = False
        result = TestRestoreSurvivorGuard._restore(self, server, _rec(pane_id=""))
        self.assertEqual("restore_survivor", result.outcome)
        self.assertEqual(before, len([c for c in server.calls if c[0] == "new-window"]))

    def test_a_recycled_id_during_the_clear_keeps_the_strangers_mark(self):
        """A server restart between the verified respawn and the clear hands the
        `%N` to another record's attempt: the value guard must decline."""
        server = _Server()

        def after(srv, args):
            if args[0] == "if-shell" and "respawn-pane" in args[-1]:
                pane = srv.panes.get(args[3])
                if pane is not None and "@aitask_respawn_token" in pane:
                    pane["@aitask_restore_attempt"] = "0badf00d:12345678"
                    pane["@aitask_frozen"] = "0badf00d"
        server.after = after
        self._mismatch(server)
        (p,) = server.panes.values()
        self.assertEqual("0badf00d:12345678", p.get("@aitask_restore_attempt"))
        self.assertEqual("0badf00d", p.get("@aitask_frozen"))

    def test_the_success_clear_spares_a_recycled_strangers_marks(self):
        server = _Server()
        pane = server.add("aitasks", "agent-x", **{
            "@aitask_frozen": "0badf00d", "@aitask_restore_attempt": "0badf00d:12345678"})
        self.swap_tmux(server)
        agent_restore._clear_frozen_stamp(pane, _RID, _NONCE)
        p = server.panes[pane]
        self.assertEqual(("0badf00d", "0badf00d:12345678"),
                         (p.get("@aitask_frozen"), p.get("@aitask_restore_attempt")))

    def test_the_success_clear_retires_our_own_marks(self):
        server = _Server()
        pane = server.add("aitasks", "agent-x", **{
            "@aitask_frozen": _RID, "@aitask_restore_attempt": _MARK})
        self.swap_tmux(server)
        agent_restore._clear_frozen_stamp(pane, _RID, _NONCE)
        p = server.panes[pane]
        self.assertEqual((None, None),
                         (p.get("@aitask_frozen"), p.get("@aitask_restore_attempt")))


def agent_sessions_mod():
    return agent_restore.agent_sessions


class TestBootstrapHelper(unittest.TestCase):
    """`_bootstrap_project_session` — the subprocess contract (t1784).

    Only ``(<created session>, "")`` is ownership. Every other answer — an exit
    0 that did not report a creation included — comes back with an EMPTY
    session, so `_launch_into_new_window` never adopts a session by inference.
    """

    ROOT = "/proj/b"

    def _call(self, rc=0, stdout="", stderr="", raises=None):
        done = subprocess.CompletedProcess(args=[], returncode=rc,
                                           stdout=stdout, stderr=stderr)
        run = unittest.mock.Mock(return_value=done, side_effect=raises)
        with unittest.mock.patch.object(agent_restore.subprocess, "run", run):
            got = agent_restore._bootstrap_project_session(self.ROOT)
        return got, run

    def test_it_runs_the_canonical_bootstrap_in_create_only_mode(self):
        _, run = self._call(stdout="BOOTSTRAP_CREATED:aitasks\n")
        script = str(Path(agent_restore.__file__).resolve().parent / "tmux_bootstrap.sh")
        self.assertEqual(["bash", script, "--create-only", self.ROOT],
                         run.call_args.args[0])
        self.assertGreater(run.call_args.kwargs.get("timeout") or 0, 0,
                           "an unbounded bootstrap could outlive the restore's lease")

    def test_each_outcome_maps_as_documented(self):
        cases = [
            (dict(rc=0, stdout="BOOTSTRAP_CREATED:aitasks\n"), ("aitasks", "")),
            (dict(rc=0, stdout=""), ("", "no creation reported")),
            (dict(rc=43, stderr="BOOTSTRAP_FAILED:session_exists:aitasks\n"
                                "spawn_session_detached: session 'aitasks' already exists\n"),
             ("", "session_name_taken:aitasks")),
            (dict(rc=42, stderr="BOOTSTRAP_FAILED:stale_path\n"
                                "spawn_session_detached: not an aitasks project: /proj/b\n"),
             ("", "stale_path")),
            (dict(rc=4, stderr="spawn_session_detached: tmux new-session failed for 'aitasks'\n"),
             ("", "spawn_session_detached: tmux new-session failed for 'aitasks'")),
            (dict(rc=3, stderr=""), ("", "rc=3")),
        ]
        for kwargs, want in cases:
            with self.subTest(rc=kwargs["rc"], stdout=kwargs.get("stdout", "")):
                got, _ = self._call(**kwargs)
                self.assertEqual(want, got)

    def test_the_real_helper_refuses_an_unreadable_default_session(self):
        """t1811, end to end: the real `--create-only` bootstrap, unpatched.

        A config whose `tmux.default_session` is a block scalar. The helper must
        refuse before touching tmux (exit 44), and this parser must turn its real
        stderr into the named reason. A logging `tmux` stub sits first on PATH:
        if the refusal ever regressed, the create attempt would hit the stub, not
        a real server, and the empty log below would catch it. The stub is only
        reachable because `AIT_NO_SYSTEMD_RUN` disables the `systemd-run --user`
        spawn (whose `tmux` resolves through the user manager's PATH, not ours);
        the socket and TMUX_TMPDIR are isolated as a second barrier.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _root_with_config(
                str(Path(tmp) / "proj"), "tmux:\n  default_session: >-\n    x\n")
            stub_dir = Path(tmp) / "bin"
            stub_dir.mkdir()
            log = Path(tmp) / "tmux_calls.log"
            stub = stub_dir / "tmux"
            stub.write_text(f'#!/usr/bin/env bash\necho "$*" >> "{log}"\nexit 1\n')
            stub.chmod(0o755)
            with _EnvGuard(PATH=f"{stub_dir}{os.pathsep}{os.environ.get('PATH', '')}",
                           AIT_NO_SYSTEMD_RUN="1",
                           AITASKS_TMUX_SOCKET=f"t1811-test-{os.getpid()}",
                           TMUX_TMPDIR=tmp, TMUX=None):
                got = agent_restore._bootstrap_project_session(root)
            self.assertEqual(("", "default_session_unreadable:block_scalar"), got)
            self.assertFalse(log.exists() and log.read_text().strip(),
                             "a refused create must not call tmux at all")

    def test_a_timeout_and_a_spawn_error_are_reported_not_raised(self):
        got, _ = self._call(raises=subprocess.TimeoutExpired(cmd="bash", timeout=15))
        self.assertEqual(("", "timeout"), got)
        got, _ = self._call(raises=OSError("bash: not found"))
        self.assertEqual(("", "bash: not found"), got)


class TestRespawnFailureIsPersisted(_SwapMixin, unittest.TestCase):
    """The rollback reason must carry the launch error to the viewer (t1784).

    The coordinator's wire line goes to a detached `run-shell` job nobody reads,
    and the viewer that asked for the restore is replaced — so `last_error`,
    written by `restore-abort --error`, is the only channel by which the user
    learns WHY a restore failed. A bare `respawn` there hides the root and the
    bootstrap's verdict that `_launch_into_new_window` took care to name.
    """

    def test_the_rollback_reason_carries_the_launch_error(self):
        store = self.swap_store(_RecordingStore(answers={
            "restore-begin": (0, "RESTORING:7f3a2c1d|deadbeef"),
            "restore-abort": (0, "ABORTING:7f3a2c1d"),
            "standin-respawned": (0, "FROZEN:7f3a2c1d"),
        }))
        self.swap_tmux(_ScriptedTmux({3: (1, "")}))     # probe: the pane is gone
        err = "no_session_for_root:/x|bootstrap:session_name_taken:aitasks"
        with unittest.mock.patch.object(agent_restore, "_reread", return_value=_rec()), \
             unittest.mock.patch.object(agent_restore, "build_resume_argv",
                                        return_value="claude --resume sess-abc"), \
             unittest.mock.patch.object(agent_restore, "_launch_into_new_window",
                                        return_value=("", 0, err)):
            result = agent_restore.restore("7f3a2c1d")
        self.assertFalse(result.ok)
        self.assertIn(err, result.line)
        aborts = [list(c) for c in store.calls if c and c[0] == "restore-abort"]
        self.assertEqual(1, len(aborts))
        argv = aborts[0]
        self.assertIn("--error", argv)
        self.assertEqual(f"respawn:{err}", argv[argv.index("--error") + 1],
                         "the persisted reason must name the launch failure, "
                         "not just the stage")


class TestSeamsAreBoundToThisEngine(unittest.TestCase):
    """The failure seam must not be shared with the freeze engine."""

    def test_fail_at_is_bound_to_AITASKS_RESTORE_FAIL_AT(self):
        self.assertEqual("AITASKS_RESTORE_FAIL_AT",
                         getattr(agent_restore._fail_at, "env_var", None))

    def test_a_freeze_injection_does_not_fire_in_the_restore_engine(self):
        with _EnvGuard(AITASKS_TEST_MODE="1", AITASKS_FREEZE_FAIL_AT="begin"):
            agent_restore._fail_at("begin")   # must NOT raise



class TestSessionTargeting(unittest.TestCase):
    """`_resolve_target_session` (t1847): an explicit session is the ONLY target.

    `ait ide --session B` can open a second session of the same project. A
    gone-pane restore driven from it must land in B — never in the first
    session discovery happens to list, and never in a freshly bootstrapped one.
    """

    ROOT = str(REPO_ROOT)

    def _sessions(self, *names):
        return [types.SimpleNamespace(session=n, project_root=Path(self.ROOT))
                for n in names]

    def _checked(self, sessions, complete=True):
        return unittest.mock.patch.object(
            agent_restore, "discover_aitasks_sessions_checked",
            return_value=(sessions, complete))

    def test_explicit_session_wins_over_an_earlier_same_root_session(self):
        with self._checked(self._sessions("A", "B")):
            target, error = agent_restore._resolve_target_session(self.ROOT, "B")
        self.assertEqual(("B", ""), (target.session, error))

    def test_unattributed_session_fails_closed_without_bootstrap(self):
        with self._checked(self._sessions("A")), \
             unittest.mock.patch.object(agent_restore, "_bootstrap_project_session") as boot:
            target, error = agent_restore._resolve_target_session(self.ROOT, "C")
        self.assertIsNone(target)
        self.assertEqual("session_not_for_root:C", error)
        boot.assert_not_called()

    def test_a_session_of_another_root_fails_closed(self):
        other = [types.SimpleNamespace(session="C", project_root=Path("/elsewhere"))]
        with self._checked(self._sessions("A") + other):
            target, error = agent_restore._resolve_target_session(self.ROOT, "C")
        self.assertEqual((None, "session_not_for_root:C"), (target, error))

    def test_an_incomplete_scan_is_unverified_not_absent(self):
        with self._checked(self._sessions("A"), complete=False):
            target, error = agent_restore._resolve_target_session(self.ROOT, "C")
        self.assertEqual((None, "session_unverified:C"), (target, error))

    def test_explicit_session_never_uses_the_unchecked_discovery(self):
        """The unchecked discovery reads panes through a bare `=<s>` target,
        which tmux can resolve as a window of the CURRENT session (t1874)."""
        with self._checked(self._sessions("B")), \
             unittest.mock.patch.object(agent_restore, "discover_aitasks_sessions") as plain:
            agent_restore._resolve_target_session(self.ROOT, "B")
        plain.assert_not_called()

    def test_no_session_keeps_the_first_match(self):
        with unittest.mock.patch.object(agent_restore, "discover_aitasks_sessions",
                                        return_value=self._sessions("A", "B")):
            target, _ = agent_restore._resolve_target_session(self.ROOT)
        self.assertEqual("A", target.session)

    def test_restore_threads_the_session_into_the_gone_pane_launch(self):
        seen = {}

        def fake_launch(rec, command, env, session=None):
            seen["session"] = session
            return "", 0, f"session_not_for_root:{session}"

        rec = _rec(pane_id="")
        with unittest.mock.patch.object(agent_restore, "_reread", return_value=rec), \
             unittest.mock.patch.object(agent_restore, "build_resume_argv",
                                        return_value="claude --resume x"), \
             unittest.mock.patch.object(agent_restore, "_launch_into_new_window",
                                        side_effect=fake_launch), \
             unittest.mock.patch.object(agent_restore, "_rollback", return_value=""), \
             unittest.mock.patch.object(ops, "store",
                                        return_value=(0, "RESTORING:7f3a2c1d|abcd1234")):
            result = agent_restore.restore("7f3a2c1d", session="B")
        self.assertEqual("B", seen["session"])
        self.assertIn("session_not_for_root:B", result.line)

    def test_main_accepts_an_option_like_session_value(self):
        with unittest.mock.patch.object(agent_restore, "restore") as restore, \
             unittest.mock.patch("sys.stdout"):
            restore.return_value = agent_restore.RestoreResult("7f3a2c1d", True, "hook", "RESTORED:7f3a2c1d")
            rc = agent_restore.main(["restore", "7f3a2c1d", "--session", "-n"])
        self.assertEqual(0, rc)
        restore.assert_called_once_with("7f3a2c1d", repick=False, session="-n")

    def test_main_rejects_a_dotted_session(self):
        with unittest.mock.patch("sys.stderr"):
            self.assertEqual(2, agent_restore.main(
                ["restore", "7f3a2c1d", "--session", "a.b"]))

if __name__ == "__main__":
    unittest.main(verbosity=2)
