---
priority: medium
effort: medium
depends: [1807]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1807]
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: manual_verification
created_at: 2026-09-16 09:17
updated_at: 2026-09-16 09:28
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1807

## Verification Checklist

- [ ] From a terminal OUTSIDE tmux, with the -L ait server stopped: run `bash tests/test_restore_flows_live.sh` twice back to back; both runs report ALL TESTS PASSED and exit 0 (the first run is the cold-server case that flaked in t1806)
- [ ] Guard control: `FROZEN_WAIT_TRIES=5 FAKE_AGENT_HOOK_DELAY=3 bash tests/test_restore_flows_live.sh` — every case logs `FAIL: make_frozen(...): no @aitask_record stamp ...` on stderr and stops at its `|| exit 1` guard, the footer reports SOME TESTS FAILED, and the suite exits non-zero
- [ ] Hook-delay stress: `FAKE_AGENT_HOOK_DELAY=1 bash tests/test_restore_flows_live.sh` — Case 1 (happy resume) passes and the suite exits 0; if another case fails, rerun it on the pre-t1807 tree before attributing it to this change
- [ ] `bash tests/test_frozen_agents_acceptance.sh` passes (its wait_for_record_stamp now comes from tests/lib/frozen_fixtures.sh, with the 150-poll budget passed explicitly)
- [ ] `bash tests/test_freeze_engine_live.sh` passes (tests/lib/frozen_fixtures.sh gained wait_for_record_stamp)
