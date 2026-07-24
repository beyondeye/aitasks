---
priority: medium
effort: medium
depends: [1225]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1225]
created_at: 2026-07-24 16:12
updated_at: 2026-07-24 16:12
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1225

## Verification Checklist

- [ ] In `ait board`, focus a task, press `p`, edit the command in the dialog (e.g. append `--model haiku`), choose the direct Run action — the terminal that opens must carry the edited command, not `aitask_codeagent.sh invoke pick <n>`
- [ ] Open a task's detail screen, choose pick from there, override the agent/model via the (A)gent control, then Run — the launched command must reflect the override
- [ ] In `ait board`, press `n` (create), edit the command in the dialog, then Run — `ait create` must launch with the edited command
- [ ] Launch brainstorm from a task, edit the command in the dialog, then Run — the brainstorm TUI must launch with the edited command
- [ ] On an In-Flight task, press `g` (resume), override the profile via the (E)dit control, then Run — the launched command must carry the profile override
- [ ] Cancel `ait create` and quit the brainstorm TUI after launching them via Run — no "Code agent invocation failed" toast may appear (non-zero exit is an ordinary cancel there)
- [ ] With no terminal emulator available (suspend path), run a pick from the dialog — after the agent exits, the board must reload tasks and restore focus to the originating card
- [ ] Confirm the tmux launch tab is unaffected: edit the command, launch into tmux, and verify the pane runs the edited command as before
