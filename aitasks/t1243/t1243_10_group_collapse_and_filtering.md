---
priority: high
effort: medium
depends: [t1243_9]
issue_type: feature
status: Ready
labels: [aitask_board, tui, python]
gates: [risk_evaluated]
anchor: 1243
created_at: 2026-07-28 01:16
updated_at: 2026-08-04 10:02
---


## Context

**Child 10 of 14** in the t1243 decomposition (design plan:
`aiplans/p1243_board_task_groups_and_fast_reordering.md` — Workstream C).

Two jobs that share one root cause: **a collapsed group mounts a `GroupHeader`
and none of its member cards.** That breaks filtering (which evaluates mounted
cards), and it makes the persisted collapse key a piece of state with a
lifecycle nobody owns.

**Anchor re-verification (do this first)** — see t1243_1; anchor on symbol names.

## Key files to modify

- `.aitask-scripts/board/aitask_board.py` — `apply_filter`,
  `TaskManager.load_metadata` / `save_metadata` (`collapsed_groups`),
  `update_column`, `delete_column`, and the group operations' collapse-key
  handling.
- `tests/test_board_group_filtering.py` — **new**.

## Reference files for patterns

- `TaskManager.collapsed_columns` property/setter and
  `settings["collapsed_columns"]` — the precedent for a persisted per-user view
  toggle, including how `delete_column` already prunes it.
- `_PROJECT_KEYS = {"columns", "column_order"}` / `_USER_KEYS = {"settings"}` and
  `config_utils.split_config` — **unlisted keys silently fall to the project
  layer**; nested per-user state goes under `settings`.
- `settings["topic_sort_mode"]` in `board_config.local.json` — an existing
  per-user grouping preference in the user layer.
- t1243_4's data-level match predicate and widget-kind-agnostic accumulator —
  this child is the reason they exist.

## Implementation plan

### 1. Unit-level filtering

`apply_filter` evaluates **mounted `TaskCard`s**, derives `cols_with_visible`
from them, and rescues focus only off a `TaskCard` / `EmptyColumnPlaceholder`.
With collapsed groups that breaks four ways at once: filters have no member
widgets to evaluate so a header's visibility is never computed; a column holding
only collapsed groups contributes nothing to `cols_with_visible` and **wrongly
shows its `EmptyColumnPlaceholder`**; and focus resting on a header the pass just
hid is never rescued.

Filter **units, from member data**:

1. **Expanded group** — each member card is evaluated as today. The header is
   visible iff **>= 1 member matches**; non-matching members hide individually.
2. **Collapsed group** — no member widgets exist, so evaluate the members' `Task`
   data directly via t1243_4's shared predicate. The header is visible iff
   **>= 1 member — or >= 1 member's child — matches**, so a collapsed group stays
   findable by a child's text, matching what the expanded view would show.
3. **Collapsed partial match** — the header stays visible and reports the count
   (`▸ perf work (3) · 2 match`). A collapsed group deliberately does **not**
   auto-expand and does **not** hide non-matching members, because none are
   rendered; the count is what tells the user to expand.
4. **Column content** — a visible `GroupHeader` counts as content, so
   `cols_with_visible` includes its column and the empty placeholder stays hidden.
5. **Focus rescue** — `GroupHeader` joins the isinstance tuple that triggers
   `_refocus_column`.
6. **Scoped pass** — `apply_filter(cols=...)` queries `GroupHeader` within the
   scoped columns too, not just `TaskCard`.

### 2. Persisted collapse state

`settings["collapsed_groups"]` — a list of `"<col_id>/<slug>"` — in
**`board_config.local.json`** (the user layer), alongside `collapsed_columns` and
`topic_sort_mode`. Explicitly *persisted*, unlike the in-memory-only
`expanded_tasks`. Runtime saves must **never** write the project layer.

### 3. Collapse-key lifecycle — five owners, no orphans

A composite key goes stale on five transitions; each owning operation updates it:

| Transition | Owner | Action |
|---|---|---|
| Group renamed | group-rename command (t1243_12) | rewrite the slug half; on a confirmed merge, combine |
| Group moved to another column | group lateral / to-edge move (t1243_11) | rewrite the col half; on coalesce, combine and drop the vacated key |
| Last member removed (group dissolved) | removal command (t1243_12) | drop the key |
| Column id renamed | `TaskManager.update_column` (already reassigns `board_col`) | rewrite the col half |
| Column deleted | `TaskManager.delete_column` (already prunes `collapsed_columns`) | re-point the col half to `unordered` — the group survives the move |

**Coalesce key-combination rule:** the destination `"<col>/<slug>"` key wins if
it already exists; otherwise the arriving key's state is adopted under the
destination key; the vacated key is dropped by the same owner.

Plus a **prune-on-load sweep**: drop any key whose `(col, slug)` has no members.
That is the backstop for states no transition caught — e.g. an external
`aitask_update.sh --boardgroup` edit, or a task archived from another checkout.

## Verification

The full filtering matrix, each also in its **scoped-`cols`** variant:

- expanded + search; collapsed + search; **collapsed group matched only via a
  member's child**; base filter; add-on filter; partial match (count badge
  rendered); no match (header hidden); empty-placeholder interaction for a column
  of only collapsed groups; focus rescue off a hidden header.

Collapse state:

- **restart-and-assert after each of the five transitions** — collapse a group,
  perform the transition, reload the manager, assert the collapse state followed;
- stale keys are pruned on load;
- **no project-layer write is ever issued** (assert `board_config.json` is
  byte-identical after any runtime collapse/expand);
- the coalesce key-combination rule, for both "destination key exists" and
  "only arriving key exists".

## Notes for sibling tasks

**Two additional owners of the collapsed-key lifecycle land before this task, via
`t1377_4` / `t1377_5`.**

`t1377_4_column_merge_engine` ships against the pre-`boardgroup` model (this task's
Workstream C had not landed), and the parent's user-confirmed sequencing was
"land before, with a documented migration". Two new call sites now mutate column
config and `settings.collapsed_columns`:

1. **`TaskManager.merge_columns(source_ids, dest_id)`** — N->1 merge. Moves every
   member to the destination with fresh appended indices, removes each source from
   `columns` + `column_order`, and prunes each source's `collapsed_columns` entry.
   `unordered` is allowed as source (config-removal skipped) and as destination.
2. **`TaskManager.update_column`'s rename path** — t1377_4 fixed a latent bug there:
   it migrated `column_order` and every member's `boardcol` but **not** the
   `collapsed_columns` entry, orphaning it. It now migrates that too. The path was
   dead in the UI before t1377_5 made it reachable.

**What this task must extend when it introduces composite `"<col>/<slug>"` keys in
`settings.collapsed_groups`:**

- `merge_columns` must re-point the **column half** of every affected group key to
  the destination, applying this task's coalesce rule ("destination key wins if it
  already exists; otherwise the arriving key's state is adopted under the
  destination name"). Merging two columns can collide two same-slug groups into one
  `(column, slug)` identity — that is exactly the coalesce case.
- `update_column`'s rename must rewrite the column half of those keys as well.

Add both to this task's five-owner collapse-key lifecycle table. `merge_columns`
lives in `board/aitask_board.py` alongside `move_tasks_to_column`; see
`aiplans/archived/p1377/p1377_4_column_merge_engine.md` for its final contract,
including the non-transactional partial-merge / convergent-retry semantics.
