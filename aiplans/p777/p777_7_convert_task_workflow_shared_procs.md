---
Task: t777_7_convert_task_workflow_shared_procs.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_7 — Convert shared `task-workflow/` procedures

## Scope

HIGH-IMPACT child. The shared procedures govern every skill's behavior during ownership, planning, review, archival, and feedback. Convert ALL procedures with profile branches to `.j2`; leave plain `.md` procedures as-is.

## Step Order

1. **Audit** — `grep -l "profile" .claude/skills/task-workflow/*.md` to find profile-touching procedures. Expected list (verify): `SKILL.md`, `planning.md`, `satisfaction-feedback.md`, `manual-verification.md`, `manual-verification-followup.md`, `remote-drift-check.md`.
2. **Decide cross-reference strategy** — when the rendered aitask-pick-fast SKILL.md refers to a shared proc, what path does it use? Two options:
   - (a) Template variable `{% set tw = "task-workflow-" + profile.name %}` and emit `{{ tw }}/planning.md` everywhere.
   - (b) Post-process renderer output to rewrite `task-workflow/` → `task-workflow-<profile>/` based on profile context.
   - **Recommended: (a)** — explicit and reviewable. Update aitask-pick template (t777_6) accordingly. Document the decision here.
3. **Convert each profile-touching procedure** to `.j2` (preserve all current content; replace "Profile check:" blocks with `{% if %}…{% else %}…{% endif %}`).
4. **Update `aitask_skill_render.sh`** (t777_2) — recursive include rendering MUST handle task-workflow procs. Plain `.md` procedures must be COPIED unchanged to `task-workflow-<profile>/` so cross-references resolve.
5. **Frontmatter `name`** — task-workflow procs use `name: task-workflow` currently; rendered versions don't need a different name since they're referenced by file path, not slash command. Leave unchanged OR set `name: task-workflow-{{ profile.name }}` for consistency.

## Critical Files

- All `.claude/skills/task-workflow/*.md` files with profile branches → `.j2`
- `.aitask-scripts/aitask_skill_render.sh` (modify — handle task-workflow recursion + plain `.md` copy)
- `.claude/skills/aitask-pick/SKILL.md.j2` (modify if option (a) chosen — cross-refs to `task-workflow-<profile>/`)

## Pitfalls

- **Cross-reference rot** — if the rendered chain breaks (skill references `task-workflow-fast/planning.md` but renderer wrote it to `task-workflow/planning.md`), the agent reads stale content. Test end-to-end.
- **Plain `.md` procedures** — must be present in `task-workflow-<profile>/` (copied verbatim) so cross-references resolve even for non-templated procs.
- **`execution-profile-selection.md`** — special case. It's the LOADER. May not need templating (the loader itself reads profile YAML at runtime), but verify.

## Verification

See task description. End-to-end stub-dispatch test must succeed including all task-workflow references.
