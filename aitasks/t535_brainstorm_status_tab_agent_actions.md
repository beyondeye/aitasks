---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [brainstorming, ui]
created_at: 2026-04-13 17:26
updated_at: 2026-04-13 17:26
boardidx: 110
---

In the ait brainstorm TUI status tab, surface useful actions on existing code agents so users can manage them without dropping to the CLI.

Desired actions (at minimum):
- Clean up failed agents (remove entries for agents in Failed state)
- Kill a running agent (send a cancellation / terminate signal via ait crew commands)
- Possibly also: retry a failed agent, or mark a stuck agent as Failed

Currently the status tab is read-only; users have to use 'ait crew ...' manually to clean up or kill agents, which breaks the flow when working inside a brainstorm session.

Suggested approach:
- Add a small action row or key bindings on the status tab that operate on the currently-selected agent row.
- Shell out to existing 'ait crew' commands rather than duplicating mutation logic.
- Confirm destructive actions (kill, cleanup) with a modal.

Relates to parent t461 (interactive launch mode) but is independent — useful regardless of launch mode.
