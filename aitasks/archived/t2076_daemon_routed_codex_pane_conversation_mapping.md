---
priority: low
risk_code_health: medium
risk_goal_achievement: high
effort: high
depends: []
issue_type: enhancement
status: Done
labels: [codex, frozen, session_persistence]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2040
implemented_with: claudecode/opus5_5
created_at: 2026-10-20 10:33
updated_at: 2026-10-20 15:54
completed_at: 2026-10-20 15:54
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2077** id=2026-10-21T12:33:08Z.e395f5fff7898142159958ea from=t2077 from_verified=yes at=2026-10-21T12:33:08Z base=ba4fde3822c67af2fb3aee56c36a16d673b3e1d2 base_branch=main dirty=yes host=omg16
>
> | Advisory, from t2077 (code committed as ab1704c89 on main). The codex observation path t2076 builds on has changed. Tree-relative claims as of that commit:
> | 
> | 1. New public `agent_sessions.codex_observe_pid(pid) -> (session_id, transcript, cli_id, miss)` resolves the codex ONCE and reads session and model from that same process. The process is either the pane process, or the pane shell's single FOREGROUND codex child (`_codex_child_of_shell`: foreground = child pgrp == terminal tpgid). `codex_session_for_pid` is now a 3-tuple wrapper over it, and `codex_resume_evidence` is unchanged.
> | 2. `agent_freeze._observe_codex_session` calls only `codex_observe_pid`. It no longer calls `codex_session_for_pid` or `codex_process_model`, so tests and stubs must patch `codex_observe_pid`; the `tests/test_agent_freeze.py` harness already does.
> | 3. Every fd-based answer is re-validated after all fd targets and rollout headers have been read. A process that exits or changes mid-read now yields `MISS_NO_PROCESS`, never `MISS_NO_MATCH`, including at depth 0. Through a shell, `MISS_NOT_CODEX` is issued only from a consistent, re-read snapshot.
> | 4. `_capture_codex_session` now observes records that hold an id under NO agent kind (a hook that ran outside the wrapper). A positive observation records `codex/<model>` or clears the id; a miss leaves the record alone.
> | 
> | Unchanged: `_CODEX_DISPROVING_MISSES` / `_CODEX_FD_DISPROOFS`. A daemon-routed, hand-started codex still reads `MISS_NO_MATCH` from its TUI process.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-20T12:42:05Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-20T12:48:36Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-20T12:54:05Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:e8a79b4d2c3adfff

> **✅ gate:risk_evaluated** run=2026-10-20T12:54:05Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2076/risk_evaluated_2026-10-20T12:54:05Z-risk_evaluated-a1.log`
