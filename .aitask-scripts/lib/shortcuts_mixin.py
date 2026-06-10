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

from textual.binding import Binding

from config_utils import load_yaml_config
from keybinding_registry import register_app_bindings, resolve_key
from shortcut_labels import render_label
from userconfig_persist import _userconfig_path


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
        cfg = load_yaml_config(_userconfig_path())
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
        default_bindings = self.BINDINGS
        self.BINDINGS = register_app_bindings(
            self._shortcuts_scope, default_bindings
        )
        self._relink_live_bindings(default_bindings, self.BINDINGS)

    def _relink_live_bindings(self, defaults, overridden) -> None:
        """Move remapped keys into the live keymap Textual built from defaults.

        Textual copies the class-level ``_merged_bindings`` (computed from the
        *default* keys at class-definition time) into ``self._bindings`` during
        ``super().__init__()``. Because we substitute override keys into
        ``self.BINDINGS`` *after* that copy, the live keymap would otherwise
        keep firing the default key — overrides reach the editor row / registry
        / footer hint / tab title but pressing the new key does nothing. For
        each binding whose key was remapped, move it from its default key to
        its override key in ``self._bindings`` so the new key fires, without
        disturbing the framework bindings (quit, command palette, screen
        tab-nav, ...) that live alongside in the same map and are absent from
        ``self.BINDINGS``.

        ``register_app_bindings`` returns exactly one entry per input binding,
        in order, so ``defaults`` and ``overridden`` align by index.
        """
        live = getattr(self, "_bindings", None)
        if live is None:  # defensive: non-DOMNode use (tests / future scopes)
            return
        mapping = live.key_to_bindings
        for default_b, active_b in zip(defaults, overridden):
            old_key = getattr(default_b, "key", None)
            new_key = getattr(active_b, "key", None)
            action = getattr(active_b, "action", None)
            if not old_key or not new_key or old_key == new_key:
                continue
            bucket = mapping.get(old_key)
            if bucket is not None:
                # Drop only this action's binding from the default key; a
                # second action sharing that key keeps its live entry.
                remaining = [
                    b for b in bucket if getattr(b, "action", None) != action
                ]
                if remaining:
                    mapping[old_key] = remaining
                else:
                    del mapping[old_key]
            mapping.setdefault(new_key, []).append(active_b)

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
