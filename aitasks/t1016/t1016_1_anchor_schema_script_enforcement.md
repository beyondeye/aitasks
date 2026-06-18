---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [aitask_board, child_tasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-17 13:35
updated_at: 2026-06-18 11:00
---

## Context

Foundation child of t1016 (anchor task topic grouping). Introduces the scalar
`anchor: <task_id>` frontmatter field and the structurally-unbypassable
enforcement of the inheritance rule in `aitask_create.sh`, plus editability via
`aitask_update.sh`, sync-safety in `aitask_merge.py`, and the fold no-op
decision. **Every other t1016 child depends on this** (the field and flags must
exist before docs/spawn-sites/board can reference them). This child OWNS the
inheritance + merge unit tests (testability-first).

Anchor semantics (from t1016): group key = `anchor` if set, else own id. A
follow-up sets `anchor = source.anchor or source.id` — always flattened to the
root, never chained. A child auto-inherits `anchor = parent.anchor-or-id`. A
root has NO `anchor:` line (absent ⇒ own-id is the key).

## Key Files to Modify

- `.aitask-scripts/aitask_create.sh` — add `--anchor <id>` and `--followup-of
  <src>` flags, resolution + validation logic, emit `anchor:` in the 3 create
  paths + draft finalize, help text.
- `.aitask-scripts/aitask_update.sh` — add editable `--anchor` (scalar
  read-modify-write, clear-by-empty).
- `.aitask-scripts/board/aitask_merge.py` — add an explicit scalar merge rule
  for `anchor` (newer-side-wins) so concurrent syncs don't drop it into the
  generic unresolved/PARTIAL path.
- `.aitask-scripts/aitask_fold_mark.sh` — one-line comment documenting that
  `anchor` is scalar and intentionally NOT unioned on fold (primary wins).
- `tests/test_anchor_create.sh`, `tests/test_anchor_update.sh` (new),
  `tests/test_aitask_merge.py` (add a case).

## Reference Files for Patterns

- **Scalar emit idiom** (conditional `if [[ -n "$x" ]]; then echo "x: $x"; fi`):
  `aitask_create.sh` `create_task_file()` (~L1647-1748, see `assigned_to`
  ~L1723-1726), `create_child_task_file()` (~L379-480, see `issue` ~L460-462),
  `create_draft_file()` (~L493-606, see `assigned_to` ~L580-582) and
  `finalize_draft()` (~L637-758, strips draft-only fields — make sure `anchor`
  is carried through, not stripped).
- **Arg parsing**: `aitask_create.sh::parse_args` (~L144-182); init `BATCH_*`
  globals near other batch vars.
- **Validation to mirror**: `validate_xdeps_pair()` in
  `.aitask-scripts/lib/task_utils.sh` (L318-358) — note it uses
  `aitask_query_files.sh ... task-status <id>` for existence, which is
  ARCHIVED-INCLUSIVE (returns `STATUS:Done` for archived). Use the same
  subcommand and accept ANY `STATUS:*` (incl. Done) so anchoring to an archived
  topic root is allowed; `die` only on `STATUS:NOT_FOUND`/empty.
- **Read a field from a source task file**: `read_yaml_field` (lib/yaml_utils.sh,
  used by `read_xdeps`/`read_xdeprepo` in task_utils.sh ~L286-300). Resolve the
  source/parent path with `resolve_task_file()` (task_utils.sh ~L518-602,
  archived-inclusive). If the source resolves only inside a tar bundle (very old
  archive) and its anchor can't be read, fall back to `anchor = <source_id>`.
- **Update RMW idiom**: `aitask_update.sh` — `CURRENT_ASSIGNED_TO` parse
  (~L469), `BATCH_*_SET` + new-value block (~L1740-1744 for `assigned_to`),
  `write_task_file()` param + conditional emit (~L630-636). Supports clearing via
  `--assigned-to ""` — mirror for `--anchor ""`.
- **Merge rule to mirror**: `aitask_merge.py::merge_frontmatter` (L146-214); the
  `updated_at` newer-wins rule at L189-190
  (`merged[key] = local_val if local_ts >= remote_ts else remote_val`). Insert an
  `elif key == "anchor":` with the same body just before the generic `else`
  (~L209). Existing merge tests: `tests/test_aitask_merge.py` (see
  `test_updated_at_keeps_newer` ~L124) and `tests/test_aitask_merge.sh`.

## Implementation Plan

1. **aitask_create.sh flags + globals**: init `BATCH_ANCHOR=""`,
   `BATCH_FOLLOWUP_OF=""`; parse `--anchor`/`--followup-of` in `parse_args`.
2. **resolve_anchor()** helper (call after parse, before file creation):
   - explicit `--anchor` set → use verbatim (after validation).
   - elif `--followup-of <src>` set → resolve src path (archived-inclusive),
     read `src.anchor`; `anchor = src.anchor` if non-empty else `<src>` (flatten;
     a follow-up of a follow-up resolves to the same root — never chains).
   - elif `--parent <p>` (child) → `anchor = parent.anchor` if non-empty else
     `<p>`.
   - else → empty (root).
   - `--anchor` + `--followup-of` together → explicit `--anchor` wins.
3. **validate_anchor()**: for each of `--anchor` / `--followup-of` that is set,
   `task-status <id>`; `die` on `NOT_FOUND`/empty; accept any other `STATUS:*`.
   Local-only (no cross-repo anchors v1).
4. **Emit** the resolved `anchor` (conditional scalar) in `create_task_file`,
   `create_child_task_file`, `create_draft_file`; ensure `finalize_draft`
   preserves it (do NOT add `anchor` to the draft-field strip sed).
5. **Help/usage** text: document both flags.
6. **aitask_update.sh**: `--anchor` flag + `BATCH_ANCHOR_SET`; `CURRENT_ANCHOR`
   in `parse_yaml_frontmatter`; new-value RMW; `has_update` wire; `write_task_file`
   param + emit. Clear-by-empty supported.
7. **aitask_merge.py**: add the `anchor` newer-side-wins rule.
8. **aitask_fold_mark.sh**: add the scalar-no-union comment near the list-union
   block.

## Verification Steps

Run: `bash tests/test_anchor_create.sh`, `bash tests/test_anchor_update.sh`,
`python3 -m pytest tests/test_aitask_merge.py -v` (or
`bash tests/run_all_python_tests.sh`), and re-run `bash tests/test_aitask_merge.sh`.

Cases:
- root (no flags) → file has no `anchor:` line.
- `--anchor 42` → `anchor: 42`.
- `--followup-of <src-without-anchor>` → `anchor: <src>`.
- `--followup-of <src-with-anchor=R>` → `anchor: R` (flatten).
- follow-up of a follow-up → resolves to root `R` (no chaining).
- child of parent-without-anchor → `anchor: <parent>`.
- child of parent-with-anchor=R → `anchor: R`.
- `--anchor <nonexistent>` and `--followup-of <nonexistent>` → non-zero exit,
  no file created.
- `--anchor <archived-task-id>` → SUCCEEDS (archived-inclusive validation).
- `--anchor` + `--followup-of` both → explicit `--anchor` wins.
- `aitask_update.sh --batch <id> --anchor X` sets it; `--anchor ""` clears it.
- draft created with anchor then `--finalize` → anchor preserved in final file.
- `test_anchor_keeps_newer`: local `updated_at` newer → merged keeps local
  anchor and `anchor` is NOT in the unresolved list.

## Notes for sibling tasks

- The `anchor` field is the persistent record for NEW tasks and loose follow-ups.
  Legacy tasks remain anchorless; the board child (t1016_4) handles legacy
  parent+children grouping via a display-time `topic_key` fallback — no migration.
- Roots deliberately have no `anchor:` key; consumers must treat absent anchor as
  "own id is the group key".
- Keep `anchor` OUT of `BOARD_KEYS` (it is semantic, not board-layout) — relevant
  to t1016_4's `task_yaml.py` work.
