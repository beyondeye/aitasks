---
priority: medium
effort: medium
depends: [1518]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1518]
anchor: 1159
followup_kind: manual_verification
created_at: 2026-08-17 12:50
updated_at: 2026-08-17 12:50
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1518

## Verification Checklist

- [ ] In a real tmux session run `ait minimonitor` following a real Codex agent with a shadow launched via `e`, press `L`, and confirm it ARMS (banner `⟳ auto-recheck ARMED`) rather than refusing
- [ ] Repeat with a real OpenCode followed agent: press `L` and confirm it arms
- [ ] With the loop armed and the Codex agent parked at an exec-approval dialog, move the option cursor with the arrow keys and confirm NO recheck line is injected into the shadow pane
- [ ] Same for OpenCode's permission dialog — its selection is rendered as ANSI styling only, so it exercises a different code path (NO_CHANGE before any boundary lookup)
- [ ] Let the followed agent do real work and settle at a dialog; confirm EXACTLY ONE recheck line lands in the shadow and the banner progresses to `⟳ recheck #N sent — waiting for shadow`
- [ ] Confirm the arm refusal names the supported set (`the recheck loop supports claude, codex, opencode`) rather than the old "Claude-only for now" — reproduce with a pane whose agent does not resolve, e.g. the measured `node` case
