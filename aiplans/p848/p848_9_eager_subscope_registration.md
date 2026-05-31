---
Task: t848_9_eager_subscope_registration.md
Parent Task: aitasks/t848_customizable_shortcuts.md
Sibling Tasks: aitasks/t848/t848_10_case_aware_mnemonic_label_rendering.md, aitasks/t848/t848_6_documentation_for_customizable_shortcuts.md, aitasks/t848/t848_7_manual_verification_customizable_shortcuts.md, aitasks/t848/t848_8_cascade_reset_to_default.md
Archived Sibling Plans: aiplans/archived/p848/p848_1_shortcut_registry_and_overrides.md, aiplans/archived/p848/p848_2_label_renderer_and_board_pilot.md, aiplans/archived/p848/p848_3_sweep_remaining_tuis.md, aiplans/archived/p848/p848_4_in_tui_shortcut_editor_modal.md, aiplans/archived/p848/p848_5_settings_tui_shortcuts_tab.md
Base branch: main
plan_verified: []
---

# p848_9 — Eager sub-scope registration + `?`-as-shared

## Context

In the in-TUI `?` shortcut editor (t848_4), the rows come from
`keybinding_registry.iter_scope_bindings(scope)`, which only sees scopes
that were **registered this session**. Modal/sub-screen scopes
(`board.detail`, `board.agent_cmd`, `codebrowser.copypath`, `applink.pairing`,
…) register lazily in `ShortcutsMixin.__init__`, only when that screen is first
constructed. So opening `?` in `ait board` *before* opening any task lists only
`board` (+ whatever shared scopes exist) — `board.detail` / `board.agent_cmd`
are missing until the user has opened a task detail once. The editor should
list **every sub-scope of the active TUI** up front.

Second, **required** deliverable (confirmed in the task): make the `?` editor
binding (`open_shortcuts_editor`) a **`shared`-scope** shortcut, exactly like
the `j` TUI switcher. Today `?` is recorded under each App's own scope, so it
appears once per TUI rather than once globally. Registering it under `shared`
makes the editor list it once (under `shared`) and a rebind apply in every TUI.

