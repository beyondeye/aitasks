---
Task: t900_redesign_settings_execution_profile_screen.md
Worktree: (none — profile 'fast', working on current branch)
Branch: (current branch)
Base branch: main
---

# t900 — Redesign the Settings "Execution Profiles" tab

## Context

The Settings TUI (`ait settings`) Profiles tab currently renders everything —
the profile selector, all ~30 parameters, and the Save/Revert/Delete buttons —
into one `VerticalScroll(#profiles_content)`. As soon as you scroll the
parameters, the selector and buttons scroll off-screen, the buttons always
carry the profile name in their labels, and there is no way to filter the long
parameter list. Save/Revert are always clickable even when nothing changed.

This task restructures the tab into four fixed/scrolling panes, adds a
name-filter search box, single-key shortcuts for the action buttons, Tab-key
pane navigation, and dirty-state gating for Save/Revert — and renames the tab
to "Execution Profiles" throughout. The user explicitly asked for these and
for single, lowercase, framework-consistent shortcut keys (no Ctrl/Alt) and a
search that matches the parameter **name only**.

All changes are confined to **`.aitask-scripts/settings/settings_app.py`**. The
shared renderer `.aitask-scripts/lib/profile_editor.py` is **not** modified
(its `ProfileEditScreen` modal must keep working unchanged); the settings tab
parses the flat widget stream `compose_profile_fields()` already yields to
build its own group/field index.

## Current code map (already read)

- `compose()` line ~1306 — `TabPane("Profiles", id="tab_profiles")` →
  `yield VerticalScroll(id="profiles_content")`. Positional title list at
  line ~1295 also contains `"Profiles"`.
- `_populate_profiles_tab()` lines ~2471–2594 — builds the whole tab into
  `#profiles_content`: intro, selector `CycleField`, "Editing:" line, fields via
  `compose_profile_fields(...)`, then the three buttons
  (`btn_profile_save__/revert__/delete__{safe_fn}`).
- `on_cycle_field_changed()` line ~2605 — currently handles only
  `profile_selector` (returns early for all other CycleFields).
- `on_button_pressed()` line ~2624 — maps `btn_profile_save__/revert__/delete__`
  to the save-confirm modal / `_revert_profile` / delete-confirm modal.
- `on_key()` lines ~1390–1583 — tab switch (a/b/c/m/p/s/t), up/down via
  `_nav_vertical`, Enter→string/int editor, `?`→field detail. Guard returns
  early when an `Input` is focused.
- CSS block lines ~1161–1245; `BINDINGS` + `check_action` (gated `d`/`l`)
  lines ~1249–1276. The Shortcuts tab (`_populate_shortcuts_tab`, ~2864) is the
  reference pattern for non-scrolling shell + inner-scroll + pinned buttons +
  `render_label_cfg("…","d")` button labels.
- Helpers to reuse: `collect_profile_values(query_one, base, id_prefix=…)` and
  `compose_profile_fields(...)` from `profile_editor.py`; `_safe_id`;
  `render_label_cfg` (already imported from `shortcuts_mixin`).
- Free single lowercase keys (reserved: `q e i r d l`, tabs `a b c m p s t`,
  `j`, `?`): chosen **`w` = Save, `v` = Revert, `x` = Delete**.

## Implementation

### 1. Rename the tab + intro to "Execution Profiles"
- `compose()`: change both the positional `"Profiles"` (line ~1295) and
  `TabPane("Profiles", …)` (line ~1306) to `"Execution Profiles"`. Tab id stays
  `tab_profiles`; `p` shortcut unchanged.
- In `_populate_profiles_tab` intro hint, reword the lead sentence from
  "Profiles pre-answer…" to "Execution profiles pre-answer…". (The section
  header is already "Execution Profiles".)

### 2. Non-scrolling four-pane layout
- `compose()`: `yield Vertical(id="profiles_content")` instead of
  `VerticalScroll` (mirrors `#shortcuts_content`).
