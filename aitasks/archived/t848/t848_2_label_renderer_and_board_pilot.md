---
priority: medium
effort: medium
depends: [t848_1]
issue_type: feature
status: Done
labels: [custom_shortcuts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-27 17:27
updated_at: 2026-05-29 06:37
completed_at: 2026-05-29 06:37
---

## Context

Second child of t848. Builds the `(X)plore`-style label renderer that decouples button-label text from the binding key, then proves the contract by migrating **the board TUI only**. Catching design issues here is cheap; t848_3 sweeps the same pattern across every other TUI.

Depends on t848_1 for the registry.

## Key Files to Modify

- **NEW** `.aitask-scripts/lib/shortcut_labels.py`
  - `render_label(text: str, key: str) -> str`:
    - First case-insensitive match of `key` (single char) in `text` is wrapped: `Pick` + `p` → `(P)ick`; `Copy Rel` + `r` → `Copy (R)el`.
    - No match: `text + " (" + key.upper() + ")"`. `Pick` + `o` → `Pick (O)`.
    - Multi-key combos (anything with `+` or longer than 1 char): `text + " (" + display_form(key) + ")"`, where `display_form("ctrl+r")` → `"Ctrl+R"`.
  - Pure function; no Textual dependency.

- **NEW** `.aitask-scripts/lib/shortcuts_mixin.py`
  - `class ShortcutsMixin`:
    - Class attr `_shortcuts_scope: str` (must be overridden by subclass).
    - Class attr `SHORTCUTS_MIXIN_BINDINGS = [Binding("?", "open_shortcuts_editor", "Keys")]` to splice into App `BINDINGS` like `TuiSwitcherMixin.SWITCHER_BINDINGS` already does (`lib/tui_switcher.py:1030-1032`).
    - `__init__`: calls `super().__init__(...)` then `self.BINDINGS = register_app_bindings(self._shortcuts_scope, self.BINDINGS)`.
    - `label(self, action_id: str, text: str) -> str`: looks up key via `keybinding_registry.resolve_key(self._shortcuts_scope, action_id, default=None)` and calls `render_label(text, key)`.
    - `action_open_shortcuts_editor(self)`: **stub** — `raise NotImplementedError("Implemented in t848_4")`. The binding slot is reserved so the registry knows about it from day one.

- `.aitask-scripts/board/aitask_board.py`:
  - `class KanbanApp(TuiSwitcherMixin, ShortcutsMixin, App):` add the mixin (preserve current MRO of `TuiSwitcherMixin`).
  - Set `_shortcuts_scope = "board"` on `KanbanApp` (and on any modal classes that own their own BINDINGS — typically not needed since modals' bindings are scoped to the same App instance).
  - Splice `*ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS` into `KanbanApp.BINDINGS` next to `*TuiSwitcherMixin.SWITCHER_BINDINGS` (line ~3279).
  - Replace every hand-coded `(X)` button label at `aitask_board.py:2262-2282`:
    - `Button("(P)ick", …)` → `Button(self.app.label("pick_task", "Pick"), …)`
    - `Button("(B)rainstorm", …)` → `…label("brainstorm_task", "Brainstorm")`
    - `Button("\U0001f512 (L)ock", …)` → keep the lock emoji prefix, label = `"\U0001f512 " + self.app.label("lock", "Lock")` (lock has no `Binding` today — add `Binding("l", "lock", "Lock", show=False)` to the App's BINDINGS so the registry knows the action exists).
    - Same shape for `(U)nlock`, `(C)lose`, `(V)iew Plan`, `(S)ave Changes`, `(R)evert`, `(E)dit`, `(N)ame`, `(D)elete/Archive`.
  - Audit any other `Button(...)` labels in `aitask_board.py` (and its submodules `lib/board_*` if any) that contain `\([A-Za-z]\)` — replace them too.

- **NEW** `tests/test_shortcut_labels.sh` — golden-style cases for `render_label`:
  - happy: `("Pick", "p")` → `(P)ick`
  - case-sensitivity: `("Pick", "P")` → `(P)ick`
  - no match: `("Pick", "o")` → `Pick (O)`
  - multi-letter case (compound): `("Toggle Children", "x")` → `Toggle Children` keeps `x` mid-word? — decide: case-insensitive first match means → `Toggle Children` has lowercase `x` mid-word `e(x)`. Decide whether to wrap the inner `x`; recommended: **yes, first letter match wherever found**. Document the rule in the renderer docstring.
  - multi-key: `("Move Right", "ctrl+r")` → `Move Right (Ctrl+R)`
  - empty key: `("Foo", "")` → `Foo`

- **NEW** `tests/test_shortcut_labels_golden/` — text files with the expected output of `render_label` for the cases above. Per memory `feedback_golden_file_tests_for_template_engines`, commit goldens and diff on every run.

## Reference Files for Patterns

- `.aitask-scripts/lib/tui_switcher.py` — exemplary mixin: splices its `SWITCHER_BINDINGS` into every App's BINDINGS, provides an action method, registers a shortcut. Mirror its shape.
- `.aitask-scripts/board/aitask_board.py:2262-2282` — the canonical hand-coded `(X)` label block.
- t848_1's Final Implementation Notes — read first for the `Binding` mutation API.

## Implementation Plan

1. Implement `shortcut_labels.render_label` purely (no Textual import). Add `display_form` for multi-key combos.
2. Implement `ShortcutsMixin` against the API decided in t848_1.
3. Modify `KanbanApp`:
   - Add mixin and `_shortcuts_scope`.
   - Add missing per-button bindings (`lock`, `unlock`, `view_plan`, `save_changes`, `revert`, `edit`, `rename`, `delete`) using `show=False` where appropriate.
   - Replace button-label strings.
4. Write golden tests for `render_label`.
5. Launch `ait board` manually; verify all migrated buttons render correctly under default keys.
6. With `userconfig.yaml` patched to `{shortcuts: {board: {pick_task: "o"}}}`, relaunch and verify `(P)ick` now reads `Pick (O)`.

## Verification Steps

```bash
bash tests/test_shortcut_labels.sh
# board pilot
ait board                       # observe button labels match default keys
# rebind test (manual)
yq -i '.shortcuts.board.pick_task = "o"' aitasks/metadata/userconfig.yaml
ait board                       # observe (P)ick has become Pick (O)
yq -i 'del(.shortcuts)' aitasks/metadata/userconfig.yaml
```

The manual board-launch verification belongs in the aggregated `manual_verification` sibling that the parent planning offers post-children-creation.

## Notes for sibling tasks

- Document the `render_label` first-match rule (first case-insensitive occurrence anywhere in the string, including mid-word) so t848_3's sweep doesn't have to guess.
- If `app.label(...)` proves awkward at button construction sites that don't have `self.app` handy (some Textual widgets compose before mount), record the workaround pattern (likely: pass a key-lookup closure into the widget at instantiation) so t848_3 can copy it.
