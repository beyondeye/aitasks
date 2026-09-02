---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Ready
labels: [tui, aitask_monitor, aitask_monitormini, agent_marks]
gates: [risk_evaluated]
anchor: 1685
followup_kind: risk_mitigation
created_at: 2026-09-02 18:35
updated_at: 2026-09-02 18:35
---

## Origin

Risk-mitigation ("after") follow-up for t1685, created at Step 8d after implementation landed.

## Risk addressed

Goal-achievement risk, from `aiplans/archived/p1685_*.md`:

> The task's "roughly eight `PaneCategory.AGENT` sites per app" was resolved by
> exhaustive enumeration, but three sites are deliberately left unchanged
> (`_resolve_shadow_target`, `_switcher_selected_session`, the minimonitor review
> loop). If one is in fact reachable for a parked agent, a hidden agent stays
> actionable in a way the user did not expect. · severity: medium (residual —
> deferred, not closed, by the spawned audit)

t1685 threaded a per-tick parked set through the consumers that partition agents
— the pane list, the session bar, auto-switch, the completed set, the concern
offer and the signature scan. Three `PaneCategory.AGENT` sites were reasoned
about and deliberately left alone. That reasoning was not tested, which is
exactly the gap this task closes.

## Goal

Re-audit the three deferred sites against a **parked** agent and close any that
turn out to be reachable in a way the user would not expect.

1. **`MonitorApp._resolve_shadow_target`** (`monitor_app.py`, the `e` / `E`
   shadow-launch guard). With the `P` filter OFF a parked card is focusable, so
   `e` can target a parked agent. Decide whether launching a shadow beside an
   agent the user has declared they are done watching is coherent, and if not,
   refuse with a message that names the parked state.

2. **`MonitorApp._switcher_selected_session`** (`monitor_app.py`). It reads the
   focused pane's session for TUI-switcher pre-selection. Confirm a parked
   focused card yields a sensible pre-selection rather than nothing, and that
   the filter being on cannot leave it reading a pane with no card.

3. **The minimonitor review loop** (`review_loop.py`, `_service_review_loop`).
   t1685 deliberately did NOT touch it: §7 requires the followed agent to keep
   being watched even while parked, and the loop is bound to that agent. Confirm
   that decision holds end-to-end — the loop must keep firing for a parked
   followed agent — and pin it with a test, because right now nothing fails if
   someone "helpfully" adds a parked exclusion there.

Each site gets either a behavioural test proving the current behaviour is
intended, or a fix plus a test. "Audited and fine" without an executable
assertion does not close this task — the whole point is that the reasoning was
untested.

## Reference

- `aiplans/archived/p1685_park_code_agents_tristate_mark_and_visibility_toggle.md`
  — the parked-set design, the consumer table, and the `## Risk` bullet above.
- `tests/test_monitor_parked_filter.py` — the existing consumer-exclusion suite;
  the natural home for the monitor-side additions.
