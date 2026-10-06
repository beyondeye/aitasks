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

## Verification Checklist

- [ ] Open two or more trails from the selector; each opens in its own tab and the strip shows "<n> <title> <glyph>"
- [ ] Switch with [ and ] (wraps), with 1-9, and by clicking a tab; the banner and summary pane follow the active tab
- [ ] After switching away and back, the card you last focused in that tab is focused again (try quick back-to-back switches too)
- [ ] Ctrl+W closes the active tab and shows its neighbour; closing the last tab shows "no trail selected — press s"
- [ ] s lists already-open trails as "● open"; choosing one switches to its tab; r inside the selector re-scans
- [ ] A background tab shows • after its freshness check or a reload lands; the mark clears when you switch to it
- [ ] R on a tab, then switch away: when the refresh lands the trail's tab reloads (• if in the background)
- [ ] At 80 columns with 4+ tabs the strip stays on one row and labels are elided, not wrapped
