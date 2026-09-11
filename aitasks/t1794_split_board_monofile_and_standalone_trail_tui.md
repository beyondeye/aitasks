---
priority: medium
effort: high
depends: []
issue_type: refactor
status: Implementing
labels: [aitask_board, tui, trails, python, refactor]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1794_1, t1794_2, t1794_3, t1794_4, t1794_5, t1794_6, t1794_7, t1794_8, t1794_9, t1794_10]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-09-10 23:34
updated_at: 2026-09-11 15:08
---

## Goal

`ait board` has grown into a very large single-file Textual TUI
(`.aitask-scripts/board/aitask_board.py`, 14,102 lines, 92 classes) with many
secondary screens, and it is heavy to run. This task (a) refactors the board
source out of the giant mono-file into common imported modules, and (b) carves
the **implementation-trails screen** ("By-Trail" view) out as a **separate TUI**
that can be launched stand-alone (`ait trail`, or similar) **while staying
reachable from the board TUI** exactly as today.

This is a complex, multi-step change and **must be decomposed into child tasks
at planning time** (see the suggested decomposition below). Every pending task
that refers to the board or to the implementation-trail screen must be sent a
note about the updated design (see "Notes to affected tasks").

## Measured starting point (2026-09-10, aitasks repo at e2f12c499, 403 parent task files)

- Running `ait board` RSS after 10 s idle: **317 MiB** under the PyPy venv
  (`~/.aitask/pypy_venv`, the `require_ait_python_fast` path the launcher
  chooses) vs **183 MiB** under `/usr/bin/python3` (CPython). `import textual,
  rich` alone is ~31 MiB on CPython; `import aitask_board` brings CPython to
  ~68 MiB before any data is loaded.
- **No memory concern is recorded anywhere in the repo.** The only recorded
  board performance metric is cold-start import time
  (`aidocs/framework/python_tui_performance.md`: `import aitask_board`
  ~202 ms). Any "saves memory" claim in this task must therefore be a
  before/after measurement in the same interpreter, with the same task tree,
  reported as signed margins — not an inference from line counts.
- Everything is imported eagerly: only 6 function-local imports in the whole
  file (`urlparse`, `webbrowser`, `section_viewer`, `SkipAction`,
  `SelectOverlay`). A split that keeps every module imported at boot is
  neutral on both memory and cold-start; the savings, if any, come from what a
  stand-alone trail TUI does **not** import (TaskManager, 40 modals, the
  Kanban render paths).

## Structure of the mono-file (line numbers at e2f12c499)

- `KanbanApp(TuiSwitcherMixin, ShortcutsMixin, App)` `:8487–14098` — ~5,600
  lines (40%): CSS `:8521–8795`, `BINDINGS` `:8796–8905`, `check_action`
  `:9030–9130`, all `action_*`, workers, render paths.
- `TaskManager` `:1459–2958` (~1,500 lines); `TaskDetailScreen` `:6882–7709`
  (~830 lines); 40 `ModalScreen` subclasses; ~45 widget classes; ~45 plain
  module functions (workflow-phase derivation `:223–617`, git/commit helpers,
  topic grouping `:1030–1160`).
- Module-level constants bind `TASKS_DIR` (from `task_dir()`, `TASK_DIR`-env
  sensitive) and derivatives at import time (`:109–126`) — this is what the
  test fixture harness rebinds (see hazards).
- `board/` is the only TUI directory with **no `__init__.py`**; it holds
  `aitask_board.py` and the unrelated CLI `aitask_merge.py`. All other TUIs
  (`monitor/`, `codebrowser/`, `logview/`, `agentcrew/`, …) are packages.
- `aitask_board.py` parses **no** arguments — `ait board "$@"` is forwarded by
  `aitask_board.sh` and silently ignored. A `--view`/`--screen` flag is
  greenfield.

## The trail screen today (~1,800 lines, 13% of the file)

