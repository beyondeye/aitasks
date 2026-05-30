"""Mixin + helper for Textual classes that opt into customisable shortcuts.

A class (App / Screen / ModalScreen / Static-with-BINDINGS) that wants
its bindings registered under a scope, its keys remapped from
``aitasks/metadata/userconfig.yaml``, and its labels rendered with the
active shortcut key should:

* Subclass ``ShortcutsMixin`` and set ``_shortcuts_scope = "<scope>"``.
* In the case of an ``App`` it MAY splice
  ``*ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS`` into its ``BINDINGS``
  class attr to expose the ``?`` shortcut-editor binding. Modal/Screen
  subclasses must NOT splice — the editor binding is owned at App
  level only.

Module-level ``get_label`` is provided for callsites that don't have a
``ShortcutsMixin`` instance available (e.g. custom widgets that render
labels from a parent app's scope).
"""

from __future__ import annotations

from textual.binding import Binding

from keybinding_registry import register_app_bindings, resolve_key
from shortcut_labels import render_label


class ShortcutsMixin:
    _shortcuts_scope: str = ""

    SHORTCUTS_MIXIN_BINDINGS = [
        Binding("?", "open_shortcuts_editor", "Keys"),
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not self._shortcuts_scope:
            raise RuntimeError(
                "ShortcutsMixin subclass must set _shortcuts_scope"
            )
        self.BINDINGS = register_app_bindings(
            self._shortcuts_scope, self.BINDINGS
        )

    def label(self, action_id: str, text: str, *, style: str = "wrap") -> str:
        key = resolve_key(self._shortcuts_scope, action_id) or ""
        return render_label(text, key, style=style)

    def action_open_shortcuts_editor(self) -> None:
        # Top-level import name: .aitask-scripts/lib/ is on sys.path, so modules
        # there import as bare names (not package-relative).
        from shortcut_editor_modal import ShortcutEditorModal

        self.app.push_screen(ShortcutEditorModal(scope=self._shortcuts_scope))


def get_label(scope: str, action_id: str, text: str, *, style: str = "wrap") -> str:
    """Render ``text`` annotated with the active key for ``(scope, action_id)``."""
    key = resolve_key(scope, action_id) or ""
    return render_label(text, key, style=style)
