---
priority: medium
effort: medium
depends: [876]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [876]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-31 16:34
updated_at: 2026-05-31 17:19
boardidx: 120
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t876

## Verification Checklist

- [ ] In any TUI, press `?` and confirm a `shared.tui_switcher` group lists the 11 quick-jumps (App Linker, Board, Monitor, Code Browser, Settings, Statistics, Syncer, Brainstorm, Explore, Git, New Task)
- [ ] Open Settings → Shortcuts tab (`s`) and confirm the `shared.tui_switcher` scope and its quick-jump rows appear
- [ ] Rebind a quick-jump (e.g. `shortcut_board`) in the editor, relaunch, and confirm the switcher overlay's bottom hint AND per-item shortcut label show the new key, and pressing it jumps to Board
- [ ] Confirm escape / enter / ←/→ still work inside the overlay and are NOT listed as editable rows (structural keys stay fixed)
- [ ] Rebind the shared "open switcher" key (e.g. j → k), relaunch, and confirm `k` both opens AND closes the switcher (toggle mirrors the open key); escape still closes
- [ ] Verify cross-session switcher routing with multiple aitasks tmux sessions (←/→ session nav + quick-jumps across sessions) — automated coverage (test_tui_switcher_multi_session.sh) could not run inside tmux during implementation
- [ ] TODO: verify .aitask-scripts/lib/tui_switcher.py end-to-end in tmux (overlay open/close, switch, hint rendering)
