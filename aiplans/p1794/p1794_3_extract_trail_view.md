---
Task: t1794_3_extract_trail_view.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_10_website_docs_trails_tui.md, aitasks/t1794/t1794_11_measure_document_retrospective.md, aitasks/t1794/t1794_12_manual_verification_split_board_monofile_and_standalone_trai.md, aitasks/t1794/t1794_4_extract_task_model_manager_and_workflow_phase.md, aitasks/t1794/t1794_5_lift_trail_screen_mixin.md, aitasks/t1794/t1794_6_standalone_trails_tui.md, aitasks/t1794/t1794_7_extract_detail_screen.md, aitasks/t1794/t1794_8_extract_column_dialogs.md, aitasks/t1794/t1794_9_notes_to_affected_tasks.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_1_board_package_contract_and_baseline.md, aiplans/archived/p1794/p1794_2_extract_board_widgets.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-14 17:51
---

# p1794_3 — Extract the pure trail code into `board_trail_view.py`

Parent plan: `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
(C1, C2, C3, C7 PINNED; Decisions "Stand-alone scope"). Archived siblings:
`p1794_1` (package contract, C1/C2 guards, keymap golden, footprint baseline),
`p1794_2` (`board_widgets.py`; its Final Implementation Notes are the pattern).

## Context

`aitask_board.py` (13,573 lines) is being split into flat-imported
`board/board_*.py` modules. This child moves the **pure** By-Trail code —
projection model, cards, columns and the three trail modals — into
`board_trail_view.py`, so the stand-alone `ait trails` TUI (child 6) can render
trails without importing the Kanban app, and so the trail model can be tested
headless. Behaviour-preserving: the embedded board view must not change.

## Step 0 — Rebase check (pre-phase `rebase_check_before_each_child`) — DONE at planning

- HEAD `c90ae55e8`. `git log -- .aitask-scripts/board/ tests/test_board_bytrail_view.py
  tests/lib/board_fixture.py`: newest is `53542c976` (t1794_2); nothing on
  `origin/main` beyond HEAD touches these paths. The task body's `e2f12c499`
  anchors are ~8 lines off (t1794_2 removed 533 lines); every range below was
  re-read at HEAD.
- Foreign `Implementing` ∩ board/trail regex: `t1688`, `t1555_2`, `t1800` —
  incidental mentions only. **t1647_5** (By-Trail command) is still `Ready`:
  nothing landed to rebase onto. No stop.
- **Shared worktree:** t1799 (Implementing) holds uncommitted comment edits in
  `tests/test_board_package_contract.py` and `lib/shortcut_scopes.py`. This
  task does **not** edit either file; the code commit names only its own paths,
  and the manual smoke runs in an isolated worktree (see Verification) so
  foreign edits cannot leak into its result.

## Premises corrected by verification

- **Signature break:** `load_local_project_name()` is called with no argument
  at `tests/test_board_bytrail_view.py:2777, 2794` and
  `tests/test_board_fixture_harness.py:181`. They pass `ab.TASKS_DIR` now.
- **C7 CSS list:** there is no `#board_container` rule in `KanbanApp.CSS`
  (only comments mention it — the widget is an unstyled `HorizontalScroll`),
  and `TaskCard.markable-card:*` are Kanban hover rules that trail cards never
  match (never markable). Neither moves. The trail-owned rules are exactly
  `.trail-drift` (`:8053`) and `#trail_summary` + its comment (`:8086–8091`).
- **Modal CSS:** `TrailDetailScreen` / `TrailSummaryScreen` already carry
  `DEFAULT_CSS`. `TrailSelectScreen` has none and borrows from
  `KanbanApp.CSS`: `Screen { align: center middle; }`, `#dep_picker_dialog`,
  `#dep_picker_title`, `.picker-dialog` rules, `PickerItem*`.
- **`test_board_reference_doc_literals.py` pins no trail literal** — nothing to
  repoint there.
