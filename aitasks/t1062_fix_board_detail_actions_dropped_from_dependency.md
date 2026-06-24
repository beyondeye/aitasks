---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [ui]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-24 14:40
updated_at: 2026-06-24 14:46
---

## Problem

In `ait board`, opening a task's detail screen and then opening a **dependency** (or parent/child) task's detail from within it leaves that nested detail screen's actions dead. Repro: open task **968** detail → open its dependency **929_3** detail → press **p** (pick). Instead of picking 929_3, the detail screen bounces back to 968 and nothing happens.

## Root cause

`TaskDetailScreen` (`.aitask-scripts/board/aitask_board.py:3119`) does **not** perform its actions itself — it signals every action to the caller via `self.dismiss(<result>)` and relies on the **caller's result callback** to act on it:

- `pick_task()` → `self.dismiss("pick")` (`:3624`)
- also `"edit"` (`:3490`), `"edit_plan"` (`:3488`), `"rename"` (`:3617`), `"delete_archive"` (`:3621`), `"brainstorm"` (`:3629`), `"reverted"` (`:3474`), `"locked"`/`"unlocked"` (`:3712`, `:3717`)
- bare `self.dismiss()` (`:3483`, `:3733`) = Back/Escape, no result

Only the **top-level board push** wires the callback that interprets these results:

```python
self.push_screen(TaskDetailScreen(focused.task_data, self.manager), check_edit)   # :5336
```

`check_edit` (`:5235`) translates the result into the real action (pick → AgentCommandScreen, edit → editor, etc.; revert/lock/unlock fall through to a granular refresh).

But the **four nested push sites pass no callback**, so every dismiss result is silently discarded and the screen just pops back to the parent detail:

- `DependsField._open_dep` (single dep) — `:1629`
- `DepPickerItem.on_key` (multi-dep picker) — `:2478`  ← the 968→929_3 repro path
- `ParentField` — `:2154`
- `_reload_detail_screen` — `:1805`

## Scope — general, not pick-only

Because all actions share the `dismiss(<result>)` channel, **every** action is broken from a nested (dependency/parent/child) detail, not just pick: pick, edit, edit-plan, rename, delete/archive, brainstorm, revert, lock/unlock. Only Back/Escape works (no result). Fixing only the pick site would leave 7 other actions broken.

## Fix direction (structural)

Route all four nested push sites through a single app-level helper (e.g. `KanbanApp.open_task_detail(task)`) that **always** pushes `TaskDetailScreen` wired to a result handler, so a callback-less push becomes impossible.

**Key subtlety:** the existing `check_edit` is a closure over `focused` — a board `TaskCard`. A dependency may be filtered out or off-board, so there is no card to key off. The generalized handler must:
- act on the **dismissed screen's `task_data`** (the dependency), not a board-focused card;
- use a card-independent refresh (the current granular-refresh branch at `:5321`–`:5335` assumes `focused.task_data`/`focused.column_id`/`refresh_columns`);
- replicate the pick path correctly (pick opens an `AgentCommandScreen` in a tmux window with `on_pick_result` → `run_aitask_pick`, `:5260`).

## Acceptance criteria

- Opening a dependency/parent/child task detail from within another detail and pressing pick actually picks that nested task (repro: 968 → 929_3 → p picks 929_3).
- The same nested-detail path works for edit, edit-plan, rename, delete/archive, brainstorm, revert, lock/unlock — each acts on the nested task.
- The fix is structural: a single callback-wired helper used by all four push sites (`:1629`, `:1805`, `:2154`, `:2478`), so no future push site can drop results.
- Refresh after a nested-detail action does not assume a focused board card (works when the nested task is filtered/off-board).
- Back/Escape from a nested detail still simply returns to the parent detail.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-24T13:20:38Z status=pass attempt=1 type=human
