---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: enhancement
status: Done
labels: [shadow, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1411, 1410]
assigned_to: dario-e@beyond-eye.com
anchor: 1307
implemented_with: claudecode/opus5
created_at: 2026-07-29 10:16
updated_at: 2026-08-04 13:37
completed_at: 2026-08-04 13:37
boardidx: 81920
---

Close the residual wrong-pane hazard that **t1307** documented but, being
documentation-only by scope, could not eliminate.

## Context — what t1307 left open

t1307 hardened the `aitask-shadow` skill against model-side truncation of
`<followed_pane_id>` (observed: a Codex agent transcribed `%237` down to `%7`).
It replaced every single-digit pane-id example with a realistic multi-digit one,
moved the "pass it verbatim" contract *inside* the copied command block, and
codified a recovery: read the shadow's own `@aitask_shadow_target` binding, else
list panes and accept only an exact match, else ask the user.

That reduces the probability of a mis-copy but cannot eliminate it, and it
leaves one case entirely unguarded:

> **A mangled id that happens to name a live pane succeeds.** The capture
> returns another agent's screen, no error is raised, and the recovery never
> fires. The shadow then advises on the wrong agent's work.

t1307's `## Risk` section recorded this as an accepted goal-achievement risk.
This task tracks the deferred structural work.

## Two candidate mitigations (either or both)

### 1. Binding-based self-resolution (removes the transcription step entirely)

Teach `.aitask-scripts/aitask_shadow_capture.sh` to resolve the pane itself when
invoked with no `<pane_id>`: read `@aitask_shadow_target` from its own pane
(`$TMUX_PANE`) and capture that. The skill's Step 1 then becomes an argument-free
command, so the id never crosses the model's token stream and cannot be mangled.

The helper already reads that option — see `shadow_stamp_analyzed_at()` in
`aitask_shadow_capture.sh` — so the lookup is a reuse, not new machinery.

**Known constraint (verify before designing):** `minimonitor_app.py::_spawn_shadow`
stamps `@aitask_shadow_target` *after* `launch_in_tmux()` returns, so a very early
capture can race the stamp. The explicit-argument path must therefore remain
supported as the fallback, and the no-argument path must degrade cleanly (clear
error, not a silent wrong-pane capture) when the option is unset — e.g. a
manually-invoked shadow, or a shadow running outside tmux.

### 2. Wrong-pane collision warning (catches the silent case)

When the helper *is* given an explicit `<pane_id>` and its own pane carries an
`@aitask_shadow_target` that **differs**, emit a loud warning (or refuse without
an override flag). This is the only check that can catch a truncated id which
collides with a live-but-wrong pane, because that path produces a successful
capture and no error.

## Scope notes

- Both mitigations are **script changes** — deliberately excluded from t1307,
  whose acceptance criteria required documentation-only edits.
- `tests/test_shadow_capture.sh` already exercises the analyzed-at stamping with
  live tmux; extend it there. Cover: no-arg with a binding present, no-arg with
  the option unset, explicit id matching the binding, and explicit id conflicting
  with the binding.
- All tmux access must route through `lib/tmux_exec.sh` (`ait_tmux`) per
  `tests/test_no_raw_tmux.sh` — the helper already sources it.
- Read `aidocs/framework/shadow_agent.md` before changing capture semantics.

## Verification

```bash
bash tests/test_shadow_capture.sh
bash tests/test_no_raw_tmux.sh
shellcheck .aitask-scripts/aitask_shadow_capture.sh
```

Prove each new guard can fail (drive the helper from a pane whose binding
conflicts with the argument and confirm it warns/refuses), not merely that the
happy path still passes.

If the skill's Step 1 command changes, update
`.claude/skills/aitask-shadow/SKILL.md` (the source of truth) in the same
commit — the `.agents/` and `.opencode/` shadow wrappers are pure redirects and
need no port.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-04T09:39:28Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-04T10:28:51Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-04T10:37:16Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:e3f285682c1e4390

> **✅ gate:risk_evaluated** run=2026-08-04T10:37:16Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1319/risk_evaluated_2026-08-04T10:37:16Z-risk_evaluated-a1.log`
