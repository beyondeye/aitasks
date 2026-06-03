---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: [t923_3]
issue_type: refactor
status: Done
labels: [testing, bash_scripts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-03 11:27
updated_at: 2026-06-03 16:16
completed_at: 2026-06-03 16:16
---

## Context

Migration child for t923. Depends on 923_1/923_2/923_3. **Read 923_1's archived
plan for the lib API and recipe; read 923_3's notes for the needle-audit
pattern.**

This child migrates the **regex bucket**: files whose inline `assert_contains`
uses plain `grep -q` (case-sensitive **regex**) or `grep -qE`. These call sites
map to the shared **`assert_contains_re` / `assert_not_contains_re`** variants
(`grep -qE`) — UNLESS a needle audit shows the needle contains no regex
metacharacters (`. * [ ] ^ $ \ ( ) | + ?`), in which case the fixed-string
default is behavior-equivalent and may be left as-is.

## Scope

~27 files (plain `-q` / `-qE`) **plus 3 files needing manual flavor inspection**
(their `assert_contains` grep line was ambiguous to the auto-bucketer):
`test_add_model.sh`, `test_update_multiline_yaml.sh`, `test_yaml_utils.sh` —
open each, read its actual `assert_contains` body, and classify by hand before
migrating. Regenerate the regex-bucket list with 923_1's bucketing command.

## Recipe (per file, verified batches)

1. Snapshot baseline via `assert_migration_verify.sh`.
2. Source `tests/lib/asserts.sh`, delete shared inline defs, keep `PASS/FAIL/TOTAL`.
3. **Needle audit + remap:** for each `assert_contains`/`assert_not_contains` call:
   - Needle contains regex metacharacters used as regex → rename to `assert_contains_re` / `assert_not_contains_re`.
   - Needle is a plain literal (no metacharacters) → fixed-string default is equivalent; may stay on `assert_contains`. When unsure, use `_re` to preserve original semantics.
   - **Caution:** a literal needle like `t42.md` under the original plain `-q` was technically regex (`.` = any char) but almost always *intended* literally — fixed-string is actually MORE correct. Only keep `_re` when the pattern is a genuine regex (anchors, classes, alternation).
4. Re-run the harness; counts MUST be identical. A delta means a metacharacter mattered — switch that call to `_re` (or fix a latent test bug — note it).
5. Commit the batch (plain `git`).

## Verification

- Standalone counts identical before vs after for every migrated file.
- The 3 manual-inspection files correctly classified and migrated.
- No remaining inline regex `assert_contains` defs in migrated files.
- `shellcheck` clean on a sample.

## Notes for sibling tasks

Record the classification of the 3 manual files, any needle that was a genuine regex, and any latent test bug surfaced by the audit (→ "Upstream defects identified"). 923_5 does the final whole-suite verification gates.

## Step 9 (Post-Implementation): standard cleanup, archival, and merge per task-workflow.
