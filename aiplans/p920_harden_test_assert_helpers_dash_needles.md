---
Task: t920_harden_test_assert_helpers_dash_needles.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Harden test assert helpers against dash-prefixed needles (t920)

## Context

The per-file `assert_contains` / `assert_not_contains` helpers in `tests/`
implement their match with `echo "$actual" | grep -qi "$expected"` — **no `--`
end-of-options guard**. Any needle that begins with `-`/`--` is misparsed by
`grep` as an option rather than a search string:

- `assert_contains "... --print ..."` → `grep` errors out → **false FAIL**.
- `assert_not_contains "--print" ...` → `grep` errors out (non-zero) → the
  "not found" branch is taken → **false PASS** (silently masks a regression).

This was hit while adding Test 11e in t778 (`claudecode batch-review` gating
`--print` behind `--headless`); t778 worked around it by switching the test
needles to dash-free forms (`print` / `print review-me`). The helper itself
remains fragile, so the task is to fix the helpers uniformly and remove the
workaround.

The test suite has **no shared assert library** — each of ~70 test files
carries its own copy of these helpers. The task explicitly asks to "audit
other test files in `tests/` for the same unguarded-grep assert pattern and
fix uniformly."

## Scope (measured)

- **111 unguarded assert-grep lines across 70 files** in `tests/`.
- **91 lines are already guarded** (`grep -q… -- "$x"`) and must stay untouched.
- Flag variants present: `grep -q`, `grep -qi`, `grep -qF`, `grep -qE`.
  All four take a needle/pattern argument; the `--` guard is correct for every
  one (it only terminates option parsing — `-i`/`-F`/`-E` semantics, including
  regex interpretation under `-E`, are unaffected).

## Approach

Add a `--` end-of-options guard to every unguarded assert-grep call, uniformly.
This is the minimal fix that preserves existing `-i` (case-insensitive),
`-F` (fixed-string), and `-E` (regex) behavior exactly — unlike a pure-bash
`[[ == *…* ]]` substring test, which would silently drop case-insensitivity and
regex support that many helpers rely on.

### Step 1 — Mechanical guard insertion across `tests/`

Transform `grep -q<flags> "$VAR"` → `grep -q<flags> -- "$VAR"` for the 111
unguarded lines. Dry-run already confirmed this regex hits **exactly 111 lines**,
introduces **no double-guards**, and leaves the 91 already-guarded lines alone:

```bash
for f in $(grep -rlE 'grep -q[a-zA-Z]* "\$' tests/); do
  sed -E -i 's/grep -q([iFEx]*) "(\$[A-Za-z_][A-Za-z0-9_]*)"/grep -q\1 -- "\2"/g' "$f"
done
```

(Run on this Linux/GNU-sed dev box as a one-off shell operation — this is not a
`sed -i` call being committed into a framework script, so the `sed_inplace()`
convention does not apply. Result is verified by grep afterward, not trusted
blindly.)

Representative affected files (pattern repeats identically in all 70):
`tests/test_codeagent.sh`, `tests/test_claim_id.sh`, `tests/test_sync.sh`,
`tests/test_web_merge.sh`, `tests/test_query.sh`, `tests/test_crew_*.sh`,
`tests/test_archive_*.sh`, `tests/test_fold_*.sh`, …

### Step 2 — Remove the t778 workaround + add it back as a regression assertion

In `tests/test_codeagent.sh` Test 11e (lines 258–268), the needles were
deliberately made dash-free to dodge this very bug. Now that the helper is
guarded, restore the real flag-string needles so the test actually asserts on
`--print` (this doubles as the regression test that the fix works):

- Line 261–262 comment (`# Note: needles avoid a leading "--" …`): delete it
  (the helper now handles `--` needles).
- Line 264: `assert_not_contains "... (no --print)" "print" "$output"`
  → needle `"--print"`.
- Line 268: `assert_contains "... adds --print" "print review-me" "$output"`
  → needle `"--print review-me"`.

This makes Test 11e a live exercise of a `--`-prefixed needle through both
`assert_contains` and `assert_not_contains`.

## Verification

1. **No unguarded assert-grep remains:**
   ```bash
   grep -rnE 'grep -q[a-zA-Z]* "\$' tests/ | grep -v ' -- '   # expect: no output
   ```
2. **No accidental double-guards:**
   ```bash
   grep -rnE 'grep -q[a-zA-Z]* -- -- ' tests/                 # expect: no output
   ```
3. **Run the directly-affected test (now exercises `--print` needles):**
   ```bash
   bash tests/test_codeagent.sh        # Test 11e must PASS with --print needles
   ```
4. **Run a representative spread of other touched suites** to confirm the guard
   did not change any passing assertion:
   ```bash
   bash tests/test_claim_id.sh
   bash tests/test_query.sh
   bash tests/test_fold_mark.sh
   bash tests/test_web_merge.sh
   ```
5. **shellcheck** a couple of edited files:
   ```bash
   shellcheck tests/test_codeagent.sh tests/test_query.sh
   ```

## Step 9 (Post-Implementation)

Single-task, current-branch: no worktree/branch cleanup. Proceed to archival via
`./.aitask-scripts/aitask_archive.sh 920` after review/commit, then push.

## Risk

### Code-health risk: low
- Uniform, idempotent `--` guard insertion confined entirely to test-helper
  functions; no production/runtime code touched. Existing needles never start
  with `-`, so every currently-passing assertion behaves identically. Blast
  radius is wide in file-count (70 files) but each change is the same one-token
  insertion, machine-verified (111 lines changed, 0 double-guards, 91 guarded
  lines untouched). · severity: low · → mitigation: none
- No shared helper exists to fix in one place; per-file duplication is
  pre-existing and out of scope (a shared assert-lib refactor would touch the
  source-on-startup chain + test_scaffold and is a much larger change). Noting
  as a possible future follow-up, not mitigating now. · severity: low
  · → mitigation: none

### Goal-achievement risk: low
- Fix targets the documented root cause directly and is confirmed by restoring
  the t778 dash-free workaround to real `--print` needles as a live regression
  assertion. · severity: low · → mitigation: none
