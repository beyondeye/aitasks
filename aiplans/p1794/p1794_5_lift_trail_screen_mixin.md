---
Task: t1794_5_lift_trail_screen_mixin.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_6_*.md … t1794_12_*.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-17 14:44
---

# p1794_5 — Lift the App half of By-Trail into `TrailScreenMixin` (verified)

## Context

Child 5 of t1794 (parent plan `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`,
contracts C1/C3/C10 PINNED, "Scope decisions" for `run_dialog_command`).
Children 1–4 extracted the widgets, the pure trail view and the task data layer.
The App half of By-Trail — its state, ~37 methods, launch helper and bindings —
still lives on `KanbanApp`, so a second App (child 6, `ait trails`) cannot host
the screen. This child moves it into `board/board_trail_screen.py` as
`TrailScreenMixin` behind an explicit `TrailHost` protocol. `ait board` must not
change observably: the child-1 key-map golden stays **unchanged**.

## Verification of the original plan (2026-09-17, HEAD 454329428)

Rebase check: `board/` last changed at a3e08bd1b (t1794_4). t1647_5 and t1296 are
still `Ready` (not landed); the only foreign `Implementing` task touching recent
code (t1816) changed brainstorm/diffviewer/lib only. No foreign work on this
region. `aitask_board.py` is now 10,277 lines; all line numbers below are current.

Corrected premises (the rest of the plan holds):

1. **`TRAIL_BINDINGS` cannot be spliced as one block.** The trail rows interleave
   with board rows (`r refresh_board` / `r trail_refresh_local`, `s sync_remote` /
   `s trail_select`, `enter` among the movement keys, `T` after `b`, `M` after
   `m`). Instead `board_trail_screen` defines the canonical list plus an
   action-keyed map `TRAIL_BINDING`, and `KanbanApp.BINDINGS` references
   `TRAIL_BINDING["<action>"]` at each original position. Same objects (C10
   identity), same order (golden unchanged).
2. **`_refresh_subtitle` moves into the mixin** (it is the trail chrome writer,
   `:5700–5749`). It is therefore not a host member. Its non-trail fallback reads
   `manager.auto_refresh_minutes` / `manager.settings`, which stay in `TrailHost`
   exactly as the original plan listed.
3. **`run_dialog_command`'s hook takes the refocus filename:**
   `_after_dialog_command(refocus_filename)`, because today's body calls
   `refresh_board(refocus_filename=refocus_filename)` (`:8757`).
4. **`CODEAGENT_SCRIPT` / `CODEAGENT_FAILURE_NOTICE`** (`:174, :178`) are read by
   both moved code (`_launch_trail`, `run_dialog_command` default) and staying code
   (pick/resume/work-report). C1 forbids importing the board, so they move to
   `board_trail_screen.py` and the board re-imports them (`ab.CODEAGENT_*` keeps
   resolving; both are cwd-relative, C2-safe).
5. **More C3 sites than listed.** `run_dialog_command` reads
   `find_terminal` / `spawn_in_terminal` / `subprocess`:
   `tests/test_board_dialog_run_dispatch.py:237–279` (6 `find_terminal`, 1
   `spawn_in_terminal`) and `tests/test_board_work_report.py:242–243` patch them on
   `ab`. Also one **direct read** `ab._trail_versions(handle)` inside a patch lambda
   (`tests/test_board_bytrail_view.py:1363`). The `patch.object(ab.subprocess,
   "call")` patches mutate the shared module and stay live.
6. **MagicMock worker tests** (`RunDialogCommandWorkerTests`) assert
   `app.manager.load_tasks` / `app.refresh_board` on a bare `MagicMock`. With the
   hook, those would silently stop being reached. `_call` binds the real board
   hook onto the mock (`app._after_dialog_command = lambda r:
   ab.KanbanApp._after_dialog_command(app, r)`), so every existing assertion
   stays and still proves the end-to-end refresh.
