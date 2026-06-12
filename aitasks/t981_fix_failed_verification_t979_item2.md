---
priority: medium
effort: medium
depends: [978]
issue_type: bug
status: Ready
labels: [verification, bug]
created_at: 2026-06-12 11:28
updated_at: 2026-06-12 11:28
---

## Failed verification item from t978

> Detach tmux (prefix d) → resize the terminal much wider → reattach (tmux attach) → confirm the minimonitor pane snaps back to ~40 columns instead of staying proportionally wide (the reported bug)

### Source

- **Manual-verification task:** `aitasks/t979_manual_verification_pin_minimonitor_pane_width_on_resize_fol.md` (item #2)
- **Origin feature task:** t978
- **Origin archived plan:** `aiplans/archived/p978_pin_minimonitor_pane_width_on_resize.md`

### Commits that introduced the failing behavior

- a97bc6445 bug: Pin minimonitor companion pane width on resize (t978)

### Files touched by those commits

- .aitask-scripts/lib/tmux_exec.py
- .aitask-scripts/monitor/minimonitor_app.py
- .aitask-scripts/monitor/tmux_monitor.py
- tests/test_tmux_exec.py

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t979 item #2.
