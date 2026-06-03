---
priority: low
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [testing, bash_scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-03 11:24
updated_at: 2026-06-03 11:44
---

## Context

Foundation child for t923 (consolidate duplicated bash assert helpers in the
test suite into one sourced lib). This child builds the shared library, a
before/after verification harness, and migrates a small pilot batch to prove
the pattern and the safety net. **No bulk migration here** — siblings 923_2..5
do that, each depending on this child.

Parent decision (locked at planning): the shared `assert_contains` /
`assert_not_contains` default to **fixed-string** (`grep -qF`, the plurality
flavor and the safest — no regex-metacharacter surprises). Two explicit
**named flavor variants** absorb the other two forms found in the suite:
`assert_contains_ci` / `assert_not_contains_ci` (case-insensitive) and
`assert_contains_re` / `assert_not_contains_re` (extended-regex). Migration in
later children maps each file's call sites to the variant matching that file's
**original inline flavor**.

## Background facts established during parent planning

- 168 `tests/test_*.sh` files; ~132 carry an inline helper block + `PASS`/`FAIL`/`TOTAL` counters.
- Big-3 helpers (`assert_eq`/`assert_contains`/`assert_not_contains`) have **uniform argument order** everywhere: `(desc, expected/needle, actual/haystack)`. Only internal var names differ → signature-safe to consolidate.
- `assert_contains` grep flavors across files: fixed `-qF` ~66, case-insensitive `-qi` ~33, regex (plain `-q` / `-qE`) ~27, plus 3 needing manual flavor inspection.
- Counter contract `PASS`/`FAIL`/`TOTAL` is near-universal (3 files use `pass()`/`fail()` funcs instead — handled in 923_5).
- Every file sources `tests/lib/test_scaffold.sh` at the top via the absolute `$PROJECT_DIR` path BEFORE any `cd`. A sibling `tests/lib/asserts.sh` sourced the same way is safe even in scaffolded fake-repo tests → **no `CLAUDE.md` scaffold-entry needed** (that rule governs runtime libs under `.aitask-scripts/lib/`, not test-only libs). `test_scaffold.sh` defines none of these helpers.
- The t920 fix added a `--` end-of-options guard to every `grep -q… -- "$needle"`. The shared lib MUST carry that guard.

## Key files

- **New: `tests/lib/asserts.sh`** — canonical helper definitions (functions only; counters stay file-local, referenced as globals `PASS`/`FAIL`/`TOTAL`). Must be BSD-safe (no GNU-only grep/sed; see `aidocs/framework/sed_macos_issues.md`). Guard against double-sourcing with `_AIT_ASSERTS_LOADED`.

  Provide:
  - `assert_eq(desc, expected, actual)`
  - `assert_contains(desc, needle, haystack)` — `grep -qF -- "$needle"` (fixed-string)
  - `assert_not_contains(desc, needle, haystack)` — fixed-string
  - `assert_contains_ci` / `assert_not_contains_ci` — `grep -qiF -- "$needle"` (fixed-string, case-insensitive)
  - `assert_contains_re` / `assert_not_contains_re` — `grep -qE -- "$needle"` (extended-regex, case-sensitive)
  - `assert_exit_zero(desc, cmd...)`, `assert_exit_nonzero(desc, cmd...)`
  - `assert_file_exists`, `assert_file_not_exists`, `assert_dir_exists`, `assert_dir_not_exists`
  - Match the existing FAIL-message wording closely (e.g. `FAIL: $desc (expected '$expected', got '$actual')`) so output diffs stay minimal.
  - **Scope boundary:** do NOT add the ~40 single-use domain helpers (`assert_yaml_valid`, `assert_env_detected`, `assert_symlink`, …). Those are not duplication; they stay inline in their one file. Synonym exit-helper names (`assert_nonzero_exit`, `assert_exits_zero`, …) are handled in 923_5.

- **New: `tests/lib/assert_migration_verify.sh`** — before/after verification harness. Given a list of test files, runs each individually (the suite has ~6 known batch cross-contamination failures per t920 — run files standalone for apples-to-apples) and records `<file> PASS=<n> FAIL=<n> TOTAL=<n>` (parse each test's own summary, or count `FAIL:` lines + exit status). Mode A: snapshot to a baseline file. Mode B: re-run and diff against baseline, exit nonzero on any count change. This is the safety net every migration child reuses. Keep it self-contained and BSD-safe.

- **~10 pilot files**: migrate a representative spread — pick ~4 fixed-string, ~3 case-insensitive, ~3 regex files (and at least one that also defines exit/file helpers). For each: snapshot baseline → replace the inline helper block with `. "$PROJECT_DIR/tests/lib/asserts.sh"` placed immediately after the existing `test_scaffold.sh` source → remap that file's `assert_contains`/`assert_not_contains` call sites to `_ci`/`_re` where the original inline flavor was case-insensitive/regex (audit needles: a literal needle with correct case is flavor-agnostic and can stay on the fixed-string default) → re-run verify, counts MUST be identical.

## Bucketing command (regenerate flavor lists; siblings reuse this)

```bash
for f in tests/test_*.sh; do
  g=$(awk '/^[[:space:]]*assert_contains\(\)/{infn=1} infn&&/grep/{print; infn=0; exit}' "$f")
  [[ -z "$g" ]] && continue
  # classify $g: -qi/-Fqi/-qiF => CI ; -qF/-F -q/-Fq => FIXED ; -qE or plain -q => REGEX
done
```

## Verification

- `shellcheck tests/lib/asserts.sh tests/lib/assert_migration_verify.sh` clean (modulo pre-existing info notes).
- The ~10 pilot files: standalone `bash tests/test_*.sh` pass/fail/total counts identical before vs after (via the harness).
- `assert_contains()` now defined in `tests/lib/asserts.sh`; pilot files no longer define it inline.

## Notes for sibling tasks (write comprehensive Final Implementation Notes!)

Record: the exact `asserts.sh` API + flavor-variant names as built, the verify-harness invocation, the precise block-removal/source-insertion recipe, any pilot file that needed a needle audit (and why), and any gotcha (e.g. a file with mixed flavors across `assert_contains` vs `assert_not_contains`). Siblings 923_2..5 depend entirely on these notes.

## Step 9 (Post-Implementation): standard cleanup, archival, and merge per task-workflow.
