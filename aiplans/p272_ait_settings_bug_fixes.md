---
Task: t272_ait_settings_bug_fixes.md
Worktree: (working on current branch)
Branch: main
Base branch: main
---

# Plan: Settings TUI Bug Fixes (t272)

## Context

The `ait settings` TUI (`aiscripts/settings/settings_app.py`, Textual framework) has several UX issues:
1. No arrow key navigation — only Tab works, and only partially
2. Agent Defaults tab: pressing Enter opens a plain text input modal for editing model names — bad UX since values follow `<agent>/<model>` format
3. Project/user layer settings hidden behind a "Save to" toggle inside the modal dialog

## Changes — all in `aiscripts/settings/settings_app.py`

### 1. Global navigation improvements

- **Letter shortcuts**: `a` (Agent Defaults), `b` (Board), `m` (Models), `p` (Profiles) to jump to tabs
- **Up/Down arrows**: Move focus between focusable widgets within the active tab
- Both handled in `on_key()` with guards: skip when `Input` has focus or modal is active
- Handle letter keys in `on_key()` (not BINDINGS) to avoid firing when typing in Input fields
- Add `_nav_vertical()` helper: finds focusable widgets in active TabPane, moves focus

### 2. FuzzySelect widget (new)

Custom Container widget with autocomplete filtering:
- **Input** field at top for typing
- **VerticalScroll** with **FuzzyOption** items below, filtered on `Input.Changed`
- Up/Down arrows navigate highlighted option (handled in `FuzzySelect.on_key`, bubbles from Input since single-line Input doesn't consume up/down)
- Enter selects (via `Input.Submitted`)
- Escape posts `Cancelled` message
- Case-insensitive substring match on both display text and description
- Posts `Selected(value)` message on selection

### 3. AgentModelPickerScreen modal (new, replaces EditValueScreen)

Two-step ModalScreen for agent defaults editing:
- **Step 1**: FuzzySelect for code agent (claude, gemini, codex, opencode — from `MODEL_FILES.keys()`)
- **Step 2**: FuzzySelect for model (loaded from `models_<agent>.json`, showing name + notes + verification score for the operation)
- Escape on step 2 goes back to step 1; Escape on step 1 dismisses
- Dismisses with `{"key": operation, "value": "agent/model"}`

### 4. Agent Defaults tab: dual project/user rows

Replace single ConfigRow per operation with TWO rows:
- `[PROJECT] task-pick: claude/opus4_6` — project-level setting
- `[USER] task-pick: (inherits project)` or actual override value
- Row IDs: `agent_proj_<key>` and `agent_user_<key>`
- Enter on either row opens AgentModelPickerScreen; save target determined by which row was edited
- **d/Delete key** on a USER row clears the override (removes from local config)

### 5. Remove EditValueScreen

- Delete `EditValueScreen` class (lines 272-306) — only used for agent defaults, now replaced
- Delete `_handle_agent_edit` method (lines 516-546) — replaced by `_handle_agent_pick`
- Keep `EditStringScreen` (used for profiles) and `ImportScreen` (used for import)

## Implementation order

- [x] 1. Add `FuzzyOption` and `FuzzySelect` widget classes (after ConfigRow, ~line 267)
- [x] 2. Add `AgentModelPickerScreen` modal (after EditStringScreen, ~line 368)
- [x] 3. Delete `EditValueScreen` class
- [x] 4. Rewrite `_populate_agent_tab()` for dual rows
- [x] 5. Rewrite `on_key()`: add a/b/m/p tab switching, up/down nav, new agent row handling, d/delete for clearing overrides
- [x] 6. Add helper methods: `_nav_vertical()`, `_handle_agent_pick()`, `_clear_user_override()`
- [x] 7. Delete `_handle_agent_edit()`
- [x] 8. Update CSS: add FuzzySelect, FuzzyOption, picker dialog styles
- [x] 9. Update hint text in Agent Defaults tab

## Key files

- `aiscripts/settings/settings_app.py` — sole file to modify
- `aiscripts/lib/config_utils.py` — reference for config API (no changes)
- `aitasks/metadata/models_*.json` — model data structure reference
- `aitasks/metadata/codeagent_config.json` — config structure reference

## Verification

1. Run `python aiscripts/settings/settings_app.py` (or `./ait settings`)
2. Test letter keys a/b/m/p switch tabs
3. Test up/down arrows move focus between widgets in each tab
4. Test Agent Defaults: each operation shows [PROJECT] and [USER] rows
5. Test Enter on a row opens the two-step picker (agent → model)
6. Test fuzzy filtering by typing partial names
7. Test Escape goes back (step 2→1) or dismisses (step 1)
8. Test d/Delete clears a user override
9. Test saving to project vs user layer works correctly
10. Test Board/Models/Profiles tabs still function normally

## Final Implementation Notes

- **Actual work done:** All 5 planned changes implemented — navigation improvements, FuzzySelect widget, AgentModelPickerScreen two-step picker, dual project/user rows, EditValueScreen removal.
- **Deviations from plan:**
  - FuzzySelect child widget IDs made dynamic (`{self.id}_input`, `{self.id}_list`) to avoid DuplicateIds when multiple FuzzySelect instances coexist in the modal.
  - Agent tab widget IDs include a repopulation counter (`_repop_counter`) to avoid DuplicateIds from Textual's async `remove_children()`.
  - `@on(FuzzySelect.Selected, "#selector")` CSS-selector decorators replaced with method-name handlers (`on_fuzzy_select_selected`) because custom messages lack the `control` property required by Textual's `@on` with CSS selectors.
  - ConfigRow got a `subordinate` flag for indented user override rows with visual hierarchy (└ connector, "(d to remove)" hint).
  - Added explanatory hint text describing project vs user local preference layout.
- **Issues encountered:**
  - Textual's `@on` decorator with CSS selectors requires a `control` property on message classes — fixed by using method-name handlers.
  - Textual's `remove_children()` is async; IDs remain registered until event loop processes removal — fixed with counter-based unique IDs.
  - Modal detection in `on_key` required `isinstance(self.screen, ModalScreen)` not `isinstance(self.screen, SettingsApp)`.
- **Key decisions:** Used method-name message handlers over CSS-selector-based `@on` for FuzzySelect messages to avoid needing `control` property.

## Step 9: Post-Implementation

After implementation and commit, archive the task using `./aiscripts/aitask_archive.sh 272`.
