---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [custom_shortcuts, tui_switcher]
created_at: 2026-05-31 14:08
updated_at: 2026-05-31 14:08
---

The TUI switcher *dialog's* shortcuts do not appear in the customizable-shortcuts
list (the in-TUI `?` editor and the Settings → Shortcuts tab) introduced by the
t848 series. Only the single `j` key that *opens* the switcher is customizable.

This task belongs to the **t848 customizable-shortcuts series** — explore creates
standalone tasks, so consider re-parenting it under `t848` (as a `t848_N` child)
when picking it up. Depends conceptually on t848's registry/editor infrastructure.

## Root cause

The customizable-shortcuts system only records a class's `BINDINGS` if that class
*opts in* to `ShortcutsMixin`. The registration sweep in
`.aitask-scripts/lib/shortcut_scopes.py` (`_load_and_register`, ~lines 115-121)
registers a class only when it has a truthy `_shortcuts_scope` **and** a
`BINDINGS` list:

```python
scope = getattr(cls, "_shortcuts_scope", "")
bindings = getattr(cls, "BINDINGS", None)
if scope and bindings:
    keybinding_registry.register_app_bindings(scope, list(bindings))
```

- **Broken:** `TuiSwitcherOverlay` (`.aitask-scripts/lib/tui_switcher.py:287`) is a
  plain `ModalScreen` — no `ShortcutsMixin`, no `_shortcuts_scope`. Its rich
  `BINDINGS` (lines ~333-350: `enter`→switch, `←/→`→session nav, and the
  `a/b/m/c/s/t/y/r/x/g/n` quick-jumps, plus `escape`/`j`→close) are **never**
  recorded in `keybinding_registry._DEFAULTS`. So neither `iter_scope_bindings`
  (in-TUI `?` editor) nor `iter_all_bindings` (Settings tab) can surface them.
- **The only registered switcher binding** is the module-level call at
  `tui_switcher.py:1064-1065`:
  `register_app_bindings("shared", TuiSwitcherMixin.SWITCHER_BINDINGS)` — just the
  `j` open key (action `tui_switcher`), registered under `shared` so every TUI's
  editor lists it. The overlay's *internal* keys were left out. The manifest entry
  confirms intent stopped there:
  `("tui_switcher", "lib/tui_switcher.py", ("shared",))  # module-level register`
  in `shortcut_scopes.py:62`.
- **Working comparison:** `AgentCommandScreen(ShortcutsMixin, ModalScreen)` with
  `_shortcuts_scope = "shared.agent_cmd"` (`agent_command_screen.py:132,136`) opts
  in correctly and *does* show up. This is the pattern to follow.

## Fix shape

1. Make `TuiSwitcherOverlay` opt in, mirroring `AgentCommandScreen`:
   `class TuiSwitcherOverlay(ShortcutsMixin, ModalScreen)` + a class attr
   `_shortcuts_scope = "shared.tui_switcher"`. (Modal/Screen subclasses must NOT
   splice `SHORTCUTS_MIXIN_BINDINGS` — the `?` editor binding is App-level only;
   see `shortcuts_mixin.py` docstring.)
2. Update the `KNOWN_BINDING_SOURCES` entry for `tui_switcher` in
   `shortcut_scopes.py:62` from scope tuple `("shared",)` to
   `("shared", "shared.tui_switcher")` so the filtered sweep
   (`register_scope_bindings`) loads/registers it, and
   `tests/test_shortcut_scopes.py` (which asserts the manifest scopes) passes.
3. Decisions to resolve during implementation:
   - **`j`-toggle coherence:** the overlay binds `j`→`dismiss_overlay` (close) while
     the mixin binds `j`→`tui_switcher` (open). They're intentionally the same key
     (toggle). If a user rebinds the shared *open* key, decide whether the overlay's
     *close* key should follow it or stay hardcoded.
   - **Label sync:** the quick-jump letters are also hardcoded in `_render_hint`
     (`tui_switcher.py:~563`) and `_TUI_SHORTCUTS` (`~164`). If those become
     rebindable, the hint text + dict must render from the resolved keys (e.g. via
     `ShortcutsMixin.label` / `shortcut_labels.render_label`) or they'll go stale.
   - Decide which overlay actions are user-customizable vs. fixed (e.g. `escape`,
     `enter`, `left/right` may stay fixed; the TUI quick-jumps are the main
     candidates).
4. Regenerate any affected goldens/tests; add coverage that
   `shared.tui_switcher` bindings appear via `iter_all_bindings` and the
   scope-filtered `iter_scope_bindings`.

## Acceptance criteria

- The TUI switcher overlay's customizable bindings appear in the Settings →
  Shortcuts tab and in the in-TUI `?` editor under a `shared.tui_switcher` scope.
- `tests/test_shortcut_scopes.py` passes with the updated manifest.
- No regression to the existing `j` open-switcher shared binding or to coherence
  linting.
