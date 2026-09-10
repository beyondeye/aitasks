"""Contract tests for the shared frozen-agent plumbing (t1738).

`lib/agent_frozen_ops.py` exists so the freeze engine (`lib/agent_freeze.py`)
and the restore coordinator (`lib/agent_restore.py`, t1705_5) share one
definition of the store's wire protocol instead of forking it. That makes its
surface a **cross-module contract**, and the freeze suite only pins it
*incidentally* — through the members `agent_freeze` happens to call. Three
promised exports have no caller there at all (`test_mode`, `SESSIONS_SH`,
`PANE_FACT_FORMAT` / `PANE_FACT_KEYS`), so a rename or omission would ship green
and surface only when the second engine is written against a name that is not
there.

This file also enforces the two rules the module docstring states and nothing
else checks:

* the **seam rule** — `store` and `_TMUX` are swapped in place by tests, so every
  consumer must reach them by late binding; an import-time alias in an engine
  module binds the original object and misses the swap;
* the **one-way dependency arrow** — this module must never import either
  engine, because reconcile has to keep settling abandoned restores with no
  coordinator present.

No tmux, no store file, no `agent_sessions`.

Run: python3 tests/test_agent_frozen_ops.py
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

import agent_freeze  # noqa: E402
import agent_frozen_ops as ops  # noqa: E402

#: Every name the module promises its consumers. Written from the contract, not
#: read back from the module — a list derived from `dir(ops)` would pin nothing.
PROMISED_CALLABLES = (
    "store", "store_show", "nonce_from", "run",
    "pane_facts", "pane_location", "set_option", "unset_option", "respawn",
    "int_or_zero", "test_mode", "make_fail_at", "pause_at",
    # t1773: the tri-state resolver promoted out of `agent_freeze` (the restore
    # coordinator may not import that module), plus the atomic respawn it feeds.
    "probe_pane", "tmux_quote", "respawn_if_stamped",
)
PROMISED_VALUES = (
    "StageFailure", "SESSIONS_SH", "PANE_FACT_FORMAT", "PANE_FACT_KEYS",
    "EXIT_LOCK_BUSY", "EXIT_TRANSITION_REFUSED", "EXIT_NONCE_MISMATCH",
    "EXIT_LEASE_HELD",
    "TMUX_UNREACHABLE", "PROBE_PANE_FORMAT", "PROBE_PANE_KEYS",
    "RESPAWN_PROBE_FORMAT",
)

#: Engine modules that import the shared surface. `agent_restore` joins this
#: list in t1705_5 — it is looked up dynamically so this file needs no edit then.
ENGINE_MODULES = ("agent_freeze", "agent_restore")


class _RecordingStore:
    """Stands in for the `aitask_agent_sessions.sh` wrapper invocation."""

    def __init__(self, rc: int = 0, out: str = "") -> None:
        self.calls: list[tuple[str, ...]] = []
        self.rc = rc
        self.out = out

    def __call__(self, *argv: str, timeout: float = 20.0):
        self.calls.append(tuple(argv))
        return self.rc, self.out


class _FakeTmux:
    """Records gateway argv and replays one scripted answer."""

    def __init__(self, rc: int = 0, out: str = "") -> None:
        self.calls: list[list[str]] = []
        self.timeouts: list[float | None] = []
        self.rc = rc
        self.out = out

    def run(self, args, timeout=None):
        self.calls.append(list(args))
        self.timeouts.append(timeout)
        return self.rc, self.out


class _SwapMixin:
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


class SurfaceContractTests(unittest.TestCase):
    """Case 1 — the promised names exist, including the ones nothing calls."""

    def test_every_promised_callable_is_present_and_callable(self):
        missing = [n for n in PROMISED_CALLABLES if not hasattr(ops, n)]
        self.assertEqual(missing, [], (
            "agent_frozen_ops no longer exports these. The surface is a "
            "cross-module contract shared with the restore coordinator "
            "(t1705_5) — a member that moves or is renamed must be RE-PINNED "
            f"here, not dropped: {missing}"))
        not_callable = [n for n in PROMISED_CALLABLES if not callable(getattr(ops, n))]
        self.assertEqual(not_callable, [], f"promised functions are not callable: {not_callable}")

    def test_every_promised_value_is_present(self):
        missing = [n for n in PROMISED_VALUES if not hasattr(ops, n)]
        self.assertEqual(missing, [], (
            "agent_frozen_ops no longer exports these constants/classes. "
            f"Re-pin them rather than dropping them: {missing}"))

    def test_the_exit_codes_match_the_wrapper_table(self):
        # The values, not merely the names: an engine branches on them, and a
        # silently changed code turns a refusal into an unhandled failure.
        self.assertEqual(
            (ops.EXIT_LOCK_BUSY, ops.EXIT_TRANSITION_REFUSED,
             ops.EXIT_NONCE_MISMATCH, ops.EXIT_LEASE_HELD),
            (3, 5, 6, 8),
            "wrapper exit codes drifted from `aitask_agent_sessions.sh`'s header")

    def test_the_pane_fact_format_and_keys_stay_in_step(self):
        self.assertEqual(len(ops.PANE_FACT_FORMAT.split("\t")),
                         len(ops.PANE_FACT_KEYS),
                         "PANE_FACT_FORMAT and PANE_FACT_KEYS must have equal arity — "
                         "pane_facts() rejects any read whose field count differs")


class StoreLateBindingTests(_SwapMixin, unittest.TestCase):
    """Case 2 — swapping `ops.store` redirects everything built on it."""

    def test_store_show_reaches_the_swapped_store(self):
        fake = self.swap_store(_RecordingStore(0, "state:frozen\npane_id:%3\n"))
        fields = ops.store_show("abc123")
        self.assertEqual(fake.calls, [("show", "abc123")],
                         "store_show must call `store` by module-global lookup; a "
                         "`from … import store` alias would bypass the swap")
        self.assertEqual(fields, {"state": "frozen", "pane_id": "%3"})

    def test_store_show_returns_empty_on_a_refusal(self):
        self.swap_store(_RecordingStore(ops.EXIT_TRANSITION_REFUSED, "REFUSED:x"))
        self.assertEqual(ops.store_show("abc123"), {})

    def test_nonce_from_reads_the_pipe_tail(self):
        self.assertEqual(ops.nonce_from("FREEZING:abc123|deadbeef"), "deadbeef")
        self.assertEqual(ops.nonce_from("LEASED:abc123|  n1  "), "n1")
        self.assertEqual(ops.nonce_from("NO_PIPE"), "")


class TmuxLateBindingTests(_SwapMixin, unittest.TestCase):
    """Case 3 — swapping `ops._TMUX` redirects every gateway caller."""

    def test_run_delegates_to_the_swapped_client(self):
        fake = self.swap_tmux(_FakeTmux(0, "ok\n"))
        self.assertEqual(ops.run(["list-panes"]), (0, "ok\n"))
        self.assertEqual(fake.calls, [["list-panes"]])
        self.assertEqual(fake.timeouts, [None],
                         "omitting the timeout must leave the gateway's own default in force")

    def test_run_forwards_an_explicit_timeout(self):
        fake = self.swap_tmux(_FakeTmux())
        ops.run(["capture-pane"], timeout=30.0)
        self.assertEqual(fake.timeouts, [30.0])

    def test_pane_facts_issues_one_display_message_and_maps_positionally(self):
        values = [
            "aitasks", "agent-pick-1705", "%1", "4242", "0", "/tmp/proj",
            "rec1", "", "", "sess-abc",
        ]
        fake = self.swap_tmux(_FakeTmux(0, "\t".join(values) + "\n"))
        facts = ops.pane_facts("%1")
        self.assertEqual(fake.calls,
                         [["display-message", "-p", "-t", "%1", ops.PANE_FACT_FORMAT]])
        self.assertEqual(facts, dict(zip(ops.PANE_FACT_KEYS, values)))

    def test_pane_facts_returns_empty_on_a_short_read(self):
        self.swap_tmux(_FakeTmux(0, "only\ttwo\n"))
        self.assertEqual(ops.pane_facts("%1"), {},
                         "a field-count mismatch is a gone/unreadable pane, not a partial dict")

    def test_pane_facts_returns_empty_on_a_failed_read(self):
        self.swap_tmux(_FakeTmux(1, ""))
        self.assertEqual(ops.pane_facts("%1"), {})

    def test_pane_location_parses_the_pair(self):
        fake = self.swap_tmux(_FakeTmux(0, "%1\t8888\n"))
        self.assertEqual(ops.pane_location("%1"), ("%1", 8888))
        self.assertEqual(fake.calls[0][:4], ["display-message", "-p", "-t", "%1"])

    def test_pane_location_reports_the_gone_pane_pair(self):
        for rc, out in ((0, "\t8888\n"), (0, "%1\n"), (0, "%1\tnope\n"), (1, "")):
            with self.subTest(rc=rc, out=out):
                self.swap_tmux(_FakeTmux(rc, out))
                self.assertEqual(ops.pane_location("%1"), ("", 0))

    def test_set_and_unset_option_use_the_p_and_pu_forms(self):
        fake = self.swap_tmux(_FakeTmux(0, ""))
        self.assertTrue(ops.set_option("%1", "@aitask_frozen", "rec1"))
        self.assertTrue(ops.unset_option("%1", "@aitask_standin_ready"))
        self.assertEqual(fake.calls, [
            ["set-option", "-p", "-t", "%1", "@aitask_frozen", "rec1"],
            ["set-option", "-pu", "-t", "%1", "@aitask_standin_ready"],
        ])

    def test_option_writes_report_a_refusal(self):
        self.swap_tmux(_FakeTmux(1, ""))
        self.assertFalse(ops.set_option("%1", "@aitask_frozen", "rec1"))
        self.assertFalse(ops.unset_option("%1", "@aitask_frozen"))

    def test_respawn_passes_dash_k(self):
        fake = self.swap_tmux(_FakeTmux(0, ""))
        self.assertTrue(ops.respawn("%1", "ait frozenagent --record rec1"))
        self.assertEqual(fake.calls, [
            ["respawn-pane", "-k", "-t", "%1", "ait frozenagent --record rec1"],
        ])
        self.swap_tmux(_FakeTmux(1, ""))
        self.assertFalse(ops.respawn("%1", "cmd"))


class ProbePaneTests(_SwapMixin, unittest.TestCase):
    """The tri-state resolver (t1773). Its three verdicts must stay apart.

    `gone` and `unknown` mean opposite things to a caller: the first says the
    pane is not there, the second says we could not find out. `drop_record`
    fails closed on `unknown` rather than skipping its kill; the restore router
    fails closed rather than launching a second agent beside a live stand-in.
    Collapsing them re-introduces V9 in one direction and a duplicate agent in
    the other.
    """

    def test_a_present_pane_maps_its_three_facts_positionally(self):
        tmux = self.swap_tmux(_FakeTmux(out="%104\tabc123\t0"))
        verdict, facts = ops.probe_pane("%104")
        self.assertEqual("present", verdict)
        self.assertEqual({"pane_id": "%104", "frozen": "abc123", "dead": "0"}, facts)
        self.assertEqual(
            [["display-message", "-p", "-t", "%104", ops.PROBE_PANE_FORMAT]],
            tmux.calls, "one round trip, asking about the pane DIRECTLY")

    def test_a_nonzero_rc_is_gone(self):
        self.swap_tmux(_FakeTmux(rc=1, out=""))
        self.assertEqual(("gone", None), ops.probe_pane("%104"))

    def test_an_unreachable_tmux_is_UNKNOWN_never_gone(self):
        self.swap_tmux(_FakeTmux(rc=ops.TMUX_UNREACHABLE, out=""))
        self.assertEqual(
            ("unknown", None), ops.probe_pane("%104"),
            "rc -1 means tmux could not be reached — NOT that the pane is gone")

    def test_a_short_read_is_gone(self):
        self.swap_tmux(_FakeTmux(out="%104\tabc123"))
        self.assertEqual(("gone", None), ops.probe_pane("%104"))

    def test_an_empty_pane_id_is_gone(self):
        # `display-message -p -t <gone pane>` exits ZERO with empty output on
        # tmux 3.x, so the field is the only usable signal.
        self.swap_tmux(_FakeTmux(out="\t\t"))
        self.assertEqual(("gone", None), ops.probe_pane("%104"))

    def test_the_format_and_keys_stay_in_step(self):
        self.assertEqual(len(ops.PROBE_PANE_FORMAT.split("\t")),
                         len(ops.PROBE_PANE_KEYS))


class TmuxQuoteTests(unittest.TestCase):
    """One nesting level for tmux's own lexer, for commands inside `if-shell`."""

    def test_it_escapes_the_three_characters_tmux_acts_on(self):
        self.assertEqual(r'"a\\b \"c\" \$d"', ops.tmux_quote(r'a\b "c" $d'))

    def test_a_command_with_single_quotes_survives(self):
        # tmux single-quotes are fully literal with no escape, so the
        # double-quote form is the only one that can carry these at all — and
        # agent command strings routinely contain them.
        out = ops.tmux_quote("""sh -c 'printf %s "hi"; ls > /tmp/x'""")
        self.assertTrue(out.startswith('"') and out.endswith('"'))
        self.assertIn("'printf %s", out, "single quotes pass through untouched")
        self.assertIn(r'\"hi\"', out, "double quotes are escaped")
        self.assertIn(";", out, "a command separator must survive verbatim")

    def test_an_ordinary_command_is_merely_wrapped(self):
        self.assertEqual('"claude --resume sess-abc"',
                         ops.tmux_quote("claude --resume sess-abc"))


