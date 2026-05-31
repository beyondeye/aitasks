---
Task: t876_register_tui_switcher_overlay_shortcuts.md
Worktree: (none — profile 'fast', working on current branch)
Branch: main
Base branch: main
---

# t876 — Register TUI-switcher overlay shortcuts in the customizable-shortcuts system

## Context

The t848 series made TUI shortcuts customizable: bindings registered under a
*scope* surface in the in-TUI `?` editor and the Settings → Shortcuts tab, and
pick up per-user overrides from `userconfig.yaml`. The **TUI switcher overlay**
(`TuiSwitcherOverlay`, `.aitask-scripts/lib/tui_switcher.py:287`) was never wired
in: it's a plain `ModalScreen` whose rich `BINDINGS` (Enter→switch, ←/→ session
nav, the `a/b/m/c/s/t/y/r/x/g/n` quick-jumps, and `escape`/`j`→close) are *never*
recorded in `keybinding_registry._DEFAULTS`. Only the module-level `j` key that
*opens* the switcher is registered (under `shared`, `tui_switcher.py:1064-1065`).
So none of the overlay's internal keys appear in the editor/Settings tab.

**Goal:** make the overlay's **quick-jump letters** customizable (visible +
editable under a new `shared.tui_switcher` scope), keep the structural keys
(escape/enter/←/→) fixed, and make the `j` close-key mirror the shared open key.
(Decisions confirmed with the user.)

## Approach — class-body `register_app_bindings`, not `ShortcutsMixin`

The task sketch suggested adding `ShortcutsMixin`, mirroring `AgentCommandScreen`.
Investigation of Textual 8.2.7 shows that's the wrong tool here, for two reasons:

