---
priority: medium
effort: medium
depends: [1466]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1466]
created_at: 2026-08-10 17:19
updated_at: 2026-08-10 17:19
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1466

## Verification Checklist

- [ ] Two real /aitask-pick panes, same task: pane B is refused with the live-holder prompt, the prompt does NOT say "crashed", "Pick a different task" is the first option, and the task file + lock are untouched (./ait lock --list still shows pane A)
- [ ] At that prompt choose "Force-claim anyway": the claim succeeds AND no second "Reclaim and continue?" prompt appears afterwards (forced-takeover suppression)
- [ ] Board TUI: press Lock on a Ready task, then launch an agent for that same task from the board — the pick is refused as a live holder (the board's own pane is the anchor); unlocking from the board then lets the pick through
- [ ] Same pane, same session: re-pick a task you already hold (and resume an in-flight one) — the lock refreshes silently with no refusal and no reclaim prompt
- [ ] Unverifiable path: with the tmux gateway unreachable (AITASKS_TMUX_SOCKET pointed at a dead server), re-picking your own held task is refused as unverifiable and needs --force — confirm the message reads as "could not be established", not as a crash
- [ ] Remote lane: run /aitask-pickrem against a task held by a live session — it must abort with the live-holder message and never force-claim
