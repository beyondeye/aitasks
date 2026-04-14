---
Task: t540_1_foundation_file_references_field.md
Parent Task: aitasks/t540_task_creation_from_codebrowser.md
Parent Plan: aiplans/p540_task_creation_from_codebrowser.md
Sibling Tasks: aitasks/t540/t540_2_*.md, aitasks/t540/t540_3_*.md, aitasks/t540/t540_4_*.md, aitasks/t540/t540_5_*.md, aitasks/t540/t540_6_*.md, aitasks/t540/t540_7_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan — t540_1: `file_references` foundation

## Scope

Add a structured `file_references: [path, path:N, path:N-M]`
frontmatter list to task files, plus the create/update batch flags
and a `aitask_find_by_file.sh` query helper. This is the foundation
every other t540 child (except t540_2 and t540_6) depends on.

## Exploration results (from parent planning)

Key touchpoints already located:

- `.aitask-scripts/aitask_create.sh`
  - `usage()` ~ lines 72-105 — document the new flag.
  - `parse_args` ~ lines 115-143 — add
    `--file-ref) BATCH_FILE_REFS+=("$2"); shift 2 ;;`.
  - `format_labels_yaml()` at lines 1112-1120 — clone shape for
    `format_file_references_yaml()`.
  - `create_task_file()` at lines 1122-1184 — emit
    `file_references: <yaml>` after `labels: ...` (omit when empty).
  - Child-task write path at ~1300-1356 — mirror the same emit.
  - Interactive file-attach flow at ~1036-1082 — users who add
    files interactively should also get the structured list (in
    addition to the existing body append). Append files gathered
    interactively to `BATCH_FILE_REFS` before the task file is
    written.

- `.aitask-scripts/aitask_update.sh`
  - `parse_args` at ~lines 177-223 — add `--file-ref` (append) and
    `--remove-file-ref` (remove) flags, mirroring
    `--remove-child`. Find the frontmatter-rewrite helper the
    existing `--remove-child` flag uses — likely an awk/sed block
    that rebuilds the frontmatter around an updated list. Reuse
    that helper for the new field.

- `.aitask-scripts/lib/task_utils.sh`
  - `get_user_email()` at lines 163-170 — idiom for the new
    `get_file_references()` helper. Use grep on `^file_references:`
    and a sed to strip brackets, then split on `,`. No PCRE
    (macOS). Guard double-source with the existing
    `_AIT_*_LOADED` pattern.

- New script `.aitask-scripts/aitask_find_by_file.sh`
  - Model structured output on `aitask_query_files.sh` and
    `aitask_fold_validate.sh`.
  - Scan `aitasks/*.md` and `aitasks/t*/t*_*.md` (NOT
    `aitasks/archived/`).
  - Filter by status — only `Ready` or `Editing` tasks count.
  - Output `TASK:<id>:<file>` per match. Exit 0 on no matches.

## Implementation sequence

1. `lib/task_utils.sh` — add `get_file_references`.
2. `aitask_update.sh` — add `--file-ref` / `--remove-file-ref`
   using the existing frontmatter-rewrite helper.
3. `aitask_create.sh` — add `--file-ref` parse, extend
   interactive flow to populate `BATCH_FILE_REFS`, add
   `format_file_references_yaml`, emit in both parent and child
   writers.
4. `aitask_find_by_file.sh` — new file, source `lib/task_utils.sh`,
   implement scan.
5. `tests/test_file_references.sh` — see verification below.
6. `shellcheck` on everything touched.

## Dedup rule (exact-string)

- `foo.py:10-20` and `foo.py:10-20` → one entry.
- `foo.py:10-20` and `foo.py:30-50` → two entries.
- `foo.py` and `foo.py:10-20` → two entries.
- Apply dedup on every `--file-ref` append in both create and
  update paths.

## Verification

- `bash tests/test_file_references.sh` — PASS with the following
  cases:
  1. batch create with single `--file-ref foo.py` — frontmatter
     has `file_references: [foo.py]`.
  2. batch create with multiple mixed refs
     `--file-ref a.py --file-ref b.py:10-20` — list in order,
     brackets, no quoting drift.
  3. batch update `--file-ref c.py` on existing task — appended.
  4. batch update `--remove-file-ref a.py` — removed.
  5. de-dup on append — adding an existing entry is a no-op.
  6. `aitask_find_by_file.sh a.py` — returns all `Ready`/`Editing`
     tasks containing `a.py` (range-agnostic).
  7. Status filter — a task with status `Postponed`, `Done`,
     `Folded`, or `Implementing` is NOT returned by the helper
     even when it references the file.
- Regression: `bash tests/test_draft_finalize.sh` — PASS.
- `shellcheck .aitask-scripts/aitask_create.sh
  .aitask-scripts/aitask_update.sh
  .aitask-scripts/aitask_find_by_file.sh
  .aitask-scripts/lib/task_utils.sh` — clean.

## Post-implementation

Standard archival via
`./.aitask-scripts/aitask_archive.sh 540_1` per task-workflow
Step 9.
