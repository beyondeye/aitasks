# Test Execution Procedure

Discovers and runs tests, presents results, computes health score, and optionally
runs a verification gate. Referenced from Step 4 of the main workflow.

**Input:**
- Source-to-test mapping from Step 3 (available when `tier = s` or `tier = e`)
- `tier` — context variable: `q` (quick), `s` (standard), or `e` (exhaustive)

**Output:**
- Test pass/fail results
- Health score (when `tier = s` or `tier = e`)
- Verification evidence table (when `tier = e`)

---

## 4a: Discover test commands `[Tier: q, s, e]`

Read `aitasks/metadata/project_config.yaml` for:
- `test_command` — primary test runner
- `lint_command` — linter command

If neither configured, auto-detect from project structure:
- Look for `tests/test_*.sh` files (this project's pattern)
- Check for `pytest.ini`, `package.json` test scripts, `Makefile` test targets

## 4b: Run tests `[Tier: q, s, e]`

- If `test_command` is **configured**: run it through the shared helper —
  `./.aitask-scripts/aitask_run_project_command.sh test_command` — and keep the
  `VERDICT:` / `REASON:` / `DETAIL:` lines it prints.
- If `lint_command` is **configured**: run it the same way
  (`aitask_run_project_command.sh lint_command`).
- If individual test files were found matching changed source: run those
  specifically, directly. Same for any command **auto-detected** in 4a rather
  than configured — the helper only speaks `project_config.yaml` keys, and an
  auto-detected runner never opted into the exit contract.

The helper applies the project's `gate_command_exit_contract` opt-in, so a
configured command that exits with the documented did-not-run code reports
`VERDICT:skip` instead of a failure — exactly as the `tests_pass` / `lint` gate
verifiers report it. See `.claude/skills/task-workflow/build-verification.md`
for the branch rules and the copy-safe invocation block (exit `1` and `2` are
both normal, so the status must be captured in the `if`-form shown there); the
exit contract itself is documented once, in `run_project_command_key()`.

Collect pass / fail / **did-not-run** results.

## 4c: Present results `[Tier: q, s, e]`

Display test results summary. A command that reported `VERDICT:skip` gets its
own row form — it must be visible, not silently absent and not shown as a
failure:
```
Test Results:
  tests/test_foo.sh ........... PASS
  tests/test_bar.sh ........... FAIL (exit code 1)
  tools/run-tests.sh .......... SKIP (did not run — exit 2)
  shellcheck aitask_baz.sh .... PASS
```

## 4d: Health Score `[Tier: s, e]`

**Skip when `tier = q`.**

After test execution, compute and display a QA health score based on four weighted
components.

**Scoring rubric:**
- **Lint (20% weight):** Start at 100. Deduct per issue: errors -10, warnings -5, info -2. Floor at 0. If no lint command configured, mark as N/A and redistribute weight proportionally among remaining components.
- **Tests (30% weight):** `(pass_count / total_count) * 100` over **every test that actually executed** — the configured `test_command` *and* any individual test files 4b ran directly. If no tests were found at all, score 0: that is a real coverage gap.

  A configured command that reported `VERDICT:skip` **declared it did not run**, so it is neither a gap nor a failure — it contributes nothing to the numerator *or the denominator*. What that leaves depends on whether anything else ran:
  - **Other tests executed** (direct per-file runs): score the component from those results as usual. A direct test that **failed still fails and still counts** — a skipped configured runner must never redistribute a failure out of the score. Note the skipped runner beside the score so the reduced coverage is visible.
  - **Nothing else executed**: there is no test evidence at all — mark the component **N/A** and redistribute its weight, exactly like a missing `lint_command` below.

  Scoring a did-not-run as 0 is the same category error the gate path was fixed for; marking the component N/A while a real failure sits in the results table is the opposite error, and is worse.
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

If a component is N/A — no lint command configured, or a configured command reported it did not run **and nothing else executed for that component** — show "N/A" and redistribute its weight proportionally among the remaining components. A component with any executed result is never N/A.

## 4e: Verification Gate `[Tier: e]`

**Skip when `tier = q` or `tier = s`.**

Before proceeding, verify all test claims with concrete evidence:

1. **Re-run all tests fresh** (not cached) — run the full test command again,
   **through the same helper** a configured command used in 4b
   (`aitask_run_project_command.sh <key>`). This is a second execution site: run
   raw, a configured command's did-not-run exit is read as a plain failure here
   despite every SKIP / N/A rule above.
2. **Read full output** and verify each result individually
3. **Build evidence table:**

| Claim | Evidence | Verified |
|-------|----------|----------|
| "All tests pass" | Test output: "12/12 passed, 0 failures" | Yes/No |
| "Lint clean" | Linter output: "0 errors, 0 warnings" | Yes/No |
| "No regressions" | All pre-existing tests still pass | Yes/No |

4. **Flag unverified claims:** If any claim cannot be backed by concrete output evidence, flag it explicitly before proceeding. Do not use words like "should", "probably", or "likely" for test outcomes — state what the evidence shows.

   A `VERDICT:skip` on the fresh run belongs here: the configured runner did not run, so a claim resting on it is **unverified, not false**. Record `Verified: No` with the helper's `DETAIL:` text as the evidence cell. Never report it as a pass, and never report it as a failure — "could not check" is its own state.

   **A skipped configured runner does not blank the other evidence.** This step re-runs the configured command; it does not re-run the individual test files 4b executed directly. Any of those results still stands — re-run them too, and if one of them **fails**, that is a real failing claim and goes to step 5, whatever the configured runner reported. Scope the unverified row to the claim the skipped runner actually backed, not to the whole "no regressions" table.
5. If any verification fails, report the discrepancy and ask the user how to proceed before continuing. A fresh run that returns a **different** verdict from 4b is not a discrepancy: it is a genuinely fresh execution, and the lock or resource the command was waiting on may have cleared (or been taken) in between. Do not route that through this step.
