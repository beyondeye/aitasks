---
priority: low
risk_code_health: low
risk_goal_achievement: medium
effort: low
depends: []
issue_type: chore
status: Implementing
labels: [aitask_monitormini, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1326
implemented_with: claudecode/opus5_5
created_at: 2026-07-30 10:34
updated_at: 2026-10-15 12:47
boardidx: 109568
---

## Context

Risk-mitigation "after" task for **t1326**, paying down width debt that predates
it.

The minimonitor agent row renders at ~38 usable columns (`#mini-pane-list`,
40-wide pane minus `padding: 0 1`) and the worst case already overflows. Verified
by a real 40-column tmux capture during t1326:

```
 ★ ● ◆ ≈ agent-pick-1326-lon…  PROMPT
 123s
```

t1326 was **column-neutral** — it added 2 columns for the always-on ★/☆ pair and
took 2 back by cutting the window-name cap from 22 to 20 — so it did not create
the overflow, but it did consume the remaining headroom. A third always-on glyph
(t1343's conflict advisory is a candidate) has nowhere to come from.

## Goal

Audit the row across every glyph combination at 40 columns and decide, explicitly,
what gives way — rather than cutting the name cap again by reflex.

Combinations to cover: mark (★/☆) × shadow (absent / `◆` / `◆!`) × compare-mode
(`≈` / `=`) × status (`Active` / `IDLE 123s` / `PROMPT 123s` / `DONE 123s`) ×
name length.

## Acceptance criteria

- [ ] A test asserts the **composited screen** at width 40 (not `widget.render()`,
      which cannot reveal Rich ellipsising) for the worst-case combination
- [ ] The row's column budget is documented in one place with the arithmetic, so
      the next glyph has a stated budget to fit rather than a guess
- [ ] A decision is recorded on what sheds first when a glyph is added — name tail,
      status verbosity, or a second line
- [ ] Any change is confirmed by a real tmux capture at 40 columns, not only by
      Textual's headless renderer

## Incoming scope: cell-width-aware truncation (from t1382)

t1382 added an `other` section to the minimonitor pane list and, in review,
confirmed a defect that applies to **every** row in this file: the name/command
caps use `len()`, which counts code points rather than terminal cells. A window
name of 20 double-width (CJK / emoji) characters occupies 40 cells, so the row
overflows and Rich clips it — measured on the new `other` row at 36 code points
/ **64 cells** against the 38-cell budget.

It was dispositioned as a follow-up and routed here rather than fixed in t1382,
because `_agent_card_text` has the identical flaw and is the far more common
row: fixing one without the other would leave the audit's budget claim untrue.

- [ ] Replace the `len()`-based caps in `_agent_card_text` and
      `_other_card_text` with cell-width-aware truncation
      (`rich.cells.cell_len` / `set_cell_size`)
- [ ] Add a double-width case to the budget assertions — see the note in
      `test_row_fits_the_column_budget` (`tests/test_minimonitor_other_section.py`),
      which currently pins single-cell input only and says so
- [ ] State the budget in **cells**, not code points, wherever it is documented

## Reference

- `_agent_card_text` in `.aitask-scripts/monitor/minimonitor_app.py` (`max_name`)
- `format_pane_status` / `format_state_dot` / `format_shadow_glyph` /
  `format_mark_glyph` in `.aitask-scripts/monitor/monitor_shared.py`
- `_HINT_WIDTH_BUDGET = 38` in `tests/test_minimonitor_own_task_info.py`
- `_screen_text` / `_flat` in `tests/test_minimonitor_pick_by_number.py` — the
  composited-screen assertion helpers

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1996** id=2026-10-15T06:25:01Z.d9f526725902a77e3379566d from=t1996 from_verified=yes at=2026-10-15T06:25:01Z base=ec65fcc158699810929a8a20252406e681260d72 base_branch=main dirty=yes host=omg16
>
> | t1996 (code commit ec65fcc15 on main) bounds the elapsed counter in the agent
> | status badge, which changes one input to this audit's worst-case row.
> | 
> | - `format_pane_status` now renders the counter through `format_elapsed_compact`
> |   (`.aitask-scripts/monitor/monitor_shared.py`), capped at 4 characters and
> |   rounded down: `0s`…`999s`, then whole minutes `16m`…`240m`, then whole hours
> |   `4h`…`999h` (capped).
> | - So the widest status is 11 cells: `PROMPT 999s` / `PROMPT 240m` /
> |   `PROMPT 999h`. `IDLE <t>` / `DONE <t>` are at most 9 and 9.
> | - This task's body uses `PROMPT 123s` (and `IDLE/DONE 123s`) as the status in
> |   its worst-case row and matrix (lines ~25-26, ~40). That example is still
> |   within the bound, but the true worst case is now the fixed 11-cell
> |   `PROMPT 999s`, no longer an open-ended number of digits.
> | - The name-cap comment in `minimonitor_app.py` (~line 2371) was rewritten to say
> |   the same; the name cap itself (20) was not changed.
> | 
> | Advisory context only — whether this changes the audit's matrix or layout
> | options is this task's own call.

> **👁 note:read** id=2026-10-15T06:37:32Z.e8369c2f3edce66d9ff43320 by=t1351 at=2026-10-15T06:37:32Z mode=explicit ids=2026-10-15T06:25:01Z.d9f526725902a77e3379566d

> **✉ note:t2001** id=2026-10-15T12:19:20Z.3f95291fb6a945d4e0396100 from=t2001 from_verified=yes at=2026-10-15T12:19:20Z base=cbfc74fed97d56da9204ea726daa43e69323b943 base_branch=main dirty=yes host=omg16
>
> | Shared-working-tree overlap with t2001 (advisory; moment-relative, as of this note).
> | 
> | t2001 (review loop must not send keys into a shadow pane in tmux copy-mode) is about to edit,
> | in the SAME working tree, two files that also carry your uncommitted hunks:
> | 
> | - .aitask-scripts/monitor/minimonitor_app.py: _fire_shadow_recheck, _submit_shadow_prompt,
> |   _loop_hold, _loop_auto_disarm, the ACTION_FIRE branch of _service_review_loop, __init__ loop state,
> |   and the monitor_core import block
> | - .aitask-scripts/monitor/monitor_core.py: a new query_pane_mode() next to capture_raw_tail
> |   (+ a re-export line in tmux_monitor.py)
> | 
> | Those regions are not the ones you have touched (agent_display_name / match_agent_prefix /
> | row budgets), but a whole-file `git commit -- <path>` from either session would sweep in the
> | other's uncommitted work. t2001 will commit ONLY its own hunks (temp-index whitelist,
> | verified in an isolated snapshot). If you commit those two files before t2001 does, please
> | stage only your own hunks as well.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-15T09:47:43Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-15T12:27:32Z status=pass attempt=1 type=human
