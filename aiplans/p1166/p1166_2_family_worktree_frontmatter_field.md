---
Task: t1166_2_family_worktree_frontmatter_field.md
Parent Task: aitasks/t1166_shared_worktree_for_child_task_families.md
Sibling Tasks: aitasks/t1166/t1166_1_family_worktree_helper_script.md, aitasks/t1166/t1166_3_task_workflow_family_mode_main_path.md, aitasks/t1166/t1166_4_family_failure_recovery_surfaces.md, aitasks/t1166/t1166_5_family_worktree_docs_and_profile_surface.md
Base branch: main
---

# Plan: t1166_2 — `family_worktree` frontmatter field

## Context

Adds the durable per-family opt-in field. Semantics (PINNED): `family_worktree: true` — boolean scalar, **parent tasks only**, absent = false; set by the workflow at the child-creation checkpoint (t1166_3) or via `ait update`. Follow `aidocs/framework/aitasks_extension_points.md` "Adding a new frontmatter field" with the `anchor` (t1016) worked example as the scalar template. Parallel with t1166_1 (which only reads the field via yaml utils).

## Steps

1. **`aitask_create.sh` write path**: add `--family-worktree true|false` batch flag; reject when combined with `--parent` (field is parent-only — mirror the `--anchor`-vs-`--parent` rejection at ~215); emit `family_worktree: true` in all three frontmatter emit sites (mirror anchor emits at ~528, ~656, ~1856) only when true. Interactive flow: skip (field is workflow-set; note in help text).
2. **`aitask_update.sh`**: `--family-worktree VALUE` (`true`/`false`/`""` to clear), mirroring `--anchor` flag plumbing at ~220 (parse), ~748-750 (validate), ~1914-1918 (apply), ~2136-2140 (usage). Validation: reject for child ids (`<p>_<c>`) with a distinct error message.
3. **`aitask_fold_mark.sh`**: scalar no-op comment next to the anchor comment (~315-317): primary task's value wins; never unioned.
4. **`board/aitask_merge.py` `merge_frontmatter()`**: newer-`updated_at`-wins scalar branch (mirror `anchor` at ~223). Explicitly NOT `_LIST_UNION_FIELDS`, NOT `BOARD_KEYS`. **`board/task_yaml.py`**: normalize to bool on load (~57, 99-102 area).
5. **Board TUI widget: explicitly out of scope** (anchor precedent — board layer ships separately). State this in Final Implementation Notes.
6. **Documentation surfaces (ALL of layer 5)**:
   - `seed/aitasks_agent_instructions.seed.md` "## Task File Format" YAML block; regenerate AGENTS.md via the `update_agentsmd` marker path; hand-edit `.codex/instructions.md` + `.opencode/instructions.md` (markerless mirrors — never run insert_aitasks_instructions on them).
   - `CLAUDE.md` "### Task File Format" YAML block (hand-maintained).
   - `website/content/docs/development/task-format.md` frontmatter table.
   - `.claude/skills/task-workflow/task-creation-batch.md` (canonical semantics definition) + flag list in `.claude/skills/aitask-create/SKILL.md`. NOTE: both are templated/closure files — if edited, regenerate affected goldens + rerender in the same commit (`aidocs/framework/skill_authoring_conventions.md`).
   - Extension-points checklist itself only if a missing layer is discovered.
7. **Tests**: new `tests/test_family_worktree_frontmatter.sh` — create parent with flag (field present), create without (absent), child-creation rejection, update set/clear roundtrip, child-update rejection; add a `family_worktree` newer-wins case to the aitask_merge test (`tests/test_aitask_merge.sh` / its Python harness).

## Verification

- `bash tests/test_family_worktree_frontmatter.sh`
- `bash tests/test_aitask_merge.sh`
- `shellcheck .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_update.sh .aitask-scripts/aitask_fold_mark.sh`
- `grep -rn family_worktree` across every layer-5 surface listed above — all present.
- If task-creation-batch.md / aitask-create SKILL.md changed: `bash tests/test_skill_render_task_workflow.sh` + `./.aitask-scripts/aitask_skill_verify.sh`.
