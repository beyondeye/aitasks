---
Task: t923_5_synonyms_stragglers_and_final_gates.md
Parent Task: aitasks/t923_consolidate_test_assert_helpers_shared_lib.md
Sibling Tasks: aitasks/t923/t923_1_*.md, aitasks/t923/t923_2_*.md, aitasks/t923/t923_3_*.md, aitasks/t923/t923_4_*.md
Archived Sibling Plans: aiplans/archived/p923/p923_1_*.md, aiplans/archived/p923/p923_2_*.md, aiplans/archived/p923/p923_3_*.md, aiplans/archived/p923/p923_4_*.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-03 17:13
---

# Plan: Synonyms, stragglers, and final verification gates (t923_5)

Terminus child of t923. Depends on 923_1..923_4. **Read 923_1's archived plan
(`aiplans/archived/p923/p923_1_*.md`) for the lib API, migration recipe, and
harness usage.** This child cleans up the long tail and runs the whole-suite
verification gates from the parent task.

## Context

t920 added a `--` end-of-options guard to the `grep` in `assert_contains` /
`assert_not_contains` across the suite — in ~70 inline copies, because there
was no shared assert library. t923 consolidates those into `tests/lib/asserts.sh`.
Children 923_1..4 built the lib + verification harness (`assert_migration_verify.sh`)
and migrated the flavor-bucketed files (fixed / case-insensitive / regex). This
final child sweeps everything the buckets missed and proves whole-suite parity.

## Verify-pass findings (2026-06-03 — codebase re-checked against the plan)

The lib (`tests/lib/asserts.sh`) and harness (`tests/lib/assert_migration_verify.sh`)
exist as built by 923_1. Re-running the plan's discovery commands against the
current tree:

- **Step 1 — synonym files: 10, exact match to the plan's list.**
  `grep -lE '^[[:space:]]*assert_(nonzero_exit|zero_exit|exits_zero|exits_nonzero|exit_code)\(\)' tests/test_*.sh`
  → `test_aitask_update_xdeps`, `test_aitask_merge`,
  `test_aitask_create_xdeprepo_alone`, `test_lock_force`,
  `test_skill_render_uniform`, `test_lock_diag`, `test_skill_verify`,
  `test_xdeps_validation`, `test_skill_render`, `test_skill_rerender`.
  Synonyms in use: `assert_zero_exit`/`assert_exits_zero` → canonical
  `assert_exit_zero`; `assert_nonzero_exit`/`assert_exits_nonzero` → canonical
  `assert_exit_nonzero`. **`assert_exit_code` divergence CONFIRMED (plan warning
  is correct):**
  - `test_lock_diag` + `test_lock_force`: `assert_exit_code(desc, expected_code, cmd...)`
    — takes an **expected exit code** and runs a command. **Leave inline**
    (distinct domain helper; canonical helpers take no expected code).
  - `test_aitask_merge`: `assert_exit_code(desc, expected, actual)` — pure
    `[[ expected == actual ]]`, i.e. **`assert_eq`-equivalent**. May remap to
    `assert_eq` *or* leave inline. Default to leaving inline unless the harness
    confirms a clean count match — behavior-preservation over name-purity.

- **Step 2 — pass()/fail() files: 3, but Step 2 is effectively a no-op.**
  - `test_parallel_cross_repo_planning_procedure.sh` — **already sources
    `asserts.sh`** (comment + only `assert_file_contains` left inline as a domain
    helper); its `pass()/fail()` are domain wrappers. **No action.**
  - `test_agentcrew_error_recovery.sh`, `test_agentcrew_terminal_push.sh` — use
    `pass()/fail()` wrappers **directly** and define **no** consolidated assert
    helpers (they are absent from the straggler grep). Nothing to consolidate;
    **leave as-is**, rationale: different counter/wrapper model, no shared
    `assert_*` call sites to migrate.

