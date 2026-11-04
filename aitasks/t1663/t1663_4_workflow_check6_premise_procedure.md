---
priority: medium
effort: high
depends: [t1663_3]
issue_type: feature
status: Ready
labels: [task-workflow, skills]
gates: [risk_evaluated]
anchor: 1538
created_at: 2026-09-01 15:19
updated_at: 2026-09-01 15:19
---

Wire the advisory premise check into task-workflow as Step 3 Check 6, backed by a new procedure file, with renders and goldens.

## Context

Fourth child of t1663. Design in `aidocs/framework/task_premise_staleness.md` ("Interaction"). The check fires on every entry path (pick, board agent launch, explore) because they all funnel through task-workflow Step 3; it runs for `Ready` tasks only — Checks 1-5 route Done/orphaned/manual-verification/in-flight tasks away first, which is also what keeps the t1555 MV seam and this one from double-prompting.

## Key files

- `.claude/skills/task-workflow/SKILL.md` — add **Check 6** after Check 5: run `./.aitask-scripts/aitask_premise_stale.sh check <task_file>`; `FRESH`/`SKIP` → silent fall-through to Step 4; `ASK_STALE` → the prompt below. Keep the check's caller to the one-line procedure-dispatch shape.
- `.claude/skills/task-workflow/premise-staleness.md` (new procedure file, per `aidocs/framework/skill_authoring_conventions.md` §"Extract new procedures") — carries: the NON-SKIPPABLE banner (enumerate what does not cover the prompt; no profile key bypasses it in v1); evidence INSIDE the widget question text (visibility rule — decision content never in same-turn prose); four options: (1) "Proceed — premise still valid" → after the Step 4 lock claim, re-run the producer, compare `FINGERPRINT:` to the prompted one — equal → advance `premise_baseline` to the prompted `CHECKED:` sha (transaction: re-check fingerprint → decide → write → advance last → commit); different → void the answer, show fresh evidence, re-prompt; (2) "Review & replan with this evidence" → continue with evidence threaded into planning context; an existing plan takes the §6.0 verify path with force_verify (mirror §6.0a's shape); baseline advances only at the Step 7 post-approval writes; (3) "Postpone task" → status Postponed, end; (4) "Pick a different task" → return to selection.
- Renders: `./.aitask-scripts/aitask_skill_verify.sh` + `./.aitask-scripts/aitask_skill_rerender.sh <profile>` per profile; regenerate goldens (`tests/golden/procs/task-workflow/…`, and SKILL goldens) IN THE SAME COMMIT (conventions doc §"Regenerate goldens").

## Reference files for patterns

- Step 3 Checks 1-5 in `.claude/skills/task-workflow/SKILL.md:30-102` — the helper→decision→prompt→route shape.
- `.claude/skills/task-workflow/remote-drift-check.md` — the advisory-evidence prompt shape and the collect-then-prompt-once rule.
- `.claude/skills/task-workflow/planning.md` §6.0a — the force_verify threading this mirrors for the replan option.
- `aidocs/framework/agent_runtime_guards_audit.md` — read before adding any `{% if agent %}` gate.

## Verification (this child owns the UI/workflow cases; pinned outcomes)

- End-to-end exercise (the record's required test — distinguishes "correctly quiet" from "never runs"): seed a task with baseline + scope in a fixture repo → change a scope file + commit → check reads `ASK_STALE` → dismiss ("Proceed") → baseline advanced to the CHECKED sha → immediate re-check reads `FRESH` (no re-fire).
- TOCTOU pin (revision axis): land a commit between check and write → advanced baseline equals the prompted `CHECKED:` sha, NOT the newer HEAD.
- TOCTOU pin (metadata axis): mutate `file_references:` (or the stored baseline) between prompt and post-lock write → fingerprint mismatch detected → no advance on the stale answer.
- Replan path: choosing "Review & replan" leaves the baseline unchanged; it advances only after plan approval.
- Rendered-variant invariance: `aitask_skill_verify.sh` passes; goldens updated in the same commit.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1981** id=2026-11-04T13:37:51Z.f0739597daea67d9faa6f041 from=t1981 from_verified=yes at=2026-11-04T13:37:51Z base=5026118e29a2635e34760ae91d842f73fd6078e6 base_branch=main dirty=yes host=omg16
>
> | From t1981 (task relations and obsolescence). Advisory: a stale assumption in your body, plus a neighbouring change.
> | 
> | 1. Your body plans the premise check as "Step 3 Check 6". In .claude/skills/task-workflow/SKILL.md, Step 3 Check 6 is already the `## Inbox` unread-notes check (t1657, around line 103 at commit 5026118e2). The premise check needs a different number.
> | 2. t1981_5 (a child of t1981, not created yet when this note was written; see aidocs/framework/task_relations.md D8) will add a "related work" display check to Step 3, also after Check 6. Whichever of the two lands second takes the next free number and re-reads Step 3 first. Both checks are advisory and never end the workflow.
