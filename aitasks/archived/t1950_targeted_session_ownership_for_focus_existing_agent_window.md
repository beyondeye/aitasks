---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: performance
status: Done
labels: [tmux, aitask_board]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1946
implemented_with: claudecode/opus5_5
created_at: 2026-10-11 19:33
updated_at: 2026-10-12 10:03
completed_at: 2026-10-12 10:03
---

## Context

t1946 added `focus_existing_agent_window(task_id, project_root)` in
`.aitask-scripts/lib/agent_launch_utils.py`, used by `ait board` (`p` and the
resume `g`) and `ait trails` (`p`). Window names carry only the task number, so
the helper searches a session only when the canonical discovery attributes it to
`project_root`. It checks the caller's verified session and the configured
`default_session`, because one gateway server hosts every project's sessions and
every project defaults to `aitasks`.

## Problem

`_sessions_owned_by(project_root)` calls the whole-server
`discover_aitasks_sessions()` synchronously on every `p` / `g` press. For each
unregistered session that issues a `list-panes`, plus a `show-environment` when
no pane resolves (`_collect_live_roots`). So the cost grows with unrelated
sessions: a project-A lookup lists project B's panes. Only two candidates need
attributing: the caller's session and the configured one. Confirmed in the
t1946 review (disposition: follow-up).

## Wanted

A targeted resolver that attributes **one named session** with the exact
canonical rule `_collect_live_roots` applies per session:
1. the registration stamp (`PROJECT_ROOT_OPTION`) via `_registered_root`;
2. else the pane vote over that session's panes (`_list_panes_argv`, which uses
   `tmux_session_scope_target`, never a bare `=<session>`);
3. else the legacy `AITASKS_PROJECT_<sess>` registry (`_read_registry_entry`).

It must reuse those helpers, not fork the rule. Ideally `_collect_live_roots`
itself calls the per-session resolver, so the two cannot drift. Then
`focus_existing_agent_window` attributes just its candidates (at most two
sessions) instead of the whole server.

## Constraints

- Positive evidence only: a session that cannot be attributed is not owned.
- A session that does not exist resolves to "not owned".
- Keep `focus_existing_agent_window`'s contract and tests unchanged.

## Verification

- `tests/test_pick_command_screen.py` stays green, including
  `LiveTwoServerTests`: cross-server caller, caller in another project's session,
  configured `aitasks` session owned by another project, and the positive control.
- Add a test proving a lookup issues no `list-panes` for an unrelated session.
- Discovery parity: `discover_aitasks_sessions` results are unchanged (existing
  discovery tests, e.g. the t1922 pane-vote suites).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-12T06:50:07Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-12T07:01:01Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-12T07:03:39Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:534b1069764ad838

> **✅ gate:risk_evaluated** run=2026-10-12T07:03:39Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1950/risk_evaluated_2026-10-12T07:03:39Z-risk_evaluated-a1.log`
