---
Task: t2309_guarded_enter_for_shadow.md
Base branch: main
Output branch: main
---

# t2309 — Guarded, acked Enter for the minimonitor's shadow recheck

## Context

Since t2275 the minimonitor auto-recheck and the sitrep request delivery share
one submit loop (`monitor/agent_submit.submit_typed_text`). The two still differ
in **transport**:

- the sitrep path presses Enter with `monitor_core.guarded_send_key`: one
  `if-shell -F` whose condition is the run identity (unfrozen, same `pane_pid`,
  same server generation) AND `#{pane_in_mode} == 0`, acked by a per-dispatch
  nonce;
- the minimonitor's `send_enter` (`minimonitor_app._submit_shadow_prompt`,
  ~L6224) still calls a plain `monitor.send_keys(shadow_pane, "Enter")`.

So on the minimonitor side a tmux mode entered in the one round trip between the
pre-Enter mode read and the keystroke is still not closed: the Enter goes into
copy-mode as copy-pipe-and-cancel. This is the documented t2001 residual,
`aidocs/framework/shadow_agent.md` item 9. A shadow run replaced between the
write and the Enter is not caught either.

**Scope (user-confirmed):** guard the **Enter only**. The prompt write stays
`send_keys -l`. Moving it to `guarded_paste_text` changes the write transport,
which needs t1525's live drain sweep re-run over every shadow agent. That goes
to a spawned follow-up (see `## Risk`). The write-side one-round-trip residual
stays documented.

**Outcome mapping (user-confirmed):**

| guarded Enter result | loop outcome | code |
|---|---|---|
| `skipped` / `in_mode` | hold (prompt is in the composer, Enter withheld) | `HOLD_PRE_ENTER_IN_MODE` (existing) |
| `skipped` / `identity_changed` | disarm | new `DISARM_SHADOW_RUN_CHANGED` |
| `unknown` (ack not read back) | disarm (the Enter may have gone; a hold could produce a duplicate round) | new `DISARM_ENTER_UNACKNOWLEDGED` |
| `failed` (malformed, nothing dispatched) | disarm, text left in the composer | `DISARM_ENTER_SEND_FAILED` (existing) |
| shadow identity frozen at fire time | hold, nothing written | new `HOLD_SHADOW_FROZEN` |
| shadow identity unreadable at fire time | hold, nothing written | new `HOLD_SHADOW_IDENTITY_UNREADABLE` |

## Frozen-shadow semantics (measured in exploration, re-confirmed in step 1)

- A shadow can be frozen: `aitask_frozen.sh freeze <pane>` →
  `agent_freeze.freeze_pane` never checks `@aitask_shadow_target`
  (`shadow_agent.md` ~L268). The freeze does `respawn-pane -k` into a stand-in
  viewer and unsets only `@aitask_frozen` / the stand-in-ready option on
  rollback.
- `match_shadow_pane_info` (`monitor_core.py:612`) does not filter on
  `@aitask_frozen`. So a frozen shadow whose pane option binding survives the
  respawn is still "the shadow" to the loop.
- `dispatch_condition` → `run_identity_condition` requires an unfrozen pane, so
  every guarded Enter into a frozen shadow would skip with `identity_changed`.
  The guard therefore checks frozen **before the write** (hold, nothing
  written), not only at the Enter.

## Implementation

1. **Confirm the frozen-shadow premise on a private tmux server.** In the
   scratchpad, on its own `-L` socket and never the user's server: create a
   pane, set `@aitask_shadow_target`, `respawn-pane -k` it, and confirm the
   option survives. Then set `@aitask_frozen` and confirm
   `monitor_core.dispatch_condition` evaluates false through `if-shell -F`.
   Record the result in the plan's Final Implementation Notes. If the binding
   does not survive the respawn, the frozen hold is a pure backstop and stays
   anyway, because a restore also respawns.

