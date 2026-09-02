---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [minimonitor, monitor, tmux, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-09-02 09:09
updated_at: 2026-09-02 12:04
---

Agent ordering in `ait minimonitor` follows the tmux **window index** (i.e. the
order windows sit in the session), not the window name. Order the pane list by
tmux **window name** instead, still grouped per tmux session.

## Current behaviour

`monitor_core.pane_sort_key` (`.aitask-scripts/monitor/monitor_core.py:916`) is
the single ordering authority:

```
(pane.session_name, tmux_index_key(pane.window_index), tmux_index_key(pane.pane_index))
```

It is consumed by:

- tmux discovery — `TmuxMonitor._PANE_SORT_KEY` (`monitor_core.py:2041`), applied
  in both `_discover_panes_multi` and `_discover_panes_multi_async`
- `MiniMonitorApp._rebuild_pane_list` (`minimonitor_app.py:2489`)
- `MonitorApp._rebuild_pane_list` (`monitor_app.py:1741`)

t1659 deliberately collapsed these into one key so the two TUIs' lists cannot
drift apart, and pinned that with `cross_tui_order_parity` in
`tests/test_monitor_pane_sort_order.py`.

## Requirement

Replace the **second slot** of the key — `window_index` → `window_name`.
`session_name` keeps leading the key, so per-session grouping (and minimonitor's
session dividers in multi-session mode) is unchanged. `pane_index` stays as the
final tiebreaker.

**The name comparison MUST be natural / numeric-aware, not lexicographic.**
Agent windows are named `agent-(pick|qa|resume|explore|raw)-<id>`, so a plain
string compare puts `agent-pick-10` before `agent-pick-2` — which is precisely
the "jumps back to low numbers part-way down the list" bug t1659 exists to
prevent. Split the name into digit / non-digit runs and compare digit runs
numerically, reusing the same category-slot discipline as `tmux_index_key`
(a category slot, **never** a large sentinel integer — see the `SentinelBoundaryTests`
rationale in the existing test module). Task ids with a child suffix
(`agent-pick-100_1`) must order sensibly against their parent
(`agent-pick-100`).

Ties (two windows with the same name) must still produce a **total,
deterministic** order — fall through to `window_index` and then `pane_index`.

## Design decisions for planning

1. **Shared key vs. minimonitor-only.** The request names minimonitor, but the
   key is single-sourced by design. Changing `pane_sort_key` itself keeps both
   TUIs in parity (preserving the t1659 invariant) and is the recommended route;
   forking a minimonitor-only key would break `cross_tui_order_parity` and
   should only be chosen with an explicit reason.
2. **Config knob.** Optional: expose the choice as `tmux.monitor.pane_order`
   (`window_index` | `window_name`) through `load_monitor_config`
   (`monitor_core.py:3035`). If added, the value has to reach *both* the
   discovery sort and both `_rebuild_pane_list` call sites — `pane_sort_key` is
   currently a module-level function with no config access, so this needs a
   factory or an explicit parameter, not ambient state. Decide during planning
   whether the knob earns its keep or whether name ordering simply becomes the
   behaviour.
3. **Discovery order.** `_PANE_SORT_KEY` also orders discovery output, not just
   the rendered lists. Confirm no consumer (review loop, applink server,
   `count_other_real_agents`) depends on index order before changing it.

## Testing

Extend `tests/test_monitor_pane_sort_order.py` rather than replacing it — its
existing invariants (numeric index comparison, total order on non-numeric input,
cross-TUI parity, the `discriminating_fixture_control` negative control) all
still hold and must keep passing.

Add:

- a fixture of window **names** that separates natural from lexicographic order
  in both directions (e.g. `agent-pick-2`, `agent-pick-9`, `agent-pick-10`,
  `agent-pick-20`), with a negative control proving the fixture discriminates —
  a single-digit-only fixture would pass while proving nothing
- a case pinning that panes stay grouped by session when window names interleave
  across sessions (a name that sorts first in session B must not surface above
  session A's panes)
- a duplicate-name case pinning the deterministic tiebreak
- cross-TUI parity re-asserted under the new key

## Docs

If a config key is added, update `seed/project_config.yaml`,
`website/content/docs/tuis/monitor/reference.md` (the configuration table) and
the inherited-keys list in `website/content/docs/tuis/minimonitor/how-to.md`.
Otherwise document the ordering rule wherever the pane list is described.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-02T09:04:56Z status=pass attempt=1 type=human
