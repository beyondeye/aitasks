---
priority: medium
effort: medium
depends: [2167]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [2167]
assigned_to: dario-e@beyond-eye.com
anchor: 2167
followup_kind: manual_verification
created_at: 2026-10-30 11:35
updated_at: 2026-10-30 11:44
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t2167

## Verification Checklist

- [ ] macOS: `bash tests/test_merge_lock_concurrency.sh` Case 2 (N=51) — all 51 merges land, no leaked holder (no `HELD:` / `RETAINED`), and `status` reports `FREE` afterwards
- [ ] macOS: Cases 12 and 13 of the same suite pass — no `LOCK_UNAVAILABLE:guard_busy` cascade and no leftover holders
- [ ] macOS: `bash tests/test_merge_lock_broker.sh` passes in full, including Cases 19–23 (fixed-fd read-write FIFOs, `read -t` and fractional `sleep` under the Homebrew bash; the 30 s production cadence with the `bsdinfo` holder probe)
- [ ] macOS: Case 22/22c red control — in a scratch copy of the tree with both the unguarded pre-probe and the seam's instance gating removed in lib/merge_lock.sh, `finish` reports `RETAINED:release_failed`, so the regression still discriminates with the slower macOS probe