class RespawnIfStampedTests(_SwapMixin, unittest.TestCase):
    """The atomic stamp-checked respawn, and above all its EVIDENCE rule.

    `if-shell` exits 0 whether or not its branch ran, so the helper needs proof.
    A pid delta is not proof: across a tmux server restart the before-read and
    the after-read can describe two different panes, so a correctly REJECTED
    dispatch still shows a changed pid. Reading that as success hands the caller
    a stranger's pane and pid — which `restore-confirm` would then
    liveness-confirm as the restored agent.
    """

    class _Seq:
        """Replays one scripted answer per call, in order."""

        def __init__(self, answers):
            self.answers = list(answers)
            self.calls: list[list[str]] = []

        def run(self, args, timeout=None):
            self.calls.append(list(args))
            answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
            return answer

    def _run(self, answers, **kw):
        tmux = self.swap_tmux(self._Seq(answers))
        kw.setdefault("option", "@aitask_frozen")
        kw.setdefault("expect", "abc123")
        result = ops.respawn_if_stamped("%104", "claude --resume s", **kw)
        return result, tmux

    def _token_of(self, tmux) -> str:
        branch = next(c for c in tmux.calls if c and c[0] == "if-shell")[-1]
        return branch.split("@aitask_respawn_token ", 1)[1].split()[0]

    def test_the_dispatch_is_one_if_shell_carrying_the_whole_branch(self):
        _, tmux = self._run(
            [(0, "9999"), (0, ""), (0, "tok\t%104\t51000\t9999")],
            env={"A": "1", "B": "2"}, unset="@aitask_standin_ready")
        dispatch = next(c for c in tmux.calls if c and c[0] == "if-shell")
        self.assertEqual(["if-shell", "-F", "-t", "%104"], dispatch[:4])
        self.assertEqual("#{==:#{@aitask_frozen},abc123}", dispatch[4],
                         "the stamp check must be the if-shell CONDITION, so the "
                         "server evaluates it in the same command-queue run")
        branch = dispatch[-1]
        self.assertIn("set-option -pu -t %104 @aitask_standin_ready ;", branch)
        self.assertIn("respawn-pane -k -e A=1 -e B=2 -t %104 ", branch)
        self.assertTrue(
            branch.rstrip().split(" ; ")[-1].startswith("set-option -p -t %104 "
                                                        "@aitask_respawn_token "),
            "the token must be written LAST, so its presence also proves the "
            "respawn ahead of it succeeded (an if-shell sequence aborts on error)")

    def test_the_token_is_fresh_on_every_call(self):
        seen = set()
        for _ in range(2):
            _, tmux = self._run([(0, "9999"), (0, ""), (0, "no\t%104\t51000\t9999")])
            seen.add(self._token_of(tmux))
        self.assertEqual(2, len(seen),
                         "a reused token would let a STALE option read as this "
                         "call's evidence")

    def test_our_token_coming_back_is_the_only_success(self):
        class _Echo(self._Seq):
            def run(self, args, timeout=None):
                if args and args[0] == "display-message" and len(self.calls) >= 2:
                    tok = self.token
                    self.calls.append(list(args))
                    return 0, f"{tok}\t%104\t51000\t9999"
                if args and args[0] == "if-shell":
                    self.token = args[-1].split("@aitask_respawn_token ", 1)[1].split()[0]
                return super().run(args, timeout)

        tmux = self.swap_tmux(_Echo([(0, "9999"), (0, "")]))
        fired, pane, pid, reason = ops.respawn_if_stamped(
            "%104", "cmd", option="@aitask_frozen", expect="abc123")
        self.assertEqual((True, "%104", 51000, ""), (fired, pane, pid, reason))
        self.assertIn(["set-option", "-pu", "-t", "%104", "@aitask_respawn_token"],
                      tmux.calls, "a per-attempt token must not outlive the attempt")

    def test_a_CHANGED_PID_WITHOUT_the_token_is_NOT_success(self):
        """The whole reason the token exists.

        This is what a server restart between the pre-read and the dispatch
        looks like from here: the branch was correctly rejected (no token), but
        the recorded `%N` now belongs to a stranger whose pid differs.
        """
        (fired, pane, pid, reason), _ = self._run(
            [(0, "9999"), (0, ""), (0, "\t%104\t77777\t12345")])
        self.assertFalse(fired, "a pid delta is not evidence that the branch ran")
        self.assertEqual(("", 0), (pane, pid),
                         "handing back a location would let the caller adopt a "
                         "stranger's pane as its restored agent")
        self.assertEqual("server-restarted", reason)

    def test_no_token_within_the_same_server_generation_is_a_stamp_mismatch(self):
        (fired, pane, pid, reason), _ = self._run(
            [(0, "9999"), (0, ""), (0, "\t%104\t77777\t9999")])
        self.assertEqual((False, "", 0, "stamp-mismatch"), (fired, pane, pid, reason))

    def test_a_foreign_token_is_not_ours(self):
        (fired, _, _, reason), _ = self._run(
            [(0, "9999"), (0, ""), (0, "somebodyelse\t%104\t51000\t9999")])
        self.assertFalse(fired)
        self.assertEqual("stamp-mismatch", reason)

    def test_a_failed_pre_read_dispatches_nothing_at_all(self):
        (fired, pane, pid, reason), tmux = self._run([(1, "")])
        self.assertEqual((False, "", 0, "pane-gone"), (fired, pane, pid, reason))
        self.assertEqual([], [c for c in tmux.calls if c and c[0] == "if-shell"],
                         "nothing may be dispatched at a pane we could not read")

    def test_a_short_after_read_is_not_success(self):
        (fired, _, _, reason), _ = self._run([(0, "9999"), (0, ""), (0, "tok\t%104")])
        self.assertEqual((False, "pane-gone"), (fired, reason))

