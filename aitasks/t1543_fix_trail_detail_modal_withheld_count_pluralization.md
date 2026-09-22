---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_board, tui, trails]
anchor: 1210
followup_kind: review_finding
created_at: 2026-08-17 17:17
updated_at: 2026-08-17 17:17
---

## Problem

`TrailDetailScreen._sections`'s `more(count, noun)` helper
(`.aitask-scripts/board/aitask_board.py:4106-4109`) pluralizes by appending
`"s"` to the **end** of the noun phrase it is handed:

```python
def more(count, noun):
    if count:
        plural = "" if count == 1 else "s"
        text.append(f"… {count} more {noun}{plural}\n")
```

Two of its three call sites pass a multi-word phrase whose head noun is at the
**start**, so for any count other than 1 the rendered line is ungrammatical:

| call site | noun passed | rendered at count > 1 |
|---|---|---|
| `other_drift` | `reason for other entries` | `… 4 more reason for other entriess` |
| `other_obs` | `observation not affecting this entry` | `… 24 more observation not affecting this entrys` |
| `other_evidence` | `evidence record` | `… 54 more evidence records` (correct) |

Only the third reads correctly, and only because its head noun happens to sit
last. The first produces a doubled `s`; the second produces `entrys`. Both also
leave the head noun (`reason`, `observation`) singular against a plural count.

Observed live during t1505_5 manual verification, in the By-Trail detail modal
on both standing artifacts — `art:trail-shadow-review-loop` (entry
`aitasks#1294`: 4 withheld drift reasons, 24 withheld observations) and
`art:trail-gates-framework-landing` (entry `aitasks#635_24`: 14 withheld
observations).

## Fix

Stop deriving the plural by suffixing the whole phrase. Either take both forms
explicitly:

```python
def more(count, singular, plural=None):
    ...
```

called as `more(n, "reason for other entries", "reasons for other entries")`,
or pluralize the head noun and keep the qualifier fixed. Cosmetic only — no
behaviour reads these strings, and the counts themselves are correct.

## Verification

Open the By-Trail detail modal on an entry with more than one withheld
observation and more than one withheld drift reason (either standing artifact
qualifies) and read the `… N more` lines. Worth pinning the three rendered
strings in `tests/test_board_bytrail_view.py`, which already covers this modal
— a count of exactly 1 hides the bug, so any pin must use a count > 1.

## Origin

Surfaced by t1505_5, the manual verification of t1505_1..4. The defect is in
text added by t1505_2 (entry-first detail modal). No t1505_5 checklist item
asserts grammaticality, so all 20 items passed; this is recorded separately
rather than as a verification failure.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1794_9** id=2026-09-22T06:08:05Z.70917a7d1d5f28ae0f65350e from=t1794_9 from_verified=yes at=2026-09-22T06:08:05Z base=4d1ea067ed3bb714e196165c4aea241d1b00e73a base_branch=main dirty=yes host=omg16
>
> | t1794 split the board mono-file `.aitask-scripts/board/aitask_board.py`
> | (children t1794_1..8 landed; the last extraction is commit 387d8cb20). Any
> | `aitask_board.py:NN` anchor in your body or plan is STALE: aitask_board.py is
> | now ~6.8k lines (was ~13.7k) and most classes moved. Re-derive by symbol
> | (grep the class/function name), not by line number.
> | 
> | Where symbols live now (.aitask-scripts/board/):
> | - aitask_board.py: KanbanApp (incl. action_* handlers, _do_archive,
> |   action_work_report, sync), Kanban/InFlight/Topic columns, board-only modals
> |   (delete/archive/rename/commit/settings/cross-repo/gate choice), key map,
> |   command palette provider
> | - board_task_manager.py: TaskManager (paths injected as required kw-only
> |   tasks_dir / metadata_file / gates_registry_file; no module-global reads)
> | - board_task_model.py: Task, MoveResult, MergeResult
> | - board_workflow_phase.py: workflow-phase / in-flight derivation
> | - board_widgets.py: TaskCard, ColumnHeader, PickerItem, badge/marker helpers,
> |   LoadingOverlay
> | - board_detail_screen.py: TaskDetailScreen + its field widgets and pickers
> | - board_column_dialogs.py: ColumnEdit/Select/Manage/MultiSelect screens,
> |   ColorSwatch, column confirm dialogs
> | - board_trail_view.py: pure trail rendering - trail cards/columns, trail
> |   modals (TrailDetailScreen, TrailSelectScreen, summary), TRAIL_CSS
> | - board_trail_screen.py: TrailScreenMixin (all By-Trail actions),
> |   TRAIL_BINDINGS, TrailHost protocol, TRAIL_ACTION_CAPABILITIES
> | - trails_app.py: the new stand-alone `ait trails` TUI, hosting the same mixin
> | 
> | Rules a change to these files must keep (full text: contracts C1-C3 in
> | aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md; note that the
> | line ranges in that plan's "Target file map" are PRE-split mono-file anchors,
> | not current ones):
> | 1. Flat imports between board/*.py (`import board_x`), never `board.`-qualified.
> | 2. No board/*.py other than aitask_board.py reads TASKS_DIR / METADATA_FILE /
> |    etc. at import time - moved code receives paths by parameter.
> | 3. No board/*.py imports aitask_board.
> | All three are test-enforced (tests/test_board_package_contract.py,
> | tests/test_board_fixture_harness.py). Test patch targets follow the symbol:
> | patch board_task_manager.X (etc.), not aitask_board.X, for moved code.
> | 
> | Advisory, not an instruction: tree-relative claims above are as of the base
> | SHA this note records.
> | 
> | Your body (aitasks/t1543_fix_trail_detail_modal_withheld_count_pluralization.md) cites stale line anchors: aitask_board.py:4106-4109; symbols you name -> current module: TrailDetailScreen -> board_trail_view.py.
