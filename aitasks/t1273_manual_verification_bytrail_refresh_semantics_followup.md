---
priority: medium
effort: medium
depends: [1268]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1268]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-28 00:34
updated_at: 2026-07-28 01:08
artifacts:
  - handle: art:trail-t1273-verify
    kind: implementation_trail
    name: t1273 verify fixture
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1268

## Verification Checklist

- [x] Footer in By-Trail reads `r Refresh · R Agent Refresh · d Freshness · s Select Trail · S Sync`, and reverts to `r Refresh · s Sync · C Commit All` on leaving the view (press `a`) — PASS 2026-07-28 01:08 auto: live tmux board; By-Trail footer = 'r Refresh  R Agent Refresh  d Freshness  s Select Trail  S Sync'; after 'a' it reverted to 'r Refresh  s Sync  C Commit All'
- [x] Edit a trail member's `status:` on disk, press `r` — the card updates immediately, with no agent dialog and no perceptible delay — PASS 2026-07-28 01:07 auto: live tmux board; edited t635_30 status Ready->Postponed on disk, pressed r -> card re-rendered 📋 Postponed in 0.33s, no modal/agent dialog; unchanged without the keypress
- [ ] Press `d` — banner returns to `⟳ checking freshness…` then `⚠ stale: N`, and detail-bearing drift markers appear on the owning cards (including an archived member rendered as a ghost card)
- [ ] Press `R`, launch into tmux, let the skill land a new artifact version — within ~20s the board notifies "Trail artifact updated — reloading" and re-renders with no keypress
- [ ] Press `R` twice in quick succession — the second press is a no-op, and `R Agent Refresh` disappears from the footer while the launch is pending
- [x] Press `C` in By-Trail — nothing happens (the action is hidden) — PASS 2026-07-28 01:08 auto: live tmux board; C hidden from By-Trail footer (visible in All with the same modified task); pressing C left the screen byte-identical and committed nothing
- [ ] Press `S` — `ait sync` runs and the cards reflect what was pulled
- [x] Enter By-Trail and cancel the trail selector — `r`/`d`/`R` are absent from the footer; only `s Select Trail` and `S Sync` remain — PASS 2026-07-28 01:07 auto: live tmux board; By-Trail + Esc on selector -> footer read '? Keys  q Quit  ⏎ View/Edit  s Select Trail  S Sync  n New Task  O Options' (r/d/R absent)
- [x] Trail-selection modal badge reads "(recorded)" rather than implying a live freshness verdict — PASS 2026-07-28 01:07 auto: live tmux board; selector row read 'owner t635 · ad_hoc · ✓ current (recorded) · 2026-07-27T08:59:52Z'
- [ ] Verify `.aitask-scripts/board/aitask_board.py` By-Trail flows end-to-end in tmux (interactive surface touched by this task)
