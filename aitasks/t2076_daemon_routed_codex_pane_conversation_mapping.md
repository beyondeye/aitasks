---
priority: low
effort: high
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
created_at: 2026-10-20 10:33
updated_at: 2026-10-20 11:05
---

## Origin

Split out of t2046, which was closed with no change to the stamped freeze path
because t2047 (00322dab0) made it moot. **Closing t2046 does not mean
daemon-routed codex can be resumed.** It cannot today; such an agent restores
only by re-picking its task. This task is the missing capability.

## Problem

A codex TUI started by hand, without `-c tui.alternate_screen=never` (the
framework's own launches carry it in `CODEX_TUI_OVERRIDES`), can be routed
through the shared app-server daemon. The framework then has no positive evidence
of which conversation belongs to which pane:

- The TUI process holds no `rollout-*.jsonl`. The daemon holds every routed
  pane's rollout, so the freeze's `codex_session_for_pid` returns `MISS_NO_MATCH`,
  and the daemon's fds alone cannot attribute a session to one pane. Membership
  is not attribution.
- The daemon runs every routed session's SessionStart hook with the `TMUX_PANE`
  of the pane that started it. So since t2047 the hook records nothing when a
  daemon hop sits between the hook and its pane (`aitask_session_hook.sh` §5b).
- Result: no `codeagent_session_id`, no restore, re-pick only. This is documented
  in `website/content/docs/workflows/freeze-and-restore-agents.md` and
  `website/content/docs/concepts/framework-session.md`.

Evidence: t2040's and t2047's archived plans, Final Implementation Notes (codex
0.163.0, isolated tmux, throwaway CODEX_HOME):
- the daemon argv is `…/bin/codex app-server --listen unix:// --managed-daemon`;
- `daemon.pid` `processIdentity` (bootId and startTicks) matches the live process;
- the daemon is a child of its starter while that pane lives, and is reparented
  afterwards.

## Candidate evidence sources to evaluate (measure before choosing)

- The TUI's client socket to `$CODEX_HOME/app-server-control/app-server-control.sock`
  (control socket name found in the 0.163.0 binary): map the TUI's socket to its
  peer with sock_diag (`ss -xp` / netlink). Then find which thread the daemon
  serves on that connection.
- The daemon's own state: `$CODEX_HOME/app-server-daemon/loaded-threads.json`, or
  an app-server protocol query that lists threads per client.
- A codex-side change or option that exposes the thread id to the TUI process,
  or makes the daemon run hooks with the client's environment.

## Acceptance

- The hook or the freeze attributes a session to a pane with **positive,
  pane-specific evidence**, never by membership in the daemon's open rollouts.
- t2046's rules stay in place for anything not positively attributed:
  `MISS_NO_MATCH` clears, and the unstamped fallback does not re-send a
  disproved pane stamp (`tests/test_agent_freeze.py`, `CodexSessionCaptureTests`).
- Live check: two hand-started (daemon-routed) codex panes, one turn each, then
  freeze both. Each record carries its own pane's session, and a restore resumes
  the right conversation in each.
