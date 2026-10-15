---
Task: t2009_stale_sent_delivery_clears_fresh_loop_hold.md
Base branch: main
Output branch: main
---

# t2009 — A stale delivery must not change the new lifecycle's loop-hold state

## Context

In `_service_review_loop` (`.aitask-scripts/monitor/minimonitor_app.py:4651-4672`),
the `"sent"` branch calls `self._clear_loop_hold()` even when
`ctrl.confirm_fire(token, …)` returns `False`. It returns `False` when the
delivery was superseded: the user pressed `L` to disarm and `L` again to re-arm
during the post-Enter drain or capture, and that capture read non-BUSY.
`_submit_shadow_prompt` returns `"sent"` on a non-BUSY post-Enter read without
checking the token again. A BUSY read retries through a token check instead. The stale delivery therefore
sets `_loop_hold_reason` to `None` on the new lifecycle. Two things follow:
- The hold banner the new lifecycle is showing changes to "ARMED".
- The next hold for the same cause counts as a new edge, so it is recorded and
  toasted a second time.

**A second case of the same defect, one branch away (recommended scope
extension).** A stale `"not_ready"` delivery returns
`HOLD_DELIVERY_SUPERSEDED`. The caller passes it to `ctrl.abort_fire(token)`,
which does nothing and returns `False`, and then calls
`self._loop_hold(HOLD_DELIVERY_SUPERSEDED)` anyway. That call **overwrites**
the new lifecycle's `_loop_hold_reason`. `HOLD_DELIVERY_SUPERSEDED` has no
banner in `review_loop.LOOP_HOLD_BANNERS`, so the effects match the `"sent"`
case: the new lifecycle's hold banner is replaced by "ARMED", and its next hold
is recorded and toasted again. The plan fixes both branches the same way, so
that "a stale delivery never changes the new lifecycle's hold state" is true
for the whole `if outcome` chain. To keep the task to the `"sent"` fix only,
drop Step 2 and its test row at the checkpoint.

Why this is safe for live deliveries: every non-superseded `"not_ready"` and
`"failed"` verdict is decided right after a token check, with no await in
between. For a live token, `confirm_fire` and `abort_fire` therefore always
return `True`, and the live paths behave exactly as they do now.

## Implementation steps

1. **`"sent"` branch: clear the hold only when the confirmation succeeds**
   (`minimonitor_app.py` ~4655):
   ```python
   if outcome == "sent":
       # Recovery: a delivery landed, so any standing hold is over — but only
       # THIS lifecycle's. A non-BUSY post-Enter read returns "sent" with no
       # token re-check, so a disarm + re-arm during that drain/capture makes
       # it stale: `confirm_fire` refuses it, and the hold reason now belongs
       # to the fresh lifecycle — clearing it would drop its banner and
       # re-fire its edge-triggered record (t2009).
       if ctrl.confirm_fire(token, time.monotonic()):
           self._clear_loop_hold()
   ```

2. **Stale `"not_ready"` branch: record the hold, but leave the live hold state
   alone.** Add a keyword-only `live: bool = True` to `_loop_hold`
   (`minimonitor_app.py:4222`):
   - `live=True` (the default, used by every existing call site): behaviour
     does not change.
   - `live=False`:
     - skip the edge check and do not assign `_loop_hold_reason`;
     - use `banner = ""`, so no banner is painted and no "holding" toast is
       shown;
     - still record the event (`KIND_HOLD`, with `detail` merged in);
     - still raise the "(not recorded)" warning if the record fails. A failed
       record is a fault in its own right (t1606).

   Caller (~4657):
   ```python
   elif outcome == "not_ready":
       ...existing comment...
       # A superseded delivery is still RECORDED (t1606: a lifecycle event,
       # not a fault), but its abort is refused and the hold state is the
       # fresh lifecycle's — overwriting it with a banner-less
       # HOLD_DELIVERY_SUPERSEDED would blank that lifecycle's banner (t2009).
       live = ctrl.abort_fire(token)
       self._loop_hold(reason, detail=detail, live=live)
   ```
   Update the `_loop_hold` docstring with one short paragraph on `live=False`.
   Leave the "Banner reflects the post-decision state every tick" block as it
   is: it already reads the new lifecycle's `ctrl.state` and
   `_loop_hold_reason`.

