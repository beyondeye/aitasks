---
priority: medium
effort: low
depends: []
issue_type: test
status: Implementing
labels: [aitask_monitor, aitask_monitormini, tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1382
followup_kind: upstream_defect
created_at: 2026-09-02 23:13
updated_at: 2026-09-03 09:37
---

## Origin

Spawned from t1686 during Step 8b review.

## Upstream defect

- `tests/test_kill_agent_pane_smart.sh` — the live fixture builds its companion
  as the **LAST** pane, where dropping a helper changes no count, so it could
  never observe the last-record drop that silently killed windows containing a
  live agent. Left as-is by t1686 (it remains a valid fallback-rung control),
  but its ordering is why the defect below survived undetected.

The defect it could not see (found and **already fixed** in t1686, listed here
only as the diagnostic chain):

- `.aitask-scripts/monitor/monitor_core.py:3053` — `kill_agent_pane_smart`
  iterated `stdout.strip().splitlines()` over a `list-panes` format already
  ending in `#{@aitask_shadow_target}`, which is empty on every non-shadow pane.
  `str.strip()` acts on the whole buffer, so it ate the trailing tab of the
  **last** record; that record was then short a field and silently `continue`d.
  When the dropped pane was the only other real agent,
  `count_other_real_agents` returned 0 and the **whole window was killed with a
  live agent still in it.**

## Diagnostic context

From t1686's Final Implementation Notes. The defect was invisible to the live
suite purely because of fixture ordering: `make_window()` creates pane 0 (agent),
splits pane 1 (agent), then splits pane 2 (the companion). tmux lists panes in
index order, so the companion is always last — and a *helper* being dropped from
`records` changes no count, because it was going to be excluded anyway. The one
ordering that discriminates (an unmarked **real agent** listed last) is never
built.

t1686 demonstrated the defect live on an isolated tmux server: with the pre-fix
`strip()`, `kill_agent_pane_smart` on one of two real agent panes returned
`killed_window=True` and destroyed the surviving agent; with the fix it returned
`killed_window=False` and the sibling survived.

## Suggested fix

Add a case to `make_window()` (or a second fixture window) in which an **unmarked
real agent** pane is created last, then assert that killing a sibling collapses to
`kill_pane` and the last pane survives. Keep the existing companion-last case — it
is the fallback-rung control. The synthetic equivalents already exist as
`KillAgentPaneSmartTests::test_counts_an_unmarked_last_real_agent` and its paired
control in `tests/test_monitor_companion_filter.py`; this task carries the same
discrimination into the live-tmux tier.
