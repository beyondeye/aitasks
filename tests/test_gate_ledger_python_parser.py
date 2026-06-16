#!/usr/bin/env python3
"""Structured Python parser tests for lib/gate_ledger.py (t635_8)."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
GATE_LEDGER_PATH = PROJECT_DIR / ".aitask-scripts" / "lib" / "gate_ledger.py"
GATE_SH = PROJECT_DIR / ".aitask-scripts" / "aitask_gate.sh"

spec = importlib.util.spec_from_file_location("gate_ledger", GATE_LEDGER_PATH)
assert spec is not None and spec.loader is not None
gate_ledger = importlib.util.module_from_spec(spec)
sys.modules["gate_ledger"] = gate_ledger
spec.loader.exec_module(gate_ledger)


PASS = 0
FAIL = 0
TOTAL = 0


def assert_eq(desc: str, expected, actual) -> None:
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if expected == actual:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {desc} (expected {expected!r}, got {actual!r})")


def assert_true(desc: str, actual) -> None:
    assert_eq(desc, True, bool(actual))


def assert_false(desc: str, actual) -> None:
    assert_eq(desc, False, bool(actual))


FIXTURE = """---
priority: high
status: Implementing
gates: [plan_approved, build_verified, review_approved]
also_blocks_dependents: [docs_updated]
---

## Context
Body.

## Gate Runs

> **❌ gate:build_verified** run=2026-01-01T00:00:00Z status=fail attempt=1 duration=4s type=machine
>
> Verifier: `build`
> Result: failed
> Log: `.aitask-gates/t10/build.log`

> **✅ gate:plan_approved** run=2026-01-01T00:01:00Z status=pass attempt=1 type=human
>
> Note: approved

> **✅ gate:build_verified** run=2026-01-01T00:02:00Z status=pass attempt=2 duration=3s type=machine
>
> Verifier: `build`
> Result: passed
> Log: `.aitask-gates/t10/build2.log`

> **⏸ gate:review_approved** run=2026-01-01T00:03:00Z status=pending type=human
>
> Awaiting: `.aitask-gates/t10/review.signed`
"""


def write_registry(path: Path) -> None:
    path.write_text(
        """gates:
  plan_approved:
    type: human
    blocks_dependents: false
  build_verified:
    type: machine
    blocks_dependents: true
  review_approved:
    type: human
    blocks_dependents: true
  docs_updated:
    type: machine
    blocks_dependents: false
""",
        encoding="utf-8",
    )


def test_structured_parse() -> None:
    runs = gate_ledger.parse_gate_run_blocks(FIXTURE)
    assert_eq("four gate runs parsed", 4, len(runs))
    assert_eq("first gate name", "build_verified", runs[0].name)
    assert_eq("first gate status", "fail", runs[0].status)
    assert_eq("first gate attempt", "1", runs[0].attempt)
    assert_eq("first gate verifier body field", "build", runs[0].body_fields["verifier"])
    assert_eq("first gate log body field strips ticks", ".aitask-gates/t10/build.log", runs[0].body_fields["log"])
    assert_eq("arbitrary body field parsed", ".aitask-gates/t10/review.signed", runs[3].body_fields["awaiting"])
    assert_true("line number is populated", runs[0].line_number > 0)
    assert_true("raw marker preserved", runs[0].raw_marker.startswith("> **"))
    assert_true("raw body lines preserved", runs[0].raw_body_lines)


def test_current_state_and_legacy_compat() -> None:
    current = gate_ledger.derive_gate_runs(FIXTURE)
    assert_eq("last run wins for build_verified", "pass", current["build_verified"].status)
    assert_eq("latest build attempt retained", "2", current["build_verified"].attempt)
    legacy = gate_ledger.derive_status(FIXTURE)
    assert_eq("legacy derive_status keeps dict shape", "pass", legacy["build_verified"]["status"])
    assert_false("legacy dict does not expose body_fields", "body_fields" in legacy["build_verified"])
    marker_dicts = gate_ledger.parse_gate_runs(FIXTURE)
    assert_eq("legacy parse_gate_runs count", 4, len(marker_dicts))
    assert_eq("legacy marker dict has icon", "✅", marker_dicts[1]["icon"])


def test_prefilter_and_empty() -> None:
    assert_true("marker prefilter detects ledger markers", gate_ledger.has_gate_markers(FIXTURE))
    assert_false("marker prefilter ignores ordinary task", gate_ledger.has_gate_markers("---\nstatus: Ready\n---\nbody\n"))
    assert_eq("empty format status", "", gate_ledger.format_status("no markers"))
    assert_eq("empty structured state", {}, gate_ledger.derive_gate_runs("no markers"))


def test_task_gate_state() -> None:
    with tempfile.TemporaryDirectory(prefix="gate_state_") as tmp:
        task = Path(tmp) / "t10_demo.md"
        registry = Path(tmp) / "gates.yaml"
        task.write_text(FIXTURE, encoding="utf-8")
        write_registry(registry)

        state = gate_ledger.read_task_gate_state(str(task), str(registry))
        assert_eq("declared gates read from task", ["plan_approved", "build_verified", "review_approved"], state.declared_gates)
        assert_eq("archive waits for review", "BLOCKED", state.archive_decision)
        assert_eq("archive pending review", ["review_approved"], state.archive_pending)
        assert_eq("deps wait for review plus also_blocks_dependents", "BLOCKED", state.dependents_decision)
        assert_eq("deps pending list", ["review_approved", "docs_updated"], state.dependents_pending)
        assert_eq("resume point from checkpoints", "IMPLEMENT", state.resume_point)
        assert_true("status text includes current build pass", "build_verified: pass (attempt 2" in state.status_text)


def test_bash_status_parity() -> None:
    with tempfile.TemporaryDirectory(prefix="gate_status_parity_") as tmp:
        task_dir = Path(tmp) / "aitasks"
        task_dir.mkdir()
        (task_dir / "t10_demo.md").write_text(FIXTURE, encoding="utf-8")
        env = os.environ.copy()
        env["TASK_DIR"] = str(task_dir)
        bash_status = subprocess.check_output([str(GATE_SH), "status", "10"], cwd=PROJECT_DIR, env=env, text=True).strip()
        py_status = gate_ledger.format_status(FIXTURE)
        assert_eq("python format_status matches bash status", bash_status, py_status)


def main() -> int:
    test_structured_parse()
    test_current_state_and_legacy_compat()
    test_prefilter_and_empty()
    test_task_gate_state()
    test_bash_status_parity()

    print("")
    print("==========================")
    print(f"Results: {PASS}/{TOTAL} passed, {FAIL} failed")
    print("==========================")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
