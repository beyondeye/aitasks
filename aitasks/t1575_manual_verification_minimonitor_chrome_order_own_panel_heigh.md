---
priority: medium
effort: medium
depends: [1566]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1566]
anchor: 1566
followup_kind: manual_verification
created_at: 2026-08-18 16:55
updated_at: 2026-08-18 16:55
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1566

## Verification Checklist

- [ ] Launch `ait minimonitor` in a real 40-column companion pane and confirm the followed agent sits at the top with its name, both wrapped title lines and the phase line visible, and no scrollbar glyph
- [ ] Confirm the shadow-stale and auto-recheck banners render BELOW the followed-agent panel, one and at most two rows respectively
- [ ] Confirm no session bar is present by default; set `tmux.minimonitor.session_bar: true` in `aitasks/metadata/project_config.yaml`, relaunch, and confirm the bar returns above the followed agent
- [ ] Launch `ait minimonitor` outside tmux and confirm the "Not inside tmux" error is still visible despite the bar shipping hidden
- [ ] Resize the companion pane narrower (approx 22-30 columns) and confirm the followed-agent panel still renders without a scrollbar
- [ ] With a real shadow companion running, trigger a stale-feedback state and confirm the one-row banner reads the narrow wording and is not cut off
- [ ] Verify `.aitask-scripts/monitor/minimonitor_app.py` end-to-end in tmux alongside a live agent, including the `M` multi-session toggle still listing agents from other sessions