1. **The mixin is all-or-nothing.** Both the Settings sweep
   (`shortcut_scopes._load_and_register`) and the mixin's `__init__` register the
   *entire* class `BINDINGS` under the scope. That makes escape/enter/←/→
   customizable too — contrary to the user's "quick-jumps only" choice. Moving
   the structural keys out of class `BINDINGS` is not an option (see #2).
2. **`self.BINDINGS` reassignment in `__init__` does NOT affect live keys.**
   Verified empirically: Textual builds `self._bindings` (the live dispatch map)
   from the **class-level** merged map in `DOMNode.__init__`, *before* the mixin
   reassigns `self.BINDINGS`. An override (or any append) done in `__init__`
   never reaches `key_to_bindings`. The pattern that *does* wire overrides into
   live dispatch is a **class-body** call — exactly what
   `brainstorm_dag_display.py:450` does:
   `BINDINGS = register_app_bindings("brainstorm.dag", [...])`.

So the right pattern (precedent: `brainstorm.dag`) is: pass **only the
quick-jumps** through `register_app_bindings("shared.tui_switcher", ...)` at class
body, and keep the structural keys as plain literal `Binding`s in the same list.
Result: all keys stay functional; only the quick-jumps land in `_DEFAULTS` (so
only they appear in the editor); overrides are baked into live dispatch at launch;
no `escape`/`j` registry collapse (they're unregistered literals).

## Changes

### 1. `.aitask-scripts/lib/tui_switcher.py`

**Top imports (~line 36-39):** add
`from keybinding_registry import register_app_bindings, resolve_key` and
`from shortcut_labels import render_label, display_form`. (No import cycle:
`keybinding_registry`/`shortcut_labels` don't import `tui_switcher`. The module
already imports `keybinding_registry` at the bottom.)

**Bottom (line 1064-1065):** drop the `as _register_shared_bindings` alias import;
call `register_app_bindings("shared", TuiSwitcherMixin.SWITCHER_BINDINGS)` using
the new top import. Behavior identical (the `j`-open shared binding is preserved).

**New module-level constants (just above the class, ~line 173):**
```python
_TUI_SWITCHER_SCOPE = "shared.tui_switcher"
_QUICK_JUMP_BINDINGS = [
    Binding("a", "shortcut_applink", "App Linker", show=False),
    Binding("b", "shortcut_board", "Board", show=False),
    Binding("m", "shortcut_monitor", "Monitor", show=False),
    Binding("c", "shortcut_codebrowser", "Code Browser", show=False),
    Binding("s", "shortcut_settings", "Settings", show=False),
    Binding("t", "shortcut_stats", "Statistics", show=False),
    Binding("y", "shortcut_syncer", "Syncer", show=False),
    Binding("r", "shortcut_brainstorm", "Brainstorm", show=False),
    Binding("x", "shortcut_explore", "Explore", show=False),
    Binding("g", "shortcut_git", "Git", show=False),
    Binding("n", "shortcut_create", "New Task", show=False),
]
# Resolve the shared "open switcher" key at import; the overlay closes on the
# same key (toggle). Skipped if it collides with a fixed/quick-jump key
# (escape always closes).
_OVERLAY_OPEN_KEY = resolve_key("shared", "tui_switcher", "j") or "j"
_OVERLAY_RESERVED = {"escape", "enter", "left", "right",
                     "a", "b", "c", "g", "m", "n", "r", "s", "t", "x", "y"}
```

**`TuiSwitcherOverlay.BINDINGS` (replace lines 333-350):**
```python
BINDINGS = [
    Binding("escape", "dismiss_overlay", "Close", show=False),
    Binding("enter", "select_tui", "Switch", show=False),
    Binding("left", "prev_session", "Prev session", show=False, priority=True),
    Binding("right", "next_session", "Next session", show=False, priority=True),
    *([Binding(_OVERLAY_OPEN_KEY, "dismiss_overlay", "Close", show=False)]
      if _OVERLAY_OPEN_KEY not in _OVERLAY_RESERVED else []),
    *register_app_bindings(_TUI_SWITCHER_SCOPE, _QUICK_JUMP_BINDINGS),
]
```
The class stays a plain `ModalScreen` (no mixin, no `_shortcuts_scope` — so the
sweep's class introspection skips it; the class-body `register_app_bindings`
fires during the sweep's `exec_module` and populates `_DEFAULTS`).

**Label sync — render hint/list from resolved keys** (decision: quick-jumps are
rebindable, so hardcoded letters would go stale):
- `_TUI_SHORTCUTS` (line 164) — keep as the default-key dict; add a helper
  `_resolve_tui_shortcut(name)` → `resolve_key(_TUI_SWITCHER_SCOPE,
  f"shortcut_{name}", _TUI_SHORTCUTS[name])`. Update `_TuiListItem.compose`
  (line 270) to call it instead of the raw dict lookup.
- `_render_hint` (line 563) — rebuild the quick-jump segments from resolved keys
  via `render_label(text, key, style="wrap")`, wrapping the `(K)` group in the
  existing `[bold bright_cyan]…[/]` markup with a small regex helper; render the
  close-key label from `_OVERLAY_OPEN_KEY`. (Cosmetic: the highlighted letter
  becomes uppercase, e.g. `(b)oard` → `(B)oard`, matching the `render_label`
  convention used by Settings buttons like `(L)int`.)

### 2. `.aitask-scripts/lib/shortcut_scopes.py`

Update the manifest entry (line 62) so it accurately lists both scopes the module
contributes:
```python
("tui_switcher", "lib/tui_switcher.py", ("shared", "shared.tui_switcher")),
```

### 3. Tests

- **`tests/test_shortcut_scopes.py`** — add a test that, after
  `register_all_known_bindings()`, the `shared.tui_switcher` quick-jump actions
  (e.g. `shortcut_board`, `shortcut_create`) appear in `iter_all_bindings()`, and
  that `register_scope_bindings("board")` + `iter_scope_bindings("board")`
  surfaces `shared.tui_switcher` (it's a `shared.*` scope, always included).
  (The existing `test_sweep_registers_every_source_scope` already passes once the
  source declares the scope — the regex picks up the `register_app_bindings(
  "shared.tui_switcher", …)` literal.)
- **`tests/test_settings_shortcuts_tab.py`** — add `"shared.tui_switcher"` to the
  asserted scope set in `test_tab_populated_with_cross_tui_scopes` (end-to-end:
  the scope shows in the Settings tab).

No goldens reference the switcher scopes; no `.md.j2`/skill changes, so
`aitask_skill_verify.sh`/golden regeneration are N/A.

## Decisions resolved (per user)

- **Customizable scope:** quick-jump letters only; escape/enter/←/→ stay fixed
  (unregistered literals).
- **`j` toggle:** mirrors the shared open key (`_OVERLAY_OPEN_KEY`), recomputed at
  launch; escape always closes; skipped on key collision.
- **Label sync:** hint + per-item shortcut render from resolved keys so they
  track rebinds.

## Verification

```bash
# Targeted unit tests
python3 tests/test_shortcut_scopes.py
python3 tests/test_settings_shortcuts_tab.py
# Switcher overlay regression (CSS/footer + action methods)
bash tests/test_tui_switcher_footer_fit.sh
bash tests/test_tui_switcher_multi_session.sh
bash tests/test_tui_switcher_brainstorm_session.sh
# Registry/editor coverage
python3 tests/test_keybinding_registry.sh 2>/dev/null || bash tests/test_keybinding_registry.sh
python3 tests/test_shortcut_editor_modal.py
# Lint
shellcheck .aitask-scripts/aitask_*.sh   # (no shell touched, sanity only)
```
Manual smoke (optional, requires tmux): launch any TUI, press `?`, confirm a
`shared.tui_switcher` group lists the quick-jumps; open Settings → Shortcuts (`s`)
and confirm the scope appears; rebind e.g. `shortcut_board` and confirm the
switcher hint/list reflect the new key on next launch.

Skim `aidocs/tui_conventions.md` "Shortcut-scope registration" during
implementation to align comment wording (class-body register precedent:
`brainstorm.dag`).

## Post-implementation

Follow shared workflow **Step 8** (user review) → **Step 9** (this task has no
branch/worktree: skip merge; run `./.aitask-scripts/aitask_archive.sh 876`, then
`./ait git push`). Per CLAUDE.md, suggest a follow-up aitask to port the same
registration to the Codex CLI / OpenCode switcher equivalents only if those
trees carry a parallel switcher (they don't — this is Python TUI code, shared).

## Final Implementation Notes

- **Actual work done:** Implemented as planned. `TuiSwitcherOverlay`'s 11
  quick-jumps now register under `shared.tui_switcher` via a class-body
  `register_app_bindings(...)` call; structural keys (escape/enter/←/→) stay
  fixed literals; the `j` close-toggle mirrors the resolved shared open key
  (`_OVERLAY_OPEN_KEY`), skipped on collision. `_render_hint` and
  `_TuiListItem.compose` render quick-jump labels from resolved keys via
  `render_label`/`display_form` (added `_hint_segment` + `_HINT_ITEMS`). Manifest
  entry in `shortcut_scopes.py` updated to `("shared", "shared.tui_switcher")`.
  Added `TuiSwitcherScopeTests` and extended the Settings-tab scope assertion.
- **Deviations from plan:** None in substance. `_OVERLAY_RESERVED_KEYS` is derived
  from `_QUICK_JUMP_BINDINGS` keys (+ escape/enter/left/right) rather than a
  hardcoded literal set.
- **Issues encountered:** A concurrent session was editing the shortcuts system
  in the same working tree (`shortcut_labels.py`, `shortcuts_mixin.py`,
  `settings_app.py`, `aitask_setup.sh`, `test_shortcut_labels.sh`,
  `.claude/settings.local.json` showed edits not made by this task). Committed
  only the four t876 files via explicit `git add` paths. t876's code uses only
  stable pre-existing APIs (`render_label`, `display_form`, `resolve_key`,
  `register_app_bindings`), so it is independent of those edits.
  `test_tui_switcher_multi_session.sh` could not run (its safety guard refuses to
  run inside a tmux session); its paths are covered by the footer-fit and
  brainstorm-session switcher tests.
- **Key decisions:** (per user) quick-jumps only customizable; structural keys
  fixed; `j`-toggle mirrors the open key; hint/list render from resolved keys.
  Chose class-body `register_app_bindings` (precedent: `brainstorm.dag`) because
  it is the only pattern that both wires overrides into Textual's live key map AND
  registers a *subset* of a screen's bindings.
- **Upstream defects identified:** `.aitask-scripts/lib/shortcuts_mixin.py:41 — the
  mixin's `self.BINDINGS = register_app_bindings(...)` reassignment runs in
  __init__ after super().__init__(), but Textual 8.2.7 builds the live key map
  (self._bindings) from the class-level merged map during DOMNode.__init__, so the
  reassignment never reaches live dispatch.` Verified empirically on a minimal
  App/ModalScreen + ShortcutsMixin with literal BINDINGS: a saved override appears
  in the editor/registry but does NOT rebind the live key (only class-body
  register_app_bindings — as brainstorm.dag and now tui_switcher use — does). This
  would affect every mixin-only scope (e.g. `board`, `board.detail`,
  `shared.agent_cmd`). NOTE: `shortcuts_mixin.py` had concurrent uncommitted edits
  (+69 lines) during this task that may already address this — confirm before
  filing a follow-up.
