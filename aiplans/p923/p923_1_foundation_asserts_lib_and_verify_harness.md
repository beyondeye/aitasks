---
Task: t923_1_foundation_asserts_lib_and_verify_harness.md
Parent Task: aitasks/t923_consolidate_test_assert_helpers_shared_lib.md
Sibling Tasks: aitasks/t923/t923_2_migrate_fixed_string_files.md, aitasks/t923/t923_3_migrate_case_insensitive_files.md, aitasks/t923/t923_4_migrate_regex_files.md, aitasks/t923/t923_5_synonyms_stragglers_and_final_gates.md
Archived Sibling Plans: aiplans/archived/p923/p923_*_*.md
Base branch: main
---

# Plan: Foundation — shared asserts lib + verify harness + pilot (t923_1)

Foundation for the t923 consolidation. Builds the shared library, the
before/after verification harness, and migrates a ~10-file pilot. Siblings
923_2..5 depend on the API and recipe established here.

## Design decisions (locked at parent planning)

- `assert_contains` / `assert_not_contains` default to **fixed-string**
  (`grep -qF`). Explicit named variants `_ci` (case-insensitive, `grep -qiF`)
  and `_re` (extended-regex, `grep -qE`) absorb the other two flavors found in
  the suite. Later children remap each file's call sites to the variant
  matching that file's original inline flavor.
- Functions only; counters (`PASS`/`FAIL`/`TOTAL`) stay file-local and are
  referenced by the lib as globals.
- Scope: consolidate only the genuinely-duplicated **core** helpers. Single-use
  domain helpers stay inline. Synonym-named exit helpers handled in 923_5.

## Step 1 — Create `tests/lib/asserts.sh`

Draft (refine wording to match the dominant existing messages):

```bash
#!/usr/bin/env bash
# tests/lib/asserts.sh — shared assertion helpers for the test suite.
# Source AFTER tests/lib/test_scaffold.sh, via the absolute $PROJECT_DIR path.
# Functions mutate the caller's file-global PASS / FAIL / TOTAL counters.
# BSD-safe (no GNU-only grep/sed flags). See aidocs/framework/sed_macos_issues.md.

[[ -n "${_AIT_ASSERTS_LOADED:-}" ]] && return 0
_AIT_ASSERTS_LOADED=1

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

# --- substring / pattern containment ---------------------------------------
# Default: fixed-string (literal) match. Use _ci for case-insensitive,
# _re for extended-regex. All carry the t920 `--` end-of-options guard.

assert_contains() {
    local desc="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if printf '%s' "$haystack" | grep -qF -- "$needle"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$needle', got '$haystack')"
    fi
}

assert_not_contains() {
    local desc="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if printf '%s' "$haystack" | grep -qF -- "$needle"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output NOT containing '$needle', got '$haystack')"
    else
        PASS=$((PASS + 1))
    fi
}

assert_contains_ci()      { local d="$1" n="$2" h="$3"; TOTAL=$((TOTAL+1)); if printf '%s' "$h" | grep -qiF -- "$n"; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); echo "FAIL: $d (expected output containing (ci) '$n', got '$h')"; fi; }
assert_not_contains_ci()  { local d="$1" n="$2" h="$3"; TOTAL=$((TOTAL+1)); if printf '%s' "$h" | grep -qiF -- "$n"; then FAIL=$((FAIL+1)); echo "FAIL: $d (expected output NOT containing (ci) '$n', got '$h')"; else PASS=$((PASS+1)); fi; }
assert_contains_re()      { local d="$1" n="$2" h="$3"; TOTAL=$((TOTAL+1)); if printf '%s' "$h" | grep -qE -- "$n"; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); echo "FAIL: $d (expected output matching /$n/, got '$h')"; fi; }
assert_not_contains_re()  { local d="$1" n="$2" h="$3"; TOTAL=$((TOTAL+1)); if printf '%s' "$h" | grep -qE -- "$n"; then FAIL=$((FAIL+1)); echo "FAIL: $d (expected output NOT matching /$n/, got '$h')"; else PASS=$((PASS+1)); fi; }

# --- exit-code -------------------------------------------------------------
assert_exit_zero() {
    local desc="$1"; shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: $desc (command exited non-zero)"; fi
}

assert_exit_nonzero() {
    local desc="$1"; shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then FAIL=$((FAIL + 1)); echo "FAIL: $desc (expected non-zero exit, got 0)"; else PASS=$((PASS + 1)); fi
}

# --- filesystem ------------------------------------------------------------
assert_file_exists()     { local d="$1" p="$2"; TOTAL=$((TOTAL+1)); if [[ -f "$p" ]]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); echo "FAIL: $d (file not found: $p)"; fi; }
assert_file_not_exists() { local d="$1" p="$2"; TOTAL=$((TOTAL+1)); if [[ ! -f "$p" ]]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); echo "FAIL: $d (file unexpectedly exists: $p)"; fi; }
assert_dir_exists()      { local d="$1" p="$2"; TOTAL=$((TOTAL+1)); if [[ -d "$p" ]]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); echo "FAIL: $d (dir not found: $p)"; fi; }
assert_dir_not_exists()  { local d="$1" p="$2"; TOTAL=$((TOTAL+1)); if [[ ! -d "$p" ]]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); echo "FAIL: $d (dir unexpectedly exists: $p)"; fi; }
```

