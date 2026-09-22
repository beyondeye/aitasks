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

## Sent notes

Sent 2026-09-22 with `./ait note <id> --from 1794_9 --with-live --file <body>`,
base `4d1ea067e`. All 63 returned `NOTE_APPENDED:` (from_verified=yes) followed
by `LIVE_NONE:unlocked` — durable success, no live holder, nothing resent.
`dirty=yes` on every note reflects an unrelated untracked `aidocs/testing_engine/`.

Deviations from the plan: added a t1830-specific paragraph (per-module
`dismiss(` counts: aitask_board 41, board_detail_screen 44,
board_column_dialogs 20, board_trail_view 8), since its "~89 sites in
aitask_board.py" premise no longer holds.

- t1470 — `NOTE_APPENDED:2026-09-22T06:08:02Z.76398491b866be486e6c7a43` → `aitasks/t1470_surface_intrawave_parallel_safety_in_bytrail_view.md` · `LIVE_NONE:unlocked`
- t1543 — `NOTE_APPENDED:2026-09-22T06:08:05Z.70917a7d1d5f28ae0f65350e` → `aitasks/t1543_fix_trail_detail_modal_withheld_count_pluralization.md` · `LIVE_NONE:unlocked`
- t1526 — `NOTE_APPENDED:2026-09-22T06:08:08Z.ac98f1d17b265799d8e3356d` → `aitasks/t1526_trail_modal_blank_labelled_line_on_whitespace_narrative.md` · `LIVE_NONE:unlocked`
- t1645 — `NOTE_APPENDED:2026-09-22T06:08:10Z.c66ba3cca3243862ea8abf69` → `aitasks/t1645_agent_facing_implementation_trail_reference_doc.md` · `LIVE_NONE:unlocked`
- t1569 — `NOTE_APPENDED:2026-09-22T06:08:13Z.43057c177aad6bbbe179b167` → `aitasks/t1569_background_work_roadmap_trail_for_followup_backlog.md` · `LIVE_NONE:unlocked`
- t1634 — `NOTE_APPENDED:2026-09-22T06:08:16Z.45ef5f3821b1ed029e922ad7` → `aitasks/t1634_fold_candidate_clustering_for_backlog_roadmap.md` · `LIVE_NONE:unlocked`
- t1296 — `NOTE_APPENDED:2026-09-22T06:08:18Z.fc11b7cb2a2daa33bf804bfd` → `aitasks/t1296_agent_command_dialog_key_collisions.md` · `LIVE_NONE:unlocked`
- t1647 — `NOTE_APPENDED:2026-09-22T06:08:21Z.417985f84a44f751203f2857` → `aitasks/t1647_merge_trails_skill_shared_helpers_board_command_docs.md` · `LIVE_NONE:unlocked`
- t1647_5 — `NOTE_APPENDED:2026-09-22T06:08:23Z.3086d85150ad048f58345565` → `aitasks/t1647/t1647_5_board_bytrail_fold_trails_command.md` · `LIVE_NONE:unlocked`
- t1647_6 — `NOTE_APPENDED:2026-09-22T06:08:26Z.3dddbcba014639da6208bc58` → `aitasks/t1647/t1647_6_merge_trails_docs_website_and_rfc.md` · `LIVE_NONE:unlocked`
- t1243 — `NOTE_APPENDED:2026-09-22T06:08:29Z.5b12d9fb8303f479a44ee07c` → `aitasks/t1243_board_task_groups_and_fast_reordering.md` · `LIVE_NONE:unlocked`
- t1243_11 — `NOTE_APPENDED:2026-09-22T06:08:31Z.129cd34dad527a310a59d991` → `aitasks/t1243/t1243_11_group_formation_and_block_moves.md` · `LIVE_NONE:unlocked`
- t1243_12 — `NOTE_APPENDED:2026-09-22T06:08:33Z.9161609578a0f0543a980b37` → `aitasks/t1243/t1243_12_group_membership_commands.md` · `LIVE_NONE:unlocked`
- t1243_13 — `NOTE_APPENDED:2026-09-22T06:08:36Z.657b6954592eb41ee51ad5ea` → `aitasks/t1243/t1243_13_documentation.md` · `LIVE_NONE:unlocked`
- t1243_14 — `NOTE_APPENDED:2026-09-22T06:08:39Z.b31445afcc7e9ebae8b462c0` → `aitasks/t1243/t1243_14_retrospective_benchmark.md` · `LIVE_NONE:unlocked`
- t1250 — `NOTE_APPENDED:2026-09-22T06:08:41Z.a0f0005f4c539a5a4928cdba` → `aitasks/t1250_board_selector_wrap_2d_hittest.md` · `LIVE_NONE:unlocked`
- t1256 — `NOTE_APPENDED:2026-09-22T06:08:44Z.8796aead434252f122d721ee` → `aitasks/t1256_board_guard_stray_nav_key_selection_change.md` · `LIVE_NONE:unlocked`
- t1257 — `NOTE_APPENDED:2026-09-22T06:08:46Z.299e1c82d9a7f22aba0695d7` → `aitasks/t1257_board_auto_refresh_refocus_discards_scroll.md` · `LIVE_NONE:unlocked`
- t1290 — `NOTE_APPENDED:2026-09-22T06:08:49Z.070e5e0f568a22c43cf84239` → `aitasks/t1290_board_inflight_view_drops_focus.md` · `LIVE_NONE:unlocked`
- t1329 — `NOTE_APPENDED:2026-09-22T06:08:52Z.c969571107a366e91f97016f` → `aitasks/t1329_fix_task_title_and_plan_badge_rendering.md` · `LIVE_NONE:unlocked`
- t1330 — `NOTE_APPENDED:2026-09-22T06:08:54Z.744237a64d76268b810da1e4` → `aitasks/t1330_guard_numberless_task_filenames.md` · `LIVE_NONE:unlocked`
- t1334 — `NOTE_APPENDED:2026-09-22T06:08:57Z.50f19b63ae548f5eedf7e9ca` → `aitasks/t1334_work_report_skips_idless_tasks.md` · `LIVE_NONE:unlocked`
- t1338 — `NOTE_APPENDED:2026-09-22T06:08:59Z.9f019017dfd72065e2674e8c` → `aitasks/t1338_work_report_drops_unparseable_task_filenames.md` · `LIVE_NONE:unlocked`
- t1348 — `NOTE_APPENDED:2026-09-22T06:09:02Z.8083637aa51142872344eb0b` → `aitasks/t1348_board_work_report_drops_one_column_task.md` · `LIVE_NONE:unlocked`
- t1356 — `NOTE_APPENDED:2026-09-22T06:09:04Z.1956c994097aa06a4306c01d` → `aitasks/t1356_idless_task_filename_and_hook_status_race.md` · `LIVE_NONE:unlocked`
- t1363 — `NOTE_APPENDED:2026-09-22T06:09:07Z.74415b07f2f8b7df01b9cd7b` → `aitasks/t1363_fix_board_work_report_key_docs_and_ait_help_gate_pass.md` · `LIVE_NONE:unlocked`
- t1364 — `NOTE_APPENDED:2026-09-22T06:09:09Z.450ecd7bdacad836684096f4` → `aitasks/t1364_warn_on_unparseable_task_filenames.md` · `LIVE_NONE:unlocked`
- t1367 — `NOTE_APPENDED:2026-09-22T06:09:12Z.46b819c4803f71f01a739303` → `aitasks/t1367_board_fixture_harness_docs.md` · `LIVE_NONE:unlocked`
- t1368 — `NOTE_APPENDED:2026-09-22T06:09:15Z.6ebe94b4365676caea19e30e` → `aitasks/t1368_widen_live_tree_guard_sweep.md` · `LIVE_NONE:unlocked`
- t1373 — `NOTE_APPENDED:2026-09-22T06:09:17Z.ffbc40ec2c39cafbfd4821e9` → `aitasks/t1373_confirm_dialog_body_label_split.md` · `LIVE_NONE:unlocked`
- t1399 — `NOTE_APPENDED:2026-09-22T06:09:20Z.b292aeb540c526024b865cc5` → `aitasks/t1399_board_vertical_move_stale_dirty_marker.md` · `LIVE_NONE:unlocked`
- t1400 — `NOTE_APPENDED:2026-09-22T06:09:22Z.9754d6434c7c13d5f540ebed` → `aitasks/t1400_board_column_header_live_count.md` · `LIVE_NONE:unlocked`
- t1401 — `NOTE_APPENDED:2026-09-22T06:09:25Z.0ab4dbe87ee4f0851bafcbb2` → `aitasks/t1401_board_movement_dom_invariant_harness.md` · `LIVE_NONE:unlocked`
- t1402 — `NOTE_APPENDED:2026-09-22T06:09:28Z.83ebb5bfbafb27627d12035c` → `aitasks/t1402_board_focus_query_storm_on_move.md` · `LIVE_NONE:unlocked`
- t1403 — `NOTE_APPENDED:2026-09-22T06:09:31Z.16240e1429ce0031b97d1984` → `aitasks/t1403_board_nav_column_widgets_query_cost.md` · `LIVE_NONE:unlocked`
- t1404 — `NOTE_APPENDED:2026-09-22T06:09:33Z.47d40c05b2c23fd34a7d5748` → `aitasks/t1404_settings_columns_editable.md` · `LIVE_NONE:unlocked`
- t1421 — `NOTE_APPENDED:2026-09-22T06:09:36Z.054b308a574acd6a4ee6addd` → `aitasks/t1421_fix_shortcut_rebind_key_normalization.md` · `LIVE_NONE:unlocked`
- t1424 — `NOTE_APPENDED:2026-09-22T06:09:39Z.1ec0b249d6c4ffdffdc1a53a` → `aitasks/t1424_reconcile_shortcuts_editor_and_command_palette.md` · `LIVE_NONE:unlocked`
- t1431 — `NOTE_APPENDED:2026-09-22T06:09:41Z.41f761b5015be2af82cfa54b` → `aitasks/t1431_board_move_column_validation.md` · `LIVE_NONE:unlocked`
- t1445 — `NOTE_APPENDED:2026-09-22T06:09:44Z.4b649db61f8369a75f57ae1b` → `aitasks/t1445_board_move_result_reports_unwritten_tasks_as_moved.md` · `LIVE_NONE:unlocked`
- t1447 — `NOTE_APPENDED:2026-09-22T06:09:46Z.c601c50ec046f170a7ae5504` → `aitasks/t1447_audit_companion_hook_arming_and_dead_monitor_guards.md` · `LIVE_NONE:unlocked`
- t1448 — `NOTE_APPENDED:2026-09-22T06:09:49Z.0eb24ab5fb8af8eeb8881daa` → `aitasks/t1448_shadow_concern_badge_currency.md` · `LIVE_NONE:unlocked`
- t1450 — `NOTE_APPENDED:2026-09-22T06:09:52Z.48b55281431acc40dca910bf` → `aitasks/t1450_board_test_harness_and_modal_escape_result_gaps.md` · `LIVE_NONE:unlocked`
- t1454 — `NOTE_APPENDED:2026-09-22T06:09:54Z.896ec2fa514cac9a3d200e5f` → `aitasks/t1454_fix_failed_verification_t1377_7_item18.md` · `LIVE_NONE:unlocked`
- t1455 — `NOTE_APPENDED:2026-09-22T06:09:56Z.c6311e93c28b6df0e4cd9d76` → `aitasks/t1455_fix_failed_verification_t1377_7_item20.md` · `LIVE_NONE:unlocked`
- t1570 — `NOTE_APPENDED:2026-09-22T06:09:59Z.1c94f521acc067cb97ba4ad4` → `aitasks/t1570_task_detail_dialog_footer_hint_clipped_narrow.md` · `LIVE_NONE:unlocked`
- t1572 — `NOTE_APPENDED:2026-09-22T06:10:02Z.93d10ae823c5aa42a9107562` → `aitasks/t1572_sweep_same_edge_dock_siblings.md` · `LIVE_NONE:unlocked`
- t1613 — `NOTE_APPENDED:2026-09-22T06:10:04Z.5c72fe8d1c2465cc8a9e6f74` → `aitasks/t1613_duplicate_lib_module_objects_make_test_patches_inert.md` · `LIVE_NONE:unlocked`
- t1632 — `NOTE_APPENDED:2026-09-22T06:10:08Z.afd48cd17aa24958d5287e31` → `aitasks/t1632_board_tui_boardcol_reuse_column_of_seam.md` · `LIVE_NONE:unlocked`
- t1639 — `NOTE_APPENDED:2026-09-22T06:10:10Z.248f3e3b44fa4e3ddbd4eacc` → `aitasks/t1639_adopt_nerd_font_glyph_vocabulary_behind_declared_tier.md` · `LIVE_NONE:unlocked`
- t1663_2 — `NOTE_APPENDED:2026-09-22T06:10:13Z.53ce91263516a7128172fae8` → `aitasks/t1663/t1663_2_premise_baseline_field_end_to_end.md` · `LIVE_NONE:unlocked`
- t1710 — `NOTE_APPENDED:2026-09-22T06:10:15Z.4c4f7262760fa9abcb315a4b` → `aitasks/t1710_archive_sh_pathspec_scope.md` · `LIVE_NONE:unlocked`
- t1714 — `NOTE_APPENDED:2026-09-22T06:10:18Z.0f2a751e72ce54c06cb036e3` → `aitasks/t1714_shared_metadata_write_mutex.md` · `LIVE_NONE:unlocked`
- t1725_5 — `NOTE_APPENDED:2026-09-22T06:10:20Z.a638c0aaaf55b08f5744772d` → `aitasks/t1725/t1725_5_syncer_and_board_deferral_screen_with_commit_on_behalf.md` · `LIVE_NONE:unlocked`
- t1830 — `NOTE_APPENDED:2026-09-22T06:10:23Z.5a8fc88ff9655b0ac3f38c5c` → `aitasks/t1830_guard_dismiss_remaining_tuis.md` · `LIVE_NONE:unlocked`
- t1835 — `NOTE_APPENDED:2026-09-22T06:10:25Z.88c99abaf8f3e7676f6277c9` → `aitasks/t1835_surface_illegal_name_in_yaml_readers.md` · `LIVE_NONE:unlocked`
- t635_37 — `NOTE_APPENDED:2026-09-22T06:10:28Z.1123cd83f9d42ff3f31c05fa` → `aitasks/t635/t635_37_settings_registry_gate_picker.md` · `LIVE_NONE:unlocked`
- t1135 — `NOTE_APPENDED:2026-09-22T06:10:30Z.7b56f36dbeada99c51ebfba6` → `aitasks/t1135_artifact_manifest_lifecycle_hard_delete_orphan_reaping.md` · `LIVE_NONE:unlocked`
- t879 — `NOTE_APPENDED:2026-09-22T06:10:33Z.7c26476141792d849a403f95` → `aitasks/t879_fix_shortcuts_mixin_live_rebind.md` · `LIVE_NONE:unlocked`
- t745 — `NOTE_APPENDED:2026-09-22T06:10:35Z.a2c3596b7dad283a475ddaa6` → `aitasks/t745_improve_node_comparator.md` · `LIVE_NONE:unlocked`
- t1186 — `NOTE_APPENDED:2026-09-22T06:10:38Z.ec8ed8a9b62ab76d0de776de` → `aitasks/t1186_chatlink_wizard_allowlist_live_pickers.md` · `LIVE_NONE:unlocked`
- t1516 — `NOTE_APPENDED:2026-09-22T06:10:40Z.dedf0973bbb405f42f81b06e` → `aitasks/t1516_task_yaml_verifies_normalization_asymmetry.md` · `LIVE_NONE:unlocked`
- t1162 — `NOTE_APPENDED:2026-09-22T06:10:43Z.b6b5f522f19d7aed30c1ad56` → `aitasks/t1162_add_manager_facing_work_report_skill_and_board_flow.md` · `LIVE_NONE:unlocked`

