---
Task: t1806_run_live_restore_suites_outside_tmux.md
Base branch: main
Output branch: main
---

# t1806 — Manual verification of t1802 (auto-execution record)

Strategy: autonomous (profile `fast`, "Yes, autonomous"). Every item was run
inline from a shell OUTSIDE tmux (`TMUX` unset) with the dedicated `-L ait`
server stopped at the start (verified: `no server running on
/private/tmp/tmux-501/ait`). This file is the retroactive record of what was
actually run. Full logs live in this session's scratchpad
(`item1_acceptance.log`, `item2_restore_flows.log`,
`item2_restore_flows_run2.log`, `item3_acceptance_prefix.log`,
`item3_restore_flows_prefix.log`, `repro_case1_race.sh`) and are not committed.

## Execution Log

### Item 1
- Item text: From a terminal NOT inside tmux, with the `-L ait` server stopped, `bash tests/test_frozen_agents_acceptance.sh` passes, including the t1802 assertions in Cases 5 and 6c.
- Approach: CLI invocation.
- Action run: `bash tests/test_frozen_agents_acceptance.sh`
- Output (trimmed):
  ```
  === Case 5 — the happy restore: ack=hook, captures deleted, join intact ===
  === Case 6c — tmux restarted; only an UNRELATED session exists ===
  === Summary ===
  Passed: 160 / 160
  ALL TESTS PASSED
  ```
  Passing assertions print nothing, so the t1802 assertions are proven live
  by the pre-fix control in item 3, where exactly those lines fail.
- Verdict: pass

### Item 2
- Item text: In the same terminal, `bash tests/test_restore_flows_live.sh` passes, including the t1802 assertions in Case 1 (resume) and Case 2 (re-pick).
- Approach: CLI invocation, run twice.
- Action run: `bash tests/test_restore_flows_live.sh` (run 1, cold server), then again (run 2).
- Output (trimmed), run 1:
  ```
  FAIL: case 1: restore exits 0 (expected '0', got '1')
  FAIL: case 1: reports a HOOK-verified restore (expected output containing 'RESTORED:48176214|hook', got 'RESTORE_FAILED:48176214|no_session')
  FAIL: case 1: the replacement got AITASK_AGENT_STRING from the coordinator (expected 'claudecode/opus5', got '')
  ... (5 more case 1 lines, all downstream of the preflight failure)
  Passed: 76 / 84
  ```
  Run 2:
  ```
  Passed: 84 / 84
  ALL TESTS PASSED
  ```
- Diagnosis: the run 1 failure is at restore PREFLIGHT (`no_session`), before
  any t1802 code runs. Root cause reproduced deterministically with the
  suite's own fixtures and `FAKE_AGENT_HOOK_DELAY=3`: `make_frozen` upserts
  `--session-id sess-orig` but never stamps `@aitask_record`; when the freeze
  runs before the hook has stamped the pane (a cold first launch), the freeze
  engine's fallback upsert selects the record by pane and writes
  `--session-id ""`, which the store takes as a value. The agent string
  survives (the t1802 guard) while the session id is blanked. Filed as
  t1807 (product: same class as t1802 for `codeagent_session_id`; fixture:
  wait for the stamp before freezing).
- Verdict: pass (t1802 assertions hold; the flake is pre-existing and filed)

### Item 3
- Item text: Pre-fix control — with the `.aitask-scripts/lib/agent_restore.py` part of 85ed142f6 temporarily reverted, re-run both suites and confirm the `AITASK_AGENT_STRING` environment assertions FAIL; record assertions may still pass. Then restore the change.
- Approach: CLI invocation.
- Action run:
  ```
  git show 85ed142f6 -- .aitask-scripts/lib/agent_restore.py > t1802_agent_restore.patch
  git apply -R t1802_agent_restore.patch      # 3 insertions, 21 deletions
  bash tests/test_frozen_agents_acceptance.sh
  bash tests/test_restore_flows_live.sh
  git checkout -- .aitask-scripts/lib/agent_restore.py
  ```
- Output (trimmed), acceptance:
  ```
  FAIL: case 5: the replacement got AITASK_AGENT_STRING from the coordinator (expected 'claudecode/opus5', got '')
  FAIL: case 6c: the new-window replacement got AITASK_AGENT_STRING (expected 'claudecode/opus5', got '')
  Passed: 158 / 160
  ```
  restore-flows:
  ```
  FAIL: case 1: the replacement got AITASK_AGENT_STRING from the coordinator (expected 'claudecode/opus5', got '')
  FAIL: case 2: the re-picked agent got AITASK_AGENT_STRING from the coordinator (expected 'claudecode/opus5', got '')
  Passed: 82 / 84
  ```
  Exactly the four environment assertions fail; every record assertion
  (`agent_string` / `agent_kind` survive) still passes on the store guard
  alone, as the checklist predicted. `git status` clean after the checkout.
- Verdict: pass

## Cleanup

- `aiplans/…` and `aitasks/…`: only this plan file and the t1806 checklist were written; t1807 was created via `ait create`.
- Reverted patch restored with `git checkout -- .aitask-scripts/lib/agent_restore.py`; working tree clean.
- Each suite tears down its own isolated `-L ait` server and fixture dir; the reproduction script uses the same `cleanup` trap.
- Scratchpad logs and `repro_case1_race.sh` left in the session scratchpad (not in the repo).
