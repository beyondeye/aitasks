---
priority: medium
effort: low
depends: [t732_1, t732_2, t732_3, t732_4, t732_5, t732_6]
issue_type: test
status: Implementing
labels: [testing, verification]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-03 16:32
updated_at: 2026-05-05 09:12
---

## Context

Child 7 of t732. **Trailing retrospective-eval child.** Depends on all six cluster-fix siblings (t732_1..t732_6) being archived. Re-runs the full shell test suite to confirm zero failures and catches any new regressions introduced by the cluster fixes.

## Why this child exists

Per the CLAUDE.md "Plan split: in-scope children, not deferred follow-ups" memory: multi-phase parent tasks default to all phases as siblings + a trailing retrospective-eval child. For a triage parent that touches 13 tests across 6 cluster-fix children, a final whole-suite verification is needed to:

1. Confirm `for t in tests/test_*.sh; do bash "$t"` produces 0 failures.
2. Detect any **new** regressions surfaced by the cluster fixes (e.g., a test that previously passed but breaks because t732_5's scaffold helper changes setup behavior).
3. Decide whether any newly-discovered failure warrants a follow-up task (rather than expanding scope here).
4. Update CLAUDE.md only if a recurring portability/scaffolding gotcha was learned during the cluster fixes.

## Driver script (from t732 Origin section)

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

## Success condition

`FAIL_T == 0` on the host's clean Linux/CPython 3.14.3 environment.

## Regression-handling protocol

If a previously-passing test now fails:

1. Identify which sibling fix caused it (`git bisect` against the merge commits of t732_1..t732_6).
2. **Default action: spawn a follow-up task** — do NOT expand t732_7's scope to include the fix. This child's role is verification, not implementation.
3. Use `/aitask-create` to file the regression with reference to the suspect sibling.
4. Mark t732_7 as Done if the follow-up is filed; the freshly discovered regression lives in its own task.

The exception: a trivial one-line fix can be made inline if it would otherwise block the parent t732 archival. Document the inline fix in Final Implementation Notes.

## CLAUDE.md update gate

Update CLAUDE.md ONLY if a sibling fix surfaced a recurring portability/scaffolding gotcha that future contributors would re-introduce without the guardrail. Examples that would qualify:
- A new entry under "Shell Conventions" if a portability issue (sed/grep/wc/mktemp/base64) was the root cause of one of the cluster fixes.
- A new entry under "TUI (Textual) Conventions" if Cluster A surfaced a Textual-version-pinning policy.
- A new entry under "Adding a new helper script" if Cluster Z's `tests/lib/test_scaffold.sh` should be a permanent part of the test-authoring contract.

Do NOT add CLAUDE.md content for one-off fixes (e.g., a single help-text typo, a single model-config refresh).

## Verification

- The driver loop above prints `All green ✓`.
- If any failures remain, each is documented in the Final Implementation Notes with: (a) which sibling fix introduced it (or "pre-existing"), (b) follow-up task filed (link), (c) whether it was inline-fixed instead.
- CLAUDE.md is touched only if a guardrail-worthy gotcha was identified.
