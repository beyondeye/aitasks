---
priority: medium
effort: medium
depends: [t540_1]
issue_type: feature
status: Ready
labels: [aitask_fold, bash_scripts]
created_at: 2026-04-14 10:16
updated_at: 2026-04-14 10:16
---

t540_7: extend `aitask_fold_mark.sh` so that when tasks are folded
together, the primary's `file_references` frontmatter list becomes the
deduped union of its own entries plus every folded task's entries.
This keeps the structured list accurate after fold, so the auto-merge
find helper (t540_3) and the board's file_references widget (t540_5)
see the full picture after any fold operation.

## Context

`aitask_fold_content.sh` already merges task BODIES. But the fold
machinery does not touch most of the primary's frontmatter today —
only `folded_tasks` and (for child tasks) `children_to_implement`.
Without this task, folding A into B would preserve A's
`file_references` only as text inside the merged body section, not
in B's structured list. Subsequent queries via
`aitask_find_by_file.sh` would then miss that A's files ever existed
in this chain, breaking the auto-merge exclusion guarantees the
parent plan relies on.

## Depends on

- **t540_1** — needs the `file_references` field format and the
  `get_file_references()` helper.

## Design decisions (from parent plan)

- **Where:** in `aitask_fold_mark.sh`, not
  `aitask_fold_content.sh`. The mark script already owns the
  primary-frontmatter rewrite (it sets `folded_tasks`), so
  extending it keeps fold mechanics cohesive and atomic with the
  single fold commit.
- **Dedup:** exact-string match on entries. `foo.py:10-20` and
  `foo.py:10-20` collapse; `foo.py:10-20` and `foo.py:30-50` are
  distinct and both kept. Path-only (`foo.py`) and path+range
  (`foo.py:10-20`) are kept as distinct entries. No range merging
  in the first pass.
- **Order:** primary's existing entries first (order preserved),
  then folded tasks' entries in fold-argument order, then
  first-occurrence dedup.
- **Transitive handling:** when B is folded into C and B already
  has `folded_tasks: [A]`, A's `file_references` must also be
  unioned into C (the existing transitive loop already visits A's
  file to re-point `folded_into` — extend that same loop to
  collect `file_references`).

## Key files to modify

1. `.aitask-scripts/lib/task_utils.sh`
   - New `union_file_references <primary_file>
     <folded_file1> [<folded_file2> ...]` helper. Prints the
     unioned list to stdout as a YAML array string (e.g.,
     `[foo.py, bar.py:10-20]`) using the same
     `format_file_references_yaml` idiom t540_1 adds to the
     create script — or better, move/share that formatter
     between create and this helper.
   - Internally uses `get_file_references` (t540_1) to read
     each file.

2. `.aitask-scripts/aitask_fold_mark.sh`
   - Locate the primary-frontmatter-rewrite section that
     currently sets `folded_tasks`. Extend it to also:
     a. Call `union_file_references` passing the primary file
        and every folded task file (including transitive
        folded tasks).
     b. Update the primary's `file_references` field in the
        same in-memory rewrite that sets `folded_tasks`, so
        only ONE write occurs and the fold commit captures
        both changes atomically.
   - The existing transitive loop (the one that re-points
     `folded_into` on the pre-existing `folded_tasks` chain)
     must be enhanced to include the transitive task files in
     the union call.
   - Structured-output lines should stay unchanged
     (`PRIMARY_UPDATED`, `FOLDED`, `TRANSITIVE`, `COMMITTED`).

3. `tests/test_fold_file_refs_union.sh` *(new)*
   - Setup: primary task P with
     `file_references: [a.py:1-5]`; folded task Q with
     `file_references: [b.py, a.py:10-20]`.
   - Run `aitask_fold_mark.sh --commit-mode none P Q` (pairs
     with `aitask_fold_content.sh` if needed).
   - Assert: P's `file_references` = `[a.py:1-5, b.py, a.py:10-20]`
     (exact ordering, no dedup collapse since entries differ).
   - Dedup case: set up Q with `[a.py:1-5]` (same as P);
     after fold, P still has `[a.py:1-5]` (one entry, no
     duplicate).
   - Transitive case: P with `[p.py]`, Q with `[q.py]` and
     `folded_tasks: [R]`, R (file still exists, status
     Folded) with `[r.py]`. Fold Q into P. Assert P's
     `file_references` = `[p.py, q.py, r.py]` — R's entries
     were unioned via the transitive path.
   - No regressions: existing `aitask_fold_mark.sh` behavior
     for `folded_tasks`, `folded_into`, and status updates
     must remain identical. If any existing test exercises
     `aitask_fold_mark.sh`, update it to assert the new
     `file_references` line appears (as empty list when no
     fold inputs carry file_references — or just absent).

## Reference files for patterns

- `.aitask-scripts/aitask_fold_mark.sh` — the script to extend;
  study the existing `folded_tasks` CSV-rewrite logic as the
  template for the new frontmatter write.
- `.aitask-scripts/lib/task_utils.sh` — pattern for shell
  helpers; must not double-source.
- `tests/test_fold_*.sh` (if any) — style guide for writing the
  new test.

## Implementation plan

1. Add `union_file_references` to `lib/task_utils.sh`.
2. Extend `aitask_fold_mark.sh` to call it inside the
   existing frontmatter-rewrite section, passing primary +
   direct-fold + transitive-fold file lists.
3. Write `tests/test_fold_file_refs_union.sh`.
4. Run any existing fold tests to confirm no regression.
5. `shellcheck` both touched scripts.

## Verification

- `bash tests/test_fold_file_refs_union.sh` — PASS.
- Regression: manual fold of two real tasks (one with
  file_references, one without) — confirm the primary ends
  with the union and the fold commit is a single commit with
  both `folded_tasks` and `file_references` changes in its
  diff.
- End-to-end integration with t540_3: once both t540_3 and
  t540_7 land, the auto-merge flow in `aitask_create.sh`
  naturally produces correct `file_references` on the new
  primary without any t540_3-side code change.

## Out of scope

- Range merging (contiguous/disjoint range union) — explicit
  follow-up; the first pass keeps distinct ranges as distinct
  entries.
- `aitask_fold_content.sh` body merging — untouched.
