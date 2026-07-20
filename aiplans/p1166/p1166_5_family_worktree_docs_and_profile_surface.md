---
Task: t1166_5_family_worktree_docs_and_profile_surface.md
Parent Task: aitasks/t1166_shared_worktree_for_child_task_families.md
Sibling Tasks: aitasks/t1166/t1166_1_family_worktree_helper_script.md, aitasks/t1166/t1166_2_family_worktree_frontmatter_field.md, aitasks/t1166/t1166_3_task_workflow_family_mode_main_path.md, aitasks/t1166/t1166_4_family_failure_recovery_surfaces.md
Base branch: main
---

# Plan: t1166_5 — docs + profile surface

## Context

Documents the landed family-worktree behavior (t1166_3/4) across profile schema help and the website, and verifies — but does not port — the cross-agent render story. Read `aidocs/framework/documentation_conventions.md` before writing prose (current-state-only, genericized agent references). Document what the LIVE source does at implementation time, not this plan's snapshot.

## Steps

1. **`profiles.md`** (authoring copy in `.claude/skills/task-workflow/`): `create_worktree` schema-table row + worktree example — add: a parent's `family_worktree: true` overrides `create_worktree: false` for its children (family mode); family worktrees always base on `main` (profile `base_branch` does not apply — v1 limitation). Regenerate goldens/rerender if profiles.md is in the golden set (it is closure-shared; verify with `tests/test_skill_render_task_workflow.sh`).
2. **`profile_editor.py`** `create_worktree` help text (~129-137): append the same override one-liner (short + detailed descriptions).
3. **Website**:
   - `workflows/parallel-development.md`: family-worktree section — opt-in at split time, shared `aiwork/t<parent>` on `aifamily/t<parent>`, per-child selective sync with main-side verification, final merge at family completion, hard serialization guard, v1 limitations (single-host, path-level, main base).
   - `skills/aitask-pick/_index.md`: family-mode child picks reuse the shared worktree.
   - `workflows/crash-recovery.md`: family worktree survey note.
   - `workflows/_index.md` is hand-curated — bullet needed ONLY if a new page is added (prefer extending existing pages).
4. **Cross-agent verification (not a port)**: after `aitask_skill_rerender.sh`, grep `.agents/skills/` and `.opencode/skills/` for `family-sync` / `aifamily` to confirm the closure rendered; confirm `.codex/instructions.md` / `.opencode/instructions.md` mirrors carry `family_worktree` (t1166_2's hand-sync). Create separate port tasks ONLY if an agent-specific surface diverges; record the finding either way in Final Implementation Notes.

## Verification

- `cd website && hugo build --gc --minify`
- `bash tests/test_skill_render_task_workflow.sh` (if profiles.md or any closure file changed)
- Grep checks from step 4 all pass.
