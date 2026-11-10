---
priority: low
effort: medium
depends: []
issue_type: performance
status: Ready
labels: [release_scripts, bash_scripts]
anchor: 2261
created_at: 2026-11-10 16:17
updated_at: 2026-11-10 16:17
---

## Context

Follow-up of t2261_2 (release-notify consumer), from its review. A separable
performance item, not a missing functional requirement.

`ril_list_residue` (`.aitask-scripts/lib/release_issue_ledger.sh`) runs on every
`ait release-notify` invocation, including runs with no pending work. For EVERY
historical record under `aitasks/metadata/release_issues/released/<tag>/` it calls
`_ril_hit_state` (a `rev-parse HEAD:<path>` plus a `status --porcelain`) and a
separate `rev-parse HEAD:<pending twin>` lookup: at least three git processes per
clean record. The released history only grows, so the residue scan's cost grows
with every release.

## What to do

Batch the queries so detection costs O(1) git calls, not O(records):

- one `status --porcelain --untracked-files=all -z -- <root>/released <root>/pending`
  gives every untracked / staged / modified / deleted path at once;
- one `ls-tree -r --name-only HEAD -- <root>/pending` gives every pending path
  HEAD holds (to find a released copy whose pending twin is still in HEAD);
- derive the same two outputs as today (`released:<path>`, `unpaired:<path>`)
  from those listings. Every git rc stays checked: a failed listing must still
  make `ril_list_residue` return non-zero (unknown), never an empty "no residue".

`ril_resume_move` itself keeps its per-record checks (it runs only for residue).

## Verification

- `bash tests/test_release_notify.sh` (cases (p), (q) cover every residue shape)
  and `bash tests/test_release_notify_branch_mode.sh` (case 6) still pass.
- Add a case with many committed released records and no residue, asserting
  the scan's git-call count stays constant (a counting `git` shim), and a
  control where the status listing fails -> `RESIDUE:-|scan_failed`.
