---
Task: t923_5_synonyms_stragglers_and_final_gates.md
Parent Task: aitasks/t923_consolidate_test_assert_helpers_shared_lib.md
Sibling Tasks: aitasks/t923/t923_1_*.md, aitasks/t923/t923_2_*.md, aitasks/t923/t923_3_*.md, aitasks/t923/t923_4_*.md
Archived Sibling Plans: aiplans/archived/p923/p923_1_*.md, aiplans/archived/p923/p923_2_*.md, aiplans/archived/p923/p923_3_*.md, aiplans/archived/p923/p923_4_*.md
Base branch: main
---

# Plan: Synonyms, stragglers, and final verification gates (t923_5)

Terminus child. Depends on 923_1..923_4. **Read 923_1's plan for the API/recipe.**

## Step 1 — Synonym exit-helper files (~10)

Files using non-canonical exit-check names. Regenerate:
```bash
grep -lE '^[[:space:]]*assert_(nonzero_exit|zero_exit|exits_zero|exits_nonzero|exit_code)\(\)' tests/test_*.sh
```
Known set: `test_aitask_update_xdeps.sh`, `test_aitask_merge.sh`,
`test_aitask_create_xdeprepo_alone.sh`, `test_lock_force.sh`,
`test_skill_render_uniform.sh`, `test_lock_diag.sh`, `test_skill_verify.sh`,
`test_xdeps_validation.sh`, `test_skill_render.sh`, `test_skill_rerender.sh`.

Per file: source `asserts.sh`, drop shared inline defs, and **rename synonym
call sites to canonical names** (`assert_exit_zero` / `assert_exit_nonzero`).
**Before renaming, confirm the synonym's signature/semantics match the
canonical helper.** `assert_exit_code` in particular may take an expected-code
argument — if its semantics differ, leave it inline rather than force-fit.
Verify counts unchanged.

## Step 2 — `pass()`/`fail()`-style files (3)

Files using `pass()`/`fail()` functions instead of `PASS/FAIL/TOTAL`. Migrate
the shared assert helpers where signatures allow; if a file's counter model is
fundamentally different, leave it inline and note why (must not change behavior).

## Step 3 — Stragglers

Any remaining `tests/test_*.sh` still defining a consolidated helper inline
(e.g. files that only define exit/file/dir helpers and so weren't in the flavor
buckets). Find:
```bash
grep -lE '^[[:space:]]*(assert_eq|assert_contains|assert_not_contains|assert_exit_zero|assert_exit_nonzero|assert_file_exists|assert_file_not_exists|assert_dir_exists|assert_dir_not_exists)\(\)' tests/test_*.sh
```
Migrate with the standard recipe.

## Step 4 — Final verification gates (from parent t923)

1. `grep -rnE 'assert_contains\(\)' tests/` → defined **once** (in
   `tests/lib/asserts.sh`). The `_ci`/`_re` variants are distinct names and are
   acceptable; the gate concerns `assert_contains()` itself.
2. `shellcheck tests/lib/asserts.sh` and a sample of migrated files clean
   (modulo pre-existing info notes).
3. No remaining inline unguarded grep assert:
   `grep -rnE 'grep -q[a-zA-Z]* "\$' tests/ | grep -v ' -- '` → empty.
4. **Whole-suite parity:** run every `tests/test_*.sh` standalone on `main`
   (baseline) vs the migrated tree; pass/fail counts identical, accounting for
   the ~6 pre-existing batch cross-contamination failures (run individually).

## Final Implementation Notes (fill in)

Final count of inline helper defs remaining (should be only legitimately
single-use/domain helpers); any synonym/pass-fail file deliberately left inline
(with rationale); whole-suite parity result.

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9. This is the last
child; its archival also archives the parent t923.
