---
priority: medium
effort: medium
depends: [1268]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1268]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-28 00:34
updated_at: 2026-07-28 00:41
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1268

## Verification Checklist

- [ ] Footer in By-Trail reads `r Refresh · R Agent Refresh · d Freshness · s Select Trail · S Sync`, and reverts to `r Refresh · s Sync · C Commit All` on leaving the view (press `a`)
- [ ] Edit a trail member's `status:` on disk, press `r` — the card updates immediately, with no agent dialog and no perceptible delay
- [ ] Press `d` — banner returns to `⟳ checking freshness…` then `⚠ stale: N`, and detail-bearing drift markers appear on the owning cards (including an archived member rendered as a ghost card)
- [ ] Press `R`, launch into tmux, let the skill land a new artifact version — within ~20s the board notifies "Trail artifact updated — reloading" and re-renders with no keypress
- [ ] Press `R` twice in quick succession — the second press is a no-op, and `R Agent Refresh` disappears from the footer while the launch is pending
- [ ] Press `C` in By-Trail — nothing happens (the action is hidden)
- [ ] Press `S` — `ait sync` runs and the cards reflect what was pulled
- [ ] Enter By-Trail and cancel the trail selector — `r`/`d`/`R` are absent from the footer; only `s Select Trail` and `S Sync` remain
- [ ] Trail-selection modal badge reads "(recorded)" rather than implying a live freshness verdict
- [ ] Verify `.aitask-scripts/board/aitask_board.py` By-Trail flows end-to-end in tmux (interactive surface touched by this task)
