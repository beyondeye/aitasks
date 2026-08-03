---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: []
gates: [risk_evaluated]
anchor: 635
created_at: 2026-08-03 10:59
updated_at: 2026-08-03 10:59
---

## Origin

Spawned from t1370 during Step 8b review. t1370 fixed this exact defect class in
`cleanup_locks()` in the same file; `list_locks()` was outside its scope.

## Upstream defect

- `.aitask-scripts/aitask_lock.sh:362` — `list_locks()` has the same
  `set -euo pipefail` abort that t1370 removed from `cleanup_locks()`:

  ```bash
  lock_files=$(git ls-tree "$current_tree_hash" | grep '_lock\.yaml' | awk '{print $4}')
  ```

  When the `aitask-locks` branch holds no lock files, `grep` exits 1, `pipefail`
  propagates it, and `set -e` kills the shell **before** the
  `if [[ -z "$lock_files" ]]` guard on the next line can print "No active locks"
  and return 0. So `ait lock --list` exits 1 with **no output** whenever nothing
  is locked — the ordinary state of most projects.

## Diagnostic context

Found while writing t1370's negative controls. A mutation that restored the
grep-based listing in `cleanup_locks()` was expected to fail the new
empty-branch test; when the search for the mutation site ran, it matched **two**
sites — line 362 (`list_locks`) and the one under repair. Line 362 is untouched
original code.

Verified end-to-end during t1370: on a repo whose lock branch exists but holds
no locks, the same pipeline shape returns exit 1 and prints nothing.

t1370 fixed its own site structurally (drop `grep`; `awk` exits 0 on no match)
rather than appending `|| true`, and additionally fixed a second instance of the
class in the same function (`tid=$(echo "$lf" | grep -oE '^t[0-9]+' | sed …)`,
which aborts the sweep on any stray non-`t<N>` file).

## Suggested fix

- Mirror t1370's structural fix rather than patching with `|| true`:
  ```bash
  lock_files=$(git ls-tree "$current_tree_hash" | awk '$4 ~ /_lock\.yaml$/ {print $4}')
  ```
- Add a test to `tests/test_task_lock.sh` asserting that `--list` on an
  initialized-but-empty lock branch exits 0 and prints its "No active locks"
  message. `setup_paired_repos` + `--init` is the fixture; the existing Test 13
  covers only the non-empty case, which is why this never surfaced.
- Prove the test discriminates by restoring the `grep` form and confirming it
  fails.
- Note: `cleanup_locks()`'s dispatcher entry is called **bare** on purpose so
  `set -e` stays live inside it (see t1370). Do not "fix" this by wrapping calls
  in `|| rc=$?` — that disables `set -e` for the whole function body and hides
  the very failures this class produces.

## Relation to the broader audit

t1370 also confirmed an `after` risk-mitigation task to audit `.aitask-scripts/`
for this pattern repo-wide. This task is the one confirmed instance; the audit
covers the rest.
