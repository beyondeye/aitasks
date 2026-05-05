---
Task: t732_7_verify_full_suite_zero_failures.md
Parent Task: aitasks/t732_fix_failing_pre_existing_test_suite.md
Archived Sibling Plans: aiplans/archived/p732/p732_1_cluster_a_textual_tui_api_drift.md, aiplans/archived/p732/p732_2_cluster_b_python_resolve_version_comparison.md, aiplans/archived/p732/p732_3_cluster_c_branch_mode_and_upgrade_commit.md, aiplans/archived/p732/p732_4_cluster_d_external_tool_drift.md, aiplans/archived/p732/p732_5_cluster_z_test_scaffold_missing_aitask_path.md, aiplans/archived/p732/p732_6_cluster_f_codemap_help_text.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-05 09:09
---

# p732_7 — Final verification (whole suite zero failures)

## Context

Trailing retrospective-eval child of t732. After all six cluster-fix siblings (t732_1..t732_6) have been archived, this task re-runs the full shell test suite end-to-end to confirm zero failures and to surface any regression introduced by the sibling fixes. Per the CLAUDE.md "Plan split: in-scope children, not deferred follow-ups" memory, multi-phase parent tasks default to a trailing whole-suite verification child rather than punting verification to a follow-up.

## Verified-against-current-state notes

- All six sibling tasks are archived under `aitasks/archived/t732/` (cluster A, B, C, D, Z, F). Confirmed via `ls aitasks/archived/t732/` and `git log --oneline --grep="t732"` showing landed cluster-fix commits.
- The shell test suite now has **114 tests** (`tests/test_*.sh`), up from 112 in the original Origin section. The driver loop globs `tests/test_*.sh`, so the count drift is automatically picked up.
- All dependencies (`depends: [732_1..732_6]`) are satisfied.
- The plan body (regression-handling protocol, CLAUDE.md update gate, success condition) is unchanged and remains the canonical reference.

## Goal

After all 6 cluster-fix siblings (t732_1..t732_6) are archived, re-run the full shell test suite, confirm 0 failures, and decide whether any new regressions warrant follow-up tasks or trivial inline fixes.

## Steps

1. Read `aitasks/t732/t732_7_verify_full_suite_zero_failures.md` for the full regression-handling protocol and CLAUDE.md update gate (already loaded into context).

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

3. **Success path** (`FAIL_T == 0`):
   - Document the driver-loop output in Final Implementation Notes.
   - Decide whether any of the cluster fixes surfaced a guardrail-worthy gotcha that justifies a CLAUDE.md update (per the gate in the task file). Default: no update unless a recurring portability/scaffolding pattern was discovered.
   - Proceed to Step 8 review and archival.

4. **Failure path** (`FAIL_T > 0`): triage each failure:
   - **Originally failing** (in t732 Origin) and one of the cluster fixes missed it: file follow-up or coordinate inline fix with sibling owner.
   - **Originally passing** (regression introduced by a cluster fix): `git bisect` against the merge commits of t732_1..t732_6 to identify the suspect sibling. **Default action: file a follow-up task with `/aitask-create`**, do NOT expand t732_7's scope to fix it. Trivial one-line inline fix is the only exception (only if needed to unblock parent t732 archival).
   - Per failure, document in Final Implementation Notes: (a) which sibling fix introduced it (or "pre-existing"), (b) follow-up task filed (link), (c) whether it was inline-fixed instead.

5. **CLAUDE.md update gate** (per the task body):
   - Update CLAUDE.md ONLY if a sibling fix surfaced a recurring portability/scaffolding gotcha that would re-trip future contributors without a guardrail.
   - Examples that would qualify: a Shell Conventions entry for a new portability gotcha (sed/grep/wc/mktemp/base64), a TUI Conventions entry for a Textual-version-pinning policy from Cluster A, an "Adding a new helper script" entry if Cluster Z's `tests/lib/test_scaffold.sh` should become a permanent test-authoring contract.
   - Do NOT add CLAUDE.md content for one-off fixes (e.g., a single help-text typo from Cluster F, a single model-config refresh from Cluster D).

6. Document the outcome in Final Implementation Notes (driver-loop output, follow-up tasks filed, CLAUDE.md decisions).

## Verification

- Driver loop prints `All green ✓` with `PASS: 114  FAIL: 0` (or however many tests `tests/test_*.sh` resolves to at run time — 114 as of verification).
- Final Implementation Notes documents every outcome (success or each remaining failure with its disposition).
- CLAUDE.md changes (if any) are minimal and address recurring gotchas, not one-offs.
- Upstream defects identified: any cross-cutting bugs surfaced during the suite run that are out of scope for the sibling fixes go in the canonical "Upstream defects identified" bullet for Step 8b follow-up offers.

## Step 9

Archive via `./.aitask-scripts/aitask_archive.sh 732_7`. The parent t732 will auto-archive once t732_7 archives (assuming the other six are already Done — they are).
