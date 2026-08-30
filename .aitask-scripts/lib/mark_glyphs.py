#!/usr/bin/env python3
"""The ONE authority for the repo's multi-select mark glyph and its colours (t1638).

CODEPOINT POLICY. A glyph is admissible here only if **(a)** every family in
:data:`SUPPORTED_FONTS` covers it, and **(b)** no emoji font claims the
codepoint. Both halves are enforced executably by
``tests/test_mark_glyphs_single_source.py``; neither is a style preference.

Rule (b) is the t1638 defect, and it is worth stating precisely because the
obvious replacement glyph fails it too. `☑` U+2611 is covered by *no* supported
Nerd Font, so fontconfig resolves it by fallback — and rank 2 of that fallback
chain is Noto Color Emoji. A colour-bitmap glyph ignores the requested
foreground entirely, so the mark painted its own dark colours on a dark
background and vanished. `☐` U+2610 has no emoji coverage, ranks the emoji font
last, and therefore kept honouring `#6272A4`; that asymmetry was the whole bug.

  * `✔` U+2714 was **REJECTED** as the replacement: it resolves to
    `Adwaita Mono -> Noto Color Emoji` exactly like `☑`, so it reintroduces the
    identical defect. (It is also absent from CaskaydiaMono NF.) The task that
    produced this module proposed it; measurement overruled the proposal.
  * U+FE0E (VS15, the text-presentation selector) was **REJECTED**: it is in
    neither supported font's cmap, so honouring it is a property of the
    terminal's shaper. That is the same unverifiable environment-dependence this
    module exists to remove, and it cannot be pinned by any in-repo test.

SCOPE. This module governs the multi-select mark only. The rest of the TUI
glyph inventory has not been measured against the policy above, and the t1638
measurement found confirmed violations already shipping — notably `✔` U+2714 in
the board's by-trail entries, which is this exact defect. Do not assume a glyph
elsewhere in the repo satisfies this policy merely because this module exists.

**t1639 supersedes the selection rule below.** Choosing codepoints from the
intersection of every supported font optimises for coverage and pays for it in
shape — `✓`/`□` is a tick beside a square where `☑`/`☐` was a checkbox and its
empty twin. t1639 introduces a declared glyph tier defaulting to the Nerd Font
Private Use Area (`U+F046`/`U+F096`), which carries the real shapes and is
structurally immune to this defect because nothing but icon fonts claims the
PUA. The glyphs below become the `unicode` fallback tier, not the only answer.

ACCEPTED RESIDUAL. `□` U+25A1 is East Asian Width *Ambiguous*, where the `☐` it
replaces was *Neutral* — a terminal configured wide-ambiguous renders it in two
cells while Rich budgets one. This was chosen deliberately over the narrow-safe
`▫` U+25AB, and it is the same exposure the repo already carries for `●` and `◆`
on the very same monitor rows. Recorded, not overlooked; pinned by
``test_every_ratified_glyph_is_single_cell``.

Deliberately **import-free at module level** (cf. ``followup_kinds``): the board
imports lib/ modules on the PyPy fast path, and the drift guard must be able to
import this without pulling in Rich or Textual. :func:`rich_mark_style` imports
Rich inside the function body, for the one caller that needs a ``Style`` object.
"""

from __future__ import annotations

# --- Glyphs -----------------------------------------------------------------

#: The multi-select mark: "included in this multi-item action" (t1004). Shown
#: always — an empty box signals "selectable but unselected", which a blank or a
#: dot does not. Do not collapse this into the monitor's ``★``/``☆``
#: prioritised-agent mark; ``monitor_shared.format_mark_glyph`` records why the
#: two vocabularies are kept apart.
MARK_CHECKED = "✓"    # ✓ CHECK MARK
MARK_UNCHECKED = "□"  # □ WHITE SQUARE

# --- Colours ----------------------------------------------------------------

