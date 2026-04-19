---
Task: t583_2_verifies_frontmatter_field_three_layer.md
Parent Task: aitasks/t583_manual_verification_module_for_task_workflow.md
Sibling Tasks: aitasks/t583/t583_3_verification_followup_helper_script.md, aitasks/t583/t583_4_manual_verification_workflow_procedure.md, aitasks/t583/t583_5_archival_gate_and_carryover.md, aitasks/t583/t583_6_issue_type_manual_verification_and_unit_tests.md, aitasks/t583/t583_7_plan_time_generation_integration.md, aitasks/t583/t583_8_documentation_website_and_skill.md, aitasks/t583/t583_9_meta_dogfood_aggregate_verification.md
Archived Sibling Plans: aiplans/archived/p583/p583_1_verification_parser_python_helper.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-19 11:17
---

# Plan: t583_2 — `verifies:` Frontmatter Field (3-layer propagation)

## Context

Adds a new `verifies: [task_id, ...]` list frontmatter field used by manual-verification tasks to declare which feature siblings they validate. Per CLAUDE.md's "Adding a New Frontmatter Field" rule, new list fields must touch **3 layers** (create/update scripts, fold_mark union, board TaskDetailScreen widget) or the board silently drops them.

Independent of t583_1. Required by t583_3 (follow-up helper uses the list to disambiguate) and t583_7 (generation integration populates it).

## Verification findings — divergences from original plan

Codebase verification (plan was written before `depends:` pattern was fully traced):

1. **`format_yaml_list()` lives locally in each script** (aitask_create.sh:1182, aitask_update.sh:393), NOT in `lib/task_utils.sh`. Mirror by reusing the local function (do not refactor to shared lib now).
2. **`depends` in aitask_update.sh uses a single `--deps` set-all flag** (line 194), NOT add/remove/set variants. The closest match for the spec's 3-flag pattern is **labels** (`--labels`, `--add-label`, `--remove-label` at lines 195-197, processed via `process_label_operations()` at line 555). Mirror the labels pattern for `verifies`.
3. **`issue_type: manual_verification` does not exist yet** in `aitasks/metadata/task_types.txt`. t583_6 registers it. **Defer the interactive prompt gating**: this task adds batch-flag support only. The interactive prompt gated by `issue_type == manual_verification` lands in t583_6 (or its own follow-up), once the type exists.
4. **`fold_mark.sh` folded_tasks union is inline** (lines 99-149, using `declare -A seen` associative-array dedup), not a shared helper. Mirror that exact inline pattern for `verifies:` union.
5. **`DependsField` is read-only** (aitask_board.py:918) — navigation + removal only, no inline edit widget. `VerifiesField` matches (read-only).

## Files to modify

### 1. `.aitask-scripts/aitask_create.sh`

- **Line ~138** (batch parser): add `--verifies) BATCH_VERIFIES="$2"; shift 2 ;;` next to `--deps`.
- Add `BATCH_VERIFIES=""` to the batch-mode variable init block near the top.
- Thread `verifies` parameter through `create_task_file()` and its variants (lines 390, 470, 1398 are the 3 write sites).
- In each of the 3 write sites, **after** the `depends: $deps_yaml` line, emit **conditionally** (only if non-empty — avoids noise in all tasks):
  ```bash
  if [[ -n "$verifies" ]]; then
      local verifies_yaml
      verifies_yaml=$(format_yaml_list "$verifies")
      echo "verifies: $verifies_yaml"
  fi
  ```
