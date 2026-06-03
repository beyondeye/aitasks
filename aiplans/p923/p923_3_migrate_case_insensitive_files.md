---
Task: t923_3_migrate_case_insensitive_files.md
Parent Task: aitasks/t923_consolidate_test_assert_helpers_shared_lib.md
Sibling Tasks: aitasks/t923/t923_1_*.md, aitasks/t923/t923_2_*.md, aitasks/t923/t923_4_*.md, aitasks/t923/t923_5_*.md
Archived Sibling Plans: aiplans/archived/p923/p923_1_*.md, aiplans/archived/p923/p923_2_*.md
Base branch: main
---

# Plan: Migrate case-insensitive (`grep -qi`) files (t923_3)

Depends on 923_1/923_2. **Read 923_1's plan for the API/recipe and 923_2's notes
for batch refinements.**

These files' inline matching is case-insensitive, so call sites map to the
shared **`assert_contains_ci` / `assert_not_contains_ci`** variants — unless a
needle audit shows the needle's case already matches the asserted output
verbatim (then the fixed-string default is equivalent).

## Step 1 — Regenerate the file list

923_1's bucketing command, CI bucket (~33 files: `grep -qi`, `grep -Fqi`,
`grep -qiF`).

## Step 2 — Migrate in verified batches

1. `snapshot` baseline.
2. Per file: source `asserts.sh`, delete shared inline defs, keep `PASS/FAIL/TOTAL`.
3. **Needle audit + remap** per `assert_contains`/`assert_not_contains` call:
   - Casing could differ between needle and output (original `-qi` load-bearing)
     → rename to `assert_contains_ci` / `assert_not_contains_ci`.
   - Needle case already matches output exactly → fixed-string default is
     equivalent; may stay on `assert_contains`. **When in doubt, use `_ci`**
     (preserves original behavior).
4. `check` — counts MUST match. A delta means a casing actually mattered →
   switch that call to `_ci` (or you've found a latent test bug; note it under
   "Upstream defects identified").
5. `shellcheck` sample; commit batch (plain `git`).

## Step 3 — Verify

- Standalone counts identical before vs after.
- No remaining inline `grep -qi` assert defs in migrated files.
- `shellcheck` clean on a sample.

## Final Implementation Notes (fill in)

Which files genuinely needed `_ci` vs were flavor-agnostic; any latent casing
bug surfaced.

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9.
