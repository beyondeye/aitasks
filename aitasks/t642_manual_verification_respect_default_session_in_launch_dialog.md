---
priority: medium
effort: medium
depends: [640]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [640]
created_at: 2026-04-24 15:44
updated_at: 2026-04-24 15:44
boardidx: 60
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t640

## Verification Checklist

- [ ] Config respected on first open: in a project configured with `tmux.default_session: aitasks_mob`, with both `aitasks_mob` and `aitasks` tmux sessions running, open `ait board`, press `p` on a task. Dialog's session dropdown must default to `aitasks_mob`.
- [ ] No cross-project leak: Open `ait board` in project A (default_session `aitasks`), press `p`, pick `aitasks`, dismiss. Switch to project B (default_session `aitasks_mob`), open `ait board`, press `p`. Dialog must default to `aitasks_mob`, NOT `aitasks`.
- [ ] Per-project memory within same project: In project B, open dialog, switch session to a different live session (e.g. `aitasks_other`), confirm. Close dialog, reopen in same project B. Dialog must default to `aitasks_other` (last-used wins over config default).
- [ ] Fallback when config session not live: Kill the session named in `default_session`. Reopen the dialog — it must fall back to a live session (first in list), not crash.
- [ ] Window per-project memory: launch a task into an existing window, dismiss, reopen dialog in same project. Window dropdown should default to the remembered window when that window is still alive and the caller did not pass `default_tmux_window`.
- [ ] Create TUI (n on board) also respects default_session: verify the same fix applies when launching via `ait create` from the board, not just pick.
- [ ] Monitor launch dialog: open `ait monitor`, trigger an agent launch. Same dialog, same priority order — verify default_session is respected there too.
- [ ] TODO: verify .aitask-scripts/lib/agent_command_screen.py end-to-end in tmux
