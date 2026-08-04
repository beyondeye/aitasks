---
Task: t1377_5_board_column_management_dialog.md
Parent Task: aitasks/t1377_minimonitor_pick_column_action_and_board_column_management.md
Sibling Tasks: aitasks/t1377/t1377_1_*.md, aitasks/t1377/t1377_2_*.md, aitasks/t1377/t1377_3_*.md, aitasks/t1377/t1377_4_*.md, aitasks/t1377/t1377_6_*.md
Archived Sibling Plans: aiplans/archived/p1377/p1377_*_*.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# p1377_5 — board ad-hoc column-management dialog

## Goal

One discoverable dialog behind one key covering reorder / delete / merge (add and
edit folded in), wiring up t1377_4's merge engine. Satisfies parent AC4, AC5, AC7.

The gap this closes is **discoverability plus merge**: add / edit / delete already
exist but **no key is bound to any of them** — they are reachable only via the
Ctrl+P palette or the header ✎ button.

## Step 1 — de-duplicate first (NON-OPTIONAL, before adding anything)

`KanbanCommandProvider` duplicates its seven-command list **verbatim** between
`discover()` and `search()`. Adding a command to one and not the other silently
breaks discovery or search. Collapse both onto a single `_COMMANDS` tuple of
`(display, action_attr, help)` **first**, then add commands.

This is `t1243_7`'s §1 mandate, cited to `aidocs/framework/planning_conventions.md`
("Refactor duplicates before adding to them"). t1243_7 is `Ready` behind
`t1243_4 → 5 → 6`, so it has not landed and this child does the refactor.

**Drop a reverse note** into `aitasks/t1243/t1243_7_move_to_column_command.md`
under `## Notes for sibling tasks`: the de-dup landed here; t1243_7 should consume
`_COMMANDS` rather than redo it.

## Step 2 — `ColumnManageScreen`, bound to `e`

`e` is verified free in `KanbanApp.BINDINGS`. **Do not take `m` (reserved by
t1243_7) or `G` (t1243_12).**

- Footer-visible with a short label.
- `check_action` gating: visible in the kanban views, **hidden** in In-Flight /
  By-Topic / By-Trail, which render derived lanes rather than columns — mirroring
  how `w` is column-scoped.

Contents, reusing existing screens (**AC7 forbids a second picker inside the
board**):

| Operation | Reuse |
|---|---|
| reorder | ↑/↓ in the dialog list → rewrite `column_order` wholesale → `save_metadata()` (generalises the one-step `_shift_column`) |
| add / edit | `ColumnEditScreen` via `_handle_column_edit_result` |
| delete | `DeleteColumnConfirmScreen` |
| merge | `SelectionList` multi-select of sources (the `WorkReportColumnSelectScreen` shape) → `ColumnSelectScreen` for the destination → `merge_columns` |

List `unordered` as a merge source only when it holds tasks (precedent:
`action_collapse_column` hand-injects the synthetic entry).

Keep the palette entries working through `_COMMANDS`, and add "Manage Columns" /
"Merge Columns".

Style with the existing `#column_edit_dialog` / `.picker-dialog` ids;
`.picker-dialog` already carries the t1366 scroll/focus fix. The new modal lives
inside an already-manifested module, so `register_all_known_bindings()` picks up its
scope automatically — **no `KNOWN_BINDING_SOURCES` edit**.

### Partial-merge reporting (contract from t1377_4)

Branch on `result.complete`:

- complete → `notify("Merged N tasks into <dest>")`
- partial → `severity="warning"`, naming counts and the retry, e.g.
  `"Merged 7 of 9 into Backlog — 2 failed, re-run to finish"`

A bare "Merged" toast on a partial merge is the specific failure this clause exists
to prevent.

## Step 3 — Workstream C migration note

`boardgroup` does not exist yet — `BOARD_KEYS == BOARD_LAYOUT_KEYS ==
("boardcol", "boardidx")` today. When `t1243_10` lands,
`settings.collapsed_groups` holds composite `"<col>/<slug>"` keys whose column half
must be rewritten on rename and re-pointed on delete/merge; t1243_10 already owns
that multi-owner lifecycle.

**Drop a reverse note** into
`aitasks/t1243/t1243_10_group_collapse_and_filtering.md` naming `merge_columns` and
the fixed `update_column` as two additional owners of the collapsed-key lifecycle.

**Do not pre-build group handling here** — the user confirmed at parent planning
that this deliverable lands *before* Workstream C with a documented migration.

## Tests

| Case | Assertion |
|---|---|
| `_COMMANDS` parity | `discover()` and `search()` expose the same set, **with a negative control** (add a command to one path only; show the guard fails) |
| reorder | `column_order` persisted and survives a reload |
| merge e2e | through the real `KanbanApp` on `tests/lib/board_fixture.py` |
| **partial merge** | takes the **warning** notification path, not the success one |
| footer visibility | per view via `check_action`, including ≥1 view where `e` must be **hidden** |

## Verification

```bash
bash tests/run_all_python_tests.sh    # read ONLY the last line
```

Live acceptance (real terminal) is covered by the manual-verification sibling — a
footer/visibility claim is only proven by an actual capture.

## Coordination — read before starting

`t1243_4` was `Implementing` in `aitask_board.py` during parent planning
(`apply_filter`, `refresh_git_status`), and `t1243_5` will later rewrite movement
actions to async. Different regions from column management, but this child edits
`BINDINGS`, `CSS` and `KanbanCommandProvider`.

**Re-read `aitask_board.py` immediately before implementing**, grep for symbols
rather than trusting line numbers, and keep the new UI **strictly above the render
layer** so t1243_5 does not rewrite it. Stage explicit paths; never `git stash` /
`git add -A` in this shared checkout.

## Notes for sibling tasks

*(fill in at Step 8 — record the `_COMMANDS` tuple shape for t1243_7, and the final
`e` binding + `check_action` predicate for t1377_6's docs.)*
