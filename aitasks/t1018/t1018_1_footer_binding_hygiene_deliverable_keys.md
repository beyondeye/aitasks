---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [brainstorming, tui, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
anchor: 1018
created_at: 2026-06-21 10:18
updated_at: 2026-06-21 10:44
---

## Context
Foundation child of t1018. Make `ait brainstorm`'s contextual shortcuts
**genuinely scoped to the screen/tab that owns them** — bound/unbound with the
active surface — instead of declared globally at the App level and merely
*hidden* per-context via `check_action()` (which returns `None` = hidden but
still-live). This child establishes the per-screen binding model and the
deliverable-key approach that t1018_2 (operation restart) builds on, and it
fixes the genuinely-broken bindings.

**Why this is the foundation:** t1018_2's restart actions and the existing
retry-apply actions share the same `ctrl+shift+x`/`ctrl+shift+y` surface. This
child owns the binding-model cleanup so t1018_2 can re-home that functionality
onto the Running-tab operation row without clobbering it.

### Verified current state (post-t983, corrects stale task-body premises)
The umbrella body (t1018) was written before t983_11 landed; several claims are
stale. Confirmed against the as-landed code:
- **`ctrl+shift+b`/`ctrl+shift+l` (preview ratio / numbered) were already moved
  by t983_11** onto `ActionsWizardScreen.BINDINGS` (`brainstorm_app.py:3278-3279`),
  so they are now correctly *scoped to the wizard modal* — the umbrella's
  "lines 3849-3850, App-level, ungated" claim is stale. **But they remain
  undeliverable `ctrl+shift+<letter>` chords** (the ghostty→tmux→Textual stack
  collapses `Ctrl+Shift+B`→`Ctrl+B` = tmux prefix; `Ctrl+Shift+L`→`Ctrl+L`),
  so fixing their *delivery* is still in scope here.
- **The genuine footer leak is the three retry-apply actions**, all App-level and
  NOT gated by `check_action` (default branch returns `True` → shown/live
  everywhere):
  - `ctrl+r` → `action_retry_initializer_apply` (`:5545`, **show=True**, visibly
    leaks into the footer on every tab/screen).
  - `ctrl+shift+x` → `action_retry_explorer_apply` (`:5546`, show=False, live
    everywhere; undeliverable chord).
  - `ctrl+shift+y` → `action_retry_synthesizer_apply` (`:5548`, show=False, live
    everywhere; undeliverable chord).
- The Running-tab row actions (`w`/`R`/`x`/`p`/`k`/`K`) are per-row `on_key`
  handlers with render-time hints, **deliberately NOT footer Bindings**
  (t983_9's explicit decision) — that pattern is correct and stays.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py`
  - App-level `BINDINGS` (`:5516-5550`) — the 15 explicit bindings + 2 mixin unpacks.
  - `check_action()` (`:5632-5670`) — gates only `node_action`/`toggle_deferred`
    (`:5644-5653`) and `_TAB_SCOPED_ACTIONS` (`open_node_detail`→`tab_browse`,
    dict at `:5555`, gate at `:5656-5670`); default `return True` (`:5657-5658`).
  - `ActionsWizardScreen.BINDINGS` (`:3275`, chords at `:3278-3279`) — the wizard
    modal owning the preview-pane keys; has editable TextAreas
    (`ta_module_preview_steer` etc.) so a focused field consumes letter keys.
- `tests/test_brainstorm_proposal_preview.py` — currently calls action methods
  directly; only one `pilot.press("tab")` (`:357`). Needs real key-dispatch tests.

## Reference Files for Patterns
- `aidocs/framework/tui_conventions.md` — "TUI footer must surface every
  operation on the affected tab/screen"; the `check_action`/`priority`
  query-scope gotchas; "New TUIs / dialogs must register in the global shortcut
  manifest" (`ShortcutsMixin` / `_shortcuts_scope` / `register_app_bindings`;
  brainstorm_app.py is already a `KNOWN_BINDING_SOURCES` entry, so new in-file
  scopes are auto-swept).
- `aidocs/framework/tmux_gateway.md` — read before editing.
- `_PreviewMinimap` priority `tab`/`shift+tab` bindings (`:953-957`) and the
  `NodeRow` widget-level `o` binding (`:2522-2524`) are existing examples of
  per-widget BINDINGS in this file.

## Implementation Plan (detail in aiplans/p1018/p1018_1_*.md)
1. **Gate the three leaking retry-apply actions** via `check_action()` so they
   stop showing/firing globally — scope each to the surface where it is
   meaningful. Keep the underlying `action_retry_*` / `_try_apply_*` methods
   intact (t1018_2 re-homes the explorer/synthesizer ones onto the Running-tab
   GroupRow and removes the dead chord bindings — DO NOT delete those two action
   methods here).
2. **Replace the undeliverable wizard preview chords** `ctrl+shift+b`/
   `ctrl+shift+l` with deliverable keys on `ActionsWizardScreen` (prefer
   `alt+<letter>` — ESC-prefixed, non-printable, ignored by a focused TextArea,
   and reliably distinguishable; AVOID bare `ctrl+b` = tmux prefix and any
   `ctrl+shift+<letter>`). Remove the dead chord bindings.
3. **Establish the per-screen scoping model**: prefer moving contextual bindings
   onto the owning Screen/widget `BINDINGS` (bound/unbound with the surface);
   where that is impractical, extend `check_action()` so every leaking action is
   gated. Honor the `self.screen.query_one` vs `self.query_one` priority gotcha.
4. **Footer-coverage audit** (per the convention): on each tab/screen, every
   operation should be footer-visible OR deliberately hidden with justification.
   Flip wrongly-hidden `show=False` bindings; gate leaking ones.
5. **Register/refresh shortcut-manifest scopes** if any new scope is introduced.
6. **Coordinate with t1018_2**: this child does NOT touch the Running-tab row
   `on_key` pattern; it leaves the `action_retry_explorer_apply` /
   `action_retry_synthesizer_apply` methods for t1018_2 to re-home. Document the
   handoff in `## Notes for sibling tasks`.

## Verification
- `python -m pytest tests/test_brainstorm_proposal_preview.py` green, including
  NEW `pilot.press(...)` tests for the replacement preview keys (the suite never
  drove key dispatch before — that is why the undeliverable chords passed CI).
- A focused TextArea in the wizard still receives the replacement keys as no-ops
  (does not trigger the preview action) when typing — assert via pilot.
- `check_action` unit/pilot assertions: each retry-apply action is hidden/inactive
  on tabs/screens where it is irrelevant, active where relevant.
- Full brainstorm suite green: `python -m pytest tests/test_brainstorm*.py`.
- **Live-stack manual verification is REQUIRED and is covered by the aggregate
  t1018_4 sibling** — the headless Textual driver delivers chords the real
  ghostty→tmux→Textual stack cannot, so unit/pilot tests cannot catch the
  delivery class of bug. (Verify the new `alt+<letter>` keys actually fire
  through the real terminal stack inside tmux.)
