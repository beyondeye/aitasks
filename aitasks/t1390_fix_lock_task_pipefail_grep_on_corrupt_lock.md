---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: []
gates: [risk_evaluated]
anchor: 635
created_at: 2026-08-03 16:29
updated_at: 2026-08-03 16:29
boardidx: 18432
---

## Origin

Spawned from t1378 during Step 8b review. t1378 fixed this exact defect class in
`list_locks()` in the same file; `lock_task()` was outside its scope. t1370 fixed
it in `cleanup_locks()`. This is the last known unfixed instance in
`aitask_lock.sh`.

## Upstream defect

- `.aitask-scripts/aitask_lock.sh:162-165` — inside `lock_task()`'s "lock already
  exists" branch, three fields are extracted with unguarded `grep` pipelines:

  ```bash
  locked_by=$(echo "$lock_content" | grep '^locked_by:' | sed 's/locked_by: *//')
  locked_at=$(echo "$lock_content" | grep '^locked_at:' | sed 's/locked_at: *//')
  locked_hostname=$(echo "$lock_content" | grep '^hostname:' | sed 's/hostname: *//')
  ```

  Under the file's `set -euo pipefail`, a lock file missing any of those keys
  makes `grep` exit 1, `pipefail` propagates it, and `set -e` kills the script —
  so **acquiring a lock fails outright** when the *existing* lock file is corrupt
  or truncated.

## Diagnostic context

Found while implementing t1378, which fixed the same class twice in
`list_locks()` (the `git ls-tree | grep | awk` listing and the four
`echo | grep | sed` field extractions).

The omission looks accidental rather than deliberate: the **adjacent** lines
172-173 in the same branch already carry `|| true` guards for the PID-anchor
fields, with a comment explicitly naming the hazard ("`|| true` keeps pipefail
from killing the script"). Lines 162-165 sit immediately above and lack it.

Note line 166 already applies the `unknown` placeholder convention
(`[[ -z "$locked_hostname" ]] && locked_hostname="unknown"`) — that guard is
unreachable for a missing key today, because the pipeline aborts before it.

## Suggested fix

- Reuse the `_lock_field()` helper t1378 added above `list_locks()` (it is
  already file-scoped and returns empty + exit 0 on a missing key):
  ```bash
  locked_by=$(_lock_field locked_by "$lock_content")
  locked_at=$(_lock_field locked_at "$lock_content")
  locked_hostname=$(_lock_field hostname "$lock_content")
  ```
  Prefer this structural fix over appending `|| true`, matching how t1370 and
  t1378 resolved the other three instances.
- Consider whether lines 172-173's `|| true` guards should also migrate to
  `_lock_field` for consistency (they are already correct, so this is cleanup,
  not a fix).
- Add a test to `tests/test_task_lock.sh`: with a corrupt/truncated lock file
  already on the branch, a lock attempt by a *different* email must still report
  `LOCK_FAILED` cleanly rather than aborting. `setup_paired_repos` + the
  `plant_lock_blob` helper added by t1378 (Tests 13c/13d) is the fixture.
- Prove the test discriminates by restoring one `grep` form and confirming it
  fails.

## Relation to the broader audit

t1370 confirmed an `after` risk-mitigation task to audit `.aitask-scripts/`
repo-wide for this pattern. This is a confirmed instance in a file the audit
already covers; close it as merged if the audit lands first.
