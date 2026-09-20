---
Task: t1794_8_extract_column_dialogs.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_10_website_docs_trails_tui.md, aitasks/t1794/t1794_11_measure_document_retrospective.md, aitasks/t1794/t1794_12_manual_verification_split_board_monofile_and_standalone_trai.md, aitasks/t1794/t1794_9_notes_to_affected_tasks.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_1_board_package_contract_and_baseline.md, aiplans/archived/p1794/p1794_2_extract_board_widgets.md, aiplans/archived/p1794/p1794_3_extract_trail_view.md, aiplans/archived/p1794/p1794_4_extract_task_model_manager_and_workflow_phase.md, aiplans/archived/p1794/p1794_5_lift_trail_screen_mixin.md, aiplans/archived/p1794/p1794_6_standalone_trails_tui.md, aiplans/archived/p1794/p1794_7_extract_detail_screen.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-20 10:04
---

# p1794_8 — Extract the column dialogs into `board_column_dialogs.py`

Parent plan: `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
(C1, C3, C5 PINNED). The last extraction of the t1794 board mono-file split.

## Context

`ait board` began as a 14,102-line single-file Textual TUI. Children 1–7 of
t1794 carved out the widget layer, the trail view and its App half, the
stand-alone trails app, the three data-layer modules and the task editor;
`aitask_board.py` is now **7,407 lines / 35 classes**. This child moves the last
cohesive cluster — the column-management dialogs — into
`board/board_column_dialogs.py`, leaving `aitask_board.py` holding `KanbanApp`,
the Kanban render paths, the key map / `check_action`, `InFlightTaskCard`, the
task-select screens, the module constants and the three injected helpers: the
shape the parent's acceptance criteria describe.

Behaviour must not change. The column-manage save path is a commit boundary
(`aidocs/framework/tui_conventions.md:347–406`) and moves verbatim.

## Verification finding 1 — the plan's move set is incomplete and must be widened

The existing plan (and the parent's "Target file map") names **six** classes.
Re-derived against the current tree, that set **cannot compile** under the
pinned C1 contract: *"No `board/*.py` may import `aitask_board`"*, guarded by an
AST scan in `tests/test_board_package_contract.py::ImportBackTests`.

`ColumnManageScreen` — which the plan does move — pushes three screens the plan
does **not**:

| pushed at | class | in plan's set? |
|---|---|---|
| `aitask_board.py:2323`, `:2327` | `ColumnEditScreen` | **no** |
| `aitask_board.py:2354` | `DeleteColumnConfirmScreen` | **no** |
| `aitask_board.py:2412` | `MergeColumnsConfirmScreen` | **no** |

Leaving them behind forces `from aitask_board import ColumnEditScreen` in the
new module — a circular import and a direct C1 violation. Independently,
`ColumnEditScreen` is the **sole** consumer of `ColorSwatch` (`:1944`,
`:1949–1952`), which the plan *does* move, so the named set splits a class from
its only caller.

Checked at the pinned SHA `e2f12c499`, this is a naming oversight, not a
boundary decision: the map's range `ColumnManageItem/Screen (:8060–8397)`
already **spans** `MergeColumnsConfirmScreen (:8089)`; only `ColumnEditScreen
(:7839)` and `DeleteColumnConfirmScreen (:7913)` fall outside every named range.

**Correction: the move set is 9 classes.** C1 is pinned; the file map is not.
Moving 9 lands `aitask_board.py` closer to the parent's target shape, not
further from it.

## Verification finding 2 — the `board_columns` import becomes a pure re-export and must NOT be tidied away

After the move, **every** in-file user of the `from board_columns import (...)`
block at `aitask_board.py:407–410` is gone. All uses are inside the move set:

```
1920, 1923-1930, 1943, 1965   ColumnEditScreen   (PALETTE_COLORS, generate_col_id)
2379, 2383-2384               ColumnManageScreen (UNORDERED_ID/TITLE/COLOR)
```

The block must stay anyway, because two things pin it:
- `tests/test_board_columns_seam.py:582` asserts the literal text
  `"from board_columns import"` inside `aitask_board.py`;
- 13 sites in `tests/test_board_column_manage.py` read `B.UNORDERED_ID`
  (`:138, 193, 286, 290, 295, 296, 300, 304, 308, 783, 786, 787, 789`).

A `# noqa`-style comment explaining *why* the now-userless import stays goes in
with the change, and the new pin test asserts it.

## Verification finding 3 — two guards need a new entry; two already cover us

| site | action |
|---|---|
| `tests/test_board_package_contract.py::HeadlessImportTests` (`:798`) | **add** `test_board_column_dialogs_imports_without_the_board`, copying `:851–861` |
| `tests/test_board_fixture_harness.py:1354` | **add** `"board_column_dialogs"` to the anti-vacuity sibling tuple |
| `tests/test_board_fixture_harness.py:350` `MIGRATED_MODULES` | **add** `"test_board_column_dialogs.py"`, as t1794_2/3/4/5 each did for their own pin test. Without it the new test could later regain a canonical `aitask_board` import or a chdir and the strict tier would not notice. |
| `tests/lib/board_fixture.py:213` `BOARD_MODULE_NAMES` | **already lists** `board_column_dialogs` (added pre-emptively in t1794_1) — no edit |
| `lib/shortcut_scopes.py` `KNOWN_BINDING_SOURCES` | **no row.** Six moved classes declare plain `BINDINGS`, but none subclasses `ShortcutsMixin` or sets `_shortcuts_scope` (the only one in the file is `"board"` on `KanbanApp:2547`). The manifest lists only scope contributors — `board_trail_screen.py` exports `TRAIL_BINDINGS` and is deliberately absent. |

`lib/tui_registry.py` (keys on tmux window names), `test_mark_glyphs_single_source.py`
(moved code uses `● ○ █`, no `MARK_*`), `test_no_raw_tmux.sh` (no `tmux` in the
moved ranges; C5 pins all three raw sites in `aitask_board.py`),
`test_board_reference_doc_literals.py` and `test_record_protocol.py` — all
unaffected.

## Move set (9 classes, 3 discontiguous regions, ~590 lines)

| lines | classes |
|---|---|
| `1568–1633` | `ColumnMultiSelectScreen` |
| `1871–2015` | `ColorSwatch`, `ColumnEditScreen`, `DeleteColumnConfirmScreen` |
| `2072–2450` | `ColumnSelectItem`, `ColumnSelectScreen`, `ColumnManageItem`, `MergeColumnsConfirmScreen`, `ColumnManageScreen` |

`DEFAULT_REFRESH_OPTIONS` + `SettingsScreen` (`:2016–2071`) sit between regions 2
and 3 and **stay** — verified to reference no moved class. Likewise
`TaskSelectScreenBase` … `CommitMessageScreen` (`:1635–1870`) between regions 1
and 2. `KanbanCommandProvider` (`:2453`) bounds region 3.

## Why no injection is needed (simpler than t1794_7)

The moved classes call **no module-level `aitask_board` function**. Their host
reach is entirely `self.app.<method>` — runtime lookup on `KanbanApp`, needing
no import: `_column_title` (`:5371`), `_apply_column_edit` (`:6487`),
`_merge_source_columns` (`:6566`), `_report_merge` (`:6576`), plus `notify` /
`push_screen`. All stay on `KanbanApp`.

So unlike `board_detail_screen.py`, this module needs **no keyword-callable
injection** and no `make_*` binder. Everything else resolves from already-shared
modules: the five `board_columns` names; `PickerItem` from `board_widgets`;
`TaskManager` (annotation) from `board_task_manager`. **C2 is trivially
satisfied** — none is `TASKS_DIR`-derived and the module resolves no task
directory.

## Files to modify

**NEW — `.aitask-scripts/board/board_column_dialogs.py`**
Docstring in the `board_detail_screen.py:1–28` house style: what family lives
here (t1794_8); "extracted verbatim … the board re-exports every name, so
`ab.X` keeps resolving; a stub of a name they call must target
`board_column_dialogs`"; a `Contracts` list stating C1 (bare-name, never imports
the board; **no injection needed — the host reach is `self.app`**) and C2
(resolves no task directory); and a note that **the CSS stays in
`KanbanApp.CSS`** (`:2745`, `:2774`) — the board is the only App that pushes
these dialogs (`trails_app.py` uses none, verified), matching the t1794_7
precedent. `WIDGET_CSS`/`TRAIL_CSS` are *not* the model here.

**`.aitask-scripts/board/aitask_board.py`**
Delete the three regions; add the import pair next to the `board_detail_screen`
block (`:164–181`) in the established shape — the comment paragraph, then
`import board_column_dialogs` **plus** `from board_column_dialogs import (…)`.
The bare `import` is what `PatchPairingTests` keys on and what makes
`ab.board_column_dialogs` a live patch target. Keep `:407–410` with its new
"re-export only" comment.

**NEW — `tests/test_board_column_dialogs.py`**
A `MOVED_NAMES` tuple of the 9 names, then **two independent pins** — the
runtime one and the source one, because neither subsumes the other:

1. **Source-level single home (primary).** Reuse the existing shared helper
   `tests/lib/board_single_home.py::_single_home_findings(board_src,
   module_src, MOVED_NAMES, view_label="board_column_dialogs.py")`. Pure `ast`
   over both sources; it reports any name not bound **exactly once** in the new
   module, and any name the board **still binds at module scope**, at whatever
   line. Its own negative controls already live in
   `test_board_trail_view.SingleHomeTests` (`:126–169`) and cover **both**
   orderings — `COPY + IMPORT` and `IMPORT + COPY` — so they need no
   re-authoring.
2. **Re-export identity (secondary).** `ab.X is ab.board_column_dialogs.X` plus
   `__module__`, mirroring `test_board_detail_screen.py:82–104`.

The source check is not redundant with the identity check: as
`board_single_home.py`'s own docstring puts it, *"Re-export identity cannot see
a stale copy left ABOVE the board's import (the import rebinds the name,
identity stays true, the dead duplicate survives)"*. t1794_7 pinned identity
only; t1794_3/\_4 used this helper, and that is the stronger precedent to follow.

Plus a pin for finding 2 — the board still re-exports the five `board_columns`
names though nothing in it uses them (`_imported_from(board_src,
"board_columns")` from the same helper module).

**`tests/test_board_package_contract.py`**, **`tests/test_board_fixture_harness.py`**
— the two additions in finding 3.

## C3 sweep — empty, proven rather than assumed

The concrete command, with every name spelled out — the 9 moved classes plus
every module-global the moved bodies resolve through the board's namespace:

```bash
grep -rnE 'patch(\.object)?\(\s*(B|ab|self\.ab|aitask_board)\s*,\s*"(ColorSwatch|ColumnEditScreen|DeleteColumnConfirmScreen|ColumnSelectItem|ColumnSelectScreen|ColumnManageItem|MergeColumnsConfirmScreen|ColumnManageScreen|ColumnMultiSelectScreen|PALETTE_COLORS|generate_col_id|UNORDERED_ID|UNORDERED_TITLE|UNORDERED_COLOR|PickerItem|TaskManager)"' tests/
# → exit 1, no matches
```

**Positive control** (same regex, generic name class) — proves the pattern can
match, so the empty result above is a real empty set and not a broken pattern:

```bash
grep -rnE 'patch(\.object)?\(\s*(B|ab|self\.ab|aitask_board)\s*,\s*"[A-Za-z_]+"' tests/
# → matches, e.g. test_board_dialog_run_dispatch.py:112 patch.object(ab, "resolve_agent_string")
#              test_board_group_focus.py:953  patch.object(self.ab, "build_column_units")
```

Re-run both at implementation time; the sweep is only valid against the tree it
is run on.

**Zero repoints, zero mutants.** The patch sites in `test_board_column_manage.py`
are either `patch.object(B.Task|B.TaskManager, "<method>")` — which mutate the
**shared class object**, so they land through any module alias — or already
repointed to `B.board_task_manager` by child 4 (`:691, 709, 725, 745`). The
moved dialogs reach those only via `self.manager`, never as module globals.

Existing consumers keep working through the re-export unchanged:
`test_board_column_dialog.py` (isinstance + direct instantiation at `:238`),
`test_board_work_report.py` (`ColumnMultiSelectScreen`, `:269`, `:292`),
`test_board_move_command.py` (`ColumnSelectScreen`). Mentions in
`monitor/monitor_shared.py:3246`, `lib/board_columns.py:122,165,663`,
`test_minimonitor_pick_by_number.py:2158`,
`test_board_columns_reconcile.py:470` are **comments only**.

## Order

1. **Rebase check** (parent pre-phase) — done. Neighbours **t1404**, **t1441**,
   **t1442**, **t1714** are all `Ready`; no foreign `Implementing`, so no
   checkpoint stop. Read, not pre-implemented.
2. Create `board_column_dialogs.py`; move the 9 classes verbatim.
3. Delete the three regions; add the import pair; comment the `board_columns`
   re-export.
4. Add the new pin test and the two guard entries.
5. Targeted tests, then the full suite.
6. Record the residual class list + line count for **t1794_11**.

**Separate cleanup, not a drive-by.** `tests/test_board_detail_screen.py`
documents itself as held to the strict tier (its docstring says "see
`MIGRATED_MODULES`") but t1794_7 never added it to that tuple. That is t1794_7's
gap, not this task's: it needs its own red-then-green check that the test still
passes under the strict tier. **Spawn it as an "after" follow-up task at Step
8d** rather than folding it in here — this child adds only its own entry.

## Verification

The task's stated acceptance grep (now also enforced, more strictly, by the
source-level single-home pin — the grep only sees `^class`, the AST helper sees
any module-scope binding):

```bash
grep -n '^class ColorSwatch\|^class ColumnEditScreen\|^class DeleteColumnConfirmScreen\|^class ColumnSelectItem\|^class ColumnSelectScreen\|^class ColumnManageItem\|^class MergeColumnsConfirmScreen\|^class ColumnManageScreen\|^class ColumnMultiSelectScreen' \
  .aitask-scripts/board/aitask_board.py            # → empty

python -m pytest tests/test_board_column_dialogs.py tests/test_board_column_dialog.py \
  tests/test_board_column_manage.py tests/test_board_columns_seam.py \
  tests/test_board_columns_reconcile.py tests/test_board_package_contract.py \
  tests/test_board_fixture_harness.py tests/test_board_keymap_characterization.py \
  tests/test_shortcut_scopes.py tests/test_board_work_report.py \
  tests/test_board_move_command.py tests/test_board_detail_screen.py \
  tests/test_board_trail_view.py -q
#                      ^ owns the negative controls for the single-home helper

bash tests/test_no_lib_to_tui_import.sh
bash tests/run_all_python_tests.sh                 # last line → PYTHON SUITE: PASSED
```

Read **only the last line** for the suite verdict, and do not pipe it to `tail`
without `set -o pipefail` — piping discards the exit status.

Manual in tmux: `ait board` → column manage (add / rename / recolour / shift+↑↓
reorder / delete / merge, each with its cancel path, and Esc-closes-with-changes
returning the `_changed` flag), `m` move a card to a chosen column, `M` in
By-Trail moves a wave.

## Notes for sibling tasks

- **t1794_9** — `ColumnSelectItem.render()` and `ColorSwatch.render()` move to
  `board/board_column_dialogs.py`; **t1441** and **t1442** both cite them at
  stale `aitask_board.py` line numbers (`:5748`, `:5517`) and need a note.
- **t1794_11** — residual `^class` list and line count, recorded at
  implementation time. Baseline before this child: 35 classes / 7,407 lines.
  **After t1794_8: 26 classes / 6,843 lines** (−9 classes, −564 lines; the new
  `board_column_dialogs.py` is 645 lines including its header).

  The 26 residual classes of `aitask_board.py`, in file order — this is the
  end-state shape the parent's acceptance criteria describe (`KanbanApp`, the
  Kanban render paths, the key map / `check_action`, `InFlightTaskCard`, the
  task-select screens, the module constants and the three injected helpers):

  ```
  CollapsedColumnPlaceholder  EmptyColumnPlaceholder  GroupHeader
  ViewSelector                InFlightTaskCard        InFlightColumn
  TopicColumn                 TopicSortModeItem       TopicSortModeScreen
  GateChoiceItem              GateChoiceScreen        KanbanColumn
  DeleteConfirmScreen         DeleteArchiveConfirmScreen
  OrphanParentArchiveScreen   CrossRepoTaskScreen     IssueTypeFilterScreen
  TaskSelectScreenBase        WorkReportTaskSelectScreen
  MoveTaskSelectScreen        RenameTaskScreen        CommitMessageScreen
  SettingsScreen              KanbanCommandProvider   BoardScreen
  KanbanApp
  ```

- **t1794_7 follow-up (separate cleanup, not done here)** —
  `tests/test_board_detail_screen.py` documents itself as held to the strict
  fixture tier ("see `MIGRATED_MODULES`") but was never added to that tuple.
  `test_board_column_dialogs.py` *was* added by this child. The older file needs
  its own red-then-green check and is spawned as an "after" follow-up.

## Risk

**Code-health risk: low.** Verbatim move, no behaviour change, following a
pattern executed seven times already in this parent task. Blast radius is 2
source files + 3 test files; every existing call site keeps resolving through
the re-export. The module needs no injection and no CSS split, making it the
simplest of the eight extractions. The commit-boundary save path moves
untouched. The net is strong and specific: the C1 `ImportBackTests`, the
`UnresolvedGlobalsTests` symtable scan (which catches a verbatim move that
forgot an import), the new **source-level** single-home pin (which, unlike a
runtime identity check, catches dead duplicate source left behind in either
ordering), and `test_board_column_dialog.py` / `test_board_column_manage.py`.
The C3 sweep is a proven empty set with a positive control.

**Goal-achievement risk: low.** The task's own acceptance grep is satisfied by
the widened set, and the widening is *forced* by a pinned contract rather than
chosen. The one judgement call — that "column dialogs" excludes `SettingsScreen`
— is checked: it references no moved class and is board settings, not column
management.

**Mitigations: none required.** The deviation from the parent file map is
documented above and is mechanically enforced by the C1 AST guard, which fails
red if the boundary is drawn wrong.

## Final Implementation Notes

- **Actual work done:** Created `.aitask-scripts/board/board_column_dialogs.py`
  (645 lines) holding the **9** column-management classes moved verbatim from
  `aitask_board.py`: `ColumnMultiSelectScreen`, `ColorSwatch`,
  `ColumnEditScreen`, `DeleteColumnConfirmScreen`, `ColumnSelectItem`,
  `ColumnSelectScreen`, `ColumnManageItem`, `MergeColumnsConfirmScreen`,
  `ColumnManageScreen`. Three discontiguous source regions (`1568–1632`,
  `1871–2012`, `2072–2448`), extracted with a scripted slice so the bodies are
  byte-identical. `aitask_board.py` went **7,407 → 6,843 lines, 35 → 26
  classes**; it gained the standard `import board_column_dialogs` +
  `from board_column_dialogs import (…)` pair with the house comment block.
  New pin test `tests/test_board_column_dialogs.py`; guard entries added to
  `tests/test_board_package_contract.py` and `tests/test_board_fixture_harness.py`
  (both `MIGRATED_MODULES` and the anti-vacuity sibling tuple); one genuine fix
  in `tests/test_board_columns_reconcile.py`.

- **Deviations from plan:** None from the *approved* plan. The approved plan
  itself deviated from the pre-existing p1794_8 / parent file map by widening
  the move set from 6 classes to 9 — forced by C1 ("no `board/*.py` may import
  `aitask_board`"), since `ColumnManageScreen` pushes `ColumnEditScreen`,
  `DeleteColumnConfirmScreen` and `MergeColumnsConfirmScreen`. Checked at the
  pinned SHA `e2f12c499`: the map's range `ColumnManageItem/Screen (:8060–8397)`
  already spanned `MergeColumnsConfirmScreen (:8089)`, so only two classes were
  genuinely unnamed. Two further additions came out of user review — the
  `MIGRATED_MODULES` entry for the new test, and replacing a runtime-only
  identity pin with the source-level single-home check.

- **Issues encountered:**
  1. `tests/test_board_columns_reconcile.py::SavePathContainmentTests` failed:
     its anti-vacuity union compared the whole-board-tree `save_metadata`
     caller scan against callers found in **two** hardcoded files, and
     `ColumnManageScreen._shift` moved out of `aitask_board.py`. Fixed by
     naming all three modules (added `DIALOGS_PATH` + an `assertIn("_shift",
     dialog_sites)`), keeping the test's meaning rather than loosening it.
  2. My own first pin test asserted `assertNotIn("aitask_board", source)` for
     C1 — which the module docstring legitimately violates in prose ("extracted
     from `aitask_board.py`"). Replaced with an AST scan for real `Import` /
     `ImportFrom` nodes.
  3. The `from board_columns import` block lost its last in-file consumer (all
     uses were inside the move set). It must stay: `test_board_columns_seam.py`
     asserts the literal import text in `aitask_board.py`, and
     `test_board_column_manage.py` reads `B.UNORDERED_ID` at 13 sites. Kept with
     a `# noqa: E402,F401` and a comment saying why, plus a test pinning it.
  4. Wrote `C` as the column-manage key into the t1794_12 checklist from
     memory; the binding is actually `e` (`aitask_board.py:2333`). Corrected
     before committing.

- **Key decisions:**
  - **No injection, unlike t1794_7.** The moved classes call no module-level
    board function — their host reach is `self.app.<method>` and
    `self.manager`, both resolved at call time — so there is no `make_*` binder
    and no keyword-callable plumbing. This is the simplest of the eight
    extractions.
  - **CSS stays in `KanbanApp.CSS`**, following the t1794_7 precedent, not the
    `WIDGET_CSS` / `TRAIL_CSS` split: the board is the only App that pushes
    these dialogs (`trails_app` uses none) and several rules are shared with
    other board modals.
  - **No `lib/shortcut_scopes.py` row.** Six moved classes carry plain
    `BINDINGS` but none subclasses `ShortcutsMixin` or sets `_shortcuts_scope`;
    `KNOWN_BINDING_SOURCES` lists only scope contributors (`board_trail_screen.py`
    exports `TRAIL_BINDINGS` and is deliberately absent).
  - **Source-level single home over runtime identity.** Reused the shared
    `tests/lib/board_single_home.py` helper (t1794_3/_4's precedent) rather than
    t1794_7's identity-only pins: identity cannot see a stale copy left *above*
    the board's import. Mutant-checked in-memory — the pin catches a copy below
    the import, above it, and a duplicate in the new module.
  - **C3 sweep proven, not assumed:** the concrete 16-name grep returns zero
    matches, and a positive control with the same regex shape returns 21. Zero
    patch repoints, zero mutants needed.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t1794_9** — notes to t1441 and t1442 were **already sent by this child**
    (ids `2026-09-20T08:00:30Z.b981800f…` and `2026-09-20T08:00:43Z.b9d73869…`),
    because this change is what invalidated their locations. Do not re-send;
    check `aitask_query_files.sh inbox 1441 1442` before composing.
  - **t1794_11** — the residual class list and line count are recorded above
    under "Notes for sibling tasks".
  - **t1794_12** — the t1794_8 checklist was expanded from 3 items to 7 to match
    the widened move set: the grep now names all 9 classes, the merge flow gets
    an end-to-end item, and the Esc-with-changes dismiss path gets its own.
  - **Pattern for any future extraction:** the per-module guards are now a
    four-site checklist — `BOARD_MODULE_NAMES` (already pre-seeded in
    `board_fixture.py`), a `HeadlessImportTests` probe, the anti-vacuity sibling
    tuple, and `MIGRATED_MODULES`. t1794_7 missed the last one; see the
    follow-up recorded above.
