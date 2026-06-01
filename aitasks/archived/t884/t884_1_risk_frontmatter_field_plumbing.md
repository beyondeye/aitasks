---
priority: high
effort: medium
depends: []
issue_type: enhancement
status: Done
labels: [task_workflow, aitask-create, aitask_board]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-01 00:30
updated_at: 2026-06-01 11:53
completed_at: 2026-06-01 11:53
---

## Context

Foundation child of t884 (add task risk evaluation in planning — see `aiplans/p884_add_task_risk_evaluation_in_planning.md`). Adds the two new task frontmatter fields the rest of the feature builds on. **No behavior change when the fields are absent** — this is pure additive plumbing.

- **`risk`** — scalar, values `high|medium|low`, an aggregate risk level (over code-health + goal-achievement dimensions) assigned by the risk-evaluation step in a later child (t884_3) via `aitask_update.sh`. It is **NOT chosen up-front at task creation** — mirror `priority`'s *update/display* plumbing only, not its create-time input handling. **Display-only — NOT a sort/score dimension, NO border color.**
- **`risk_mitigation_tasks`** — a YAML **list** of task IDs (the "before" mitigations whose landing later forces plan re-verification). Omitted by default.

Decision (from parent plan): mirror `priority`'s existing hardcoded duplication of `high|medium|low` rather than extracting a shared constant for `risk` alone (a lone cross-language constant would be a new drift surface `priority` lacks). t884_7 files a named follow-up to extract both enums to a single source.

## Key Files to Modify

- `.aitask-scripts/aitask_create.sh` — **No change.** `risk` is NOT chosen up-front at task creation; it is a planning output assigned later by the risk-evaluation step (t884_3) via `aitask_update.sh`. `risk_mitigation_tasks` is likewise written post-create (t884_4). Both fields are always absent at create time, so there is nothing to serialize — do NOT add a `--risk` flag, `select_risk()`, interactive prompt, validation, or create-time serialization.
- `.aitask-scripts/aitask_update.sh` — this is where `risk` enters. Add `BATCH_RISK`/`CURRENT_RISK` vars, `--risk` flag, parse from file, validation, `interactive_update_risk()` fn, field-selection handler, and `write_task_file` serialization (conditional-emit like `verifies`/`xdeprepo` so unset = no `risk:` line). Also add `--risk-mitigation-tasks` (list, read-modify-write friendly) so later children can populate it.
- `.aitask-scripts/aitask_ls.sh` — parse `risk` for **display only**; do NOT add it to the `p_score` sort pipeline.
- `.aitask-scripts/board/aitask_board.py` — add `risk` to the snapshot dict (~line 2388), a ReadOnlyField for Done/Folded (~2424), and an editable `CycleField("Risk", ["low","medium","high"], ...)` (~2429). NO `_risk_border_color` analog.
- `.aitask-scripts/aitask_fold_mark.sh` — add explicit handling for the `risk_mitigation_tasks` **list** field: drop/ignore on fold (task-instance-specific, not foldable/unionable). `risk` scalar needs no fold change.
- `tests/test_update_risk.sh` (**new**) — automated coverage of `aitask_update.sh` risk handling (set, validate, omit-by-default, `--risk-mitigation-tasks` list read-modify-write) plus a guard that `aitask_create.sh` emits no risk fields.
- `tests/test_fold_risk_mitigation_drop.sh` (**new**) — automated coverage that fold drops `risk_mitigation_tasks` and keeps the primary's `risk`.

## Reference Files for Patterns

- `priority`'s *update/display* plumbing is the template (NOT its create-time input handling — `aitask_create.sh` is untouched here): `aitask_update.sh` (flag ~227, parse ~380, validation ~1461, `interactive_update_priority` ~987, `write_task_file` ~487), `aitask_ls.sh` (~225-230), `aitask_board.py` CycleField (~956-1046, instantiated ~2429). For the conditional-emit (omit-when-unset) pattern, follow `verifies`/`xdeprepo` in `write_task_file` rather than `priority` (which is always written).
- `aitask_fold_mark.sh` list-field handling: see how it unions `verifies` and manages `folded_tasks` (those are the list-handling precedents; `risk_mitigation_tasks` should be the opposite — explicitly dropped).

## Implementation Plan

1. Add `risk` where `priority` appears in **update/ls/board only** (NOT create), mirroring the pattern (but: omit-by-default, no border color, no sort score).
2. Add `risk_mitigation_tasks` list support to `aitask_update.sh` serialization + `--risk-mitigation-tasks` flag (read-modify-write for additive use later). Not handled at create.
3. Add the `risk_mitigation_tasks` drop rule to `aitask_fold_mark.sh`.
4. Defaults: both fields omitted entirely when not set; readers use `.get(...)`/absent-safe parsing and render nothing.
5. Write automated tests (`tests/test_update_risk.sh`, `tests/test_fold_risk_mitigation_drop.sh`) following the self-contained bash convention with the `setup_fake_aitask_repo` scaffold; model on `tests/test_fold_mark.sh` and `tests/test_verified_update_flags.sh`. Board rendering is left to the t884_8 manual-verification sibling (no automated board test here).

## Verification Steps

- A freshly created task (`aitask_create.sh ... --desc "x"`, no risk flag) has **no** `risk:` line — confirm create was not touched.
- `./.aitask-scripts/aitask_update.sh --batch <id> --risk medium` updates the field; interactive mode offers Risk; `--risk-mitigation-tasks` writes the list.
- `ait board` shows the risk value (read-only for Done/Folded, CycleField otherwise); existing tasks with no risk render blank, no errors.
- Fold a task carrying `risk_mitigation_tasks` into a primary → primary keeps its own `risk`, and `risk_mitigation_tasks` is NOT carried over.
- **New automated tests pass:** `bash tests/test_update_risk.sh && bash tests/test_fold_risk_mitigation_drop.sh`.
- `shellcheck .aitask-scripts/aitask_update.sh .aitask-scripts/aitask_ls.sh .aitask-scripts/aitask_fold_mark.sh tests/test_update_risk.sh tests/test_fold_risk_mitigation_drop.sh` (create.sh unchanged).
- Run any existing `bash tests/test_*update*` / `*fold*` suites.

## Notes for sibling tasks

The `risk` scalar and `risk_mitigation_tasks` list both land here. Later children (884_3 writes `risk`; 884_4 populates `risk_mitigation_tasks` via read-modify-write of `--risk-mitigation-tasks`; 884_5 reads `risk_mitigation_tasks`) depend on these flags existing.
