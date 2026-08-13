---
priority: medium
effort: medium
depends: [t1216_3]
issue_type: test
status: Ready
labels: [aitask_monitor, shadow, tui]
gates: [risk_evaluated]
anchor: 1111
followup_kind: risk_mitigation
created_at: 2026-07-30 08:12
updated_at: 2026-08-13 23:06
boardidx: 105472
---

## Origin

Risk-mitigation ("after") follow-up for t1216_3, created at Step 8d after
implementation landed.

## Risk addressed

Goal-achievement, severity medium — from `aiplans/archived/p1216/p1216_3_monitor_concern_picker.md`:

> The monitor is the **first production consumer** of
> `concern_block_signature`. Its reflow stability is a property claim over
> arbitrary tmux wrapping that t1216_1's tests could only sample; if real-world
> wrapping defeats it, badges silently never appear — an invisible failure.

## Goal

Verify, against **live tmux** rather than in-process fixtures, that
`concern_block_signature` stays both stable and discriminating for a real
concern block re-rendered at many pane widths, and that the monitor's badge
actually fires as a result.

Specifically:

- Drive a real shadow-shaped concern block through a live tmux pane resized
  across a wide sweep of widths (including the `_SENTINEL_SAFE_COLS = 24`
  boundary and several widths either side), capturing each with the real
  `capture-pane -p -e` path the monitor's tick uses.
- Assert the digest is **stable** across widths where the block text is
  unchanged, and **discriminating** when a concern's text genuinely changes.
- Quantify the documented mid-word-wrap residual: how many widths in the sweep
  re-hash an unchanged block. The contract says this fails safe (at most one
  spurious re-offer) — this task establishes the actual rate instead of assuming
  it is rare.
- Assert the monitor's badge fires end-to-end for at least one narrow width
  where the cheap detector returns `None` and the sub-sentinel probe must
  recover the block.

## Why this is not already covered

- **t1216_1's `tests/test_shadow_seam.py`** samples widths in-process by
  constructing strings; it never asks tmux to do the wrapping, so it cannot
  falsify the property against real terminal behaviour.
- **t1216_5** is a human walkthrough — it will notice a badge that never
  appears, but not a width-dependent rate, and it is not a regression guard.

## Constraints

Any live-tmux test must isolate itself: use `require_isolated_tmux()` from
`tests/lib/tmux_isolation.sh`, or pin an own socket and session name and only
ever `kill-session` that — see `tests/test_minimonitor_concern_smoke.py` for the
pattern. This must be safe to run from inside a working tmux session with live
code agents.

## Reference

- `.aitask-scripts/monitor/concern_parser.py` — `concern_block_signature`,
  `_SENTINEL_SAFE_COLS`, and the strictness table documenting the residual.
- `.aitask-scripts/monitor/monitor_app.py` — `_scan_concern_signatures`
  (carry-forward below the sentinel width) and `_offer_concerns` (the probe).
- `tests/test_monitor_concern_action.py::MidWordWrapDedupTests` — the in-process
  counterpart, including the asserted "the two digests really differ"
  precondition this task should reproduce against live tmux.
