---
priority: medium
effort: medium
depends: [t540_1]
issue_type: feature
status: Implementing
labels: [aitask-create, aitask_fold, bash_scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-14 10:14
updated_at: 2026-04-14 13:06
---

t540_3: when `aitask_create.sh` is invoked with one or more
`--file-ref` flags, detect pending tasks that already reference the
same path and offer to fold them into the newly-created task. Reuses
the existing `aitask_fold_*` scripts — no new fold logic is written
here.

## Context

t540_1 adds the `file_references` field and a `aitask_find_by_file.sh`
query helper. This task plugs that helper into the create flow so the
user doesn't unknowingly open a second task that competes with an
existing pending one for the same file. The merge happens via the
existing fold infrastructure, so there is ONE merge code path in the
project.

## Depends on

- **t540_1** — needs `--file-ref` flag, `file_references` field, and
  `aitask_find_by_file.sh` helper.
- Benefits from (but does not require) t540_7 — the frontmatter
  `file_references` union on fold. Without t540_7, the body merge
  still happens but the primary's frontmatter list is not unioned;
  that is a follow-up refinement handled by t540_7.

## Design decisions (from parent plan)

- **Scope:** any invocation of `aitask_create.sh` with `--file-ref`
  triggers the check, not only the codebrowser path.
- **Interactive mode:** present matches via fzf
  (`Select tasks to merge into the new task`) with `>> Done / >>
  None` exits mirroring the label picker.
- **Batch mode:** `--auto-merge` / `--no-auto-merge` flags, default
  `--no-auto-merge` for backwards compatibility.
- **Fold mechanics:** always fold matched existing tasks INTO the
  new task (new task is primary). Execution:
  1. Create the new task file normally (so it exists on disk).
  2. Run `aitask_fold_validate.sh --exclude-self <new_id>
     <match_ids...>` to drop ineligible matches.
  3. Pipe `aitask_fold_content.sh <new_file> <matched_files...>`
     through `aitask_update.sh --batch <new_id> --desc-file -` to
     merge bodies.
  4. Run `aitask_fold_mark.sh --commit-mode fresh <new_id>
     <match_ids...>` to update frontmatter and commit the fold.
- **Exclusion safety (three layers):**
  1. `aitask_find_by_file.sh` filters by status (`Ready`/`Editing`
     only) so Folded tasks never surface.
  2. `aitask_fold_validate.sh` double-checks status before the
     fold actually runs.
  3. `aitask_fold_mark.sh` handles transitive folds with dedup, so
     a chain of "same file" tasks collapses cleanly.

## Key files to modify

1. `.aitask-scripts/aitask_create.sh`
   - After the task is successfully created on disk (after the
     `create_task_file` call, both parent and child code paths,
     around lines 1300-1356), add a post-create "auto-merge" step
     that:
     - Unions all `--file-ref` path portions (strip `:start-end`).
     - For each distinct path, calls `aitask_find_by_file.sh
       <path>` and collects unique `TASK:<id>:<file>` lines.
     - Excludes the just-created task ID from the candidate set
       (it shouldn't be in the result anyway, but belt + braces).
     - **Interactive mode:** if any candidates remain, offer fzf
       multi-select (using `--multi`) with `>> Done` / `>> None`
       sentinels. Empty selection means "create as-is".
     - **Batch mode:** if `--auto-merge` flag is set, fold all
       candidates; if `--no-auto-merge` (default), print a
       visible warning listing the candidates and skip the fold.
   - On non-empty user selection, execute the 4-step fold
     sequence above. Collect `VALID:<id>:<file>` lines from
     `aitask_fold_validate.sh` and skip any `INVALID:` ones with
     a warning.
   - Use `die()` / `warn()` / `info()` from `terminal_compat.sh`
     for all user-facing output (per CLAUDE.md).
   - Add new flags `--auto-merge` / `--no-auto-merge` to parse_args
     around lines 115-143; default `BATCH_AUTO_MERGE=false`.

2. `tests/test_auto_merge_file_ref.sh` *(new)*
   - Create task A with `--file-ref foo.py` (no merge).
   - Create task B with `--file-ref foo.py --auto-merge` — confirm
     A is folded into B (B has `folded_tasks: [<A_id>]`, A has
     `status: Folded`, `folded_into: <B_id>`).
   - Create task C with `--file-ref foo.py` and `--no-auto-merge`
     — confirm B is NOT folded (batch default).
   - Status-filter test: set A's status to `Postponed`, create
     task D with `--file-ref foo.py --auto-merge`, confirm A is
     NOT offered (filtered out by the find helper).
   - Transitive test: set up B with `folded_tasks: [A]`, create E
     with `--file-ref foo.py --auto-merge` selecting B — confirm
     A's `folded_into` is re-pointed to E after fold (verified via
     `aitask_fold_mark.sh` transitive logic).

## Reference files for patterns

- `.aitask-scripts/aitask_fold_validate.sh`,
  `aitask_fold_content.sh`, `aitask_fold_mark.sh` — already
  production-tested; called as-is, no changes.
- `.claude/skills/aitask-fold/SKILL.md` — interactive fold
  workflow for UX consistency (user-facing language).
- `.aitask-scripts/aitask_create.sh` label-picker fzf loop at
  lines 801-899 for the `>> Done / >> None` sentinel style.

## Implementation plan

1. Add `--auto-merge` / `--no-auto-merge` flag parsing.
2. Refactor the post-`create_task_file` block so it can run the
   auto-merge step in both the parent and child code paths
   without code duplication (helper function
   `run_auto_merge_if_needed(new_id, new_file)`).
3. Write the helper: union distinct paths, query find helper,
   present fzf / batch-flag decision, run fold validation, run
   fold content merge + update, run fold mark.
4. Write `tests/test_auto_merge_file_ref.sh`.
5. Run shellcheck.

## Verification

- `bash tests/test_auto_merge_file_ref.sh` — PASS.
- `bash tests/test_file_references.sh` — still PASS (must not
  regress t540_1's tests).
- Manual interactive: create two pending tasks referencing
  `tests/test_file_references.sh`, then run `./.aitask-scripts/aitask_create.sh`
  interactively adding the same file ref. Confirm the fzf merge
  picker appears, pick one, confirm fold-mark commit lands.
- Manual batch with `--no-auto-merge` (default) — matches
  detected are warned but NOT folded; the new task is created
  standalone.
- Manual batch with `--auto-merge` — matches are silently folded.

## Out of scope

- Codebrowser "c" keybinding — t540_4.
- Fold-time frontmatter union of `file_references` — t540_7.
- Board field widget — t540_5.
