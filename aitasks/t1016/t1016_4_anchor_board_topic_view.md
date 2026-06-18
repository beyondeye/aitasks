---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: high
depends: [t1016_3]
issue_type: feature
status: Implementing
labels: [aitask_board, child_tasks]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-17 13:36
updated_at: 2026-06-18 16:45
---

## Context

Board child of t1016 (anchor task topic grouping). Makes the `anchor` field
visible and editable where tasks are picked: a group-by-anchor "by-topic" board
view plus an editable anchor field in the task detail screen. Modeled on the
existing **inflight** alternate-layout view.

Depends on t1016_1 (the `anchor` field + `aitask_update.sh --anchor` must exist).
This child also owns the board-feature doc row and the headless board test.

## Key design rules (resolved during planning)

- **Group key (`topic_key`)** for a task: `anchor` if set; **elif the task is a
  child → its parent's topic_key** (= parent.anchor or parent id) — a display-time
  fallback so legacy parent+children trees (created before anchor existed) cluster
  with NO file migration; else the task's own id.
- **Grouping rule**: bucket all tasks by `topic_key`. A bucket of **size >= 2**
  becomes a topic lane (label = title of the task whose own-id == key; if that
  task is archived/absent, fall back to the id or first member's title — the id
  stays a stable key). **Singleton buckets collapse into one "Ungrouped" lane.**
  This avoids both a lane-per-root and hidden roots.
- **Editable anchor persists via `aitask_update.sh --batch <id> --anchor <val>`**
  (task-id fields shell out, like DependsField/ChildrenField — NOT the CycleField
  save_with_timestamp path).
- Defer a "re-anchor whole group" action (out of v1).

## Key Files to Modify

- `.aitask-scripts/board/task_yaml.py` — scalar `anchor` normalization in
  `parse_frontmatter` (t-prefix `\d+_\d+` child ids; preserve parent ints /
  already-`t` ids). Keep `anchor` OUT of `BOARD_KEYS`.
- `.aitask-scripts/board/aitask_board.py` — `topic_key` derivation; pure
  `group_tasks_by_topic(tasks)`; `AnchorField` in `TaskDetailScreen`; the
  by-topic base view (selector + binding + `_set_base_filter` branch +
  `refresh_board` re-bucket + `TopicColumn` + optional `TopicTaskCard` +
  `apply_filter` branch).
- `website/content/docs/tuis/board/reference.md` — add the `by-topic` base-view
  row (key `y`) to the Base filters table (ships with the feature).
- Tests (below).

## Reference Files for Patterns

- **Inflight view precedent** in `aitask_board.py`: `ViewSelector.BASES` (~L906),
  binding `i` (~L4214) → `action_view_inflight` (~L4655), `_set_base_filter`
  (~L4697), `refresh_board` re-bucket branch (~L4402-4411), `InFlightColumn`
  (~L1186), `InFlightTaskCard` (~L1153, overrides `_priority_border_color`
  ~L1178), `apply_filter` branch (~L4514). Model `TopicColumn`/`TopicTaskCard`
  and the bytopic branches on these.
- **Scalar normalization**: `task_yaml.py::_normalize_task_ids` (L51-66) — the
  list version; write the scalar analog.
- **Editable task-id field shelling out to aitask_update.sh**: DependsField /
  ChildrenField in `TaskDetailScreen.compose()`; the extension-points checklist
  (`aidocs/framework/aitasks_extension_points.md` L19-22) mandates this pattern.
- **Priority-border infra**: `TaskCard._priority_border_color` /
  `_idle_border_style` / `on_mount`/`on_blur` (~L1116-1138) — reuse for optional
  topic borders.
- **Headless board test harness**: `tests/test_board_view_filter.py` —
  `app.run_test(size=(160,48))` + `pilot.press()` + `pilot.pause()` +
  `app.query(TaskCard)`; chdir-to-REPO_ROOT setUpClass; runner
  `tests/run_all_python_tests.sh` (PYTHONPATH includes board/ + lib/).

## Implementation Plan

1. `task_yaml.py`: normalize scalar `anchor` on parse.
2. `aitask_board.py`: add `topic_key` (with the child→parent fallback) and a pure
   `group_tasks_by_topic(tasks)` returning ordered (label, [tasks]) lanes + an
   "Ungrouped" lane, per the grouping rule above. Keep it import-testable (no
   widget deps).
3. Add the by-topic base view: `ViewSelector.BASES` entry; binding `y` +
   `action_view_bytopic`; `_set_base_filter("bytopic")` branch (reload like
   inflight if needed); `refresh_board` branch that builds `TopicColumn`s from
   `group_tasks_by_topic`; `TopicColumn` (model on `InFlightColumn`); optional
   `TopicTaskCard` topic border; `apply_filter` branch (bytopic shows all eligible
   cards, like inflight).
4. Add `AnchorField` to `TaskDetailScreen.compose()` → on save shell out to
   `aitask_update.sh --batch <id> --anchor <val>`; reload the task after.
5. Add the board-reference doc row.

## Verification Steps

- `tests/test_board_topic_group.py` (new, pure): root + its `--followup-of`
  followups + inherited children cluster in one lane; a LEGACY anchorless child
  groups with its parent via the fallback; an anchorless singleton → "Ungrouped";
  an archived/absent root id remains a stable lane key.
- `tests/test_board_topic_view.py` (new, headless pilot, mirrors
  `test_board_view_filter.py`): `app.run_test()` → `pilot.press("y")` → assert
  TopicColumn(s) render and `apply_filter` hides non-matching cards under search.
- `task_yaml.py` scalar-normalization unit test (extend an existing board parse
  test or add one).
- Run `bash tests/run_all_python_tests.sh`.
- Live multi-screen UX (visual grouping, detail-edit round-trip, archived-root
  rendering) → covered by the aggregate manual-verification sibling t1016_5.

## Notes for sibling tasks

- `group_tasks_by_topic` and `topic_key` are the pure, testable core — keep board-
  widget logic thin around them.
- The child→parent `topic_key` fallback is display-time only (the file may have no
  `anchor:`); that is intentional and is what lets legacy trees group without
  migration.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-18T13:45:33Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-18T13:45:34Z status=pass attempt=1 type=machine