Near-zero App coupling (~900 lines, liftable into a module with one import
back for `TaskCard`/`PickerItem`/`Task`):
- constants `:1162–1183`; dataclasses `TrailEntryView`/`TrailWaveLane`
  `:1185–1201`; projection helpers `load_local_project_name`,
  `trail_ref_to_local_id`, `canonical_trail_ref`, `build_trail_lanes`,
  `trail_drift_by_ref`, `trail_summary_text`, `run_trail_drift` `:1202–1362`;
- `_GhostTaskStub` `:3761–3777`; badges `_trail_badge_text`/`_trail_drift_text`
  `:3917–3947`; `TrailTaskCard`, `TrailGhostCard`, `TrailColumn` `:3948–4108`;
- `_trail_stored_freshness`, `TrailSelectItem`, `TrailSelectScreen`
  `:4286–4375`; `TrailDetailScreen` `:4376–4735` and `TrailSummaryScreen`
  `:4736–4790` — both already **pure** (no `self.app`, no `manager`).

Entangled with `KanbanApp` (~850 lines): state `:8934–8964`
(`active_trail_handle`, `_trail_*`, watch timer/handle/baseline/ticks),
`check_action` gating `:9041–9112` (hides non-trail actions in `bytrail`,
rebinds `r`/`s`), bindings `:8833–8841, 8854, 8881, 8899` (`r R d s S v T M z`),
header/summary/actions `:9429–9703`, `action_view_bytrail` `:10342`,
`action_trail_move_wave` `:11060–11177`, render + workers + launch
`:11739–12200` (`_render_bytrail`, `_trail_discovery_worker`,
`_activate_trail`, `_start_trail_drift`, `_install_trail_watch`,
`_launch_trail`, `_with_trail_baseline`, …). App surface these reach:
`self.manager` (`task_datas`, `child_task_datas`,
`find_task_including_archived`), `refresh_board`, `_refresh_subtitle`,
`_get_local_project`, `_focused_card`, `_modal_is_active`, `_run_sync`,
`run_dialog_command`, `notify`, `push_screen`, `base_filter`, `@work`.

External calls: `aitask_trail_gather.sh drift --trail <handle>`
(`run_trail_drift`); `ait artifact get/versions` only through
`lib/trail_discovery.py` (`load_trail_blob`, `_trail_versions`); the
`/aitask-trail` skill launch via `resolve_dry_run_command(Path("."), "trail",
…)` → `AgentCommandScreen` / `launch_in_tmux`. The board is **read-only** on
trails (`:1151–1160`, `lib/trail_discovery.py:20–25`) — keep that contract.
`aitask_board.py:53–66` re-exports `trail_discovery` names; tests patch on
`trail_discovery`, not on the board.

Existing shared modules the trail code already depends on:
`lib/trail_discovery.py` (291 l), `lib/trail_schema.py` (822 l),
`lib/trail_gather.py` (1,631 l, via the `.sh`), `lib/config_utils.py`,
`lib/agent_command_screen.py`, `lib/agent_launch_utils.py`.

## Precedent for a stand-alone TUI carved from a bigger one

`monitor/` ships **two Apps in one package** (`monitor_app.py`,
`minimonitor_app.py`) with two launchers (`aitask_monitor.sh`,
`aitask_minimonitor.sh`), two `ait` subcommands (`ait:211–212`), two
`lib/shortcut_scopes.py` entries (`:54–55`) and `lib/tui_registry.py`
entries. Targeted-launch flags exist in `codebrowser_app.py:1616–1630`
(`--focus PATH[:RANGE]`), `logview_app.py:226–235`, `monitor_app.py:3867`.
The board ↔ trail hand-off should reuse `TuiSwitcherMixin` / `tui_switcher`
rather than invent a new launch path.

## Hazards a split must handle (all measured, not guessed)