- **No interactive prompt** in this task (`manual_verification` type doesn't exist yet; t583_6 adds it).

### 2. `.aitask-scripts/aitask_update.sh`

Mirror the **labels** pattern (not `depends`):

- **Line ~195** (parser): add three flags:
  ```bash
  --verifies) BATCH_VERIFIES="$2"; BATCH_VERIFIES_SET=true; shift 2 ;;
  --add-verifies) BATCH_ADD_VERIFIES+=("$2"); shift 2 ;;
  --remove-verifies) BATCH_REMOVE_VERIFIES+=("$2"); shift 2 ;;
  ```
- State vars near top (alongside `BATCH_LABELS_SET`, `BATCH_ADD_LABELS`, `BATCH_REMOVE_LABELS`):
  ```bash
  BATCH_VERIFIES=""
  BATCH_VERIFIES_SET=false
  BATCH_ADD_VERIFIES=()
  BATCH_REMOVE_VERIFIES=()
  CURRENT_VERIFIES=""
  ```
- **Frontmatter reader at line 335** (after `depends)` case): add
  ```bash
  verifies)
      CURRENT_VERIFIES=$(parse_yaml_list "$value")
      CURRENT_VERIFIES=$(normalize_task_ids "$CURRENT_VERIFIES")
      ;;
  ```
- Add **`process_verifies_operations()`** helper near `process_label_operations()` (line 555) — same shape, but **after** building the final CSV, pipe through `normalize_task_ids` (task IDs, not free-form strings).
- Add to `has_update` detection block (~line 1278):
  ```bash
  [[ "$BATCH_VERIFIES_SET" == true ]] && has_update=true
  [[ ${#BATCH_ADD_VERIFIES[@]} -gt 0 ]] && has_update=true
  [[ ${#BATCH_REMOVE_VERIFIES[@]} -gt 0 ]] && has_update=true
  ```
- Call `process_verifies_operations` in the main update flow (mirroring the `new_labels=...` call at line 1355); pass resulting `new_verifies` into `write_task_file`.
- **Write path at line 442** (after `depends:` emission): emit conditionally (only if non-empty, consistent with create path):
  ```bash
  if [[ -n "$verifies" ]]; then
      local verifies_yaml
      verifies_yaml=$(format_yaml_list "$verifies")
      echo "verifies: $verifies_yaml"
  fi
  ```
- Add `verifies` as a new positional parameter to `write_task_file()` (after `file_references`).

### 3. `.aitask-scripts/aitask_fold_mark.sh`

Parallel to the existing `folded_tasks` union (lines 99-149), add a **`verifies` union block**:

- Read primary's current `verifies:` via `parse_yaml_list "$(read_yaml_field "$primary_file" "verifies")"`.
- For each folded task file, read its `verifies:` list.
- Dedupe using a separate `declare -A seen_verifies=()` associative array (do NOT reuse the `seen` array from folded_tasks — different namespace).
- Join into `verifies_csv`.
- At the `aitask_update.sh --batch "$primary_id" ...` call at **line 185**, add:
  ```bash
  $( [[ -n "$verifies_csv" ]] && printf -- '--verifies %s' "$verifies_csv" )
  ```
  Or (cleaner): build a `verifies_args=()` array like the `file_ref_args` pattern at line 176 and splat it.

No transitive handling needed for `verifies:` (unlike `folded_tasks`, these don't form a chain — just union the lists).

### 4. `.aitask-scripts/board/aitask_board.py`

- After `DependsField` class (line 918), add `VerifiesField` class (copy-and-rename):
  - `render()` → `f"  [b]Verifies:[/b] {v_str}"`
  - Keep `can_focus = True`, `on_key`, `on_focus`, `on_blur` unchanged.
  - `_open_dep` → `_open_verify`: same navigation; for a single item, push `TaskDetailScreen`; for multiple, push `DependencyPickerScreen` (reuse — it's task-agnostic).
  - `_ask_remove_dep` → `_ask_remove_verify`: invokes a new `_remove_verify_from_task()` helper.
- After `_remove_dep_from_task` (line 982), add `_remove_verify_from_task()` — identical shape, operating on `task.metadata["verifies"]`.
- **TaskDetailScreen.compose()** — after the `depends` block at line 1986-1992, add:
  ```python
  if meta.get("verifies"):
      verifies = meta["verifies"]
      if verifies and self.manager:
          yield VerifiesField(verifies, self.manager, self.task_data, classes="meta-ro")
      elif verifies:
          v_str = ", ".join(str(v) for v in verifies)
          yield ReadOnlyField(f"[b]Verifies:[/b] {v_str}", classes="meta-ro")
  ```

## Reference patterns (verified)

- `parse_yaml_list()` — `lib/task_utils.sh:106`
- `normalize_task_ids()` — `lib/task_utils.sh:146`
- `format_yaml_list()` — **local**: `aitask_create.sh:1182`, `aitask_update.sh:393`
- `process_label_operations()` — `aitask_update.sh:555`
- folded_tasks union (inline dedup) — `aitask_fold_mark.sh:99-149`
- `DependsField` class — `aitask_board.py:918-979`
- `DependsField` composition — `aitask_board.py:1986-1992`

## Verification

1. **Batch create round-trip** — use `feature` type (since `manual_verification` doesn't exist yet):
   ```bash
   ./.aitask-scripts/aitask_create.sh --batch --type feature --name test_verifies --verifies "10,11" --desc "test"
   ```
   Inspect resulting file: `verifies: [10, 11]` present in frontmatter.

2. **Batch update — set/add/remove**:
   ```bash
   ./.aitask-scripts/aitask_update.sh --batch <id> --verifies "20,21"       # set
   ./.aitask-scripts/aitask_update.sh --batch <id> --add-verifies 22        # add
   ./.aitask-scripts/aitask_update.sh --batch <id> --remove-verifies 20     # remove
   ```
   Inspect: `verifies: [21, 22]` after the sequence.

3. **Empty-case preservation** — create a task WITHOUT `--verifies`; confirm no `verifies:` line appears (conditional emission).

4. **Fold union** — create two throwaway tasks with `verifies: [1, 2]` and `verifies: [2, 3]`; fold both into a third; inspect primary: `verifies: [1, 2, 3]` (deduped).

5. **Board render** — launch `ait board`, open detail panel of a task with `verifies:`, confirm `Verifies:` field renders in the meta section.

6. **Cleanup** — after verification, archive/delete the throwaway test tasks.

## Automated tests

Add **`tests/test_verifies_field.sh`** — bash test mirroring the structure of `tests/test_fold_file_refs_union.sh` (sandboxed temp git repo, `assert_eq` / `assert_contains` / `assert_not_contains` helpers, PASS/FAIL summary).

**Test setup** (shared `setup_project` function, copied from `test_fold_file_refs_union.sh`):
- Create temp dir + bare remote + local clone
- Copy `aitask_create.sh`, `aitask_update.sh`, `aitask_fold_mark.sh`, and `lib/` helpers into the sandbox
- Seed `aitasks/metadata/task_types.txt` with the 8 standard types
- Seed empty `labels.txt`

**Test cases:**

1. **`test_create_with_verifies`** — run `aitask_create.sh --batch --type feature --name t_a --verifies "10,11" --desc "x"`; grep the resulting file for exactly `verifies: [10, 11]`.
2. **`test_create_without_verifies_omits_field`** — run `aitask_create.sh --batch --type feature --name t_b --desc "y"` (no `--verifies`); assert the file does NOT contain a `verifies:` line (conditional emission).
3. **`test_update_set_verifies`** — create a task, then run `aitask_update.sh --batch <id> --verifies "20,21"`; assert `verifies: [20, 21]`.
4. **`test_update_add_verifies`** — starting from `[20, 21]`, run `--add-verifies 22`; assert `verifies: [20, 21, 22]`.
5. **`test_update_remove_verifies`** — starting from `[20, 21, 22]`, run `--remove-verifies 20`; assert `verifies: [21, 22]`.
6. **`test_update_add_and_remove_combined`** — single invocation with both `--add-verifies 30 --remove-verifies 21`; assert `verifies: [22, 30]`.
7. **`test_update_verifies_overrides_add_remove`** — `--verifies "40,41" --add-verifies 42` in one call; assert `--verifies` seeds the base, then add applies: `[40, 41, 42]`.
8. **`test_update_add_verifies_dedup`** — starting from `[10, 11]`, run `--add-verifies 11`; assert the list is unchanged (dedup).
9. **`test_fold_unions_verifies`** — create three tasks: A with `verifies: [1, 2]`, B with `verifies: [2, 3]`, C (primary, no verifies); fold A and B into C; assert C has `verifies: [1, 2, 3]` (order: existing-primary, then folded in fold-order, deduped).
10. **`test_fold_preserves_primary_verifies`** — A with `verifies: [1, 2]`, primary C starts with `verifies: [9]`; fold A into C; assert C has `verifies: [9, 1, 2]` (primary entries first).
11. **`test_fold_no_verifies_anywhere`** — fold tasks with no `verifies:` into a primary with no `verifies:`; assert the resulting primary does NOT gain a `verifies:` line (no empty list emission).

The test file is self-contained, uses only bash + git, and runs via `bash tests/test_verifies_field.sh`. No runner changes needed.

**Board widget test** — not included; `aitask_board.py`'s TUI behavior is out of scope for bash tests. The compose-method addition is covered by manual verification step 5. (If a Python test suite is desired for `VerifiesField` later, it would live in `tests/test_aitask_board_*.py`, but that's deferred; existing `DependsField` has no Python test either.)

## Follow-up task to create before implementation

`format_yaml_list()` is currently defined byte-identically in two places (`aitask_create.sh:1182` and `aitask_update.sh:393`), and `format_labels_yaml` / `format_file_references_yaml` in `aitask_create.sh` are synonyms of it. Its inverses (`parse_yaml_list`, `normalize_task_ids`) already live in `lib/task_utils.sh`.

**As the first action of Step 7 (implementation), before any `verifies:` work,** create a follow-up chore/refactor task via `aitask_create.sh --batch` with this shape:

- **Name:** `consolidate_format_yaml_list_helper`
- **Type:** `refactor`
- **Priority:** low
- **Effort:** low
- **Labels:** `framework`
- **Description:** Move `format_yaml_list()` from `aitask_create.sh` and `aitask_update.sh` into `lib/task_utils.sh` (alongside the existing `parse_yaml_list` / `normalize_task_ids`). Delete both local copies. Collapse `format_labels_yaml()` and `format_file_references_yaml()` (in `aitask_create.sh`) into calls to the shared `format_yaml_list`. Add a unit test in `tests/test_task_utils.sh` (or new `tests/test_format_yaml_list.sh`) covering empty, single-entry, and multi-entry cases.

Record the new task ID in the plan's **Final Implementation Notes** so t583_2's own commit message can reference it as "see tNNN for follow-up".

After creating the follow-up task, proceed with t583_2 using the **local `format_yaml_list`** pattern unchanged. The refactor is intentionally deferred to keep t583_2's diff scoped to the new field.

## Out of scope (explicit)

- **Interactive prompt** in `aitask_create.sh` gated by `issue_type: manual_verification` — deferred to t583_6 (which adds the type) or its follow-up.
- **Python test for `VerifiesField` widget** — mirroring the (absent) `DependsField` test pattern; not added now.
- **Actually performing** the `format_yaml_list` consolidation — done in the follow-up task above, not here.

## Step 9 reminder

Standard post-implementation flow per `.claude/skills/task-workflow/SKILL.md` Step 9. Commit format: `feature: Add verifies frontmatter field (t583_2)`. Plan file commit uses `ait:` prefix.

## Final Implementation Notes

- **Actual work done:** Implemented the 3-layer propagation for the new `verifies: [task_id, ...]` list frontmatter field. Layer 1 (create): added `--verifies` batch flag to `aitask_create.sh`, threaded through `create_task_file()`, `create_child_task_file()`, `create_draft_file()`; field emitted conditionally only when non-empty. Layer 2 (update): added `--verifies`, `--add-verifies`, `--remove-verifies` flags to `aitask_update.sh` mirroring the labels pattern; added `process_verifies_operations()` helper; extended frontmatter reader, write_task_file signature, and all 3 write_task_file call sites (parent completion, interactive mode, batch mode). Layer 3 (fold): added `verifies` union block in `aitask_fold_mark.sh` parallel to the existing `folded_tasks` union, using a separate `seen_verifies` associative array; no transitive walk (verifies entries are feature-task references, not fold chains). Layer 4 (board): added `VerifiesField` read-only widget class + `_remove_verify_from_task()` helper in `aitask_board.py`, composed into `TaskDetailScreen` after the depends block. Added `tests/test_verifies_field.sh` with 13 test cases covering all three layers; all pass.
- **Deviations from plan:** One refinement to `process_verifies_operations()` — the `local IFS=','; joined="${new_array[*]}"` pattern required splitting the assignment into two lines (bash does not apply `VAR=value cmd` prefix semantics to bare variable assignments). Fixed during implementation.
- **Issues encountered:** None material. Initial smoke test attempted `--commit` in sandbox and failed because `aitask_claim_id.sh` depends on `archive_scan.sh` and the counter infrastructure. Worked around by smoke-testing in draft mode (no counter needed) and doing the full round-trip in the automated test using seeded task files.
- **Key decisions:** Conditional emission (only write `verifies:` when non-empty) rather than always emitting `verifies: []` — keeps noise out of all existing tasks. No interactive prompt gated by `issue_type: manual_verification` was added because that type does not yet exist in `task_types.txt` (t583_6 registers it). Labels pattern (set + add + remove) chosen over depends pattern (single set-all) to match the expected fine-grained ergonomics of a verifies list.
- **Follow-up task created:** **t587** — chore/refactor task to consolidate `format_yaml_list()` (currently byte-identically defined in `aitask_create.sh:1182` and `aitask_update.sh:393`; synonyms `format_labels_yaml` / `format_file_references_yaml` also collapse into it) into `lib/task_utils.sh`. Deliberately deferred to keep t583_2's diff scoped to the new field. See `aitasks/t587_consolidate_format_yaml_list_helper.md`.
- **Notes for sibling tasks:**
  - **t583_3 (follow-up helper)** can depend on `verifies:` being a stable list field on manual-verification tasks. Use `parse_yaml_list` + `normalize_task_ids` from `lib/task_utils.sh` to read it from a task file — same pattern as depends.
  - **t583_6 (issue_type: manual_verification)** adds the type to `aitasks/metadata/task_types.txt`. Once that lands, the interactive prompt in `aitask_create.sh` can be gated on `issue_type == manual_verification` and call a new `select_verifies()` helper (mirror `select_dependencies()` at line 959).
  - **t583_7 (plan-time generation)** populates `verifies:` at task creation time — pass `--verifies "id1,id2,..."` to `aitask_create.sh --batch`.
  - **Fold behavior:** `aitask_fold_mark.sh` unions `verifies` across primary + folded tasks, deduped, primary entries first. No transitive walk (unlike folded_tasks).
  - **Board widget:** `VerifiesField` is read-only (Enter navigates to the verified task or removes on confirm). For edit ergonomics, shell out to `aitask_update.sh --verifies`. If a later task wants a picker, reuse `DependencyPickerScreen` (already task-agnostic).
