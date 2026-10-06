---
priority: medium
effort: medium
depends: [t1357_2]
issue_type: feature
status: Ready
labels: [task_workflow, skills]
gates: [risk_evaluated]
anchor: 1357
created_at: 2026-07-31 10:57
updated_at: 2026-07-31 10:57
---

## Context

Third child of t1357. The deterministic helpers (t1357_2) cover the coarse
step boundaries; this child adds the explicit stamp lines for spans that have
NO deterministic helper at their boundary, plus the end-of-run capture hook.
These are best-effort by nature (an agent can skip a prose instruction) —
that is accepted; the `src` field lets t1357_7 measure which ones fire.

Parent plan: `aiplans/p1357_task_workflow_step_stats_and_drift.md`
(child t1357_3 section). Depends on t1357_1 + t1357_2.

## Key files to modify

Source of truth is the Jinja source tree `.claude/skills/task-workflow/`
(NOT the rendered `-fast-`/`-default-`/`-remote-` trees). Gap spans mapped
during exploration (line refs are to the rendered fast variant — re-locate in
the .j2 sources):

1. `SKILL.md(.j2)` Step 7 implementation body (~WF:364): stamp
   `implement begin` right before "Follow the approved plan" and
   `implement end` at the "Do NOT commit" boundary before Step 8.
2. Step 8 review loop (~WF:483 "Need more changes"): stamp
   `review begin` at first entry, `review point --sub iteration` per
   iteration, `review end` when "Commit changes" is selected.
3. `planning.md(.j2)`: `planning begin --sub plan_mode` right after
   `EnterPlanMode`, `planning end --sub plan_mode` at `ExitPlanMode`;
   `planning begin/end --sub risk_evaluation` around the Risk Evaluation
   Procedure dispatch; `env_setup point` in the no-worktree Step 5 branch.
4. **Step 9b capture hook** (`SKILL.md` ~WF:782, next to satisfaction
   feedback): pass `--task-id <id>` to the `aitask_usage_update.sh` call
   (added in t1357_2) so feedback-stamp + `capture --outcome done
   --sweep-orphans` fire deterministically at workflow end.
5. Abort/deferral outcomes: in `task-abort.md` add
   `capture <id> --outcome aborted || true`; in the "Approve and stop here"
   checkpoint branch of `planning.md` add `capture <id> --outcome deferred || true`.
6. `model-self-detection.md`: after resolving the agent string, also resolve
   reasoning effort where self-detectable (Claude Code: from the session
   context if available; otherwise `unknown`; Codex/OpenCode: `unknown`) and
   call `aitask_stats_step.sh set-dim <id> --agent <string> --effort <e> || true`.
   Same call added in `agent-attribution.md` after `implemented_with` write.

## Rendering / goldens (MANDATORY)

- Read `aidocs/framework/skill_authoring_conventions.md` BEFORE editing.
- All stamp lines are agent-invariant plain bash (no `{% if agent %}` gates
  needed — see `aidocs/framework/agent_runtime_guards_audit.md` if tempted).
- Rerender per profile (one call per profile) via
  `./.aitask-scripts/aitask_skill_render.sh` for task-workflow (+ any skill
  whose stub surface changed), run
  `./.aitask-scripts/aitask_skill_verify.sh`, and regenerate affected goldens
  under `tests/golden/procs/task-workflow/` in the SAME commit.
- Per CLAUDE.md: changes are Claude-Code-first; at the end, suggest separate
  aitasks for porting to the Codex (`.agents/skills/`) and OpenCode
  (`.opencode/skills/`) trees (auto-rendered surfaces need no port if the
  agent surface is unchanged — check `project_closure_changes_autorender` note).

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh` passes; goldens regenerated.
- Grep the rendered fast/default/remote task-workflow trees: every stamp
  call appears in each (agent-invariance).
- Live smoke (end-to-end from the parent plan's Verification section): run a
  `/aitask-pick` cycle on a scratch task; verify spool fills, Step 9b capture
  commits exactly one per-run events file, and an aborted run captures with
  `outcome=aborted`.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1907** id=2026-10-06T21:00:40Z.bb606ef2ff1180d14b8f1224 from=t1907 from_verified=yes at=2026-10-06T21:00:40Z base=db06dfdf8cccb50099363e4a6f2ff2d482aa485c base_branch=main dirty=yes host=omg16
>
> | Advisory (from t1907, tree-relative to the recorded base SHA): your step 4 "Step 9b capture hook" places the `aitask_usage_update.sh` call in task-workflow `SKILL.md` (~WF:782). As of t1907 that call lives in `.claude/skills/task-workflow/satisfaction-feedback.md`, Step 0 ("Record usage (unconditional)"); SKILL.md Step 9b only invokes that procedure. t1907 did not move the call.
> | 
> | What t1907 changed around it: a profile with `enableFeedbackQuestions: false` now renders that procedure as Step 0 only (no rating prompt, no `aitask_verified_update.sh`, no NON-SKIPPABLE banner). The shipped `fast` and `remote` profiles both set `false`. Step 0, with the `aitask_usage_update.sh` call, is still rendered for every profile, so a `--task-id` edit there reaches all of them. Changing that file means regenerating `tests/golden/procs/task-workflow/satisfaction-feedback-{default,fast,remote}.md` and the committed remote prerenders (`aitask_skill_rerender.sh remote`).
