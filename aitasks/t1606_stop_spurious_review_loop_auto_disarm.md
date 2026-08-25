---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [shadow, aitask_monitormini, review_loop]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1159
implemented_with: claudecode/opus5
created_at: 2026-08-25 16:33
updated_at: 2026-08-25 17:49
---

The minimonitor auto-recheck loop (`L`, t1159_2) **auto-disarms almost immediately
after arming**, non-deterministically. Re-arming right away usually works and the
loop then delivers the recheck prompt correctly. Auto-deactivation destroys the
feature's usefulness, and the user cannot tell why it happened.

Reported live 2026-08-25, tmux window `agent-pick-1601`: followed agent `claude`
(`%197`), shadow `codex` (`%201`, a `node` wrapper), minimonitor `%198`.

## Deliverable 1 (first): make the disarm reason knowable

**This must land before any behavioural fix.** Every hypothesis below is
currently unfalsifiable in production, because the cause is not recorded
anywhere and the toast fades.

There are **4 auto-disarm call sites** collapsed into **3 messages**, two of
which are ambiguous across at least five distinct causes:

| site | condition | current message |
|---|---|---|
| `minimonitor_app.py:3545` | mid-loop `shadow_key not in SHADOW_READY_DETECTORS` | names the agent |
| `minimonitor_app.py:3624` | latched-False replay -> `ACTION_AUTO_DISARM` | "followed agent or shadow pane is gone" |
| `minimonitor_app.py:3643` | `ctrl.tick` -> `ACTION_AUTO_DISARM` | "followed agent or shadow pane is gone" |
| `minimonitor_app.py:3656` | any `"failed"` from `_fire_shadow_recheck` | the delivery `detail` string |

`review_loop.tick` (`review_loop.py:190`) returns `ACTION_AUTO_DISARM` for
`agent_present is False` **or** `shadow_present is False` — two different
failures, one message. `_fire_shadow_recheck` / `_submit_shadow_prompt` reach
`"failed"` from at least five distinct conditions (no monitor, prompt-write
`send_keys` False, pre-Enter verdict DIALOG, pre-Enter verdict UNKNOWN,
pre-Enter verdict READY/WORKING, Enter `send_keys` False, retry budget
exhausted) and collapse them into two hardcoded strings.

Required:
- A distinct machine-readable reason code per condition, carried from the
  deciding site to the disarm.
- A **durable record** (not just a toast) so the next occurrence is
  identifiable after the fact.
- The user-visible message must name the actual condition.

## Deliverable 2: ambiguous pre-Enter reads must abort, not disarm

`_submit_shadow_prompt` (`minimonitor_app.py:3800-3808`):

```python
before = review_loop.shadow_state(await capture_raw_tail(monitor, shadow_pane), shadow_key)
if before != review_loop.SHADOW_BUSY:
    return "failed", (leftover if before in (SHADOW_DIALOG, SHADOW_UNKNOWN) else missing)
```

which `_service_review_loop:3656` routes to `_loop_auto_disarm(detail)` — the
whole loop dies.

**The asymmetry is pinned by the test suite itself**, in
`tests/test_minimonitor_concern_action.py`:

- `test_a_dialog_after_the_enter_is_unverified_not_submitted` — post-Enter
  `SHADOW_DIALOG` warns loudly and asserts
  `assertTrue(app._review_loop.armed)  # NOT a disarm`. Its docstring names
  transcript masking as the reason: `_ordered_state` sweeps prompt patterns
  over the whole tail before the composer scan, so a dialog string in the
  shadow's own transcript masks a still-busy composer.
- `test_only_a_busy_composer_authorises_the_enter` — pre-Enter `SHADOW_DIALOG`
  and READY/WORKING both **disarm**.
- `test_an_unreadable_pane_before_the_enter_vetoes_the_send` — a plain
  `capture_raw_tail` failure (`SHADOW_UNKNOWN`) **disarms**.

