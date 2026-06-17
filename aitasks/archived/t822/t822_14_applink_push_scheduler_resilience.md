---
priority: medium
effort: low
depends: [t822_8]
issue_type: chore
status: Done
labels: [ait_bridge]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-16 00:00
updated_at: 2026-06-17 10:53
completed_at: 2026-06-17 10:53
---

Verify the landed push scheduler (t822_8) for two resilience gaps identified during plan review, then propose and implement any hardening that is actually needed.

## Origin

Risk-mitigation follow-up for t822_8 (snapshot push loop). Two code paths were flagged during plan review as untested and unplanned after t822_8 landed:

1. **Back-pressure under load** — the `content_transport.md` spec defines "coalesce → drop cursor → skip tick" behavior when a client is slow. The `_run_once` tests cover skip-tick (idle = zero bytes), but the coalesce path (multiple dirty signals in one tick → one keyframe, not multiple) and the drop-cursor path (cursor frame dropped when back-pressured) are untested.
2. **Abrupt connection loss mid-send** — if `ws.send()` raises mid-push (client disconnects abruptly), the exception must propagate cleanly and `_handle`'s `finally` block must cancel the `PushScheduler` task without leaking. This path has no automated test.

Neither gap is covered by t985 (`applink_security_review_hardening`, which is scoped to the control-plane) or the planned `applink_dataplane_limits_hardening` task (which addresses resource limits: max panes, frame-size cap, decode-bomb guards).

## Step 1 — Read and assess the landed code

Read the landed implementation from t822_8:
- `.aitask-scripts/applink/pusher.py` (scheduler, `_run_once`, back-pressure logic, stop/teardown)
- `.aitask-scripts/applink/server.py` (`_handle` finally block, `_pushers` lifecycle)
- `tests/test_applink_pusher.sh` (existing scheduler tests)

For each gap, determine:
- Does the landed code actually implement the behaviour correctly (even if untested)?
- Is the missing test just coverage, or is there a real bug?

## Step 2 — Propose options

For each gap, propose options ranging from "add a test only" (if code is already correct) to "fix + test" (if there is an actual bug). Include trade-offs and a recommendation.

## Step 3 — Implement agreed hardening

After the options are reviewed and one is selected per gap, implement:
- Any code fixes needed.
- Tests in `tests/test_applink_pusher.sh` covering the two scenarios:
  - **coalesce:** fake monitor returns dirty pane twice before a tick; `_run_once()` sends exactly one keyframe, not two.
  - **abrupt disconnect:** fake WS raises `ConnectionClosed` on `send()`; scheduler catches cleanly, `_handle` finally cancels task, no leaked asyncio task, no unhandled exception.

## Verification

- `bash tests/test_applink_pusher.sh` → PASS including the two new cases.
- `bash tests/test_applink_smoke.sh` → PASS.
- No asyncio `Task exception was never retrieved` warnings in the server log during the disconnect scenario.
