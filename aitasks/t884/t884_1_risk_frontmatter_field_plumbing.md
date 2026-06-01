---
priority: high
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [task_workflow, aitask-create, aitask_board]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-01 00:30
updated_at: 2026-06-01 09:32
---

## Context

Foundation child of t884 (add task risk evaluation in planning — see `aiplans/p884_add_task_risk_evaluation_in_planning.md`). Adds the two new task frontmatter fields the rest of the feature builds on. **No behavior change when the fields are absent** — this is pure additive plumbing.

- **`risk`** — scalar, values `high|medium|low`, an aggregate risk level (over code-health + goal-achievement dimensions) assigned by the risk-evaluation step in a later child. Mirrors the existing `priority` field exactly. **Display-only — NOT a sort/score dimension, NO border color.**
- **`risk_mitigation_tasks`** — a YAML **list** of task IDs (the "before" mitigations whose landing later forces plan re-verification). Omitted by default.

Decision (from parent plan): mirror `priority`'s existing hardcoded duplication of `high|medium|low` rather than extracting a shared constant for `risk` alone (a lone cross-language constant would be a new drift surface `priority` lacks). t884_7 files a named follow-up to extract both enums to a single source.

## Key Files to Modify

- `.aitask-scripts/aitask_create.sh` — add `--risk` batch flag + default (omit by default, do NOT default to medium), validation (`high|medium|low`), `select_risk()` interactive fzf fn, interactive flow + summary display, and serialization in all 3 `create_*_file` functions (draft, task, child). `risk_mitigation_tasks` is NOT user-set at create — it is written later by the mitigation procedure; only ensure the serializer can emit it if present (or skip entirely at create).
- `.aitask-scripts/aitask_update.sh` — add `BATCH_RISK`/`CURRENT_RISK` vars, `--risk` flag, parse from file, validation, `interactive_update_risk()` fn, field-selection handler, and `write_task_file` serialization. Also add `--risk-mitigation-tasks` (list, read-modify-write friendly) so later children can populate it.
- `.aitask-scripts/aitask_ls.sh` — parse `risk` for **display only**; do NOT add it to the `p_score` sort pipeline.
- `.aitask-scripts/board/aitask_board.py` — add `risk` to the snapshot dict (~line 2388), a ReadOnlyField for Done/Folded (~2424), and an editable `CycleField("Risk", ["low","medium","high"], ...)` (~2429). NO `_risk_border_color` analog.
- `.aitask-scripts/aitask_fold_mark.sh` — add explicit handling for the `risk_mitigation_tasks` **list** field: drop/ignore on fold (task-instance-specific, not foldable/unionable). `risk` scalar needs no fold change.

## Reference Files for Patterns

- `priority` plumbing is the exact template — see parent plan's "Critical files" and the verified line refs: `aitask_create.sh` (batch flag ~144, validation ~1766, `select_priority` ~802, serialization in `create_draft_file`/`create_task_file`/`create_child_task_file`), `aitask_update.sh` (flag ~227, parse ~380, validation ~1461, `interactive_update_priority` ~987, `write_task_file` ~487), `aitask_ls.sh` (~225-230), `aitask_board.py` CycleField (~956-1046, instantiated ~2429).
- `aitask_fold_mark.sh` list-field handling: see how it unions `verifies` and manages `folded_tasks` (those are the list-handling precedents; `risk_mitigation_tasks` should be the opposite — explicitly dropped).

## Implementation Plan

1. Add `risk` everywhere `priority` appears in create/update/ls/board, mirroring the pattern (but: omit-by-default, no border color, no sort score).
2. Add `risk_mitigation_tasks` list support to create/update serialization + `aitask_update.sh` flag (read-modify-write for additive use later).
3. Add the `risk_mitigation_tasks` drop rule to `aitask_fold_mark.sh`.
4. Defaults: both fields omitted entirely when not set; readers use `.get(...)`/absent-safe parsing and render nothing.

## Verification Steps

- `./.aitask-scripts/aitask_create.sh --batch --commit --name tmp_risk --priority low --effort low --type chore --labels task_workflow --risk high --desc "x"` → new task file has `risk: high`; a task created WITHOUT `--risk` has no `risk:` line.
- `./.aitask-scripts/aitask_update.sh --batch <id> --risk medium` updates the field; interactive mode offers Risk.
- `ait board` shows the risk value (read-only for Done/Folded, CycleField otherwise); existing tasks with no risk render blank, no errors.
- Fold a task carrying `risk_mitigation_tasks` into a primary → primary keeps its own `risk`, and `risk_mitigation_tasks` is NOT carried over.
- `shellcheck .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_update.sh .aitask-scripts/aitask_ls.sh .aitask-scripts/aitask_fold_mark.sh`.
- Run any existing `bash tests/test_*create*` / `*update*` suites.

## Notes for sibling tasks

The `risk` scalar and `risk_mitigation_tasks` list both land here. Later children (884_3 writes `risk`; 884_4 populates `risk_mitigation_tasks` via read-modify-write of `--risk-mitigation-tasks`; 884_5 reads `risk_mitigation_tasks`) depend on these flags existing.