8. **Review concern (verified 2026-09-17): "extracted `T` action raises
   NameError".** The premise does not hold for this plan. The mixin's
   `action_trail_task` is only the policy seam, and the body that reads
   `TaskCard._parse_filename` / `topic_key` stays in `aitask_board.py` as
   `_trail_task_target`, with both names bound there. The underlying gap is real:
   only the normal-view `T` launch has a real-path test
   (`test_board_bytrail_view.py:901`). The By-Topic root resolution and the
   inflight/bytrail/modal early returns are untested, and the seam test stubs
   `_trail_task_target`. Addressed by explicit ownership notes in steps 1–2 and
   `TrailTaskRealPathTests` in step 3.
7. Board-shared launch patches (`resolve_dry_run_command`, `resolve_agent_string`,
   `AgentCommandScreen`, `launch_in_tmux`, `TmuxLaunchConfig`) stay on `ab` in
   `test_board_dialog_run_dispatch.py` / `test_board_work_report.py`
   (pick/resume/work-report callers stay in the board). They are repointed only
   where the caller is `_launch_trail` (`test_board_bytrail_view.py`).

## Implementation

### 1. `.aitask-scripts/board/board_trail_screen.py` (NEW)

Module docstring: C1/C2 contract, the host-protocol rule, and "patch trail
launch/drift names here, not on `aitask_board`". No `aitask_board` import and no
task-dir resolution. Imports: `re`, `shlex`, `subprocess`, `Path`, `Protocol`;
`rich` `cell_len`/`set_cell_size`/`Text`; textual `work`, `Binding`, `Static`,
`NoMatches`; `agent_command_screen.AgentCommandScreen`;
`agent_launch_utils` (`find_terminal`, `spawn_in_terminal`,
`resolve_dry_run_command`, `resolve_agent_string`, `TmuxLaunchConfig`,
`launch_in_tmux`, `maybe_spawn_minimonitor`); `keybinding_registry.resolve_key`;
`topic_semantics.task_own_id`; `trail_discovery` (`discover_trails`,
`_trail_versions`, `load_trail_blob`, `compute_trail_overlaps`);
`board_widgets.LoadingOverlay`; `board_trail_view` (`TrailColumn`, the three
screens, `TRAIL_WATCH_*`, `build_trail_lanes`, `trail_drift_by_ref`,
`trail_summary_text`, `run_trail_drift`, `load_local_project_name`).

Contents:
- `CODEAGENT_SCRIPT`, `CODEAGENT_FAILURE_NOTICE` (moved verbatim).
- `TRAIL_BINDINGS` — the 9 `Binding` rows moved verbatim from `:5008–5016, 5029,
  5056` plus `enter view_details` (`:4989`), in board declaration order.
  `TRAIL_BINDING = {b.action: b for b in TRAIL_BINDINGS}`. The explanatory
  comments on the duplicate-key pairs stay at the board's use sites.
- `TRAIL_ACTION_CAPABILITIES = {"trail_move_wave": ("_review_then",
  "_choose_move_destination", "_column_title", "marked", "_reject_stale",
  "_apply_move_to_column"), "trail_sync": ("_run_sync",)}`.
- `class TrailHost(Protocol)` with docstring and members:
  - attributes: `manager`, `tasks_dir`, `base_filter`, `sub_title`, `title`
  - methods: `refresh_board`, `_focused_card`, `_modal_is_active`,
    `_get_focused_col_id`, `_queue_refocus`, `apply_filter`, `refresh_bindings`,
    `_banner_budget`, `_after_dialog_command`, `_trail_task_target`, `notify`,
    `push_screen`, `pop_screen`, `set_interval`, `call_after_refresh`,
    `query_one`, `query`, `suspend`
  - `REQUIRED_WIDGETS: ClassVar = ("HeaderTitle", "#trail_summary",
    "#trail_summary_body", "#board_container")` (mount target for `TrailColumn`;
    `LoadingOverlay` is pushed, not queried)
  - `MANAGER_MEMBERS: ClassVar = ("load_tasks", "task_datas", "child_task_datas",
    "find_task_including_archived", "auto_refresh_minutes", "settings")`
  - the optional capabilities are documented via `TRAIL_ACTION_CAPABILITIES`.
