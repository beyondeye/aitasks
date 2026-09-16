---
Task: t1813_manual_verification_live_restore_suites.md
Base branch: main
Output branch: main
---

# t1813 — Manual verification of t1807 (auto-execution record)

Strategy: autonomous (profile `fast`, "Yes, autonomous"). Every item was run
inline, serially, from a shell OUTSIDE tmux (`TMUX` unset) with the dedicated
`-L ait` server stopped at the start of each run (verified before item 1 and
after items 1, 2 and 5: `no server running on /private/tmp/tmux-501/ait`).
Tree under test: `617c00f9a` (the t1807 commit). This file is the retroactive
record of what was actually run. Full logs live in this session's scratchpad
(`item1_run1.log`, `item1_run2.log`, `item2.log`, `item3.log`, `item4.log`,
`item5.log`) and are not committed.

## Execution Log

### Item 1
- Item text: From a terminal OUTSIDE tmux, with the -L ait server stopped: run `bash tests/test_restore_flows_live.sh` twice back to back; both runs report ALL TESTS PASSED and exit 0 (the first run is the cold-server case that flaked in t1806)
- Approach: CLI invocation
- Action run: `bash tests/test_restore_flows_live.sh` twice, back to back, `-L ait` confirmed down before the first (cold-server) run and still down after the second
- Output (trimmed): run 1 `Passed: 84 / 84`, `ALL TESTS PASSED`, exit 0; run 2 `Passed: 84 / 84`, `ALL TESTS PASSED`, exit 0
- Verdict: pass

### Item 2
- Item text: Guard control: `FROZEN_WAIT_TRIES=5 FAKE_AGENT_HOOK_DELAY=3 bash tests/test_restore_flows_live.sh` — every case logs `FAIL: make_frozen(...): no @aitask_record stamp ...` on stderr and stops at its `|| exit 1` guard, the footer reports SOME TESTS FAILED, and the suite exits non-zero
- Approach: CLI invocation plus static check of the emitter
- Action run: `FROZEN_WAIT_TRIES=5 FAKE_AGENT_HOOK_DELAY=3 bash tests/test_restore_flows_live.sh` (stdout+stderr captured); then `grep` of the suite for `make_frozen "` call sites and of `make_frozen_fail()` for the `>&2` redirect
- Output (trimmed): 15 lines `FAIL: make_frozen(agent-pick-17NN): no @aitask_record stamp on %N within the wait budget` (agent-pick-1705 … 1719), no other PASS/FAIL line, `Passed: 0 / 15`, `SOME TESTS FAILED (15)`, exit 1. The suite has 16 `make_frozen` call sites in 15 guarded `( … ) || exit 1` subshells; the 16th (agent-pick-1720) shares Case 13's subshell with 1719 and is never reached once the first guard exits — so 15 failures is exactly one per guarded block. `make_frozen_fail()` emits the line with `echo "FAIL: make_frozen($window): $reason" >&2`, so the line is on stderr.
- Verdict: pass

### Item 3
- Item text: Hook-delay stress: `FAKE_AGENT_HOOK_DELAY=1 bash tests/test_restore_flows_live.sh` — Case 1 (happy resume) passes and the suite exits 0; if another case fails, rerun it on the pre-t1807 tree before attributing it to this change
- Approach: CLI invocation
- Action run: `FAKE_AGENT_HOOK_DELAY=1 bash tests/test_restore_flows_live.sh`
- Output (trimmed): `=== Case 1 — happy resume: ack=hook, captures DELETED ===` present, zero `FAIL` lines, `Passed: 84 / 84`, `ALL TESTS PASSED`, exit 0. No other case failed, so the pre-t1807 rerun clause did not apply.
- Verdict: pass

### Item 4
- Item text: `bash tests/test_frozen_agents_acceptance.sh` passes (its wait_for_record_stamp now comes from tests/lib/frozen_fixtures.sh, with the 150-poll budget passed explicitly)
- Approach: CLI invocation plus static check
- Action run: `bash tests/test_frozen_agents_acceptance.sh`; `grep -n wait_for_record_stamp` across the suite and `tests/lib/frozen_fixtures.sh`
- Output (trimmed): zero `FAIL` lines, `Passed: 160 / 160`, `ALL TESTS PASSED`, exit 0. `wait_for_record_stamp()` is defined at `tests/lib/frozen_fixtures.sh:105` (`tries="${2:-$FROZEN_WAIT_TRIES}"`) and the acceptance suite calls it with an explicit `150` at lines 346 and 1158.
- Verdict: pass

### Item 5
- Item text: `bash tests/test_freeze_engine_live.sh` passes (tests/lib/frozen_fixtures.sh gained wait_for_record_stamp)
- Approach: CLI invocation
- Action run: `bash tests/test_freeze_engine_live.sh`
- Output (trimmed): zero `FAIL` lines, `Passed: 110 / 110`, `ALL TESTS PASSED`, exit 0. `-L ait` still down afterwards.
- Verdict: pass

## Cleanup

- No scratch directories were created outside the session scratchpad; the
  six `item*.log` captures there are session-private and need no removal.
- No tmux sessions or servers were created by this procedure directly; each
  suite tears down its own isolated socket. `/private/tmp/tmux-501/` holds
  only dead sockets from earlier test runs (every one answers
  `no server running`), untouched here.
