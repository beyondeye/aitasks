"""Pure functions for rendering TUI labels with their active shortcut key.

Two styles, callsite-selected:

- ``"wrap"`` — used for button labels. The key is inlined into the
  label text where possible (``Pick`` + ``p`` -> ``(P)ick``), falling
  back to a parenthesised prefix when no match exists (``New Task`` +
  ``0`` -> ``(0) New Task``).

- ``"leading"`` — used for inline filter labels (``ViewSelector``).
  When the key is the first letter of the text the rendering matches
  the pre-t848 convention ``l Locked``; when it isn't, the function
  falls back to a middle-dot separator ``o · Locked`` so the active
  key is still visible.

The ``wrap`` style uppercases the matched in-text character by default
(``Export`` + ``x`` -> ``E(X)port``). Pass ``uppercase_key=False`` to
preserve the matched character's actual case (``E(x)port``); this is
driven globally by the ``shortcut_label_case`` user setting, resolved in
``shortcuts_mixin`` (this module stays config-free and parameter-driven).

No Textual dependency.
"""

from __future__ import annotations

_MULTI_KEY_SEPARATOR = "+"
_LEADING_DOT_SEP = " · "


def _is_multi_key(key: str) -> bool:
    return _MULTI_KEY_SEPARATOR in key or len(key) > 1


def display_form(key: str) -> str:
    """Pretty-print a Textual binding key for inclusion in a label.

    ``ctrl+r`` -> ``Ctrl+R``; ``a`` -> ``A``; ``escape`` -> ``Escape``.
    """
    if not key:
        return ""
    parts = key.split(_MULTI_KEY_SEPARATOR)
    return _MULTI_KEY_SEPARATOR.join(p.capitalize() if p.isalpha() else p.upper() for p in parts)


def render_label(
    text: str, key: str, *, style: str = "wrap", uppercase_key: bool = True
) -> str:
    """Render ``text`` annotated with shortcut ``key`` in the chosen ``style``.

    ``style="wrap"``:
      * empty key -> ``text``
      * single char in text (case-insensitive, first occurrence anywhere
        including mid-word): wrap that char in parens. Uppercased when
        ``uppercase_key`` (default), otherwise the matched character's
        original case is preserved.
      * single char not in text: prefix ``(K) text``.
      * multi-key combo: prefix ``(Display) text``.

    ``style="leading"``:
      * empty key -> ``text``
      * single char == first letter of text (case-insensitive):
        ``k text`` (lowercase key + space + original-case text).
      * single char != first letter (or absent): ``k · text``.
      * multi-key combo: ``Display · text``.

    ``uppercase_key`` governs only the matched-in-text character of the
    ``wrap`` style. The no-match prefix, multi-key display form, and the
    ``leading`` style are unaffected.
    """
    if not key:
        return text
    if style == "wrap":
        return _render_wrap(text, key, uppercase_key)
    if style == "leading":
        return _render_leading(text, key)
    raise ValueError(f"unknown render_label style: {style!r}")


def _render_wrap(text: str, key: str, uppercase_key: bool = True) -> str:
    if _is_multi_key(key):
        return f"({display_form(key)}) {text}"
    # Single-char key: search case-insensitively for first occurrence.
    target = key.lower()
    for i, ch in enumerate(text):
        if ch.lower() == target:
            glyph = ch.upper() if uppercase_key else ch
            return f"{text[:i]}({glyph}){text[i + 1:]}"
    return f"({key.upper()}) {text}"


def _render_leading(text: str, key: str) -> str:
    if _is_multi_key(key):
        return f"{display_form(key)}{_LEADING_DOT_SEP}{text}"
    if text and text[0].lower() == key.lower():
        return f"{key.lower()} {text}"
    return f"{key.lower()}{_LEADING_DOT_SEP}{text}"
