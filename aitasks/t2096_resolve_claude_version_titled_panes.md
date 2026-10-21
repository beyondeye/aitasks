---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [minimonitor, monitor, macos, agent_keys]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-21 12:49
updated_at: 2026-10-21 14:44
---

## Symptom

Pressing `L` in minimonitor while following a Claude Code agent refuses with:

    Auto-recheck unavailable for '2.1.306' — the recheck loop supports claude, codex, opencode

Claude **is** in the supported set, so the message is self-contradictory to the user.

## Root cause

On macOS, current Claude Code (2.1.x) sets its process title to its version
string, so tmux reports `#{pane_current_command}` = `2.1.306` (or whatever version
is running). Verified live on 2026-10-21:

| pane | pane_current_command | `ps -o comm= -p <pane_pid>` | children |
|------|----------------------|-----------------------------|----------|
| %4, %10 | `2.1.306` | `claude` | none |
| %13 | `2.1.306` | `claude` | `caffeinate` |
| %2 | `2.1.281` | `claude` | none |
| %12 (codex) | `codex` | `codex` | `codex-code-mode-host` |

`lib/agent_keys.py:agent_key_from_pane` has two rungs:
1. `agent_key_from_command(current_command)` — basename `2.1.306` → no match.
2. One level of **children** of `pane_pid` — none, or `caffeinate` → no match.

It never asks for the pane process's **own** comm, which is `claude`. Result:
`agent_key == ""`, and `minimonitor_app.py:action_toggle_review_loop`
(`review_loop.review_loop_agent_supported(followed_key)` branch, ~line 4578) shows
the "unsupported" refusal with the raw pane command interpolated.

The module docstring of `agent_keys.py` ("claude → native ELF binary → pane
reports `claude` ✓", measured 2026-08-13) is now stale.

## Blast radius (beyond the `L` key)

Every consumer of `agent_key_from_pane` currently gets `""` for Claude panes on
this machine, silently degrading:
- prompt-pattern scoping (t1467) in `monitor/monitor_core.py` (`_classify_batch`,
  and call sites ~3046/3141/3233) — falls back to the unscoped flat list;
- workflow-phase live tiers (`lib/workflow_phase.py`);
- shadow-agent key resolution (`_resolve_shadow_agent_key`) — a Claude shadow
  would hit "could not resolve the shadow's agent yet";
- `lib/pane_state_probe.py`.

## Fix

1. In `agent_key_from_pane`, add a rung between the command and the children:
   resolve the pane pid's **own** comm (`ps -o comm= -p <pane_pid>`, basename,
   via the same portable pattern as `_child_commands`, same 2s timeout and the
   same positive/negative cache semantics). Keep the "ambiguity suppresses" and
   one-level-of-children rules intact.
2. In `action_toggle_review_loop`, distinguish `followed_key == ""` ("could not
   identify the followed agent from pane command '…' — try again") from a
   resolved-but-unsupported key; the current wording claims non-support for what
   is really a resolution miss (`""` means "could not resolve", per the
   agent_keys contract).
3. Update the stale measurement table in the `agent_keys.py` docstring.
4. Tests in `tests/test_agent_keys.py`: a pane whose command is a version string
   and whose own comm is `claude` resolves to `claude`; children-ambiguity and
   cache behaviour unchanged. Run the pre-fix control (the new test must fail on
   unfixed code). Check `tests/lib/fake_agent_binary.py` and existing fixtures
   that use `pane_pid=0` / pid 1 so the new rung does not make them
   host-dependent (see t1116's note on pid-1 fixtures).
5. Verify live: arm `L` against a real Claude pane with a shadow.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-21T11:44:06Z status=pass attempt=1 type=human
