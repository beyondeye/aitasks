---
Task: t1794_9_notes_to_affected_tasks.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_10_*.md, aitasks/t1794/t1794_11_*.md, aitasks/t1794/t1794_12_*.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-22 08:42
---

# p1794_9 — Notes to every pending task the board split affects

## Context

The board mono-file split under t1794 has now **fully landed** (children 1–8
archived; the last extraction, t1794_8, is commit `387d8cb20`). `aitask_board.py`
went from ~13.7k to 6,843 lines and its classes moved into eight sibling modules,
so every `aitask_board.py:NN` anchor in a pending task body is stale and many
symbols now live elsewhere. This child sends each affected pending task one
durable `ait note` so the next agent to pick it re-derives its anchors against
the right module. No source files change.

## Verification findings (this session, HEAD `4d1ea067e`)

- **File map realized as designed.** `board/` now holds `aitask_board.py`,
  `board_widgets.py`, `board_trail_view.py`, `board_task_model.py`,
  `board_task_manager.py`, `board_workflow_phase.py`, `board_trail_screen.py`,
  `trails_app.py`, `board_detail_screen.py`, `board_column_dialogs.py`
  (+ `aitask_trails.sh`). Class homes confirmed by grep.
- **The parent plan's file map cites pre-split mono-file line numbers**
  (`:3181`, `:1459–2958`, …). The shared note must say so, or a reader would
  treat those as current anchors. The note therefore carries a compact
  symbol → module index (current state) and points to the plan for the
  rules C1–C3, rather than to the map's line ranges.
- **Correction to the planned t1632 note.** The plan said "the board imports
  `board_columns` from `aitask_board.py` only". False now: `board_task_manager.py`,
  `board_task_model.py` and `board_column_dialogs.py` import `board_columns`
  directly; `aitask_board.py:429` keeps a *pure re-export* pinned by
  `tests/test_board_columns_seam.py` (literal-text check) and
  `tests/test_board_column_manage.py` (`B.UNORDERED_ID`).
- **t1647_5 capability seam is concrete:** `TRAIL_ACTION_CAPABILITIES` in
  `board_trail_screen.py:111` + the mixin's `hasattr` gate (`:231`);
  `TrailsApp.check_action` at `trails_app.py:354`.
- **Target set re-derived:** 103 files match the grep (93 at planning).
  Newcomers: t1135, t1356, t858, t879, t1368, t1555_2, t1808, t1830, t1835,
  t1843, t1845. Plan owners t745 / t1186 / t1516 / t1162 / t1569 / t1647 all
  still pending and their plans still cite `aitask_board.py:NN`.
- **Already notified by the extraction children** (specific, symbol-level
  notes): t1441, t1442 (from t1794_8), t1521 (from t1794_7). Skip — a second,
  generic note adds nothing.
- **Already written against the split layout:** t1843 (cites
  `board_trail_screen.py:771-783`), t1845 (cites `board_detail_screen.py`). Skip.
- The previous session (crashed, PID 2943192) sent **no** notes — no inbox in
  the tree carries a `note:t1794*` block other than the three above.

## Recipients

**Send (shared body + per-target "your stale citations" line):**

- Trail-subsystem code/design tasks: t1470, t1543, t1526, t1645, t1569,
  t1634, t1296, t1647, t1647_5, t1647_6.
- Board-architecture / anchor-citing tasks: t1243, t1243_11, t1243_12,
  t1243_13, t1243_14, t1250, t1256, t1257, t1290, t1329, t1330, t1334, t1338,
  t1348, t1356, t1363, t1364, t1367, t1368, t1373, t1399, t1400, t1401, t1402,
  t1403, t1404, t1421, t1424, t1431, t1445, t1447, t1448, t1450, t1454, t1455,
  t1570, t1572, t1613, t1632, t1639, t1663_2, t1710, t1714, t1725_5, t1830,
  t1835, t635_37, t1135, t879.
- Plan owners (note names their plan file): t745, t1186, t1516, t1162
  (t1569 / t1647 already above — their note also names the plan).

**Skip (recorded with reason in "Sent notes"):**

- Manual-verification checklists that only drive the live UI (behaviour is
  unchanged by a behaviour-preserving split; none cites a line number): t1249,
  t1261, t1291, t1372, t1422, t1439, t1569_7, t1647_7, t889, t1162_6, t1239,
  t1295, t1301, t1315, t1342, t1386, t1387, t1440, t1462, t1471, t1625,
  t1725_7, t1742, t729, t583_9, t571_7.