Same ambiguity, opposite response. The pre-Enter path should keep the **veto**
(fail closed: send nothing) but route to `ctrl.abort_fire(token)` -> WAITING,
still armed — the next tick re-permits.

`SHADOW_UNKNOWN` disarming is also a direct contradiction of the rule this
subsystem states for itself in `find_shadow_pane_info_async`'s docstring:
*"a transient tmux failure pauses the loop, only a verified absence disarms it"*.

**Safety argument for abort-not-disarm:** `_ready_from_state`
(`review_loop.py:639`) returns `True` only for `SHADOW_READY`. A composer
genuinely holding leftover text classifies `SHADOW_BUSY`, so the next fire is
blocked and the loop merely holds. No runaway is possible.

**Constraint from t1525:** it deliberately chose *visible auto-disarm over
silent hold* (quoted in t1531). So the replacement must be a **visible** hold —
banner + reason — never a silent one. Do not simply revert to holding quietly.

**Keep fatal:** genuine transport failures — `send_keys` returning `False`, and
a persistently swallowed Enter past `SHADOW_SUBMIT_RETRIES` — are real evidence
of stranded text and should still disarm.

## Deliverable 3: the message must be true

On a masked or unreadable read the user is told *"recheck text left in the
shadow composer — submit or clear it there manually"* while the composer is
empty. Verified live: `%201` classified `state=ready`, zero pattern hits, at the
moment that message would have been shown.

## Evidence gathered (2026-08-25)

Ruled OUT empirically against the live session — do not re-investigate without
new evidence:

| path | measurement | result |
|---|---|---|
| shadow reverse-lookup verified-absence | 200 samples, control-mode + concurrent capture load | 0 failures |
| followed-agent presence `False` | 150 `capture_all_async` cycles | 0 failures |
| shadow agent-key resolution (`node` -> `codex`, two-rung) | 6 samples | stable |
| at-rest `DIALOG` masking | 420 samples, 6 live codex shadows, ~4 min | 0 hits, 0 capture failures |
| post-write composer readback at `d = COMPOSER_DRAIN_SECONDS` | 15 reps, live codex TUI at 60x64 under ~8 concurrent agents | 15/15 `busy` |
| Enter submit + post-verify | 12 reps, local `/status` command (no API cost) | 12/12 submitted |

**The failure was NOT reproducible synthetically.** Every mechanism is clean in
isolation, which is exactly why Deliverable 1 comes first.

Self-referential masking is nonetheless real in this repo — the codex dialog
literals live in files the shadow reviews: `Press enter to confirm or esc to
cancel` (4 files), `Yes, proceed (y)` (4 files), `Do you want to proceed?` (8
files).

## Most plausible production-reachable trigger

The shadow's job on "refetch and recheck" is to **run commands**, so codex pops
an exec-approval dialog as a normal consequence. The tick-time readiness read
authorises the fire; the pre-Enter readback happens ~`COMPOSER_DRAIN_SECONDS`
plus one capture later. A dialog appearing in that window yields `DIALOG` ->
`leftover` -> loop dead, with a false message. This is a hypothesis, not a
confirmed cause — Deliverable 1 exists to settle it.

## Test impact

These existing pins encode the current policy and must be revisited
deliberately (distinguish contract from fixture — the Enter **veto** is
contract and must be preserved; only the disarm changes):

- `test_only_a_busy_composer_authorises_the_enter`
- `test_an_unreadable_pane_before_the_enter_vetoes_the_send`
- `test_prompt_write_failure_sends_no_enter_and_disarms` (should stay fatal)
- `test_a_persistently_swallowed_enter_disarms_with_the_leftover_message` (should stay fatal)

## Related (not folded)

- **t1531** `bracketed_paste_delivery` — replaces the literal-write + timed-Enter
  transport with a bracketed paste. Same code path, different deliverable;
  complementary. Whichever lands second should re-check the other's assumptions.
- **t1503** non-convergence, **t1524** never-settled shadow, **t1542** boundary
  anchor rot — all cover over-*holding*, the opposite failure.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-25T14:49:55Z status=pass attempt=1 type=human
