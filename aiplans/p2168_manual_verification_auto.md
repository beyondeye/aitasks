---
Task: t2168_manual_verification_merge_lock_waiter_backoff_and_release_st.md
Base branch: main
Output branch: main
---

# t2168 — manual verification of t2167 on macOS (autonomous auto-verification)

Host: Darwin 24.6.0 arm64 (Mac mini), Homebrew GNU bash 5.3.9 (`/opt/homebrew/bin/bash`),
PID identity probe kind `bsdinfo`. Tree: `main` @ `cfd671f97` (the t2167 code commit).

Note: at pick time origin/main was `6405506d1` and did not contain the t2167 code
(the task/plan had been archived but the code commit was not pushed). The user
pushed it during the session; main was fast-forwarded to `cfd671f97` and
`_MERGE_LOCK_POLL_SECS=30` / broker Cases 19–23 were confirmed present before any
item ran.

## Execution Log

### Item 1
- Item text: macOS: `bash tests/test_merge_lock_concurrency.sh` Case 2 (N=51) — all 51 merges land, no leaked holder, `status` reports `FREE` afterwards
- Approach: CLI invocation
- Action run: `bash tests/test_merge_lock_concurrency.sh`
- Output (trimmed): `Results: 30/30 passed, 0 failed` / `All tests PASSED`, 21 s wall. Case 2 asserts (51 MERGE_OK, 51 merge commits, 51 distinct branches, 0 bad rc, 0 cap hits, contention observed and named, `status` == `FREE`) all passed; no `FAIL`, `HELD:` or `RETAINED` lines in output. Asserts run in the main shell (not subshells), so the counters are trustworthy.
- Verdict: pass

### Item 2
- Item text: macOS: Cases 12 and 13 of the same suite pass — no `LOCK_UNAVAILABLE:guard_busy` cascade and no leftover holders
- Approach: CLI invocation (same run as item 1)
- Action run: as item 1
- Output (trimmed): all Case 12 / 13 / 13b asserts passed (HOLDER_CHANGED detected, new holder intact and RELEASED, guard released on TERM, force-release then MERGE_OK); no `guard_busy` anywhere in the output
- Verdict: pass

### Item 3
- Item text: macOS: `bash tests/test_merge_lock_broker.sh` passes in full, including Cases 19–23
- Approach: CLI invocation
- Action run: `bash tests/test_merge_lock_broker.sh`
- Output (trimmed): `Results: 135/135 passed, 0 failed`, 39 s wall (same count as the Linux run recorded in the t2167 plan). Case 19 runs with seams off (production 30 s cadence); Cases 22/22c use fixed fds 5–8 on read-write FIFOs with `read -t` rendezvous. `get_pid_starttime_kind $$` → `bsdinfo` on this host.
- Verdict: pass

### Item 4
- Item text: macOS: Case 22/22c red control — pre-probe and seam instance gating removed → `finish` reports `RETAINED:release_failed`
- Approach: scratch-tree mutant (t2167 plan's M1)
- Action run: `git archive HEAD | tar -x` into a scratchpad dir; Python edit removed the `_merge_lock_dead_key=""` … `fi` pre-probe block from `merge_lock_acquire` and the `[[ -n "$_merge_lock_dead_key" … ]] || return 0` line from `_merge_lock_liveness_seam` (diff reviewed, `bash -n` OK); ran `bash tests/test_merge_lock_broker.sh` there under a 480 s `perl alarm` watchdog
- Output (trimmed): `Results: 129/135 passed, 6 failed`, 57 s, no hang. Failures: 22b guard `held`; 22 finish `RETAINED:release_failed`; 22 waiter token `P`; 22c token `P`; 22c finish `RETAINED:release_failed`; 22c lock dir still present. Matches the M1 result recorded for Linux.
- Verdict: pass

## Cleanup
- Scratch mutant tree and logs under the session scratchpad (`t2168/`) — removed.
- Test temp dirs (`test_mergelock_*`, `test_mergefix_*`) — none left behind; no leftover broker / test processes.
- No tmux sessions created.