3. **Make the comments and docs match the new behaviour.** Each of these
   currently claims that every superseded delivery ends as a hold. Describe the
   exception **by outcome, not by whether the Enter has been sent yet**. A BUSY
   post-Enter read means the Enter reached tmux but the agent swallowed it. It
   still detects supersession: it `continue`s to the next attempt's token
   check, or, on the last attempt, reaches the token check before budget
   exhaustion (`test_rearm_at_the_final_post_enter_capture_never_disarms` pins
   that path). Only the **non-BUSY** post-Enter read returns `"sent"` without a
   recheck. That read is READY/WORKING, or DIALOG/UNKNOWN, which are reported
   as unverified.
   - The `_submit_shadow_prompt` docstring paragraph "Supersession is checked
     before ANY outcome is decided". Add one sentence:
     - a non-BUSY post-Enter read returns `"sent"` without re-checking the
       token, because it is a claim about a key already sent;
     - the caller's `confirm_fire` rejects a stale token, and the hold clear
       depends on that result;
     - a BUSY read still passes through a token check, on the retry or before
       the budget-exhausted return.
   - `aidocs/framework/shadow_agent.md:942`. Replace "a superseded delivery
     always ends as `HOLD_DELIVERY_SUPERSEDED`" with wording by outcome:
     - supersession is reported as `HOLD_DELIVERY_SUPERSEDED` on every path
       that reaches a token check, which includes a swallowed Enter (BUSY
       post-Enter read → retry, or budget exhaustion);
     - the one exception is a non-BUSY post-Enter read, which returns `sent`;
     - the caller's `confirm_fire`/`abort_fire` rejects a stale token on both
       outcomes, so a superseded delivery never changes the live lifecycle's
       hold state. Its superseded hold is still recorded.

     Write it in current-state form (no history narrative), following
     `documentation_conventions.md`.

4. **Tests.** Add them to `SupersessionDuringDeliveryAwaitsTests` in
   `tests/test_minimonitor_concern_action.py` and reuse `_run_until_rearmed`.
   In each hook, re-arm **and then** call `app._loop_hold(HOLD_SHADOW_IN_MODE)`
   to stand in for a hold the new lifecycle set itself. Pick a reason that has
   a banner, so a lost banner shows up in the assertion.
   - `test_a_stale_sent_keeps_the_fresh_lifecycles_hold`
     - Setup: the composer submits (`swallow_enter` stays False). The hook is
       on the post-Enter capture: `_enters(m) == 1 and ctrl.state ==
       DELIVERING`.
     - Assert:
       - `_enters(mon) == 1` and `mon.submitted`, which shows the `"sent"`
         route was actually taken;
       - the new arm survived, with the same generation and no `KIND_DISARM`;
       - `ctrl.rounds_fired == 0`: the stale confirm was rejected;
       - `app._loop_hold_reason == HOLD_SHADOW_IN_MODE`;
       - `app._loop_banner_text == loop_hold_banner(HOLD_SHADOW_IN_MODE)`;
       - after calling `app._loop_hold(HOLD_SHADOW_IN_MODE)` again,
         `HOLD_SHADOW_IN_MODE` occurs in `KIND_HOLD` **exactly once**, which
         shows the edge trigger was not reset.
   - `test_a_stale_not_ready_keeps_the_fresh_lifecycles_hold` (Step 2)
     - Setup: the hook is on the pre-Enter capture with a BUSY tail, using the
       same condition as `_pre_enter_capture_row`.
     - Assert:
       - zero Enters;
       - the new arm survived;
       - `HOLD_DELIVERY_SUPERSEDED` is still recorded in `KIND_HOLD`;
       - the new reason and banner are unchanged;
       - the same exactly-once check on `HOLD_SHADOW_IN_MODE` passes;
       - no "holding" toast mentions supersession.
   - **Negative control, run first:** add both tests **before** making the
     Step 1 and Step 2 code changes, and run them against the unmodified code.
     Each must fail on the reason/banner assertion: `None` in the `"sent"` row,
     `HOLD_DELIVERY_SUPERSEDED` in the `"not_ready"` row. Then apply the fixes
     and confirm both pass. Do not use stash or restore for this; it is purely
     a matter of ordering.
   - **Valid-token controls (existing, must stay green):**
     - `HoldLifecycleTests.test_a_successful_delivery_clears_the_hold`: a live
       `"sent"` still clears the hold;
     - `test_a_dialog_before_the_enter_holds_visibly_and_stays_armed` and
       `test_supersession_is_recorded_but_not_surfaced`: a live `"not_ready"`
       still holds visibly, and supersession is still recorded;
     - every `_assert_fresh_arm_survived` row, which asserts that
       `HOLD_DELIVERY_SUPERSEDED` is recorded.

## Verification

```bash
~/.aitask/venv/bin/python -m pytest -q tests/test_minimonitor_concern_action.py
~/.aitask/venv/bin/python -m pytest -q tests/test_review_loop.py tests/test_minimonitor_concern_smoke.py
```

Then run the whole suite and read only its last line:
`bash tests/run_all_python_tests.sh` (check `${PIPESTATUS[0]}` if you pipe the
output).

## Post-implementation

Step 9: current-branch mode. Run build verification and gates
(`risk_evaluated` is recorded by the orchestrator), then archive t2009.

## Risk

### Code-health risk: low
- `_loop_hold(live=False)` makes recording of a stale superseded hold
  non-edge-triggered: every stale delivery now records once, where before an
  overwrite could suppress a later record. No consumer reads
  `_loop_hold_reason == HOLD_DELIVERY_SUPERSEDED`. The change is
  record-additive, and the existing `_assert_fresh_arm_survived` rows and the
  t1606 hold tests still pin the recording · severity: low · → mitigation: none
  (covered by the plan's own regression rows and the existing valid-token
  controls)

### Goal-achievement risk: low
None identified.