- Rewrite `_populate_profiles_tab` to mount, in order, into `#profiles_content`:
  1. **Top pane (fixed):** the intro header/hint, the selector
     `CycleField(id="cf_profile_selector_{rc}")`, and the "Editing: <name>
     (<file>) <scope>" label. (Empty-profiles and "+ Add new profile" early
     returns stay as today.)
  2. **Search pane (fixed):** `Input(id="profiles_search",
     placeholder="Filter parameters by name…")`. Preserve its current text
     across param re-renders (see §3).
  3. **Params pane (scrolls):** `VerticalScroll(id="profiles_params_scroll")`
     holding the grouped fields produced by `compose_profile_fields(...)`.
  4. **Button pane (fixed):** `Horizontal(id="profiles_buttons",
     classes="tab-buttons")` with the three buttons.
- While mounting the params, **build a group/field index** by walking the flat
  `compose_profile_fields(...)` stream (no change to that function):
  - a `Label` with class `section-header` opens a new group;
  - a `CycleField`/`ConfigRow` is a field (key = `field_key`/`row_key`);
  - a following `Label` with class `section-hint` is that field's hint.
  Store `self._profile_groups: list[(header_label, [(key, field_widget,
  hint_label)])]` for the filter in §3.
- Buttons: drop the profile name from labels. Use
  `render_label_cfg("Save", "w")`, `render_label_cfg("Revert", "v")`,
  `render_label_cfg("Delete", "x")`; keep ids
  `btn_profile_save__/revert__/delete__{safe_fn}` so `on_button_pressed` and
  `_profile_id_map` mapping keep working.

### 3. Name-only fuzzy filter
- Handle `Input.Changed` for `#profiles_search` (new `@on(Input.Changed,
  "#profiles_search")` or branch in an `on_input_changed`). Call
  `_apply_profile_filter(text)`:
  ```python
  q = text.strip().lower()
  for header, fields in self._profile_groups:
      any_vis = False
      for key, fw, hint in fields:
          vis = (q in key.lower()) if q else True
          fw.display = vis
          if hint is not None: hint.display = vis
          any_vis = any_vis or vis
      header.display = any_vis
  ```
- Toggling `display` on the **field widgets themselves** (not a wrapper) keeps
  them out of `_nav_vertical` (it filters on `w.display`) while leaving them
  queryable by `collect_profile_values` (`query_one` finds them regardless of
  display) — so **edits to a filtered-out field are not lost on Save**. This is
  why we filter by display rather than unmounting/remounting widgets.
- On full repop (profile switch), re-apply the saved search text after mounting.

### 4. Disable Save/Revert when there are no unsaved changes
- Add `_profile_is_dirty(filename) -> bool`:
  ```python
  base = self.config_mgr.profiles.get(filename, {})
  data, _ = collect_profile_values(self.query_one, base,
                                   id_prefix=f"{_safe_id(filename)}_{self._profiles_tab_rc}")
  return data != base
  ```
  (`config_mgr.profiles[filename]` is the last saved/loaded YAML — it's what
  Save writes back and Revert reloads, so it is the correct baseline.)
- Add `_update_profile_button_states()` that sets `disabled = not dirty` on the
  Save and Revert buttons (Delete stays enabled). Disabled buttons are
  non-focusable, so `_nav_vertical` skips them automatically.
- Call it: at the end of `_populate_profiles_tab` (initial → not dirty →
  disabled); in `on_cycle_field_changed` for any non-selector profile CycleField;
  and at the end of `_handle_profile_string_edit` (string/int edits). After Save
  (`_save_profile` updates `config_mgr.profiles`) and Revert (reload + repop),
  the buttons return to disabled.

### 5. Single-key shortcuts w / v / x
- Add to `BINDINGS`: `Binding("w","profile_save",…,show=False)`,
  `Binding("v","profile_revert",…)`, `Binding("x","profile_delete",…)` (registered
  through `ShortcutsMixin` like the rest → customizable).
- Gate them to the Profiles tab in `check_action`: add a
  `_PROFILE_TAB_ACTIONS = {"profile_save","profile_revert","profile_delete"}`
  set; return `None` when the active tab isn't `tab_profiles` (mirrors the
  `_SHORTCUT_TAB_ACTIONS` gating). While the search `Input` has focus, Textual
  routes the printable key to the Input, so the binding does not fire — no extra
  guard needed.
- Action methods reuse existing paths, scoped to `self._selected_profile`:
  - `action_profile_save`: no-op + notify "No changes to save" if not dirty;
    else push `SaveProfileConfirmScreen` exactly like the
    `btn_profile_save__` branch.
  - `action_profile_revert`: no-op if not dirty; else `_revert_profile(fn)`.
  - `action_profile_delete`: push `DeleteProfileConfirmScreen` like the
    `btn_profile_delete__` branch.

