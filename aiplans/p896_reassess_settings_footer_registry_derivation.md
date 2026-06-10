---
Task: t896_reassess_settings_footer_registry_derivation.md
Base branch: main
plan_verified: []
---

# Plan: t896 — Migrate Settings tab-switch keys onto the keybinding registry

## Context

During t848_7 manual verification, item #6 — *"Settings tab-switcher footer
correctly lists current tab keys (registry-derived, not hardcoded)"* — was found
**not satisfied**. t896 reassessed the t848_3 deferral and the decision is to
**migrate** (not accept-as-is).

Verified current state in `.aitask-scripts/settings/settings_app.py`:

- `_TAB_SHORTCUTS` (line 160) is a raw `dict` of **7 keys** (`a/b/c/m/p/s/t` →
  tab ids), driven by a raw `on_key` handler (line 1477) — **not** Textual
  `Binding`s, **not** in the keybinding registry, **not** user-customizable.
- **9** hand-composed footer hint strings all read `a/b/c/m/p/t: switch tabs` —
  **every one is missing the `s` (Shortcuts) key**: the hardcoded hints have
  already drifted from reality.
- Every *other* settings key (`q/e/i/r/d/l/w/v/x/?/j`) already flows through the
  registry. The tab keys are the lone raw-`on_key` exception.
- The p848_3 deferral rationale claimed "the registry already records" the
  per-tab bindings — inaccurate; no tab bindings exist in the registry.

**Outcome:** register 7 tab-switch actions under the `settings` scope (making
them rebindable in the existing Shortcuts editor) and render all footer hints
from the registry so they can never drift and auto-include every tab key.

## Approach

Convert the raw `on_key` dict dispatch into 7 registered `Binding`s + action
methods, and replace the 9 hardcoded hint literals with a registry-derived
helper. Reuse the existing `ShortcutsMixin` / `keybinding_registry` machinery
(both already imported in `settings_app.py`) — no new infrastructure.

### File: `.aitask-scripts/settings/settings_app.py`

**1. Replace `_TAB_SHORTCUTS` (key→tab) with an action-keyed map (action→tab).**
This becomes the single source of truth shared by the bindings, the action
methods, and the footer-hint helper:

```python
# Tab-switch action_id -> TabPane id. The KEY for each action comes from the
# keybinding registry (default in BINDINGS below), so users can rebind tab
# switching in the Shortcuts editor and the footer hint follows automatically.
_TAB_SWITCH_ACTIONS = {
    "switch_tab_agent":     "tab_agent",
    "switch_tab_board":     "tab_board",
    "switch_tab_project":   "tab_project",
    "switch_tab_models":    "tab_models",
    "switch_tab_profiles":  "tab_profiles",
    "switch_tab_shortcuts": "tab_shortcuts",
    "switch_tab_tmux":      "tab_tmux",
}
```

**2. Add 7 `Binding`s to `SettingsApp.BINDINGS`** (after the existing
profile/shortcut-tab bindings, ~line 1286). Default keys preserve today's
mnemonics; `show=False` keeps them out of the auto-footer (hints are rendered
manually in `section-hint` labels, consistent with `d/l/w/v/x`):

```python
Binding("a", "switch_tab_agent",     "Agent tab",     show=False),
Binding("b", "switch_tab_board",     "Board tab",     show=False),
Binding("c", "switch_tab_project",   "Project tab",   show=False),
Binding("m", "switch_tab_models",    "Models tab",    show=False),
Binding("p", "switch_tab_profiles",  "Profiles tab",  show=False),
Binding("s", "switch_tab_shortcuts", "Shortcuts tab", show=False),
Binding("t", "switch_tab_tmux",      "Tmux tab",      show=False),
```

These register under the `settings` scope automatically via
`ShortcutsMixin.__init__` → `register_app_bindings(...)`, so they appear as
editable rows in the existing Shortcuts tab. No key collides with the current
settings bindings (`q/e/i/r/d/l/w/v/x/?/j`).

**3. Extract the tab-switch focus logic into a private helper** (the exact
focus dance currently inside `on_key`, lines 1478–1489, which prevents Textual
from reverting the switch when the new tab has no focusable content):

```python
def _switch_to_tab(self, tab_id: str) -> None:
    try:
        tabbed = self.query_one(TabbedContent)
        tabbed.active = tab_id
        tabbed.query_one("Tabs").focus()
        self.call_after_refresh(self._focus_first_in_tab, tab_id)
    except Exception:
        pass
```

**4. Add 7 thin action methods** (Textual resolves `Binding(..., "switch_tab_agent")`
to `action_switch_tab_agent`). Distinct action_ids are required so each tab key
is independently rebindable:

```python
def action_switch_tab_agent(self):     self._switch_to_tab("tab_agent")
def action_switch_tab_board(self):     self._switch_to_tab("tab_board")
def action_switch_tab_project(self):   self._switch_to_tab("tab_project")
def action_switch_tab_models(self):    self._switch_to_tab("tab_models")
def action_switch_tab_profiles(self):  self._switch_to_tab("tab_profiles")
def action_switch_tab_shortcuts(self): self._switch_to_tab("tab_shortcuts")
def action_switch_tab_tmux(self):      self._switch_to_tab("tab_tmux")
```

