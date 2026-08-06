#!/usr/bin/env python3
"""Unit tests for the orchestrator's registry parsing + pure decision logic (t635_11).

Covers the parts that must be testable WITHOUT subprocesses / agents:
  - gate_ledger.read_registry parses the new keys and distinguishes
    `unlocks` ABSENT (None) from explicit `[]` (concern 1);
  - gate_orchestrator.compute_unlocked is pure over in-memory state, including
    the global linear-vs-DAG mode and skip-as-satisfied;
  - gate_ledger.archive_status / dependents_status treat `skip` as satisfied
    (concern 2).

Run: python3 tests/test_gate_orchestrator_registry.py
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".aitask-scripts", "lib"))

import gate_ledger as gl  # noqa: E402
import gate_orchestrator as go  # noqa: E402

PASS = 0
FAIL = 0


def check(desc, expected, actual):
    global PASS, FAIL
    if expected == actual:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {desc}\n  expected: {expected!r}\n  actual:   {actual!r}")


def _write(text):
    fd, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w") as fh:
        fh.write(text)
    return path


# --- GateRun stand-in for pure compute_unlocked tests ----------------------

class _Run:
    def __init__(self, name, status, run="r", note=""):
        self.name = name
        self.fields = {"status": status, "run": run}
        self.body_fields = {"note": note} if note else {}

    @property
    def status(self):
        return self.fields["status"]

    @property
    def run_id(self):
        return self.fields["run"]


def state_of(*pairs):
    return {n: _Run(n, s) for n, s in pairs}


# --- registry parsing: absent vs [] + new keys -----------------------------

def _check_registry_keys():
    reg = _write(
        "gates:\n"
        "  a:\n"
        "    type: machine\n"
        "    verifier: aitask-gate-a\n"
        "    max_retries: 3\n"
        "    timeout_seconds: 120\n"
        "    unlocks: [b, c]\n"
        "  b:\n"
        "    type: machine\n"
        "    unlocks:\n"
        "      - c\n"
        "  c:\n"
        "    type: machine\n"
        "    unlocks: []\n"
        "  d:\n"
        "    type: human\n"
        "    signal: file-touch\n"
        "    signal_target: \".aitask-gates/<task-id>/d.signed\"\n"
    )
    r = gl.read_registry(reg)
    os.unlink(reg)
    check("gate names not polluted", {"a", "b", "c", "d"}, set(r))
    check("inline unlocks list", ["b", "c"], r["a"]["unlocks"])
    check("verifier parsed", "aitask-gate-a", r["a"]["verifier"])
    check("max_retries int", 3, r["a"]["max_retries"])
    check("timeout_seconds int", 120, r["a"]["timeout_seconds"])
    check("block-form unlocks list", ["c"], r["b"]["unlocks"])
    check("explicit [] is empty list (terminal)", [], r["c"]["unlocks"])
    check("ABSENT unlocks -> None (distinct from [])", None, r["d"]["unlocks"])
    check("human signal", "file-touch", r["d"]["signal"])
    check("human signal_target", ".aitask-gates/<task-id>/d.signed", r["d"]["signal_target"])
    check("defaults: verifier empty when absent", "", r["b"]["verifier"])
    check("defaults: max_retries 0 when absent", 0, r["b"]["max_retries"])


# --- compute_unlocked: linear vs DAG, skip-as-satisfied --------------------

def _check_compute_unlocked_linear():
    declared = ["a", "b", "c"]
    reg = {g: gl._default_gate_meta() for g in declared}  # all unlocks absent
    # nothing run yet -> only first gate unlocked (pure linear)
    check("linear: only first unlocked", ["a"],
          go.compute_unlocked(declared, reg, state_of(), {}))
    # a passed -> b unlocked
    check("linear: a pass -> b unlocked", ["b"],
          go.compute_unlocked(declared, reg, state_of(("a", "pass")), {}))
    # a SKIPPED -> b still unlocked (skip is satisfied)
    check("linear: a skip -> b unlocked (skip satisfies)", ["b"],
          go.compute_unlocked(declared, reg, state_of(("a", "skip")), {}))


def _check_compute_unlocked_dag():
    declared = ["a", "b", "c"]
    reg = {g: gl._default_gate_meta() for g in declared}
    reg["a"]["unlocks"] = ["b", "c"]  # explicit fan-out -> DAG mode
    # In DAG mode, b and c (absent) are TERMINAL, so they do NOT chain b->c.
    check("dag: only a unlocked initially", ["a"],
          go.compute_unlocked(declared, reg, state_of(), {}))
    check("dag: a pass -> b AND c unlocked (true parallel fan-out)", ["b", "c"],
          go.compute_unlocked(declared, reg, state_of(("a", "pass")), {}))


def _check_compute_unlocked_budget():
    declared = ["a"]
    reg = {"a": gl._default_gate_meta()}
    reg["a"]["max_retries"] = 1  # budget 2
    runs = {"a": [_Run("a", "fail"), _Run("a", "fail")]}  # 2 fails used
    check("budget exhausted -> not unlocked", [],
          go.compute_unlocked(declared, reg, state_of(("a", "fail")), runs))
    runs1 = {"a": [_Run("a", "fail")]}  # 1 fail used, budget remains
    check("budget remaining -> unlocked", ["a"],
          go.compute_unlocked(declared, reg, state_of(("a", "fail")), runs1))


# --- skip satisfies archive / dependents -----------------------------------

def _check_skip_satisfies_archive_and_deps():
    task = _write(
        "---\n"
        "status: Implementing\n"
        "gates: [build_verified, docs_updated]\n"
        "also_blocks_dependents: [docs_updated]\n"
        "---\n"
        "Body.\n"
        "\n"
        "## Gate Runs\n"
        "\n"
        "> **✅ gate:build_verified** run=r1 status=pass attempt=1\n"
        "\n"
        "> **⏭ gate:docs_updated** run=r2 status=skip attempt=1\n"
    )
    reg = _write(
        "gates:\n"
        "  build_verified:\n"
        "    type: machine\n"
        "    blocks_dependents: true\n"
        "  docs_updated:\n"
        "    type: machine\n"
        "    blocks_dependents: false\n"
    )
    dec, pending = gl.archive_status(task)
    check("skip does not block archive", "ALL_PASS", dec)
    dec2, pend2 = gl.dependents_status(task, reg)
    check("skip satisfies a blocks_dependents/also gate", "SATISFIED", dec2)
    os.unlink(task)
    os.unlink(reg)


# --- is_stuck purity (current-digest comparison) ---------------------------

def _check_is_stuck():
    # two trailing fails on the SAME current digest -> stuck
    runs = [
        _Run("g", "running", run="r1", note="stuckhash:AAA"),
        _Run("g", "fail", run="r1"),
        _Run("g", "running", run="r2", note="stuckhash:AAA"),
        _Run("g", "fail", run="r2"),
    ]
    check("two same-digest fails -> stuck", True, go.is_stuck(runs, "AAA"))
    check("code changed (digest BBB) -> not stuck", False, go.is_stuck(runs, "BBB"))
    check("no digest available -> not stuck", False, go.is_stuck(runs, None))
    one = [
        _Run("g", "running", run="r1", note="stuckhash:AAA"),
        _Run("g", "fail", run="r1"),
    ]
    check("single fail -> not stuck (one transient retry allowed)", False,
          go.is_stuck(one, "AAA"))


def _check_next_attempt_and_live_run():
    """The attempt ORDINAL counts terminal runs only, and is deliberately NOT the
    retry-BUDGET count (t1262)."""
    def ledger(*markers):
        """Each marker is `<gate> <k=v ...>`; rendered as a real marker line."""
        body = ""
        for m in markers:
            name, _, fields = m.partition(" ")
            body += f"> **x gate:{name}** {fields}\n\n"
        return "## Gate Runs\n\n" + body

    check("no runs -> attempt 1", 1, gl.next_attempt(ledger(), "g"))
    check("one fail -> attempt 2", 2,
          gl.next_attempt(ledger("g run=r1 status=fail attempt=1"), "g"))
    # The running block does not advance the counter: its closer shares its number.
    check("running + fail is ONE attempt -> next is 2", 2,
          gl.next_attempt(ledger("g run=r1 status=running attempt=1",
                                 "g run=r1 status=fail attempt=1"), "g"))
    check("running alone consumes nothing -> attempt 1", 1,
          gl.next_attempt(ledger("g run=r1 status=running attempt=1"), "g"))
    check("pending consumes nothing -> attempt 1", 1,
          gl.next_attempt(ledger("g run=r1 status=pending"), "g"))
    check("skip is terminal -> attempt 2", 2,
          gl.next_attempt(ledger("g run=r1 status=skip attempt=1"), "g"))
    check("other gates are not counted", 1,
          gl.next_attempt(ledger("h run=r1 status=fail attempt=1"), "g"))

    # The ordinal/budget split, pinned so a future refactor cannot silently
    # collapse the two into one function.
    class _R:
        def __init__(self, status):
            self.status = status
    check("_attempts_used counts a pass as 0 budget spent", 0,
          go._attempts_used([_R("pass")]))
    check("...while the ordinal counts it as a run", 2,
          gl.next_attempt(ledger("g run=r1 status=pass attempt=1"), "g"))

    # live_run: at most one, closed by a terminal marker with the same run id.
    check("no live run on an empty ledger", None, gl.live_run(ledger(), "g"))
    check("open running run is live", ("r1", "1"),
          gl.live_run(ledger("g run=r1 status=running attempt=1"), "g"))
    check("a terminal marker for the same run id closes it", None,
          gl.live_run(ledger("g run=r1 status=running attempt=1",
                             "g run=r1 status=fail attempt=1"), "g"))
    check("a terminal marker for a DIFFERENT run leaves it live", ("r2", "2"),
          gl.live_run(ledger("g run=r1 status=fail attempt=1",
                             "g run=r2 status=running attempt=2"), "g"))
    # A `pending` for the same run id ends the window too: `--only-if-running`
    # takes the LAST marker for that id, so a run left pending can no longer be
    # closed and must not be reported live (t1262).
    check("a pending marker for the same run id ends the live window", None,
          gl.live_run(ledger("g run=r1 status=running attempt=1",
                             "g run=r1 status=pending"), "g"))
    check("a later running marker re-opens the window", ("r1", "2"),
          gl.live_run(ledger("g run=r1 status=running attempt=1",
                             "g run=r1 status=pending",
                             "g run=r1 status=running attempt=2"), "g"))
    check("a run with no run id is never live", None,
          gl.live_run(ledger("g status=running attempt=1"), "g"))


_CHECKS = (_check_registry_keys, _check_compute_unlocked_linear, _check_compute_unlocked_dag,
           _check_compute_unlocked_budget, _check_skip_satisfies_archive_and_deps, _check_is_stuck,
           _check_next_attempt_and_live_run)


def main() -> int:
    for fn in _CHECKS:
        fn()

    print(f"\nResults: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


class ScriptChecksTest(unittest.TestCase):
    """Collects this file's script-style checks under unittest discovery (t1211).

    ``check()`` tallies into ``FAIL`` instead of raising, so the assertion is on
    ``main()``'s return code; the per-check detail is printed to stdout.
    """

    def test_all_checks_pass(self):
        self.assertEqual(main(), 0, "script checks failed — see stdout above")


if __name__ == "__main__":
    sys.exit(main())
