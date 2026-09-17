---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-17 11:31
updated_at: 2026-09-17 22:52
---

## Origin

Spawned from t1825 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/tmux_bootstrap.sh:376 — _tmux_bootstrap_resolve_session (and its Python twin agent_launch_utils.read_default_session_status) accept a hand-edited tmux.default_session containing '.' or ':'; only ait setup's writer and, since t1825, ait ide --session reject those tmux target separators, so a hand-edited config still hands tmux a session it cannot address`

## Diagnostic context

t1825 (code commit `50b865dda`) added `_tmux_bootstrap_session_name_ok` in
`tmux_bootstrap.sh`: it returns 1 for a name holding `.` or `:`.
- `ait ide --session` dies on such a name.
- `aitask_setup.sh::setup_tmux_default_session` warns and falls back to `aitasks`
  before writing.

The configured-value path is not covered. With
`tmux:\n  default_session: a.b\n`, `_tmux_bootstrap_resolve_session` prints
`a.b` with rc 0, and `read_default_session_status` returns `("a.b", None)`: a
dotted name is a valid YAML plain scalar, so neither line reader reports it.
The YAML-backed `load_tmux_defaults` (board, monitors, agentcrew) reads the
same `a.b`, so every reader agrees on a name tmux cannot target.

## Suggested fix

- Decide whether an illegal configured name is a new problem shape (e.g.
  `illegal_tmux_name`) reported by both twins, so they fall back to `aitasks`
  with the sentinel. Or keep the readers YAML-faithful and validate at the
  consumers that hand the name to tmux (`ait ide`, bootstrap, agentcrew/monitor
  session creation).
- If it becomes a shape:
  - Add it to `DEFAULT_SESSION_PROBLEM_SHAPES`.
  - Note that `load_tmux_defaults` would then diverge unless it applies the same
    check.
  - Extend `tests/test_tmux_default_session_resolvers.py` and
    `tests/test_ide_session_override.sh`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-17T19:45:32Z status=pass attempt=1 type=human
>
> Note: drift

> **✅ gate:plan_approved** run=2026-09-17T19:52:20Z status=pass attempt=2 type=human

> **✅ gate:review_approved** run=2026-09-17T20:33:08Z status=pass attempt=1 type=human
