---
Task: t1079_harden_task_id_assignment_against_counter_drift.md
Worktree: .
Branch: current
Base branch: main
---

# t1079 - Harden Task ID Assignment With Hot-Path Active Scans

## Summary

Normal task creation should not scan archived task history. The hot path repairs
counter drift only against active task files, while explicit repair paths
(`--resync` and `ait setup`) scan active and archived history to fully repair
the shared counter.

## Implementation Plan

1. Split counter scanning in `.aitask-scripts/aitask_claim_id.sh`.
   - Add an active-only scan for normal `--claim`.
   - Keep the existing active+archived `scan_max_task_id` path for `--init` and
     the new explicit repair path.

2. Change normal ID claims.
   - Remote CAS and local-only claims should hand out
     `max(counter_value, active_max + 1)`.
   - The counter should advance to the claimed ID plus one.
   - Normal claims must not inspect `aitasks/archived` or archive tarballs.

3. Add explicit repair.
   - Add `aitask_claim_id.sh --resync`.
   - Remote mode should fetch the counter branch, compute `full_max + 1`, and
     CAS-push a repair commit only if the counter is behind.
   - Local mode should initialize or update the local counter branch to the same
     full-history target.

4. Harden parent task creation.
   - Add one shared parent-ID claim helper in `.aitask-scripts/aitask_create.sh`.
   - Use it from parent draft finalization and `--batch --commit`.
   - Retry only when the claimed ID already exists as an active parent task.
   - Do not call archived lookup helpers from task creation.

5. Wire setup repair.
   - In `.aitask-scripts/aitask_setup.sh`, when `aitask-ids` already exists,
     run `aitask_claim_id.sh --resync` best-effort.
   - Keep fresh initialization behavior unchanged.

## Verification

- `bash -n .aitask-scripts/aitask_claim_id.sh .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_setup.sh tests/test_claim_id.sh tests/test_draft_finalize.sh tests/test_create_silent_stdout.sh tests/test_setup_git.sh`
- `bash tests/test_claim_id.sh`
- `bash tests/test_draft_finalize.sh`
- `bash tests/test_create_silent_stdout.sh`
- `bash tests/test_setup_git.sh`

## Risk

### Code-health risk: medium

- This touches central task creation and setup paths, where regressions can
  block task creation across repos. Mitigated with focused regression coverage
  for remote claims, local claims, setup resync, draft finalization, and silent
  direct creation.

### Goal-achievement risk: low

- The desired performance/correctness split is explicit and is reflected in the
  tests: normal claims and create guards cover active drift only; setup/resync
  cover archived drift repair.

## Final Implementation Notes

- **Actual work done:** Added active-only hot-path self-healing for normal
  claims, explicit full-history `--resync`, setup-time resync for existing
  counters, and active-parent-only retry guards in parent task creation.
- **Deviations from plan:** None.
- **Issues encountered:** None beyond normal fixture wiring for deterministic
  counter drift tests.
- **Key decisions:** Normal `--claim` and `aitask_create.sh` never inspect
  archived task history; archived-only drift is accepted until setup/resync is
  run.
- **Upstream defects identified:** None
