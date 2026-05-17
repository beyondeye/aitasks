---
priority: high
effort: high
depends: [t777_6]
issue_type: refactor
status: Ready
labels: [aitask_pick]
created_at: 2026-05-17 11:59
updated_at: 2026-05-17 11:59
---

## Context

Depends on t777_6 (pilot). Converts the shared `task-workflow/*.md` procedures (used by ALL skills) to templates. This is HIGH-IMPACT because every skill's behavior is governed by these procedures during task ownership, planning, review, archival, and feedback collection.

Recommended approach (per parent plan): the .j2 templates emit profile-suffixed paths in their cross-references. E.g. the rendered aitask-pick-fast SKILL.md says "see `task-workflow-fast/planning.md`" instead of "see `task-workflow/planning.md`". This avoids stub-per-proc complexity — the rendered chain points to consistent profile-suffixed files end-to-end.

## Key Files to Modify

Convert these `.claude/skills/task-workflow/*.md` to `.j2` templates (verify list by grepping for `profile` at impl time):
- `SKILL.md` — Steps 3/3b/4/5/6 profile branches (largest)
- `planning.md` — Step 6.0/6.1/Checkpoint profile branches (second largest)
- `satisfaction-feedback.md` — `enableFeedbackQuestions`
- `manual-verification.md` — any profile branches
- `manual-verification-followup.md` — `manual_verification_followup_mode`
- `remote-drift-check.md` — `base_branch`
- `execution-profile-selection.md` — used by Step 0a (the loader). May or may not need templating; assess at impl time. If it stays runtime, it must be smart enough to detect "we're inside a rendered context" and short-circuit.
- others as discovered

Plain `.md` procedures (no profile branches like `agent-attribution.md`, `lock-release.md`, `task-abort.md`, etc.) stay as plain `.md` — copied unchanged into each agent's `task-workflow-<profile>/` directory at render time.

Render machinery:
- The renderer (t777_2) needs to know that template includes from the skill SKILL.md to task-workflow are profile-suffixed at render time. This may require a template helper like `{% set tw = "task-workflow-" + profile.name %}` and using `{{ tw }}/planning.md` for references.
- Alternative: at render time, post-process the rendered output to rewrite `task-workflow/` references to `task-workflow-<profile>/` based on the profile name. Surface trade-offs in the plan file.

## Reference Files for Patterns

- Current `.claude/skills/task-workflow/SKILL.md` and `planning.md`
- `task-workflow/stub-skill-pattern.md` from t777_3

## Implementation Plan

1. Audit which procedures actually branch on profile keys: `grep -l "profile" .claude/skills/task-workflow/*.md`
2. For each procedure with profile branches: convert to `.j2` (preserve all current content, replace "Profile check:" blocks with `{% if %}/{% else %}/{% endif %}`)
3. Decide on cross-reference strategy (suffix template variable vs post-processing rewrite). Document in `aiplans/p777/p777_7_convert_task_workflow_shared_procs.md`.
4. Update `aitask_skill_render.sh` (t777_2) if needed to:
   - Recursively render referenced task-workflow procedures into `<agent>/skills/task-workflow-<profile>/`
   - Copy plain `.md` procedures unchanged into the same per-profile directory
5. Per-agent: each agent gets its own rendered `task-workflow-<profile>/` directory tree (rendered from the same Claude-path source).
6. Update aitask-pick template (from t777_6) to reference `task-workflow-{{ profile.name }}/` paths where relevant.

## Verification Steps

1. `ait skill render pick --profile fast --agent claude` ALSO produces `.claude/skills/task-workflow-fast/` populated with rendered + copied procs.
2. The rendered `aitask-pick-fast/SKILL.md` references `task-workflow-fast/` (not `task-workflow/`).
3. Plain `.md` procs (like `agent-attribution.md`) are present unchanged in `task-workflow-fast/`.
4. `ait skill verify` passes for all task-workflow `.j2` files against default profile for all 4 agents.
5. Stub-dispatch end-to-end: `/aitask-pick 777` triggers full flow including task-workflow references — agent successfully reads `task-workflow-<profile>/SKILL.md` Step 3 etc.
