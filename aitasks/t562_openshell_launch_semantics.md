---
priority: low
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [agentcrew]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-15 12:39
updated_at: 2026-04-16 15:07
---

## Context

Sibling task t461_9 registered both `openshell_headless` and
`openshell_interactive` in `VALID_LAUNCH_MODES` and added them to the
`LAUNCHERS` dispatch registry in
`.aitask-scripts/agentcrew/agentcrew_runner.py`. Both launchers
currently raise `LaunchError`:

- `_launch_openshell_headless`: "openshell_headless launch mode is
  not yet implemented — tracked in follow-up task"
- `_launch_openshell_interactive`: "openshell_interactive launch
  mode is not yet implemented — tracked in follow-up task"

The picker modals (`LaunchModePickerScreen`, `AgentModeEditModal`) and
the shell validators already accept both variants, so a user can
configure an agent to use them end-to-end — it just transitions to
`Error` on launch.

## Goal

Implement real launch semantics for both `openshell_headless` and
`openshell_interactive` so that configuring an agent with either mode
actually launches a working process attached to the standard crew
bookkeeping (pid, heartbeat, log file, status transitions).

## Design questions to resolve during planning

- **What is "openshell" concretely?** Proposed: a sandboxed subprocess
  running a shell (bash/zsh, not Claude Code), with the work prompt
  delivered as the shell's initial input or as a preloaded history
  entry so a human operator can inspect and execute it.
- **Headless variant:** pipe the shell's stdout/stderr into the log
  file (same pattern as `_launch_headless`) and run non-interactively.
- **Interactive variant:** spawn a tmux window or fallback terminal
  attached to the shell so a human can drive it (same pattern as
  `_launch_interactive`, including pipe-pane log mirroring and
  `maybe_spawn_minimonitor`).
- **Sandboxing:** chroot? Linux namespaces? bubblewrap? None? Just a
  scoped working directory under the crew worktree? Needs a concrete
  threat model from the user.
- **Prompt delivery:** positional arg, stdin, heredoc, or preloaded
  history entry (`HISTFILE`)?
- **Lifecycle:** does the runner still own the lifecycle (heartbeat,
  status transitions), or is openshell launch fire-and-forget?

## Files to modify

- `.aitask-scripts/agentcrew/agentcrew_runner.py` — replace the two
  stub functions with real implementations, add any shared helpers
  (e.g., `_build_openshell_cmd`).
- `tests/test_brainstorm_crew.py` or a new
  `tests/test_openshell_launch.py` — at least one case per variant
  using a mock shell or a minimal `echo`-based stub.

## Acceptance

- Both `openshell_headless` and `openshell_interactive` launch
  successfully in the e2e canary (no `LaunchError`).
- Headless variant writes shell output to the agent's `_log.txt`.
- Interactive variant integrates with tmux pipe-pane and minimonitor
  the same way `_launch_interactive` does.
- `tests/test_brainstorm_crew.py` (or dedicated test file) has at
  least one passing case per variant.
- Status transitions (`Running` → `Completed` / `Error`) and
  heartbeat files behave the same as existing modes.