#: Dracula "Yellow" / "Gray" — the same two entries as
#: ``lib/board_columns.py::PALETTE_COLORS``. Restated rather than indexed out of
#: that list on purpose: ``PALETTE_COLORS`` is a USER-FACING picker whose order
#: is presentation, so deriving a semantic colour from a picker index would let
#: a reorder repaint every mark in the repo. The agreement is asserted instead —
#: see ``tests/test_markup_colour_contract.py::RatifiedStylesTests``.
#:
#: A HEX, not the bare name ``yellow``. Rich resolves ``yellow`` to ``#808000``
#: (the ANSI-3 olive) while Textual resolves it to ``#FFFF00``, so the DAG's
#: Rich ``Style`` and the three Textual-markup call sites had been painting
#: DIFFERENT colours ever since t1004 unified the glyph. An ANSI name also
#: remaps per theme and is unpinnable in a test (cf. ``TUI_RUNNING_STYLE`` in
#: ``tui_switcher``).
#:
#: This does NOT establish a repo-wide "no bare ANSI names" rule.
#: ``monitor_shared.STATE_STYLE_IDLE``/``_ACTIVE`` stay ``yellow``/``green`` by
#: decision — repainting the agent-state ladder is a different change.
MARK_CHECKED_COLOUR = "#F1FA8C"
MARK_UNCHECKED_COLOUR = "#6272A4"

#: Markup style tokens (Textual/Rich ``[...]`` bodies), derived from the colours
#: above so the pair can never drift apart.
MARK_CHECKED_STYLE = f"bold {MARK_CHECKED_COLOUR}"
MARK_UNCHECKED_STYLE = MARK_UNCHECKED_COLOUR

# --- Coverage scope ---------------------------------------------------------

#: The font families this repo's glyph vocabulary is VERIFIED against.
#:
#: Nothing in the repo declared this before t1638 — "the supported Nerd Fonts"
#: was an unwritten assumption, which is precisely how a codepoint covered by
#: none of them became the convention. The coverage claim is therefore exactly
#: as broad as this tuple and no broader: a deployment on some third font is
#: unverified by construction. Extending it is one entry here plus a
#: regeneration of ``tests/data/font_coverage.json``.
SUPPORTED_FONTS = ("JetBrainsMono Nerd Font", "CaskaydiaMono Nerd Font")

#: Why each ratified glyph survives font fallback — the recorded evidence a
#: future change has to contend with, rather than rediscover. Pinned non-empty
#: by ``test_glyph_evidence_is_recorded``; the coverage half of each claim is
#: independently machine-checked against ``tests/data/font_coverage.json``.
GLYPH_EVIDENCE = {
    MARK_CHECKED: (
        "U+2713 CHECK MARK: covered by every family in SUPPORTED_FONTS, and no "
        "emoji font claims it. The strongest candidate measured — fontconfig "
        "rank 1 is the primary terminal font itself, so it never falls back at "
        "all. EAW Neutral."
    ),
    MARK_UNCHECKED: (
        "U+25A1 WHITE SQUARE: covered by every family in SUPPORTED_FONTS, "
        "Geometric Shapes, no emoji property. EAW Ambiguous — see the accepted "
        "residual in the module docstring."
    ),
}


# --- Accessors --------------------------------------------------------------


def mark_glyph(marked: bool) -> str:
    """The bare glyph for a mark state, with no styling."""
    return MARK_CHECKED if marked else MARK_UNCHECKED


def mark_style(marked: bool) -> str:
    """The bare markup style token, for callers composing their own tag."""
    return MARK_CHECKED_STYLE if marked else MARK_UNCHECKED_STYLE


def mark_markup(marked: bool) -> str:
    """The mark as ready-to-render Textual/Rich markup, e.g. ``[bold #F1FA8C]✓[/]``.

    **This is the rendering entry point.** Call sites must not compose the tag
    themselves: a hand-rolled ``f"[bold yellow]{MARK_CHECKED}[/]"`` sources the
    glyph correctly while re-forking the colour, which is exactly the drift
    ``tests/test_mark_glyphs_single_source.py`` Rule 4 forbids.

    No trailing separator: the DAG box and the concern rows use different ones,
    so that spacing is a layout decision belonging to the call site.
    """
    return f"[{mark_style(marked)}]{mark_glyph(marked)}[/]"


def rich_mark_style(marked: bool):
    """The mark's style as a :class:`rich.style.Style`, for ``Text``-based rows.

    Rich is imported here rather than at module scope so this module stays free
    of heavy imports for the board's fast path, and so the drift guard can
    import it with no third-party dependency available.
    """
    from rich.style import Style

    if marked:
        return Style(color=MARK_CHECKED_COLOUR, bold=True)
    return Style(color=MARK_UNCHECKED_COLOUR)
