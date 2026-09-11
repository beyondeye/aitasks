---
Task: t1794_split_board_monofile_and_standalone_trail_tui.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1794 — Split the board mono-file and carve out a stand-alone trails TUI

### Pre-phase (risk mitigations)

This parent's implementation body is the child decomposition below, so its
inline pre-phases are realised as child scope (a decomposed parent never runs
Steps 7/8 itself):

1. [characterize_board_keymap_and_views] **Child 1 additionally lands a
   characterization test** (`tests/test_board_keymap_characterization.py`)
   that pins, before any extraction: the full `KanbanApp.BINDINGS` key → action
   table (`aitask_board.py:8796–8905`), the `check_action` visibility matrix
   for every action across the six `base_filter` values (`:8982–9280`), and the
   widget ids / classes the trail view queries (`HeaderTitle`, `#trail_summary`,
   `#trail_summary_body`, `#board_container`, `LoadingOverlay`). The table is a
   golden literal in the test, generated once from the fixture-loaded module
   and reviewed by hand; children 5 and 6 must keep it green unchanged, which
   is what makes "the board behaves exactly as before" a checked claim rather
   than an asserted one. Negative control: a temporarily removed binding in a
   copy of the table fails the test.
2. [rebase_check_before_each_child] **Every child plan's first step is a
   rebase check**: `git log --oneline -20 -- .aitask-scripts/board/` since the
   plan's recorded SHA; re-read every region the child moves against the
   current tree (line numbers in this plan are `e2f12c499` anchors, not
   contracts); grep pending `aitasks/` for tasks now `Implementing` on the
   board (`grep -l '^status: Implementing' aitasks/*.md aitasks/t*/*.md` ∩
   the board regex from child 9) and treat any landed decision — t1647_5's
   By-Trail command in particular — as ground truth to rebase onto, naming in
   the child plan which premise it corrected. A child that finds a foreign
   `Implementing` task on its region stops at its own plan checkpoint
   ("Approve and stop here") instead of forking ahead.

## Context

`.aitask-scripts/board/aitask_board.py` is 14,102 lines / 92 classes and is
still growing (15 commits in the last 25 days; t1647_1 already started lifting
trail seams into `lib/trail_discovery.py`). The By-Trail view (~1,800 lines) is
the most self-contained subsystem in it and is the one users want to open
without paying for the whole Kanban app. This task (a) turns `board/` into a
package of flat-imported modules and (b) ships the By-Trail screen as a
stand-alone `ait trails` TUI that is also reachable from the board and from the
`j` switcher — while `ait board` keeps every existing key, view (including the
embedded By-Trail view) and modal.

The parent task is decomposed into **11 children** (plus the aggregate
manual-verification sibling the workflow offers). This plan fixes the target
file map and the cross-child contracts; each child plan is written after
approval and is self-contained.

Exploration verified the task file's structural claims against HEAD
`e2f12c499` (line numbers below are current) and an adversarial review pass
corrected the first draft in four places (module naming, the `TaskManager`
patch-mode tests, the `aitask_board` import-back prohibition, the trail host
protocol). No other task is `Implementing` on board/trail code
(`aitask_query_files.sh inflight` → `NO_INFLIGHT`), so no child is gated on
foreign in-flight work.

## Decisions (settled with the user — PINNED, do not re-decide in children)

| Decision | Value |
|---|---|
| Subcommand / tmux window name / registry name | **`ait trails`**, window `trails`, label "Trails" |
| Launcher / app file | `.aitask-scripts/aitask_trails.sh` → `.aitask-scripts/board/trails_app.py` |
| Switcher quick-jump key | **`i`** (registered under `shared.tui_switcher`; `t` is stats) |
| Interpreter | Launcher uses **`require_ait_python`** (CPython). PyPy only if the t718_6 benchmark in child 11 shows a win (`aidocs/framework/tui_conventions.md` forbids routing by analogy). |
| Stand-alone scope | **Read-only trail flows**: select / detail / summary / local refresh / drift / artifact watch / agent launch (`/aitask-trail`). `m`/`M` move-to-column and `S` task-data sync stay board-only. `m` is a board binding and is not declared in the trails App; `M` and `S` are members of the shared `TRAIL_BINDINGS` and therefore **stay declared** in `TrailsApp.BINDINGS` (one override owner) but are **hidden and non-dispatching** there — `check_action → False` plus a capability guard inside the action methods, so neither the default nor a remapped key reaches them (verification contract in child 6). |
| Board `z` view | **Unchanged and embedded.** `tests/test_board_bytrail_view.py` (4,584 lines) is the arbiter of "unchanged". Board ↔ trails hand-off is the switcher (`j`, `i`), not a `z` delegation. |
| Board CLI | `aitask_board.py` stays argument-free. No `--view` flag. |
| Shortcut ownership | **The trails TUI uses the board's customizable keys — the same `(board, <action>)` entries.** `TrailsApp` sets `_shortcuts_scope = "board"`; there is no `trails` scope. The trail bindings are single-sourced as `TRAIL_BINDINGS` in `board_trail_screen.py` and spliced into both Apps' `BINDINGS`, so a rebind of `shortcuts.board.trail_select` (or any trail action) in `ait board`, in `ait trails`, or in Settings → Shortcuts changes the key in both. |
| `T` in the stand-alone | **Bound and live**: `/aitask-trail <task_id>` for the focused **live local member** (author/refresh a trail rooted at that task); a ghost, cross-repo or unfocused card gives a visible `notify` and no launch. The embedded board keeps hiding `T` in By-Trail (`check_action :9264–9271`) — behaviour selected by a host policy method, not by a shared `base_filter` gate. |
| Package style | `board/__init__.py` added (docstring only); **all intra-board imports stay flat**, modules are `board_*`-prefixed, and **no `board/*.py` other than `trails_app.py`'s own launcher path may import `aitask_board`**. |