- `class TrailScreenMixin` (no `__init__`):
  - `_init_trail_state()` — the attribute block `:5108–5139`, verbatim with its
    comments.
  - `_has_trail_capability(action) -> bool` — every name in
    `TRAIL_ACTION_CAPABILITIES[action]` resolves via `hasattr`.
  - Verbatim moves (bodies unchanged except the listed edits):
    `_trail_depth_note`, `_trail_banner`, `_refresh_trail_summary`,
    `_refresh_subtitle`, `_rerender_trail`, `action_trail_summary_expand`,
    `action_trail_refresh_local`, `action_trail_refresh_drift`,
    `action_trail_refresh_agent`, `action_trail_select`, `action_trail_sync`,
    `action_trail_move_wave`, `_get_local_project` (edit: `self.tasks_dir` for
    `TASKS_DIR`), `_render_bytrail`, `_build_active_trail_lanes`,
    `_open_trail_select`, `_trail_discovery_worker`, `_on_trail_discovery`,
    `_open_trail_select_from_cache`, `_activate_trail`, `_start_trail_drift`,
    `_trail_drift_worker`, `_on_trail_drift`, `_reload_active_trail`,
    `_trail_reload_worker`, `_on_trail_reload`, `_stop_trail_watch`,
    `_install_trail_watch`, `_trail_watch_tick`, `_trail_watch_worker`,
    `_on_trail_watch`, `_launch_trail`, `_with_trail_baseline`,
    `_trail_baseline_worker`, `_finish_trail_launch`, `_after_trail_launch`.
  - `action_trail_sync` / `action_trail_move_wave`: first line
    `if not self._has_trail_capability("<action>"): return`, then today's body.
  - `action_trail_task`: `target = self._trail_task_target(); if target is None:
    return; self._launch_trail([target], target)`. It references **no** module
    global: the target-resolution body (which reads `TaskCard._parse_filename`,
    `task_own_id` and `topic_key`) stays in the board as `_trail_task_target`
    (step 2). So `board_trail_screen` deliberately does not import `TaskCard` or
    `topic_key`. If a later change moves that body into the mixin, it must add
    `from board_widgets import TaskCard` and `from topic_semantics import
    topic_key`. `UnresolvedGlobalsTests` (`test_board_package_contract.py`, which
    scans every `board/*.py`) fails on the omission, and the real-path test in
    step 3 fails at runtime.
  - `_open_trail_entry_detail(card) -> bool` — the trail branch of
    `action_view_details` (`:7470–7477`); returns `False` when the card has no
    `trail_entry`.
  - `run_dialog_command` (`:8725–8757`, `@work(exclusive=True)`) — last two
    lines become `self._after_dialog_command(refocus_filename)`.
- Build method by method with a script from the original line ranges (the t1794_3
  technique). Then check that every unedited method body is a substring of the
  new module before editing the board.

### 2. `.aitask-scripts/board/aitask_board.py`

- `import board_trail_screen` next to the other bare imports, plus
  `from board_trail_screen import (CODEAGENT_FAILURE_NOTICE, CODEAGENT_SCRIPT,
  TRAIL_ACTION_CAPABILITIES, TRAIL_BINDING, TRAIL_BINDINGS, TrailHost,
  TrailScreenMixin)` with a re-export comment in the existing style, stating that
  trail launch/drift/discovery stubs patch `ab.board_trail_screen`. Delete the two
  constant definitions `:174, :178`. Update the `board_trail_view` comment
  (`:106–108`, "`run_trail_drift` is still patched here") because it becomes
  false.