class SeamRuleTests(unittest.TestCase):
    """Case 4 — no engine module import-aliases a swapped name."""

    def test_no_engine_binds_a_global_to_the_original_store_or_client(self):
        banned = {id(ops.store): "store", id(ops._TMUX): "_TMUX"}
        offenders: list[str] = []
        checked: list[str] = []
        for mod_name in ENGINE_MODULES:
            module = sys.modules.get(mod_name)
            if module is None:
                try:
                    module = __import__(mod_name)
                except ImportError:
                    continue          # not shipped yet (agent_restore, t1705_5)
            checked.append(mod_name)
            for name, value in vars(module).items():
                if id(value) in banned:
                    offenders.append(f"{mod_name}.{name} -> agent_frozen_ops.{banned[id(value)]}")
        self.assertIn("agent_freeze", checked,
                      "anti-vacuity: the engine list must reach at least agent_freeze")
        self.assertEqual(offenders, [], (
            "These engine globals are import-time ALIASES of a swapped name. The "
            "tests replace `agent_frozen_ops.store` / `._TMUX` in place, and an "
            "alias binds the original object, so the swap is silently bypassed. "
            f"Call them through the module instead — `frozen_ops.store(...)`: {offenders}"))

    def test_agent_freeze_reaches_the_shared_module_itself(self):
        self.assertIs(agent_freeze.frozen_ops, ops,
                      "agent_freeze must hold the module object, not a copy of its members")


