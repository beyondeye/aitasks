---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [sitrep, tui]
gates: [risk_evaluated]
anchor: 2175
created_at: 2026-11-09 10:04
updated_at: 2026-11-09 10:04
---

## Context

Child of t2211 (sitrep two-pane window with the sitrep TUI). These UI refinements were requested by the user after t2211_3 landed (code commit 706bf2f6d; archived plan `aiplans/archived/p2211/p2211_3_sitrep_tui_actions_respawn_launches_board_focus.md`).

t2211_3 added, for task items (`kind=task`, local ref `t<N>[_<M>]`):
- a `Pri/Eff` list column (`hi/lo`);
- Priority / Effort / Task status lines in the details;
- a "Task description" link.

The data comes from the task FILE through `sitrep_tui_model.TaskMeta` / `task_meta()` / `task_metas()`. It is read per store generation in `SitrepTuiApp._apply` (`app._metas`), and fresh when details open (`open_item`).

## Requested refinements

1. **Priority and effort on one line in the item details.**
   - Today `ItemDetailScreen.body_content` prints separate `Priority` and `Effort` lines.
   - Make it one labelled line, e.g. `Priority    high · effort low`. Keep labels styled and values plain (`_field`, `Content.assemble`; t2017 markup safety).
   - Update `LabelledDetailsTests.LABELS` in `tests/test_sitrep_tui_app.py` and the TaskMeta tests in `tests/test_sitrep_tui_actions.py`.

2. **The `d` "Done/dismissed" toggle must be visibly a toggle.**
   - What `d` does: `action_toggle_closed` shows or hides the "Recently done" and "Dismissed" groups. It changes nothing in the store.
   - The user reported that it seems to work only when an item is selected. A pilot probe on 2026-11-09 showed it toggles with no highlight and with focus off the list too.
   - The likely cause: the two groups are appended at the BOTTOM of the list, so on a short pane the change is off-screen. Nothing shows whether they are currently shown either: the footer label stays "Done/dismissed" and there are no counts.
   - Fix:
     - make the state visible: the footer label says "Show done" / "Hide done", and the header shows the hidden counts (e.g. `· 3 done, 2 dismissed hidden`);
     - on show, move the highlight to (and scroll to) the first closed group's first item; on hide, keep the highlight rule `_rebuild_list` already has;
     - first reproduce the user's "only when an item is selected" report in a real pane. If a genuine focus/selection dependency exists (e.g. focus on the situation pane or another widget), fix it there.
   - Tests: a pilot test that `d` toggles from every focus state; that showing makes the first closed item visible (`scroll_visible` / region inside the list's viewport) in a short pane; and that the label/header reflect the state.

3. **Show when a follow-up task was created** (task items that name a local task to pick).
   - Read `created_at` from the task file frontmatter (`YYYY-MM-DD HH:MM`, local time, no zone). Extend `TaskMeta` with `created_at`; never raise on a missing or odd value.
   - Display: the time (`HH:MM`) when it is today, else the date (`YYYY-MM-DD`, or a shorter `MM-DD` when it is the current year — decide and pin it). Both in the list row (a short cell; keep `header_text` / `row_text` aligned by construction from `COLUMNS`, and keep the free text last) and in the details (full value).
   - "Today" uses the TUI's clock seam (`model.resolve_now()` / `AITASK_SITREP_NOW`), converted consistently with the file's local-time value — state the rule. The list cell must update across midnight on the existing age-refresh tick (`_refresh_ages`), without reparsing the store.

4. **Filter the list by labels.**
   - Task items carry labels in their task file's `labels:` frontmatter (extend `TaskMeta` with `labels`).
   - Add a key opening a multi-select label picker. Offer the labels present on the store's task items (optionally `aitasks/metadata/labels.txt`). Applying it filters the main list.
   - Decide and pin what happens to non-task items (triage, decisions, watches, pushes, xrefs) while a filter is active. Proposed: hidden, with the header saying "filtered by: sitrep, tui · N items hidden" and a one-key clear.
   - Follow the existing patterns:
     - `SelectOnClickList` for any new list (a click only selects; Enter opens);
     - `check_action` + `refresh_bindings` for the binding;
     - the `_rebuild_list` highlight-keeping rule;
     - the filter is per-session UI state, never written to the store.
   - Add the key to `sitrep_tui_actions.ACTION_BINDINGS` (or the app BINDINGS) and check collisions with the existing keys `q enter d l s j ? r x R A p b P`.

## Key files

- `.aitask-scripts/sitrep_tui/sitrep_tui_model.py`: `TaskMeta`, `task_meta`, `task_metas`, `COLUMNS`, `header_text`, `row_text`, `pri_eff_cell`, `group_items`.
- `.aitask-scripts/sitrep_tui/sitrep_tui_app.py`: `ItemDetailScreen.body_content`, `_rebuild_list`, `_refresh_ages`, `_render_header`, `action_toggle_closed`, `check_action`, BINDINGS.
- `.aitask-scripts/sitrep_tui/sitrep_tui_actions.py`: `ACTION_BINDINGS`, if the filter key lives there.
- Tests: `tests/test_sitrep_tui_app.py`, `tests/test_sitrep_tui_actions.py` (TaskMetaTests; the fixture rewrites `aitasks/t10_demo.md` with frontmatter).

## Reference patterns

- t2211_8 (readability; archived plan `aiplans/archived/p2211/p2211_8_*`): the NEXT_STEPS table, column header alignment pinned by `content_region.x`, one-line rows.
- t2211_3 (archived plan above), "Notes for sibling tasks": item resolution against the current store, details are snapshots.
- `aidocs/framework/tui_conventions.md`: shortcut scopes, settings overrides, markup-safe rendering.

## Verification

- New and updated pilot tests for each refinement, plus `bash tests/run_all_python_tests.sh --test-dir tests` (read the last line).
- Manual check in a real sitrep window: details line, `d` toggle in a short pane, created date/time on task rows, and the label filter applied and cleared.
- Add the new keys and columns to the t2211_6 docs and the t2211_7 checklist (send each an `ait note`).
