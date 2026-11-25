---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitormini, frozen_agents, tui]
gates: [risk_evaluated]
anchor: 2337
followup_kind: upstream_defect
created_at: 2026-11-25 09:55
updated_at: 2026-11-25 09:55
---

## Origin

Spawned from t2354 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/minimonitor_app.py:3359-3367` — the docked own-agent card's second line `  frozen <YYYY-MM-DDTHH:MM:SSZ> <badge>` is 2+6+1+20+17 = 46 cells against 36 at the default width for `drop ok, triaged`, so it wraps, and `_OWN_PANEL_MAX_ROWS` reserves one row for it (pre-existing from t2337).

## Diagnostic context

t2354 made the frozen-agent sitrep badge replace the word `frozen` on the minimonitor/monitor **list** rows, because word + badge broke the 12-cell name floor (`_MIN_NAME_CELLS`) and cut off the task id. It did not touch the **docked** own-agent card (`MiniMonitorApp._own_card_text`, frozen branch). That card renders:

```
<mark>F <identity>
  frozen 2026-11-24T18:52:00Z drop ok, triaged
```

- The stamp is `agent_sessions._TS_FMT` = `%Y-%m-%dT%H:%M:%SZ` (20 cells).
- The suffix is `monitor_shared.format_frozen_sitrep_badge(state)` (leading space + badge, up to 17 cells; width = `1 + frozen_state_width(state)`).
- Row budget for the docked card is `target_width - 2 (padding) - 2 (indent)` = 36 at the default width 40 (the same derivation as `_own_phase_budget`).
- `_OWN_PANEL_MAX_ROWS` counts ONE row for this line (it replaces the phase line), so a wrapped continuation is hidden by the panel's max-height cap, or it pushes the border.

Any badge of 7+ cells overflows with the full stamp (2+6+1+20 = 29 already).

## Suggested fix

Budget the line like the list rows do: shorten the stamp (e.g. `HH:MM` or `MM-DD HH:MM`, maybe locale-free and still UTC-labelled), and/or apply the t2354 rule (badge in place of `frozen`, since the `F` glyph is on line 1). Then clip to the computed budget with `_clip`. Pin it with a test in `tests/test_minimonitor_row_budget.py` over every `FROZEN_SITREP_BADGES` key plus `None`, at width 40 and with the widest stamp. Update `website/content/docs/tuis/minimonitor/how-to.md` (~line 178, "a second indented line reads a dim `frozen` followed by the timestamp") if the shape changes.
