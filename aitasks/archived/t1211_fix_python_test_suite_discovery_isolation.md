---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [testing, python]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1229]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-07-22 11:08
updated_at: 2026-07-24 10:57
completed_at: 2026-07-24 10:57
boardcol: bug_fixes
boardidx: 40
---

## Origin

Spawned from t1208 during Step 8b review.

## Upstream defect

- `tests/run_all_python_tests.sh:26 — full-suite unittest discovery yields 4 failures + 1 error in TUI switcher / agent-command tests (e.g. tests/test_tui_switcher_agent_launch.py:250, "AgentCommandScreen() is not an instance of <class 'agent_command_screen.AgentCommandScreen'>") that pass in isolation; a module imported under two identities during discovery breaks isinstance checks, making the aggregate suite unusable as a gate.`
- `tests/test_gate_orchestrator_registry.py:203 — calls sys.exit() at import time, so unittest discovery reports it as a collection ERROR and the aggregate run exits non-zero regardless of the code under test.`

## Diagnostic context

Observed while verifying t1208 (em-dash truncation in the verification
checklist parser). The task's own suites were all green:

- `tests.test_verification_parse` + `tests.test_verification_section_headers`
  → 54 pass, exit 0
- `tests/test_verification_followup.sh` → 32/32
- Negative controls fire correctly (reverting the fix makes both suites exit 1)

But `bash tests/run_all_python_tests.sh` (1791 tests) reported
`FAILED (failures=4, errors=1)`. Narrowing:

- `python3 -m unittest tests.test_tui_switcher_agent_launch` alone → 14/14 OK.
- `python3 -m unittest discover -s tests -p 'test_[amt]*.py'` (320 tests,
  covering the TUI switcher, agent-command and minimonitor modules) → OK.

So the failures only appear in the *full* discovery set: some other module
loads `agent_command_screen` under a second identity (a `spec_from_file_location`
/ `sys.modules` assignment, or a second entry reachable via the
`.aitask-scripts/board` + `.aitask-scripts/lib` PYTHONPATH), after which
`assertIsInstance(screen, AgentCommandScreen)` compares two distinct classes
with the same name. Every test module in the repo imports it plainly as
`from agent_command_screen import AgentCommandScreen`, so the second identity
is introduced indirectly and needs tracing.

Note: pytest is not installed in this environment, so `run_all_python_tests.sh`
takes its `unittest discover` fallback branch (line 26). Whether the same
breakage occurs under the pytest branch (line 23) is untested and worth
checking — the two branches have different import semantics.

## Impact

The aggregate Python suite cannot currently be used as a pass/fail gate: it
exits non-zero on a clean tree, so a real regression is indistinguishable from
the standing noise. Each task must instead hand-pick its own modules, which is
exactly the check most likely to be skipped.

## Suggested fix

1. Trace the duplicate import of `agent_command_screen` (e.g. run discovery
   with a `sys.modules` audit hook, or bisect the module set) and make the
   offending test import it by the same name as everyone else.
2. Give `tests/test_gate_orchestrator_registry.py` an
   `if __name__ == "__main__":` guard around its `sys.exit(...)` so it is
   importable under discovery.
3. Once both are fixed, confirm `bash tests/run_all_python_tests.sh` exits 0 on
   a clean tree — and, per the "prove the harness can fail" rule, that a
   deliberately broken assertion still makes it exit 1.

## Acceptance criteria

- [ ] `bash tests/run_all_python_tests.sh` exits 0 on a clean tree (no failures, no collection errors).
- [ ] A deliberately failing assertion in any collected test makes the runner exit 1.
- [ ] `tests/test_gate_orchestrator_registry.py` is importable under discovery and still works when run directly.
- [ ] The root cause of the duplicate `agent_command_screen` identity is identified and fixed, not worked around by skipping the affected tests.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-22T15:44:01Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-24T07:52:45Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-24T07:57:12Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:f2493192b4ae6491

> **✅ gate:risk_evaluated** run=2026-07-24T07:57:12Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1211/risk_evaluated_2026-07-24T07:57:12Z-risk_evaluated-a1.log`
