---
priority: medium
effort: medium
depends: [t848_4]
issue_type: enhancement
status: Done
labels: [custom_shortcuts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-05-30 23:17
updated_at: 2026-05-31 14:01
completed_at: 2026-05-31 14:01
---

## Context

Follow-up to **t848_4** (the in-TUI `?` shortcut editor). The editor enumerates
bindings from `keybinding_registry._DEFAULTS` via `iter_scope_bindings(scope)`,
which only contains scopes that have been **registered this session**. Modal /
sub-screen scopes (e.g. `board.detail` — the Pick/Brainstorm/etc. buttons,
`codebrowser.copypath`, `applink.pairing`, `brainstorm.compare_select`) register
their bindings lazily, in `ShortcutsMixin.__init__`, when that screen is first
constructed (the t848_2 / t848_3 design).

Consequence: open `?` in `ait board` before opening any task and the editor lists
only `board` and `shared` — the `board.detail` shortcuts are missing until the
user has opened a task detail once. The editor should list *every* sub-scope of
the active TUI up front.

This task also has a **second, required goal** (confirmed by the user): make the
`?` editor binding (`open_shortcuts_editor`) a **`shared`-scope** shortcut, exactly
like the `j` TUI switcher. Today `?` is recorded under each App's own scope, so it
appears once per TUI (not duplicated, but not shared either). Since `?` is the same
binding spliced into every App via `ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS`, it
must be registered under `shared` so the editor lists it once under `shared` and a
rebind applies in every TUI.

## Key Files to Modify

- `.aitask-scripts/lib/keybinding_registry.py` — where defaults are recorded.
- `.aitask-scripts/lib/shortcuts_mixin.py` — sub-screens declare their scope here.
- `.aitask-scripts/lib/shortcut_editor_modal.py` — consumes `iter_scope_bindings`.
- Each App that owns sub-scope screens (board, codebrowser, applink, brainstorm,
  syncer/shared.stale_entry, …).

## Approaches to weigh (pick during planning)

1. **Static scope manifest** — a declared map `app_scope -> [sub-scope screen
   classes]`; the editor (or App startup) imports + registers each class's
   BINDINGS once. Explicit, testable, but must be kept in sync as screens change.
2. **Eager registration at App startup** — each App, in its own `__init__`,
   registers the BINDINGS of its known sub-screen classes (without instantiating
   the screens), e.g. via a class attribute `_shortcut_subscopes = [TaskDetailScreen, ...]`
   that `ShortcutsMixin` walks. Keeps the declaration next to the App.
3. **Registry self-population** — a one-time scan that imports each TUI module
   and reads sub-screen `BINDINGS`/`_shortcuts_scope` class attrs.

Prefer the approach that avoids instantiating heavyweight screens (registration
should read `cls.BINDINGS` + `cls._shortcuts_scope` only).

## Implementation Plan

1. Choose the registration mechanism (favor option 2: a `_shortcut_subscopes`
   class attr listing sub-screen classes, walked by `ShortcutsMixin.__init__`
   to `register_app_bindings(cls._shortcuts_scope, cls.BINDINGS)` for each).
2. Annotate each App with its sub-scope screen classes.
3. Confirm idempotency (`register_app_bindings` already tolerates re-registration
   when the screen is later actually constructed).
4. Extend `tests/test_shortcuts_registry_coverage.sh` to assert every expected
   sub-scope (`board.detail`, `board.agent_cmd`, `codebrowser.copypath`,
   `applink.pairing`, `applink.status`, `brainstorm.dag`,
   `brainstorm.compare_select`, `shared.stale_entry`) is present after merely
   constructing each App (no modal opened).
5. **(Required) Register `?` under `shared`.** Register
   `ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS` under the `"shared"` scope at module
   import in `lib/shortcuts_mixin.py` (mirror the `tui_switcher.py:1065`
   `register_app_bindings("shared", SWITCHER_BINDINGS)` pattern). The shared-action
   resolution added in t848_4 (`register_app_bindings` skips a per-App copy when
   `("shared", action)` already exists) then automatically de-duplicates `?` so it
   shows once under `shared` and a rebind applies everywhere.
   - **Watch the import-order + `_reset_for_tests()` interaction:** the import-time
     shared registration runs once per process. Tests that call
     `keybinding_registry._reset_for_tests()` wipe it and must re-trigger it (the
     coverage test already re-imports `tui_switcher` for the `j` case — do the same
     for `shortcuts_mixin`, or expose an idempotent
     `register_shared_bindings()` helper the test can call).
   - Confirm `?` still actually opens the editor in every TUI after the change
     (the binding key is unchanged unless overridden under `shared`).

## Verification Steps

```bash
bash tests/test_shortcuts_registry_coverage.sh   # now asserts sub-scopes eagerly
python3 tests/test_shortcut_editor_modal.py
# Manual: ait board → ? (before opening any task) → board.detail rows present.
# Manual: ait monitor → ? → `?`/open_shortcuts_editor listed once under `shared`
#         (like `j`); NOT under the monitor scope.
```

## Notes

- Depends on **t848_4** (editor + iter_scope_bindings). Not a dependency of
  t848_5/t848_6/t848_7.
- The `?`-as-shared work is a **required** deliverable of this task (see
  Implementation Plan step 5 + the second goal in Context), not optional. t848_4
  already made `tui_switcher` resolve from `shared` and left `open_shortcuts_editor`
  per-App; this task finishes that consistency.
