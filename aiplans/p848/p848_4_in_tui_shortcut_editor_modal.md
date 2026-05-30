---
Task: t848_4_in_tui_shortcut_editor_modal.md
Parent Task: aitasks/t848_customizable_shortcuts.md
Sibling Tasks: aitasks/t848/t848_5_settings_tui_shortcuts_tab.md, aitasks/t848/t848_6_documentation_for_customizable_shortcuts.md, aitasks/t848/t848_7_manual_verification_customizable_shortcuts.md
Archived Sibling Plans: aiplans/archived/p848/p848_1_shortcut_registry_and_overrides.md, aiplans/archived/p848/p848_2_label_renderer_and_board_pilot.md, aiplans/archived/p848/p848_3_sweep_remaining_tuis.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-05-30 22:43
---

# p848_4 — `?` in-TUI shortcut editor modal (verified)

## Context

Fourth child of **t848 "customizable shortcuts"**. The prior children built the
plumbing:

- **t848_1** — `lib/keybinding_registry.py` (scope/action_id → key map + override
  resolver) and `lib/shortcut_persist.py` (atomic `save_override` /
  `clear_override` / `reset_scope` into `aitasks/metadata/userconfig.yaml`).
- **t848_2** — `lib/shortcut_labels.py` (the `(X)plore` renderer) and
  `lib/shortcuts_mixin.py` (`ShortcutsMixin` + module-level `get_label`); board
  pilot.
- **t848_3** — swept every remaining TUI onto `ShortcutsMixin`; `?` is bound at
  App level in every TUI (via `SHORTCUTS_MIXIN_BINDINGS`) and currently fires a
  *stub* toast: "Shortcuts editor not yet available — coming in t848_4". Also did
  the brainstorm `?`→`H` migration (already in place — verified).

This task replaces that stub with the real `ShortcutEditorModal`, so a user can
press `?` inside any TUI and rebind/reset/clear that TUI's shortcuts, persisted to
`userconfig.yaml` — closing the customization loop without hand-editing YAML.

Registered scopes after t848_3 (the editor enumerates these): `applink`,
`applink.pairing`, `applink.status`, `board`, `board.detail`, `board.agent_cmd`,
`brainstorm`, `brainstorm.dag`, `brainstorm.compare_select`, `codebrowser`,
`codebrowser.copypath`, `diffviewer`, `minimonitor`, `monitor`, `settings`,
`stats`, `syncer`, `shared`, `shared.stale_entry`.

## Verify-mode findings (deltas from the on-disk p848_4 plan)

Confirmed against the current codebase (Textual **8.2.7**). The on-disk plan is
sound in shape; these are corrections folded into the steps below:

1. **Import convention.** The on-disk plan shows `from .shortcut_editor_modal
   import …` (package-relative). That is **wrong** here — `.aitask-scripts/lib/`
   is on `sys.path`, so modules import as top-level names (this is exactly how
   `shortcuts_mixin.py` imports `keybinding_registry`/`shortcut_labels`). Use
   `from shortcut_editor_modal import ShortcutEditorModal`.
2. **Test is Python, not bash.** The repo's established Pilot-driven test pattern
   is a `.py` file run via `tests/run_all_python_tests.sh`
   (`async with app.run_test() … await pilot.press(...)`, e.g.
   `tests/test_brainstorm_dag_op_keybinding.py`). Write
   `tests/test_shortcut_editor_modal.py`, not `…​.sh`.
3. **Rebind trigger = `DataTable.RowSelected`, not a modal `enter` binding.** A
   `DataTable` with `cursor_type="row"` consumes `enter` (posts `RowSelected`)
   before a modal-level `Binding("enter", …)` would fire. Hook
   `on_data_table_row_selected`. Keep `r`/`d`/`s`/`escape` as modal `BINDINGS` —
   `DataTable` does not bind those letters, so they bubble up to the modal.