2. **`monitor/review_loop.py`: new codes + prose + banners.**
   - `DISARM_SHADOW_RUN_CHANGED = "shadow_run_changed"`, message: "the shadow
     pane's agent run changed before the Enter (frozen, restarted or replaced)
     — the recheck was not submitted to it".
   - `DISARM_ENTER_UNACKNOWLEDGED = "enter_unacknowledged"`, message: "could
     not confirm the Enter reached the shadow — the recheck may or may not have
     been submitted; check its composer".
   - `HOLD_SHADOW_FROZEN = "shadow_frozen"`, message: "the shadow pane is
     frozen — restore it and the recheck goes out; nothing written"; banner
     "⟳ holding: shadow frozen — restore it to resume".
   - `HOLD_SHADOW_IDENTITY_UNREADABLE = "shadow_identity_unreadable"`, message:
     "could not read the shadow pane's agent run — nothing written"; banner
     "⟳ holding: shadow run unreadable — will retry".
   - Update the code-block comment and keep both banners within the
     76-cell budget (the existing banner tests enforce it).

3. **`_fire_shadow_recheck` (minimonitor_app.py ~L6066–6094): read the shadow
   run identity before the write.** After the `monitor is None` check and
   **before** the pre-write mode read, so the mode stays the last read before
   the write:
   ```python
   rc, out = await monitor.tmux_run_async(
       ["display-message", "-p", "-t", shadow_pane, monitor_core.RUN_IDENTITY_FORMAT],
       timeout=3.0)
   identity = monitor_core.parse_run_identity(rc, out, shadow_pane)
   if not ctrl.delivery_valid(token):          # a new await: supersession first
       return "not_ready", review_loop.HOLD_DELIVERY_SUPERSEDED
   if identity is None:
       return "not_ready", review_loop.HOLD_SHADOW_IDENTITY_UNREADABLE
   if identity.frozen_record:
       return "not_ready", review_loop.HOLD_SHADOW_FROZEN
   ```
   Then pass `identity` to `_submit_shadow_prompt`. Resolve
   `RUN_IDENTITY_FORMAT` / `parse_run_identity` / `guarded_send_key` /
   `new_dispatch_nonce` / `DISPATCH_*` / `SKIP_IN_MODE` through the
   `monitor_core` module attribute at call time, never a `from … import`, so
   tests and mutants reach them (the `agent_submit` lookup-site rule).
   Both new holds write nothing, so `abort_fire` re-firing on the next tick is
   only a re-read, never a key-injection spin. Update the docstring: replace
   the "Accepted residual" paragraph at ~L6080 so it covers the write only,
   and add the identity read.

4. **`_submit_shadow_prompt` (~L6096): guarded transport + outcome mapping.**
   - Signature gains `identity` (last positional).
   - ```python
     async def send_enter():
         # Synchronous dispatch: no await separates the checkpoint from the
         # key (t2001), and none separates the dispatch from the outcome below,
         # so a fatal code here cannot be stale (t2009).
         return monitor_core.guarded_send_key(
             monitor, identity, "Enter", monitor_core.new_dispatch_nonce())
     ```
     This deliberately avoids sitrep's `asyncio.to_thread`. A thread hop would
     put an await between the checkpoint and the key, and between the dispatch
     and the `"failed"` returns. The caller disarms on those returns without
     a lifecycle check. The cost is 3 blocking gateway calls instead of 1
     (`if-shell`, ack read, ack unset, plus the skip-reason read on a skip),
     each with the 5s default timeout. On a tmux stall that is a ~15–20s
     worst-case event-loop block, up from ~5s. This is accepted here; bounding
     it is follow-up `bounded_guarded_dispatch_budget` (see `## Risk`).
   - In the `ENTER_NOT_SENT` branch:
     ```python
     state, reason = out.enter
     self._loop_delivery_detail["enter_dispatch"] = f"{state}:{reason}" if reason else state
     if state == monitor_core.DISPATCH_SKIPPED and reason == monitor_core.SKIP_IN_MODE:
         return "not_ready", review_loop.HOLD_PRE_ENTER_IN_MODE
     if state == monitor_core.DISPATCH_SKIPPED:
         return "failed", review_loop.DISARM_SHADOW_RUN_CHANGED
     if state == monitor_core.DISPATCH_UNKNOWN:
         return "failed", review_loop.DISARM_ENTER_UNACKNOWLEDGED
     return "failed", review_loop.DISARM_ENTER_SEND_FAILED
     ```
     The in-mode skip is the closed residual. It has the same meaning and the
     same release path as the pre-read in-mode hold: the prompt is in the
     composer and nothing was submitted. `enter_dispatch` on the record tells
     the two apart in the event log.
   - Update the docstring (transport paragraph, the t2001 pane-mode paragraph,
     the outcome list).