- `class KanbanApp(TuiSwitcherMixin, ShortcutsMixin, TrailScreenMixin, App)`.
- `BINDINGS`: replace each of the 10 rows with `TRAIL_BINDING["<action>"]` in
  place, keeping every surrounding comment.
- `__init__`: replace the state block with `self._init_trail_state()`, keeping a
  one-line pointer comment.
- Delete the moved methods. Remove imports that become dead in the board, but only
  if no re-export list or test reads them off `ab`. `trail_discovery` /
  `board_trail_view` re-exports stay (`SingleHomeTests` requires them). Check with
  pyflakes-style `UnresolvedGlobalsTests` plus `grep`.
- New board members:
  - `tasks_dir` property → `TASKS_DIR` (read at call time, fixture-safe).
  - `_trail_task_target()` — today's `action_trail_task` body (`:8217–8242`)
    verbatim, with `return None` for each early `return` and `return target`
    in place of the launch. It stays in `aitask_board.py`, where its globals are
    already bound: `TaskCard` (the `board_widgets` re-export, `:88`), and
    `task_own_id` / `topic_key` (the `topic_semantics` import, `:351–353`, still
    used by other board code, so it is not a dead import).
  - `_after_dialog_command(refocus_filename="")` — `self.manager.load_tasks();
    self.refresh_board(refocus_filename=refocus_filename)`.
  - `action_view_details`: `if self._open_trail_entry_detail(focused): return`
    before `open_task_detail`.
- **Stays unchanged:** `check_action` (incl. all trail gates), `_set_base_filter`,
  `action_view_bytrail`, `refresh_board` bytrail branch, `apply_filter`,
  `_banner_budget`, `action_move_to_column` / `_apply_move_to_column`, `_run_sync`,
  every other `run_dialog_command` caller.

### 3. Tests

- **`tests/test_board_bytrail_view.py`** — repoint every `patch.object(ab, …)` of
  `discover_trails` (×8), `_trail_versions` (×7), `run_trail_drift` (×4),
  `load_trail_blob` (×2), `resolve_dry_run_command` (×4), `resolve_agent_string`
  (×3), `AgentCommandScreen` (×2), `launch_in_tmux` (×2),
  `maybe_spawn_minimonitor` (×2) and `TmuxLaunchConfig` (×1) to
  `ab.board_trail_screen`. Also repoint the direct read at `:1363`. Leave the
  `ab.trail_discovery` patches (`:2838, :3276`), the `patch.object(app, …)`
  instance patches and the `isinstance(…, ab.AgentCommandScreen)` identity
  asserts as they are. Also sweep `ab.<name> =` and
  `addCleanup(setattr, ab, …)` for the same names (t1794_4 note).
- **`tests/test_board_dialog_run_dispatch.py`** (`:237–279`) and
  **`tests/test_board_work_report.py`** (`:242–243`): `find_terminal` /
  `spawn_in_terminal` → `ab.board_trail_screen`. The MagicMock `_call` helpers
  bind the real board hook (premise 6).
- **Mutant per repointed name** (C3), in-process with no file edits: rebind the
  owning module's name to a raising sentinel inside the test's own patch scope.
  Alternatively, temporarily call the ORIGINAL object from the board's namespace
  and confirm the tests that depend on the patch go red. Record one line per name
  in Final Implementation Notes.