1. **Fixture harness re-execs only `aitask_board.py`.**
   `tests/lib/board_fixture.py:502–545` `load_board_module()` loads the file
   under a synthetic module name with `TASK_DIR` set, so import-time constants
   bind to the fixture. Sibling modules it imports come from the shared
   `sys.modules` and keep the canonical `TASKS_DIR`. **No moved module may
   bind `TASKS_DIR`-derived constants at import time** — pass paths in, or
   resolve lazily. This is the exact failure mode of pending
   `t1613_duplicate_lib_module_objects_make_test_patches_inert` (patches
   silently inert, green in the passing direction); a split multiplies it.
   `tests/test_board_fixture_harness.py` self-tests the harness — extend it.
2. **Path-keyed manifests** that must list any new file:
   `lib/shortcut_scopes.py:47–65` `KNOWN_BINDING_SOURCES` (a new
   `ShortcutsMixin`/`BINDINGS` file fails `tests/test_shortcut_scopes.py`
   otherwise; rule in `aidocs/framework/tui_conventions.md:871–906`);
   `lib/tui_registry.py:18` (needed for the `j` switcher and window
   classification); `tests/test_mark_glyphs_single_source.py:82,117,132`;
   `tests/test_no_raw_tmux.sh:56`; `tests/test_board_reference_doc_literals.py`
   (pins literals in `aitask_board.py` against
   `website/content/docs/tuis/board/reference.md`); `tests/test_record_protocol.py:14,133`.
3. **Layering guard:** `tests/test_no_lib_to_tui_import.sh` — `lib/` must
   never `sys.path`-insert or import a TUI package; `board` is already in its
   `TUI_PACKAGES` list. Shared code promoted out of the board goes to `lib/`
   only if it has no board imports; board-internal modules stay in `board/`.
4. **Tests import flat.** 18 test files `import aitask_board` after prepending
   `tests/lib`, `.aitask-scripts`, `.aitask-scripts/board`, `.aitask-scripts/lib`
   to `sys.path` (e.g. `tests/test_board_fixture_harness.py:26–33`); 50 files
   mention it. New `board/*.py` modules are importable with no harness change
   **as long as they import flat** (`import trail_view`, not
   `from board.trail_view import …`). Adding `board/__init__.py` must not
   break the flat import path; `tests/run_all_python_tests.sh` runs pytest
   with `--dist loadfile` and a serial carve-out
   (`test_serial_carveout_doc_drift.sh` keeps it in sync).
5. **`tests/test_board_bytrail_view.py` is 4,584 lines** and
   `tests/test_trail_gather.py` 2,713 — they are the regression net for the
   extraction and must stay green at every child boundary.
6. **Installer needs nothing:** `install.sh` extracts a tarball over
   `$INSTALL_DIR` (no per-file list); only top-level `*.sh` and `lib/*.sh`
   get the exec bit (`install.sh:1068–1070`). A new `aitask_trail_tui.sh`
   launcher at the top level is covered; a launcher inside `board/` is not.
7. **PyPy fast path:** `aitask_board.sh` resolves `require_ait_python_fast`
   and probes `textual`, `yaml`, `linkify_it`. The stand-alone trail launcher
   must go through the same resolver (see
   `aidocs/framework/python_tui_performance.md`; `t1386` verifies the board
   launch after resolver hardening).
8. **Duplicate-key bindings** (`r`/`s` mean different things in `bytrail` vs
   the kanban views, resolved in `check_action`) are the stickiest coupling —
   a stand-alone app gets clean bindings, but the embedded view must keep the
   board's key map documented at
   `website/content/docs/tuis/board/reference.md:32–39,63,224,251–275`.

## Suggested child-task decomposition (settle at planning; sequential unless noted)

1. **Characterize and pin the baseline** — RSS and cold-start under both
   interpreters with a fixed task tree; a repeatable script (e.g.
   `tests/perf/board_footprint.sh` or an aidoc procedure), so every later
   child reports a signed margin against it. Also inventory every path-keyed
   manifest/test that names `board/aitask_board.py`.