5. **`monitor/review_loop_log.py` ~L345:** add `enter_dispatch` to the printed
   delivery-diagnostic keys and extend the comment.

6. **`monitor/agent_submit.py` docstring:** name both callers' Enter
   transports as guarded `guarded_send_key` dispatches. Code is unchanged: the
   loop already returns `ENTER_NOT_SENT` with `out.enter` for any non-`sent`
   state.

7. **Tests: `tests/test_submit_labels_pinned.py`.**
   - `_MmFake` gains a sync `tmux_run` that models the guarded dispatch:
     `if-shell` pops a scripted ack (`"sent"` by default, `"skipped"` or
     `"unknown"` = no ack written) and counts dispatch attempts. It also
     serves the ack read-back (`DISPATCH_ACK_FORMAT`), the `set-option -pu`,
     and the skip-reason read (a `reason_line` knob, as `srd.FakeMon` does).
     `send_keys` now raises, so any plain Enter fails the table loudly.
     `enters` counts Enter dispatch attempts.
   - `run_mm` passes `RunIdentity("%5", "4242", "1", "", "")`; a row field
     `identity` overrides it.
   - Rows: every existing label stays. `enter_send_failed` becomes
     `t2309_enter_dispatch_malformed` (an identity with a non-digit pid ⇒
     `failed` before any dispatch ⇒ `DISARM_ENTER_SEND_FAILED`, enters 0),
     with `old=("failed", DISARM_ENTER_SEND_FAILED, 1, False)`. New rows
     (no `old`): `t2309_enter_skipped_in_mode` → (`not_ready`,
     `HOLD_PRE_ENTER_IN_MODE`, 1, False); `t2309_enter_skipped_identity` →
     (`failed`, `DISARM_SHADOW_RUN_CHANGED`, 1, False);
     `t2309_enter_unacknowledged` → (`failed`, `DISARM_ENTER_UNACKNOWLEDGED`,
     1, False); `t2309_retry_enter_skipped_in_mode` (a swallowed first Enter,
     then the guarded skip) → (`not_ready`, `HOLD_PRE_ENTER_IN_MODE`, 2, False).
   - Generalize `test_only_the_t2274_rows_changed`: every `t2274_` row carries
     `old`; any row carrying `old` is prefixed `t2274_` or `t2309_` and
     differs from `expect`. Expected detail keys = `DETAIL_KEYS`, plus
     `enter_dispatch` for the `ENTER_NOT_SENT` rows. Update the module
     docstring.

