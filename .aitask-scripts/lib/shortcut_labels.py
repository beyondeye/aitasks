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


def render_label(text: str, key: str, *, style: str = "wrap") -> str:
    """Render ``text`` annotated with shortcut ``key`` in the chosen ``style``.

    ``style="wrap"``:
      * empty key -> ``text``
      * single char in text (case-insensitive, first occurrence anywhere
        including mid-word): wrap that char in parens uppercased.
      * single char not in text: prefix ``(K) text``.
      * multi-key combo: prefix ``(Display) text``.

    ``style="leading"``:
      * empty key -> ``text``
      * single char == first letter of text (case-insensitive):
        ``k text`` (lowercase key + space + original-case text).
      * single char != first letter (or absent): ``k · text``.
      * multi-key combo: ``Display · text``.
    """
    if not key:
        return text
    if style == "wrap":
        return _render_wrap(text, key)
    if style == "leading":
        return _render_leading(text, key)
    raise ValueError(f"unknown render_label style: {style!r}")


def _render_wrap(text: str, key: str) -> str:
    if _is_multi_key(key):
        return f"({display_form(key)}) {text}"
    # Single-char key: search case-insensitively for first occurrence.
    target = key.lower()
    for i, ch in enumerate(text):
        if ch.lower() == target:
            return f"{text[:i]}({ch.upper()}){text[i + 1:]}"
    return f"({key.upper()}) {text}"


def _render_leading(text: str, key: str) -> str:
    if _is_multi_key(key):
        return f"{display_form(key)}{_LEADING_DOT_SEP}{text}"
    if text and text[0].lower() == key.lower():
        return f"{key.lower()} {text}"
    return f"{key.lower()}{_LEADING_DOT_SEP}{text}"
