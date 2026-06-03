---
priority: low
effort: medium
depends: [t923_2]
issue_type: refactor
status: Ready
labels: [testing, bash_scripts]
created_at: 2026-06-03 11:25
updated_at: 2026-06-03 11:25
---

## Context

Migration child for t923. Depends on 923_1 (lib + harness) and 923_2 (fixed
batch recipe). **Read 923_1's and 923_2's archived plans first.**

This child migrates the **case-insensitive (`grep -qi` / `grep -Fqi` /
`grep -qiF`) bucket**. These files' inline matching is case-insensitive, so
their `assert_contains` / `assert_not_contains` call sites map to the shared
**`assert_contains_ci` / `assert_not_contains_ci`** variants — UNLESS a needle
audit shows a given needle is flavor-agnostic (the needle's casing already
matches the asserted output verbatim), in which case the fixed-string default
is equivalent and may be left as-is.

## Scope

~33 files. Regenerate the exact list with 923_1's bucketing command (CI bucket).

## Recipe (per file, verified batches)

1. Snapshot baseline via `assert_migration_verify.sh`.
2. For each file: source `tests/lib/asserts.sh` (after the `test_scaffold.sh` source), delete the now-shared inline helper defs, keep file-local `PASS/FAIL/TOTAL`.
3. **Needle audit + remap:** for each `assert_contains`/`assert_not_contains` call in the file, decide:
   - If the needle could match with different casing than the actual output (i.e. the original `-qi` was load-bearing), rename the call to `assert_contains_ci` / `assert_not_contains_ci`.
   - If the needle's case already matches the output exactly, the fixed-string default is behavior-equivalent; leaving it on `assert_contains` is fine. When in doubt, use the `_ci` variant (it preserves the original behavior).
4. Re-run the harness; pass/fail/total counts MUST be identical. A count change usually means a needle's casing actually mattered — switch that call to `_ci`.
5. Commit the batch (plain `git`).

## Verification

- Standalone counts identical before vs after for every migrated file.
- No remaining inline `grep -qi` assert defs in migrated files.
- `shellcheck` clean on a sample.

## Notes for sibling tasks

Record which files genuinely needed `_ci` vs were flavor-agnostic, and any case where a needle audit revealed a latent test bug (a `-qi` that was masking a casing mismatch). Surface such findings in "Upstream defects identified".

## Step 9 (Post-Implementation): standard cleanup, archival, and merge per task-workflow.
