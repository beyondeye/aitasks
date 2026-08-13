---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [aitask_board, tui, tmux, manual_verification]
verifies: [1248]
anchor: 1248
followup_kind: risk_mitigation
created_at: 2026-07-27 00:01
updated_at: 2026-08-13 23:06
boardidx: 46080
---

## Origin

Risk-mitigation ("after") follow-up for t1248, created at Step 8d after
implementation landed. Confirmed by the user during the planning-time risk
evaluation.

## Risk addressed

Goal-achievement — the tmux cursor-key trigger is inferred, not captured.
Verbatim from t1248's plan `## Risk` section:

> The *trigger* — that tmux emits a cursor key during wheel scrolling — is
> inferred, not directly observed: priority bindings are consumed at App level
> before any seam this session could instrument, so the key itself was never
> captured. The inference is strong (focus advanced by exactly one card in the
> scroll direction across 9 episodes, and `action_nav_up/down` is the only code
> path that does that), and the fix neutralises *any* focus change during an
> active scroll rather than that one trigger — but if the real trigger is
> something else entirely, the symptom could survive. · severity: medium

## Goal

Confirm in a **real tmux session with a real mouse** that the reported symptom
is gone. Everything in t1248 was proven headlessly against synthetic input; the
one thing headless testing could not reproduce is the very condition that
produces the bug. This task closes that gap.

If the symptom survives, that is the signal the inferred trigger was wrong —
reopen the investigation rather than patching around it. t1248's plan lists
what was already ruled out (wheel handling itself, periodic refresh,
`apply_filter` virtual-size churn, rendering artifacts) so the next round does
not re-tread them.

## Verification Checklist

- [ ] In tmux, wheel-scroll the Unsorted / Inbox column down for ~30s: the view never snaps back to an earlier position
- [ ] Same column, wheel-scroll up for ~30s: the view never jumps forward
- [ ] Repeat both in a short split pane (≤ 18 rows, where no card is fully visible): movement stays bounded to at most one card height, never a full rewind
- [ ] After wheel-scrolling away from the focused card, press `down`: the cursor moves to a card that is already on screen, and the view does not teleport
- [ ] Same, press `up`: the cursor moves to a card already on screen (the topmost one when focus fell off the top)
- [ ] Ordinary keyboard navigation still works: from a visible card, `up`/`down` steps one card at a time and scrolls an off-screen target into view
- [ ] `left`/`right` between columns still lands where expected and feels the same as before
- [ ] Repeat the wheel-scroll checks in the By-Topic (`y`) and By-Trail (`z`) views, which use the same TaskCard focus path
- [ ] Confirm the plain-terminal (non-tmux) behaviour is unchanged

## If it still jumps

Re-instrument rather than guess. t1248's plan records the harness: wrap
`Widget._scroll_to`, `scroll_visible` and `_size_updated` on `KanbanColumn`, and
`Screen._forward_event`. **Priority-bound keys are invisible at
`Screen._forward_event`** — they are resolved at App level
(`textual/app.py:4137`), so hook `App._check_bindings` or `App.on_event` to see
the `up`/`down` keys that actually trigger this.
