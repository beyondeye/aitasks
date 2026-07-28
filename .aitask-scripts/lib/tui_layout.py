"""Canonical terminal-width tiers for aitasks Textual TUIs.

Single Python source of truth for "how wide is this terminal?" — the question a
TUI asks when it picks a layout, not the question a widget asks about itself.

SCOPE — tiers, not component minimums. A *component minimum width* ("this widget
needs N cells to be usable", e.g. ``KanbanApp.FILTER_SEARCH_MIN_WIDTH`` or
``CodeBrowserApp.CODE_MIN_WIDTH``) is a property of that widget and deliberately
stays with it. Do not move such constants here, and do not reuse these tier
values as a component floor just because the numbers happen to match today —
``CODE_MIN_WIDTH`` is 80 by coincidence, not by derivation.

Branch on :func:`terminal_tier` / :func:`is_narrow_terminal` rather than
comparing against the raw ints: the functions resolve the module globals at call
time, so the numeric comparison exists at exactly one place in the repo.

Rationale, the full inventory of width constants that deliberately stayed put,
and the rule for adding a new TUI: ``aidocs/framework/tui_conventions.md``,
section "Terminal-width tiers vs component minimum widths".
"""

NARROW_TERMINAL_WIDTH = 80    # below this, a terminal is NARROW
WIDE_TERMINAL_WIDTH = 120     # at or above this, a terminal is WIDE

NARROW = "narrow"
NORMAL = "normal"
WIDE = "wide"

TIERS = (NARROW, NORMAL, WIDE)  # narrow-to-wide


def terminal_tier(width: int) -> str:
    """Return NARROW / NORMAL / WIDE for a terminal of ``width`` cells."""
    if width >= WIDE_TERMINAL_WIDTH:
        return WIDE
    if width >= NARROW_TERMINAL_WIDTH:
        return NORMAL
    return NARROW


def is_narrow_terminal(width: int) -> bool:
    """Return True when ``width`` falls in the NARROW tier."""
    return terminal_tier(width) == NARROW
