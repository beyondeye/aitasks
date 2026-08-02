---
priority: low
effort: medium
depends: [1312]
issue_type: refactor
status: Ready
labels: [aitask_explore, aitask-create, bash_scripts, task_workflow]
gates: [risk_evaluated]
anchor: 1312
created_at: 2026-07-29 09:16
updated_at: 2026-07-29 09:16
boardidx: 540
---

Review whether the duplicated task-metadata-gathering logic across the various
create/explore flavors is still justified, and consolidate what is not.

## Context

Raised while exploring t1312 (label auto-add + confirmation in
`/aitask-explore`). That task fixes one symptom of a broader pattern: the same
"gather task metadata, then create a task" logic is re-implemented in several
places, and they have already drifted apart from each other.

## Known duplication (starting inventory — verify and extend during planning)

**Shell layer** — `.aitask-scripts/aitask_create.sh`:
- The interactive fzf path and the `--batch` path each build frontmatter
  independently: `create_task_file()` (`:472`), `create_child_task_file()`
  (`:588`), `create_draft_file()` (`:1800`) all take a long positional argument
  list and each re-emit the YAML block (`:515`, `:640`, `:1818`).
- Vocabulary side effects are attached to only one of the two paths:
  `add_label_to_file` / `set_last_used_labels` fire interactively (`:1219`,
  `:2309`) but not in batch (t1312 §B fixes the label half).
- `sanitize_label` is duplicated into `aitask_update.sh:1368` (t1312 §A moves
  it to `lib/task_utils.sh`).

**Skill layer** — all route to the same
`.claude/skills/task-workflow/task-creation-batch.md` procedure, yet each
re-derives metadata with its own prose rules:
- `.claude/skills/aitask-explore/SKILL.md.j2` — Step 1 per-intent defaults table
- `.claude/skills/aitask-create/SKILL.md` — non-templated, interactive prompts
- `.claude/skills/aitask-explorechat/SKILL.md:108-120` — relay-driven field build
- `.claude/skills/aitask-wrap/SKILL.md.j2:79,131,162` — suggests from diff
- `.claude/skills/aitask-pr-import/SKILL.md.j2:175` — infers from PR files
- `.claude/skills/aitask-review/SKILL.md.j2:189` — hardcodes `labels: "review"`

The observable drift: labels are "existing only" in explorechat, "freely new" in
wrap, hardcoded in review, and unconstrained in explore.

## Goal

Produce a decision, not a blanket refactor. For each duplicated site, classify:
- **Genuine variation** (different UX surface / different available inputs) —
  keep, but document why in the relevant convention doc.
- **Accidental divergence** — consolidate into a shared seam (a
  `lib/task_utils.sh` helper for the shell side, a shared procedure or Jinja
  macro under `.claude/skills/task-workflow/` for the skill side).

## Acceptance Criteria

- [ ] Inventory table of every create/explore metadata-gathering site, with the
      classification above and a one-line rationale each. No site left
      unclassified.
- [ ] Sites classified as accidental divergence are consolidated, **or** an
      explicit disposition is recorded for each one that is deliberately
      deferred (with the reason and, where applicable, a follow-up task).
- [ ] Any consolidation preserves current behaviour for each caller — no
      silent UX change to a skill that was not part of the stated scope.
- [ ] Cross-skill prose rules about labels agree with whatever rule t1312
      establishes (see t1312's "Consistency note").
- [ ] Conventions captured in `aidocs/framework/skill_authoring_conventions.md`
      and/or `aidocs/framework/shell_conventions.md` as appropriate.
- [ ] `./.aitask-scripts/aitask_skill_verify.sh` passes and affected goldens are
      regenerated in the same commit.

## Dependencies

Do this **after** t1312 — that task already moves `sanitize_label` /
`add_label_to_file` into `lib/task_utils.sh` and fixes the batch/interactive
label asymmetry, which removes part of the inventory above.