- **`tests/test_trail_screen_host_protocol.py`** (NEW, fixture harness, added to
  `MIGRATED_MODULES` in `tests/test_board_fixture_harness.py`):
  - `_protocol_members(TrailHost)` including underscore members (not dunders).
    Anti-vacuity: equals the expected literal set.
  - `HOSTS = [("KanbanApp", lambda ab: ab.KanbanApp)]`, parametrised for child 6.
    For each host: every member present on an instance, every `MANAGER_MEMBERS`
    entry on `app.manager`, every `REQUIRED_WIDGETS` selector resolves with
    `query_one` under Pilot after boot (200×48), and
    `_has_trail_capability` is true for both actions.
  - Negative controls: a `SimpleNamespace` host missing `_trail_task_target`, a
    manager missing `settings`, and a Pilot App composing no `#trail_summary` are
    each reported. `_has_trail_capability("trail_sync")` is false on a stub
    without `_run_sync`, and a spy proves `action_trail_sync` returns before
    `push_screen`.
  - Binding identity: every object in `TRAIL_BINDINGS` appears in
    `KanbanApp.BINDINGS` **by `is`**, exactly once. No other board binding
    carries a `TRAIL_BINDINGS` action. Negative control: a `Binding` copy with
    equal fields is reported.
  - `_trail_task_target` policy seam: `action_trail_task` calls `_launch_trail`
    with `([t], t)` iff the target is not `None` (spy on both).
  - **Real `T` path, not stubbed** (`TrailTaskRealPathTests`,
    `FIXTURE_TASKS = bf.RICH_TOPOLOGY`, whose t9003/t9005 carry `anchor: 9002`,
    t9000_1/t9000_2 are children of t9000, and t9004 is a singleton). A real
    `KanbanApp` under Pilot, with only the outward launch seam stubbed:
    `AgentCommandScreen`, `resolve_dry_run_command` and `resolve_agent_string` on
    `ab.board_trail_screen`, plus `app.push_screen`, recording construction
    args. Each case focuses a **real rendered card** (fail, never skip, when the
    card is absent) and presses `T` through `pilot.press` (the actual binding and
    `check_action` dispatch), then calls `app.action_trail_task()` for the cases
    where the gate hides the key:
    - `all` view, focus t9003 → exactly one launch, `operation_args == ["9003"]`,
      `prompt_str == "/aitask-trail 9003"`.
    - `bytopic` view, focus t9003 → `["9002"]` (anchor root). Focus t9004 →
      `["9004"]` (own id). Focus the t9000 parent → `["9000"]`. Focus a t9000
      child card after expanding it → `["9000"]` (child fallback).
    - `inflight` and `bytrail` → `action_trail_task()` records **zero** launches.
      A modal pushed (a `LoadingOverlay`) → zero launches. Each zero-call row
      carries a liveness row **in the same test** (the `all` launch above,
      re-asserted after the zero-call action) so an inert spy cannot pass it.
    - Mutant (recorded in the notes, in-process): rebinding the board's
      `topic_key` to `lambda *a: None` turns the `bytopic` t9003 row red
      (`["9003"]`). This proves the test runs the board's resolution, not a copy.
    `test_trail_task_launch_args` (`test_board_bytrail_view.py:901`) keeps its
    normal-view check. These tests add the By-Topic, gated and modal branches
    that were not covered before.
  - `run_dialog_command` hook: the suspend path calls
    `_after_dialog_command(refocus)` exactly once.
  - **Inert-patch guard (durable C3):** AST-scan `tests/*.py` for
    `patch.object(<ab|self.ab|B|board>, "<name>")`, `<ab>.<name> = …` and
    `addCleanup(setattr, <ab>, "<name>", …)`, where `<name>` is a global that
    `board_trail_screen.py` loads and `aitask_board.py` never loads outside its
    import statements (computed from the two ASTs, not hand-listed).
    Anti-vacuity: the computed set contains `discover_trails`, `_trail_versions`,
    `run_trail_drift` and `load_trail_blob`. Negative control: a synthetic
    `patch.object(ab, "discover_trails", …)` source is flagged.
- **`tests/test_board_package_contract.py`** — `HeadlessImportTests` gains
  `board_trail_screen` (imports without loading `aitask_board`; names include
  `TrailScreenMixin`, `TrailHost`, `TRAIL_BINDINGS`). `PatchPairingTests` covers
  the bare import automatically.
- **`tests/test_board_fixture_harness.py`** — the C2 fresh-load anti-vacuity
  sibling list gains `board_trail_screen`.
