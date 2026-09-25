---
priority: low
effort: low
depends: []
issue_type: refactor
status: Implementing
labels: [framework]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1869
implemented_with: claudecode/opus5_5
created_at: 2026-09-25 07:48
updated_at: 2026-09-25 12:43
---

## Context

t1874 added a gateway helper for whole-session targets on window-typed `-t`
(`list-panes -s`): `tmux_exec.session_scope_target()` and its wrapper
`agent_launch_utils.tmux_session_scope_target()`, both emitting `=<s>:`.
The rule is documented in `aidocs/framework/tmux_gateway.md` ("Target
formatting").

t1847 (landed in d05ef7241) shipped `.aitask-scripts/lib/agent_reopen.py`
with a private `_session_scope(session)` that returns
`tmux_window_target(session, "")`. That is the same value, and it is correct,
but it is a second definition of a gateway rule.

## Change

- Replace `_session_scope` in `agent_reopen.py` with the gateway helper
  (`tmux_session_scope_target`), keeping its docstring rationale only as a
  pointer to `tmux_gateway.md`.
- Call sites as of d05ef7241: `list-panes -s` (~line 313) and `list-windows`
  (~line 376). `list-windows` is session-typed, so either `session_target` or
  the scope helper works there. Pick one deliberately and say which in the
  commit.
- Run `tests/test_agent_reopen.py` and `tests/test_frozen_reopen_live.sh`.
  The live test's raw `list-panes -s -t "=C"` (~line 202) is a test-side call
  with the same bare-form flaw; switch it to `=C:`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-25T09:43:47Z status=pass attempt=1 type=human