8. **Conflicts are blocked at edit time, never persisted** (user decision). Both
   a rebind-capture and a reset-to-default are validated against the other
   effective in-scope keys *before* being applied. If the change would collide,
   it is refused with a `notify(...)` error naming the conflicting action — the
   pending state stays collision-free, so save always proceeds with no
   confirm dialog. This makes a `_ConfirmScreen` unnecessary. The blocked
   reset-to-default case is exactly what the deferred **t848_8** (cascade reset)
   will later auto-resolve.
4. **Add a "Scope" column.** With the sub-scope model (`board` vs `board.detail`,
   etc.) the editor must show scope to disambiguate identically-named actions
   (e.g. `close` exists in several scopes). Columns: **Scope · Action · Key ·
   Default · Label · Origin**.
5. **`refresh_bindings()` does NOT live-rekey.** `App.refresh_bindings()` exists
   in 8.2.7 but only re-evaluates *enabled* state + refreshes the footer; it does
   not rebuild the active key-map from `BINDINGS`. So the effective behavior is
   the **restart-fallback**: persist the override, drop the registry cache,
   best-effort `refresh_bindings()`, then notify "Saved — restart the TUI to
   apply." (This answers the explicit question in the task's "Notes for sibling
   tasks" for t848_5.)
6. **Public registry getter** instead of reaching into `_DEFAULTS`. Add
   `iter_scope_bindings(prefix)` to `keybinding_registry.py` (framework change is
   welcome here). It returns every `(scope, action_id, default_key, label)` whose
   scope equals `prefix` or starts with `prefix + "."`, **plus** the global
   `shared` / `shared.*` scopes (those bindings — e.g. the `j` TUI switcher — are
   active in every TUI; the Scope column makes the cross-TUI effect explicit).
7. **brainstorm `?`→`H` already done** (t848_3, commit 663755c0). No migration
   work — verified `Binding("H", "op_help")` (line 2759), `?` editor splice (line
   2748), footer "Esc / H close" (line 1428). The task's "if deferred, do it
   here" branch is a no-op.

## Files

**New:**
- `.aitask-scripts/lib/key_capture_screen.py`
- `.aitask-scripts/lib/shortcut_editor_modal.py`
- `tests/test_shortcut_editor_modal.py`

**Modified:**
- `.aitask-scripts/lib/keybinding_registry.py` — add `iter_scope_bindings()`.
- `.aitask-scripts/lib/shortcuts_mixin.py` — replace the stub
  `action_open_shortcuts_editor` body.

