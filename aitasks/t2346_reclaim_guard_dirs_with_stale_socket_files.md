---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [tests, test_infrastructure, tmp_cleanup]
gates: [risk_evaluated]
anchor: 2290
followup_kind: carry_over
created_at: 2026-11-22 11:43
updated_at: 2026-11-22 11:43
---

## Origin
Deferred from t2301 by the user (review round 6): "For t2301, I'm fine with
leaving directories that contain stale socket files for manual cleanup.
Whether a socket still has a live listener can wait for a follow-up."

## Current behaviour (t2301)
`tests/lib/tmpdir_guard.sh` step 6 (`_tg_socket_under`) runs
`find <candidate> -type s -print -quit` after the mount check and before any
recursive chmod/rm. Any socket file inside a killed run's guard dir keeps the
dir (`keep:socket:<path>`), and a walk that fails keeps it too
(`keep:socket-scan-failed`). A test that left a socket file behind (bound, then
killed) therefore pins its dir until it is removed by hand.

## Goal
Reclaim a dir whose socket files are provably STALE (no live listener), and
keep it whenever that cannot be proven:
- a connect() to the socket path that fails with ECONNREFUSED is evidence of no
  listener; success, EAGAIN/backlog-full, EACCES or any other result is not;
- the connect must not be able to reach anything unintended (it runs before
  removal, on a path inside a dir already past steps 1-5 of the ladder);
- consider whether a process could still hold an fd to an unbound/unlinked
  socket — the holder scan (step 4) already covers fds into the dir.
Keep "unknown is never rounded up to dead". Tests next to `(ah)` in
`tests/test_tmpdir_guard.sh`: stale socket (bound then closed) → reclaimed;
live listener → kept; unprobeable socket → kept.
