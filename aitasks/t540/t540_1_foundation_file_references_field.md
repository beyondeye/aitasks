---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [aitask-create, bash_scripts]
created_at: 2026-04-14 10:12
updated_at: 2026-04-14 10:12
---

Foundation for t540: add a structured `file_references` frontmatter field
to task files plus the bash flags and query helper the rest of the t540
children need. This task must land before t540_3, t540_4, t540_5, t540_7.

## Context

Today `aitask_create.sh` only accepts file attachments by dropping raw
paths into the description body — no structured field, no line ranges,
no way for other tooling to find "tasks about file X". t540 introduces
a new `file_references` YAML list on the task frontmatter with entries
of the form `path`, `path:N`, or `path:N-M` (1-indexed inclusive line
numbers). This child task is the foundation: writing the field,
reading it back, and listing pending tasks that reference a given path.

## Design decisions (from parent plan)

- **Format:** YAML list of strings. Mirrors `labels` / `depends` shape.
- **Append semantics:** `--file-ref` always appends; no
  "replace-all" flag in the first pass.
- **Dedup on write:** de-dup by exact string match — keep both
  `foo.py:10-20` and `foo.py:30-50` since they are distinct ranges.
- **Line-range-agnostic search:** the find helper matches by path
  only. Two entries that differ only in range still count as the
  same file reference when searching.

## Key files to modify

1. `.aitask-scripts/aitask_create.sh`
   - Around line 72-105 (`usage()`): document the new `--file-ref`
     flag (repeatable).
   - Around line 115-143 (arg parsing): add `--file-ref) BATCH_FILE_REFS+=("$2"); shift 2 ;;` — store as an indexed array.
   - Add `--file-ref` support to the interactive prompt flow so a
     user running `aitask_create.sh` without `--batch` can add file
     references structurally (the existing file-attach flow only
     writes to the description body; keep that too for backwards
     compat, but also write the structured list).
   - Around line 1112-1120 (`format_labels_yaml`): add a
     `format_file_references_yaml()` mirror that emits
     `[foo.py, bar.py:10-20]`.
   - Around line 1122-1184 (`create_task_file` and the child-task
     creation path at ~1300-1356): emit the new
     `file_references: <yaml_list>` line into the frontmatter,
     right after `labels`. Preserve backwards compat: omit the line
     entirely when the list is empty.

2. `.aitask-scripts/aitask_update.sh`
   - Around line 177-223 (arg parsing): add two new flags:
     - `--file-ref PATH[:START[-END]]` — append an entry to the
       existing list (de-duped against exact matches already
       present).
     - `--remove-file-ref PATH[:START[-END]]` — surgical removal,
       matches `--remove-child` idiom.
   - Find the frontmatter-rewrite helper the existing
     `--remove-child` flag uses and extend it for `file_references`.

3. `.aitask-scripts/lib/task_utils.sh`
   - Add `get_file_references <task_file>` — parses the frontmatter
     and prints each entry on its own line (empty output when the
     field is absent). Use the same sed/awk style as existing
     helpers. No PCRE (macOS portability — see CLAUDE.md). Guard
     against double-sourcing with an `_AIT_*_LOADED` variable.

4. `.aitask-scripts/aitask_find_by_file.sh` *(new file)*
   - `usage`: `aitask_find_by_file.sh <path>`
   - Scans active `aitasks/*.md` and `aitasks/t*/t*_*.md` (NOT
     `aitasks/archived/` — aitask_find_by_file is about pending
     work). For each file:
     - Read frontmatter `status` — skip unless `Ready` or
       `Editing`. Skip `Implementing`, `Postponed`, `Done`,
       `Folded`.
     - Read `file_references` list — if any entry's path-only
       portion matches `<path>`, emit
       `TASK:<task_id>:<task_file>` on its own line.
   - Exit 0 even when no matches found (silent). Exit non-zero
     only on argument errors.
   - Source `lib/task_utils.sh` for the `get_file_references`
     helper.
   - Structured-output style mirrors `aitask_query_files.sh` and
     `aitask_fold_validate.sh`.

## Reference files for patterns

- `.aitask-scripts/aitask_fold_validate.sh` — structured output
  lines, task resolution, frontmatter reads.
- `.aitask-scripts/aitask_query_files.sh` — `TASK_FILE:`,
  `CHILD_FILE:`, etc. output patterns.
- `.aitask-scripts/lib/task_utils.sh` `get_user_email()` around
  line 163-170 — the simple grep/sed helper pattern to mirror.
- `.aitask-scripts/aitask_create.sh` `format_labels_yaml()` at
  lines 1112-1120 — to model `format_file_references_yaml()`.
- `.aitask-scripts/aitask_update.sh` `--remove-child` handling —
  to model `--remove-file-ref`.

## Implementation plan

1. Add `get_file_references()` to `lib/task_utils.sh`.
2. Add `--file-ref` / `--remove-file-ref` to `aitask_update.sh`
   with the same frontmatter-rewrite approach used for
   `--remove-child`.
3. Add `--file-ref` to `aitask_create.sh` (arg parsing,
   interactive flow, `create_task_file` serialization for BOTH the
   parent-task and child-task code paths).
4. Write `aitask_find_by_file.sh`.
5. Write `tests/test_file_references.sh` covering:
   - batch create with single, multiple, with-range, and
     mixed `--file-ref` flags
   - `get_file_references` round-trip
   - batch update add/remove round-trip
   - `aitask_find_by_file.sh` hit (matching status) and miss
     (excluded status) cases
   - de-dup on append (same path+range should not duplicate)
6. Run `shellcheck` on all touched scripts.

## Verification

- `bash tests/test_file_references.sh` — PASS.
- Regression: `bash tests/test_draft_finalize.sh` — PASS.
- `shellcheck .aitask-scripts/aitask_create.sh
   .aitask-scripts/aitask_update.sh
   .aitask-scripts/aitask_find_by_file.sh
   .aitask-scripts/lib/task_utils.sh` — clean.
- Manual: `./.aitask-scripts/aitask_create.sh --batch --commit
   --name tmp --priority low --effort low --type chore --labels
   testing --file-ref foo.py:10-20 --file-ref bar.py --desc "x"`,
  inspect the created task file, confirm frontmatter has
  `file_references: [foo.py:10-20, bar.py]`.
- Manual: `./.aitask-scripts/aitask_find_by_file.sh foo.py` — the
  task above appears; after setting its status to `Folded`, the
  find helper no longer returns it.

## Out of scope

- Fold-time union of `file_references` — t540_7 handles that.
- Board widget for `file_references` — t540_5 handles that.
- `aitask_create.sh` auto-merge logic — t540_3 handles that.
- Codebrowser integration — t540_4 handles that.