- **Characterization golden** `tests/test_board_keymap_characterization.py`: run
  **unchanged**. A red run means a splice or gate is wrong, so fix the code, never
  the golden.

### 4. Docs and pointers

- `tests/lib/board_fixture.py` docstring inventory: `CODEAGENT_SCRIPT` now lives
  in `board_trail_screen.py`.
- `aidocs/implementation_trail_design.md` component list, if it names
  `KanbanApp` trail methods: one pointer line to `board_trail_screen.py`
  (current-state prose only).

## Verification

- `~/.aitask/venv/bin/python -m pytest tests/test_board_bytrail_view.py
  tests/test_trail_screen_host_protocol.py tests/test_board_keymap_characterization.py
  tests/test_board_package_contract.py tests/test_board_fixture_harness.py
  tests/test_board_dialog_run_dispatch.py tests/test_board_work_report.py
  tests/test_board_trail_view.py tests/test_board_widgets.py
  tests/test_shortcut_scopes.py -q` green.
- `bash tests/run_all_python_tests.sh` → last line `PYTHON SUITE: PASSED` (read
  the last line; use `set -o pipefail` if piping). Any failure is compared against
  a clean BASE worktree before it is called pre-existing, never with stash.
- C4 bash guards: `tests/test_shortcuts_registry_coverage.sh`,
  `tests/test_keybinding_registry.sh`, `tests/test_no_raw_tmux.sh`,
  `tests/test_no_lib_to_tui_import.sh`, `tests/test_serial_carveout_doc_drift.sh`,
  `tests/test_mark_glyphs_single_source.py`.
- Residual `grep -n 'def .*trail' aitask_board.py`: expected only
  `action_view_bytrail`, `_trail_task_target`. Record the actual list in the
  notes.
- Manual smoke in tmux (isolated worktree per sibling notes; focus starts in
  search, so Escape first): `ait board` → `z` → selector → Enter → lanes → `v` →
  Esc → Enter on card (detail) → Esc → `d` → `r` → `s` (Esc) → `R` dialog (cancel)
  → `M` review (cancel) → `S` → `q`. Then in the normal view, `T` on a card opens
  the trail dialog, while in By-Trail `T` is absent from the footer. No traceback.

## Post-implementation

Task-workflow Step 8 review → path-scoped code commit `refactor: Lift the By-Trail
App half into TrailScreenMixin (t1794_5)` → plan commit → Step 9 (gates run,
archive `t1794_5`). Step 8e offers to note t1794_6 (the `_refresh_subtitle`
ownership, the `TRAIL_BINDING` map, and `_after_dialog_command(refocus)`).

## Risk

### Code-health risk: medium
- Silent patch inertness: the board keeps re-exporting `discover_trails` /
  `_trail_versions` / `run_trail_drift` / `load_trail_blob`, so a missed
  `patch.object(ab, …)` stays green in the passing direction ·
  severity: medium · → mitigation: none (in-plan: computed inert-patch guard with
  negative control + per-name mutants)
- A ~1,000-line verbatim move could drop an import or subtly edit a body ·
  severity: medium · → mitigation: none (in-plan: script-built move, substring
  check, `UnresolvedGlobalsTests`, headless import probe, 4.5k-line bytrail suite)
- `run_dialog_command` (serving 8 board launches) now lives in a trail module per
  the pinned scope decision, which is a naming/ownership oddity for future
  readers · severity: low · → mitigation: none (docstring states why)
- Board key map drift from the per-row `TRAIL_BINDING` references ·
  severity: low · → mitigation: none (golden unchanged + identity test)

### Goal-achievement risk: low
- `TrailHost` may still miss a member that only a non-board host exercises
  (child 6 would rework the protocol) · severity: low · → mitigation: none
  (user declined; t1794_6's `test_trails_app.py` host-protocol run covers it)
- The hook binding in the MagicMock worker tests could weaken what they prove ·
  severity: low · → mitigation: none (assertions unchanged; hook reached through
  the real board method)
