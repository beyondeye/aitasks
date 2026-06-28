---
Task: t1088_applink_history_coordinate_verify.md
Worktree: current branch
Branch: main
Base branch: main
---

# Plan - t1088: AppLink History Coordinate Verification

## Summary

Treat t1088 as gated on `../aitasks_mobile` t14_13 being landed. If t14_13 is
still `Implementing` or the mobile checkout lacks `history` support, stop
without archiving t1088 and record that it is waiting on mobile.

Once ready, verify the server/mobile contract from
`aidocs/applink/content_transport.md` Scrollback: `before_line` is
viewport-relative, history rows arrive as contiguous negative IDs, and the
client maps `row_id -j` to absolute `before_line - j`.

No production API change is expected in this repo. This is a verification/test
task; only add or adjust tests if verification exposes missing automated
coverage.

## Key Changes

- Readiness gate:
  - Confirm `../aitasks_mobile/aitasks/t14/t14_13_history_rpc_scrollback_gesture.md`
    is `Done` or archived.
  - Confirm mobile source contains a `history` request path, negative-row
    rendering/merge behavior, and tests for `before_line` translation.
  - If not ready, leave t1088 unarchived and do not create source changes.
- Server-side contract verification:
  - Re-run existing server checks: `bash tests/test_applink_content.sh`,
    `bash tests/test_applink_router.sh`, `bash tests/test_applink_pusher.sh`,
    `bash tests/test_applink_headless_live.sh`.
  - Confirm current server coverage still proves token acceptance,
    `not_subscribed`, stale subscribed panes, drain-time anchoring, contiguous
    `-1..-m`, and no live `frame_id` advancement.
- Mobile-side contract verification:
  - In `../aitasks_mobile`, run targeted tests covering AppLink monitor
    rendering and session behavior, preferably
    `./gradlew :domain:allTests :shared:allTests`.
  - Verify mobile tests prove `before_line=0` maps returned `-1, -2, ...`
    above the viewport top, negative rows do not corrupt live rows, and
    `not_subscribed` is surfaced without rendering scrollback.
- Manual end-to-end check:
  - Run `./ait applink`, pair the mobile app, open an idle tmux pane with
    numbered output, scroll above the live viewport, and confirm pulled lines
    are contiguous and immediately precede the viewport top.
  - Repeat on an actively appending pane; overlap by scroll delta is acceptable,
    but the app must not crash, duplicate incoherently, or corrupt the live
    viewport.
  - Kill or stale a subscribed pane and confirm a token/no-render behavior;
    confirm an unsubscribed pane yields `not_subscribed`.

## Test Plan

- Server: `bash tests/test_applink_content.sh`,
  `bash tests/test_applink_router.sh`, `bash tests/test_applink_pusher.sh`,
  `bash tests/test_applink_headless_live.sh`.
- Mobile: `cd ../aitasks_mobile && ./gradlew :domain:allTests :shared:allTests`.
- Record manual verification evidence in t1088's plan final notes: idle pane
  result, active pane result, stale subscribed pane result, and unsubscribed
  pane result.
- If any mismatch is found, create a follow-up bug in the owning repo and do
  not archive t1088 unless the mismatch is explicitly accepted as deferred.

## Risk

### Code-health risk: low

- Verification-focused task with no expected production edits. Any added tests
  should be localized to existing AppLink test files. severity: low.
  mitigation: none needed.

### Goal-achievement risk: medium

- The mobile dependency is currently not landed in the inspected checkout, so
  running verification too early would produce false failures. severity:
  medium. mitigation: readiness gate before implementation.
- Manual phone verification can be environment-sensitive. severity: medium.
  mitigation: pair automated server/mobile tests with numbered-pane manual
  checks.

## Assumptions

- Default chosen during planning: wait for mobile t14_13 to land before
  archiving t1088.
- `../aitasks_mobile` remains the paired mobile checkout.
- No new risk-mitigation task should be created from this plan because t1088 is
  already the after-mitigation created by t1057.

## Execution Notes

- **Readiness gate:** Passed. Mobile t14_13 landed in git history
  (`feature: Add AppLink history RPC scrollback to mobile monitor (t14_13)`)
  and was followed by task/plan archival. Current mobile source contains
  `HistoryPayload`, `MonitorSessionMediator.history`, negative-row merge logic
  in `PaneRenderStateMediator`, top-edge scrollback request wiring in
  `PaneContentViewer`, and related common tests.
- **Server automated verification:** Passed.
  - `bash tests/test_applink_content.sh` passed (103 checks).
  - `bash tests/test_applink_router.sh` passed (172 checks).
  - `bash tests/test_applink_pusher.sh` passed (104 checks).
  - `bash tests/test_applink_headless_live.sh` passed; history control-plane
    token was confirmed and the negative-row keyframe branch correctly skipped
    because the throwaway pane had no scrollback.
- **Mobile automated verification:** Passed with escalated filesystem access for
  Gradle cache writes:
  `cd ../aitasks_mobile && ./gradlew :domain:allTests :shared:allTests`
  completed successfully (`BUILD SUCCESSFUL`, 111 actionable tasks, 11
  executed, 100 up-to-date). Gradle emitted existing Kotlin warnings about API
  dependency types in test source sets.
- **Manual phone verification:** Not completed in this environment. The Android
  CLI exists at `/usr/local/bin/android`, but `adb` is unavailable and no
  attached device/emulator was visible from the shell. Do not archive t1088 until
  the idle-pane, active-pane, stale subscribed pane, and unsubscribed pane manual
  scenarios are verified on a paired mobile device.
