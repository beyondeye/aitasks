---
priority: medium
effort: medium
depends: [t1725_4]
issue_type: enhancement
status: Ready
labels: [syncer, tmux, robustness]
gates: [risk_evaluated]
anchor: 1599
followup_kind: review_finding
created_at: 2026-09-10 15:37
updated_at: 2026-09-10 15:37
---

## Context

Review finding on t1725_4, disposition **follow-up**. `aitask_sync.sh
--require-waiting` (the re-probe in `_commit_group`) and the deferral record's
`pane_state` column decide "the holder is parked on a prompt" from **screen text
alone**: `lib/pane_state_probe.py` captures the pane through the gateway and
classifies it with `monitor_core._classify_one`, scoped by
`agent_keys.agent_key_from_pane(current_command, pane_pid, pane_id)`.

When the agent key is **unresolved** (`""`: a shell, a wrapper, anything that is
not `claude` / `codex` / `opencode` at rung 1 or as a single child at rung 2),
`scope_patterns` removes nothing, so matching runs over the whole flat registry.
A pane that merely *displays* copied agent prompt text (a shell `cat`-ing a
transcript, a pager, a wrapper) therefore reads `waiting_<kind>` and satisfies the
gate.

Bounded today: the gate is reached only by an explicit
`--commit-for-task <id> --require-waiting` for a `self` holder (same verified
user, same host), and the 5a.3 state re-check and 5a.4 publication guard still
apply. Not a likely routine failure, but text is not provenance.

## Consumers of the text-derived state

- `aitask_sync.sh::_commit_group` — the commit gate (the one that matters).
- `aitask_sync.sh::_resolve_holder_pane` → `PROT_PANE_STATE` →
  `DeferredFile.pane_state` (display) and the `_holder_action` stderr line.
- t1725_5's commit-on-behalf offer: the button appears only for `self` rows whose
  `pane_state` is `waiting_*`.

## Goal

A `waiting_*` answer may authorize a commit only when the pane carries **durable
agent provenance**, not just prompt-shaped text. Candidate: a launch-time pane
marker — a pane user option set where agents are launched
(`lib/agent_launch_utils.py::launch_in_tmux`) and read by the probe through the
gateway. Precedent for a pane-scoped user option as an authoritative classifier:
`@aitask_shadow_target` (`aidocs/framework/shadow_agent.md`,
`aidocs/framework/tmux_gateway.md`). A lighter interim step to weigh: refuse the
gate when the agent key is unresolved (note codex panes report `node` and resolve
via rung 2, so that alone does not strand codex).

Decide explicitly whether the **display** `pane_state` keeps the monitor-parity
text classification while only the **commit gate** requires provenance, or both.
Update `aidocs/framework/monitor_idle_and_prompt_detection.md` ("A second
consumer: the sync sweep's holder probe") to match.

## Required regression test

An unrecognised pane showing the AskUserQuestion footer must **not** satisfy
`--require-waiting`: assert `holder_not_waiting`, nothing committed. Never pin
today's `waiting_claude_askuserquestion` answer for such a pane as contract.

- `tests/test_sync_holder_pane_live.sh` already builds exactly this shape — its
  holder pane runs `sh render.sh`, an unrecognised command — so **case E2
  currently commits through the unscoped fallback**. E2 must be reworked to use a
  pane with provenance, and a new case asserts the unrecognised pane refuses.
- `tests/test_pane_state_probe.py::ClassifierTests::test_scoping_is_live` pins
  `waiting_opencode_palette` for an unresolved agent (monitor parity for display);
  revisit alongside the display decision above.

Depends on t1725_4 (introduces `lib/pane_state_probe.py`, the gate wiring and the
live test).
