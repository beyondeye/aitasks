---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: upstream_defect
created_at: 2026-10-20 12:35
updated_at: 2026-10-20 12:49
---

## Origin
Spawned from t1854_4 (M3.4 cost ledger) during Step 8b review.

## Upstream defect
- `goengines/internal/testmap/runner/invoke.go:200` — `provenance()` filters `.aitask-testmap/` out of `gitx.ModifiedPaths`, whose paths are relative to the git **top level**. With `aitestmap/` in a subdirectory (the engine's root = cwd ≠ the top level), the filter misses `sub/.aitask-testmap/...`. The record's `modified[]` is then top-level-relative while every other path the engine uses (ids, closure, covers, registry) is root-relative.

## Diagnostic context
- `git status --porcelain` always reports paths relative to the top level. The `gitx.ModifiedPaths` doc comment used to say "relative to Dir"; t1854_4 corrected the comment and added a read-only `gitx.Repo.Prefix` (`rev-parse --show-prefix`) with `TestPrefixAndTopLevelRelativeStatus`.
- M3.4's anchor eligibility fails closed on it: a non-empty prefix makes every dirty-tree result `eligibility-error:root-not-toplevel` (`TestEligibilityRootNotTopLevel`). So no false anchor is produced, but under a subdirectory registry no dirty-tree pass ever anchors, and the record's `modified` paths are misleading for any other consumer.

## Suggested fix
In `provenance()`, use `Prefix` either to keep only the paths under the prefix and strip the prefix (making `modified` root-relative), or to record the prefix and filter `<prefix>.aitask-testmap/`. Then decide whether M3.4's `root-not-toplevel` guard can be relaxed, with a red-proved test for a subdirectory registry. Paths outside the prefix still matter (a test can read them), so dropping them is not sound on its own.