- **C3 sweep:** the only `patch.object` on a moved name is `run_trail_drift`
  ×4 on `ab` (`tests/test_board_bytrail_view.py:2436, 2485, 2524, 2546`). Its
  caller (`_trail_drift_worker`, `aitask_board.py:11381`) stays in the App
  half and reads the board's global, so the patches stay live — **no repoint,
  no mutant owed**. No class-attribute patch / `setattr` on a moved class.
- **Source-path guard that would go vacuous:** `tests/test_board_marking.py:284`
  reads only `aitask_board.py` for the single `yield TrailGhostCard(` site,
  which moves with `TrailColumn`.
- **Re-export identity alone does not prove a single home:** a stale copy left
  *after* the import shadows it (identity fails), but one left *before* the
  import is silently rebound (identity passes, dead duplicate remains). Step 5
  adds a name-by-name source-level single-home test.

## Move set (verbatim; anchors at HEAD)

Three contiguous regions, cut in reverse order:

| region | content |
|---|---|
| `:3770–4272` | `_trail_stored_freshness`, `TrailSelectItem`, `TrailSelectScreen`, `TrailDetailScreen`, `TrailSummaryScreen` (ends before `class KanbanColumn :4275`) |
| `:3412–3618` | `_GhostTaskStub`, `_trail_badge_text`, `_trail_drift_text`, `TrailTaskCard`, `TrailGhostCard`, `TrailColumn` (ends before `class TopicSortModeItem :3621`) |
| `:1143–1352` | section comment, `TRAIL_WATCH_INTERVAL`, `TRAIL_WATCH_MAX_TICKS`, `TRAIL_GATHER_SCRIPT`, `TRAIL_CLASSIFICATION_GLYPHS`, `_TRAIL_GHOST_LABELS`, `TrailEntryView`, `TrailWaveLane`, `load_local_project_name`, `trail_ref_to_local_id`, `canonical_trail_ref`, `build_trail_lanes`, `trail_drift_by_ref`, `trail_summary_text`, `run_trail_drift` (ends before `@dataclass(frozen=True) class MoveResult :1355`) |

**`MOVED_NAMES` (25)** — the single list every check below reads:
`TRAIL_WATCH_INTERVAL`, `TRAIL_WATCH_MAX_TICKS`, `TRAIL_GATHER_SCRIPT`,
`TRAIL_CLASSIFICATION_GLYPHS`, `_TRAIL_GHOST_LABELS`, `TrailEntryView`,
`TrailWaveLane`, `load_local_project_name`, `trail_ref_to_local_id`,
`canonical_trail_ref`, `build_trail_lanes`, `trail_drift_by_ref`,
`trail_summary_text`, `run_trail_drift`, `_GhostTaskStub`, `_trail_badge_text`,
`_trail_drift_text`, `TrailTaskCard`, `TrailGhostCard`, `TrailColumn`,
`_trail_stored_freshness`, `TrailSelectItem`, `TrailSelectScreen`,
`TrailDetailScreen`, `TrailSummaryScreen`.

Verified by the child-2 method: before cutting, assert each region's first
line and following neighbour; after writing, assert every top-level block of
each region is a byte-for-byte substring of the new module (an editor can
normalize `\uXXXX` escapes).

## Implementation steps

