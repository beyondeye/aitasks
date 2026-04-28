---
priority: low
effort: low
depends: []
issue_type: test
status: Implementing
labels: [testing]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-27 17:25
updated_at: 2026-04-28 15:41
boardidx: 40
---

The macOS audit (t658) baseline run surfaced two tests whose assertions are pinned to values that have since drifted from production behavior.

## Failure 1: test_brainstorm_cli — stale `status: init` assertion

`tests/test_brainstorm_cli.sh:201`:
```bash
status=$(grep '^status:' "$WT/br_session.yaml" | sed 's/^status: *//')
assert_eq "session status is init" "init" "$status"
```

But `aitask_brainstorm_init.sh` (via `.aitask-scripts/brainstorm/brainstorm_session.py:153`) now writes `status: init` then immediately transitions to `status: active` after creating the root node. The assertion is reading post-init state, so the right expectation is `active`. This is a stale test contract — production behavior changed (likely as part of the t573 / t579 work) and the test wasn't updated.

The other 30 assertions in this test all pass.

## Failure 2: test_verified_update_flags — hardcoded model string

`tests/test_verified_update_flags.sh`:
```
FAIL: agent/cli-id resolves to UPDATED
  expected to contain: UPDATED:claudecode/opus4_6:test_414_flags:
  actual: UPDATED:claudecode/opus4_7_1m:test_414_flags:100
```

The test passes `--cli-id` resolving to whatever the current Claude Code default is (`opus4_7_1m` on this host). The assertion is hardcoded to `claudecode/opus4_6` from when the test was written. The test logic is correct but the assertion is timeline-dependent.

## Suggested approach

- **test_brainstorm_cli:** Update line 201 to assert `active` (or, if the test still wants to verify the early-init contract, hook before the active-transition). The simpler fix is to update the expected value.
- **test_verified_update_flags:** Either pass an explicit, version-pinned `--cli-id` to the test (so the agent string is deterministic) or compute the expected agent string at runtime via `aitask_resolve_detected_agent.sh --agent claudecode --cli-id "<the_test's_input>"` and assert against that.

## Verification

After the fix, both tests pass on macOS. The t658 baseline showed every other assertion in these files already passing; only these two regressions remain.