8. **Tests: `tests/test_minimonitor_concern_action.py`.**
   - `_LoopFakeMon`:
     - The async identity read (a format carrying `pane_pid`, dispatched
       **before** the mode-query branch, so `mode_queries` stays exact)
       answers from `shadow_pid`, `server_pid`, `frozen`, `identity_rc` and an
       `on_identity_query` hook.
     - A sync `tmux_run` models `if-shell`. If the run is replaced (`run_pid`
       ≠ the condition's pid) or frozen, it skips. If the pane is in a mode,
       it skips. Otherwise it applies the Enter through the existing composer
       model and appends `("%5", "Enter", False)` to `sent`, so every
       existing Enter-count assertion keeps its meaning. An `enter_acks`
       queue can force `"unknown"`.
     - The fake also serves the ack read-back, the unset and the skip-reason
       read; other verbs fall through to `_FakeMon.tmux_run`.
   - Retarget `test_enter_failure_names_the_leftover_text_and_disarms` to
     `test_an_unacknowledged_enter_disarms_and_says_so`
     (`enter_acks=["unknown"]` ⇒ `DISARM_ENTER_UNACKNOWLEDGED`, message
     asserted).
   - New tests:
     - **`test_a_mode_entered_between_the_read_and_the_enter_withholds_it`**:
       the closed residual. `on_mode_query` flips the pane into copy-mode
       right after the pre-Enter read answers `0`. Expect no Enter applied,
       `swallowed_by_mode == 0`, a hold `HOLD_PRE_ENTER_IN_MODE` whose record
       carries `enter_dispatch=skipped:in_mode`, and the loop still armed.
     - `test_a_shadow_run_replaced_before_the_enter_disarms`: the replaced
       run skips with `identity_changed` and disarms with
       `DISARM_SHADOW_RUN_CHANGED`; no Enter.
     - `test_a_frozen_shadow_gets_no_keys_and_holds`: `HOLD_SHADOW_FROZEN`,
       `sent == []`, armed.
     - `test_an_unreadable_shadow_identity_holds_and_writes_nothing`:
       `HOLD_SHADOW_IDENTITY_UNREADABLE`.
     - `test_supersession_during_the_identity_read_is_a_hold`: a disarm and
       re-arm inside `on_identity_query` gives `HOLD_DELIVERY_SUPERSEDED`,
       and the fresh arm survives.
   - The existing negative control
     `test_the_same_fixture_out_of_mode_delivers` must stay green unchanged
     (`mode_queries == 2`).

9. **Pre-fix red proof (isolated baseline, never stash).** In a scratchpad
   `git worktree add --detach <dir> HEAD`, copy in only the new
   `test_minimonitor_concern_action.py` (fake + tests) and run the
   mode-race test there. It must FAIL: on HEAD the plain `send_keys` Enter
   lands in the mode, so `swallowed_by_mode == 1`. The frozen and
   identity-unreadable tests should fail there too. Classify each new test as
   red or green on the baseline in the Final Implementation Notes, then
   `git worktree remove` the baseline. This proves the fake models the race
   instead of green-washing it.

10. **Docs: `aidocs/framework/shadow_agent.md`.**
    - Item 7: the Enter is now a guarded `if-shell` dispatch (the write is
      still `send_keys -l`).
    - Item 9: change "supplies only the transport (`send_keys`)" to the
      guarded transport. Rewrite the **Accepted residual** paragraph: closed
      for the Enter by the guarded dispatch; it remains for the literal
      **write**, pointing at the follow-up task. Add a short table of the
      guarded-Enter outcomes and the two pre-write identity holds (above).
      Mention `enter_dispatch` in the event-log section.
    - Check `website/content/` for any page describing the auto-recheck
      residual or its hold/disarm reasons with
      `grep -rn "auto-recheck\|recheck" website/content`. Update it if one
      exists, then run `python3 check_links.py --build`.

11. **Step 9 (Post-Implementation):** cleanup, archival and merge per the
    shared workflow.

## Verification

- `python3 tests/test_submit_labels_pinned.py`: the label table (both callers).
- `python3 tests/test_minimonitor_concern_action.py` and
  `python3 tests/test_review_loop.py`.
- `python3 tests/test_minimonitor_concern_smoke.py`: the live tmux smoke drives
  the real guarded Enter path against real panes.
- The sitrep side is unchanged and must stay green:
  `python3 tests/test_sitrep_request_delivery.py`,
  `bash tests/test_sitrep_request_delivery_live.sh`, plus any
  `tests/test_agent_submit*.py`.
- `bash tests/test_no_raw_tmux.sh`: the new calls go through `monitor.tmux_run*`.
- Whole Python suite: `set -o pipefail; bash tests/run_all_python_tests.sh`,
  read the last-line verdict.
- The step-9 baseline red proof is recorded in the plan.
- **Known gap in the live coverage.** No live run above reproduces the exact
  timing gap this task closes. The minimonitor smoke
  (`test_a_pane_in_copy_mode_receives_nothing_and_stays_in_mode`) enters
  copy-mode **before** delivery and is caught by the pre-write read
  (`HOLD_SHADOW_IN_MODE`). The sitrep live suite's mutant "only the conjunct
  removed" is declared to stay **green** on its copy-mode case (h), because
  the pre-Enter Python read catches it first. The dispatch-time conjunct is
  therefore proven here only by the fake-backed test, its step-9 baseline red
  proof, and the existing `dispatch_condition` assertions. A private-server
  live test of the post-read gap is spawned follow-up
  `live_dispatch_race_test_for_shadow` (see `## Risk`).

## Risk

### Code-health risk: medium
- The Enter transport of a load-bearing loop changes, and every test of it
  runs over hand-written fakes. A fake that mis-models the guarded `if-shell`
  could pass the new tests while production differs. No live run reproduces
  the post-read gap: the minimonitor smoke is caught by the pre-write read, and
  the sitrep live suite's conjunct-only mutant is declared green on (h).
  Step 9's baseline red proof covers the fake only. · severity: medium ·
  → mitigation: live_dispatch_race_test_for_shadow
- The guarded dispatch runs synchronously on the Textual event loop. That is
  deliberate: it keeps the no-await checkpoint→key and dispatch→outcome
  invariants. But it makes 3 blocking `tmux_run` calls (plus a 4th on a skip),
  each with the 5s default timeout, and the cleanup still runs after a failed
  ack. A tmux stall can freeze the minimonitor for about 15–20s, up from about
  5s with today's single `send_keys`. This plan has no responsiveness
  acceptance criterion. · severity: medium ·
  → mitigation: bounded_guarded_dispatch_budget

### Goal-achievement risk: low
- The write-side one-round-trip mode residual stays open by scope decision.
  Closing it needs the paste transport plus t1525's live drain sweep.
  · severity: low · → mitigation: guarded_prompt_write_for_shadow

### Planned mitigations
- timing: after | name: guarded_prompt_write_for_shadow | type: enhancement | priority: low | effort: medium | inline_risk: high | added_complexity: medium | addresses: goal-achievement — write-side one-round-trip mode residual left open by scope | desc: Move the minimonitor shadow recheck's literal prompt write (`_fire_shadow_recheck`) from `send_keys -l` to `monitor_core.guarded_paste_text` (identity + not-in-mode guarded, nonce-acked) and re-run t1525's live drain sweep over claude/codex/opencode, since the write transport changes
- timing: after | name: live_dispatch_race_test_for_shadow | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: low | addresses: code-health — fake-only proof of the dispatch-time mode conjunct (no live run opens the post-read gap) | desc: Add a private-server live test (tests/test_minimonitor_concern_smoke.py harness) that drives the shadow recheck against a real pane, enters copy-mode immediately AFTER the final pre-Enter mode read (wrap `monitor_core.query_pane_mode`), and asserts no Enter reached the mode, the pane is still in copy-mode, the prompt is still in the composer and the outcome is HOLD_PRE_ENTER_IN_MODE with enter_dispatch=skipped:in_mode. Include a mutant that patches `monitor_core.dispatch_condition` to the identity term only, and assert it turns that case red
- timing: after | name: bounded_guarded_dispatch_budget | type: performance | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: code-health — synchronous guarded Enter can block the minimonitor event loop ~15–20s on a tmux stall | desc: Bound the minimonitor's synchronous guarded Enter dispatch with an overall time budget (e.g. per-call timeouts through guarded_send_key/_guarded_dispatch). Alternatively, move the ack read-back and cleanup off the event loop and validate the delivery lifecycle (token) before applying their outcome. Either way the dispatch keeps the checkpoint→key ordering and the no-stale-fatal-code invariant. Add a responsiveness acceptance test with a stalled fake tmux_run, and check the sitrep caller's to_thread path for the same budget

## Final Implementation Notes

- **Actual work done:** all plan steps 1–10 as written.
  - `review_loop.py` gained `DISARM_SHADOW_RUN_CHANGED`, `DISARM_ENTER_UNACKNOWLEDGED`,
    `HOLD_SHADOW_FROZEN` and `HOLD_SHADOW_IDENTITY_UNREADABLE`, with their prose and the two hold
    banners.
  - `_fire_shadow_recheck` reads the shadow `RunIdentity` before the pre-write mode read. A token
    re-check follows it. The read holds when the identity is unreadable or frozen.
  - `_submit_shadow_prompt(…, identity)` presses Enter through a synchronous
    `monitor_core.guarded_send_key` and maps the `ENTER_NOT_SENT` answers per the table above.
    It records `enter_dispatch`.
  - `review_loop_log` prints `enter_dispatch`.
  - The `agent_submit` docstring was updated.
  - `minimonitor_app` now imports the `monitor_core` module, in place of the
    `DISPATCH_SENT` / `DISPATCH_FAILED` names (no other users).
  - Docs: `aidocs/framework/shadow_agent.md` (items 7 and 9, event log) and
    `website/content/docs/tuis/minimonitor/how-to.md` (two banner rows, the disarm paragraph,
    the log fields). `check_links.py --build` passed.
- **Step 1 measurement (private `-L` tmux server, scratchpad probe):** `@aitask_shadow_target`
  survives `respawn-pane -k`, and the respawn changes `pane_pid`. `dispatch_condition` evaluates
  `1` on the same unfrozen run, `0` with `@aitask_frozen` set, and `0` for the pre-respawn
  identity. So a frozen shadow stays bound, and the pre-write `HOLD_SHADOW_FROZEN` is
  reachable, not only a backstop.
- **Step 9 baseline red proof:** a detached worktree at HEAD `cfb089df8`, with only the new
  `tests/test_minimonitor_concern_action.py` copied in, then removed.
  - RED `test_a_mode_entered_between_the_read_and_the_enter_withholds_it`: `1 != 0 : an Enter
    reached the mode`. HEAD's plain `send_keys` Enter went into copy-mode, which is the residual
    itself.
  - RED `test_a_shadow_run_replaced_before_the_enter_disarms`: the Enter was sent to the
    respawned run.
  - RED `test_a_frozen_shadow_gets_no_keys_and_holds` and
    `test_an_unreadable_shadow_identity_holds_and_writes_nothing`: HEAD wrote prompt + Enter.
  - RED `test_rearm_at_the_identity_read_writes_nothing`: "the hook never fired". This one is
    structural: HEAD has no identity read.
  - RED `test_an_unacknowledged_enter_disarms_and_says_so`: `0 != 1`, no guarded dispatch on
    HEAD.
  - GREEN negative control `test_the_same_fixture_out_of_mode_delivers`.
- **Deviations from plan:**
  - `_LoopFakeMon` gained an `after_mode_reply` hook, called after the mode answer is fixed.
    The race test needs it to enter the mode *after* the pre-Enter read independently of the
    transport. Flipping inside the fake's `if-shell` would have made the HEAD run red for the
    wrong reason (no flip at all).
  - The fake evaluates the real `dispatch_condition` string: frozen term, `pane_pid`, server
    `pid`, `PANE_NOT_IN_MODE`.
  - The pinned table gained one more row than planned (`t2309_enter_skipped_frozen`: a
    mid-flight freeze classifies `identity_changed`), plus
    `test_the_enter_dispatch_answer_is_recorded`.
- **Issues encountered:** the probe's first run returned `None` identities because the probe
  `.strip()`ped trailing empty tab fields. That was a probe bug, not a product issue.
- **Key decisions:**
  - The guarded dispatch stays synchronous, preserving the no-await checkpoint→key and
    dispatch→outcome invariants.
  - The unacked Enter disarms rather than holds, so it never causes a duplicate round.
  - Both choices were user-confirmed at planning.
- **Upstream defects identified:** None.
