---
priority: medium
effort: high
depends: [t1794_2]
issue_type: refactor
status: Ready
labels: [aitask_board, tui, trails, python, refactor]
gates: [risk_evaluated]
anchor: 1794
created_at: 2026-09-11 15:08
updated_at: 2026-09-11 15:08
---

## Context

Child 3 of t1794. Extract the **pure** trail code — constants, dataclasses,
projection helpers, ghost stub, badges, trail cards/columns and the three trail
modals — into `board_trail_view.py`. This is the module the stand-alone
`ait trails` TUI (child 6) renders with, and the module whose pure core the
headless `TrailModelTests` will run against without importing the board. It has
exactly one module-global read (`TASKS_DIR` in `load_local_project_name`,
`aitask_board.py:1207`) and no test patch sites of its own — every trail patch
target in `tests/test_board_bytrail_view.py` is called from the App half,
which child 5 moves.

**Read first:** `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
— "Target file map", C1, C2, C3, C7 (`TRAIL_CSS`), Decisions "Stand-alone
scope". Anchors at `e2f12c499` (unchanged at `c78deab36`).

## Key files to modify

- `.aitask-scripts/board/board_trail_view.py` — NEW. Move verbatim:
  constants `TRAIL_WATCH_INTERVAL`, `TRAIL_WATCH_MAX_TICKS`,
  `TRAIL_GATHER_SCRIPT` (`:1162–1164`), `TRAIL_CLASSIFICATION_GLYPHS`
  (`:1169–1175`), `_TRAIL_GHOST_LABELS` (`:1177–1181`); dataclasses
  `TrailEntryView` (`:1184–1193`), `TrailWaveLane` (`:1196–1199`); helpers
  `load_local_project_name` (`:1202–1215`), `trail_ref_to_local_id`
  (`:1218–1227`), `canonical_trail_ref` (`:1230–1242`), `build_trail_lanes`
  (`:1245–1287`), `trail_drift_by_ref` (`:1290–1306`), `trail_summary_text`
  (`:1309–1331`), `run_trail_drift` (`:1334–1360`); `_GhostTaskStub`
  (`:3761–3776`); `_trail_badge_text` (`:3917–3923`), `_trail_drift_text`
  (`:3926–3945`); `TrailTaskCard` (`:3948–4012`), `TrailGhostCard`
  (`:4014–4063`), `TrailColumn` (`:4066–4106`); `_trail_stored_freshness`
  (`:4286–4306`), `TrailSelectItem` (`:4309–4338`), `TrailSelectScreen`
  (`:4341–4373`), `TrailDetailScreen` (`:4376–4733`), `TrailSummaryScreen`
  (`:4736–4788`). Plus NEW `TRAIL_CSS` (C7).
- `.aitask-scripts/board/aitask_board.py` — `import board_trail_view` +
  flat re-import of every moved name (tests read `ab.build_trail_lanes`,
  `ab.TrailInfo` (from `trail_discovery`, unchanged), `ab.TrailDetailScreen`…);
  `KanbanApp.CSS` interpolates `TRAIL_CSS` in place of the trail rules it holds
  today (`.trail-drift :8582`, `#trail_summary :8620`, `#board_container`
  layout rule `:8606`, `TaskCard.markable-card:* :8576,8580` — re-derive the
  full set by grepping `KanbanApp.CSS` for `trail`, `#board_container`,
  `markable`); `_get_local_project` (`:11733–11737`) passes `TASKS_DIR`
  explicitly to `load_local_project_name(tasks_dir, config_path=None)`.
- `tests/test_board_bytrail_view.py` — `TrailModelTests` (`:204–430`) gains a
  sibling class that imports `board_trail_view` directly (no `board_fixture`,
  no board import) and runs the same model assertions; the C7 containment test
  (`TRAIL_CSS in KanbanApp.CSS`).
- `tests/test_board_reference_doc_literals.py` — pins for trail literals
  (`TRAIL_CLASSIFICATION_GLYPHS`, ghost labels, banner text) read
  `board_trail_view`.

## Reference files for patterns

- `aitask_board.py:53–66` — bare-import + flat re-import pairing.
- `aidocs/framework/tui_conventions.md` "Modals pushed by multiple Apps must
  carry their own DEFAULT_CSS" (`:254–270`) — `TrailSelectScreen`,
  `TrailDetailScreen`, `TrailSummaryScreen` each get a `DEFAULT_CSS` covering
  what they borrow from `KanbanApp.CSS` today (`TrailSummaryScreen`'s
  docstring at `:4746` already notes it has "CSS it cannot rely on").
- `aidocs/implementation_trail_design.md` §9.1–9.3 — the view's contract.
- `tests/lib/board_fixture.py:82–99` — `project_config.yaml` with
  `project.name` is required for trail tests (`load_local_project_name`).
- `lib/trail_discovery.py` — already promoted seams (t1647_1); `board_trail_view`
  imports `TrailInfo`, `trail_entry_refs` from it, never from the board.

## Implementation plan

1. **Rebase check** (parent pre-phase): `git log --oneline -20 --
   .aitask-scripts/board/ tests/test_board_bytrail_view.py`; re-read every
   range above; check for foreign `Implementing` tasks on By-Trail —
   **t1647_5** (adds a board command inside the By-Trail view) is the known
   collision: if it has landed, its command lives in the App half and is
   child 5's concern, but any widget it added to the cards/modals moves here.
   Stop at the checkpoint if a foreign task is `Implementing` on these ranges.
2. Create `board_trail_view.py`; imports: `board_widgets` (`TaskCard`,
   `PickerItem`, `ColumnHeader`, `_followup_marker`, `_followup_glyph_text`,
   `_plan_approved_marker`, `_status_badge_text`), `trail_discovery`,
   `topic_semantics.task_own_id`, `cross_repo_notation.parse_cross_repo_ref`,
   `yaml`, `subprocess`. `load_local_project_name(tasks_dir: Path,
   config_path: Path | None = None)` — no `TASKS_DIR` name in the module.
3. `TRAIL_CSS` string; modal `DEFAULT_CSS`.
4. Replace the definitions in `aitask_board.py`; import pair; CSS
   interpolation; `_get_local_project` passes `TASKS_DIR`.
5. C3 sweep: `grep -n 'patch.object(\(ab\|self.ab\), "' tests/test_board_bytrail_view.py`
   and classify each name: called from the App half (stays valid — `ab.X`
   still resolves because the board re-imports it and the App methods call
   it through the board namespace) vs called from inside `board_trail_view`
   (must repoint to `ab.board_trail_view.X`; e.g. `run_trail_drift` is called
   by `_trail_drift_worker :11908` — App half; `trail_drift_by_ref` inside
   `TrailDetailScreen` — no patch today; confirm). Mutant per repointed patch.
6. Add the headless model test class and the C7 containment test.

## Verification steps

- `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED`.
- `python -m pytest tests/test_board_bytrail_view.py -q` green with no
  assertion changed in intent (only patch targets moved, each with a recorded
  mutant); the new headless class passes with `aitask_board` absent from
  `sys.modules` (assert that in the test).
- Child-1 guards green (`test_board_package_contract`,
  `test_board_fixture_harness` C2 scan — `board_trail_view` contains none of
  the C2 names — and `test_board_keymap_characterization` unchanged).
- `ait board` → `z` → `s` select a trail → lanes render, `enter` detail, `v`
  summary, `d` drift (manual in tmux).
