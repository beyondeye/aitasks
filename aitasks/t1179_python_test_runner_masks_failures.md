---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [bash_scripts]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1171
implemented_with: claudecode/opus5
created_at: 2026-07-20 12:12
updated_at: 2026-07-28 19:22
boardcol: bug_fixes
boardidx: 10
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

## Restated acceptance criteria (2026-07-28, at implementation time)

Both defects were re-checked against live HEAD before implementing, and the
findings differ from the report above. This section supersedes the literal
claims in `## Upstream defect` and `## Suggested fix`; the original text is kept
verbatim for traceability. Full analysis in
`aiplans/p1179_python_test_runner_masks_failures.md`.

**(2) is already fixed — no work in this task.** t1211 (`26af930bb`, landed
after this task was filed) made `shortcut_scopes`' manifest sweep exec each TUI
module under a private `_PROBE_PREFIX` name instead of its canonical name; that
re-binding was what gave `AgentCommandScreen` a second class identity under full
discovery. `tests/test_shortcut_scopes.py` now pins the property in both
directions with a negative control, and a full run reports
`Ran 2479 tests … OK`, exit 0.

**(1) is real, but not by the stated mechanism.** The runner contains no
`Results:` line, and its last command runs under `set -euo pipefail`, so direct
execution already propagates the framework's status. What actually happens:
six *script-style* test modules print their own green tallies to **stdout**
while the framework verdict goes to **stderr**; redirected or piped, CPython
block-buffers stdout and flushes it at exit, so those green tallies land *below*
`FAILED`. And `… 2>&1 | tail -40` returns `tail`'s `0`, which is where the
reported "exits 0" came from. Revised criteria:

1. The status is propagated via an explicit captured `rc`, not as an accident of
   "last command wins".
2. The **last line of output is always a verdict derived from that status** —
   `PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`.
3. Body output is ordered truthfully (`PYTHONUNBUFFERED=1`).
4. The verdict/exit path is backend-independent by construction and exercised
   under **both** the pytest and unittest branches.
5. **Not fixed, by design:** a piped invocation still exits with the pipeline's
   status. No change to this script can alter that — only `set -o pipefail` or
   `${PIPESTATUS[0]}` in the *caller*. Documented in the runner header and
   `CLAUDE.md`; the stderr banner is what makes the truth survive `2>&1 | tail`
   even when the status does not.
6. **Out of scope:** wiring the suite into `.github/workflows/`. The suite takes
   ~12 minutes; CI wiring is a separate decision, deferred rather than absorbed.
7. **No `PYTHONPATH` regression:** `tests/test_runner_python_isolation.sh` and
   `tests/test_python_bootstrap_isolation.sh` (t1236, recovered by t1306) stay
   green. Nothing in this task touches `PYTHONPATH`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-28T16:19:48Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-29T07:18:35Z status=pass attempt=1 type=human