**IMPORTANT — match existing semantics, then verify empirically:** before
finalizing the FAIL-message wording and the exact `[[ -f ]]` / arg signatures,
diff against the real inline definitions of the pilot files. The existing
`assert_contains` used `echo "$actual" | grep …`; `printf '%s'` avoids `echo`
backslash/`-n` surprises but verify it does not change matching for needles
that relied on a trailing newline. If any pilot count shifts, reconcile the lib
to the real behavior (the lib must match what files rely on, not the other way).

## Step 2 — Create `tests/lib/assert_migration_verify.sh`

A before/after counts harness. Suggested interface:

```
assert_migration_verify.sh snapshot <baseline_file> <test_file>...   # Mode A
assert_migration_verify.sh check    <baseline_file> <test_file>...    # Mode B
```

- Runs each `<test_file>` standalone (`bash "$f"`), captures stdout, and parses
  the file's own `PASS=`/`FAIL=`/`TOTAL=` summary line (the suite prints a
  summary). If a file has no machine-parseable summary, fall back to counting
  `^FAIL:` lines and the process exit status.
- `snapshot` writes `relpath|PASS|FAIL|TOTAL` per file to the baseline.
- `check` re-runs and diffs against the baseline; prints any `CHANGED:<file> …`
  line and exits nonzero if any count differs.
- Self-contained, BSD-safe, `set -euo pipefail`, `#!/usr/bin/env bash`.
- Run files individually (NOT batched) to avoid the ~6 known cross-contamination
  failures noted in t920.

## Step 3 — Pilot migration (~10 files)

Pick a spread across flavors (regenerate buckets with the parent's bucketing
command). Suggested: ~4 fixed (`test_claim_id.sh` is a clean exemplar), ~3
case-insensitive, ~3 regex, including at least one that also defines exit/file
helpers.

Per file:
1. `snapshot` the file into a pilot baseline.
2. Insert `. "$PROJECT_DIR/tests/lib/asserts.sh"` right after the existing
   `. "$PROJECT_DIR/tests/lib/test_scaffold.sh"` line.
3. Delete the inline defs now provided by the lib; keep file-local
   `PASS=0/FAIL=0/TOTAL=0` and any single-use/domain helpers.
4. Remap call sites: `_ci` for case-insensitive files, `_re` for regex files
   (with needle audit — literal/correct-case needles can stay on the default).
5. `check` against the baseline — counts MUST match.

## Step 4 — Verify

- `shellcheck tests/lib/asserts.sh tests/lib/assert_migration_verify.sh` clean.
- All pilot files: counts identical before vs after.
- `grep -nE '^assert_contains\(\)' tests/lib/asserts.sh` → exactly one; pilot
  files no longer define it inline.

## Final Implementation Notes (fill in at completion — siblings depend on this)

Document the final lib API, the harness invocation, the exact
block-removal/source-insertion recipe, any pilot file needing a needle audit,
and any deviation from the draft above.

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9.
