---
Task: t732_7_verify_full_suite_zero_failures.md
Parent Task: aitasks/t732_fix_failing_pre_existing_test_suite.md
Sibling Tasks: aitasks/t732/t732_*.md
Archived Sibling Plans: aiplans/archived/p732/p732_*.md
Worktree: (current branch — fast profile sets create_worktree:false)
Branch: (current branch)
Base branch: main
---

# p732_7 — Final verification (whole suite zero failures)

## Goal

After all 6 cluster-fix siblings (t732_1..t732_6) are archived, re-run the full shell test suite, confirm 0 failures, and decide whether any new regressions warrant follow-up tasks or trivial inline fixes.

## Prerequisites

This child has `depends: [732_1, 732_2, 732_3, 732_4, 732_5, 732_6]`. Do not pick it until all six siblings show `status: Done` in archive (the dependency check should enforce this automatically).

## Steps

1. Read `aitasks/t732/t732_7_verify_full_suite_zero_failures.md` for full context including the regression-handling protocol and CLAUDE.md update gate.
2. Run the driver loop:
   ```bash
   PASS_T=0; FAIL_T=0; FAILED_TESTS=()
   for t in tests/test_*.sh; do
     if bash "$t" >/dev/null 2>&1; then
       PASS_T=$((PASS_T + 1))
     else
       FAIL_T=$((FAIL_T + 1))
       FAILED_TESTS+=("$t")
     fi
   done
   echo "PASS: $PASS_T  FAIL: $FAIL_T"
   [[ $FAIL_T -eq 0 ]] && echo "All green ✓" || printf '  %s\n' "${FAILED_TESTS[@]}"
   ```
3. If `FAIL_T == 0`: success path. Skip to verification + archive.
4. If `FAIL_T > 0`: triage each failure:
   - Was the test originally failing in t732 ("Origin" section) and one of the cluster fixes missed it? File a follow-up task or coordinate inline fix with the relevant sibling owner.
   - Was the test originally passing (regression)? `git bisect` against t732_1..t732_6 merge commits. **Default action: file a follow-up task**, not inline fix (unless trivial one-liner needed to unblock parent t732 archival).
5. Decide CLAUDE.md updates per the gate in the child task body. Add only guardrail-worthy gotchas.
6. Document outcome in Final Implementation Notes (driver-loop output, follow-up tasks filed, CLAUDE.md decisions).

## Verification

- Driver loop prints `All green ✓`.
- Final Implementation Notes documents every outcome (success or each remaining failure with its disposition).
- CLAUDE.md changes (if any) are minimal and address recurring gotchas, not one-offs.

## Step 9

Archive via `./.aitask-scripts/aitask_archive.sh 732_7`. The parent t732 will auto-archive once t732_7 archives (assuming the other six are already Done).
