---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: [t635_33]
issue_type: enhancement
status: Implementing
labels: [gates, task_workflow, execution_profiles]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 635
implemented_with: claudecode/fable5
created_at: 2026-07-19 08:27
updated_at: 2026-07-23 17:26
---

## Context

t635_33 landed the `active_gates` model: the execution profile renders a gate-machinery
ceiling (`rendered_gates`, defaulting to `default_gates`), the task's `gates:` selects
within it at runtime, and a four-field derived tuple (`active_gates`,
`active_gates_filtered`, `active_gates_profile`, `active_gates_digest`) is materialized
at claim time (task-workflow Step 4 `aitask_gate.sh materialize-active`) and consumed by
every enforcer. See `aiplans/p635/p635_33_gate_activation_render_time.md` (archived under
`aiplans/archived/p635/` after t635_33 completes).

The **remote/web lanes were carved out** of t635_33 to bound blast radius: `aitask-pickrem`
and `aitask-pickweb` have their own skill trees and goldens, and their ownership steps do
NOT yet call `materialize-active` — so a task picked through those lanes never gets an
`active_gates` tuple and all enforcers fall back to raw `gates:` (today's behavior).

**Interim risk (documented, narrow):** only a task with a LITERAL `gates:` declaration
picked under the `remote` profile is affected, and `remote` declares no `default_gates`,
so the pre-t635_33 behavior is simply retained — the refactor did not worsen anything.
This task closes the gap so the lanes are consistent.

## Scope

1. **`aitask-pickrem` ownership step:** add the always-rendered `materialize-active` call
   (mirroring task-workflow Step 4): after ownership is claimed, run
   `./.aitask-scripts/aitask_gate.sh materialize-active <task_id> --profile aitasks/metadata/profiles/<active_profile_filename>`
   when a profile is in scope; parse the one-line `MATERIALIZED:<csv>` /
   `MATERIALIZED:(empty)` / `NOOP:unchanged` output. Skip the call when no profile
   resolves (raw-`gates:` fallback governs; never guess).
2. **`aitask-pickweb` ownership step:** same call. Note pickweb avoids cross-branch
   operations — materialize writes the task file via `aitask_update.sh`; verify how the
   pickweb local-data mode (`.aitask-data-updated/`) interacts with the tuple write and
   route accordingly (may need the completion-marker variant like agent attribution uses).
3. **`remote.yaml`:** set explicit `rendered_gates: []` (the render-nothing override —
   key-presence semantics, landed in t635_33) so the remote lane's ceiling is declared,
   not implicit.
4. **Skill sources + rendered trees:** edit the pickrem/pickweb authoring sources
   (`.claude/skills/aitask-pickrem/`, `.claude/skills/aitask-pickweb/` and their `.md.j2`
   files if templated), rerender all profile variants x agent trees, regenerate their
   goldens, run `./.aitask-scripts/aitask_skill_verify.sh`.

## Key files

- `.claude/skills/aitask-pickrem/` and `.claude/skills/aitask-pickweb/` (+ `.agents/skills/`,
  `.opencode/` mirrors per the rerender driver)
- `aitasks/metadata/profiles/remote.yaml` (+ `seed/` copy if profiles are seeded)
- `tests/golden/skills/` goldens for the two skills
- Reference: task-workflow `SKILL.md` Step 4 materialize-active call shape (t635_33)

## Verification

- Render-content assertion: rendered pickrem/pickweb variants contain the
  `materialize-active` call in their ownership step (all profiles).
- `remote.yaml` round-trips through the profile editor with `rendered_gates: []` intact.
- A task with literal `gates: [risk_evaluated]` picked under `remote` materializes
  `active_gates: []` and archives without a manual gate append (the t635_33
  negative-control, exercised through the remote lane).
- `aitask_skill_verify.sh` passes; goldens committed in the same change.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-23T14:26:48Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-23T15:36:50Z status=pass attempt=1 type=human