**Skipped (not sent), with reason:**
- UI-only manual-verification checklists, no line citations: t1249, t1261,
  t1291, t1372, t1422, t1439, t1569_7, t1647_7, t889, t1162_6, t1239, t1295,
  t1301, t1315, t1342, t1386, t1387, t1440, t1462, t1471, t1625, t1725_7,
  t1742, t729, t583_9, t571_7.
- Incidental mentions: t427, t858, t1376, t919, t259_6, t417_11, t386_9,
  t1459 (aitask_merge.py, unchanged), t1514 (test-file line), t1647_4, t1808,
  t1555_2 (incidental; was Implementing).
- Already notified by an extraction child: t1441, t1442 (t1794_8), t1521 (t1794_7).
- Already written against the split layout: t1843, t1845.
- No target was missing or archived at send time.

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

## Final Implementation Notes
- **Actual work done:** Re-verified the plan against HEAD `4d1ea067e` (all eight
  extraction children had landed since it was written), re-derived the target
  list (103 grep matches), generated one body per recipient (shared symbol →
  module index + the task's own stale `aitask_board.py:NN` anchors and moved
  symbols + a specific paragraph where planned), and sent 63 notes. No source
  files changed.
- **Deviations from plan:** (1) `--from 1794_9` rather than `--from 1794`: this
  session holds t1794_9's lock, so every note carries `from_verified=yes`.
  (2) The shared body inlines a compact symbol → module index instead of
  pointing only at the parent plan's file map, because that map's line ranges
  are pre-split mono-file anchors. (3) The planned t1632 note ("the board
  imports board_columns from aitask_board.py only") was false; the sent note
  says the import is now in four modules and aitask_board.py keeps a pinned
  pure re-export. (4) Added a t1830-specific paragraph (per-module dismiss counts).
  (5) Manual-verification checklists from the original group (a) (t1261,
  t1372, t1439, t1569_7, t1647_7) were skipped as UI-only, per the group (c) rule.
- **Issues encountered:** The previous session crashed after claiming the task
  and before sending anything; reclaimed via RECLAIM_CRASH, no partial state.
- **Key decisions:** Skip targets that an extraction child already notified
  specifically (t1441, t1442, t1521) and tasks already written against the
  split layout (t1843, t1845), so no task gets a redundant generic note.
- **Upstream defects identified:** None
- **Notes for sibling tasks:** t1794_10 (website docs) can use the shared note's
  symbol → module index as the current layout. For t1794_11 (retrospective):
  the parent plan's "Target file map" still cites pre-split line numbers; say
  that in the retrospective or replace them with symbol names.
