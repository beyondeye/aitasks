---
priority: medium
effort: medium
depends: [777]
issue_type: test
status: Ready
labels: [testing, test_infrastructure, triage]
created_at: 2026-05-18 18:58
updated_at: 2026-05-18 18:58
boardidx: 50
---

## Context

Spawned from t734 (test-scaffold helper port) during the regression-baseline
capture. Before t734 began porting, the whole-suite run on `main` reported
**11 pre-existing failures** unrelated to the helper change. t734's
acceptance bar was "no NEW failures introduced by the port" — explicitly out
of scope for that task. The same 11 are still failing after the port (the
port is a true no-op against them).

This task triages the 11 failures once t777 (modular pick skill — large
multi-child parent that touches `task-workflown`, profile flow, and several
TUIs) lands, since several of the failing tests are TUI / tmux / skill-render
tests that t777's restructuring may either fix or replace.

## Pre-existing failures (captured 2026-05-18 on `main`, commit a124727a)

```
tests/test_codeagent.sh
tests/test_kill_agent_pane_smart.sh
tests/test_multi_session_monitor.sh
tests/test_multi_session_primitives.sh
tests/test_opencode_setup.sh
tests/test_skill_verify.sh
tests/test_tmux_control_resilience.sh
tests/test_tmux_control.sh
tests/test_tmux_exact_session_targeting.sh
tests/test_tmux_run_parity.sh
tests/test_tui_switcher_multi_session.sh
```

Group by surface (preliminary, refine during triage):

- **tmux / multi-session control** (6 tests): `test_tmux_control.sh`,
  `test_tmux_control_resilience.sh`, `test_tmux_exact_session_targeting.sh`,
  `test_tmux_run_parity.sh`, `test_kill_agent_pane_smart.sh`,
  `test_tui_switcher_multi_session.sh`, `test_multi_session_monitor.sh`,
  `test_multi_session_primitives.sh`. Likely share a single root cause
  (tmux fixture / environment assumption that no longer holds, or a
  Textual/tmux interaction broken on this branch).
- **Setup / agent surfaces** (3 tests): `test_codeagent.sh`,
  `test_opencode_setup.sh`, `test_skill_verify.sh`. These are unrelated to
  tmux and likely have distinct root causes.

## Why wait for t777

t777 is in flight and:
- Swaps `task-workflown` → `task-workflow` (t777_23), which touches the
  exact code path that `test_skill_verify.sh` exercises.
- Restructures the pick-skill stub surface (t777_6 → t777_15), which
  affects skill rendering / verify tests.
- Likely touches profile-aware execution paths used by `test_codeagent.sh`.

Running the triage **after** t777 lands avoids burning effort on failures
that the t777 work will either fix outright or migrate into a different
test shape.

## Approach

1. **Re-baseline.** After t777 archives, re-run the whole-suite driver loop
   (see t734 plan §3) and capture the new failure set. Some of the 11 may
   be gone; some may have shifted.
2. **Triage per-test.** For each remaining failure:
   - Reproduce locally (`bash tests/<file>` with stderr captured).
   - Classify root cause: environment (tmux availability, terminal
     capability, hostname assumption), pre-existing code bug, stale test
     fixture, or genuine regression introduced between baseline date and
     re-baseline date.
3. **File individual tasks.** Group failures with the same root cause into
   one fix task; one-off failures get one task each. Use `bug` issue_type
   for code defects and `test` for fixture/environment issues.
4. **No batch fix here.** This task is the *triage*, not the fix. The
   triage output is N follow-up tasks (one per root cause). Per
   `aidocs/planning_conventions.md` "Audit-only tasks": if a failure has
   no fix worth filing (e.g., test asserts on an OS-specific tmux version
   no longer supported), document the dismissal in the plan and don't
   spawn a task.

## Verification

- Whole-suite run captured post-t777 and saved as the new baseline.
- Each remaining failure has either: (a) a filed follow-up task with a
  pointer back to this task, or (b) a documented dismissal in the plan
  with rationale.
- Plan file's "Final Implementation Notes" lists every triage decision so
  future audits can reconstruct the logic.

## Out of scope

- Fixing any of the failures (each fix is its own task spawned by triage).
- Touching tests t734 already ported — those are green and tracked by
  the new helper.
- Any work that doesn't reduce to "is failure X still real, and if so,
  what's the root cause?"
