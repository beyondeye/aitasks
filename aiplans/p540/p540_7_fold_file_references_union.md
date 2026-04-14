---
Task: t540_7_fold_file_references_union.md
Parent Task: aitasks/t540_task_creation_from_codebrowser.md
Parent Plan: aiplans/p540_task_creation_from_codebrowser.md
Sibling Tasks: aitasks/t540/t540_1_*.md, aitasks/t540/t540_2_*.md, aitasks/t540/t540_3_*.md, aitasks/t540/t540_4_*.md, aitasks/t540/t540_5_*.md, aitasks/t540/t540_6_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan — t540_7: union `file_references` during fold

## Scope

Extend `aitask_fold_mark.sh` so that when tasks are folded together,
the primary's `file_references` frontmatter list becomes the deduped
union of its own entries plus every folded task's entries (including
transitive folded tasks). Keeps the structured list accurate so
t540_3 (auto-merge) and t540_5 (board widget) have complete data.

## Depends on

- **t540_1** — needs `file_references` field +
  `get_file_references()` helper in `lib/task_utils.sh`.

## Exploration results (from parent planning)

- **Fold-mark script:** `.aitask-scripts/aitask_fold_mark.sh`.
  Structured outputs: `PRIMARY_UPDATED:<id>`, `FOLDED:<id>`,
  `CHILD_REMOVED:<p>:<c>`, `TRANSITIVE:<id>`, and one of
  `COMMITTED:<hash>` / `AMENDED` / `NO_COMMIT`. The primary's
  frontmatter is rewritten in-place to set `folded_tasks: <csv>`
  (deduped, including transitive tasks re-pointed here). That
  rewrite block is where the new union logic must live so a
  single atomic file write captures both `folded_tasks` and
  `file_references`.

- **Transitive traversal:** the mark script already iterates
  over each pre-existing `folded_tasks` entry of the folded
  tasks to re-point `folded_into` to the new primary. Piggyback
  on that loop: as each transitive task file is touched, also
  read its `file_references` and collect it into the union
  call.

- **Existing helpers reused:**
  - `get_file_references <file>` (t540_1) — reads the list from
    a task file.
  - `format_file_references_yaml <csv>` (t540_1) — formats the
    union back into the `[..., ...]` YAML string.

## Design

- **New helper `union_file_references <primary_file>
  <folded1> [<folded2>...]`** in `lib/task_utils.sh`:
  - Reads each file via `get_file_references`.
  - Concatenates into one list in order: primary first, then
    each folded in argument order.
  - Dedupes by first-occurrence exact-string match. Entries
    differing only in range are kept as distinct entries (no
    range merging in first pass).
  - Prints the unioned list as CSV on stdout.
- **Call site in `aitask_fold_mark.sh`:** inside the existing
  frontmatter-rewrite block for the primary task:
  - Collect direct folded task file paths.
  - Collect transitive folded task file paths (the same list
    the existing loop walks).
  - Call `union_file_references` with `<primary> <direct...>
    <transitive...>`.
  - If the result is non-empty, write `file_references:
    [<formatted>]` into the primary frontmatter alongside
    `folded_tasks`. If the result is empty (no file refs
    anywhere in the chain), leave the field absent.

## Implementation sequence

1. Add `union_file_references` to `lib/task_utils.sh`.
2. Extend the primary-frontmatter-rewrite block in
   `aitask_fold_mark.sh` to collect transitive files and call
   the new helper, then emit `file_references:` in the rewrite.
3. Write `tests/test_fold_file_refs_union.sh`:
   - Basic: primary `[a.py:1-5]`, folded `[b.py, a.py:10-20]`
     → primary `[a.py:1-5, b.py, a.py:10-20]`.
   - Dedup: primary `[a.py:1-5]`, folded `[a.py:1-5]` →
     primary `[a.py:1-5]` (single entry).
   - Transitive: primary `[p.py]`, folded Q with
     `folded_tasks: [R]`, R `[r.py]` → primary
     `[p.py, q.py, r.py]`.
4. Confirm existing fold tests (if any) still pass.
5. shellcheck.

## Verification

- `bash tests/test_fold_file_refs_union.sh` — PASS.
- Manual: fold two real tasks where one has `file_references`
  and the other has none — confirm the primary ends with the
  union and the fold commit diff contains both `folded_tasks`
  and `file_references` changes in a single commit.
- End-to-end with t540_3 (once both have landed): create a new
  task with `--file-ref foo.py --auto-merge` where a pending
  task with the same file exists. Confirm the new (primary)
  task ends with the union of both `file_references` lists.

## Post-implementation

Archival via `./.aitask-scripts/aitask_archive.sh 540_7`.
