---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [monitor, minimonitor, tmux]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1957
followup_kind: upstream_defect
created_at: 2026-10-13 13:17
updated_at: 2026-10-13 13:22
---

## Origin

Spawned from t1957_2 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/monitor_core.py:2246-2250 — get_pane_option uses show-options -pqv and treats rc 0 as a verified read, but tmux answers a MISSING pane with rc 0 and empty output under -q (measured on tmux 3.7c, pinned by tests/test_trails_focus_mailbox_live.py), so a vanished pane reads as (True, "") "verified unset" — the t1451 failure shape its docstring says the tuple exists to prevent`

## Diagnostic context

While building the `ait trails` focus mailbox (t1957_2), a probe against a real,
isolated tmux server (3.7c) showed:

- `show-options -p -q -v -t %999 @opt` (pane does not exist) → rc 0, empty output.
- `show-options -p -v -t %999 @opt` (no `-q`) → rc 1, "no such pane".
- `show-options -p -v -t <live pane> @unset` (no `-q`) → rc 1, "invalid option".
- `display-message -p -t %999 '<fmt>'` → rc 0, empty line.

So with `-q` the rc cannot tell "option unset" from "pane gone", and without
`-q` it cannot tell "pane gone" from "option unset" either. t1957_2 solved it by
reading `display-message -p -t <pane> '#{pane_id}\t#{@opt}'` and trusting the
answer only when the echoed pane id matches the requested one (see
`read_trails_focus_request` in `.aitask-scripts/lib/agent_launch_utils.py`).

`MonitorCore.get_pane_option` documents `(True, "")` as a *verified* "this
option is not set" and `(False, "")` as "tmux could not answer". Its consumer is
minimonitor's shadow-freshness check (`compute_shadow_staleness`, t1104/t1451).
A shadow pane that vanished between discovery and the read is reported as
verified-unset rather than as a failed read.

## Suggested fix

Read via `display-message -p -t <pane> '#{pane_id}\t#{<option>}'` and return
`(False, "")` unless the echoed pane id equals `pane_id`; keep `(True, value)`
otherwise. Add a live isolated-tmux test for the missing-pane case (pattern:
`tests/test_trails_focus_mailbox_live.py`). Check what the staleness consumer
should do with a vanished shadow pane before changing its input.