## Target file map (end state)

```
.aitask-scripts/board/
  __init__.py               docstring only: C1/C2 contract
  aitask_board.py           KanbanApp + Kanban render paths + board key-map/check_action +
                            module constants + _load_task_types/_get_user_email/_current_tmux_session
  board_widgets.py          ColumnHeader (:3181), MarkedSelection (:3335), TaskCard (:3402–3609),
                            badge/marker helpers (:706–730, :3778–3915), PickerItem (:4205–4230),
                            LoadingOverlay (:8004–8059)
  board_trail_view.py       pure trail code: :1162–1360, _GhostTaskStub (:3761–3776), :3917–4106,
                            :4286–4788 (three modals) + TRAIL_CSS
  board_task_model.py       Task (:753–937), MoveResult (:1364)
  board_task_manager.py     TaskManager (:1459–2958) + the module helpers only it calls
  board_workflow_phase.py   workflow-phase derivation (:223–617; pure, no global reads)
  board_trail_screen.py     TrailHost Protocol + TrailScreenMixin (the 34 trail methods,
                            :9429–9702, :10342, :11060–11136, :11733–12199, the trail branch of
                            action_view_details :11293–11300, run_dialog_command :12551–12581)
  trails_app.py             TrailsApp(TuiSwitcherMixin, ShortcutsMixin, TrailScreenMixin, App)
  board_detail_screen.py    TaskDetailScreen (:6882–7709) + field widgets (:4900–5820) +
                            detail-only pickers (:6058–6546)
  board_column_dialogs.py   ColorSwatch (:7803), ColumnSelectItem/Screen (:8017–8059),
                            ColumnManageItem/Screen (:8060–8397), ColumnMultiSelectScreen (:6546)
  aitask_merge.py           (unchanged, unrelated CLI)
.aitask-scripts/aitask_trails.sh
tests/perf/board_footprint.sh              (child 1; manual, not auto-run)
tests/test_board_package_contract.py       (child 1: C1 guards)
tests/test_board_fixture_harness.py        (child 1 extends: C2 guard — the AC names this file)
tests/test_trail_screen_host_protocol.py   (child 5)
tests/test_trails_app.py                   (child 6)
website/content/docs/tuis/trails/{_index,how-to,reference}.md (child 10)
```

The `board_` prefix follows `lib/board_columns.py` / `board_groups.py` /
`board_ordering.py` and avoids the basename collision a bare `widgets.py` would
have with `brainstorm/widgets.py`: `lib/shortcut_scopes.py:83–89` puts every
manifest module's directory on `sys.path` from a **set**, so a duplicate
basename resolves nondeterministically (the docstring at `:80–81` states the
"no colliding basenames" invariant explicitly). Verified: none of the new
basenames exists anywhere under `.aitask-scripts/`.

## Cross-child contracts (PINNED)

**C1 — Flat imports; no import-back; unique basenames.**
- Every `board/*.py` imports siblings by bare name (`import board_trail_view`),
  never `board.`-qualified. `aitask_board.py` and `trails_app.py` insert their
  own directory on `sys.path` next to the existing `lib` insert
  (`aitask_board.py:17`) so the contract holds under all five loaders: the
  launcher (`python board/<app>.py`), the fixture harness
  (`spec_from_file_location`, `tests/lib/board_fixture.py:534`), the shortcut
  sweep (`lib/shortcut_scopes.py:73–89`), the canonical `import aitask_board`
  in 17 test files, and the subprocess loader in
  `tests/test_task_dir_module_constants.py:129–158` (`PYTHONPATH` includes
  `board`).
- **No `board/*.py` may import `aitask_board`.** Under `load_board_module()`
  such an import would execute the *canonical* board while `TASK_DIR` is still
  set (`board_fixture.py:530–539`), rebinding the canonical `TASKS_DIR` to a
  temp tree and breaking `test_board_movement.IsolationNegativeControlTests`,
  and it mints a second `KanbanApp`/`Task` identity (the t1613 class). Helpers
  that both moved and staying code need (`_load_task_types :692`,
  `_get_user_email :730`, `_current_tmux_session :5630`) stay in
  `aitask_board.py` and are **injected as callables** into the moved consumers.
- A `board/*.py` module that owns a name tests patch is also **bare-imported**
  by `aitask_board.py` (`import board_task_manager` next to
  `from board_task_manager import TaskManager`), exactly as `:60–66` already
  does for `trail_discovery`, so `ab.board_task_manager` is a real patch target.
- No two directories reachable by the flat contract may share a `*.py`
  basename.
- Guards (child 1, `tests/test_board_package_contract.py`, each with a
  negative control): AST scan for `board.`-qualified imports under
  `.aitask-scripts/` and `tests/`; AST scan for `import aitask_board` /
  `from aitask_board` in `board/*.py` other than `aitask_board.py`; basename
  uniqueness across the manifest dirs; the bare-import pairing for every
  module that defines a name appearing in a `patch.object(` in `tests/`.

