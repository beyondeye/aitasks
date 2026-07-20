---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [task_workflow, git-integration, child_tasks]
gates: [risk_evaluated]
anchor: 1166
created_at: 2026-07-20 12:06
updated_at: 2026-07-20 12:06
---

## Context

Second child of t1166 (shared family worktree). Adds the `family_worktree` frontmatter field — the durable, per-family opt-in that activates family-worktree mode (user-pinned activation decision). Parallel with t1166_1 (no dependency): the helper only *reads* the field via yaml utils, so the two children touch disjoint files.

Semantics: `family_worktree: true` — boolean scalar, meaningful on a **parent** task only, absent = false. Set at the child-creation checkpoint by the workflow (t1166_3) or manually via `ait update`. A picked child discovers it structurally: child id `<parent>_<n>` → parent file → field read.

Follow `aidocs/framework/aitasks_extension_points.md` "Adding a new frontmatter field" — ALL layers, using the **`anchor` (t1016) worked example** as the template for a scalar field:

## Key Files to Modify

1. **Write path:** `.aitask-scripts/aitask_create.sh` (batch flag `--family-worktree`, interactive flow, `create_task_file` serialization — 3 emit sites, mirror the `anchor` emits) and `.aitask-scripts/aitask_update.sh` (`--family-worktree true|false|""` — mirror `--anchor` at ~220, 748-750, 1914-1918, 2136-2140; empty clears).
2. **Fold machinery:** `.aitask-scripts/aitask_fold_mark.sh` — scalar no-op comment (primary wins), mirroring the anchor comment at ~315-317.
3. **Board TUI:** ships separately (anchor precedent — board layer 3 + reference row were a separate task). Note this exclusion explicitly; do NOT add the widget here.
4. **Sync/merge rule:** `.aitask-scripts/board/aitask_merge.py` `merge_frontmatter()` — newer-`updated_at`-wins scalar branch (mirror `anchor`); NOT `_LIST_UNION_FIELDS`, NOT `BOARD_KEYS`. Plus `.aitask-scripts/board/task_yaml.py` normalization (bool).
5. **Documentation surfaces (all of them):**
   - `seed/aitasks_agent_instructions.seed.md` "## Task File Format" YAML block + regenerate AGENTS.md via the `update_agentsmd` path; hand-sync `.codex/instructions.md` and `.opencode/instructions.md` (markerless — edit by hand, do NOT run insert_aitasks_instructions).
   - `CLAUDE.md` "### Task File Format" YAML block.
   - `website/content/docs/development/task-format.md` frontmatter table.
   - `.claude/skills/task-workflow/task-creation-batch.md` (canonical semantics: field meaning + that workflow sets it at the child-creation checkpoint) and the flag list in `.claude/skills/aitask-create/SKILL.md`.
   - The extension-points checklist itself if this task reveals a missing layer.

## Reference Files for Patterns

- `anchor` field end-to-end: `aitask_create.sh` resolve_anchor ~209-250 + emit sites ~528, ~656, ~1856; `aitask_update.sh` --anchor sites; `board/task_yaml.py:57,99-102`; `board/aitask_merge.py:223`.
- Tests: `tests/test_anchor_create.sh`, `tests/test_anchor_update.sh` (shape for the new field tests), `tests/test_aitask_merge.sh` / `.py` merge cases.

## Implementation Plan

1. `aitask_create.sh`: add `--family-worktree` batch flag (accepts `true`/`false`; validation: reject on child creation — the field is parent-only, mirroring how `--anchor` is rejected with `--parent`), emit `family_worktree: true` only when true.
2. `aitask_update.sh`: `--family-worktree VALUE` with `""` to clear; parent-only validation (reject for `<p>_<c>` ids).
3. `aitask_fold_mark.sh`: scalar no-op comment.
4. `aitask_merge.py` + `task_yaml.py`: newer-wins scalar + normalization.
5. All doc surfaces above.
6. Tests: new `tests/test_family_worktree_frontmatter.sh` (create with flag, update set/clear, parent-only rejection, roundtrip) + merge-rule case added to the aitask_merge test.

## Verification Steps

- `bash tests/test_family_worktree_frontmatter.sh`
- `bash tests/test_aitask_merge.sh` (with the new case)
- `shellcheck .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_update.sh`
- Grep every layer-5 doc surface for `family_worktree` to confirm none was missed.
