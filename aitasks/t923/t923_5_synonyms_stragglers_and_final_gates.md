---
priority: low
effort: medium
depends: [t923_4]
issue_type: refactor
status: Implementing
labels: [testing, bash_scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-03 11:27
updated_at: 2026-06-03 16:27
---

## Context

Final child for t923. Depends on 923_1..923_4. **Read 923_1's archived plan for
the lib API and recipe.** This child cleans up the long tail and runs the
whole-suite verification gates from the parent task.

## Scope / work

1. **Synonym exit-helper files** (~10 files using non-canonical names:
   `assert_nonzero_exit`, `assert_zero_exit`, `assert_exits_zero`,
   `assert_exits_nonzero`, `assert_exit_code`):
   `test_aitask_update_xdeps.sh`, `test_aitask_merge.sh`,
   `test_aitask_create_xdeprepo_alone.sh`, `test_lock_force.sh`,
   `test_skill_render_uniform.sh`, `test_lock_diag.sh`, `test_skill_verify.sh`,
   `test_xdeps_validation.sh`, `test_skill_render.sh`, `test_skill_rerender.sh`
   (regenerate the list:
   `grep -lE '^[[:space:]]*assert_(nonzero_exit|zero_exit|exits_zero|exits_nonzero|exit_code)\(\)' tests/test_*.sh`).
   For each: source `asserts.sh`, drop the shared inline defs, and **rename the
   synonym call sites to the canonical lib names** (`assert_exit_zero` /
   `assert_exit_nonzero`). Check the synonym's signature matches the canonical
   one before renaming (esp. `assert_exit_code`, which may take an expected code
   argument — if its semantics differ from the canonical helpers, leave it
   inline rather than force-fit). Verify counts unchanged.

2. **`pass()`/`fail()`-style files** (3 files using `pass()`/`fail()` functions
   instead of the `PASS/FAIL/TOTAL` contract): migrate the shared assert helpers
   where signatures allow; if a file's counter model is fundamentally different,
   leave it inline and note why (consolidation must not change its behavior).

3. **Stragglers:** any remaining `tests/test_*.sh` still defining a consolidated
   helper inline (files that only define exit/file/dir helpers, no
   `assert_contains`, weren't caught by the flavor buckets). Migrate them with
   the standard recipe.

4. **Final verification gates (from the parent task t923):**
   - `grep -rnE 'assert_contains\(\)' tests/` shows the helper defined **once**
     (in `tests/lib/asserts.sh`), not ~70 times. (The `_ci`/`_re` variants are
     additional distinct names — acceptable; the gate is about `assert_contains()` itself.)
   - `shellcheck tests/lib/asserts.sh` and a sample of migrated files clean
     (modulo pre-existing info-level notes).
   - No remaining inline unguarded grep assert:
     `grep -rnE 'grep -q[a-zA-Z]* "\$' tests/ | grep -v ' -- '` → empty.
   - **Whole-suite parity:** run every `tests/test_*.sh` standalone before
     (baseline from main) vs after; pass/fail counts identical, accounting for
     the ~6 pre-existing batch cross-contamination failures noted in t920 (run
     individually for apples-to-apples).

## Verification

See the four gates above — all must pass.

## Notes for sibling tasks

This is the terminus. Record the final per-file count of inline helper
definitions remaining (should be only legitimately single-use/domain helpers),
and any synonym/pass-fail file deliberately left inline (with rationale).

## Step 9 (Post-Implementation): standard cleanup, archival, and merge per task-workflow.
