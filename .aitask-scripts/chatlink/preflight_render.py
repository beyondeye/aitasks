"""Shared plain-text rendering for preflight check rows (t1149_3).

Textual-free on purpose: both the ``ait chatlink`` status panel
(``chatlink_app.py``) and the config wizard's summary screen
(``wizard.py``) render :class:`chatlink.preflight.CheckResult` rows with
the same glyphs, and ``chatlink_app.py`` imports ``wizard.py`` — so the
shared formatter lives here rather than on ``ChatlinkApp`` (which would
be a circular import for the wizard).
"""
from __future__ import annotations

from . import preflight

#: Severity glyphs — plain text prefixes (render-level assertable).
SEVERITY_GLYPHS = {preflight.PASS: "✓", preflight.WARN: "!",
                   preflight.FAIL: "✗"}


def format_row(res: preflight.CheckResult) -> str:
    """One checklist line: severity glyph + message, with the fix hint
    appended on non-pass rows."""
    glyph = SEVERITY_GLYPHS.get(res.severity, "?")
    line = f"{glyph} {res.message}"
    if res.severity != preflight.PASS and res.fix_hint:
        line += f" — {res.fix_hint}"
    return line
