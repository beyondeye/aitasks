"""In-TUI shortcut editor modal (t848_4).

Pushed by ``ShortcutsMixin.action_open_shortcuts_editor`` when the user presses
``?`` in any TUI. Shows every binding registered under the active scope (plus its
modal sub-scopes and the global ``shared`` scope), and lets the user rebind a key,
revert an unsaved edit, or reset a binding to its default — persisting overrides
to ``aitasks/metadata/userconfig.yaml`` via ``shortcut_persist``.

Conflict policy: a rebind or reset-to-default that would collide with another key
*within the same scope* is blocked at edit time with an error toast, so the
pending set is always collision-free and saving never produces a duplicate.
Auto-resolving a blocked reset by cascading is a separate task (t848_8).

This modal carries its own ``DEFAULT_CSS`` (per ``feedback_modal_self_contained_css``)
and intentionally does NOT use ``ShortcutsMixin`` — its own ``r``/``d``/``s``/Esc
keys are not user-customizable, so they must not register into the editable
registry.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Label

import keybinding_registry
import shortcut_persist
from key_capture_screen import KeyCaptureScreen
from userconfig_persist import MalformedUserConfigError

# Pending-edit sentinel: "clear this override on save (revert to default)".
_CLEAR = object()


class ShortcutEditorModal(ModalScreen[None]):
    """Edit the shortcut bindings visible from one TUI scope."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("r", "revert_row", "Revert edit"),
        Binding("d", "reset_default", "Reset to default"),
        Binding("s", "save", "Save"),
    ]

    DEFAULT_CSS = """
    ShortcutEditorModal {
        align: center middle;
    }
    #shortcut_editor_dialog {
        width: 90%;
        max-width: 110;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        border: thick $accent;
        background: $surface;
    }
    #se_title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
    }
    #se_help {
        color: $text-muted;
        width: 100%;
        margin-bottom: 1;
    }
    #se_table {
        height: auto;
        max-height: 70%;
    }
    """

    def __init__(self, scope: str) -> None:
        super().__init__()
        self._scope = scope
        # rows: list of (scope, action_id, default_key, label)
        self._rows = keybinding_registry.iter_scope_bindings(scope)
        self._defaults = {(s, a): dk for s, a, dk, _ in self._rows}
        # pending edits keyed by (scope, action_id) -> new_key:str | _CLEAR
        self._pending: dict[tuple[str, str], object] = {}

    # ------------------------------------------------------------------ compose
    def compose(self) -> ComposeResult:
        with Container(id="shortcut_editor_dialog"):
            yield Label(f"Shortcuts — {self._scope}", id="se_title")
            yield Label(
                "Enter: rebind  •  r: revert edit  •  d: reset to default  "
                "•  s: save  •  Esc: cancel",
                id="se_help",
            )
            yield DataTable(id="se_table", cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#se_table", DataTable)
        table.add_columns("Scope", "Action", "Key", "Default", "Label", "Origin")
        self._refresh_table()
        table.focus()

    # -------------------------------------------------------------- table build
    def _refresh_table(self) -> None:
        table = self.query_one("#se_table", DataTable)
        # Preserve cursor position across a rebuild.
        cursor = table.cursor_row
        table.clear(columns=False)
        colliding = self._colliding_pairs()
        for scope, action_id, default_key, label in self._rows:
            table.add_row(
                *self._row_cells(scope, action_id, default_key, label, colliding),
                key=self._row_key(scope, action_id),
            )
        if table.row_count:
            table.move_cursor(row=min(cursor or 0, table.row_count - 1))

    def _row_cells(self, scope, action_id, default_key, label, colliding):
        eff = self._effective_key(scope, action_id, default_key)
        key_cell = (
            Text(eff, style="bold red")
            if (scope, action_id) in colliding
            else eff
        )
        return (
            scope,
            action_id,
            key_cell,
            default_key,
            label,
            self._origin(scope, action_id),
        )

    # ---------------------------------------------------------------- key state
    @staticmethod
    def _row_key(scope: str, action_id: str) -> str:
        # action_ids are identifiers and scopes are dotted, so a space never
        # appears inside either — safe to split on the first space.
        return f"{scope} {action_id}"

    def _effective_key(self, scope, action_id, default_key) -> str:
        if (scope, action_id) in self._pending:
            pend = self._pending[(scope, action_id)]
            return default_key if pend is _CLEAR else pend
        return keybinding_registry.resolve_key(scope, action_id) or default_key

    def _origin(self, scope, action_id) -> str:
        if (scope, action_id) in self._pending:
            return "pending"
        overrides = keybinding_registry.load_user_overrides().get(scope, {})
        return "user" if action_id in overrides else "default"

    def _default_for(self, scope, action_id) -> str:
        return self._defaults.get((scope, action_id), "")

    def _cursor_key(self) -> tuple[str, str] | None:
        table = self.query_one("#se_table", DataTable)
        if table.cursor_row is None or table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key((table.cursor_row, 0))
        if row_key.value is None:
            return None
        scope, action_id = str(row_key.value).split(" ", 1)
        return scope, action_id

    def _would_collide(self, scope, action_id, candidate_key) -> str | None:
        """Return the action_id already holding ``candidate_key`` in ``scope``
        (excluding the row being edited), accounting for pending edits."""
        for s, aid, default_key, _ in self._rows:
            if s != scope or aid == action_id:
                continue
            if self._effective_key(s, aid, default_key) == candidate_key:
                return aid
        return None

    def _colliding_pairs(self) -> set[tuple[str, str]]:
        """(scope, action_id) pairs whose effective key duplicates another in
        the same scope — for display-only red highlighting (pre-existing
        hand-edited collisions; new ones are blocked at edit time)."""
        by_scope: dict[str, dict[str, list[str]]] = {}
        for s, aid, dk, _ in self._rows:
            by_scope.setdefault(s, {}).setdefault(
                self._effective_key(s, aid, dk), []
            ).append(aid)
        out: set[tuple[str, str]] = set()
        for s, key_map in by_scope.items():
            for aids in key_map.values():
                if len(aids) > 1:
                    out.update((s, aid) for aid in aids)
        return out

    # ------------------------------------------------------------- rebind flow
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value is None:
            return
        scope, action_id = str(event.row_key.value).split(" ", 1)
        self.app.push_screen(
            KeyCaptureScreen(),
            lambda key: self._apply_capture(scope, action_id, key),
        )

    def _apply_capture(self, scope: str, action_id: str, key) -> None:
        if key is None:
            return
        clash = self._would_collide(scope, action_id, key)
        if clash is not None:
            self.app.notify(
                f"'{key}' is already bound to '{clash}' in {scope}.",
                severity="error",
                timeout=4,
            )
            return
        self._pending[(scope, action_id)] = key
        self._refresh_table()

    # --------------------------------------------------------------- r / d / s
    def action_revert_row(self) -> None:
        rk = self._cursor_key()
        if rk is None:
            return
        if rk in self._pending:
            del self._pending[rk]
            self._refresh_table()

    def action_reset_default(self) -> None:
        rk = self._cursor_key()
        if rk is None:
            return
        scope, action_id = rk
        default_key = self._default_for(scope, action_id)
        clash = self._would_collide(scope, action_id, default_key)
        if clash is not None:
            self.app.notify(
                f"Cannot reset: default key '{default_key}' is already bound to "
                f"'{clash}' in {scope}. Rebind that first.",
                severity="error",
                timeout=5,
            )
            return
        self._pending[(scope, action_id)] = _CLEAR
        self._refresh_table()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        # Pending is collision-free by construction, so save unconditionally.
        touched: set[str] = set()
        try:
            for (scope, action_id), pend in self._pending.items():
                default_key = self._default_for(scope, action_id)
                if pend is _CLEAR or pend == default_key:
                    shortcut_persist.clear_override(scope, action_id)
                else:
                    shortcut_persist.save_override(scope, action_id, str(pend))
                touched.add(scope)
        except MalformedUserConfigError as exc:
            # Each writer reads the whole file before writing, so a malformed
            # userconfig.yaml raises before anything is persisted — nothing is
            # half-written. Surface the error and keep the modal open with the
            # pending edits intact so the user can fix the file and retry (or
            # cancel) instead of silently overwriting their config.
            self.app.notify(
                f"Cannot save shortcuts: {exc}. "
                "Fix or delete userconfig.yaml, then retry.",
                severity="error",
                timeout=8,
            )
            return
        for scope in touched:
            keybinding_registry.refresh(scope)
        # refresh_bindings() refreshes enabled-state/footer but does NOT rebuild
        # the active key-map from BINDINGS in Textual 8.x, so the new keys take
        # full effect on next launch — surface that to the user.
        try:
            self.app.refresh_bindings()
        except Exception:
            pass
        self.app.notify(
            "Shortcuts saved — restart the TUI to apply the new keys.",
            severity="information",
            timeout=4,
        )
        self.dismiss(None)
