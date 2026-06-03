---
Task: t923_2_migrate_fixed_string_files.md
Parent Task: aitasks/t923_consolidate_test_assert_helpers_shared_lib.md
Sibling Tasks: aitasks/t923/t923_1_*.md, aitasks/t923/t923_3_*.md, aitasks/t923/t923_4_*.md, aitasks/t923/t923_5_*.md
Archived Sibling Plans: aiplans/archived/p923/p923_1_*.md
Base branch: main
---

# Plan: Migrate fixed-string (`grep -qF`) files (t923_2)

Depends on 923_1. **Read `aiplans/archived/p923/p923_1_*.md` first** for the
`asserts.sh` API, the `assert_migration_verify.sh` invocation, and the exact
block-removal/source-insertion recipe.

The simplest bucket: these files' inline `assert_contains`/`assert_not_contains`
already use fixed-string matching, so call sites map directly to the shared
**default** — no `_ci`/`_re` remap.

## Step 1 — Regenerate the file list

Use 923_1's bucketing command; take the FIXED bucket (~66 files: `grep -qF`,
`grep -F -q`, `grep -Fq`). Exclude any already migrated in 923_1's pilot.

## Step 2 — Migrate in verified batches (~15-20 files)

For each batch:
1. `assert_migration_verify.sh snapshot <baseline> <files...>`.
2. Per file: insert the `asserts.sh` source after the `test_scaffold.sh` source;
   delete the now-shared inline helper defs; keep file-local `PASS/FAIL/TOTAL`
   and single-use/synonym helpers. No call-site renaming (fixed = default).
3. **Per-call-site flavor check:** if a file's `assert_not_contains` (or
   `assert_contains`) is actually a *different* flavor than fixed, remap that
   helper's calls to the matching `_ci`/`_re` variant. Per-call-site, not
   per-file.
4. `assert_migration_verify.sh check <baseline> <files...>` — counts MUST match.
   Investigate any delta before committing.
5. `shellcheck` a sample; commit the batch with plain `git`
   (`refactor: Consolidate fixed-string assert helpers, batch N (t923_2)`).

## Step 3 — Verify

- Standalone counts identical before vs after for every migrated file.
- Migrated files no longer define the consolidated helpers inline.
- `shellcheck` clean on a sample.

## Final Implementation Notes (fill in)

Count of clean vs per-call-site-flavor files; any file resisting the recipe;
harness refinements.

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9.
