---
priority: high
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_board, tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: codex/gpt5_5
created_at: 2026-06-15 08:34
updated_at: 2026-06-15 10:57
---

## Problem

In `ait board`, opening a task's detail view and selecting the **Verifies:** line (Enter) opens a dialog to browse the tasks that a manual-verification task verifies. For tasks that are already **archived**, the dialog shows `(not found)` next to the task number instead of the task's info — and pressing Enter on such an item wrongly offers to *remove* the (legitimate) reference.

Observed in a linked repo's board (e.g. `aitasks_mobile` task `t13_9`), but the defect is in the framework board code, not the data — so the fix is single-repo (this framework repo).

## Root cause

`TaskManager.find_task_by_id()` (`.aitask-scripts/board/aitask_board.py:340-349`) searches **only active** task dicts:
- `self.task_datas` — loaded from `aitasks/*.md`
- `self.child_task_datas` — loaded from `aitasks/t*/*.md`

It never searches `aitasks/archived/`, the numbered `_b*/old*.tar.zst` bundles, or the legacy `old.tar.zst`/`old.tar.gz`. Any verified task that has been archived therefore resolves to `None`.

Symptom path:
- `VerifiesField._open_verify()` (`aitask_board.py:1161-1180`): on a `None` lookup it appends `(v_num, None, f"{v_label} (not found)")` — the `(not found)` label.
- `DependencyPickerScreen.on_key` (`aitask_board.py:1759-1777`): pressing Enter on a `None` (archived) item routes to `_ask_remove_dep()`, offering to remove a legitimately-archived reference. This is wrong for archived tasks (they are done, not stale).

Note: the same `find_task_by_id` miss likely affects the `Depends:` line dialog too — verify whether `DependsField` exhibits the same archived-task gap and fix consistently.

## Canonical helpers (reuse — do not reinvent)

Archived-task resolution already exists:
- **Python:** `.aitask-scripts/lib/archive_iter.py` — `iter_all_archived_markdown(archived_dir)` and `archive_path_for_id(task_id)` (computes the numbered `_b<dir>/old<bundle>.tar.zst` path; bundle = id // 100, dir = bundle // 10).
- **Shell:** `.aitask-scripts/lib/task_utils.sh` `resolve_task_file()` — 3-tier lookup (active → archived dir → numbered/legacy tar bundles).

Prefer the Python helper from the board.

## Fix shape

1. Give `find_task_by_id()` (or a new `find_task_including_archived()` fallback) an **archived fallback**, used only when the active lookup misses. Resolve via `archive_iter` so it covers loose archived files, numbered bundles, and legacy archives.
2. Make it **lazy + cached** — scanning tar bundles on every lookup is expensive; only touch archives when the active lookup misses, and cache resolved archived tasks for the board session.
3. Render archived hits as **read-only info** (so Enter opens a read-only detail view), NOT routing to the remove-dependency prompt. Reserve the `_ask_remove_dep()` path for genuinely missing tasks (not found in active OR archived).
4. Apply consistently to both `VerifiesField` and `DependsField` if both share the gap.

## Acceptance

- Selecting a Verifies line whose verified tasks include archived ones shows their title/info (not `(not found)`).
- Enter on an archived verified task opens it read-only; no "remove dependency" prompt for archived tasks.
- Genuinely-missing task IDs still show `(not found)` and still offer removal.
- Board lookup performance is not regressed for the common (active-only) case.

See `aidocs/framework/tui_conventions.md` for board/TUI conventions.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-15T07:58:20Z status=pass attempt=1 type=human
