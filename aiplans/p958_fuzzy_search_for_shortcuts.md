---
Task: t958_fuzzy_search_for_shortcuts.md
Worktree: (none — working on current branch, profile 'fast')
Branch: main
Base branch: main
---

# t958 — Fuzzy search box for the shortcuts dialogs

## Context

aitasks recently added customizable keyboard shortcuts to every TUI. Two
places list shortcuts:

1. **The in-TUI `?` editor modal** — `ShortcutEditorModal`
   (`.aitask-scripts/lib/shortcut_editor_modal.py`), opened with `?` in every
   TUI. It shows a `DataTable` of every binding visible from the active scope
   (scope + modal sub-scopes + `shared`).
2. **The Settings TUI "Shortcuts" tab** — `_populate_shortcuts_tab()` in
   `.aitask-scripts/settings/settings_app.py`, which lists **all** bindings
   across **every** TUI in a `DataTable`.

Neither dialog can be filtered, so finding a specific shortcut among dozens of
rows is tedious. The task: add a fuzzy search box at the top of the dialog so
the user can type to narrow the list. (User decisions: cover **both** dialogs;
use **fuzzy subsequence** matching.)

## Approach

Add a reusable fuzzy-subsequence matcher under `lib/`, then wire an always-
visible `Input` search box into each of the two dialogs that filters and ranks
the table rows live. Filtering is **display-only** — it never changes the
underlying binding set, so all collision/rebind/reset logic is untouched.

### 1. New shared helper: `.aitask-scripts/lib/fuzzy_filter.py`

A small, general-purpose subsequence matcher. The repo already has a fuzzy
matcher in `.aitask-scripts/codebrowser/file_search.py` (`PathFuzzySearch`,
adapted from *toad*), but it lives in the `codebrowser/` package and is
path-specialized (first-letter bonus keyed on `/`, 2× filename boost). Importing
`codebrowser` code from `lib/` would invert the dependency direction, so this
adds a sibling **general-text** scorer in `lib/` instead (word-boundary bonus on
spaces, not `/`; no path heuristics). Codebrowser keeps its own version
untouched — de-duping the two is explicitly out of scope.

API:

```python
def match(query: str, candidate: str, *, case_sensitive: bool = False
          ) -> tuple[float, Sequence[int]]:
    """(score, matched_positions); (0.0, ()) when query is not a subsequence."""

def rank(query, items, *, key):
    """Return items whose key() string fuzzily matches `query`, best first.
    Empty/whitespace query → items returned unchanged (original order)."""
```

`match` reuses the toad alignment algorithm (discover every in-order alignment,
score the best) with a generalized first-letter set: position `0` and every
index after a space. `rank` sorts by **negative score** (stable → ties keep the
caller's original order). Scope-honest names per repo conventions (not a generic
`utils`).

### 2. `ShortcutEditorModal` (`lib/shortcut_editor_modal.py`)

- **compose():** insert `Input(id="se_search", placeholder="Filter shortcuts…")`
  between the `#se_help` label and the `#se_table` DataTable. Add `Input` to the
  `textual.widgets` import.
- **State:** `self._query = ""` in `__init__`.
- **on_mount():** focus the **search Input** instead of the table (so the user
  can type immediately) — keep `add_columns(...)` + `_refresh_table()`.
- **Visible-rows helper:** add `_visible_rows()` returning `self._rows` when
  `self._query` is blank, else
  `fuzzy_filter.rank(self._query, self._rows, key=self._candidate)` where
  `_candidate((scope, action_id, default_key, label))` builds
  `f"{action_id} {label} {self._effective_key(...)} {default_key} {scope}"`
  (so the user can search by action, label, the actual bound key, or scope).
- **_refresh_table():** iterate `self._visible_rows()` instead of `self._rows`.
  The collision helpers (`_would_collide`, `_colliding_pairs`) still scan the
  full `self._rows`, so red-highlighting and rebind-blocking stay correct even
  when a colliding partner is filtered out of view.
- **on_input_changed(event):** guard `event.input.id == "se_search"`, set
  `self._query = event.value`, `_refresh_table()`, then move the table cursor to
  row 0 (result set changed). Non-filter refreshes (rebind/revert/reset) keep
  the existing clamp-preserve behavior since the query is unchanged.
- **Input → table navigation** (Input is single-line, so ↑/↓ bubble to the
  modal): add `on_input_submitted` (Enter in the box) and a `Binding("down",
  "focus_table", show=False)` whose `action_focus_table` focuses `#se_table` and
  positions the cursor on row 0. When the table is focused it consumes ↓ itself,
  so this binding only fires from the Input. While the Input is focused it
  consumes printable keys, so the existing `r`/`d`/`s` modal actions are
  naturally inert during typing and resume once focus is in the table — no
  conflict. `Esc` still cancels from either focus.