No `./ait` startup-chain change → **no** `tests/lib/test_scaffold.sh` update
(these are `lib/` modules, consistent with t848_1's precedent). No `.j2`/skill or
golden-file changes.

## Step-by-step

### 1. `keybinding_registry.iter_scope_bindings(prefix)`

```python
def iter_scope_bindings(prefix: str) -> list[tuple[str, str, str, str]]:
    """Return (scope, action_id, default_key, label) for the editor.

    Includes every recorded binding whose scope == prefix or starts with
    `prefix + "."` (the TUI's own scope + its modal sub-scopes), plus the
    global `shared` / `shared.*` scopes. Sorted by (scope, action_id) for a
    stable table order.
    """
    out = []
    for (scope, action_id), (default_key, label) in _DEFAULTS.items():
        if (
            scope == prefix
            or scope.startswith(prefix + ".")
            or scope == "shared"
            or scope.startswith("shared.")
        ):
            out.append((scope, action_id, default_key, label))
    return sorted(out, key=lambda r: (r[0], r[1]))
```

### 2. `key_capture_screen.py`

```python
from __future__ import annotations
from textual import events
from textual.screen import ModalScreen
from textual.widgets import Label

class KeyCaptureScreen(ModalScreen[str | None]):
    """One-shot key capture. Dismisses with the key combo, or None on Esc."""
    DEFAULT_CSS = """  /* self-contained, per feedback_modal_self_contained_css */
    KeyCaptureScreen { align: center middle; }
    KeyCaptureScreen > Label {
        width: auto; padding: 1 3; border: round $accent;
        background: $surface; color: $text;
    }
    """
    # Bare modifier names that arrive as their own Key events; ignore them and
    # keep waiting for the real combo.
    _MODIFIERS = frozenset({"ctrl", "shift", "alt", "meta", "super", "hyper"})

    def compose(self):
        yield Label("Press a key to bind…  (Esc to cancel)")

    def on_key(self, event: events.Key) -> None:
        event.stop()
        event.prevent_default()
        if event.key == "escape":
            self.dismiss(None)
            return
        if event.key in self._MODIFIERS:
            return  # wait for the full combo, e.g. "ctrl+r"
        self.dismiss(event.key)
```

`event.key` already encodes combos (`"ctrl+r"`, `"shift+down"`). No allow-list
is applied yet — documented for t848_5 (e.g. it may want to block `ctrl+c`).

### 3. `shortcut_editor_modal.py`

`ShortcutEditorModal(ModalScreen[None])` — does **not** use `ShortcutsMixin`
(its own `escape/r/d/s` keys are intentionally non-customizable, so they must
not register into the editable registry). Carries its own `DEFAULT_CSS`.

```python
from __future__ import annotations
from dataclasses import dataclass
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Label

import keybinding_registry
import shortcut_persist
from key_capture_screen import KeyCaptureScreen

_CLEAR = object()  # pending sentinel: "remove this override on save"

class ShortcutEditorModal(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("r", "revert_row", "Revert edit"),       # undo unsaved edit on row
        Binding("d", "reset_default", "Reset to default"),  # clear override -> default
        Binding("s", "save", "Save"),
    ]
    DEFAULT_CSS = """ ... #shortcut_editor_dialog, DataTable, .collision { color:$error } ... """

    def __init__(self, scope: str) -> None:
        super().__init__()
        self._scope = scope
        # rows: list of (scope, action_id, default_key, label)
        self._rows = keybinding_registry.iter_scope_bindings(scope)
        # pending edits keyed by (scope, action_id) -> new_key:str | _CLEAR
        self._pending: dict[tuple[str, str], object] = {}

    def compose(self) -> ComposeResult:
        with Container(id="shortcut_editor_dialog"):
            yield Label(f"Shortcuts — {self._scope}", id="se_title")
            yield Label(
                "Enter: rebind • r: revert edit • d: reset to default • s: save • Esc: cancel",
                id="se_help",
            )
            yield DataTable(id="se_table", cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        t = self.query_one("#se_table", DataTable)
        t.add_columns("Scope", "Action", "Key", "Default", "Label", "Origin")
        for scope, action_id, default_key, label in self._rows:
            t.add_row(*self._row_cells(scope, action_id, default_key, label),
                      key=f"{scope}{action_id}")  # NUL-joined row key
        self._recompute_collisions()

    # --- effective-key / cell helpers -------------------------------------
    def _effective_key(self, scope, action_id, default_key) -> str:
        if (scope, action_id) in self._pending:
            pend = self._pending[(scope, action_id)]
            return default_key if pend is _CLEAR else pend  # _CLEAR -> default
        return keybinding_registry.resolve_key(scope, action_id) or default_key

    def _origin(self, scope, action_id) -> str:
        if (scope, action_id) in self._pending:
            return "pending"
        ov = keybinding_registry.load_user_overrides().get(scope, {})
        return "user" if action_id in ov else "default"
    # _row_cells -> (scope, action_id, effective_key, default_key, label, origin)

    # --- rebind flow -------------------------------------------------------
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        scope, action_id = str(event.row_key.value).split("", 1)
        self.app.push_screen(
            KeyCaptureScreen(),
            lambda key: self._apply_capture(scope, action_id, key),
        )

    def _apply_capture(self, scope, action_id, key):
        if key is None:
            return
        clash = self._would_collide(scope, action_id, key)
        if clash is not None:
            self.app.notify(
                f"'{key}' is already bound to '{clash}' in {scope}.",
                severity="error", timeout=4)
            return
        self._pending[(scope, action_id)] = key
        self._refresh_table()

    # --- r / d / s ---------------------------------------------------------
    def action_revert_row(self):   # discard this row's UNSAVED pending edit
        rk = self._cursor_key()
        self._pending.pop(rk, None); self._refresh_table()

    def action_reset_default(self):  # clear override -> revert to default key
        scope, action_id = self._cursor_key()
        default_key = self._default_for(scope, action_id)
        clash = self._would_collide(scope, action_id, default_key)
        if clash is not None:
            self.app.notify(
                f"Cannot reset: default key '{default_key}' is already bound to "
                f"'{clash}' in {scope}. Rebind that first.",
                severity="error", timeout=5)
            return
        self._pending[(scope, action_id)] = _CLEAR
        self._refresh_table()

    def action_cancel(self):
        self.dismiss(None)

    def action_save(self):
        # Pending is collision-free by construction (edit-time blocking), so
        # save proceeds unconditionally — no confirm dialog.
        touched = set()
        for (scope, action_id), pend in self._pending.items():
            default_key = self._default_for(scope, action_id)
            if pend is _CLEAR or pend == default_key:
                shortcut_persist.clear_override(scope, action_id)
            else:
                shortcut_persist.save_override(scope, action_id, pend)
            touched.add(scope)
        for scope in touched:
            keybinding_registry.refresh(scope)
        try:
            self.app.refresh_bindings()
        except Exception:
            pass
        # refresh_bindings() does not live-rekey in Textual 8.2.7:
        self.app.notify("Shortcuts saved — restart the TUI to apply the new keys.",
                        severity="information", timeout=4)
        self.dismiss(None)

    def _would_collide(self, scope, action_id, candidate_key) -> str | None:
        """Return the action_id already holding `candidate_key` in `scope`
        (excluding the row being edited), accounting for pending edits, else None."""
        for s, aid, default_key, _label in self._rows:
            if s != scope or aid == action_id:
                continue
            if self._effective_key(s, aid, default_key) == candidate_key:
                return aid
        return None
```

**Conflict policy (block-at-edit-time):** every rebind and every reset-to-default
runs `_would_collide` against the other effective in-scope keys first. A clash is
refused with a `notify(severity="error")` and the change is not applied — so the
pending set never contains an in-scope duplicate and `action_save` needs no
confirm. (Auto-resolving the blocked reset by cascading is deferred to t848_8.)
`_recompute_collisions` is kept **display-only**: it red-highlights any row whose
effective key duplicates another in-scope key — relevant only for a *pre-existing*
collision a user hand-wrote into `userconfig.yaml`.

Row-key lookup mirrors `syncer_app.py`:
`row_key, _ = table.coordinate_to_cell_key((table.cursor_row, 0))` then split
`row_key.value` on the space separator. `_default_for(scope, action_id)` reads
the default from `_DEFAULTS` (via the `self._rows` tuple already loaded).

### 4. Mixin wiring — `shortcuts_mixin.py`

Replace the stub body (keep the method name/signature):

```python
def action_open_shortcuts_editor(self) -> None:
    from shortcut_editor_modal import ShortcutEditorModal   # top-level import
    self.app.push_screen(ShortcutEditorModal(scope=self._shortcuts_scope))
```

The `getattr(self, "notify", ...)` guard and the "coming in t848_4" toast are
removed. `?` is only ever live at App level, so `self.app.push_screen` is safe.

### 5. `tests/test_shortcut_editor_modal.py` (Pilot-driven)

Mirror `tests/test_brainstorm_dag_op_keybinding.py`: `sys.path.insert` for
`.aitask-scripts` + `.aitask-scripts/lib`; a tiny `_HostApp(ShortcutsMixin, App)`
with `_shortcuts_scope="testscope"` and two `Binding`s; `chdir` into a tempdir
that contains `aitasks/metadata/userconfig.yaml` so persistence writes there;
`keybinding_registry._reset_for_tests()` in setUp.

Cases:
1. Press `?` → `ShortcutEditorModal` mounts; assert table rows match the
   registered bindings (scope + action_ids present).
2. Select a row (`pilot.press("enter")`), the `KeyCaptureScreen` mounts; send a
   new key (`pilot.press("o")`); assert the row's Key cell + Origin update.
3. Press `s` → assert `userconfig.yaml` now has
   `shortcuts: {testscope: {<action>: "o"}}` and the modal dismissed.
4. Re-open (`?`); assert Current key reads `o`, Origin `user`.
5. Press `d` (reset to default) then `s`; assert the override is removed from YAML.
6. **Rebind blocked on collision:** rebind row A to row B's current key; assert
   the change is *not* applied (A's Key cell unchanged), an error `notify` fired,
   and after `s` the YAML has no override for A.
7. **Reset-to-default blocked on collision:** set up A overridden to B's default
   key, then press `d` on B (reset B to its default); assert it's refused with the
   "Cannot reset … rebind that first" message and B's override is unchanged.
8. **`r` reverts** an unsaved rebind on a row (no YAML change after).
9. (Unit) `iter_scope_bindings` returns the scope's own + sub-scope + `shared`
   rows, sorted.

Some assertions (e.g. cell classes) are simplest via direct method calls on the
modal instance with mocked `app`/`dismiss` (the `test_stale_entry_modal.py`
style) where Pilot introspection is awkward — mix both styles as each case fits.

## Verification

```bash
python3 tests/test_shortcut_editor_modal.py            # or via the runner below
bash tests/run_all_python_tests.sh -k shortcut_editor  # pytest path
bash tests/test_keybinding_registry.sh
bash tests/test_shortcut_labels.sh
bash tests/test_shortcuts_registry_coverage.sh

# Manual smoke (defer aggregated checks to the t848_7 manual-verification sibling):
ait board        # press ? → editor opens, table filled with board / board.* / shared rows
                 # rebind a row → s → "restart to apply" toast; relaunch → key changed
ait brainstorm   # ? opens editor (H still opens op-help)
```

## Verification (for the t848_7 manual-verification sibling)

- `?` opens the editor in every TUI; the table shows that TUI's scope + its
  sub-scopes + `shared`.
- Rebind a visible action (e.g. board.detail → Pick); after relaunch the
  `(P)ick` label reflects the new key.
- `r` (reset pending) and `d` (clear override) behave distinctly; `s` persists.
- An in-scope collision highlights red and `s` requires confirmation.

## Notes for sibling tasks

- **t848_5 (Settings → Shortcuts tab):** `self.app.refresh_bindings()` is **not**
  sufficient for live re-keying in Textual 8.2.7 — the active key-map is built
  once at App init and not rebuilt from `BINDINGS`. The editor uses the
  restart-fallback notification. The Settings tab should set the same expectation
  (or implement a deliberate App-bindings rebuild if it wants live apply).
- `KeyCaptureScreen` applies **no** combo allow-list yet (only `escape`=cancel and
  bare-modifier suppression). t848_5's row editor can share an allow-list (e.g.
  reserve `ctrl+c`) — add it in `key_capture_screen.py` so both consume it.
- `iter_scope_bindings(prefix)` is the public registry getter for any
  scope-filtered binding view (the Settings tab can pass `""`-like logic or
  iterate `_DEFAULTS` for the global tree).

## Deferred follow-up — create sibling task t848_8 (cascade reset)

Per the design decision, t848_4 *blocks* a reset-to-default (or rebind) that would
collide within a scope. The richer resolution is a new t848 child, created during
this task's implementation via `aitask_create.sh --parent 848` (depends on
`t848_4`), with a description covering:

- When a reset-to-default would put a binding back onto a key currently held by
  another in-scope action, offer a **cascade**: also reset (or relocate) the
  conflicting binding, following the conflict chain until the scope is
  collision-free.
- Detect and break **cycles** (A↔B swaps) and present a **multi-row preview** of
  every binding the cascade will touch, with a single confirm before persisting.
- Surface the entry point from the editor (e.g. when `_would_collide` fires on a
  reset, offer "Resolve with cascade?" instead of only erroring).
- Reference files: `lib/shortcut_editor_modal.py` (this task),
  `lib/keybinding_registry.py` (`iter_scope_bindings`, `resolve_key`),
  `lib/shortcut_persist.py` (`save_override`/`clear_override`).

I will create this task (not implement it) as part of t848_4, and add it to the
parent's `children_to_implement`.

## Step 9 — Post-implementation

Standard child-task archival (Step 9 of task-workflow). Note: the new t848_8 is a
*pending* sibling, not part of this task's archival.