- **Step 3 — stragglers: 20 files (the bulk of the work — larger and more
  heterogeneous than the plan's "long tail" wording implies).**
  `grep -lE '^[[:space:]]*(assert_eq|assert_contains|assert_not_contains|assert_exit_zero|assert_exit_nonzero|assert_file_exists|assert_file_not_exists|assert_dir_exists|assert_dir_not_exists)\(\)' tests/test_*.sh`
  → 20 files. **Correction to the plan's Step 3 characterization:** these are
  NOT all "only exit/file/dir helpers, no assert_contains". **10 of the 20 define
  `assert_contains` (some also `assert_not_contains`)** and are required to pass
  Gate 1. They escaped 923_2/3/4 because **several match substrings with bash
  glob (`[[ "$haystack" == *"$needle"* ]]`) instead of `grep -q*`** — a flavor
  the flavor-buckets never scanned for. Representative glob files:
  `test_multi_session_monitor`, `test_resolve_detected_agent`,
  `test_tui_switcher_footer_fit`, `test_verified_update_flags`. The remaining
  assert_contains stragglers use `grep -qF` (`test_opencode_setup`,
  `test_skill_render_aitask_pickn`, `test_skill_render_task_workflown`).
  - **Flavor → variant mapping:** `[[ "$h" == *"$n"* ]]` and `grep -qF` are both
    **literal substring** matches → remap to the **default `assert_contains`**
    (no `_ci`/`_re`). One semantic nuance: `[[ == ]]` is whole-string (not
    line-oriented) while the lib's `printf '%s' | grep -qF` is line-oriented — a
    needle spanning a `\n` would differ. None of these needles span newlines;
    the harness backstops any divergence.
  - The other 10 stragglers define only `assert_eq` (and a couple `assert_exit_*`),
    e.g. `test_create_silent_stdout`, `test_format_yaml_list`, `test_task_levels`,
    `test_xdeps_parser`, `test_tmux_exact_session_targeting`. Standard recipe;
    apply `assert_eq_trim` only where the inline `assert_eq` trimmed (none of
    these obviously do — verify per-file before remapping).

- **Gate 3 already clean:** `grep -rnE 'grep -q[a-zA-Z]* "\$' tests/ | grep -v ' -- '`
  → empty now. (Gate 1 currently shows the 10 inline `assert_contains` defs that
  Step 3 must remove.)

## Step 1 — Synonym exit-helper files (10)

For each: source `asserts.sh` (insert `. "$PROJECT_DIR/tests/lib/asserts.sh"`
right after the `PROJECT_DIR` source line — anchor on `PROJECT_DIR`, not the
scaffold, per 923_1), drop the shared inline defs, and **rename synonym call
sites to canonical names** (`assert_exit_zero` / `assert_exit_nonzero`). Handle
`assert_exit_code` per the verify-pass finding above (leave inline in
lock_diag/lock_force; merge's is assert_eq-equivalent — leave inline unless a
clean count match is confirmed). `snapshot` before, `check` after; FAIL count +
EXIT must be identical.

## Step 2 — pass()/fail() files (3)

No-op per verify-pass finding: one already migrated, two have no shareable
helpers. Confirm with the harness that all three still pass unchanged; record
the leave-inline rationale in Final Implementation Notes.

## Step 3 — Stragglers (20)

Migrate each with the standard 923_1 recipe (snapshot → insert source →
delete inline defs the lib provides → remap call sites to the matching variant →
keep file-local `PASS=0/FAIL=0/TOTAL=0` and single-use/domain helpers like
`assert_file_contains` / divergent `assert_exit_code` → check). For the 10
assert_contains stragglers, remap to **default `assert_contains`** (glob and
`-qF` are both literal). Audit any plain-`grep -q` (BRE) needles for ERE-only
metacharacters before choosing `_re` (none expected here). Migrate in batches;
each file runs standalone, so commit incrementally (matches sibling batching).

## Step 4 — Final verification gates (from parent t923)

1. `grep -rnE 'assert_contains\(\)' tests/` → defined **once** (in
   `tests/lib/asserts.sh`). `_ci`/`_re` are distinct acceptable names.
2. `shellcheck tests/lib/asserts.sh` and a sample of migrated files clean
   (modulo pre-existing info notes).
3. `grep -rnE 'grep -q[a-zA-Z]* "\$' tests/ | grep -v ' -- '` → empty.
4. **Whole-suite parity:** run every `tests/test_*.sh` standalone on `main`
   (baseline) vs the migrated tree; pass/fail counts identical, accounting for
   the ~6 pre-existing batch cross-contamination failures (run individually).
   Use the `assert_migration_verify.sh` harness for the full set, not just the
   touched files, to catch any incidental breakage.

## Risk

### Code-health risk: medium
- Wide blast radius — ~30 test files touched (10 synonym + 20 straggler).
  Each edit is mechanical and independently harness-verified, but the breadth
  itself is the principal code-health exposure. · severity: medium · →
  mitigation: in-task before/after harness (`assert_migration_verify.sh`),
  run per file (snapshot→check) and over the whole suite (Gate 4).
- Glob→grep semantic translation: the 4 `[[ "$h" == *"$n"* ]]` stragglers map
  to line-oriented `grep -qF`; a newline-spanning needle would differ. None
  observed, but it is a genuine behavior translation. · severity: low · →
  mitigation: per-file FAIL-count + EXIT parity check; needle audit before
  remap.
- `assert_exit_code` over-migration: force-fitting the lock_diag/lock_force
  expected-code variant onto canonical `assert_exit_*` would silently drop the
  expected-code comparison. · severity: medium · → mitigation: leave those
  inline (verify-pass decision); harness catches any count shift.

### Goal-achievement risk: low
- Goal is concrete and fully enumerated (exact file lists + four checkable
  gates), and the recipe is proven across 923_1..4. The only completeness
  question is whole-suite parity, which is itself Gate 4. · severity: low ·
  → mitigation: Gate 4 whole-suite harness run.

_No separate before/after mitigation tasks: the principal code-health risk is
mitigated in-task by the verification harness (this task's inherited
deliverable from 923_1), exactly as in the four prior children._

## Final Implementation Notes (fill in)

Final count of inline helper defs remaining (should be only legitimately
single-use/domain helpers — e.g. `assert_file_contains`, the expected-code
`assert_exit_code`, the agentcrew `pass/fail` wrappers); any synonym/pass-fail
file deliberately left inline (with rationale); whole-suite parity result.

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9. This is the last
child; its archival also archives the parent t923.