1. **Create `.aitask-scripts/board/board_trail_view.py`.**
   - Module docstring: what lives here (the By-Trail rendering half — RFC §9,
     `aidocs/implementation_trail_design.md`; the section comment at `:1143–1149`
     moves here), read-only contract, C1 (flat, no `aitask_board`, no
     `sys.path` edit), C2 (no task-dir resolution; paths come in by parameter),
     and that stubs of names called *inside* this module must target
     `board_trail_view` (reachable as `ab.board_trail_view`).
   - Imports (exactly what the moved code uses):
     `from __future__ import annotations`; `re`, `subprocess`,
     `dataclasses.dataclass, field`, `pathlib.Path`, `yaml`;
     `rich.text.Text`; `textual.on`, `textual.binding.Binding`,
     `textual.containers.Container, VerticalScroll`,
     `textual.screen.ModalScreen`, `textual.widgets.Button, Label, Static`;
     `board_widgets` → `ColumnHeader, PickerItem, TaskCard, _followup_glyph_text,
     _followup_marker, _plan_approved_marker, _status_badge_text`;
     `trail_discovery` → `TrailInfo, trail_entry_refs`;
     `topic_semantics` → `task_own_id`;
     `cross_repo_notation` → `parse_ref as parse_cross_repo_ref`.
   - The 25 names verbatim, in their original relative order, with one change:
     `load_local_project_name(tasks_dir: Path, config_path: Path | None = None)`,
     body `path = config_path or (tasks_dir / "metadata" / "project_config.yaml")`
     (C2 — no `TASKS_DIR` name in the module; parameter named `tasks_dir`, since
     a local named `task_dir` is flagged like the resolver).
   - **`TRAIL_CSS`** (module constant, after the constants block):
     ```css
     /* Drift marker on trail cards. Two classes, not `.trail-drift` alone: the
        label also carries `.task-info` (colour $text-muted, owned by the host
        App's card rules), and a two-class selector wins regardless of which
        stylesheet the host puts first. */
     .task-info.trail-drift { color: #FFB86C; }
     /* By-Trail summary pane (t1505_1) — the existing comment, verbatim. */
     #trail_summary { height: 6; border-top: hkey $secondary-background; padding: 0 1; }
     ```
     A leading comment names what TRAIL_CSS deliberately does **not** own: the
     card / column-header / picker / loading-overlay rules of `board_widgets`
     widgets (`.task-title`, `.task-info`, `.col-header-*`, `PickerItem*`,
     `#loading_*`) stay with the host App — child 6's `TrailsApp` must supply
     them.
   - **`TrailSelectScreen.DEFAULT_CSS`** (tui_conventions "Modals pushed by
     multiple Apps"), mirroring the `KanbanApp.CSS` values it borrows today —
     Textual auto-scopes unprefixed rules to the screen (`css/parse.py:174`):
     ```css
     TrailSelectScreen { align: center middle; }
     #dep_picker_dialog { width: 60%; height: auto; max-height: 50%;
         background: $surface; border: thick $accent; padding: 1 2; }
     #dep_picker_title { text-align: center; padding: 0 0 1 0; text-style: bold; }
     #dep_picker_dialog.picker-dialog { overflow-y: auto; }
     .picker-dialog #dep_picker_title { width: 100%; dock: top; }
     PickerItem { height: auto; width: 100%; padding: 0 1; }
     PickerItem.dep-item-focused { background: $primary 20%; outline-left: thick $accent; }
     ```
     In the board, App CSS outranks `DEFAULT_CSS` and the values are identical,
     so the board renders unchanged.

2. **`aitask_board.py`: import pair, cut, CSS, caller.**
   - After the `board_widgets` import block, a comment mirroring it (names are
     RE-EXPORTS; inside `board_trail_view` the helpers call each other through
     that module) plus `import board_trail_view` and
     `from board_trail_view import (TRAIL_CSS, <all 25 MOVED_NAMES>)`. It
     precedes every import-time use.
   - Cut the three regions (reverse order), leaving a one-line pointer where
     the section comment stood.
   - `KanbanApp.CSS`: delete the `.trail-drift` line and the `#trail_summary`
     comment + rule; close the literal with `""" + TRAIL_CSS`.
   - `_get_local_project` (`:11207`): `load_local_project_name(TASKS_DIR)`.
   - Drop `from cross_repo_notation import parse_ref as parse_cross_repo_ref`
     (`:51`) — its only users moved and no test reads it. Confirm with the
     child-2 AST probe: every name imported into `aitask_board.py` is loaded in
     it or is a declared re-export (`board_widgets`, `board_trail_view`,
     `trail_discovery`, `mark_glyphs` lists).

3. **Shared model checks — `tests/lib/trail_model_checks.py` (new).**
   The seven projection tests of `TrailModelTests` that exercise moved code
   (`test_glyph_map_pins_schema_classification_enum`,
   `test_lanes_wave_and_position_order`,
   `test_entry_resolution_live_archived_missing_cross_repo`,
   `test_drift_by_ref_grouping_and_trail_level_drop`,
   `test_drift_text_bounds_and_truncation`,
   `test_drift_matches_the_t_prefixed_ref_spelling`,
   `test_build_trail_lanes_threads_drift_to_entries`) move **verbatim** into a
   plain mixin `TrailModelChecks` whose only seams are `self.tv` (the module
   under test) and `self.make_task(filename, status="Ready")`; `ab.` becomes
   `self.tv.` / `trail_schema.` / `trail_discovery.` (the last two imported from
   `lib/` directly). `FIXTURE_PATH`, `load_fixture()` and `ghost_doc()` move
   there too, and `test_board_bytrail_view.py` imports them under its existing
   names (`_load_fixture`, `_ghost_doc`) instead of defining them — one copy.
   No board import, no `board_fixture` import.

4. **`tests/test_board_bytrail_view.py`.**
   - `TrailModelTests(TrailModelChecks, ByTrailTestBase)`: `tv` = `self.ab`
     (through the re-exports, as before), `make_task` = `self._mk_task`; keeps
     its two `trail_discovery` tests (`test_compute_trail_overlaps`,
     `test_fold_dedup_precedence`) in place. Assertions unchanged in intent.
   - NEW `HeadlessTrailModelTests(unittest.TestCase)` beside it: a subprocess
     (`sys.executable -c`, `PYTHONPATH` = `tests/lib` + `board` + `lib`,
     `cwd=REPO_ROOT`, `TASK_DIR` unset) whose script imports `board_trail_view`
     and `trail_model_checks`, runs `TrailModelChecks` with `tv =
     board_trail_view` and a `SimpleNamespace(filename, metadata)` task, and
     prints `{"run", "ok", "loaded"}` (`loaded` = which of `aitask_board`,
     `board_fixture` are in `sys.modules`). Asserts `ok`, `run` == the number
     of `test_` methods on `TrailModelChecks` (anti-vacuity, counted in the
     parent) and `loaded == []`. The import lives inside the script string, so
     `LiveTreeSweepTests` (tier 1) does not flag it — the `HeadlessImportTests`
     shape. Negative control: the same script with `import aitask_board`
     prepended reports it loaded.
   - `load_local_project_name(ab.TASKS_DIR)` at `:2777`, `:2794`.

5. **NEW `tests/test_board_trail_view.py`** (fixture tier via
   `bf.FixtureBoardTestBase`; reaches the module only as
   `self.ab.board_trail_view`; added to `MIGRATED_MODULES`). Holds
   `MOVED_NAMES` (the 25 above) as the one list:
   - **`SingleHomeTests` — source-level, name by name, private names included.**
     Pure helper `_top_level_bindings(source) -> dict[name, lineno]` over the
     module body's `FunctionDef` / `AsyncFunctionDef` / `ClassDef` / `Assign`
     (every `Name` target, tuple targets unpacked) / `AnnAssign` targets —
     imports are not bindings. Pure checker
     `_single_home_findings(board_src, view_src, names)` returns one finding per
     name that is **missing from the view** or **bound in the board**, each
     naming the file and line. Tests:
     - on the real `aitask_board.py` / `board_trail_view.py`: `[]`, with a
       `subTest` per name so a failure names it;
     - completeness both ways: `set(_top_level_bindings(view_src))` ==
       `set(MOVED_NAMES) | {"TRAIL_CSS"}` — nothing moved without being listed,
       nothing listed that the view does not define;
     - the board **imports** every name (the `from board_trail_view import (…)`
       node lists all 25 + `TRAIL_CSS`), so re-exports cannot silently shrink;
     - negative controls on synthetic sources through the same checker:
       (a) a board source that imports `_trail_badge_text` and **re-defines it
       above the import** (the shape identity cannot see) → flagged;
       (b) the same re-definition **below** the import → flagged;
       (c) a module-level `_TRAIL_GHOST_LABELS = {…}` left in the board →
       flagged; (d) a view source missing `run_trail_drift` → flagged;
       (e) a board source that only imports the names → clean.
   - `ReexportIdentityTests`: every moved name + `TRAIL_CSS` —
     `getattr(ab, n) is getattr(ab.board_trail_view, n)`; the five classes'
     `__module__ == "board_trail_view"`; negative control on a namespace copy.
     (Runtime complement to the source check: proves the fixture-loaded board
     binds the extracted objects.)
   - `TrailCssTests`: `TRAIL_CSS in ab.KanbanApp.CSS`; each declaration line of
     `TRAIL_CSS` occurs **exactly once** in `KanbanApp.CSS` (no leftover
     duplicate); anti-vacuity: it declares `.trail-drift` and `#trail_summary`.
     Order independence under Pilot: a bare `App` whose `CSS` is `TRAIL_CSS`
     **followed by** `.task-info { color: red; }` renders a
     `Label(classes="task-info trail-drift")` in `#FFB86C`. Negative control:
     the same App with the old single-class `.trail-drift` rule renders red —
     the order dependence is real and the selector is what removes it.
   - `ModalDefaultCssTests`: each of the three modals pushed in a bare `App`
     with no CSS lays out its own dialog (`#dep_picker_dialog` width 60%,
     `#trail_detail_dialog` / `#trail_summary_dialog` 80%, screen align
     center). Negative control: a `TrailSelectScreen` subclass with
     `DEFAULT_CSS = ""` does not get the 60% width.

6. **Guards and path-keyed tests that follow the code (C5).**
   - `tests/test_board_fixture_harness.py`: `MIGRATED_MODULES` gains
     `test_board_trail_view.py`; `FreshLoadC2Tests` real-tree test also asserts
     `board_trail_view` is in `report["modules"]` and `fresh` (+ docstring);
     `:181` → `load_local_project_name(self.ab.TASKS_DIR)`.
   - `tests/test_board_marking.py::test_ghost_cards_are_mounted_only_by_the_bytrail_column`:
     scan every `.aitask-scripts/board/*.py`; exactly one construction site
     overall, located in `board_trail_view.py`, the scanned set contains it
     (anti-vacuity); message lists `file:line`.
   - `tests/test_mark_glyphs_single_source.py`: the `aitask_board.py` `✓` waiver
     reason loses the "by-trail freshness" clause (that literal moved to
     `board_trail_view.py`, which renders no mark and is not a `CONSUMER`);
     it still earns its place — the picker tick `:4912` and gate-row `:6524`.
   - No `lib/shortcut_scopes.py` row: the moved screens declare no
     `_shortcuts_scope` (checked). `test_board_package_contract.py` is not
     edited: `UnresolvedGlobalsTests` and every C1 guard glob `board/*.py`, so
     they cover the new module automatically.

7. **Pointers to the moved code.**
   `lib/followup_kinds.py:22` and the drift note in
   `website/content/docs/workflows/implementation-trails.md:35` →
   `board/board_trail_view.py`; `aidocs/implementation_trail_design.md:623`
   names both files (view state / workers / keys in `aitask_board.py`;
   projection, cards, columns, modals in `board_trail_view.py`);
   `tests/lib/board_fixture.py` docstring rows for `TRAIL_GATHER_SCRIPT` and
   `load_local_project_name` name `board_trail_view.py`.

## Verification

All of this runs **before** the Step 8 review, on the uncommitted change.

- `bash tests/run_all_python_tests.sh` → last line `PYTHON SUITE: PASSED`
  (`${PIPESTATUS[0]}` if piped). The 4 `test_parallel_admission_collect`
  date-rot failures are owned by t1799 and reported as such if still present.
- `~/.aitask/venv/bin/python -m pytest tests/test_board_bytrail_view.py
  tests/test_board_trail_view.py tests/test_board_widgets.py
  tests/test_board_package_contract.py tests/test_board_fixture_harness.py
  tests/test_board_keymap_characterization.py tests/test_board_marking.py
  tests/test_board_followup_glyph.py tests/test_board_plan_approved_marker.py
  tests/test_board_move_command.py tests/test_mark_glyphs_single_source.py
  tests/test_textual_markup_colours.py tests/test_board_reference_doc_literals.py -q`
  green; keymap golden **unchanged**.
- C4 bash guards: `test_no_lib_to_tui_import.sh`, `test_no_raw_tmux.sh`,
  `test_shortcuts_registry_coverage.sh`, `test_keybinding_registry.sh`,
  `test_serial_carveout_doc_drift.sh`; `pytest tests/test_shortcut_scopes.py
  tests/test_task_dir_module_constants.py`.
- **Single home, name by name:** `SingleHomeTests` green (the enforced form).
  Independent shell cross-check of the same claim, one line per name, all 25:
  ```bash
  for n in TRAIL_WATCH_INTERVAL TRAIL_WATCH_MAX_TICKS TRAIL_GATHER_SCRIPT \
      TRAIL_CLASSIFICATION_GLYPHS _TRAIL_GHOST_LABELS TrailEntryView TrailWaveLane \
      load_local_project_name trail_ref_to_local_id canonical_trail_ref \
      build_trail_lanes trail_drift_by_ref trail_summary_text run_trail_drift \
      _GhostTaskStub _trail_badge_text _trail_drift_text TrailTaskCard \
      TrailGhostCard TrailColumn _trail_stored_freshness TrailSelectItem \
      TrailSelectScreen TrailDetailScreen TrailSummaryScreen; do
    b=$(grep -cE "^(class|def) $n\b|^$n\s*[:=]" .aitask-scripts/board/aitask_board.py)
    v=$(grep -cE "^(class|def) $n\b|^$n\s*[:=]" .aitask-scripts/board/board_trail_view.py)
    echo "$n board=$b view=$v"
  done | awk '$2!="board=0" || $3!="view=1" {bad=1; print "BAD", $0} END {exit bad}'
  ```
  Exit 0 ⇔ every name is defined exactly once in the view and nowhere in the
  board.
- Red runs (in-process, no repo edits): `_single_home_findings` neutered to
  `[]` turns controls (a)–(d) red; the headless probe sees the board when it
  is imported; identity check on a copied namespace; CSS order-dependence
  control; empty-`DEFAULT_CSS` control; C2 real-tree anti-vacuity with
  `board_trail_view` dropped from the report; the marking scan at its old
  scope finds 0 sites.
- Website: `cd website && python3 check_links.py --build`.
- **Manual smoke — one route, exact provenance, before the commit.** The shared
  checkout also carries t1799's uncommitted edits, so neither it nor a plain
  detached worktree of `HEAD` shows *this change alone*. Two isolated
  worktrees built from one recorded base:
  1. `BASE=$(git rev-parse HEAD)`; list this task's code paths in
     `$SCRATCH/paths.txt` (the tracked files it modifies + its three new files:
     `board/board_trail_view.py`, `tests/lib/trail_model_checks.py`,
     `tests/test_board_trail_view.py`).
  2. **base** — `git worktree add --detach aiwork/t1794_3_smoke_base "$BASE"`.
  3. **change** — `git worktree add --detach aiwork/t1794_3_smoke_change "$BASE"`;
     `git diff --binary "$BASE" -- $(tracked paths) | git -C aiwork/t1794_3_smoke_change apply`;
     copy the three new files in. **Fail closed** unless
     `git -C aiwork/t1794_3_smoke_change status --porcelain -uall` lists exactly
     `paths.txt` — that is the provenance claim (`$BASE` + this task's diff, no
     foreign edit). Record `$BASE` and the diff's `sha256sum` in the plan.
  4. `./.aitask-scripts/aitask_init_data.sh --link-worktree <wt>` for both
     (expect `LINKED` / `ALREADY_LINKED`).
  5. In each worktree, on a private tmux socket (`tmux -L ait_smoke_$$`,
     `unset TMUX TMUX_PANE`, 200×50), launch `./ait board` and drive, waiting
     for a screen state specific to each step before sending the next key
     (`capture-pane` polling, 20 s cap per step, fail on timeout): boot → `z` →
     "Select trail — ↑/↓ move · Enter open · Esc cancel" → `enter` → a `W1 ·`
     wave header → `enter` on the focused card → "Trail totals:" → `escape` →
     `v` → "Trail summary" → `escape` → `d` → freshness banner in the header →
     `q` → the process exits. Save each step's capture.
  6. Pass ⇔ both worktrees reach every state, no capture contains
     `Traceback`, and base/change captures differ only in timestamps /
     freshness verdict text. Record the step list and outcome in the plan.
  7. Teardown: `kill-session -t =<session>` only (never `kill-server`; the
     private server exits when empty); remove **only** the two smoke worktrees
     this step created (they hold copies, no work), then confirm with
     `git worktree list` that neither remains.
  The committed SHA is **not** re-smoked: step 3's status check proves the
  change worktree holds exactly the paths the path-scoped commit will name.

## Risk

### Code-health risk: low
- A moved body references a name `board_trail_view.py` does not import, or a moved string is silently re-encoded; the import succeeds and the failure fires only on a rarely rendered path (ghost card, drift marker, detail reveal) · severity: low (residual — addressed by the per-block substring check and the existing `UnresolvedGlobalsTests`, which globs every `board/*.py`, plus the render-level suites in `test_board_bytrail_view.py`) · → mitigation: none
- A stale second implementation stays in the board beside the re-export (copy-and-reexport mistake); a copy above the import is rebound silently, so identity tests stay green · severity: low (residual — addressed by step 5's `SingleHomeTests`, name by name over all 25 moved names with both-way completeness and above/below-import negative controls, plus the shell cross-check) · → mitigation: none
- A patch on a moved name goes silently inert (the t1613 class) · severity: low (residual — the C3 sweep finds only `run_trail_drift` ×4, whose caller stays in the App half and reads the board's global; the patched tests assert on the fake's verdict, which the real verb cannot produce under the fixture) · → mitigation: none
- Relocating the two trail CSS rules changes the cascade (`.trail-drift` relied on source order after `.task-info`; `#trail_summary` moves to the end of the literal) · severity: low (residual — `#trail_summary` is ID-only with no competing rule; the two-class drift selector removes the order dependence, pinned by step 5's order-independence test and its negative control; the pane-height render tests stay the net) · → mitigation: none
- A path-scoped source guard goes vacuous when its literal leaves `aitask_board.py` · severity: low (residual — the one reader of moved code, `test_board_marking`, is rescoped with anti-vacuity in step 6; the other source readers were checked and inspect code that stays) · → mitigation: none
- The shared worktree holds t1799's uncommitted edits to `test_board_package_contract.py` / `shortcut_scopes.py` · severity: low · → mitigation: none (neither file is edited; path-scoped commit; the smoke runs in an isolated, status-checked worktree)

### Goal-achievement risk: low
- The headless claim ("the pure core runs without the board") could pass vacuously if the probe cannot see the board or runs no checks · severity: low (residual — subprocess with a clean `PYTHONPATH`, a run-count anti-vacuity assertion and a negative control that imports the board) · → mitigation: none
- A manual smoke with ambiguous provenance (shared checkout with foreign edits, or a worktree holding `HEAD` instead of the change) would report "unchanged" without having run this change · severity: low (residual — addressed by the single isolated-worktree route in Verification, which fails closed unless the change worktree holds exactly this task's paths) · → mitigation: none
- `TRAIL_CSS` is narrower than the parent's C7 wording: widget / card / picker / loading CSS stays with the host App, so child 6 must supply it · severity: low · → mitigation: none (stated in `TRAIL_CSS`'s own comment, recorded for siblings, and offered as a note to t1794_6 at Step 8e)

Every identified risk is low and already addressed by this plan's own
numbered steps, so no separate mitigation is proposed
(`risk_mitigations_planned = false`; no `### Planned mitigations` block).

## Post-implementation

Task-workflow Step 8 (review; path-scoped code commit
`refactor: Extract the pure trail view into board_trail_view.py (t1794_3)`;
plan commit), Step 8e (offer a note to t1794_6: TRAIL_CSS does not carry the
widget/card/loading CSS a second App needs), Step 9 (gates — `risk_evaluated`;
archive `t1794_3`).