**Design pivot (supersedes the task's original approach #2).** The task file
predates t848_5, which introduced the canonical global scope manifest
`.aitask-scripts/lib/shortcut_scopes.py` (`KNOWN_BINDING_SOURCES` +
`register_all_known_bindings()`). t848_5's Final Notes explicitly direct t848_9
to **reuse this manifest** with a *filtered* call rather than build a parallel
per-App `_shortcut_subscopes` mechanism. This plan follows that guidance.

## Approach

1. **Eager sub-scope registration** — add a *filtered* sweep
   `register_scope_bindings(scope)` to `shortcut_scopes.py` that loads only the
   manifest modules contributing `scope`, `scope.*`, and the global
   `shared`/`shared.*` scopes (so pressing `?` in one TUI does **not** import
   every other TUI). Call it from `ShortcutsMixin.action_open_shortcuts_editor`
   (once per App instance) before pushing the editor modal. `iter_scope_bindings`
   then returns the active TUI's own scope + every sub-scope + shared, with no
   instantiation of heavyweight screens.

2. **`?` as a shared binding** — register `SHORTCUTS_MIXIN_BINDINGS` under the
   `"shared"` scope at module import in `shortcuts_mixin.py` (mirroring
   `tui_switcher.py:1064-1065`). The shared-action de-dup already in
   `register_app_bindings` (t848_4) then resolves each App's `?` from `shared`
   and records no per-App copy — the editor lists `?` once under `shared`, and a
   shared rebind applies in every TUI. The key still works in every TUI because
   the binding remains spliced into each App's `BINDINGS`.

## Files to modify

### 1. `.aitask-scripts/lib/shortcut_scopes.py` — enriched manifest + filtered sweep
- **Enrich `KNOWN_BINDING_SOURCES`** entries from `(module_name, rel_path)` to
  `(module_name, rel_path, scopes_tuple)` — turning the existing trailing
  comments into data. The scope→module map was verified against source
  (`grep _shortcuts_scope` + the two `register*bindings("…")` literals); it
  matches the current comments exactly, e.g.:
  - `("aitask_board", "board/aitask_board.py", ("board", "board.detail"))`
  - `("agent_command_screen", "lib/agent_command_screen.py", ("board.agent_cmd",))`
  - `("applink_app", "applink/applink_app.py", ("applink", "applink.pairing", "applink.status"))`
  - `("brainstorm_dag_display", "…/brainstorm_dag_display.py", ("brainstorm.dag",))`
  - `("tui_switcher", "lib/tui_switcher.py", ("shared",))`
  - `("stale_entry_modal", "lib/stale_entry_modal.py", ("shared.stale_entry",))` … etc.
  Update the type annotation to `list[tuple[str, str, tuple[str, ...]]]`.
- **Update the two unpack sites** (the only consumers — verified):
  `_ensure_import_paths()` (`for _module_name, rel_path, _scopes in …`) and the
  `register_all_known_bindings()` loop.
- **Refactor** the per-module load+introspect body of
  `register_all_known_bindings()` into a private
  `_load_and_register(module_name, rel_path, failed)` helper, so both entry
  points share one implementation.
- **Add `register_scope_bindings(scope: str) -> list[str]`**: `_ensure_import_paths()`,
  then for each manifest entry whose `scopes` contains any `s` matching
  `s == scope or s.startswith(scope + ".") or s == "shared" or s.startswith("shared.")`,
  call `_load_and_register`. Idempotent + fail-soft (same try/except as the full
  sweep); returns the list of modules that failed to import. Docstring states
  it is the in-TUI `?` editor's filtered counterpart to the Settings-tab
  `register_all_known_bindings()`.

### 2. `.aitask-scripts/lib/shortcuts_mixin.py` — `?`-as-shared + eager call
- **Module-level `register_shared_bindings()`** (after the class definition):
  ```python
  def register_shared_bindings() -> None:
      """Register the App-level `?` editor binding under the global `shared` scope.

      Mirrors tui_switcher.py's module-level shared registration of `j`. Idempotent;
      runs once at import. Tests that call keybinding_registry._reset_for_tests()
      must call this again to restore it.
      """
      register_app_bindings("shared", ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS)


  register_shared_bindings()
  ```
  This runs when `shortcuts_mixin` is first imported — which every App module
  does at import time, before any App is instantiated — so `("shared",
  "open_shortcuts_editor")` is already in `_DEFAULTS` when each App's
  `ShortcutsMixin.__init__` calls `register_app_bindings(scope, BINDINGS)`, and
  the t848_4 shared-action de-dup kicks in correctly.
- **In `action_open_shortcuts_editor`**, before `push_screen`, eagerly register
  the active TUI's sub-scopes once per instance:
  ```python
  def action_open_shortcuts_editor(self) -> None:
      from shortcut_editor_modal import ShortcutEditorModal
      if not getattr(self, "_subscopes_registered", False):
          try:
              import shortcut_scopes
              shortcut_scopes.register_scope_bindings(self._shortcuts_scope)
          except Exception:
              pass  # fail-soft: editor still lists already-registered scopes
          self._subscopes_registered = True
      self.app.push_screen(ShortcutEditorModal(scope=self._shortcuts_scope))
  ```

### 3. `.aitask-scripts/lib/keybinding_registry.py` — SHARED_ACTION_IDS correctness
- Replace the dead `"shortcuts_editor"` entry with the real action id
  `"open_shortcuts_editor"` in `SHARED_ACTION_IDS` (line 27-29). The current
  string never matches any binding; the actual action (`shortcuts_mixin.py:32`)
  is `open_shortcuts_editor`. Small correctness fix so `coherence_lint` treats
  `?` as the shared action it now is. (Flagged in Final Notes.)

### 4. Tests
- **`tests/test_shortcut_scopes.py`** — add `ScopeFilteredSweepTests`:
  - `register_scope_bindings("board")` registers `board`, `board.detail`,
    `board.agent_cmd`, `shared`, `shared.stale_entry` with **no App
    instantiated**, and does **not** register unrelated scopes (`brainstorm`,
    `codebrowser`, `monitor`). Proves both eager sub-scope coverage and the
    filtering. Add one analogous case for a second TUI (e.g. `codebrowser` →
    `codebrowser`, `codebrowser.copypath`, shared).
- **`tests/test_shortcut_editor_modal.py`** — add to `IterScopeBindingsTests`,
  mirroring the existing `j`-switcher shared tests:
  - `test_shortcuts_editor_action_not_duplicated_under_app_scope`: register `?`
    under shared (via `shortcuts_mixin.register_shared_bindings()`), then
    register an app scope splicing `SHORTCUTS_MIXIN_BINDINGS`; assert
    `("<app>", "open_shortcuts_editor")` is absent, `("shared",
    "open_shortcuts_editor")` present, and `iter_scope_bindings("<app>")` lists
    it exactly once under `shared`.
  - `test_shortcuts_editor_shared_override_applies`: `save_override("shared",
    "open_shortcuts_editor", "f1")` → refresh → register app `?` → applied
    binding key is `f1`.
  - Existing `PilotTests` are unchanged: their `_reset_for_tests()` wipes the
    import-time shared registration, so `?` stays under `testscope` (still 3
    rows). Confirm they still pass.
- **`tests/test_shortcuts_registry_coverage.sh`** — after the `_reset_for_tests()`
  call, add `import shortcuts_mixin; shortcuts_mixin.register_shared_bindings()`
  (re-trigger the shared `?` post-reset, mirroring the existing tui_switcher
  re-import for the `j` shared case), and assert `open_shortcuts_editor` is
  registered under `shared` and NOT under any per-App scope.

### 5. `aidocs/tui_conventions.md` — extend the existing rule
Append to the "Shortcut-scope registration" section (added by t848_5) one
sentence: the in-TUI `?` editor eagerly registers the active TUI's sub-scopes
via `shortcut_scopes.register_scope_bindings(scope)` (a filtered manifest call),
and the `?` editor binding itself is a `shared`-scope shortcut registered in
`shortcuts_mixin.register_shared_bindings()`.

## Reuse (do not reinvent)
- `shortcut_scopes`: `_ensure_import_paths`, the `spec_from_file_location` +
  `exec_module` + class-introspection recipe (factored into `_load_and_register`).
- `keybinding_registry`: `register_app_bindings` (shared-action de-dup already
  present), `iter_scope_bindings`, `_reset_for_tests`.
- `tui_switcher.py:1064-1065` — the module-level `register_app_bindings("shared",
  …)` pattern that `register_shared_bindings()` mirrors.

## Known consideration
`register_scope_bindings("board")` re-`exec_module`s `aitask_board.py` even
though the running board process already has it loaded — this is the same proven
mechanism `register_all_known_bindings()` uses (fresh throwaway module object,
no `sys.modules` mutation, no App instantiation, fail-soft). The per-instance
`_subscopes_registered` guard makes it a one-time cost on the first `?` press.
A future refinement could introspect the already-loaded active module and
spec-load only cross-module sub-scope sources; deferred to keep this change
aligned with t848_5's "filtered call against the same manifest" design.

## Verification
```bash
python3 tests/test_shortcut_scopes.py
python3 tests/test_shortcut_editor_modal.py
bash tests/test_shortcuts_registry_coverage.sh
bash tests/test_keybinding_registry.sh
python3 -c "import ast; [ast.parse(open(f).read()) for f in ['.aitask-scripts/lib/shortcut_scopes.py','.aitask-scripts/lib/shortcuts_mixin.py','.aitask-scripts/lib/keybinding_registry.py']]; print('PARSE_OK')"
# Manual (defer aggregate checks to the t848_7 manual-verification sibling):
#   ait board    → ?  (before opening any task) → board.detail + shared.agent_cmd rows present
#   ait codebrowser → ? → shared.agent_cmd row present (reused dialog, now shared)
#   ait monitor  → ?  → open_shortcuts_editor listed once under `shared` (like `j`), NOT under monitor
```

## Post-Review Changes

### Change Request 1 (2026-05-31 — rescope agent_cmd from board to shared)
- **Requested by user:** Reviewing the change, the user noticed `agent_cmd` was
  treated as a board dialog (`board.agent_cmd`), which is wrong — the
  `AgentCommandScreen` dialog is reused across several TUIs (board, codebrowser,
  monitor, syncer), not just board. With the filtered eager sweep, pressing `?`
  in codebrowser/monitor/syncer would never surface its bindings.
- **Changes made:** Rescoped the reused dialog from `board.agent_cmd` to
  `shared.agent_cmd` (a shared sub-scope, like `shared.stale_entry`), so it
  appears in **every** TUI's `?` editor.
  - `lib/agent_command_screen.py`: `_shortcuts_scope = "shared.agent_cmd"` (+ a
    comment explaining the cross-TUI reuse). CSS ids `#agent_cmd_*` are
    unrelated widget ids — left unchanged.
  - `lib/shortcut_scopes.py`: moved the `agent_command_screen` manifest entry
    into the shared-dialogs group with scopes `("shared.agent_cmd",)`.
  - `tests/test_shortcut_scopes.py`: the board sweep test now asserts
    `shared.agent_cmd` as a shared sub-scope (not under board); the codebrowser
    sweep test asserts `shared.agent_cmd` is present too (proving the cross-TUI
    surface).
  - `lib/shortcuts_mixin.py` comment + `aidocs/tui_conventions.md` example
    updated to drop `board.agent_cmd` and cite `shared.agent_cmd`.
- **Files affected:** `.aitask-scripts/lib/agent_command_screen.py`,
  `.aitask-scripts/lib/shortcut_scopes.py`,
  `.aitask-scripts/lib/shortcuts_mixin.py`, `tests/test_shortcut_scopes.py`,
  `aidocs/tui_conventions.md`.
- **Note:** This mis-scope originated in t848_3 (it assigned `board.agent_cmd`
  assuming a board-only command flow). The custom-shortcuts feature is not yet
  released, so no user overrides exist under the old scope key — no migration
  needed.

## Step 9 — Post-implementation
Standard child-task archival (`./.aitask-scripts/aitask_archive.sh 848_9`).
t848_9 depends on t848_4 (done); it is not a dependency of the remaining
pending siblings (t848_6/_7/_8/_10).

## Final Implementation Notes

- **Actual work done:**
  - `lib/shortcut_scopes.py` — enriched `KNOWN_BINDING_SOURCES` entries to
    `(module_name, rel_path, scopes_tuple)` (the trailing comments became data);
    factored the per-module load+introspect body into `_load_and_register`;
    added `register_scope_bindings(scope)` (filtered counterpart to
    `register_all_known_bindings`) that loads only the manifest modules whose
    scopes match `scope`/`scope.*`/`shared`/`shared.*`, plus a `_scope_relevant`
    helper mirroring `iter_scope_bindings`'s filter.
  - `lib/shortcuts_mixin.py` — added module-level `register_shared_bindings()`
    (registers `?`/`open_shortcuts_editor` under `shared` at import, mirroring
    `tui_switcher.py`'s `j`); `action_open_shortcuts_editor` now calls
    `shortcut_scopes.register_scope_bindings(self._shortcuts_scope)` once per
    instance (guard flag `_subscopes_registered`, fail-soft) before pushing the
    editor, so the active TUI's modal sub-scopes + shared dialogs are listed up
    front.
  - `lib/keybinding_registry.py` — fixed the dead `SHARED_ACTION_IDS` entry
    (`shortcuts_editor` → the real action id `open_shortcuts_editor`).
  - `lib/agent_command_screen.py` — **rescoped** the reused dialog from
    `board.agent_cmd` to `shared.agent_cmd` (Post-Review CR1).
  - Tests: `tests/test_shortcut_scopes.py` (+`ScopeFilteredSweepTests`: board &
    codebrowser filtered sweeps, asserting eager sub-scopes + cross-TUI
    `shared.agent_cmd` with no App instantiated); `tests/test_shortcut_editor_modal.py`
    (+2 shared-`?` tests; made the 2 Pilot tests robust to the new shared rows);
    `tests/test_shortcuts_registry_coverage.sh` (re-trigger shared `?` post-reset
    + assert `open_shortcuts_editor` lives only under `shared`).
  - `aidocs/tui_conventions.md` — documented the filtered `?`-editor sweep and
    the `?`-as-shared registration; updated the manifest entry format.
  - **Verification:** all green — `test_shortcut_scopes.py` 4/4,
    `test_shortcut_editor_modal.py` 17/17, `test_settings_shortcuts_tab.py`
    15/15, `test_shortcuts_registry_coverage.sh` PASS,
    `test_keybinding_registry.sh` 9/9, `test_userconfig_writer_collision.sh`
    13/13, AST parse + shellcheck clean.

- **Deviations from plan:**
  - **Approach #2 (per-App `_shortcut_subscopes`) was NOT used** — per t848_5's
    Final Notes, the eager registration reuses the global manifest via a
    *filtered* `register_scope_bindings(scope)` instead.
  - Eager-registration assertions live in `tests/test_shortcut_scopes.py` (the
    manifest test), not the App-construction-based
    `test_shortcuts_registry_coverage.sh` the original task step 4 named —
    because the mechanism is now manifest-driven, not per-App construction.
  - **Post-Review CR1:** rescoped `agent_cmd` to `shared.agent_cmd` (see
    Post-Review Changes) after the user flagged it as a cross-TUI dialog.

- **Issues encountered:** Pressing `?` eagerly loads the `shared` modules (the
  filter always includes `shared`/`shared.*`), so the editor table gains shared
  rows (`j` switcher, stale-entry, agent-cmd). The two pre-existing Pilot tests
  hardcoded "no shared scope" and a fixed row index — updated to assert on the
  testscope rows and to locate the target row dynamically. This is correct
  runtime behavior, not a regression.

- **Key decisions:**
  - `register_scope_bindings` always includes shared sources so reused dialogs
    (`shared.agent_cmd`, `shared.stale_entry`) and the `j` switcher surface in
    every TUI's editor.
  - `register_shared_bindings()` runs at `shortcuts_mixin` import (before any
    App `__init__`), so the t848_4 shared-action de-dup fires for `?` exactly as
    it does for `j`.
  - The eager call re-`exec_module`s the running TUI's own module (fresh module
    object, no instantiation) — the same proven mechanism as the Settings sweep;
    a per-instance guard makes it a one-time cost.

- **Upstream defects identified:** None. (The `board.agent_cmd` mis-scope was
  within the t848 custom-shortcuts feature surface — introduced by t848_3 — and
  is fixed inline here, not an unrelated pre-existing defect.)

- **Notes for sibling tasks:**
  - **Reused/cross-TUI modal dialogs must use a `shared.<name>` scope**, not a
    host-TUI scope. `shared.agent_cmd` and `shared.stale_entry` are the
    precedents; the filtered `?` sweep + the Settings tab surface `shared.*` in
    every TUI.
  - `?` (`open_shortcuts_editor`) is now a `shared` binding (like `j`): a rebind
    under `shared` applies in every TUI; the editor lists it once under `shared`.
  - To eagerly register a single TUI's scopes, call
    `shortcut_scopes.register_scope_bindings(scope)`; for the whole cross-TUI
    set (Settings tab), `register_all_known_bindings()`. Both share
    `_load_and_register` and the enriched `KNOWN_BINDING_SOURCES` manifest.
