---
priority: low
effort: high
depends: [t923_1]
issue_type: refactor
status: Implementing
labels: [testing, bash_scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-03 11:25
updated_at: 2026-06-03 12:41
---

## Context

Migration child for t923. Depends on 923_1 (which builds `tests/lib/asserts.sh`
and `tests/lib/assert_migration_verify.sh`). **Read 923_1's archived plan
(`aiplans/archived/p923/p923_1_*.md`) first** — it defines the exact lib API,
the verify-harness invocation, and the block-removal/source-insertion recipe.

This child migrates the **fixed-string (`grep -qF`) bucket** — the largest and
simplest group. Because these files' inline `assert_contains` /
`assert_not_contains` already use fixed-string matching, their call sites map
**directly to the shared `assert_contains` / `assert_not_contains` default**
(no `_ci`/`_re` remap needed). This is the cleanest batch.

## Scope

~66 files whose inline `assert_contains` uses `grep -qF` / `grep -F -q` /
`grep -Fq`. Regenerate the exact list with the bucketing command from 923_1's
plan (do NOT trust a hardcoded list — other work may have shifted files).
Exclude any fixed-string files already migrated in 923_1's pilot.

## Recipe (per file, in verified batches of ~15-20)

1. Snapshot baseline counts via `assert_migration_verify.sh` (Mode A) for the batch.
2. For each file:
   - Insert `. "$PROJECT_DIR/tests/lib/asserts.sh"` immediately after the existing `. "$PROJECT_DIR/tests/lib/test_scaffold.sh"` source line.
   - Delete the inline definitions of the helpers now provided by the shared lib (`assert_eq`, `assert_contains`, `assert_not_contains`, and any of `assert_exit_zero/nonzero`, `assert_file_exists/not_exists`, `assert_dir_exists/not_exists` the file defines). Leave single-use domain helpers and any synonym-named exit helpers inline (synonyms handled in 923_5).
   - Keep the file-local `PASS=0 / FAIL=0 / TOTAL=0` initialization (the lib references these globals; it does not declare them).
   - Call sites need NO renaming — fixed-string is the shared default.
3. Re-run `assert_migration_verify.sh` (Mode B) for the batch; pass/fail/total counts MUST be identical. Investigate ANY delta before committing.
4. Commit the batch (`git`, not `./ait git` — these are code files), then proceed to the next batch.

## Watch for

- A file whose `assert_contains` is fixed but `assert_not_contains` is a different flavor (or vice-versa) — migrate the differing helper's call sites to the matching `_ci`/`_re` variant per its original inline flavor. Per-call-site, not per-file.
- `shellcheck` each migrated file clean (modulo pre-existing info notes).

## Verification

- Standalone pass/fail/total counts identical before vs after for every migrated file.
- Migrated files no longer define the consolidated helpers inline.
- `shellcheck` clean on a sample of migrated files.

## Notes for sibling tasks

Record how many files migrated cleanly vs needed per-call-site flavor handling, any file that resisted the mechanical recipe, and refinements to the verify harness. 923_3/923_4 reuse this exact recipe with `_ci`/`_re` remapping.

## Step 9 (Post-Implementation): standard cleanup, archival, and merge per task-workflow.
