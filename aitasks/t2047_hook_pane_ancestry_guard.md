---
priority: high
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [codex, frozen, session_persistence]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2040
followup_kind: risk_mitigation
created_at: 2026-10-18 09:38
updated_at: 2026-10-19 08:04
---

## Origin

Risk-mitigation ("after") follow-up for t2040, created at Step 8d after implementation landed.

## Risk addressed

goal-achievement — a daemon-routed codex TUI would hand the SessionStart hook the daemon's
environment (wrong or missing TMUX_PANE).

From t2040's plan `## Risk`: "The evidence and the hook timing rest on codex behaviour
measured on one version (0.163.0). The task itself names a future daemon-routed TUI as a
risk to guard: … the hook would run with the daemon's environment — no `TMUX_PANE`, or
another pane's — and could upsert the wrong pane's record. This plan does not guard that.
· severity: medium"

**This is no longer hypothetical. It was measured live in t2040** (codex 0.163.0, Linux,
isolated tmux server, throwaway CODEX_HOME):

- A codex TUI started WITHOUT `-c tui.alternate_screen=never` (for example a bare
  `codex` typed into a pane) was routed through the shared app-server daemon at
  `$CODEX_HOME/packages/app-server-daemon/...`.
- The daemon's environment carried `TMUX_PANE=%1`, the pane that started it. Hooks for
  every daemon-routed session therefore run as pane `%1`. A second hand-started codex's
  SessionStart would read `%1`'s `@aitask_record` and upsert ITS session into `%1`'s
  record. In the measurement it was saved only because `%1`'s record was frozen
  (`UPSERT_REFUSED`).
- Wrapper-launched agents (with `CODEX_TUI_OVERRIDES`, which includes
  `tui.alternate_screen=never`) ran in-process. Their hooks ran as children of the
  pane's own codex process.

## Goal

`.aitask-scripts/aitask_session_hook.sh` must refuse to record anything unless the
pane's `#{pane_pid}` is an ANCESTOR of the hook process:

- walk the hook's parent chain from `$PPID`, bounded to a few levels, with
  `ps -o ppid= -p <pid>` (portable to macOS; read `/proc/<pid>/stat` first where
  available);
- if the pane pid is not found, log to stderr and exit 0, recording nothing (the
  hook's ALWAYS-exit-0 / NEVER-stdout contracts still hold). Recording nothing is the
  fail-safe direction: the freeze engine's fallback upsert covers an unrecorded agent;
- verify that both shapes the framework produces pass: the pane pid IS the agent
  (`env … codex`/`claude` exec through), or the pane pid is a shell that spawned the
  agent;
- the hook tests' tmux stub (`tests/test_session_hook.sh`) must report an ancestor pid
  (e.g. the test shell's own `$$`), plus a negative case where the pane pid is a
  non-ancestor and nothing is upserted or stamped;
- do this in the Claude Code hook first, then check whether other agents' hook surfaces
  need the same.

Interactions: t2046 (the freeze clears a valid hook-recorded id for daemon-routed
codex) is the freeze-side half of the same daemon-routing finding. The two should agree
on how a daemon-routed codex is treated.