**5. Remove the `_TAB_SHORTCUTS` block from `on_key`** (lines 1476–1492). The
binding system now drives tab switching. Everything else in `on_key` (modal
guard, profiles `Tab` cycling, shortcuts-search nav, the `Input`-focus guard,
up/down nav) stays.

**6. Gate the tab-switch actions in `check_action`** to preserve the former
modal guard (the old `on_key` returned early when `isinstance(self.screen,
ModalScreen)`). With bindings, App-level bindings can still fire while a modal
is up, so add:

```python
def check_action(self, action, parameters):
    # Tab-switch keys are inert while a modal owns the screen — typing in a
    # dialog must not switch the background tab (parity with the old on_key
    # modal guard). Input widgets already consume letter keys when focused,
    # so the in-field case needs no extra guard.
    if action in _TAB_SWITCH_ACTIONS and isinstance(self.screen, ModalScreen):
        return None
    # ... existing sc_* / profile_* gating unchanged ...
```

**7. Add a registry-derived footer-hint helper** (replaces the literal key
list; derives from resolved keys so it auto-includes `s` and never drifts):

```python
def _tab_switch_hint(self) -> str:
    """Footer hint listing the live tab-switch keys (registry-resolved)."""
    keys = [
        keybinding_registry.resolve_key(self._shortcuts_scope, aid)
        for aid in _TAB_SWITCH_ACTIONS
    ]
    return "/".join(k for k in keys if k) + ": switch tabs"
```

Display order follows `_TAB_SWITCH_ACTIONS` insertion order → `a/b/c/m/p/s/t`
by default (now correctly including `s`).

**8. Replace the 9 hardcoded `a/b/c/m/p/t: switch tabs` literals** with the
helper. Each site is a `[dim]…[/dim]` `Label` string inside a `SettingsApp`
method; f-prefix the relevant segment and splice `{self._tab_switch_hint()}`.
Adjacent string-literal concatenation lets the f-segment mix with non-f
segments. Sites (line numbers approximate): 1978, 2108, 2208, 2367, 2452, 2539,
2582, 2610, 2697. Example:

```python
# before
"[dim]↑↓: navigate  |  a/b/c/m/p/t: switch tabs[/dim]",
# after
f"[dim]↑↓: navigate  |  {self._tab_switch_hint()}[/dim]",
```

(The line 2697 string also hardcodes `w/v/x: save/revert/delete`; that is a
separate registry-customizable concern, **out of scope** here — left as-is and
noted as a related defect.)

### File: `tests/test_settings_shortcuts_tab.py`

Existing tests already exercise the keys via `pilot.press("s")`, `pilot.press("a")`
and still pass (default keys unchanged). Add focused coverage for the migration:

- **Tab actions are registry-registered:** after instantiating `SettingsApp`,
  assert every `switch_tab_*` action is present in
  `keybinding_registry._DEFAULTS` under the `settings` scope with its default
  key (mirrors the `sc_reset/sc_lint` assertion style at lines 129–132).
- **Footer hint is registry-derived and includes `s`:** assert
  `app._tab_switch_hint()` == `"a/b/c/m/p/s/t: switch tabs"` by default, and
  that after `shortcut_persist.save_override("settings", "switch_tab_agent", "g")`
  + `keybinding_registry.refresh_all()` the hint reflects the new key (`g/...`)
  — proving derivation, not hardcoding.
- **Modal guard:** assert `check_action("switch_tab_agent", None)` is `None`
  when a `ModalScreen` is active and `True` otherwise (re-use an existing modal
  like `ResetShortcutsConfirmScreen`, as in the gating test at lines 205–216).
- **Rebound key switches the tab:** override `switch_tab_tmux` to a free key,
  refresh, re-instantiate, press the new key, assert `TabbedContent.active ==
  "tab_tmux"` (end-to-end customization path).

## Risk

### Code-health risk: low
- Self-contained single-file refactor plus its test; reuses existing
  `ShortcutsMixin` / `keybinding_registry` machinery (no new infrastructure).
  Main behavioral subtlety — modal-guard parity and `Input`-focus behavior — is
  explicitly handled (`check_action` gate; Inputs consume letter keys natively)
  and covered by tests. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Approach directly satisfies item #6's two clauses (registry-derived +
  correctly-lists-current-keys) and the decision the user selected. The only
  residual is the 7 new editable rows in the Shortcuts tab, which is the
  intended, accepted trade-off. · severity: low · → mitigation: TBD

## Verification

1. `bash tests/test_settings_shortcuts_tab.py` — all existing + new cases pass.
2. `bash tests/test_shortcuts_registry_coverage.sh` — `settings` scope coverage
   still passes (now includes the 7 `switch_tab_*` actions).
3. Manual smoke (`ait settings`): press `a/b/c/m/p/s/t` from various tabs →
   switches correctly; every tab footer now shows `a/b/c/m/p/s/t: switch tabs`
   (note `s` present); open the Shortcuts tab (`s`) and confirm the 7
   `switch_tab_*` rows are listed and editable; rebind one, reopen, confirm the
   footer hint reflects the new key.
4. Per Step 9, run the project's `verify_build` if configured.

## Step 9 (Post-Implementation)

Standard cleanup, archival (`aitask_archive.sh 896`), and merge approval per the
shared task-workflow Step 9.