2. **Extract the pure trail code** into `board/trail_view.py` (constants,
   dataclasses, projection helpers, badges, cards/columns, the three modals) —
   behaviour-preserving, `aitask_board.py` re-imports; fixture-harness
   assertion that nothing in the new module binds `TASKS_DIR` at import time;
   manifests updated; full `tests/run_all_python_tests.sh` green.
3. **Lift the App half into a `TrailScreenMixin`** (own file) with an explicit,
   minimal host protocol (the `self.app` surface listed above) so a second App
   can host it; `KanbanApp` mixes it in; `check_action`/bindings unchanged.
4. **Stand-alone trail TUI**: `board/trail_app.py` App hosting the mixin
   without `TaskManager`/kanban screens, `aitask_trail_tui.sh` launcher via
   the PyPy resolver, `ait trail` (name to settle — `ait trail` may collide
   with the `aitask-trail` skill/codeagent op; consider `ait trails` or
   `ait board --view bytrail`), `tui_registry` + `shortcut_scopes` entries,
   board → trail hand-off via `TuiSwitcherMixin` and back; first `argparse`
   surface on the board if `--view` is chosen.

   **TUI switcher integration** (`j` overlay) — the registry is the single
   source of truth for *listing and launching*, but the quick-jump key is
   hand-wired in four places; the checklist, with the file that pins each:
   - `lib/tui_registry.py:17–30` `TUI_REGISTRY`: one row
     `(<window_name>, <label>, "ait <cmd>", True)`. The window name is the
     tmux `-n` name the launcher must create its window with — it is what
     `tmux_monitor.py` uses to classify the pane as a TUI, what
     `agent_launch_utils.py:1699` uses to exclude it from minimonitor
     auto-spawn, and what `framework_version.py:172–185` treats as a busy
     window during upgrade. Docstring `:1–9` says one entry is enough — true
     for the list/launch/classify half only.
   - `lib/tui_switcher.py` quick-jump wiring, all four or none:
     `_TUI_SHORTCUTS` `:216–227` (default key), `_QUICK_JUMP_BINDINGS`
     `:399–415` (`Binding(<key>, "shortcut_<name>", <label>, show=False)`),
     an `action_shortcut_<name>` method next to `:1100–1112` calling
     `self._shortcut_switch("<name>")`, and — **optional, budgeted** —
     `_HINT_ITEMS` `:251–262`: the hint row already renders 122 columns and
     the comment above it (`:245–250`) says membership is decided by width,
     not completeness; measure with the one-liner given there before adding.
     Taken keys: `a l b m f c s t y r x X g n e` (+ `j` open/close, `?`,
     escape/enter/arrows/`[`/`]`); `t` is stats, so the trail key must be
     something else (e.g. `i`, `w`), settled at planning and registered under
     `shared.tui_switcher` so the `?` editor and Settings → Shortcuts see it.
   - `lib/shortcut_scopes.py:47–65` `KNOWN_BINDING_SOURCES`: a row for the
     new app file with its scope tuple (e.g. `("trail_app",
     "board/trail_app.py", ("trail", "trail.detail"))`) — `tests/test_shortcut_scopes.py`
     and `tests/test_shortcuts_registry_coverage.sh` fail otherwise.
   - The new App: `class TrailApp(TuiSwitcherMixin, ShortcutsMixin, App)`
     with `*TuiSwitcherMixin.SWITCHER_BINDINGS` in `BINDINGS` and
     `self.current_tui_name = "<window_name>"` in `__init__`
     (`lib/tui_switcher.py:1438–1450`), so `j` works from inside it and the
     overlay marks it `is-current`.
   - `lib/tui_switcher.py` `KNOWN_TUIS` is derived from the registry
     (`:155`), so no edit there; `CLAUDE.md:431–435` policy list and the
     website index (child 8) must agree with the registry row.
   - The board-side hand-off: `z` in the board either keeps rendering the
     embedded view or delegates to `_switch_to("<window_name>", running)` —
     the design decides, and `tests/test_board_bytrail_view.py` (4,584
     lines) is the arbiter of what "unchanged" means for the embedded path.
   - Tests that pin this surface and must be extended for the new row:
     `tests/test_shortcut_scopes.py`, `tests/test_shortcuts_registry_coverage.sh`,
     `tests/test_keybinding_registry.sh`, `tests/test_settings_shortcuts_tab.py`,
     `tests/test_tui_switcher_footer_fit.sh` (hint width in small panes),
     `tests/test_session_key_collision.py` (registry-inclusive switcher rows
     keyed on `project_root`), `tests/test_framework_version.py` (busy-window
     set), `tests/test_tui_switcher_agent_launch.py`.
