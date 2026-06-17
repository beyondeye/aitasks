---
Task: t1016_1_anchor_schema_script_enforcement.md
Parent Task: aitasks/t1016_anchor_task_topic_grouping.md
Sibling Tasks: aitasks/t1016/t1016_2_*.md, aitasks/t1016/t1016_3_*.md, aitasks/t1016/t1016_4_*.md
Archived Sibling Plans: aiplans/archived/p1016/p1016_*_*.md
Worktree: aiwork/t1016_1_anchor_schema_script_enforcement
Branch: aitask/t1016_1_anchor_schema_script_enforcement
Base branch: main
---

# Plan — t1016_1 Schema + script enforcement (anchor)

Foundation for t1016. Adds the scalar `anchor: <task_id>` field, the
`--anchor` / `--followup-of` creation flags with the inheritance rule,
editability via `aitask_update.sh`, sync-safety in `aitask_merge.py`, and the
fold no-op decision. Owns the inheritance + merge unit tests. All other t1016
children depend on this.

## Anchor semantics (authoritative)

- Group key = `anchor` if set, else own id. Roots emit **no** `anchor:` line.
- Follow-up: `anchor = source.anchor or source.id` — flattened to the root,
  never chained.
- Child: `anchor = parent.anchor or parent.id` (auto-inherit).

## Steps

### 1. `aitask_create.sh` — flags + resolution + validation
- Init `BATCH_ANCHOR=""`, `BATCH_FOLLOWUP_OF=""` near other `BATCH_*`; parse
  `--anchor`/`--followup-of` in `parse_args` (~L144-182).
- `resolve_anchor()` (call after parse, before file creation):
  1. explicit `--anchor` → use verbatim (validated).
  2. elif `--followup-of <src>` → resolve src via `resolve_task_file()`
     (archived-inclusive), read `src.anchor` with `read_yaml_field`;
     `anchor = src.anchor` if non-empty else `<src>`. (Flatten — never chains.)
     If src resolves only inside a tar bundle and anchor can't be read → fall
     back to `<src>`.
  3. elif `--parent <p>` → `anchor = parent.anchor` if non-empty else `<p>`.
  4. else empty (root).
  5. `--anchor` + `--followup-of` → explicit `--anchor` wins.
- `validate_anchor()` mirroring `validate_xdeps_pair` (task_utils.sh L318-358)
  but intra-repo: for each set flag, `aitask_query_files.sh task-status <id>`;
  `die` on `STATUS:NOT_FOUND`/empty; accept any other `STATUS:*` (incl. `Done`,
  so archived roots are allowed). Local-only v1.
- Emit `anchor:` (conditional scalar, mirror `assigned_to`) in
  `create_task_file()` (~L1647), `create_child_task_file()` (~L379, resolve from
  `--parent`), `create_draft_file()` (~L493). Ensure `finalize_draft()` (~L637)
  does NOT strip `anchor` (carry through `--finalize`).
- Add `--anchor` / `--followup-of` to help text.

### 2. `aitask_update.sh` — editable `--anchor`
- `--anchor` flag + `BATCH_ANCHOR_SET`; `CURRENT_ANCHOR` in
  `parse_yaml_frontmatter` (~L362-497); new-value RMW (~L1740-1760); `has_update`
  wire; `write_task_file()` param + conditional emit (~L513-663). Clear-by-empty
  (`--anchor ""`), mirroring `assigned_to`.

### 3. `aitask_merge.py` — scalar merge rule
- In `merge_frontmatter` (L146-214), before the generic `else` (~L209):
  `elif key == "anchor": merged[key] = local_val if local_ts >= remote_ts else
  remote_val` (newer-side-wins; mirrors `updated_at` L189-190). Prevents the
  board-edited anchor from falling into the unresolved/PARTIAL path on sync.

### 4. `aitask_fold_mark.sh` — fold no-op comment
- One-line comment near the list-union block: `anchor` is scalar, intentionally
  not unioned on fold (primary wins; folded file deleted).

## Verification

New `tests/test_anchor_create.sh`, `tests/test_anchor_update.sh`; extend
`tests/test_aitask_merge.py`. Cases:
- root → no `anchor:`; `--anchor 42` → `anchor: 42`.
- `--followup-of <src-no-anchor>` → `<src>`; `<src-anchor=R>` → `R`;
  follow-up-of-follow-up → `R` (no chain).
- child of parent-no-anchor → parent id; child of parent-anchor=R → `R`.
- `--anchor`/`--followup-of` nonexistent → non-zero, no file.
- `--anchor <archived-id>` → succeeds.
- explicit `--anchor` beats `--followup-of`; `update --anchor ""` clears;
  draft `--finalize` preserves anchor.
- `test_anchor_keeps_newer`: local newer → keeps local anchor, not unresolved.

Run: `bash tests/test_anchor_create.sh`, `bash tests/test_anchor_update.sh`,
`bash tests/run_all_python_tests.sh`, `bash tests/test_aitask_merge.sh`,
`shellcheck .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_update.sh`.

## Post-Implementation
Step 9 (review, merge to main, archive) applies when this child completes; the
parent archives automatically once all siblings are done. Record in Final
Implementation Notes any idioms/gotchas useful to siblings (esp. the
`resolve_anchor`/`validate_anchor` helpers and the merge rule location).
