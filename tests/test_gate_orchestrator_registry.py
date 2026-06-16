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

def test_registry_keys():
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

def test_compute_unlocked_linear():
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


def test_compute_unlocked_dag():
    declared = ["a", "b", "c"]
    reg = {g: gl._default_gate_meta() for g in declared}
    reg["a"]["unlocks"] = ["b", "c"]  # explicit fan-out -> DAG mode
    # In DAG mode, b and c (absent) are TERMINAL, so they do NOT chain b->c.
    check("dag: only a unlocked initially", ["a"],
          go.compute_unlocked(declared, reg, state_of(), {}))
    check("dag: a pass -> b AND c unlocked (true parallel fan-out)", ["b", "c"],
          go.compute_unlocked(declared, reg, state_of(("a", "pass")), {}))


def test_compute_unlocked_budget():
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

def test_skip_satisfies_archive_and_deps():
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

def test_is_stuck():
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


for fn in (test_registry_keys, test_compute_unlocked_linear, test_compute_unlocked_dag,
           test_compute_unlocked_budget, test_skip_satisfies_archive_and_deps, test_is_stuck):
    fn()

print(f"\nResults: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