class DependencyArrowTests(unittest.TestCase):
    """Case 5 — the shared module never depends on an engine."""

    def test_the_source_imports_neither_engine(self):
        src = Path(ops.__file__).read_text()
        code = "\n".join(
            line for line in src.splitlines()
            if line.startswith(("import ", "from ")) or line.lstrip().startswith(("import ", "from "))
        )
        for engine in ENGINE_MODULES:
            self.assertNotIn(engine, code, (
                f"agent_frozen_ops must never import {engine}. Reconcile has to settle "
                "abandoned restores with no coordinator present, so nothing it depends "
                "on may reach back toward one."))

    def test_no_engine_module_object_is_bound_in_the_namespace(self):
        bound = [n for n, v in vars(ops).items()
                 if getattr(v, "__name__", None) in ENGINE_MODULES]
        self.assertEqual(bound, [], f"engine modules bound in agent_frozen_ops: {bound}")


class SeamGateTests(unittest.TestCase):
    """Case 6 — the failure/pause seams are test-mode-gated and per-engine."""

    def setUp(self):
        for var in ("AITASKS_TEST_MODE", "AITASKS_FREEZE_FAIL_AT",
                    "AITASKS_RESTORE_FAIL_AT", "AITASKS_FROZEN_PAUSE_AT"):
            os.environ.pop(var, None)
            self.addCleanup(os.environ.pop, var, None)

    def test_test_mode_is_true_only_for_the_exact_value(self):
        self.assertFalse(ops.test_mode())
        os.environ["AITASKS_TEST_MODE"] = "0"
        self.assertFalse(ops.test_mode())
        os.environ["AITASKS_TEST_MODE"] = "yes"
        self.assertFalse(ops.test_mode())
        os.environ["AITASKS_TEST_MODE"] = "1"
        self.assertTrue(ops.test_mode())

    def test_fail_at_raises_only_under_test_mode(self):
        fail_at = ops.make_fail_at("AITASKS_FREEZE_FAIL_AT")
        os.environ["AITASKS_FREEZE_FAIL_AT"] = "begin"
        fail_at("begin")            # inert: no AITASKS_TEST_MODE
        os.environ["AITASKS_TEST_MODE"] = "1"
        with self.assertRaises(ops.StageFailure) as caught:
            fail_at("begin")
        self.assertEqual(caught.exception.stage, "begin")
        fail_at("commit")           # a different stage is not the armed one

    def test_the_two_engines_seams_are_isolated(self):
        """The reason `make_fail_at` is a factory rather than one function."""
        os.environ["AITASKS_TEST_MODE"] = "1"
        os.environ["AITASKS_RESTORE_FAIL_AT"] = "begin"
        freeze_fail = ops.make_fail_at("AITASKS_FREEZE_FAIL_AT")
        restore_fail = ops.make_fail_at("AITASKS_RESTORE_FAIL_AT")
        freeze_fail("begin")        # the restore seam must not fire here
        with self.assertRaises(ops.StageFailure):
            restore_fail("begin")

    def test_the_shipped_freeze_engine_uses_its_own_variable(self):
        self.assertEqual(getattr(agent_freeze._fail_at, "env_var", None),
                         "AITASKS_FREEZE_FAIL_AT")

    def test_pause_at_is_inert_without_test_mode(self):
        # A live SIGSTOP would hang the runner, so only the inert path is driven
        # here; `tests/test_freeze_engine_live.sh` exercises the armed one.
        os.environ["AITASKS_FROZEN_PAUSE_AT"] = "respawn"
        ops.pause_at("respawn")
        os.environ["AITASKS_TEST_MODE"] = "1"
        ops.pause_at("some-other-stage")


class IntOrZeroTests(unittest.TestCase):
    def test_missing_and_malformed_fields_degrade_to_zero(self):
        for value in (None, "", "nope", [], {}):
            with self.subTest(value=value):
                self.assertEqual(ops.int_or_zero(value), 0)

    def test_numeric_fields_parse(self):
        self.assertEqual(ops.int_or_zero("4242"), 4242)
        self.assertEqual(ops.int_or_zero(7), 7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
