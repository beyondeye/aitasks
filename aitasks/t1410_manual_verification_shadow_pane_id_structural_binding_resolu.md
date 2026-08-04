---
priority: medium
effort: medium
depends: [1319]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1319]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-08-04 13:34
updated_at: 2026-08-04 13:43
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1319

## Verification Checklist

- [ ] Spawn a real shadow from minimonitor (`e`) against a live agent; confirm its first argument-free `aitask_shadow_capture.sh` call resolves the bound followed pane with no error (the launch->stamp race at the real agent-CLI layer)
- [ ] With that shadow running, open the concern picker; confirm concerns still appear — `capture_shadow_text` now passes `--any-pane`, and a regression here surfaces as a silent "no concerns" rather than an error
- [ ] Run `ait monitor` from a personal tmux session on a different socket than `-L ait`; confirm the shadow preview column and the concern picker still work (the cross-server case the `--any-pane` opt-out exists for)
- [ ] From inside a live shadow pane, run `./.aitask-scripts/aitask_shadow_capture.sh <a-wrong-pane-id>`; confirm it exits 2, names both the requested and the bound pane, and captures nothing
- [ ] Invoke `/aitask-shadow %<id>` manually from OUTSIDE the framework's tmux server; confirm the agent follows the split recovery (ask the user to confirm the pane, then re-run with `--any-pane`) and does NOT livelock between the no-arg and explicit forms
- [ ] TODO: verify .aitask-scripts/monitor/monitor_core.py end-to-end in tmux (interactive surface touched by this task)
