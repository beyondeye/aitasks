---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [documentation, doc_quality]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2258
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-15 13:05
updated_at: 2026-11-15 17:20
completed_at: 2026-11-15 17:20
---

## Origin

Spawned from t2284 during Step 8b review.

## Upstream defect

- `.claude/skills/aitask-wrap/SKILL.md.j2:349` names a non-existent `ait archive <N>` dispatcher verb. The flags belong to `./.aitask-scripts/aitask_archive.sh`. The current text is "the user can archive manually later with `ait archive <N>`".
- `.claude/skills/aitask-web-merge/materialize-gates.md:33` names the same non-existent verb ("repair manually via aitask_gate.sh materialize-active + ait archive").

## Diagnostic context

t2284 corrected the same claim on `website/content/docs/development/task-format.md`
(the `archived_reason` row now names `./.aitask-scripts/aitask_archive.sh`). The
`ait` dispatcher has no `archive` verb. These two skill sources were left out of
t2284's scope because they are skill sources with goldens and ported copies.

## Suggested fix

Replace `ait archive <N>` with `./.aitask-scripts/aitask_archive.sh <N>` in both
sources. Then regenerate the affected goldens, run
`./.aitask-scripts/aitask_skill_verify.sh`, and port the change to the Codex and
OpenCode trees (or create tasks to port it).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-15T15:00:47Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-15T15:12:13Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-15T15:20:44Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:1e7bea3f5557e415

> **✅ gate:risk_evaluated** run=2026-11-15T15:20:44Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2300/risk_evaluated_2026-11-15T15:20:44Z-risk_evaluated-a1.log`
