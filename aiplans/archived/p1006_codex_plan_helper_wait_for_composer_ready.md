# Plan for t1006: Codex Plan Helper Waits for Composer Ready

## Task

- Task file: `aitasks/t1006_codex_plan_helper_wait_for_composer_ready.md`
- Issue type: `bug`
- Profile: `fast`
- Working directory: current branch

## Summary

Fix `.aitask-scripts/aitask_codex_plan_invoke.py` so forced-plan Codex launches
do not type `/plan ...` after a blind sleep. The helper should relay the
interactive startup session, wait for the Codex composer-ready screen, and then
inject the skill prompt exactly once.

## Implementation Steps

- Replace the fixed startup sleep + `sendline()` handoff with a PTY relay that
  forwards user input and child output from launch onward.
- Detect composer readiness from visible Codex startup suggestion text, with
  `AITASK_CODEX_PLAN_READY_PATTERN` as an override for future CLI UI changes.
- Keep `AITASK_CODEX_PLAN_STARTUP_DELAY` as a minimum post-spawn throttle after
  readiness, not as the readiness mechanism.
- Add `AITASK_CODEX_PLAN_READY_TIMEOUT` so unknown startup screens leave the
  session interactive without injecting `/plan` into a blocking prompt.
- Preserve terminal resize handling and child exit-status propagation.
- Add fake-CLI PTY regression tests for immediate readiness, trust-gate
  pass-through, and child exit before readiness.

## Final Implementation Notes

- **Actual work done:** Reworked the Codex helper into a raw PTY relay that
  forwards startup prompts to the user, watches normalized child output for
  known composer-ready strings, and sends `/plan <prompt>` only after readiness.
  Added a ready-timeout path that leaves the session interactive without
  injecting the prompt if no ready marker appears.
- **Deviations from plan:** The implementation uses a relay loop instead of
  `pexpect.expect(...)` so user input can be forwarded during trust, onboarding,
  or update screens before the composer exists.
- **Issues encountered:** Test exit statuses needed an explicit `pexpect.close()`
  after EOF so the harness reaps the helper process before assertions.
- **Key decisions:** Did not add Codex auto-trust overrides. The helper preserves
  Codex trust policy and waits for the user to clear pre-composer gates.
- **Upstream defects identified:** None
