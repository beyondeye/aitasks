---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [aitask_monitormini, tui, gates]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-08-10 19:14
updated_at: 2026-08-10 22:07
---

## Context

In `ait minimonitor`, an agent row that has a task with a gate ledger renders
**four** lines per card:

```
 ★ ● ◆ ≈ agent-pick-1420      PROMPT 12s
   merge the gates and phase lines
   gates: 3/4 pass, 1 pending
   phase: IMPLEMENT ⏸
```

Both trailing lines are emitted by `_agent_card_text`
(`.aitask-scripts/monitor/minimonitor_app.py:836-842`):

```python
gates = self._gate_cache.summary_for(info)
if gates:
    line1 += f"\n  [dim]gates: {gates}[/]"
phase = workflow_phase.render_phase(self._phase_for_snap(snap, info))
if phase:
    line1 += f"\n  [dim]{phase}[/]"
```

They convey one thing between them — how far along the task's gate workflow is —
and cost two of the four rows in a narrow, tall side column. The full
`ait monitor` **already merges them onto a single line** (the status row,
`monitor_app.py:1579-1595`), and its comment states the split is a minimonitor
width concession:

> Gate summary sits at the END of the status row (row 1) […] (Minimonitor keeps
> it on a separate line; its rows are too narrow to append here.)

That claim was never re-measured against appending the phase to the *gates*
line rather than to the status row.

## Goal

Render the gate summary and the advisory workflow phase as **one** line on the
minimonitor agent row, within the row's cell budget, with a stated shed order
for the cases that still do not fit.

## Measured width evidence

Budget: **38 cells** (`target_width` 40 minus `MiniPaneCard`'s `padding: 0 1`);
these lines carry a 2-space indent, leaving 36 for content. Measured with
`rich.cells.cell_len`:

| candidate | cells | fits |
|---|---|---|
| `  gates: 1/3 pass, 1 pending, 1 failed` (today, worst) | 38 | exactly |
| `  phase: unknown (gate recording off)` (today, worst) | 37 | yes |
| `  gates: 2/2 pass · phase: IMPLEMENT ⏸` | 38 | exactly |
| `  gates: 3/4 pass, 1 pending · phase: IMPLEMENT ⏸` | 49 | **no** |
| `  gates: 1/3 pass, 1 pending, 1 failed · phase: unknown (gate recording off)` | 76 | **no** |
| `  IMPLEMENT ⏸ · 2/2 pass` | 24 | yes |
| `  IMPLEMENT ⏸  3/4 pass, 1 pending` | 34 | yes |
| `  POSTIMPL · 1/3 pass, 1 pending, 1 failed` | 42 | **no** |

Conclusions the implementation should start from:

- A **naive labelled join** (`gates: … · phase: …`) fits only the single best
  case. `Static` wraps rather than clips, so every other case re-wraps to two
  rows — no rows saved, and the wrap point is arbitrary. This is the option to
  reject.
- **Dropping the `gates:` / `phase:` labels buys ~13 cells** and makes the
  common cases fit comfortably. The labels are largely redundant: `IMPLEMENT`
  and `3/4 pass` are each self-describing in context.
- The residual over-budget cases are the verbose ones: multi-part gate summaries
  (`n pending` + `n failed` + `n stale`, from `gate_ledger.format_gate_summary`)
  and the long `unknown (…)` phase strings from `workflow_phase.render_phase`.
  These need an explicit decision, not a wrap.

## Decisions to make (record them in the plan)

1. **Merged format.** Proposed starting point: `<PHASE><⏸> · <gate summary>`,
   phase first (it is the coarser signal), gate counts second.
2. **Shed order when over budget.** Candidates: abbreviate the gate summary tail
   (`1 pending, 1 failed` → `1⏳ 1✗`), shorten the `unknown (…)` phase variants
   *for the narrow surface only*, or drop the gate detail and keep `n/m`.
   Whatever is chosen, state it where the budget arithmetic lives.
3. **Where `render_phase` shortening lives, if any.** `render_phase` is shared
   by both monitor TUIs deliberately ("so the phase reads identically wherever
   it appears"). If minimonitor needs a shorter variant, add a narrow-surface
   renderer rather than shortening the shared one and silently changing
   `ait monitor`.
4. **Docked-panel asymmetry.** `_own_card_text` (the followed-agent panel) shows
   the phase **without** a gate summary. Decide explicitly whether it gains the
   merged line or deliberately stays phase-only, and say which in the docstring
   — that panel has a narrowed static-panel contract (t944 / t1133 / t1322 /
   t1383 / t1420) that must not be widened by accident.
5. **Full monitor.** `ait monitor` is already merged; this task should leave it
   unchanged unless decision 3 forces a shared-code change.

## Acceptance criteria

- [ ] The minimonitor agent row renders the gate summary and the workflow phase
      on a single line; a gated task's card is 3 rows, not 4
- [ ] A task with a ledger but no resolvable phase still renders the gate
      summary alone, and a task with a phase but no counted gate runs still
      renders the phase alone (each half is independently optional today —
      `summary_for` returns `""` for ungated tasks and `render_phase` returns
      `""` when there is nothing honest to say)
- [ ] A test asserts the **composited screen** at width 40 (not
      `widget.render()`, which cannot reveal Rich ellipsising) for the merged
      line, covering: best case, the multi-part gate summary, and the longest
      `unknown (…)` phase variant
- [ ] Widths are asserted in **cells** (`rich.cells.cell_len`), not code points
- [ ] The merged line's column budget and the chosen shed order are documented
      in one place with the arithmetic
- [ ] `ait monitor`'s single-line rendering is unchanged (or, if decision 3
      changed shared code, its rendering is re-asserted)
- [ ] Verified by a real 40-column tmux capture, not only Textual's headless
      renderer

## Blast radius

Small. No test and no website doc pins the `gates: ` or `phase: ` strings on
the minimonitor surface — grep over `tests/` and
`website/content/docs/` found no assertion on either prefix. The advisory phase
signal itself is unchanged: this is presentation only, and the phase must remain
advisory (it never gates a key, a spawn, or a shadow mode — see
`aidocs/framework/shadow_agent.md`).

## Relationship to t1351

`t1351_minimonitor_row_width_audit` owns the **row-1** budget (mark × shadow ×
compare-mode × status × name) and the cell-width-aware truncation fix for
`_agent_card_text` / `_other_card_text`. This task owns rows 3-4 of the same
card. They touch the same file and the same 38-cell budget, so:

- Whichever lands second should reuse the other's documented budget arithmetic
  rather than restating it.
- The composited-screen assertion helpers named in t1351 (`_screen_text` /
  `_flat` in `tests/test_minimonitor_pick_by_number.py`, `_HINT_WIDTH_BUDGET`
  in `tests/test_minimonitor_own_task_info.py`) are the ones to reuse here.

## Reference

- `_agent_card_text`, `_own_card_text`, `_phase_for_snap` —
  `.aitask-scripts/monitor/minimonitor_app.py`
- `MonitorApp._format_agent_card_text` — `.aitask-scripts/monitor/monitor_app.py:1566-1604`
  (the already-merged full-monitor rendering)
- `render_phase` — `.aitask-scripts/lib/workflow_phase.py:510-528`
- `format_gate_summary` — `.aitask-scripts/lib/gate_ledger.py:369-406`
- `GateSummaryCache` — `.aitask-scripts/monitor/monitor_core.py:2960-3062`
