---
priority: medium
effort: low
depends: []
issue_type: performance
status: Ready
labels: [monitor, minimonitor, performance]
anchor: 2034
created_at: 2026-10-16 08:01
updated_at: 2026-10-16 08:01
---

Measure how much of a minimonitor's and a monitor's CPU goes to tmux scanning
(discovery, `capture-pane`, `strip_ansi`, prompt classification) versus Textual
rendering, before the shared status server is built (see the parent task).

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
of the Go server (child 5) but not the single-idle-clock gain.