5. **Further board module extraction** (each its own child if large):
   `TaskManager` → `board/task_manager.py`; workflow-phase derivation
   (`:223–617`) → `lib/` or `board/`; `TaskDetailScreen` + its field widgets
   (`:4900–5820`, `:6882–7709`) → `board/detail_screen.py`; column-management
   dialogs (`:7839–8397`) → `board/column_dialogs.py`; pickers. Keep the
   flat-import contract and the fixture-harness invariant per module.
6. **Measure and document**: re-run child 1's script; update
   `aidocs/framework/python_tui_performance.md`, `tui_conventions.md`,
   `CLAUDE.md:143–147` (board file map) and the CHANGELOG; the website work
   is its own child (see "Website documentation" below) and the
   manual-verification follow-up covers the live board ↔ trail hand-off.
7. **Notes to affected tasks** (can run as soon as the design is approved,
   `/aitask-note … --from <this task>`): the trail-subsystem tasks
   `t1647` (+ `t1647_4`, `t1647_5` — **direct collision**: adds a board
   command inside the By-Trail view — `t1647_6`, `t1647_7`), `t1470`,
   `t1543`, `t1526`, `t1372`, `t1439`, `t1514`, `t1645`, `t1569`
   (+ `t1569_7`), `t1718`, `t1231`, `t1135`, `t1634`, `t1709`, `t1793`; and
   the board-architecture tasks `t1243` (+ `t1243_11`, `t1243_12`), `t1632`,
   `t1367`, `t1450`, `t1613`, `t1403`, `t1402`, `t1401`, `t1399`, `t1400`,
   `t1404`, `t1431`, `t1445`, `t1442`, `t1441`, `t1424`, `t1421`, `t1373`,
   `t1348`, `t1338`, `t1334`, `t1363`, `t1330`, `t1329`, `t1290`, `t1296`,
   `t1256`, `t1250`, `t1249`, `t1257`, `t1261`, `t1291`, `t1454`, `t1455`,
   `t1521`, `t1570`, `t1572`, `t1639`, `t1714`, `t1725_5`, `t1386`. Re-derive
   the list at planning time (grep pending `aitasks/` for
   `aitask_board|ait board|By-Trail|trail screen|TrailDetailScreen`), since
   it moves. Active plans that cite board line numbers: `p1647`, `p1569`,
   `p1243`, `p1231`, `p1725`, `p1162`, `p1257`, `p1516`, `p1186`.
