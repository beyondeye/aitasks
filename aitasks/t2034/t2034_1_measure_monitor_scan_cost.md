---
priority: medium
effort: low
depends: []
issue_type: performance
status: Implementing
labels: [monitor, minimonitor, performance]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2034
implemented_with: claudecode/opus5_5
created_at: 2026-10-16 08:01
updated_at: 2026-11-03 13:38
---

Measure how much of a minimonitor's and a monitor's CPU goes to tmux scanning
(discovery, `capture-pane`, `strip_ansi`, prompt classification) versus Textual
rendering, before the shared status server is built (see the parent task and t2037).

The 2026-10-16 snapshot (7 minimonitors at 0.8–3.1% CPU each, 4 monitors at
0.9–3.4%, ps lifetime averages; 69–432 MB RSS) does not separate the two.

## Do

- Profile one live minimonitor and one live monitor for a few minutes each with
  a sampling profiler attached to the PID (e.g. `py-spy`; a throwaway install,
  not a framework dependency).
- Report the share of samples in the producer path
  (`discover_panes_with_shadows_async`, `capture_all_classified_async`,
  `_tmux_async`, `classify_content`, `strip_ansi`) versus Textual
  compose/render, and the rate of `capture-pane` calls across all running
  instances.
- Repeat with 1 agent and with several agents to confirm the growth with the
  number of agents.

## Output

Numbers and method recorded in the plan file, so they are archived with the
task. If scanning turns out to be a small share, say so: that lowers the payoff
of the Go server (t2038) but not the single-idle-clock gain.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-03T11:38:04Z status=pass attempt=1 type=human