**C2 — No import-time `TASKS_DIR` in any module other than `aitask_board.py`.**
`load_board_module()` re-execs only `aitask_board.py` with `TASK_DIR` set and
restores the env in `finally` (`board_fixture.py:540–544`), so a sibling that
calls `task_dir()` at import binds the *live* tree and one that calls it at
runtime binds the *restored* env — both wrong. Moved code receives paths **by
parameter**: `TaskManager(*, tasks_dir, metadata_file, gates_registry_file,
…)` (required kw-only), `load_local_project_name(tasks_dir, config_path=None)`,
`TrailsApp(tasks_dir=…)`. Guard (child 1, **in
`tests/test_board_fixture_harness.py`** as the acceptance criteria require): AST
scan of every `board/*.py` except `aitask_board.py` for a module-level
`task_dir(` call or any of `TASKS_DIR`, `METADATA_FILE`, `GATES_REGISTRY_FILE`,
`USERCONFIG_FILE`, `EMAILS_FILE`, `TASK_TYPES_FILE`, plus a runtime check after
`load_board_module()` that no sibling in `sys.modules` holds a `Path` attribute
under the fixture tree; negative control via a synthetic offending module.
`tests/test_task_dir_module_constants.py` remains the positive control for
`aitask_board.py`'s own constants.

**C3 — Patch targets follow the symbol; every repointed patch is proven live by
a mutant.** `TaskManager` reads the board globals **at call time**
(`:1538–1539, 1547, 1561, 1645, 1723, 1775, 1836, 1855, 1879, 1926–1935, 2114,
2863`) and `KanbanApp.__init__` constructs it with no paths
(`:8909 TaskManager(on_warning=self.notify)`). Three "patch-mode" test files
construct `B.TaskManager()` bare inside a `patch.object(B, "TASKS_DIR"/
"METADATA_FILE"/…)` (`tests/test_board_persistence_seam.py:198–204, 719–722`,
`tests/test_board_manager_moves.py:91–97`, `tests/test_board_column_manage.py:93–98`;
documented as deliberate exemptions in `tests/test_board_fixture_harness.py:344–366`).
Under constructor injection those `setUp`s are rewritten to pass the patched
values explicitly; the child-4 pinning test constructs `TaskManager` **the way
they do**, not via `KanbanApp`. Other patched names and the child that moves
their caller: `datetime` (`:864`, `Task.save` → child 4), `save_local_config` /
`save_project_config` / `load_layered_config` / `project_columns_at` (→ child 4),
`discover_trails` ×8, `_trail_versions` ×7, `run_trail_drift` ×4,
`resolve_dry_run_command` ×4, `resolve_agent_string` ×3, `AgentCommandScreen`,
`launch_in_tmux`, `load_trail_blob`, `maybe_spawn_minimonitor`, `TmuxLaunchConfig`
(all called from the App half — `:11812, 12167, 11900–11906, 12083+` → child 5).
Every moving child: (a) greps `patch.object(ab|B|self.ab, "<name>"` for each
moved name, (b) repoints to the owning module, (c) records a one-line mutant
per repointed patch (bypass the call → the test goes red).

**C4 — Every child boundary is green.** `bash tests/run_all_python_tests.sh`
(read the last-line verdict) plus `tests/test_shortcut_scopes.py`,
`tests/test_shortcuts_registry_coverage.sh`, `tests/test_keybinding_registry.sh`,
`tests/test_no_raw_tmux.sh`, `tests/test_no_lib_to_tui_import.sh`,
`tests/test_serial_carveout_doc_drift.sh`, `tests/test_task_dir_module_constants.py`.
`ait board` must boot and every existing key/view/modal must work — the
manual-verification sibling covers the live checks.

**C5 — Path-keyed manifests are updated in the child that creates or moves the
file** (child 1 records the inventory; later children copy it):
`lib/shortcut_scopes.py:47–65` `KNOWN_BINDING_SOURCES` (a `_shortcuts_scope`
follows its class — `board.detail` moves with `TaskDetailScreen`; `trails` is
new), `lib/tui_registry.py:17–30`, `lib/tui_switcher.py` four-part change,
`tests/test_mark_glyphs_single_source.py:82,117,132`,
`tests/test_no_raw_tmux.sh:48–56` (allowlist stays untouched because the three
raw-`tmux` sites `:5634, 12212, 12391` all stay in `aitask_board.py` —
`_current_tmux_session` is pinned there by C1),
`tests/test_board_reference_doc_literals.py`, `tests/test_record_protocol.py:14,133`
(docstring only — the `board_columns` import stays in `aitask_board.py`),
`tests/test_board_fixture_harness.py:479–493` `_canonical_board_imports`
(widened in child 1 from the literal `"aitask_board"` to the full board module
set, so a canonical `import board_task_manager` in a fixture test is caught),
`tests/test_shortcuts_registry_coverage.sh:31` (`PYTHONPATH` gains
`.aitask-scripts/board` in child 6, so the harness does not depend on
module-body ordering).

**C6 — Layering.** Nothing moves to `lib/` in this task; all extracted modules
stay in `board/` (`tests/test_no_lib_to_tui_import.sh` already lists `board`).
`lib/` promotion is a retrospective-child question, not a default.

**C7 — Trail presentation is single-sourced.** Child 3 exports `TRAIL_CSS`
from `board_trail_view.py` holding every rule the trail view depends on today
(`.trail-drift :8582`, `#trail_summary :8620`, the `#board_container` layout
rule `:8606`, `TaskCard.markable-card:* :8576,8580`); both Apps interpolate it
into their `CSS`, and a test asserts `TRAIL_CSS in KanbanApp.CSS` and `in
TrailsApp.CSS`. The three trail modals additionally get a `DEFAULT_CSS`
(`tui_conventions.md` "Modals pushed by multiple Apps").

