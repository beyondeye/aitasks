---
priority: low
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [task_workflow, verifiedstats]
gates: [risk_evaluated]
created_at: 2026-07-22 16:41
updated_at: 2026-07-22 16:41
---

## Context

Salvaged from the **pickn / task-workflown staging experiment**, retired in
t635_36. That experiment (t928) tested four fail-closed hardening hypotheses in a
parallel copy of `task-workflow`. Three shipped to production independently and
are now enforced by the `risk_evaluated` gate verifier
(`.aitask-scripts/aitask_gate_risk.sh`). **This is the fourth — the only one that
never shipped.** The fork's source files are deleted by t635_36, so the retired
text is quoted verbatim below; there is nothing left to read it from.

Today production `task-workflow` Step 9b just says "Execute the Satisfaction
Feedback Procedure" and moves on. Nothing detects the case where the agent
silently never asked. `grep -n 'satisfaction_feedback_status\|Final-response gate'
.claude/skills/task-workflow/` returns zero hits at the time of writing.

The gap this closes: the Step-9b `AskUserQuestion` is the **only** data path that
feeds verified-model scores from interactive workflows. When an agent skips it —
under auto mode, a "be brief" instruction, or simple omission — the run's rating
is lost with no trace and no way to tell a legitimate skip from a silent one.

## Scope

Port the two retired pieces into production `task-workflow`:

**1. `.claude/skills/task-workflow/satisfaction-feedback.md` — a return contract
where every exit path sets a status.**

Add after the `**Input:**` block (verbatim from the retired fork):

```markdown
**Return contract for task-workflow Step 9b gate:**
- `satisfaction_feedback_status` — `rated` if a score was processed; `skipped` if the procedure reached a documented skip path.
- `satisfaction_skip_reason` — required when status is `skipped`. Valid values are `profile_disabled`, `preprovided_rating`, `agent_detection_failed`, `question_skipped`, or `verified_update_failed`.
```

and after the NON-SKIPPABLE "only valid skips are" list:

```markdown
For task-workflow, every skip path MUST set `satisfaction_feedback_status=skipped`
and a valid `satisfaction_skip_reason`. Silent skip is not allowed.
```

Then set the status at each of the five exit paths. The retired wording for each
(the surrounding steps are unchanged in production, so these are edits in place):

- Step 0 substep 1, detection failure: `If detection fails or no supported agent/model can be identified, skip Step 0 silently and keep 'satisfaction_skip_reason' unset; Step 1 still gets a chance to ask for feedback.` (Step 0 is best-effort usage tracking, NOT a terminal skip — it must not set a status.)
- Step 1 substep 1, profile-disabled branch (both the Jinja `{% if profile.enableFeedbackQuestions %}` false arm and the key-absent arm): `set 'satisfaction_feedback_status=skipped' and 'satisfaction_skip_reason=profile_disabled', then skip the remainder of Step 1.`
- Step 1 substep 2, self-detection fallback failure: `set 'satisfaction_feedback_status=skipped' and 'satisfaction_skip_reason=agent_detection_failed', then skip the remainder of Step 1.`
- Step 1 substep 3, preprovided rating: `process that rating directly with the update command in substep 4, set 'satisfaction_feedback_status=rated' on success ... If the preprovided rating is unusable, set 'satisfaction_feedback_status=skipped' and 'satisfaction_skip_reason=preprovided_rating', then continue without updating.`
- Step 1 substep 4, `UPDATED:` parse: `Set 'satisfaction_feedback_status=rated', clear 'satisfaction_skip_reason'` — and on failure after a rating was selected: `set 'satisfaction_feedback_status=skipped' and 'satisfaction_skip_reason=verified_update_failed', warn the user, and continue. This is a valid recorded skip because the rating could not be persisted.`
- Step 1 substep 5, dismissed question: `set 'satisfaction_feedback_status=skipped' and 'satisfaction_skip_reason=question_skipped', then continue without updating.`

**2. `.claude/skills/task-workflow/SKILL.md` Step 9b — the final-response gate.**

Append after the "Execute the Satisfaction Feedback Procedure" line (verbatim
from the retired fork):

```markdown
**Final-response gate (NON-SKIPPABLE):** After archive/push, do **not** send the final user response until one of these is true:

- `satisfaction_feedback_status=rated` because the Satisfaction Feedback Procedure asked for and processed a rating, or processed an explicit user-provided rating before the prompt fired.
- `satisfaction_feedback_status=skipped` and `satisfaction_skip_reason` is one of the valid skip reasons documented in `satisfaction-feedback.md`.

Silent omission is not a valid skip reason. If neither condition is satisfied, run or repair the Satisfaction Feedback Procedure before responding.
```

## Key files

- `.claude/skills/task-workflow/satisfaction-feedback.md` — the return contract
  and the five exit-path status writes.
- `.claude/skills/task-workflow/SKILL.md` — Step 9b final-response gate.
- `tests/golden/procs/task-workflow/` and `tests/golden/skills/` — regenerate in
  the same commit (see "Regenerate goldens after any `.md.j2` or closure edit" in
  `aidocs/framework/skill_authoring_conventions.md`).

## Design notes

- `satisfaction-feedback.md` contains Jinja (`{% if profile.enableFeedbackQuestions %}`)
  and is rendered per profile. The profile-disabled branch appears **twice** —
  once in the false arm, once in the key-absent arm. Both need the status write,
  or `remote` (`enableFeedbackQuestions: false`) renders a skip with no reason.
- Do **not** gate the final-response gate behind a profile key. Under `remote` the
  procedure sets `profile_disabled` and the gate is satisfied by that recorded
  skip — which is the point: a headless run proves *why* it did not ask.
- The gate is prose in a skill, not executable — it constrains the agent's final
  turn. Verification is therefore render-content assertions plus a live run, not
  a unit test.

## Verification

1. Render-content assertions (extend `tests/test_skill_render_task_workflow.sh`):
   for `default` / `fast` / `remote`, the rendered `SKILL.md` contains
   `Final-response gate` and `satisfaction_feedback_status=rated`, and the
   rendered `satisfaction-feedback.md` contains all five skip-reason values.
   Profile-invariant — assert for all three, not just one.
2. `remote` specifically: the rendered `satisfaction-feedback.md` profile-disabled
   branch sets `satisfaction_skip_reason=profile_disabled` (the arm that is easy
   to miss).
3. `./.aitask-scripts/aitask_skill_verify.sh` passes; goldens regenerated and
   committed in the same change.
4. Live: complete a task under `fast` and confirm the Step-9b rating prompt fires
   and the final response is not emitted before it; then under a profile with
   `enableFeedbackQuestions: false` confirm the run reports the
   `profile_disabled` skip instead of silently omitting.

## Provenance

Retired experiment: `aidocs/framework/pickn_workflown_experiment.md` (deleted by
t635_36), hypothesis 4 of 4. Its own instruction was that a follow-up task should
review the staged behavior and perform a separate production merge — this is that
task. See the archived plan `aiplans/archived/p635/p635_36_*.md` for the full
35-file salvage audit that identified this as the sole unshipped item.