8. **Website documentation** — a dedicated child, after child 4 lands (the
   command name, keys and switcher letter must be final before the page is
   written):
   - **New page set for the stand-alone trail TUI**, following the one
     directory per TUI convention: `website/content/docs/tuis/<name>/`
     with `_index.md` (front matter `title`, `linkTitle`, `weight`,
     `description`, `maturity`, `depth`), `how-to.md` and `reference.md` —
     mirror `website/content/docs/tuis/minimonitor/`, which is the precedent
     for a TUI carved out of a bigger one and documents its relationship to
     the parent TUI in the first paragraph. The reference page owns the
     key map (select/detail/summary/drift/watch/launch/move-wave) and the
     launch forms (stand-alone subcommand, from the board, from the
     switcher).
   - **Board pages**: `website/content/docs/tuis/board/reference.md`
     (`:32–39,63,165,224,251–275` — the By-Trail keys and trails section;
     `tests/test_board_reference_doc_literals.py` pins its literals against
     `aitask_board.py`, so the pin must follow the code to the new module or
     be re-pointed) and `how-to.md`; the By-Trail view either stays embedded
     and links to the new page for the full reference, or becomes a
     hand-off — whichever the design settles, the board page must say which.
   - **The TUI index** `website/content/docs/tuis/_index.md`: a new bullet
     in the list at `:17–22` (the Board bullet at `:20` currently describes
     the By-Trail view and must be rewritten), the switcher paragraph at
     `:38` (key letter for the new TUI), and the front-matter `cascade`
     link list at `:7–9`.
   - **Pages that currently assert the board is the only way to a trail**:
     `website/content/docs/skills/aitask-trail.md:87` literally states
     "There is no `ait trail` command: trails are reached through this
     skill and through the board's By-Trail view" — this sentence becomes
     false and must be rewritten (and it is why the subcommand name must
     not be confusable with the `/aitask-trail` skill / codeagent `trail`
     op); also `:12`, `:72`, `:92` (relrefs into
     `/docs/tuis/board/reference#by-trail`),
     `website/content/docs/workflows/implementation-trails.md:51,82`
     ("Press `z` for the By-Trail view…") and
     `website/content/docs/skills/aitask-backlog-roadmap.md:17`.
   - **`CLAUDE.md` TUI list policy** (`:431–435`, "Project-Specific Notes"):
     the documented-TUI list (board, monitor, minimonitor, codebrowser,
     settings, brainstorm) must gain the new TUI, and the `tui_registry` /
     `tui_switcher.KNOWN_TUIS` entries added in child 4 must agree with it.
   - Run `tests/lib/docs_vocabulary_scan.py` and the website build after
     the edits; the blog is **not** updated (blog posts are release-time,
     `create_new_release.sh`).

## Acceptance criteria

- `ait board` behaves exactly as before: every existing key, view (including
  By-Trail), modal and worker works; `tests/run_all_python_tests.sh` and the
  bash test suite are green at every child boundary.
- The trail screen runs as a stand-alone TUI from an `ait` subcommand, opens
  the same trail select/detail/summary/drift/watch/launch flows, and is
  reachable from the board (and can return to it) via the TUI switcher: it
  has a `TUI_REGISTRY` row, a quick-jump key registered under
  `shared.tui_switcher` (visible in the `?` editor and Settings → Shortcuts),
  `j` works from inside it, monitor classifies its window as a TUI, and
  minimonitor is not auto-spawned beside it.
- `aitask_board.py` is materially smaller (target: KanbanApp no longer
  contains any trail code; TaskManager, detail screen and column dialogs live
  in their own modules) and `board/` is a package with the same flat-import
  contract the tests rely on.
- Memory and cold-start are **measured** before and after in the same
  interpreter with the same task tree and reported as signed margins; the
  stand-alone trail TUI's RSS is reported against the full board's.
- No moved module binds `TASKS_DIR`-derived constants at import time
  (asserted by the fixture-harness self-test).
- Every task in the notes list has received a note pointing at the approved
  design and the new file map.
- The website documents the stand-alone trail TUI on its own page set under
  `website/content/docs/tuis/<name>/` (`_index.md`, `how-to.md`,
  `reference.md`), the TUI index and the board pages are updated, and no
  published page still states that the board is the only way to reach a
  trail (`skills/aitask-trail.md:87`).

## Docs to read before planning

`aidocs/framework/tui_conventions.md` (mandatory before editing any Textual
TUI), `aidocs/framework/python_tui_performance.md`,
`aidocs/implementation_trail_design.md` (§9 board rendering half, §9.1–9.3,
§12), `tests/lib/board_fixture.py` docstring `:1–100`, `CLAUDE.md:143–147,
344–362, 431–435`.
