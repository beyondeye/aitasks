---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Done
labels: [skills]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-15 16:57
updated_at: 2026-03-15 18:10
completed_at: 2026-03-15 18:10
---

## Goal

Split `.claude/skills/task-workflow/procedures.md` into individual procedure files (one file per procedure) and update all references across all skills to point to the specific procedure file instead of the monolithic `procedures.md`.

## Background

The `procedures.md` file contains 10 procedures in a single ~416-line file. The task-workflow directory already has a precedent for split files (`related-task-discovery.md`, `task-fold-content.md`, `task-fold-marking.md`), so this refactor aligns with the existing convention.

## Procedures to Split

Each procedure becomes its own file in `.claude/skills/task-workflow/`:

1. `task-abort.md` ← Task Abort Procedure
2. `issue-update.md` ← Issue Update Procedure
3. `pr-close-decline.md` ← PR Close/Decline Procedure
4. `contributor-attribution.md` ← Contributor Attribution Procedure (including Multi-Contributor Attribution subsection)
5. `code-agent-commit-attribution.md` ← Code-Agent Commit Attribution Procedure
6. `model-self-detection.md` ← Model Self-Detection Sub-Procedure
7. `agent-attribution.md` ← Agent Attribution Procedure
8. `satisfaction-feedback.md` ← Satisfaction Feedback Procedure
9. `test-followup-task.md` ← Test Follow-up Task Procedure
10. `lock-release.md` ← Lock Release Procedure

## References to Update (26 total across 13 files)

### task-workflow/SKILL.md (11 references)
- Task Abort Procedure → `task-abort.md`
- Agent Attribution → `agent-attribution.md`
- Contributor Attribution → `contributor-attribution.md`
- Code-Agent Commit Attribution → `code-agent-commit-attribution.md`
- Test Follow-up Task → `test-followup-task.md`
- Issue Update (×2) → `issue-update.md`
- PR Close/Decline (×2) → `pr-close-decline.md`
- Satisfaction Feedback → `satisfaction-feedback.md`
- Procedure index section at bottom

### task-workflow/planning.md (2 references)
- Satisfaction Feedback → `satisfaction-feedback.md`
- Task Abort → `task-abort.md`

### aitask-explore/SKILL.md (1 reference)
- Satisfaction Feedback → `satisfaction-feedback.md`

### aitask-wrap/SKILL.md (4 references)
- Agent Attribution → `agent-attribution.md`
- Code-Agent Commit Attribution → `code-agent-commit-attribution.md`
- Issue Update → `issue-update.md`
- Satisfaction Feedback → `satisfaction-feedback.md`

### aitask-pickrem/SKILL.md (2 references)
- Agent Attribution → `agent-attribution.md`
- Code-Agent Commit Attribution → `code-agent-commit-attribution.md`

### aitask-pickweb/SKILL.md (2 references)
- Agent Attribution → `agent-attribution.md`
- Code-Agent Commit Attribution → `code-agent-commit-attribution.md`

### Standalone skills (1 reference each — all Satisfaction Feedback):
- aitask-explain/SKILL.md → `satisfaction-feedback.md`
- aitask-changelog/SKILL.md → `satisfaction-feedback.md`
- aitask-refresh-code-models/SKILL.md → `satisfaction-feedback.md`
- aitask-reviewguide-classify/SKILL.md → `satisfaction-feedback.md`
- aitask-reviewguide-merge/SKILL.md → `satisfaction-feedback.md`
- aitask-reviewguide-import/SKILL.md → `satisfaction-feedback.md`
- aitask-web-merge/SKILL.md → `satisfaction-feedback.md`

## Implementation Notes

- Keep each file self-contained with a clear title and brief intro
- Cross-references between procedures (e.g., Task Abort references Lock Release, Satisfaction Feedback references Model Self-Detection) should use relative file links
- Update the procedure index in `task-workflow/SKILL.md` to list the individual files instead of the `procedures.md` anchors
- Delete `procedures.md` after all content is moved and references updated
- Only `.claude/skills/` is affected (no gemini/codex/opencode references)
