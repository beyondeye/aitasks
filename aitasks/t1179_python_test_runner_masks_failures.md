---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [bash_scripts]
gates: [risk_evaluated]
anchor: 1171
created_at: 2026-07-20 12:12
updated_at: 2026-07-20 12:12
boardidx: 80
---

## Origin

Spawned from t1171 during Step 8b review.

## Upstream defect

- `tests/run_all_python_tests.sh:22-26 — runner masks failures: prints "Results: 25 passed, 0 failed" and exits 0 while the unittest phase beneath it reports FAILED (14 failures + 2 errors of 1765). A real regression in any Python test would be invisible to anyone trusting the exit code or summary line. Compounded by .github/workflows/ containing zero references to tests/, so nothing else catches it.`
- `tests/test_agent_command_dialog_default_session.py:21 — order-dependent dual-import failure: passes in isolation, fails in the full suite with "AgentCommandScreen() is not an instance of <class 'agent_command_screen.AgentCommandScreen'>". The module is loaded under two distinct names, so isinstance identity breaks depending on which test ran first. Pre-existing; present on clean HEAD.`

## Diagnostic context

Surfaced while verifying t1171 (removing the Codex `/plan` injection). That
change deleted `tests/test_codex_plan_invoke.py`, so the Python suite was run to
confirm no import breakage. The wrapper exited 0 and printed
`Results: 25 passed, 0 failed`, but the unittest output immediately above it
read `Ran 1765 tests ... FAILED (failures=4, errors=1)`.

To determine whether t1171 had caused those failures, a detached git worktree at
clean HEAD was created and the same suite run there:

| | failures | errors | tests |
|---|---|---|---|
| clean HEAD (baseline) | 14 | 2 | 1765 |
| with t1171 changes | 4 | 1 | 1765 |

Two findings fall out of that comparison:

1. **The runner's exit code and summary line are both wrong.** Exit 0 plus
   "0 failed" while 16 tests fail. `run_all_python_tests.sh:22-26` dispatches to
   pytest (or falls back to `unittest discover`) but the final `Results:` line
   and the script's exit status do not reflect that phase's outcome. Anyone —
   human or agent — trusting the summary would conclude the suite is green.
2. **Failure counts vary run-to-run on identical code** (14+2 vs 4+1 across the
   same 1765 tests), which means the suite is order-dependent. The named example
   passes in isolation on clean HEAD and only fails in the full run, with an
   `isinstance` identity mismatch — the classic signature of one module being
   imported under two distinct names (`agent_command_screen` vs
   `tests.agent_command_screen`), producing two distinct class objects.

Both are pre-existing and independent of t1171, which edited no Python source.

## Suggested fix

For (1): propagate the real exit status from the pytest/unittest invocation and
derive the `Results:` line from it, so a failing suite exits non-zero. Consider a
regression test that runs the runner against a deliberately failing fixture test
and asserts a non-zero exit — otherwise the masking can silently return.

For (2): pin a single import path for the TUI modules under test (consistent
`sys.path` / package-qualified imports) so `isinstance` identity holds regardless
of test order. Fixing (1) first is worthwhile, since it is what makes (2) and any
future breakage visible at all.
