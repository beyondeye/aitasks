---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [codex, frozen, session_persistence]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [2110]
assigned_to: dario-e@beyond-eye.com
anchor: 2040
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-20 11:01
updated_at: 2026-10-21 15:33
completed_at: 2026-10-21 15:33
---

## Origin

Spawned from t2046 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/agent_sessions.py:1951 (codex_session_for_pid, depth-0 only)` + `.aitask-scripts/lib/agent_freeze.py:_CODEX_DISPROVING_MISSES` — a codex typed at a shell prompt in an aitasks pane has the SHELL as its pane pid. The observation therefore returns `MISS_NOT_CODEX`, and the freeze clears a codex id that the hook validly recorded (an in-process TUI passes t2047's ancestry walk). The restore then degrades to re-pick. Found by code reading, not measured live.

## Diagnostic context

- `codex_session_for_pid` deliberately inspects depth 0 only: "The pane's process
  IS the agent (launches exec through)". Descending would let a claude pane whose
  Bash tool ran codex capture that child's rollout.
- The framework's own launches exec through, so the pane pid is codex. A codex the
  user types into a shell prompt does not: the pane pid is the shell.
- For an **in-process** hand-started codex (one run with
  `-c tui.alternate_screen=never`), the SessionStart hook records the session.
  The pane pid (the shell) is an ancestor, and there is no daemon hop, so t2047's
  guard passes. The freeze then sees `MISS_NOT_CODEX` on the stamped path, and
  `_CODEX_DISPROVING_MISSES` clears the codex-owned id.
- A daemon-routed hand-started codex is not affected: since t2047 it gets no hook
  id at all. Tracked separately in t2076.
- t2046 split the disproving misses (`_CODEX_FD_DISPROOFS` = no_match, ambiguous).
  `not_codex` still clears a stored **codex** id on both the stamped and the
  unstamped path.

## Suggested fix

Measure first: a live hand-started in-process codex in a shell pane, one turn,
then freeze. If confirmed, distinguish "the pane process is a shell whose direct
child is the codex holding the rollout" from "the pane now runs something else".
For example:
- inspect exactly one level of children, only when the pane process is a known
  shell and exactly one direct child is codex;
- keep the claude-Bash-tool exclusion (a codex child of a non-shell agent
  process must never count).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-21T09:51:55Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-21T12:26:40Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-21T12:33:17Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:f3ec89d287047552

> **✅ gate:risk_evaluated** run=2026-10-21T12:33:17Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2077/risk_evaluated_2026-10-21T12:33:17Z-risk_evaluated-a1.log`