### 6. Tab-key navigation between the four panes
- Intercept `tab` / `shift+tab` in `on_key` **before** the `Input`-focus guard,
  only when the active tab is `tab_profiles`; call `_cycle_profile_pane(+1/-1)`
  and `event.prevent_default(); event.stop()`.
- `_cycle_profile_pane(direction)`: anchors, in order, =
  selector `CycleField` → `#profiles_search` Input → first **visible**
  focusable field in `#profiles_params_scroll` → first **enabled** button in
  `#profiles_buttons` (skip any pane with no focusable target). Determine the
  current pane from `self.focused` (identity for selector/search; ancestor
  membership for params/buttons), then focus the next/previous anchor; if the
  focus isn't in any pane, focus the first anchor.
- Up/Down keep working within a pane via the existing `_nav_vertical` (it walks
  visible focusable widgets in DOM order). Note in the on-screen hint line:
  `Tab: switch pane`.
- **Verification risk:** Textual normally implements Tab as a focus binding.
  The existing `on_key` already pre-empts `up`/`down`/`enter` with
  `event.stop()`, so intercepting `tab` the same way should work; confirm when
  running the TUI. Fallback if it doesn't: register priority
  `Binding("tab"/"shift+tab", …)` gated to the Profiles tab instead.

### 7. CSS additions (App `CSS` block)
```
#profiles_content { height: 1fr; }
#profiles_params_scroll { height: 1fr; }
#profiles_search { margin: 0 1; }
```
The fixed top/search/button regions are `height: auto`; the params scroll takes
`1fr`, pinning the buttons to the bottom (same shape as the Shortcuts tab).

## Risk

### Code-health risk: medium
- Substantial rewrite of `_populate_profiles_tab` and new key/focus handling in
  a 3000-line TUI; the selector/up-down/Tab interplay and the extended
  `@on(CycleField.Changed)` handler are load-bearing focus paths · severity:
  medium · → mitigation: profiles_tab_manual_verification
- Tab-key interception may collide with Textual's built-in focus bindings,
  needing the priority-Binding fallback · severity: low · → mitigation: TBD

### Goal-achievement risk: medium
- TUI layout/focus behaviors (1fr panes inside a padded `TabPane`, display-based
  filtering vs. nav, pinned selector while scrolling) are easy to get subtly
  wrong and only fully observable by running the TUI · severity: medium · →
  mitigation: profiles_tab_manual_verification

### Planned mitigations
- timing: after | name: profiles_tab_manual_verification | type: manual_verification | priority: medium | effort: low | addresses: code-health + goal-achievement TUI focus/layout risks | desc: Manually verify the redesigned Execution Profiles tab — pinned selector while scrolling, name-only param filter, Tab pane-cycling, w/v/x shortcuts, Save/Revert dirty-gating, and save/revert persistence.

## Verification

1. Syntax: `python3 -c "import ast,sys; ast.parse(open('.aitask-scripts/settings/settings_app.py').read())"`.
2. Launch `ait settings`, press `p` (Execution Profiles tab) and check:
   - Tab title and intro read "Execution Profiles" / "Execution profiles…".
   - Selector + Save/Revert/Delete stay visible while the parameter list scrolls.
   - Typing in the search box filters parameters by **name** only; clearing
     restores all; groups with no matches hide their header.
   - Save/Revert are disabled on a freshly selected profile; changing any field
     (cycle or string edit) enables them; Save or Revert disables them again.
   - `w`/`v`/`x` trigger Save/Revert/Delete (and are no-ops on other tabs and
     while typing in the search box); button labels show the keys and carry no
     profile name.
   - `Tab`/`Shift+Tab` cycle focus selector → search → params → buttons; Up/Down
     still move within the params/buttons.
   - Editing + Save persists to the YAML; Revert restores on-disk state.
3. No automated tests cover this tab (confirmed — nothing in `tests/` references
   `_populate_profiles_tab`/`tab_profiles`), so verification is manual; a
   manual-verification follow-up is the right safety net (offered at Step 8c).

