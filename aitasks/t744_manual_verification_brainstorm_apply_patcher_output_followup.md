---
priority: medium
effort: medium
depends: [743]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [743]
created_at: 2026-05-04 17:23
updated_at: 2026-05-04 17:23
boardidx: 100
boardcol: manual_verifications
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t743

## Verification Checklist

- [ ] - TUI auto-apply (live case): launch a fresh patcher agent from `ait brainstorm <num>` → Action tab → "Patch plan"; wait for status to flip to Completed; verify the IMPACT banner stays clear (NO_IMPACT case) AND the dashboard refreshes to show the new node within ~5 s.
- [ ] - TUI restart recovery: stop a brainstorm TUI while a patcher's status is `Completed` but its node hasn't been applied; relaunch `ait brainstorm <num>`; verify auto-apply fires within ~5 s of session load (no manual action required).
- [ ] - IMPACT_FLAG banner: drive a patcher whose change updates a `component_*` value (e.g., swap a library); verify the persistent banner shows "IMPACT_FLAG — Explorer regeneration recommended" with the affected dimensions text inline; confirm the banner does NOT clear after a session reload.
- [ ] - Ctrl+Shift+R retry: induce an apply failure (e.g., delete the source proposal); confirm the failure banner suggests the `ait brainstorm apply-patcher …` retry command; restore the proposal and press Ctrl+Shift+R; verify the apply succeeds and the banner clears.
- [ ] - CLI fallback round-trip on a real session: pick any session with a stuck patcher; run `ait brainstorm apply-patcher <num> <agent> <source>`; confirm `APPLIED:<id>:<impact>` and that the TUI shows the new state on next launch.
- [ ] - Idempotency on re-run: run the CLI fallback twice; the second invocation must print `APPLY_FAILED:node <id> already exists` (exit 1).
