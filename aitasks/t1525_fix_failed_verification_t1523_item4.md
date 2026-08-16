---
priority: medium
effort: medium
depends: [1509]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1159
followup_kind: verification_failure
created_at: 2026-08-16 10:21
updated_at: 2026-08-16 10:21
---

## Failed verification item from t1509

> Let the followed Claude agent produce output and settle at a prompt. Observe ONE automatic recheck fire: the Codex shadow receives a single-line "refetch and recheck round N" prompt plus Enter.

### Source

- **Manual-verification task:** `aitasks/t1523_manual_verification_codex_shadow_recheck_loop.md` (item #4)
- **Origin feature task:** t1509
- **Origin archived plan:** `aiplans/archived/p1509_shadow_readiness_detectors_for_non_claude_shadows.md`

### Commits that introduced the failing behavior

- a98799580 feature: Add Codex shadow readiness detection to the recheck loop (t1509)

### Files touched by those commits

- aidocs/framework/monitor_idle_and_prompt_detection.md
- aidocs/framework/shadow_agent.md
- .aitask-scripts/monitor/minimonitor_app.py
- .aitask-scripts/monitor/monitor_core.py
- .aitask-scripts/monitor/review_loop.py
- tests/review_loop_fixtures.py
- tests/test_minimonitor_concern_action.py
- tests/test_minimonitor_concern_smoke.py
- tests/test_review_loop.py

### Observed failure (live, 2026-08-16)

**The prompt is delivered but never submitted: Codex swallows the `Enter` that
arrives in the same input burst as the literal text.** The loop believes it
fired, so the round never runs and the shadow is left holding typed text.

Measured against live `codex-cli 0.146.0` panes on an isolated tmux socket:

| delay between the two `send_keys` calls | outcome |
|---|---|
| **0s (what `_deliver_recheck` does)** | **NOT submitted** — prompt stuck in the composer (2/2 trials, verified-clean composer) |
| 0.25s | submitted |
| 1.0s | submitted |

Confirmed through the **real** gateway (`monitor_core.TmuxMonitor.send_keys`,
`AITASKS_TMUX_SOCKET` pointed at the scratch socket) issuing exactly the two
calls `minimonitor_app.py:2852,2855` makes, in order, with no delay:

```
composer before delivery: ready
send_keys(prompt, literal=True) -> True   send_keys('Enter') -> True
composer AFTER delivery:  busy      <- prompt still sitting unsubmitted
```

### Why it is worse than a dropped keystroke

Both `send_keys` calls return success, so `_deliver_recheck` returns
`("sent", prompt)`, the controller enters `FIRED` and the banner reads
`⟳ recheck #1 sent — waiting for shadow`. The shadow then classifies as
`SHADOW_BUSY` (composer holding typed text) for as long as the text sits
there, and readiness never returns `True` — so the loop holds and **silently
never re-arms**. The existing `"recheck text left in the shadow composer —
submit or clear it there manually"` message is unreachable here: it is gated on
a non-zero `send_keys` rc, and tmux reports success.

A Claude shadow is unaffected (the loop shipped against it), so this is
specific to the Codex pairing t1509 exists to enable — i.e. the feature's
delivery half does not work end to end for its target configuration.

### Next steps

Make the Enter land for Codex shadows — e.g. a short inter-key delay, a
submit-and-verify (re-read the composer and retry the Enter once), or a
per-agent delivery strategy alongside `SHADOW_READY_DETECTORS`. Whatever the
fix, the delivery should **verify** submission rather than trust the two
`send_keys` return codes, since those are already `True` in the failing case.

Auto-generated from a manual-verification failure in t1523 item #4; diagnosis
added by the auto-verification run.
