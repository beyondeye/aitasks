# Test Execution Procedure

Discovers and runs tests, presents results, computes health score, and optionally
runs a verification gate. Referenced from Step 4 of the main SKILL.md workflow.

**Input:**
- Source-to-test mapping from Step 3 (available when `tier = s` or `tier = e`)
- `tier` — context variable: `q` (quick), `s` (standard), or `e` (exhaustive)
- `active_profile` — loaded execution profile (or null)

**Output:**
- Test pass/fail results
- Health score (when `tier = s` or `tier = e`)
- Verification evidence table (when `tier = e`)

---

## 4a: Discover test commands `[Tier: q, s, e]`

**Profile check:** If `qa_run_tests` is `false`:
- Display: "Profile '<name>': skipping test execution"
- Skip this entire step (4a-4e)

Read `aitasks/metadata/project_config.yaml` for:
- `test_command` — primary test runner
- `lint_command` — linter command

If neither configured, auto-detect from project structure:
- Look for `tests/test_*.sh` files (this project's pattern)
- Check for `pytest.ini`, `package.json` test scripts, `Makefile` test targets

## 4b: Run tests `[Tier: q, s, e]`

- If `test_command` configured: run it
- If individual test files found matching changed source: run those specifically
- If `lint_command` configured: run it against changed files

Collect pass/fail results.

## 4c: Present results `[Tier: q, s, e]`

Display test results summary:
```
Test Results:
  tests/test_foo.sh ........... PASS
  tests/test_bar.sh ........... FAIL (exit code 1)
  shellcheck aitask_baz.sh .... PASS
```

## 4d: Health Score `[Tier: s, e]`

**Skip when `tier = q`.**

After test execution, compute and display a QA health score based on four weighted
components.

**Scoring rubric:**
- **Lint (20% weight):** Start at 100. Deduct per issue: errors -10, warnings -5, info -2. Floor at 0. If no lint command configured, mark as N/A and redistribute weight proportionally among remaining components.
- **Tests (30% weight):** `(pass_count / total_count) * 100`. If no tests found or run, score 0.
- **Coverage (30% weight):** `(changed_source_files_with_tests / total_changed_source_files) * 100`. Uses the source-to-test mapping from Step 3.
- **Edge cases (20% weight):** Agent assessment on 0-100 scale based on test plan analysis — consider error paths, boundary conditions, platform edge cases (macOS/Linux).

**Display format:**
```
QA Health Score: XX/100
  Lint:       XX/100 (N issues)
  Tests:      XX/100 (N/M passed)
  Coverage:   XX/100 (N/M changed files have tests)
  Edge cases: XX/100 (brief assessment note)
```

If a component is N/A (e.g., no lint command), show "N/A" and redistribute its weight proportionally among the remaining components.

## 4e: Verification Gate `[Tier: e]`

**Skip when `tier = q` or `tier = s`.**

Before proceeding, verify all test claims with concrete evidence:

1. **Re-run all tests fresh** (not cached) — run the full test command again
2. **Read full output** and verify each result individually
3. **Build evidence table:**

| Claim | Evidence | Verified |
|-------|----------|----------|
| "All tests pass" | Test output: "12/12 passed, 0 failures" | Yes/No |
| "Lint clean" | Linter output: "0 errors, 0 warnings" | Yes/No |
| "No regressions" | All pre-existing tests still pass | Yes/No |

4. **Flag unverified claims:** If any claim cannot be backed by concrete output evidence, flag it explicitly before proceeding. Do not use words like "should", "probably", or "likely" for test outcomes — state what the evidence shows.
5. If any verification fails, report the discrepancy and ask the user how to proceed before continuing.