- Incidental mentions (`ait board` launch, "pattern reference", unrelated
  file): t427, t858, t1376, t919, t259_6, t417_11, t386_9, t1459
  (`aitask_merge.py`, unchanged), t1514 (a test-file line), t1647_4, t1808,
  t1555_2 (incidental; currently `Implementing` — don't disturb).
- Already notified / already post-split: t1441, t1442, t1521, t1843, t1845.

## Implementation steps

1. **Build note bodies in the scratchpad** (no sends yet):
   - `shared.md` — the common body (below).
   - For each recipient, `<id>.md` = shared body + a `Your citations:` line
     generated mechanically from the task file
     (`grep -oE 'aitask_board\.py:[0-9,-]+'` plus any moved symbol names it
     mentions: `TaskManager`, `TaskDetailScreen`, `TrailDetailScreen`,
     `TrailSelectScreen`, `ColumnSelectItem`, `ColorSwatch`, …) mapped to the
     owning module via the index.
   - Specific paragraphs appended for: **t1647 / t1647_5** (By-Trail command →
     `TRAIL_BINDINGS` row + action in `board_trail_screen.py`, widgets/modals in
     `board_trail_view.py`; must work under both hosts or be declared in
     `TRAIL_ACTION_CAPABILITIES` so `ait trails` hides it); **t1613** (child 1's
     guards in `tests/test_board_package_contract.py` and
     `tests/test_board_fixture_harness.py` are the source-level enforcement of
     the duplicate-identity hazard — re-check remaining scope against them);
     **t1632** (the corrected `board_columns` fact above); **t1243 family**
     (`TaskManager` in `board_task_manager.py`, required kw-only
     `tasks_dir/metadata_file/gates_registry_file` — no global reads);
     **t1296** (`R` is a `TRAIL_BINDINGS` row shared by object identity with
     `ait trails`, scope `board`); **plan owners** (name the plan file and its
     stale anchors).
   - Check every body `< 8192` bytes.
2. **Per target, before sending:** `./.aitask-scripts/aitask_query_files.sh
   resolve <id>` — `NOT_FOUND` or archived → record skip, do not send.
3. **Send:** `./ait note <id> --from 1794_9 --with-live --file <S>/<id>.md`,
   one at a time, appending stdout to `<S>/sent.log`. `--from 1794_9` (not the
   parent) because this session holds t1794_9's lock, so the sender can be
   proven (`from_verified=yes`); the body names t1794 and its plan.
   - `NOTE_APPENDED:` → success (a following `LIVE_NONE:` is still success;
     never resend).
   - `LIVE_PANE:` → follow `.aitask-scripts/live_delivery/<family>.md`.
   - `NOTE_APPENDED_UNCOMMITTED:` → terminal; record, don't retry.
   - `NOTE_TARGET_MISSING:` / `NOTE_ERROR:` → record and continue.
4. **Record** every result line and every skip in this plan's "Sent notes".

### Shared note body (draft)

```
t1794 split the board mono-file (children 1–8 landed; last one 387d8cb20).
Any `aitask_board.py:NN` anchor in your body/plan is STALE — aitask_board.py
is now ~6.8k lines and most classes moved. Re-derive by symbol, not by line.

Where symbols live now (.aitask-scripts/board/):
- aitask_board.py — KanbanApp, Kanban/InFlight/Topic columns, board-only
  modals (delete/archive/rename/commit/settings/cross-repo…), key map
- board_task_manager.py — TaskManager (paths injected: required kw-only
  tasks_dir / metadata_file / gates_registry_file; no module-global reads)
- board_task_model.py — Task, MoveResult, MergeResult
- board_workflow_phase.py — workflow-phase / in-flight derivation
- board_widgets.py — TaskCard, ColumnHeader, PickerItem, badges, LoadingOverlay
- board_detail_screen.py — TaskDetailScreen + its field widgets and pickers
- board_column_dialogs.py — ColumnEdit/Select/Manage/MultiSelect, ColorSwatch
- board_trail_view.py — pure trail rendering: trail cards/columns, trail
  modals (TrailDetail/TrailSelect/TrailSummary…), TRAIL_CSS
- board_trail_screen.py — TrailScreenMixin (By-Trail actions), TRAIL_BINDINGS,
  TrailHost protocol, TRAIL_ACTION_CAPABILITIES
- trails_app.py — the stand-alone `ait trails` TUI hosting the same mixin

Rules a change to these files must keep (full text: contracts C1–C3 in
aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md; its "Target
file map" line ranges are PRE-split mono-file anchors, not current ones):
1. Flat imports between board/*.py (`import board_x`), never `board.`-qualified.
2. No board/*.py other than aitask_board.py reads TASKS_DIR & co. at import
   time — receive paths by parameter.
3. No board/*.py imports aitask_board.
All three are enforced by tests (test_board_package_contract.py,
test_board_fixture_harness.py); test patch targets follow the symbol
(patch board_task_manager.X, not aitask_board.X, for moved code).

Advisory: tree-relative claims above are as of the base SHA this note records.
```

## Verification

- `sent.log` has one `NOTE_APPENDED:` per recipient, or a recorded reason;
  every skip is listed with its reason in "Sent notes".
- `./.aitask-scripts/aitask_query_files.sh inbox 1647_5` shows the note unread.
- `./ait git log --oneline -60 | grep -c 'Record note'` matches the send count.

## Post-implementation

No code. Task-workflow Step 8 (review) → Step 9: commit this plan with the
"Sent notes" section filled; archive t1794_9.

## Risk

### Code-health risk: low
None identified. No source files change; notes are path-scoped commits on the
task-data branch.

### Goal-achievement risk: low
- A note asserting a wrong current-state fact would be believed (the t1632
  line in the original plan was already wrong) · severity: low · → mitigation:
  addressed in plan — every specific claim was re-verified against HEAD in
  this session; the shared body names symbols, not line numbers, and hedges
  to the recorded base SHA.
- Recipient misclassification (a skipped task that really needed a note) ·
  severity: low · → mitigation: addressed in plan — skips are recorded per task
  with a reason, so the list is auditable and a missed task can be noted later.