**C8 — Measurement protocol.** RSS after 10 s idle and cold-start
(`import <module>`) under **both** `~/.aitask/venv/bin/python` and
`~/.aitask/pypy_venv/bin/python`, same fixed task tree (this repo at a recorded
SHA), reported as **signed margins** against the child-1 baseline. No
"saves memory" claim without a number from `tests/perf/board_footprint.sh`.

**C9 — Sequencing.** Children 1→8 form a strict chain in the order below
(each rewrites `aitask_board.py`; parallel children would conflict). The
pattern is proven on the least-coupled modules first (widgets: zero patch
sites, zero global reads; pure trail: one global read, zero patch sites) before
the manager (≈20 call-time global reads, three patch-mode test files). Child 9
(notes) depends on child 1 only. Child 10 (website docs) depends on 6. Child 11
depends on 8 and 10. The manual-verification sibling depends on its verified
children.

**C10 — One owner for the trail keys, one policy seam for `T`.**
- `keybinding_registry` keys overrides by `(scope, action_id)` and resolves
  them from `aitasks/metadata/userconfig.yaml` `shortcuts:` (`:46–85, :144–158`);
  user overrides for trail actions already live under `shortcuts.board.*`
  (`resolve_key("board", "trail_refresh_agent", "R")`, `aitask_board.py:9685`).
  So the stand-alone App registers under **scope `board`**, and its trail
  `Binding` objects are **the same objects** as the board's: child 5 defines
  `TRAIL_BINDINGS` in `board_trail_screen.py` (`trail_select s`,
  `trail_refresh_local r`, `trail_refresh_drift d`, `trail_refresh_agent R`,
  `trail_sync S`, `trail_summary_expand v`, `trail_task T`, `trail_move_wave M`,
  `view_details enter` — today's `:8832–8841, 8854, 8881` rows) and
  `KanbanApp.BINDINGS` splices `*TRAIL_BINDINGS` in place of those rows;
  `TrailsApp.BINDINGS` = `*TRAIL_BINDINGS` + `Binding("q", "quit", "Quit")`
  (the board's `:8799`) + `*SWITCHER_BINDINGS` + the `?` editor. Because
  `register_app_bindings` overwrites `_DEFAULTS[(board, action)]` with the
  last registrant's default (`:135`), identity of the objects is what makes
  a second registration a no-op rather than a silent default change.
- Test (child 6): every `(action, key, description)` in `TrailsApp.BINDINGS`
  minus `{tui_switcher, open_shortcuts_editor}` equals the corresponding
  `KanbanApp` row; a fixture `userconfig.yaml` with
  `shortcuts: {board: {trail_select: x}}` rebinds `x` → `trail_select` in
  **both** Apps under Pilot; negative control: an override under a
  hypothetical `trails` scope changes nothing.
- Manifest: `KNOWN_BINDING_SOURCES` row
  `("trails_app", "board/trails_app.py", ("board",))` — two modules may claim
  one scope (`register_scope_bindings` filters by relevance, `:216–229`;
  registration is idempotent). Documented limitation: `?` inside `ait trails`
  opens the board-scope editor, which lists the Kanban actions too and
  imports `board/aitask_board.py` under the probe name on that keypress only.
- `T` policy seam: the mixin's `action_trail_task` is
  `target = self._trail_task_target(); if target is None: return;
  self._launch_trail([target], target)`. The **board's** `_trail_task_target`
  is today's body verbatim (`:12042–12066`: modal/`inflight`/`bytrail` gate,
  ghost gate, By-Topic root resolution) so the embedded behaviour and its
  `check_action` gate are unchanged. `TrailsApp._trail_task_target` returns
  the focused card's task id when it is a live local member
  (`TrailTaskCard` with `trail_entry.task` resolved, not `is_ghost`), and
  otherwise `notify("T needs a live local task under focus")` and `None`.
  `TrailsApp.check_action("trail_task")` is true whenever a card is focused,
  so the footer advertises exactly what works.

## Scope decisions (explicit)

- Workflow-phase derivation (`:223–617`, task item 5) **is in scope**: it is
  pure (no global reads) and lands in `board_workflow_phase.py` in child 4.
- `run_dialog_command` (`:12551–12581`) is lifted into the mixin (child 5) with
  a host hook `_after_dialog_command()` (board: `load_tasks` + `refresh_board`;
  trails: reload lanes) so one implementation serves both Apps and the three
  `patch.object(app, "run_dialog_command")` instance patches keep one target.
- The shortcut sweep re-execs manifest modules under a probe name
  (`shortcut_scopes.py:124–160`), minting a second class identity for every
  class in a manifest module. That is pre-existing for everything in
  `aitask_board.py`; `grep` finds no `isinstance(…, TaskDetailScreen)` today.
  Child 7 re-runs that grep for every class it moves and records the result —
  a documented limitation, not a new guard.
- The CHANGELOG is generated at release by `/aitask-changelog` from archived
  plans; no manual entry.

## Children

Priority `medium` for all (inherits the parent). Labels
`aitask_board,tui,trails,python,refactor` unless noted. Created with
`--gates risk_evaluated` (profile default). Each child's plan carries its own
`## Verification` section and owns the test updates its change causes — no
test fixes are deferred to a later child.

### 1. `board_package_contract_and_baseline` — type `test`, effort medium, labels + `test_infrastructure`
- `board/__init__.py`; own-dir `sys.path` insert in `aitask_board.py:17`
  (evidence the package marker is inert elsewhere: no `import board` /
  `from board.` anywhere; the only `__init__.py`-walking tool,
  `tests/test_python_bootstrap_isolation.sh:117`, scans `tests/` only;
  `install.sh:1066–1071` chmods top-level `*.sh` and `lib/*.sh` only).
- C1 guards in `tests/test_board_package_contract.py`; C2 guard in
  `tests/test_board_fixture_harness.py`; widen `_canonical_board_imports`
  (`:479–493`). Each with a negative control.
- `tests/perf/board_footprint.sh`: launches a TUI module in a tmux pane through
  the gateway (`lib/tmux_exec.sh`), samples RSS at 10 s idle, measures import
  cold-start; parameters: module, interpreter; one-line record. Record the
  `aitask_board` baseline under both interpreters in a new
  `aidocs/framework/python_tui_performance.md` section "t1794 baseline", and
  the **ceiling**: RSS of a process importing only `textual`, `rich`, `yaml`
  and the Textual widgets the trail view uses — the floor child 6's number is
  judged against.
- Inventory (C5) recorded in the child plan.
- Verification: guards red→green with negative controls; full suite green;
  two baseline lines + ceiling line produced.

### 2. `extract_board_widgets` — effort medium
- `board_widgets.py` per the file map. `TaskCard`'s app surface documented as a
  `CardHost` Protocol: `check_action`, `action_toggle_children`,
  `action_view_details`, `expanded_tasks` (`:3602–3608`); `marked` is read only
  behind `self.markable` (`:3437`) and trail cards are non-markable by
  construction (`:3415–3419`) and override `on_click`. `InFlightTaskCard` stays.
- Zero patch sites, zero global reads (`Task`/`TaskManager` are string
  annotations under `from __future__ import annotations`).
- C5: `test_mark_glyphs_single_source.py` lists gain `board/board_widgets.py`;
  `test_board_reference_doc_literals.py` pins follow the badge helpers.
- Verification: `test_board_followup_glyph`, `test_board_plan_approved_marker`,
  `test_textual_markup_structure`, `test_board_inflight_view`,
  `test_board_workflow_phase` green.

### 3. `extract_trail_view` — effort high
- `board_trail_view.py` per the file map; `load_local_project_name(tasks_dir,
  config_path=None)` (C2 — its one global read, `:1207`); cards import from
  `board_widgets`; `TRAIL_CSS` + modal `DEFAULT_CSS` (C7). `aitask_board.py`
  bare-imports the module and re-imports every name flat (`TrailModelTests`
  read `ab.build_trail_lanes` etc.).
- Verification: `tests/test_board_bytrail_view.py` green unchanged in intent;
  `TrailModelTests` additionally run against `board_trail_view` imported
  directly with no board import (the headless pure-core test the extraction
  exists to enable); the C7 containment test.

### 4. `extract_task_model_manager_and_workflow_phase` — effort high
- `board_task_model.py` (`Task`, `MoveResult`), `board_task_manager.py`
  (`TaskManager` + helpers only it calls — enumerate by grep),
  `board_workflow_phase.py` (`:223–617`). Constructor takes the C2 paths
  kw-only **required**; `KanbanApp.__init__` (`:8909`) passes its globals;
  every call-time global read listed in C3 becomes a parameter read (or an
  injected callable for `_get_user_email`/`_load_task_types` if the manager
  calls them — confirm by grep).
- C3: rewrite the three patch-mode `setUp`s to pass the patched values
  explicitly; repoint `datetime`, `save_local_config`, `save_project_config`,
  `load_layered_config`, `project_columns_at` patches to the owning module;
  mutant per patch. Add a pinning test constructing `TaskManager` the way the
  patch-mode files do.
- Extend `tests/test_board_fixture_harness.py` (C2 runtime check covers the
  new modules automatically; add the explicit `board_task_manager` case as the
  documented example).
- Verification: `test_board_persistence_seam`, `test_board_manager_moves`,
  `test_board_movement` (incl. `IsolationNegativeControlTests`),
  `test_board_column_manage`, `test_followup_kind_phantom_stub`,
  `test_atomic_task_writes`, `test_board_workflow_phase`,
  `test_task_dir_module_constants` green; mutant proofs recorded.

### 5. `lift_trail_screen_mixin` — effort high
- `board_trail_screen.py`: `TrailHost` `Protocol` = exactly the non-trail App
  surface the 34 methods use — `manager` (`load_tasks`, `task_datas`,
  `child_task_datas`, `find_task_including_archived`, `auto_refresh_minutes`,
  `settings` — the last two via `_refresh_subtitle :9568–9573`, which is the
  boot state of `TrailsApp`), `tasks_dir` (for `_get_local_project :11736`),
  `refresh_board`, `_refresh_subtitle`, `_focused_card`, `_modal_is_active`,
  `_get_focused_col_id`, `_queue_refocus`, `apply_filter`, `refresh_bindings`,
  `_banner_budget`, `notify`, `push_screen`, `pop_screen`, `set_interval`,
  `call_after_refresh`, `call_from_thread`, `sub_title`, `base_filter`,
  `_after_dialog_command`; **required widget contract** as a class constant
  (`HeaderTitle` for `_banner_budget :9423`, `#trail_summary` /
  `#trail_summary_body :9509–9510`, `#board_container :9614`, `LoadingOverlay
  :11803`, a mountable `TrailColumn` target `:11778`); **optional
  board-only capabilities** (`_review_then`, `_choose_move_destination`,
  `_column_title`, `marked`, `_reject_stale`, `_apply_move_to_column`,
  `_run_sync`) — the mixin's capability query hides `trail_move_wave` /
  `trail_sync` when the host lacks them.
- `TrailScreenMixin`: the 34 methods, `_get_local_project`,
  `_init_trail_state()` (called from `KanbanApp.__init__`, `:8934–8964`),
  `_open_trail_entry_detail(card)` (the trail branch of `action_view_details`,
  `:11293–11300`; both Apps' `action_view_details` call it — trail cards call
  `self.app.action_view_details()` at `:4011, :4063`),
  `run_dialog_command` with the `_after_dialog_command` hook, the
  `TRAIL_BINDINGS` list (C10), and `action_trail_task` reduced to the
  `_trail_task_target()` policy seam with the board's `_trail_task_target`
  carrying today's body verbatim (C10). **Stays in the board:** the non-trail
  `BINDINGS` rows and `z` (`:8899`), `check_action` (`:8982–9280`, including
  the `trail_task` gate `:9264–9271`), `_set_base_filter` (`:10444–10449`),
  `refresh_board` bytrail branch (`:9750–9764`), `apply_filter` (`:10096`),
  `action_move_to_column` / `_apply_move_to_column` bytrail branches (`:11011`,
  `:11160`), `_run_sync` hook (`:12342`), `ViewSelector` entry.
- The child-1 characterization test (`KanbanApp.BINDINGS` table,
  `check_action` matrix) must stay green unchanged — that is the proof the
  splice and the policy seam changed nothing in the board.
- `tests/test_trail_screen_host_protocol.py`: every `TrailHost` member and
  widget id is present on `KanbanApp` (fixture-loaded) — and, from child 6, on
  `TrailsApp` — with a negative control (a stub missing one member is rejected).
- C3: the launch/drift patch targets move from `ab` to `ab.board_trail_screen`;
  mutant per patch.
- Verification: `test_board_bytrail_view.py` green; host-protocol test
  red→green.

### 6. `standalone_trails_tui` — effort high, labels + `tui_switcher`
- `trails_app.py`: `TrailsApp(TuiSwitcherMixin, ShortcutsMixin,
  TrailScreenMixin, App)`, **`_shortcuts_scope = "board"`** (C10),
  `current_tui_name = "trails"`; `BINDINGS = [*TRAIL_BINDINGS, Binding("q",
  "quit", "Quit"), *TuiSwitcherMixin.SWITCHER_BINDINGS]` (+ the mixin's `?`);
  `CSS` = own chrome + `TRAIL_CSS`; host provides `manager =
  TaskManager(tasks_dir=…, …)` used read-only, `tasks_dir`, the widget
  contract, `base_filter = "bytrail"`, `refresh_board` = re-render lanes,
  `_after_dialog_command` = reload lanes, `_trail_task_target` per C10, a
  `check_action` that returns `False` for `trail_move_wave` / `trail_sync`
  and `True` for `trail_task` iff a card is focused, and **none** of the
  board-only capabilities. `M` and `S` therefore remain **declared** in
  `TrailsApp.BINDINGS` (they are members of the shared `TRAIL_BINDINGS`, so
  their `(board, action)` override entries stay owned once) but are **hidden
  and non-dispatching**: `check_action → False` removes them from the footer
  and blocks dispatch; the action methods additionally guard on the same
  capability query, so a remapped key cannot reach them either. Auto-opens
  the selector on boot as the board does on `z`.
- `.aitask-scripts/aitask_trails.sh` mirrors `aitask_board.sh` with
  `require_ait_python` (decision) and the same three probes; `ait` dispatcher
  row + `TUI:` help line (`ait:28–39`); read
  `aidocs/framework/aitasks_extension_points.md` (new helper script).
- Registry/switcher four-part change: `tui_registry.py` row
  `("trails", "Trails", "ait trails", True)` right after `board`;
  `tui_switcher.py` `_TUI_SHORTCUTS["trails"] = "i"` (`:216–227`),
  `Binding("i", "shortcut_trails", "Trails", show=False)` in
  `_QUICK_JUMP_BINDINGS` (`:400–416`), `action_shortcut_trails` next to
  `action_shortcut_board` (`:1100`); `_HINT_ITEMS` (`:251–264`) only if the
  width one-liner in the comment (`:243–250`) still fits — measure, else leave
  it out and say so. `shortcut_scopes.py` row
  `("trails_app", "board/trails_app.py", ("board",))` (C10);
  `test_shortcuts_registry_coverage.sh` `PYTHONPATH` + `TUIS` entry.
  `CLAUDE.md:431–435` documented-TUI list gains `trails`.
- `tests/test_trails_app.py`: Pilot boot under the fixture tree
  (`TrailsApp(tasks_dir=Path("aitasks"))`, cwd = tree; no synthetic loader
  needed by C2), selector opens, lanes render for a fixture trail, `enter` →
  `TrailDetailScreen`, `v` → `TrailSummaryScreen`; **`T` on a focused live
  local member** with `resolve_dry_run_command` / `AgentCommandScreen` patched
  on `board_trail_screen` → exactly one launch requested with
  `op_args == ["<id>"]`; `T` on a focused ghost card → no launch and one
  `notify`; `T` with nothing focused → no launch; the C10 binding-identity and
  override-propagation tests; **declared-but-hidden contract** for
  `trail_move_wave` and `trail_sync`: both actions *are* in
  `TrailsApp.BINDINGS` (assert presence — the shared-ownership design
  requires it), `check_action` returns `False` for both, neither appears in
  `app.screen.active_bindings`, and pressing their key dispatches nothing —
  asserted with a spy on the two action methods after pressing the default
  key (`M`, `S`) **and** after pressing a remapped key supplied by a fixture
  `shortcuts: {board: {trail_move_wave: k}}` override; `m` and `z` are not
  declared at all (assert absence); the host-protocol test runs against
  `TrailsApp`. Extend for the new row:
  `test_shortcut_scopes.py`, `test_shortcuts_registry_coverage.sh`,
  `test_keybinding_registry.sh`, `test_settings_shortcuts_tab.py`,
  `test_tui_switcher_footer_fit.sh`, `test_session_key_collision.py`,
  `test_framework_version.py` (busy set contains `trails`),
  `test_tui_switcher_agent_launch.py`.
- Measurement (C8): `ait trails` RSS and cold-start vs child-1 baseline and
  ceiling, both interpreters, signed margins in the plan.

### 7. `extract_detail_screen` — effort high
- `board_detail_screen.py`: `TaskDetailScreen` (`:6882–7709`, scope
  `board.detail`), field widgets `CycleField` … `PullRequestField`
  (`:4900–5820`), detail-only pickers (`:6058–6546`) — confirm each is
  referenced only from the detail screen by grep before moving.
  `_load_task_types` (`:692`), `_get_user_email` (`:730`) and
  `_current_tmux_session` (`:5630`) **stay in `aitask_board.py`** (also called
  from `:10380, 12205, 12383`) and are injected as constructor callables (C1);
  `webbrowser` / `section_viewer` imports stay lazy.
  `TaskSelectScreenBase` / `WorkReportTaskSelectScreen` /
  `MoveTaskSelectScreen` (`:6613–6734`) are board actions and stay.
- C5: `KNOWN_BINDING_SOURCES` board row scopes → `("board",)`; new row
  `("board_detail_screen", "board/board_detail_screen.py", ("board.detail",))`.
  Raw-tmux allowlist untouched (see C5). Record the `isinstance` grep.
- Verification: `test_board_detail_gates_section`, `test_settings_shortcuts_tab`,
  `test_shortcut_scopes`, `test_board_reference_doc_literals`,
  `test_no_raw_tmux.sh` green.

### 8. `extract_column_dialogs` — effort medium
- `board_column_dialogs.py` per the file map; C3 sweep on
  `test_board_column_manage.py`.
- Verification: `test_board_column_manage` green; the markup-escape tests for
  `ColumnSelectItem.render()` (t1441/t1442 reference them) address the new
  module.

### 9. `notes_to_affected_tasks` — type `chore`, effort low, depends on 1 only
- Via `/aitask-note … --from 1794`, one note per pending task that cites the
  board mono-file or the By-Trail screen, re-derived at implementation time
  with `grep -lE 'aitask_board|ait board|By-Trail|bytrail|TrailDetailScreen|
  TrailSelectScreen|KanbanApp|TaskManager|TaskDetailScreen' aitasks/*.md
  aitasks/t*/*.md` (93 files today; re-check each target still exists
  before sending). The body **references the plan artifact**
  (`aiplans/p1794_…md`, sections "Target file map" and C1–C3) rather than
  inlining the map, and says "line numbers in your body are stale — re-derive
  against the new module". Specific notes: **t1647 / t1647_5** (adds a board
  command inside the By-Trail view — now `board_trail_screen.py` /
  `board_trail_view.py`), **t1613** (the duplicate-identity hazard this plan
  guards), **t1632** (board_columns seam), the **t1243** family, and the
  owners of the six active plans citing `aitask_board.py:NN` (p745, p1186,
  p1162, p1516, p1569, p1647).
- Verification: each `NOTE_APPENDED:` line captured in the child plan.

### 10. `website_docs_trails_tui` — type `documentation`, effort medium, labels + `website`, depends on 6
- New `website/content/docs/tuis/trails/` (`_index.md`, `how-to.md`,
  `reference.md`) modelled on `website/content/docs/tuis/minimonitor/`
  (relationship to the parent TUI in the first paragraph; reference owns the
  key map and the three launch forms: `ait trails`, switcher `i`, from the
  board via `j`).
- Board pages: `tuis/board/reference.md` (`:32–39,63,165,224,251–275`),
  `how-to.md` — embedded view stays, links to the new page for the full
  reference. `tuis/_index.md` bullets (`:17–22`; the Board bullet `:20`
  describes By-Trail and is rewritten), switcher paragraphs (`:32` lists the
  core TUIs, `:38` names the shortcut keys), cascade list (`:7–9`).
  `skills/aitask-trail.md:87` ("There is no `ait trail` command…") rewritten;
  `:12,72,92` relrefs; `workflows/implementation-trails.md:51,82`;
  `skills/aitask-backlog-roadmap.md:17`.
- Verification: `python3 check_links.py --build` (mandatory),
  `tests/lib/docs_vocabulary_scan.py`, `hugo build --gc --minify`, grep each
  documented key literal against `trails_app.py`; offer
  `check_link_relevance.py` as a report.

### 11. `measure_document_retrospective` — type `documentation`, effort medium, depends on 8 and 10
- Re-run `tests/perf/board_footprint.sh` for `aitask_board` and `trails_app`
  under both interpreters; run the t718_6 Pilot benchmark for `trails_app`;
  switch `aitask_trails.sh` to `require_ait_python_fast` **only** on a
  measured win (then extend the `AIT_USE_PYPY` table in `tui_conventions.md`).
- Update `aidocs/framework/python_tui_performance.md` (results, signed
  margins), `aidocs/framework/tui_conventions.md` (board package layout, C1/C2
  rules, trails as a switcher-visible TUI), `CLAUDE.md:143–147` (board file
  map → package), `aidocs/framework/aitasks_extension_points.md` if the new
  launcher pattern warrants a line.
- Retrospective: judge whether further extraction or `lib/` promotion is
  justified by the numbers; file standalone follow-ups **only** if the data
  says so.

### Manual-verification sibling
Offered by the workflow after the child plans are committed; should verify at
least children 5, 6, 10: `ait board` keys/views/modals unchanged (incl. `z`
By-Trail, `m`/`M`, `T` hidden in By-Trail), `ait trails` flows including `T`
on a live member launching `/aitask-trail <id>`, `j`/`i` hand-off in both
directions, monitor classifies the `trails` window as a TUI, minimonitor not
auto-spawned beside it, and a trail-key rebind made in `ait board` (`?`) is
the key `ait trails` uses after restart and vice versa.

## Hazard → owner map (from the task file)

| Hazard | Owner |
|---|---|
| 1 fixture harness re-execs only `aitask_board.py` | C1/C2 guards: child 1; applied: 3, 4, 6, 7 |
| 2 path-keyed manifests | C5: child 1 inventory; 2, 5, 6, 7 apply |
| 3 layering guard | C6: all (nothing to `lib/`) |
| 4 flat imports / `__init__.py` | C1: child 1 |
| 5 4.5k-line bytrail test is the net | children 3, 5, 6 |
| 6 installer exec bit (top-level `.sh` only) | child 6 (launcher at top level) |
| 7 PyPy resolver | decision: CPython; child 11 benchmarks |
| 8 duplicate-key bindings `r`/`s` | child 5 keeps `check_action` in the board; child 6 has clean keys |

## Verification (parent level)

- After child 11: `bash tests/run_all_python_tests.sh` last line `PYTHON SUITE:
  PASSED`; the bash tests in C4 pass; `shellcheck .aitask-scripts/aitask_trails.sh`.
- `ait trails` boots, `j` → `i` from the board reaches it and `j` → `b`
  returns; `ait board` → `z` unchanged.
- `aitask_board.py` no longer defines any class from the file map's other
  modules (grep for each class name returns only import lines).
- Signed-margin table for RSS/cold-start (board, trails, ceiling) present in
  `python_tui_performance.md`.

## Post-implementation

Each child follows task-workflow Step 9 (commit, gate run, archive). The
parent archives after child 11 and the manual-verification sibling via the
orphaned-parent path (Step 3 Check 2 / Step 9).

## Risk

### Code-health risk: high
- Wide blast radius: every child rewrites the 14k-line file that 50 test files
  mention and 8 path-keyed manifests pin; a missed manifest or a `board.`-
  qualified import surfaces only as a flake or a second class identity ·
  severity: high · → mitigation: none (bounded by C1/C2/C5 guards in child 1;
  residual is the size of the change, not a missing check)
- Silent patch inertness (the t1613 class): a repointed or forgotten
  `patch.object` stays green in the passing direction, so a child can land
  with its regression net cut · severity: high · → mitigation: none (C3's
  per-patch mutant proof is the control; it is a per-child obligation, not a
  phase)
- Embedded By-Trail view / board key map drifts while the trail methods move
  into a mixin (`check_action` gating of duplicate `r`/`s` keys, CSS split) ·
  severity: low (residual — addressed by inline pre-phase
  characterize_board_keymap_and_views) · → mitigation: inline pre-phase characterize_board_keymap_and_views
- Two Apps registering under one shortcut scope: a divergent default in
  either App silently rewrites `_DEFAULTS[(board, action)]` for the other
  (`keybinding_registry.py:135`) · severity: low · → mitigation: none (C10's
  single `TRAIL_BINDINGS` source plus the binding-identity test in child 6)

### Goal-achievement risk: medium
- The memory saving is unmeasured: a stand-alone app that still imports the
  Textual widget set may land within noise of the board, and the acceptance
  criteria only require reporting, not a target · severity: medium ·
  → mitigation: none (child 1's ceiling measurement bounds it before child 6
  is written; the AC is a signed-margin report, which child 11 delivers either way)
- Active churn on `aitask_board.py` (15 commits / 25 days, 93 pending tasks
  citing it): a child that edits against a stale tree, or ignores a landed
  decision (e.g. t1647_5's By-Trail command), produces conflicts or reverts
  someone's work · severity: low (residual — addressed by inline pre-phase
  rebase_check_before_each_child) · → mitigation: inline pre-phase rebase_check_before_each_child
- The `TrailHost` surface may be wider than enumerated; a member discovered
  only at child 6 forces rework of child 5 · severity: low · → mitigation: none
  (the host-protocol test runs against both Apps; the review pass already
  widened the enumeration by three members and the widget contract)

### Planned mitigations
- timing: pre-phase | name: characterize_board_keymap_and_views | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — embedded By-Trail view / board key map drift during the mixin lift | desc: characterization test pinning KanbanApp.BINDINGS, the check_action visibility matrix per base_filter, and the trail view's widget ids before any extraction; realised as child 1 scope
- timing: pre-phase | name: rebase_check_before_each_child | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — active churn on aitask_board.py and landed decisions of pending tasks | desc: every child plan opens with a rebase check against the current tree and a scan for foreign Implementing tasks on its region, stopping at its checkpoint instead of forking ahead

Post-inline reassessment (one pass against the augmented plan): code-health
stays **high** — the two `none`-linked bullets are the blast radius itself,
which no phase shrinks; goal-achievement stays **medium** — the unmeasured
saving remains a real, bounded concern until child 6 reports.
