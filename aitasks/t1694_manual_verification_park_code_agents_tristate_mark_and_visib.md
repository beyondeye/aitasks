---
priority: medium
effort: medium
depends: [1685]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1685]
anchor: 1685
followup_kind: manual_verification
created_at: 2026-09-02 18:34
updated_at: 2026-09-02 18:34
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1685

## Verification Checklist

- [ ] In `ait monitor`, press Space three times on one agent and confirm the mark cycles unmarked (dim ☆) → ★ → P → unmarked, with the glyph legible in your terminal font
- [ ] With an agent parked, confirm its row shows only `P`, the window name and a dim `parked` — no state dot, no status, no gate summary
- [ ] Confirm the monitor session bar shows an `N parked` term alongside the live counters, and that the live counters no longer include the parked agent
- [ ] Press `P` in `ait monitor` to hide parked agents, then `P` again to show them; confirm the list shrinks and grows
- [ ] Park the FOCUSED card while the filter is on and confirm focus lands on a visible card — not on the preview column and not nowhere
- [ ] Park the ONLY visible agent while the filter is on and confirm the pane list empties cleanly, the preview shows its empty state, and `P` still works to reveal the agent again
- [ ] With the filter OFF, focus a parked card and confirm the preview reads "This agent is parked — press Space to unpark it." rather than an empty pane
- [ ] Park an agent while the filter is on and read the toast: it must name the `P` then `Space` route back
- [ ] Confirm auto-switch (`A`) never moves focus onto a parked agent, with both an idle and an awaiting-input parked agent present
- [ ] In `ait minimonitor`, press Space on the followed agent until it is parked, and confirm the docked `── this agent ──` panel shows `P` and KEEPS updating its phase line — parking must not stop this pane watching its own agent
- [ ] With the followed agent parked, confirm `L` (auto-recheck loop), `c` (concerns) and `e` (shadow launch) still work on it
- [ ] Press `P` in `ait minimonitor` and confirm parked agents leave and rejoin the scrollable list, and that the key hints row shows `P:parked`
- [ ] Park an agent from `ait monitor` in one project and confirm it appears parked in another project's monitor within a refresh cycle (~3s)
- [ ] Verify a parked agent's tmux pane genuinely stops being captured — e.g. produce output in it and confirm no monitor re-renders its content while parked
- [ ] Rename the tmux window a minimonitor follows while its agent is parked, and confirm the docked panel keeps updating (the identity-confirmation fail-safe)
- [ ] Confirm an existing pre-t1685 marks store (~/.config/aitasks/agent_marks.json at version 1) still shows every star after upgrading
