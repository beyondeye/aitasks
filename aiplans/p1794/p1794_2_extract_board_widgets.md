---
Task: t1794_2_extract_board_widgets.md
Parent Task: aitasks/t1794_split_board_monofile_and_standalone_trail_tui.md
Sibling Tasks: aitasks/t1794/t1794_1_*.md, aitasks/t1794/t1794_3_*.md … t1794_12_*.md
Archived Sibling Plans: aiplans/archived/p1794/p1794_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-14 15:55
---

# p1794_2 — Extract the board-generic widgets into `board_widgets.py`

Parent plan: `aiplans/p1794_split_board_monofile_and_standalone_trail_tui.md`
(C1, C2, C3, C5 PINNED). Child 1 (archived plan `p1794_1`) landed the package
marker, the own-dir `sys.path` insert, `board_fixture.BOARD_MODULE_NAMES`
(already lists `board_widgets`), the C1/C2 guards and the keymap golden.

## Context

`aitask_board.py` (14,106 lines) is being split into flat-imported
`board/board_*.py` modules. This child moves the board-generic widget layer
that the trail cards (child 3) and the stand-alone `TrailsApp` (child 6)
subclass or call, so trail code never has to import `aitask_board` (C1). It is
the pattern-proving move: zero `patch.object` sites, zero task-dir reads.

## Step 0 — Rebase check (pre-phase `rebase_check_before_each_child`) — DONE at planning

- HEAD `c52534f14`. `git log -- .aitask-scripts/board/ tests/lib/board_fixture.py`
  since the plan's `c78deab36` anchor: only `c52534f14` (t1794_1 itself, which
  added the own-dir insert, shifting anchors by +4). Every range re-read.
- Foreign `Implementing` ∩ board regex: `t1688` (a call-site table row and a
  t1470 mention), `t1555_2` (a count-table row) — incidental, same as child 1.
  No foreign task on this region → no stop.
- **C3 sweep result: empty.** No `patch.object(...)` (any target expression),
  string-form `patch("…aitask_board.X")`, `setattr`, or class-attribute
  mutation names any moved symbol in `tests/`. No repointing, no mutants owed.

## Move set (current anchors at `c52534f14`)

Verbatim, keeping their relative order:

| name | lines |
|---|---|
| `_issue_indicator`, `_pr_indicator` | `:710–732` |
| `CollapseToggleButton`, `ColumnEditButton` | `:2963–2990` **(added — see below)** |
| `ColumnHeader` | `:3185–3206` |
| multi-select comment block + `MarkedSelection` | `:3326–3403` |
| `TaskCard` | `:3406–3612` |
| `_followup_marker`, `_plan_approved_marker`, `_status_badge_text`, `_followup_colour_hex`, `_followup_glyph_text` | `:3782–3918` |
| `PickerItem` | `:4209–4234` |
| `LoadingOverlay` | `:8008–8018` |

**Stay in the board:** `InFlightTaskCard :3615`, `_GhostTaskStub :3765` (child 3),
`ViewSelector :3208`, `_UNIT_SELECTOR :3182`, every `PickerItem` / `TaskCard`
subclass, all CSS (the rules styling these widgets stay in `KanbanApp.CSS`).

**Deviation from the task's list — `CollapseToggleButton` / `ColumnEditButton`
move too.** `ColumnHeader.compose` yields both; they are used nowhere else
(grep), depend only on `Static` and two `self.app` methods, and leaving them
behind would force `board_widgets` to import back from `aitask_board` (C1
forbids it). The parent file map's "ColumnHeader" entry implies them.

## Implementation steps