- **CSS:** add an `#se_search { width: 100%; margin-bottom: 1; }` rule to the
  modal's self-contained `DEFAULT_CSS` (per the "modals carry their own CSS"
  convention).

### 3. Settings "Shortcuts" tab (`settings/settings_app.py`)

- In the build-chrome branch of `_populate_shortcuts_tab()`, mount
  `Input(id="shortcuts_search", placeholder="Filter shortcuts…")` between the
  `.section-hint` label and the `DataTable` (so it survives the
  refresh-in-place path, which only re-fills rows).
- Add `self._shortcuts_query = ""` to `SettingsApp.__init__` (or initialize
  lazily). In the row-fill loop, wrap
  `keybinding_registry.iter_all_bindings()` with
  `fuzzy_filter.rank(self._shortcuts_query, [...], key=...)`, candidate =
  `f"{action_id} {label} {current} {default_key} {scope}"`.
- Add an `on_input_changed` handler guarded on
  `event.input.id == "shortcuts_search"` that stores the query and calls
  `self._populate_shortcuts_tab()`. (Check for an existing `on_input_changed`
  in `SettingsApp`; if one exists, add the branch there instead of a duplicate
  method.)
- **Do not** auto-focus this Input — it lives in a multi-widget tab; the user
  Tabs/clicks to it. The buttons' `d`/`l` shortcut keys are consumed by the
  Input only while it is focused, so no clash.
- Import `fuzzy_filter` at the top of `settings_app.py`.

## Tests

Python `unittest` (run via `python3 tests/<file>.py`), matching existing
harness style (`sys.path` insert of `.aitask-scripts` + `lib`, Textual
`App().run_test()` pilot for widget behavior).

- **`tests/test_fuzzy_filter.py` (new):** unit-test `match`/`rank` — subsequence
  hit/miss, ranking order (consecutive > scattered, word-start bonus), empty
  query passthrough, case-insensitivity.
- **`tests/test_shortcut_editor_modal.py` (extend):** pilot test — open the
  modal, type into `#se_search`, assert the DataTable `row_count` drops to the
  matching rows and a non-matching action is gone; clear the box → all rows
  return; assert collision/rebind still works after filtering.
- **`tests/test_settings_shortcuts_tab.py` (extend):** pilot test — type into
  `#shortcuts_search`, assert the shortcuts table is filtered/ranked and
  clearing restores the full list.

## Verification

1. `python3 tests/test_fuzzy_filter.py`
2. `python3 tests/test_shortcut_editor_modal.py`
3. `python3 tests/test_settings_shortcuts_tab.py`
4. `shellcheck` not needed (no shell changes).
5. Manual: `ait board`, press `?`, type in the search box — list narrows live,
   ↓/Enter moves into the table, rebind (`Enter`) / reset (`d`) / save (`s`)
   still work; `Esc` closes. Then `ait settings` → Shortcuts tab, type in the
   filter — the cross-TUI list narrows and ranks; clearing restores it.

## Step 9 (Post-Implementation)

Per the shared task-workflow: review/commit (Step 8), then archive via
`./.aitask-scripts/aitask_archive.sh 958` and `./ait git push` (Step 9).
Working on the current branch (profile 'fast'), so no worktree/merge cleanup.

## Risk

### Code-health risk: low
- Filtering is display-only and the new matcher is a self-contained pure module, so collision/rebind/save logic is untouched; main blast radius is 2 edited files + 1 new helper + tests. · severity: low · → mitigation: TBD
- Auto-focusing the `#se_search` Input on modal mount changes initial focus from the table — could affect existing `?`-modal pilot tests / muscle-memory; covered by updating the modal pilot test. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Input→table navigation assumes Textual's single-line `Input` lets ↑/↓ bubble to the modal binding; if that assumption fails, `↓` won't move into the table (Enter-to-table still works as fallback). Verified during implementation via the pilot test. · severity: low · → mitigation: TBD

## Scope notes / rejected alternatives

- **Reusing `codebrowser.PathFuzzySearch` directly:** rejected — wrong package
  dependency direction (`lib/` → `codebrowser/`) and path-specific heuristics.
- **Reusing `FuzzySelect` (`lib/agent_model_picker.py`):** it's a full
  Input+OptionList *widget* with its own selection model; the shortcuts dialogs
  need a filter over an existing `DataTable`, not a replacement picker. Only its
  filter *pattern* is borrowed; the matcher choice is fuzzy (user decision), not
  its substring filter.
- **Settings tab auto-focus:** rejected — it is one widget among many in a tab;
  stealing focus on tab entry would be disruptive. The `?` modal does auto-focus
  because search is its primary purpose.
