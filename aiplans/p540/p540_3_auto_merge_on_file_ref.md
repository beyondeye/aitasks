---
Task: t540_3_auto_merge_on_file_ref.md
Parent Task: aitasks/t540_task_creation_from_codebrowser.md
Parent Plan: aiplans/p540_task_creation_from_codebrowser.md
Sibling Tasks: aitasks/t540/t540_1_*.md, aitasks/t540/t540_2_*.md, aitasks/t540/t540_4_*.md, aitasks/t540/t540_5_*.md, aitasks/t540/t540_6_*.md, aitasks/t540/t540_7_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan — t540_3: auto-merge when `--file-ref` is used

## Scope

Whenever `aitask_create.sh` sees one or more `--file-ref` flags,
detect existing pending tasks referencing the same path and offer to
fold them into the newly-created task — reusing the existing
`aitask_fold_*` scripts. Interactive: fzf multi-select. Batch:
`--auto-merge` / `--no-auto-merge` (default `--no-auto-merge`).

## Depends on

- **t540_1** — `--file-ref` flag, `file_references` field,
  `aitask_find_by_file.sh`. **Must land first.**
- Benefits from t540_7 (fold-time frontmatter union) but does not
  require it — if t540_7 hasn't landed, the body merge still
  happens and the primary's `file_references` list is just its
  own.

## Exploration results (from parent planning)

- **Fold scripts** are production-ready and do not need changes
  here (all changes live in `aitask_create.sh`):
  - `.aitask-scripts/aitask_fold_validate.sh` —
    `--exclude-self <id>`, outputs `VALID:<id>:<path>` /
    `INVALID:<id>:<reason>`. Reasons: `not_found`, `is_self`,
    `has_children`, `status_<status>`. Status must be `Ready` or
    `Editing` to pass.
  - `.aitask-scripts/aitask_fold_content.sh` —
    `<primary_file> <folded1> [<folded2>...]`. Outputs merged
    body to stdout, strips frontmatter.
  - `.aitask-scripts/aitask_fold_mark.sh` —
    `--commit-mode fresh|amend|none`. Outputs
    `PRIMARY_UPDATED`, `FOLDED:<id>`, `TRANSITIVE:<id>`,
    `COMMITTED:<hash>`. Handles transitive folds with dedup by
    default.

- **Create flow touchpoint:** after `create_task_file` returns
  the new task's id+filepath (both the parent-task path at
  ~lines 1300-1338 and the child-task path at ~1340-1356 of
  `aitask_create.sh`), run a new `run_auto_merge_if_needed()`
  helper. Factor out as a helper to avoid duplicating logic
  between the two code paths.

- **Sentinel style for fzf:** label picker at lines 801-899 of
  `aitask_create.sh` uses `>> Done adding labels` and `>> Add new
  label` — mirror this for `>> Done` / `>> None` exits in the
  merge picker. Also use `fzf --multi` so users can pick zero,
  some, or all candidates in one keystroke.

## Design details

- **Auto-merge safety (three layers — enforced here):**
  1. `aitask_find_by_file.sh` already filters by status — folded
     tasks never surface.
  2. After user selection, pass the selected ids to
     `aitask_fold_validate.sh --exclude-self <new_id>`. Parse
     `INVALID:` lines and warn; continue only with `VALID:` ids.
  3. `aitask_fold_mark.sh`'s transitive handling gives clean
     chain collapse if the user merges a task that itself has a
     `folded_tasks` list.

- **Fold execution sequence (the new helper does this):**
  1. Write the new task (already done by the time the helper is
     called).
  2. Collect distinct file-ref paths → union of find-helper
     matches → exclude `<new_id>`.
  3. Show picker (interactive) or honor `--auto-merge` (batch).
  4. Validate: `aitask_fold_validate.sh --exclude-self
     <new_id> <candidates...>`. Skip INVALID lines.
  5. Body merge:
     `aitask_fold_content.sh <new_file> <valid_files...> |
      aitask_update.sh --batch <new_id> --desc-file -`
  6. Mark & commit:
     `aitask_fold_mark.sh --commit-mode fresh <new_id>
      <valid_ids...>`
  7. Use `info()` / `warn()` helpers for user-visible output
     (per CLAUDE.md).

- **Argument flags to add:**
  - `--auto-merge` — sets `BATCH_AUTO_MERGE=true`.
  - `--no-auto-merge` — sets `BATCH_AUTO_MERGE=false` (default).
  - Both mutually exclusive; last-wins if both given.

## Implementation sequence

1. Add `--auto-merge` / `--no-auto-merge` parse, default false.
2. Write `run_auto_merge_if_needed(new_id, new_file)` helper.
3. Call it from both parent and child create paths right after
   `create_task_file`.
4. Write `tests/test_auto_merge_file_ref.sh` (see task file for
   detailed test cases).
5. shellcheck.

## Verification

- `bash tests/test_auto_merge_file_ref.sh` — PASS.
- `bash tests/test_file_references.sh` — still PASS (no
  regression to t540_1).
- Manual interactive: create two pending tasks with
  `--file-ref foo.py`, then run `aitask_create.sh` interactively
  adding the same file ref. Confirm the fzf merge picker
  appears, pick both, confirm fold-mark commit lands with
  matching `folded_tasks`.
- Manual batch `--no-auto-merge`: matches warned but not folded.
- Manual batch `--auto-merge`: matches silently folded.

## Post-implementation

Archival via `./.aitask-scripts/aitask_archive.sh 540_3`.
