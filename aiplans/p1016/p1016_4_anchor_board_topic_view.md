---
Task: t1016_4_anchor_board_topic_view.md
Parent Task: aitasks/t1016_anchor_task_topic_grouping.md
Sibling Tasks: aitasks/t1016/t1016_1_*.md, aitasks/t1016/t1016_2_*.md, aitasks/t1016/t1016_3_*.md
Archived Sibling Plans: aiplans/archived/p1016/p1016_*_*.md
Worktree: aiwork/t1016_4_anchor_board_topic_view
Branch: aitask/t1016_4_anchor_board_topic_view
Base branch: main
---

# Plan — t1016_4 Board: anchor field + by-topic view

Surface `anchor` on the board: a group-by-anchor "by-topic" view (modeled on the
inflight view) + an editable anchor field in the detail screen. Depends on
t1016_1. Ships the board-feature doc row and the headless board test.

## Key design rules

- **`topic_key`(task)** = `anchor` if set; **elif child → parent's topic_key**
  (parent.anchor or parent id) — display-time fallback so legacy parent+children
  trees cluster with NO migration; else own id.
- **Grouping**: bucket by `topic_key`; bucket size **>= 2** → a topic lane
  (label = title of the task whose own-id == key; archived/absent root → id or
  first member's title; id stays a stable key). Singleton buckets collapse into
  one **"Ungrouped"** lane.
- **Editable anchor persists via** `aitask_update.sh --batch <id> --anchor <val>`
  (task-id field shells out like DependsField/ChildrenField — NOT the CycleField
  save_with_timestamp path).
- Defer "re-anchor whole group" action.

## Steps

1. `board/task_yaml.py`: scalar `anchor` normalization in `parse_frontmatter`
   (t-prefix `\d+_\d+`; preserve parent ints / already-`t`). Keep `anchor` OUT of
   `BOARD_KEYS` (semantic, not layout).
2. `board/aitask_board.py`:
   - `topic_key` (with child→parent fallback) + pure `group_tasks_by_topic(tasks)`
     returning ordered `(label, [tasks])` lanes + an "Ungrouped" lane per the
     grouping rule. Keep import-testable (no widget deps).
   - By-topic base view: `ViewSelector.BASES` entry; binding `y` +
     `action_view_bytopic`; `_set_base_filter("bytopic")` branch (~L4697);
     `refresh_board` re-bucket branch (~L4402) building `TopicColumn`s from
     `group_tasks_by_topic`; `TopicColumn` (model on `InFlightColumn` ~L1186);
     optional `TopicTaskCard` topic border (override `_priority_border_color`
     ~L1178); `apply_filter` branch (~L4514, bytopic shows all eligible).
   - `AnchorField` in `TaskDetailScreen.compose()` (mirror DependsField) → on save
     shell out to `aitask_update.sh --batch <id> --anchor <val>`; reload task.
3. `website/content/docs/tuis/board/reference.md`: add the `by-topic` base-view
   row (key `y`) to the Base filters table.

## Verification

- `tests/test_board_topic_group.py` (new, pure): root + followups + inherited
  children cluster; LEGACY anchorless child groups with parent via fallback;
  anchorless singleton → "Ungrouped"; archived/absent root id is a stable lane key.
- `tests/test_board_topic_view.py` (new, headless pilot, mirrors
  `tests/test_board_view_filter.py`): `app.run_test()` → `pilot.press("y")` →
  TopicColumn(s) render; `apply_filter` hides non-matching under search.
- `task_yaml.py` scalar-normalization unit test.
- `bash tests/run_all_python_tests.sh`.
- Live multi-screen UX → aggregate manual-verification sibling t1016_5.

## Post-Implementation
Step 9 applies on completion. This is the last code child — verify the parent's
remaining children list before archival. Record in Final Implementation Notes the
final keybinding chosen and any inflight-view divergences.
