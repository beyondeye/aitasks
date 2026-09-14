---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [tmux, bug]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-14 15:16
updated_at: 2026-09-14 16:06
---

## Observed (t1801 manual verification of t1784, real Claude agent, real store)

A record launched through the wrapper carried `agent_string: claudecode/opus5` /
`agent_kind: claudecode`. After one successful freeze + `restore --all`
(`RESTORED:<id>|hook`, `ack: hook`, `restore_mode: resume`) the SAME record has
`agent_string:` and `agent_kind:` EMPTY. `codeagent_session_id` survived.

## Mechanism

- `lib/agent_restore.py::build_resume_argv` calls `resolve_dry_run_command`
  (`lib/agent_launch_utils.py:~241`), which runs
  `aitask_codeagent.sh --agent-string <rec> --dry-run invoke raw --resume-session <sid>`
  and returns the bare `claude --model … --resume <sid>` argv. The coordinator
  respawns THAT argv, not the wrapper.
- `aitask_codeagent.sh::cmd_invoke` only reaches
  `export AITASK_AGENT_STRING=…` (`:646`) when it execs for real — the same
  dry-run-vs-real gap the acceptance suite header documents for LAUNCH
  (`tests/test_frozen_agents_acceptance.sh:29-33`), now on the RESTORE path.
- The shipped hook (`aitask_session_hook.sh:138`) upserts
  `--agent-string "${AITASK_AGENT_STRING:-}"` = `""`, and
  `lib/agent_sessions.py:729-731` overwrites on any non-None value, so the
  blank clobbers the stored string and `agent_kind` is re-derived as empty.

## Consequences

- A SECOND freeze/restore of the same record calls `build_resume_argv` with
  `agent_string=None` → the project's default agent is used. For a codex agent
  that means `claude --resume <codex-sid>` (the resume shapes differ per agent:
  `codex resume <sid>` vs `claude --resume <sid>`), so the second restore
  relaunches the wrong binary. `build_repick_argv` loses the agent the same way.
- monitor / minimonitor / frozenagent surfaces that show the agent kind read a
  blank after any restore.

## Why the live suites did not catch it

- `tests/test_restore_flows_live.sh` seeds records with `--agent-string` passed
  straight to the hook (`:151-158`), never through the wrapper.
- `tests/test_frozen_agents_acceptance.sh` asserts `agent_string` only after
  LAUNCH (case 1, `:599`); no restore case re-asserts it. Add that assertion to
  case 5 / 6c — it fails today.

## Fix options (pick one, with the pre-fix control above)

1. Respawn through the wrapper for real (`aitask_codeagent.sh --agent-string
   <rec> invoke raw --resume-session <sid>`) so the export path runs — but
   check the `#{pane_pid}` == agent pid invariant (the wrapper `exec`s, t1465).
2. Have the restore coordinator deliver `AITASK_AGENT_STRING=<rec>` as a fifth
   `respawn-pane -e` variable next to the four `AITASK_RESTORE_*` ones.
3. Make the store's upsert treat an EMPTY `--agent-string` as "keep existing"
   (`agent_sessions.py:729`) — defensive, and also covers agents launched by
   hand outside the wrapper.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-14T13:06:02Z status=pass attempt=1 type=human
