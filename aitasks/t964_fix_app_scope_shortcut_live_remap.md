---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [custom_shortcuts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-10 13:02
updated_at: 2026-06-10 17:02
---

## Origin

Spawned from t896 during Step 8b review.

## Upstream defect

`.aitask-scripts/lib/shortcuts_mixin.py:89 — App-scope key overrides never reach
Textual's live keymap: ShortcutsMixin sets self.BINDINGS *after*
super().__init__(), but Textual builds the live keymap from class-level
_merged_bindings during __init__, so overrides update the editor row / registry
/ footer hint / tab title but pressing the new key does not fire (even after
restart, despite shortcut_editor_modal.py:335's "restart to apply" message).
Confirmed pre-existing and uniform across ALL App-scope bindings (reproduced on
the existing export_configs `e` binding), not introduced by t896.`

## Diagnostic context

While migrating the Settings tab-switch keys onto the registry (t896), an
end-to-end test that overrode a tab key and pressed the new key failed: the
override reached `app.BINDINGS` (via `register_app_bindings`) and the
registry/footer hint/tab title, but the live keymap kept the class-default key.
Empirically confirmed the same on the pre-existing `export_configs` (`e`)
binding — so this is a framework-wide App-scope limitation, not specific to the
tab keys. Widget/Screen/Modal scopes are unaffected because they call
`register_app_bindings` at class-body load time (before the Textual metaclass
computes `_merged_bindings`); only Apps (via `ShortcutsMixin.__init__`, which
runs after `super().__init__()`) are affected.

## Impact

Per-TUI key rebinds in the Shortcuts editor are advertised as taking effect on
restart, but for App-level bindings (e.g. settings e/i/r/q/d/l/w/v/x and the new
tab-switch keys, board App keys, etc.) the live key never changes — the editor,
registry, footer hints, and tab titles all show the new key while the old key
keeps working. Confusing and undermines the customization feature for App scope.

## Suggested fix

Rebuild the App's live bindings from the overrides-applied list after
registration — e.g. in `ShortcutsMixin.__init__` (or an `on_mount`) reconstruct
`self._bindings` from `self.BINDINGS` so the substituted keys become live, or
move App-scope registration to a point before Textual computes the merged
bindings. Verify with an end-to-end pilot test that presses an overridden
App-scope key and asserts the action fires.
