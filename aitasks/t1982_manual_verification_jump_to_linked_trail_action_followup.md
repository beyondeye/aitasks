---
priority: medium
effort: medium
depends: [1957_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1957_4]
anchor: 1957
followup_kind: manual_verification
created_at: 2026-10-14 12:18
updated_at: 2026-10-14 12:18
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1957_4

## Verification Checklist

- [ ] From `ait trails` in this repo, press `L` on a trail with cross-repo members: the Linked Trails dialog lists the `aitasks_mobile` linked trail, with error rows for thinking_app / thinking_backend (still incomplete, t1978) and the note "Some projects could not be fully searched — the list may be incomplete:"
- [ ] Enter on that row switches the tmux client to the aitasks_mobile session, with the trail focused in its `ait trails` (the running instance, or a new `trails` window)
- [ ] Stop the aitasks_mobile tmux session, then repeat the jump: its session is started first (bootstrap), then the client switches and the trail opens
- [ ] Same `L` flow from `ait board` in the By-Trail view (`z`); `L` is absent from the footer in the other views and while no trail is loaded
- [ ] Version-skew warning visibility: register a scratch copy of an aitasks project whose `.aitask-scripts/board/trails_app.py` lacks `--trail`, with a trail linked to the current one. `L` → pick it → the upgrade warning shows in a dialog in THIS TUI before anything switches. "Stay here" leaves the client in place; "Switch" lands in that project's session with no trail opened. Afterwards run `ait projects remove` on the copy
- [ ] From a terminal outside the aitasks tmux server, the jump only shows the manual command `ait projects exec <project> -- ./ait trails --trail <handle>` and starts no session
