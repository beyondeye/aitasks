---
priority: low
effort: high
depends: []
issue_type: refactor
status: Implementing
labels: [testing, bash_scripts]
children_to_implement: [t923_1, t923_2, t923_3, t923_4, t923_5]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-03 10:51
updated_at: 2026-06-03 11:27
---

## Context

Follow-up to t920 (archived), which added a `--` end-of-options guard to the
unguarded `grep` in the `assert_contains` / `assert_not_contains` (and
assert-file) helpers across the test suite. The fix had to be applied to
**~70 separate copies** of those helpers because the test suite has **no shared
assert library** — every `tests/test_*.sh` file defines its own inline
`assert_eq` / `assert_contains` / `assert_not_contains` / `assert_exit_*`
helpers. This duplication is why a one-line correctness fix touched 70 files,
and it means the next helper bug (or improvement) will again require a
70-file sweep.

This task consolidates those duplicated helpers into one sourced library so
future changes happen in a single place.

## Goal

Extract the per-file bash assert helpers into a shared `tests/lib/asserts.sh`
(co-located with the existing `tests/lib/test_scaffold.sh`), and have each test
file source it instead of redefining the helpers inline.

## Key files

- **New:** `tests/lib/asserts.sh` — the canonical helper definitions
  (`assert_eq`, `assert_contains`, `assert_not_contains`, `assert_exit_zero`,
  `assert_exit_nonzero`, and the assert-file variants). Must keep the
  `PASS`/`FAIL`/`TOTAL` counter contract the existing helpers use, and the
  guarded `grep -q… -- "$needle"` form from t920.
- **~70 files:** `tests/test_*.sh` — replace the inline helper block with a
  `source`/`.` of `tests/lib/asserts.sh` (path resolved the same way each file
  already resolves `tests/lib/test_scaffold.sh`, via `$SCRIPT_DIR`/`$PROJECT_DIR`).

## Notable cleanliness / blast-radius considerations (read before implementing)

- **Helper drift:** the 70 copies are *not* guaranteed identical. Before
  collapsing them, diff the variants (counter names, output wording, extra
  asserts some files define, e.g. `assert_exit_*`, `assert_file_contains`,
  `assert_match`/`grep -qE` regex variants). The shared lib must be a superset
  that preserves every behavior currently relied on, or per-file failures will
  surface only at runtime. Enumerate the distinct helper "shapes" first.
- **Counter scoping:** the inline helpers mutate file-global `PASS`/`FAIL`/`TOTAL`.
  A sourced function mutating caller globals works in bash, but confirm no test
  file uses a different counter name or a `local` that would shadow it.
- **Startup-chain rule does NOT apply here, but verify:** the CLAUDE.md rule
  ("libs added to `./ait`'s source-on-startup chain must also be added to
  `test_scaffold.sh::setup_fake_aitask_repo()`") governs **runtime** libs under
  `.aitask-scripts/lib/`. A *test-only* lib under `tests/lib/` is sourced by the
  real test file (not inside the fake scaffolded repo), so it should not need a
  scaffold entry — but confirm no test sources asserts.sh *after* `cd`-ing into a
  scaffolded fake repo where the relative path would break.
- **macOS portability:** keep `grep`/`sed` usage in the shared lib BSD-safe
  (see `aidocs/framework/sed_macos_issues.md`); the lib will run on every
  contributor's machine.
- **Incremental migration is safe:** files can be converted in batches (each
  still runs standalone), so this need not be one atomic 70-file commit.

## Verification

- Run the full `tests/test_*.sh` suite before and after; pass/fail counts must be
  identical (account for the ~6 pre-existing batch cross-contamination failures
  noted in t920 — run suites individually for an apples-to-apples comparison).
- `grep -rnE 'assert_contains\(\)' tests/` should show the helper defined **once**
  (in `tests/lib/asserts.sh`), not ~70 times.
- `shellcheck tests/lib/asserts.sh` and a sample of migrated test files clean
  (modulo pre-existing info-level notes).
- Confirm no remaining inline `grep -q…` assert without the `--` guard:
  `grep -rnE 'grep -q[a-zA-Z]* "\$' tests/ | grep -v ' -- '` → empty.
