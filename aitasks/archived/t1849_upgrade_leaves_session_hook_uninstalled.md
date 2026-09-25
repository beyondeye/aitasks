---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [frozen, install, setup]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-09-21 22:42
updated_at: 2026-09-25 12:31
completed_at: 2026-09-25 12:31
---

## Problem

`ait upgrade` (→ `install.sh --force`) stages the Claude Code SessionStart hook seed (`aitasks/metadata/claude_settings.hooks.json`) but never merges it into `.claude/settings.json`. That merge happens only in `ait setup` (`aitask_setup.sh::setup_claude_hooks`). A project that was set up before the hook shipped and has only been upgraded since has no hook. Every agent in it is invisible to the session store until it is frozen, and it then freezes into an unrestorable record.

Observed: `thinking_app` at v0.35.1 has no `.claude/settings.json` at all. All 4 of its frozen agents can neither be restored nor re-picked.

## Wanted

Make a missing hook visible and easy to fix, without silently installing executable hooks (the consent prompt is deliberate):

- After `ait upgrade`, if the hook seed exists but `.claude/settings.json` lacks the aitasks SessionStart entry, print a specific hint: "run `ait setup` to install the session hook (needed to restore frozen agents)". Verb per CLAUDE.md: repair/populate → `ait setup`.
- Consider the same check in `ait ide` startup and/or when freezing (the freeze confirmation could note "this agent can only be viewed, not restored").
- Consider a cheap `ait setup --hooks-only` style path so users don't have to re-run the whole setup.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-25T08:23:40Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-25T09:29:15Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-25T09:31:51Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:ae53f87f3d16510b

> **✅ gate:risk_evaluated** run=2026-09-25T09:31:51Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1849/risk_evaluated_2026-09-25T09:31:51Z-risk_evaluated-a1.log`