1. **Create `.aitask-scripts/board/board_widgets.py`.**
   - Module docstring: what lives here and why (t1794_2, C1/C2); flat import
     only; **no `sys.path` insert** — the importer (`aitask_board.py`, the
     fixture, the tests) has already put `lib/` on the path; no task-dir
     resolution of any kind (C2); no `aitask_board` import (C1).
   - `from __future__ import annotations` (keeps `task: Task` /
     `manager: "TaskManager"` annotations as strings — `Task`/`TaskManager`
     are not importable here), then exactly the imports the moved code needs:
     `datetime.date`, `functools.lru_cache`, `typing.Protocol`,
     `rich.text.Text`, `textual.app.ComposeResult`,
     `textual.color.Color as TextualColor, ColorParseError`,
     `textual.containers.Container, Horizontal`, `textual.screen.ModalScreen`,
     `textual.widgets.Label, LoadingIndicator, Static`,
     `followup_kinds.marker_for`, `mark_glyphs.mark_markup`,
     `topic_semantics.parse_task_filename`.
   - Two documentation-only `typing.Protocol`s (not `runtime_checkable`):
     - `CardHost` — the `self.app` surface `TaskCard` reads:
       `marked` (only behind `self.markable`, `:3441`), `expanded_tasks`,
       `check_action`, `action_toggle_children`, `action_view_details`
       (`:3606–3612`). Docstring: trail cards are non-markable by construction
       and override `on_click`, so a trails host needs only
       `check_action` + `action_view_details` + `expanded_tasks` in practice;
       `KanbanApp` is the reference host.
     - `ColumnHeaderHost` — `toggle_column_collapse`, `open_column_edit`
       (the two buttons' `self.app` calls).
   - The moved code, verbatim. The only text edit: the multi-select comment
     block's "this module re-exports MARK_CHECKED/MARK_UNCHECKED" becomes
     "`aitask_board.py` re-exports …".

2. **`aitask_board.py`: import pair, delete definitions, drop dead imports.**
   - Directly after the `from followup_kinds import (…)` block, add a comment
     (mirroring the `trail_discovery` one at `:57–62`: names are re-exports;
     helpers inside `board_widgets` call each other through that module, so a
     stub must target `board_widgets`) plus
     `import board_widgets` and
     `from board_widgets import (CollapseToggleButton, ColumnEditButton,
     ColumnHeader, LoadingOverlay, MarkedSelection, PickerItem, TaskCard,
     _followup_colour_hex, _followup_glyph_text, _followup_marker,
     _issue_indicator, _plan_approved_marker, _pr_indicator,
     _status_badge_text)`. This precedes every import-time use
     (`InFlightTaskCard(TaskCard)`, the ten `PickerItem` subclasses).
   - Delete the eight moved regions.
   - Update the `followup_kinds` import comment ("`_followup_marker` below is
     the render boundary") to name `board_widgets._followup_marker`.
   - Remove imports whose only users moved (verified by reading the remaining
     code: 0 other references): `date` (→ `from datetime import datetime`),
     `from functools import lru_cache`, `from textual.color import …`,
     `LoadingIndicator`, `ComposeResult`, and `parse_task_filename` from the
     `topic_semantics` list. The only test reading one of them off the board
     (`test_board_detail_followup_kind.py:789`, `self.ab.TextualColor`) is
     repointed in step 3. Keep `MARK_CHECKED`/`MARK_UNCHECKED` (declared
     re-exports) and `mark_markup` (`_repaint_card_mark` still uses it).
   - Confirm after the edit with a one-off AST probe: every name imported into
     `aitask_board.py` is either loaded somewhere in it or is a declared
     re-export (the `board_widgets`, `trail_discovery`, `mark_glyphs` lists).

3. **Tests that follow the moved code (C5).**
   - `tests/test_mark_glyphs_single_source.py`: add `"board/board_widgets.py"`
     to `CONSUMERS` (it imports and uses `mark_markup` → Rule 3 holds with no
     `RE_EXPORTS` entry; it carries no `✓`/`□` literal → no `ALLOWED_LITERALS`
     entry). New negative control
     `test_negative_a_stray_tick_in_board_widgets_is_flagged`: append a
     function returning `"✓"` to the temp copy of `board/board_widgets.py` and
     assert a `board/board_widgets.py:rule2:✓:…` finding — proving
     `aitask_board.py`'s per-file `✓` waiver does not leak to the new consumer
     (the task's "stray ✓" proof, kept permanent instead of one-off).
   - `tests/test_board_reference_doc_literals.py`: the two
     `_status_badge_text` pins read `self.ab.board_widgets._status_badge_text`
     (the owner); the docstring's "a rename in `aitask_board.py`" names both
     board modules.
   - `tests/test_board_plan_approved_marker.py`
     `test_the_badge_glyph_has_exactly_one_home`: scan every
     `.aitask-scripts/board/*.py`, not just `aitask_board.py` — otherwise the
     guard goes **vacuous** (zero 📋 literals left in the board, and a second
     literal could reappear there or in any sibling). Assert exactly one hit
     overall, located in `board_widgets.py`, and that the scanned set contains
     `board_widgets.py` (anti-vacuity); the message lists `file:line`. Update
     the `date`-import docstring (`:299–301`) to name `board_widgets.py`.
   - `tests/test_board_detail_followup_kind.py:789`:
     `self.ab.TextualColor` → `self.ab.board_widgets.TextualColor` (the
     resolver module `_followup_colour_hex` actually uses).
   - `tests/test_board_fixture_harness.py` `FreshLoadC2Tests`: docstring no
     longer "vacuous until child 2"; the real-tree test now asserts
     `board_widgets` is in `report["modules"]` and `fresh` (the C2 runtime
     check exercises a real sibling from here on). Add `test_board_widgets.py`
     to `MIGRATED_MODULES`.

4. **New guard — `tests/test_board_package_contract.py`
   `_unresolved_globals(source, filename)`.** A verbatim move fails silently
   when the moved code references a name the new module does not import: the
   import succeeds and the `NameError` fires only when that path renders
   (a collapsed `ColumnHeader`, a GitLab issue badge, a `date`-typed marker).
   Stdlib `symtable`: every symbol that is referenced as an implicit global in
   any nested scope (or referenced-but-unbound at module scope) must be a
   module-level binding, a builtin, or a module dunder (incl. CPython 3.14's
   `__conditional_annotations__`). Applied to **every** `board/*.py`, so it
   also catches a dead-import removal in step 2 that was not dead, and every
   later child's module gets it for free. Probed at planning (CPython 3.14.7):
   today's tree is clean (`aitask_board.py` 0 findings); annotation-only names
   under `from __future__ import annotations` are not flagged (without the
   future import they are, under `__annotate__` — a correct finding, since
   such a name raises on introspection); class-body and function-body
   references are flagged; locals/closures/comprehensions are not. Negative
   controls (synthetic sources) pin each of those four rows.
   - Same file, `HeadlessImportTests` (next to the existing subprocess
     `OwnDirInsertTests`): subprocess (`sys.executable`, clean `PYTHONPATH` =
     `board` + `lib`, `cwd=REPO_ROOT`, `TASK_DIR` unset) runs
     `import board_widgets` and reports whether `aitask_board` got loaded and
     which names exist → not loaded, every moved name present. Negative
     control: the same probe for `aitask_board` reports it loaded (the probe
     can see the thing it asserts absent).

5. **New `tests/test_board_widgets.py`** (fixture tests via
   `bf.FixtureBoardTestBase`; reaches `board_widgets` only as
   `self.ab.board_widgets`, so tier-2 strict — no canonical import, no chdir;
   added to `MIGRATED_MODULES` with a one-line comment):
   - `ReexportIdentityTests`: for each moved name,
     `getattr(ab, n) is getattr(ab.board_widgets, n)` and
     `ab.TaskCard.__module__ == "board_widgets"` — a leftover or re-added
     definition in `aitask_board.py` breaks identity. Pure helper
     `_non_identical(board, widgets, names)`; negative control on a namespace
     holding a copy.
   - `HostProtocolTests`: `_missing_members(protocol, obj)` (annotations +
     public callables of the Protocol body); a fixture `ab.KanbanApp()`
     instance has every `CardHost` member, `ab.KanbanApp` every
     `ColumnHeaderHost` member; negative control: a `SimpleNamespace` lacking
     `expanded_tasks` is reported.

6. **Docs pointer.** `aidocs/framework/aitasks_extension_points.md:286`
   (`_plan_approved_marker` in `board/aitask_board.py`) → `board/board_widgets.py`.
   No website change: rendered literals are unchanged and still pinned.

## Verification

- `bash tests/run_all_python_tests.sh` → last line `PYTHON SUITE: PASSED`
  (`${PIPESTATUS[0]}` if piped; the 4 pre-existing
  `test_parallel_admission_collect` date-rot failures, owned by t1799, are
  reported as such if still present).
- `~/.aitask/venv/bin/python -m pytest tests/test_board_followup_glyph.py
  tests/test_board_plan_approved_marker.py tests/test_textual_markup_structure.py
  tests/test_textual_markup_colours.py tests/test_board_inflight_view.py
  tests/test_board_workflow_phase.py tests/test_mark_glyphs_single_source.py
  tests/test_board_reference_doc_literals.py tests/test_board_package_contract.py
  tests/test_board_fixture_harness.py tests/test_board_keymap_characterization.py
  tests/test_board_widgets.py tests/test_board_detail_followup_kind.py
  tests/test_board_bytrail_view.py tests/test_board_marking.py
  tests/test_board_dom_transplant.py -q` green; keymap golden **unchanged**.
- Red runs (in-process, no repo edits — the child-1 harness pattern): each new
  checker neutered (`lambda *a, **k: []` / always-identical / never-missing)
  turns its negative control red; the one-home test pointed back at
  `aitask_board.py` only reports 0 hits (proves the vacuity it fixes).
- C4 bash guards: `tests/test_no_lib_to_tui_import.sh`,
  `tests/test_no_raw_tmux.sh`, `tests/test_shortcuts_registry_coverage.sh`,
  `tests/test_keybinding_registry.sh`, `tests/test_serial_carveout_doc_drift.sh`;
  `pytest tests/test_shortcut_scopes.py tests/test_task_dir_module_constants.py`.
- `grep -n '^class TaskCard\|^class PickerItem\|^class LoadingOverlay\|^class ColumnHeader\|^class MarkedSelection' .aitask-scripts/board/aitask_board.py`
  empty; `grep -n _shortcuts_scope .aitask-scripts/board/board_widgets.py`
  empty (no `lib/shortcut_scopes.py` row needed).
- Manual smoke on a private tmux socket (`-L`, `kill-session` only): `ait
  board` boots, cards render with badges/markers, `z` renders trail cards,
  `q` quits.

## Notes for sibling tasks (to carry into Final Implementation Notes)

- CSS for the moved widgets (`.task-title-row`, `.task-info`, `.task-title`,
  `.task-number`, `.task-mark`, `.col-header-*`, `PickerItem*`,
  `#loading_dialog`/`#loading_message`) still lives in `KanbanApp.CSS`. Trail
  cards use `.task-title`/`.task-info` and the trail flow pushes
  `LoadingOverlay`, so a second App (child 6) needs those rules too — child 3's
  `TRAIL_CSS` list (and/or a `LoadingOverlay.DEFAULT_CSS`, per
  `tui_conventions.md` "Modals pushed by multiple Apps") should cover them.
- Moved classes are now ONE class object across every `load_board_module()`
  (previously each load minted its own `TaskCard`); harmless today (no test
  mutates them), but a class-attribute patch on `ab.TaskCard` is now visible to
  every board module in the worker until restored.

## Post-implementation

Task-workflow Step 8 (review; path-scoped code commit
`refactor: Extract the board-generic widgets into board_widgets.py (t1794_2)`;
plan commit), Step 9 (gates run — `risk_evaluated`; archive `t1794_2`).

## Risk

### Code-health risk: low
- A moved body references a name `board_widgets.py` does not import; the import succeeds and the `NameError` fires only on a rarely-rendered path (collapsed column header, GitLab badge, `date`-typed marker) · severity: low (residual — addressed by the plan's own step 4 `_unresolved_globals` guard over every `board/*.py`, plus the Pilot suites that render these widgets) · → mitigation: none
- Dead-import removal in `aitask_board.py` drops a name something still uses · severity: low · → mitigation: none (step 4's guard covers `aitask_board.py` too; the removal list was derived by reading the remaining code)
- Path-scoped source guards silently lose coverage when their target literal leaves `aitask_board.py` (the 📋 one-home test would pass with zero hits) · severity: low (residual — addressed by step 3's rescoping to every `board/*.py` with an anti-vacuity assertion; every other source-text reader of `aitask_board.py` was checked and inspects code that stays) · → mitigation: none
- Class identity changes from per-fixture-load to shared for the moved classes · severity: low · → mitigation: none (grep: no test mutates or class-patches them; recorded for siblings)

### Goal-achievement risk: low
- `CardHost` is hand-enumerated from reading `TaskCard`; a missed member would surface only when child 6 hosts cards in a second App · severity: low · → mitigation: none (members listed from the exact `self.app` reads at `:3441, :3606–3612`; conformance asserted on `KanbanApp`; child 5's host-protocol test runs against both Apps)
- The move set grows by two classes beyond the task's list · severity: low · → mitigation: none (forced by C1; documented above)

Every identified risk is low and already addressed by this plan's own
numbered steps (the unresolved-globals guard, the one-home rescoping, the
identity/host tests), so no separate mitigation is proposed
(`risk_mitigations_planned = false`; no `### Planned mitigations` block).

## Final Implementation Notes

- **Actual work done:**
  - `.aitask-scripts/board/board_widgets.py` (635 lines): the 14 moved names
    (`_issue_indicator`, `_pr_indicator`, `CollapseToggleButton`,
    `ColumnEditButton`, `ColumnHeader`, `MarkedSelection`, `TaskCard`,
    `_followup_marker`, `_plan_approved_marker`, `_status_badge_text`,
    `_followup_colour_hex`, `_followup_glyph_text`, `PickerItem`,
    `LoadingOverlay`) plus the documentation-only `CardHost` /
    `ColumnHeaderHost` Protocols. Verbatim was checked mechanically, not by
    eye: every top-level block of every removed region appears byte-for-byte
    in the new module (14/14). The only prose edit is the multi-select comment
    ("`aitask_board.py` re-exports …").
  - `aitask_board.py` 14,106 → 13,573 lines: `import board_widgets` + a flat
    re-import of all 14 names right after the `followup_kinds` import (with a
    re-export comment mirroring the `trail_discovery` one); the seven regions
    deleted by an asserting script (first line, trailing blank and following
    neighbour of each checked before cutting); dead imports removed — `date`,
    `lru_cache`, `TextualColor`/`ColorParseError`, `LoadingIndicator`,
    `ComposeResult`, `parse_task_filename`.
  - Tests: `test_mark_glyphs_single_source` (consumer + per-file `✓` waiver
    control), `test_board_reference_doc_literals` (pins read
    `ab.board_widgets._status_badge_text`), `test_board_plan_approved_marker`
    (📋 one-home scan over every `board/*.py`, anti-vacuity + location),
    `test_board_detail_followup_kind` (`ab.board_widgets.TextualColor`),
    `test_board_fixture_harness` (`MIGRATED_MODULES` + the C2 real-tree test
    now asserts `board_widgets` was exercised fresh), `test_board_package_contract`
    (`_unresolved_globals` over every `board/*.py`, `HeadlessImportTests`),
    new `test_board_widgets.py` (re-export identity, host protocols).
  - `aidocs/framework/aitasks_extension_points.md:286` points at `board_widgets.py`.
- **Red → green evidence:** seven in-process proofs, each control green against
  the real checker and red with it neutered: `_unresolved_globals` (flagged
  forms), the headless probe (can observe `aitask_board` loaded), `_non_identical`,
  `_missing_members`, `_protocol_members` (anti-vacuity), the per-file `✓`
  waiver (leaking a waiver to `board_widgets.py` turns the control red), and the
  C2 real-tree anti-vacuity (dropping `board_widgets` from the report turns it
  red). The pre-change 📋 scope (`aitask_board.py` only) now finds 0 literals —
  the vacuity the rescoping fixes; all of `board/*.py` finds exactly 1.
- **Deviations from plan:** none beyond the two recorded in the plan itself
  (the two column-header buttons move with `ColumnHeader`; the headless-import
  test lives in `test_board_package_contract.py`). C3 sweep: empty, so no patch
  was repointed and no mutant was owed.
- **Issues encountered:**
  - Writing the new module resolved three `\uXXXX` escapes into literal glyphs
    (`▶`/`▼`, `✎`, `⚡`) — same runtime bytes, not verbatim. The block check
    caught it before the board was edited; the three lines were restored from
    the original.
  - Manual smoke: the first run's By-Trail "pass" was a false positive (the
    pattern matched the always-visible `z · By-Trail` filter label), and its
    `q` "not quitting" was a script race (keys sent while the selector was
    still closing). Re-run with every key sent only after the screen reached
    the expected state, against this change AND a detached `HEAD` worktree
    (removed afterwards): identical — boot → `q` quits; `z` → "Select trail —
    ↑/↓ move · Enter open · Esc cancel" with real trails → `Esc` → `q` quits.
    Cards render with status/effort/label badges and marks; no traceback.
  - Full suite: `PYTHON SUITE: FAILED` — 7498 passed, 2 skipped, 4 failed;
    serial lane 11 passed. The four are the pre-existing
    `tests/test_parallel_admission_collect.py` date-rot failures recorded in
    p1794_1 (owned by t1799; `origin/main`'s t1763 commit edits that file). No
    path of this change is on that module's import path. Targeted set: 588
    passed; C4 bash guards all pass; keymap golden unchanged.
  - The shared worktree holds another session's uncommitted edits
    (`aitask_codeagent.sh`, `monitor/monitor_core.py`, codex config, review-loop
    tests, …); the code commit names only this task's paths.
- **Key decisions:**
  - The two buttons are re-exported although the board no longer uses them, so
    every moved name resolves on `ab` uniformly and the identity test covers the
    whole list.
  - `CardHost` is documentation, not `runtime_checkable`; conformance is
    asserted on a `KanbanApp()` instance because `marked` / `expanded_tasks` are
    set in `__init__`.
  - The unresolved-globals guard covers every `board/*.py`, including
    `aitask_board.py`: it catches both a lost import in moved code and an
    over-eager dead-import removal, and every later child's module gets it free.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - **Tests may not canonically import a board module in `tests/test_board_*.py`.**
    `LiveTreeSweepTests` (tier 1) flags `import board_widgets` exactly like
    `import aitask_board`. Reach a sibling as `self.ab.<module>` under the
    fixture, or put a headless check in a subprocess (see
    `HeadlessImportTests` in `test_board_package_contract.py`) — child 3's
    planned headless `TrailModelTests` sibling must follow one of these.
  - A stub of any moved helper must target `ab.board_widgets` (`TaskCard.compose`
    calls `_status_badge_text` etc. through its own module). No test does today.
  - CSS for the moved widgets (`.task-title-row`, `.task-info`, `.task-title`,
    `.task-number`, `.task-mark`, `.col-header-*`, `PickerItem*`,
    `#loading_dialog` / `#loading_message`) still lives in `KanbanApp.CSS`.
    Trail cards use `.task-title` / `.task-info` and the trail flow pushes
    `LoadingOverlay`, so the second App (child 6) needs those rules —
    child 3's `TRAIL_CSS` and/or a `LoadingOverlay.DEFAULT_CSS`.
  - The moved classes are now ONE class object across every
    `load_board_module()` (each load used to mint its own `TaskCard`). No test
    mutates them; a class-attribute patch on `ab.TaskCard` is visible to every
    board module in the worker until restored.
  - Verify a verbatim move mechanically: assert each region's first line and
    following neighbour before cutting, and check every top-level block of the
    region is a substring of the new module. An editor/tool can normalize
    `\uXXXX` escapes silently.
  - Smoke tests in tmux: wait for a screen state specific to the next step
    before each key (the By-Trail selector reads "Select trail — ↑/↓ move ·
    Enter open · Esc cancel"); compare against a detached `HEAD` worktree
    (`aitask_init_data.sh --link-worktree`) before calling anything a regression.
  - `CardHost` members for the trails host (children 5/6): `marked`,
    `expanded_tasks`, `check_action`, `action_toggle_children`,
    `action_view_details`; the column buttons need `toggle_column_collapse` /
    `open_column_edit` only if the host mounts `ColumnHeader`.
