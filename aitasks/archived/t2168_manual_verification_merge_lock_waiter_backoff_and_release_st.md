---
priority: medium
effort: medium
depends: [2167]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [2167]
assigned_to: dario-e@beyond-eye.com
anchor: 2167
followup_kind: manual_verification
created_at: 2026-10-30 11:35
updated_at: 2026-10-30 11:54
completed_at: 2026-10-30 11:54
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t2167

## Verification Checklist

- [x] macOS: `bash tests/test_merge_lock_concurrency.sh` Case 2 (N=51) — all 51 merges land, no leaked holder (no `HELD:` / `RETAINED`), and `status` reports `FREE` afterwards — PASS 2026-10-30 11:51 auto: macOS arm64, bash 5.3.9 @cfd671f97 - concurrency suite 30/30; Case 2 51/51 MERGE_OK + 51 merge commits, status FREE afterwards, 0 FAIL/HELD/RETAINED lines, suite 21s
- [x] macOS: Cases 12 and 13 of the same suite pass — no `LOCK_UNAVAILABLE:guard_busy` cascade and no leftover holders — PASS 2026-10-30 11:51 auto: same run - Cases 12 and 13 all asserts pass (HOLDER_CHANGED detected, new holder intact/RELEASED, guard released on TERM, force-release + MERGE_OK after); no guard_busy in output
- [x] macOS: `bash tests/test_merge_lock_broker.sh` passes in full, including Cases 19–23 (fixed-fd read-write FIFOs, `read -t` and fractional `sleep` under the Homebrew bash; the 30 s production cadence with the `bsdinfo` holder probe) — PASS 2026-10-30 11:52 auto: broker suite 135/135 in 39s under Homebrew bash 5.3.9; Cases 19-23 all pass (fixed fds 5-8 FIFOs, read -t rendezvous, Case 19 production 30 s cadence with seams off); host identity probe kind = bsdinfo
- [x] macOS: Case 22/22c red control — in a scratch copy of the tree with both the unguarded pre-probe and the seam's instance gating removed in lib/merge_lock.sh, `finish` reports `RETAINED:release_failed`, so the regression still discriminates with the slower macOS probe — PASS 2026-10-30 11:54 auto: scratch git-archive copy @cfd671f97 with pre-probe block + seam gating line removed; broker 129/135, finish -> RETAINED:release_failed in 22 and 22c, 22b guard held, waiter token P; no hang (57s), no leftovers