## Post-implementation
Follow task-workflow Step 8 (review) → 8b/8c/8d (upstream/manual-verification/
risk-mitigation follow-ups) → Step 9 (archival on current branch). The Step 8c
manual-verification offer covers the TUI behaviors above.

## Post-Review Changes

### Change Request 1 (2026-06-02)
- **Requested by user:** Tab did nothing when the parameter list was focused —
  it failed to move focus to the next pane.
- **Root cause:** In this Textual version a *disabled* `Button` still reports
  `can_focus = True`, so the buttons-pane anchor picked the disabled **Save**
  button (when the profile had no unsaved changes), and `focus()` on a disabled
  widget is a no-op — focus stayed on the field. The anchor/nav filters used
  `can_focus and display`, which does not exclude disabled widgets.
- **Changes made:** Switched anchor selection in `_cycle_profile_pane` (params
  + buttons loops) and the shared `_nav_vertical` / `_focus_first_in_tab`
  filters from `can_focus and display` to the stricter `focusable` property
  (which also excludes disabled and search-filtered widgets). Now Tab from a
  params field lands on Delete when Save/Revert are disabled, and on Save once
  the profile is dirty; Up/Down likewise skip disabled buttons.
- **Files affected:** `.aitask-scripts/settings/settings_app.py`
- **Verification:** Re-ran the Textual pilot — full Tab/Shift+Tab cycle across
  all four panes in both clean and dirty states; Up/Down skip disabled buttons.

## Final Implementation Notes
- **Actual work done:** Implemented entirely in
  `.aitask-scripts/settings/settings_app.py` as planned — renamed tab/intro to
  "Execution Profiles"; converted `#profiles_content` to a non-scrolling
  `Vertical`; built the four panes (fixed selector, fixed name-filter `Input`,
  scrolling `VerticalScroll` params, pinned button row); added
  `_apply_profile_filter` (name-only, display-toggle), `_profile_is_dirty` /
  `_update_profile_button_states` (Save/Revert disabled when unchanged),
  `_cycle_profile_pane` (Tab/Shift+Tab), `w`/`v`/`x` bindings +
  `action_profile_*` gated via `_PROFILE_TAB_ACTIONS` in `check_action`, and
  `render_label_cfg` button labels without the profile name.
- **Deviations from plan:** Two refinements forced by Textual runtime behavior,
  both caught by headless pilot tests:
  1. The new direct-child panes (`profiles_search`, `profiles_params_scroll`,
     `profiles_buttons`) needed **repop-counter-suffixed ids** + class-based CSS,
     because fixed sibling ids collide with the not-yet-removed previous copies
     on repop (`remove_children()` is deferred). The original code dodged this
     by nesting buttons in a per-repop `hbox`; the new direct children did not.
  2. Anchor/nav selection had to use the `focusable` property instead of
     `can_focus and display`: a *disabled* `Button` still reports
     `can_focus = True`, so Tab/Up-Down would target the disabled Save/Revert and
     `focus()` would no-op (the post-review Tab fix). This also hardened the
     shared `_nav_vertical` / `_focus_first_in_tab`.
- **Issues encountered:** See the two deviations — both surfaced only at runtime
  (DuplicateIds crash on repop; Tab no-op from the params pane) and were fixed
  before/after the user's review respectively.
- **Key decisions:** Filter hides via `display` (not unmount) so edits to
  filtered-out fields survive Save; shortcuts use single lowercase keys gated to
  the tab (no Ctrl/Alt, per user); the group/field index is parsed from the flat
  `compose_profile_fields()` stream so `lib/profile_editor.py` (and its
  `ProfileEditScreen` modal) is left untouched.
- **Upstream defects identified:** None. (The `_nav_vertical` /
  `_focus_first_in_tab` `can_focus`→`focusable` change is a hardening of the
  same file edited here, not a separate pre-existing defect — before this task
  no settings widget was ever disabled, so the latent gap never manifested.)
- **Verification:** Headless Textual `run_test()` pilots cover layout, name
  filter, dirty-gating + revert round-trip, real `Tab`/`Shift+Tab` cycling
  (clean + dirty), `w`/`v`/`x` keypresses (incl. tab-gating and search-box
  typing not firing shortcuts), and same-/switch-profile repop. Manual TUI
  verification is the residual safety net (Step 8c offer + the `after`
  risk-mitigation task).
