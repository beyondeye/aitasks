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

This module also owns the *global* ``shortcut_label_case`` user setting
(``upper`` | ``preserve``, default ``upper``) read from
``aitasks/metadata/userconfig.yaml``. It is resolved once (cached, mirroring
``keybinding_registry``'s overrides cache) and threaded into every
``render_label`` call so the wrapped mnemonic is uppercased (``E(X)port``)
or case-preserving (``E(x)port``) across every TUI from one place. The
``shortcut_labels`` renderer stays config-free; the config dependency lives
here.
"""

from __future__ import annotations

from pathlib import Path

from textual.binding import Binding

from config_utils import load_yaml_config
from keybinding_registry import register_app_bindings, resolve_key
from shortcut_labels import render_label


# Cached resolution of the global ``shortcut_label_case`` setting.
# None = not loaded yet; True = uppercase the mnemonic (default);
# False = preserve the matched character's case.
_LABEL_CASE_CACHE: bool | None = None


def _resolve_uppercase_key() -> bool:
    """Return whether wrapped mnemonics should be uppercased (global setting).

    Reads ``shortcut_label_case`` from ``userconfig.yaml`` once and caches it.
    Only the literal value ``preserve`` flips the default; anything else
    (missing, ``upper``, garbage) keeps the back-compatible uppercase behavior.
    Fail-soft: a malformed (gitignored) userconfig must not crash every TUI at
    label-render time, so any read/parse error degrades to uppercase.
    """
    global _LABEL_CASE_CACHE
    if _LABEL_CASE_CACHE is not None:
        return _LABEL_CASE_CACHE
    try:
        cfg = load_yaml_config(Path("aitasks/metadata/userconfig.yaml"))
        value = str(cfg.get("shortcut_label_case", "upper")).strip().lower()
    except Exception:
        value = "upper"
    _LABEL_CASE_CACHE = value != "preserve"
    return _LABEL_CASE_CACHE


def refresh_label_case() -> None:
    """Drop the cached ``shortcut_label_case`` so the next read re-loads.

    Mirrors ``keybinding_registry.refresh``; call after editing the setting
    (and from tests that mutate userconfig.yaml).
    """
    global _LABEL_CASE_CACHE
    _LABEL_CASE_CACHE = None


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
        return render_label(
            text, key, style=style, uppercase_key=_resolve_uppercase_key()
        )

    def action_open_shortcuts_editor(self) -> None:
        # Top-level import name: .aitask-scripts/lib/ is on sys.path, so modules
        # there import as bare names (not package-relative).
        from shortcut_editor_modal import ShortcutEditorModal

        # Eagerly register this TUI's modal sub-scopes (e.g. board.detail) and
        # the shared dialogs (shared.*) so the editor lists them up front, not
        # only after the user has opened each modal once. Filtered + fail-soft;
        # guarded so the one-time module load happens at most once per instance.
        if not getattr(self, "_subscopes_registered", False):
            try:
                import shortcut_scopes

                shortcut_scopes.register_scope_bindings(self._shortcuts_scope)
            except Exception:
                pass  # fail-soft: editor still lists already-registered scopes
            self._subscopes_registered = True

        self.app.push_screen(ShortcutEditorModal(scope=self._shortcuts_scope))


def get_label(scope: str, action_id: str, text: str, *, style: str = "wrap") -> str:
    """Render ``text`` annotated with the active key for ``(scope, action_id)``."""
    key = resolve_key(scope, action_id) or ""
    return render_label(
        text, key, style=style, uppercase_key=_resolve_uppercase_key()
    )


def render_label_cfg(text: str, key: str, *, style: str = "wrap") -> str:
    """Config-aware ``render_label`` for callsites with a literal key.

    Use when a callsite passes a literal shortcut key (not a registry
    ``(scope, action_id)``) but still needs the global ``shortcut_label_case``
    setting applied — e.g. static button labels outside a ``ShortcutsMixin``.
    """
    return render_label(
        text, key, style=style, uppercase_key=_resolve_uppercase_key()
    )


def register_shared_bindings() -> None:
    """Register the App-level ``?`` editor binding under the global ``shared`` scope.

    Mirrors ``tui_switcher.py``'s module-level shared registration of ``j``.
    Because ``?`` is the same binding spliced into every App via
    ``SHORTCUTS_MIXIN_BINDINGS``, recording it under ``shared`` makes the t848_4
    shortcut editor list it once (under ``shared``), and the shared-action
    de-dup in ``register_app_bindings`` resolves each App's ``?`` from the shared
    scope — so a rebind there applies in every TUI.

    Idempotent. Runs once at import (below); tests that call
    ``keybinding_registry._reset_for_tests()`` must call this again to restore it.
    """
    register_app_bindings("shared", ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS)


# Register at import so `("shared", "open_shortcuts_editor")` is in the registry
# before any App's ShortcutsMixin.__init__ runs (every App module imports this
# module at import time, before instantiation) — that ordering is what lets the
# shared-action de-dup fire when each App registers its own bindings.
register_shared_bindings()
