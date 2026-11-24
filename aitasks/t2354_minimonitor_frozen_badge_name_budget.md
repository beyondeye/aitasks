---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitormini, frozen_agents, tui]
gates: [risk_evaluated]
anchor: 2337
created_at: 2026-11-24 18:52
updated_at: 2026-11-24 18:52
---

## Symptom

In `ait minimonitor` (default 40-column pane), a frozen agent's row now carries the
t2337 sitrep badge after the word `frozen` (`drop ok`, `drop ok, triage`, ...). Together
with the `☆F` prefix and the `frozen` word, the badge leaves too few cells for the window
name, so the task id is cut off. Observed live:

```
 ☆F pick-226…  frozen drop ok, triage     <- agent-pick-2261_2
 ☆F pick-2295  frozen drop ok, triage     <- fits only because the id is short
```

## Root cause

`MiniMonitorApp._agent_card_text`, frozen branch
(`.aitask-scripts/monitor/minimonitor_app.py`, ~line 3029), subtracts the badge width
from the name budget:

```python
name = self._row_name(snap, prefix, cell_len("frozen")
                      + frozen_sitrep_badge_width(sitrep_state))
```

Row 1 at the default width is 36 cells (`_row_budget`). The frozen row spends them as:

| state | prefix `☆F␠` | gap | `frozen` | badge | **name room** |
|---|---|---|---|---|---|
| no badge (`None`) | 3 | 2 | 6 | 0 | 25 |
| `drop ok` | 3 | 2 | 6 | 8 | 17 |
| `unharvested` | 3 | 2 | 6 | 12 | 13 |
| `drop ok, triage` / `, review` / `, closed` | 3 | 2 | 6 | 16 | **9** |
| `drop ok, triaged` | 3 | 2 | 6 | 17 | **8** |

This breaks the module's own floor `_MIN_NAME_CELLS = 12` ("`pick-NNNN_NN`: the
commonest launch name") and rule 3 of the "What gives way" list in the row-budget
comment block (~lines 243-310): a glyph that breaks the floor sheds verbosity, never the
name's tail, because the tail is where the task id lives. The t2337 plan
(`aiplans/archived/p2337_frozen_agent_sitrep_harvest_triage_badge.md`) recorded this
risk ("The badge is longer than `frozen`, so window names get a shorter budget on the
40-column minimonitor", severity low, mitigation none). It has now happened.

The test `test_parked_and_frozen_rows_fit` (`tests/test_minimonitor_row_budget.py`
~line 238) never sets a sitrep state, so it covers only the 25-cell case. It checks that
the row fits, not that the name keeps the floor.

The full `ait monitor` (`monitor_app.py` ~line 1947) is unaffected: it does not clip the
window name on that row.

## Proposed fix (to confirm in planning)

When a sitrep badge is shown, drop the literal `frozen` word. The bold-cyan `F` in the
prefix already says the agent is frozen, and only frozen rows ever get a badge, so the word
repeats the `F`. Keep `frozen` when the state is `None`, so a row with no verdict yet
still has a word after the name. Name room with the badge, no `frozen` word:
`drop ok` 23, `unharvested` 19, `drop ok, triage`/`review`/`closed` 15,
`drop ok, triaged` 14. Every state stays at or above `_MIN_NAME_CELLS`.

Alternatives to weigh in planning if dropping the word is rejected:
- shorten the badge's secondary words (`, triage` → `+tri`);
- shed the badge's secondary segment only when the name would go below the floor
  (this changes the layout from row to row);
- keep the task id when clipping, by cutting the name in the middle or from the head
  instead of the tail.

Decide whether `ait monitor` should drop the word too, so the two TUIs show the same
words, or keep it because it has the room. Whichever is chosen, say so in the code
comment.

## Scope

- `.aitask-scripts/monitor/minimonitor_app.py`: frozen branch of `_agent_card_text`.
  Update the budget comment block: the `frozen` line should show the badge shapes and
  their name rooms.
- `.aitask-scripts/monitor/monitor_shared.py`: `format_frozen_sitrep_badge` /
  `frozen_sitrep_badge_width`, if the word moves into or out of the badge helper, and
  `monitor_app.py` if the two TUIs are kept the same.
- `tests/test_minimonitor_row_budget.py`: add a check that the name keeps at least
  `_MIN_NAME_CELLS` for **every** key of `FROZEN_SITREP_BADGES`, plus `None`, at the
  default width, so that a new badge state that is too wide fails the test. Include
  `agent-pick-2261_2` and `agent-pick-1351_12` as names that must survive whole at
  width 40.
- Docs: `website/content/docs/workflows/freeze-and-restore-agents.md` ~line 76 says
  "After the word `frozen`, the row shows what...". If the word goes away on badged
  rows, update this sentence and run `python3 check_links.py --build` in `website/`.
  Sibling task **t2351** (badge doc gaps) edits the same passage, so coordinate
  through a note.

## Out of scope (seen during exploration, not addressed here)

- Child task titles keep the child index when the title comes from the filename:
  `t1912_7_stats_branch_retrospective` renders as `7 stats branch retrospective`
  (`monitor_core.py` ~line 7139, `stem.split("_", 1)`).
- A frozen agent whose task is an archived child (`pick-2261_2`) shows no title row.
