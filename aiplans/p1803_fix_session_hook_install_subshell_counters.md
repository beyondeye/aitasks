---
Task: t1803_fix_session_hook_install_subshell_counters.md
Base branch: main
Output branch: main
---

# t1803 — Make test_session_hook_install.sh count its subshell groups

## Context

`tests/test_session_hook_install.sh` runs Groups A, B, C, C2 and D inside
`( … )` subshells but never opts into the file-backed counters from
`tests/lib/asserts.sh`. The shared helpers bump in-process `PASS`/`FAIL`/`TOTAL`,
which die at subshell exit, so those 17 assertions never reach the footer. The
file reports only Group 0 (7) + Group E (15) and exits 0 no matter what A–D do.

Measured baseline on HEAD `53542c976`: `Results: 22 passed, 0 failed, 22 total`,
rc=0, zero `FAIL:` lines printed — so A–D currently pass; they are just
unobserved.

Sweep result (the task's "consider sweeping"): a structural scan of every
`tests/*.sh` for `assert_*` calls inside standalone `(` … `)` blocks with no
`assert_counters_init` found **only this file** — both among `asserts.sh` users
and among files with inline counter helpers. No other file needs the fix.

Why the existing drift guard missed it: `tests/test_asserts_counters.sh` T12/T13
only detect the t1207 scaffolding (`_inc_pass`/`_inc_fail`, bare `COUNTER_FILE`),
not "asserts in a subshell without the opt-in". See `## Risk`.

Safety check done: `aitask_setup.sh --source-only` (sourced mid-file) and the
three libs it sources (`python_resolve.sh`, `github_release.sh`,
`data_symlinks.sh`) never assign `PASS`/`FAIL`/`TOTAL`, `AIT_ASSERT*`, `TMPDIR`,
nor install a trap — so the counter record survives the source.

## Implementation

Single file: `tests/test_session_hook_install.sh`. Pattern copied from the t1207
opted-in files (e.g. `tests/test_crew_init.sh:21-22`, footer `:252`).

1. **Opt in, right after sourcing asserts.sh** (after line 32):
   ```bash
   # Groups A–D assert inside ( … ) subshells, so the counts must be file-backed
   # or they die at subshell exit and the footer never sees them (t1207).
   assert_counters_init
   ```
2. **Fold the counter cleanup into the file's existing EXIT trap** (line 35). A
   second `trap … EXIT` would *replace* the TESTROOT cleanup, not add to it:
   ```bash
   trap 'rm -rf "$TESTROOT"; rm -f "$AIT_ASSERT_COUNTER_FILE"' EXIT
   ```
3. **Load the record in the footer, before the Results line** (so the printed
   totals are the real ones, and the existing `[[ "$FAIL" -eq 0 ]]` guard sees
   them). Called bare, per the `assert_counters_load` docblock:
   ```bash
   assert_counters_load
   echo ""
   echo "========================================="
   echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
   ```
4. Keep the existing `PASS=0 / FAIL=0 / TOTAL=0` block and its shellcheck
   comment (harmless — `assert_counters_init` re-zeroes them — and every t1207
   file kept them too).

## Verification

1. `bash tests/test_session_hook_install.sh` → `Results: 39 passed, 0 failed,
   39 total`, rc=0 (7 + 17 + 15 — the 17 A–D assertions now counted).
2. **Negative control, in an isolated mirror** (never mutate the shared tree):
   scratch dir `M` with symlinks `M/.aitask-scripts`, `M/seed`, `M/install.sh`,
   `M/tests/lib` → the real repo; copy the test into `M/tests/` and inject
   `assert_eq "NEGCTRL inside Group A" "x" "y"` inside the Group A subshell.
   - fixed file + injection → must exit **1** and report `1 failed`.
   - pre-fix control: `git show HEAD:tests/test_session_hook_install.sh` + the
     same injection → must exit **0** (proves the probe exercises the defect,
     so the red result above is attributable to the fix).
3. `shellcheck tests/test_session_hook_install.sh` — no new findings.
4. `bash tests/test_asserts_counters.sh` still passes (T12 unaffected).

## Post-implementation

Step 9: current-branch mode (fast profile) — no merge; archive via
`aitask_archive.sh 1803`.

## Risk

### Code-health risk: low
- Recurrence: the t1207 drift guard (`tests/test_asserts_counters.sh` T12/T13) only matches the old private-counter scaffolding, so a future test file that asserts inside `( … )` without the opt-in goes silently green again — exactly how this file slipped through · severity: medium · → mitigation: t1810

### Goal-achievement risk: low
None identified.

### Planned mitigations
- timing: after | name: subshell_optin_drift_guard | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: medium | addresses: Code-health recurrence — T12/T13 cannot see asserts-in-subshell-without-opt-in | desc: Add a drift guard to tests/test_asserts_counters.sh that fails when a tests/test_*.sh file sources asserts.sh, calls an assert_* helper inside a standalone ( … ) block, and never calls assert_counters_init — plus a negative-control test proving the guard can fire | created: t1810

## Final Implementation Notes
- **Actual work done:** Implemented as planned in `tests/test_session_hook_install.sh`: `assert_counters_init` right after sourcing `tests/lib/asserts.sh` (with a two-line why-comment), the counter-file cleanup folded into the file's existing `EXIT` trap, and `assert_counters_load` in the footer before the `Results` line (5 insertions, 1 modification). The file now reports 39 assertions instead of 22 — Groups A–D's 17 are counted.
- **Deviations from plan:** None.
- **Issues encountered:** The first shellcheck comparison showed an extra SC1091 on the fixed file. It was an artifact of running `shellcheck -x` from the repo root for the fixed file and from `tests/` for the HEAD copy (`# shellcheck source=` resolves relative to the working directory). Rerun from `tests/`, the fixed file has exactly the HEAD findings (pre-existing SC2016 at line 104 and SC2034 at line 217, shifted by 3).
- **Key decisions:** Opted into the file-backed counters rather than dropping the subshells — each group reassigns `DIR`/`SCRIPT_DIR`, so the subshell scoping is load-bearing isolation. Kept the file's own `PASS/FAIL/TOTAL` init block (re-zeroed by `assert_counters_init`; harmless, and matches the t1207 files). The negative control ran in an isolated scratch mirror (symlinks to `.aitask-scripts`, `seed`, `install.sh`, `tests/lib`), never in the shared tree: fixed file + injected failing assertion in Group A → rc=1, `39 passed, 1 failed, 40 total`; HEAD + the same injection → rc=0, `22 passed, 0 failed` with the `FAIL:` line printed. Sweep: a structural scan of every `tests/*.sh` (asserts.sh users and inline-helper files alike) found no other file asserting inside `( … )` without the opt-in. The recurrence risk — `tests/test_asserts_counters.sh` T12/T13 cannot see this shape — is carried by the planned "after" mitigation `subshell_optin_drift_guard`, not by an upstream-defect follow-up.
- **Upstream defects identified:** None
