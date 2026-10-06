---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: [trails, tui, board]
verifies: [1895]
anchor: 1895
followup_kind: risk_mitigation
created_at: 2026-10-06 13:55
updated_at: 2026-10-06 13:55
---

## Origin

Risk-mitigation ("after") follow-up for t1895, created at Step 8d after implementation landed.

## Risk addressed

focus restore across async re-render; tab-strip clipping/click on real terminals

- Tab switching re-renders the lanes asynchronously; focus restore could hit the detached-focus class of bugs (t1839) in `TrailsApp` · severity: medium
- Custom `TrailTabStrip` instead of the draft's Textual `Tabs` (deliberate, see the t1895 plan's Context); many tabs on a narrow terminal clip labels · severity: low

## Goal

Check the tabbed `ait trails` behaviour of t1895 in a real terminal (the automated pilot tests run headless): open several trails, switch tabs with the keyboard and the mouse, close tabs, and confirm that focus comes back to the right card and that tab labels stay readable on a narrow terminal. Use a scratch tmux session, not the main aitasks one.
