---
Task: t1357_3_skill_text_stamps_capture_hook.md
Parent Task: aitasks/t1357_task_workflow_step_stats_and_drift.md
Sibling Tasks: aitasks/t1357/t1357_1_*.md … t1357_7_*.md
Archived Sibling Plans: aiplans/archived/p1357/p1357_*_*.md
Worktree: aiwork/t1357_3_skill_text_stamps_capture_hook
Branch: aitask/t1357_3_skill_text_stamps_capture_hook
Base branch: main
Output branch: main
---

# Plan: t1357_3 — Skill-text stamps for gap spans + end-of-run capture hook

Task file enumerates the six edit groups; they are all in the Jinja source
tree `.claude/skills/task-workflow/` (never the rendered `-<profile>-` trees).

## Implementation steps

1. **Read first:** `aidocs/framework/skill_authoring_conventions.md`
   (rendering, goldens, "Regenerate goldens after any .md.j2 or closure
   edit"), `aidocs/framework/agent_runtime_guards_audit.md` (confirm no
   `{% if agent %}` gate is needed — stamp lines are agent-invariant bash).
2. Apply the stamp lines (guarded `|| true`, each a single fenced bash line
   with a one-sentence instruction) at:
   - `SKILL.md` Step 7 body: `implement begin` before "Follow the approved
     plan"; `implement end` at the do-not-commit boundary.
   - `SKILL.md` Step 8: `review begin` on entry; `review point --sub
     iteration` on each "Need more changes" loop; `review end` on "Commit
     changes".
   - `planning.md`: `planning begin/end --sub plan_mode` at
     EnterPlanMode/ExitPlanMode; `planning begin/end --sub risk_evaluation`
     around the Risk Evaluation dispatch; `env_setup point` in the
     no-worktree Step 5 branch (this branch is profile-conditional Jinja —
     place the stamp in both worktree and no-worktree renders).
   - Step 9b: change the usage-update call to pass `--task-id <task_id>`
     (t1357_2's flag) — this is the deterministic capture trigger.
   - `task-abort.md`: `capture <id> --outcome aborted || true`.
   - `planning.md` "Approve and stop here": `capture <id> --outcome deferred || true`.
   - `model-self-detection.md` + `agent-attribution.md`: `set-dim <id>
     --agent <string> --effort <effort-or-unknown> || true` after resolution.
     Effort detection: Claude Code — use the session's known reasoning-effort
     if the harness exposes it in-context, else `unknown`; Codex/OpenCode —
     `unknown` (documented limitation; enrichment back-fills for Claude Code
     in t1357_5).
3. **Rerender + goldens (same commit):** render task-workflow for each
   profile (one `aitask_skill_render.sh` call per profile — default, fast,
   remote), run `./.aitask-scripts/aitask_skill_verify.sh`, regenerate the
   affected goldens under `tests/golden/procs/task-workflow/`.
4. Grep-verify all three rendered trees contain every stamp call
   (agent-invariance check across profiles).
5. Per CLAUDE.md closure rule: cross-agent trees auto-render; if
   `aitask_skill_verify.sh` flags Codex/OpenCode surface drift, suggest
   separate port tasks in the final notes (do not port in this task).

## Verification

- `aitask_skill_verify.sh` green; goldens updated in the same commit.
- Live smoke (parent plan § Verification): one `/aitask-pick` cycle on a
  scratch task → spool fills; Step 9b capture commits exactly one
  `aitasks/metadata/stats/events/<month>/t<id>_r*.jsonl`; an aborted run
  captures `outcome=aborted`; a killed session leaves a spool that the next
  run sweeps as `outcome=orphaned`.

## Step 9

Standard Step 9.
