"""Width-adaptive multi-row footer shared by every framework TUI.

Textual's ``Footer`` is a single ``height: 1`` horizontal strip whose overflow is
reachable only by horizontal *mouse-wheel* scroll — a keyboard user has no way to
learn that a key exists. The board declares 27 shown bindings totalling ~385
columns of label text, so a third of its footer is off-screen even on a
200-column terminal.

CSS alone cannot fix it: ``Footer.compose()`` ends with
``self.styles.grid_size_columns = len(action_to_bindings)``, so a subclass that
merely switches to a grid layout still gets exactly one row. The layout has to be
re-asserted *after* ``super().compose()`` runs, and has to survive the recompose
that ``bindings_changed`` triggers on every ``bindings_updated`` signal.

``MultiRowFooter`` reflows the real ``FooterKey`` / ``KeyGroup`` / ``FooterLabel``
widgets that ``Footer.compose()`` produced into packed rows. Reflowing upstream's
own widgets — rather than re-deriving the bindings — keeps every piece of upstream
machinery working for free: ``screen.active_bindings`` (so ``check_action`` gating
still hides/disables keys), ``FooterKey.on_mouse_down`` click-to-fire, key-display
resolution via ``app.get_key_display``, the ``bindings_updated`` recompose
subscription, and the ``-command-palette`` key.

Dependencies are limited to ``textual`` + ``rich`` + stdlib + the two ``lib/``
config helpers, so this module imports cleanly under both PyPy (the board's fast
path) and CPython (the test suite).
"""

from __future__ import annotations

from rich.cells import cell_len
from textual.compose import compose as _textual_compose
from textual.containers import HorizontalGroup
from textual.widgets import Footer, Static
from textual.widgets._footer import FooterKey, FooterLabel, KeyGroup

from config_utils import load_yaml_config
from userconfig_persist import _userconfig_path

#: Rows the footer may grow to before it starts dropping keys. 3 is the smallest
#: value that shows every board binding on a 200-column terminal; 1 restores the
#: stock single-row behavior (with an honest overflow hint instead of silent
#: clipping).
DEFAULT_MAX_ROWS = 3
MIN_MAX_ROWS = 1
MAX_MAX_ROWS = 6

#: Cached resolution of the global ``footer_max_rows`` setting.
#: None = not loaded yet.
_MAX_ROWS_CACHE: int | None = None


def _resolve_max_rows() -> int:
    """Return the configured row cap (global setting), reading it once.

    Reads ``footer_max_rows`` from ``userconfig.yaml`` and caches it, mirroring
    ``shortcuts_mixin._resolve_uppercase_key``. Fail-soft: a malformed
    (gitignored) userconfig must not crash every TUI at compose time, so any
    read/parse error — and any value that is not an integer in range — degrades
    to the default.
    """
    global _MAX_ROWS_CACHE
    if _MAX_ROWS_CACHE is not None:
        return _MAX_ROWS_CACHE
    try:
        config = load_yaml_config(_userconfig_path())
        raw = config.get("footer_max_rows", DEFAULT_MAX_ROWS)
        # YAML parses `footer_max_rows: true` as a bool, and bool is an int
        # subclass — int(True) would silently mean "1 row".
        if isinstance(raw, bool):
            raise TypeError("footer_max_rows must be a number, not a bool")
        value = int(raw)
    except Exception:
        value = DEFAULT_MAX_ROWS
    if not MIN_MAX_ROWS <= value <= MAX_MAX_ROWS:
        value = DEFAULT_MAX_ROWS
    _MAX_ROWS_CACHE = value
    return value


def refresh_max_rows() -> None:
    """Drop the cached ``footer_max_rows`` so the next read re-loads.

    Mirrors ``shortcuts_mixin.refresh_label_case``; call after editing the
    setting (and from tests that mutate userconfig.yaml).
    """
    global _MAX_ROWS_CACHE
    _MAX_ROWS_CACHE = None


class OverflowHint(Static):
    """`+N more (?)` affordance shown when the row cap forced keys out.

    A dedicated class (rather than a bare ``Static``) so ``footer_item_width``
    can tell it apart from a ``FooterLabel`` — both are ``Static`` subclasses.
    """


def _hint_width(text: str) -> int:
    """Columns an :class:`OverflowHint` occupies (its CSS is ``padding: 0 1``)."""
    return cell_len(text) + 2


def _format_hint(count: int, key_display: str | None) -> str:
    if key_display:
        return f"+{count} more ({key_display})"
    return f"+{count} more"


def footer_item_width(item, *, footer_compact: bool = False) -> int:
    """Columns one composed footer item occupies, margins included.

    The packing budget is ``outer_size.width + margin.left + margin.right``:
    ``outer_size`` excludes margins, and margins *collapse* between adjacent
    siblings, so neither can be ignored. Every text component is measured in
    **cells**, not characters — terminal columns are cells, so ``len()``
    undercounts each wide/CJK glyph by a column and the row silently overflows.

    Measured against textual 8.2.7 (``tests/test_multirow_footer.py`` pins each
    of these against the real laid-out geometry):

    ==============================  ===============================
    item                            width
    ==============================  ===============================
    plain ``FooterKey``             ``kd + desc + 3`` (2 if compact)
    ``-command-palette`` key        ``kd + desc + 3`` in both modes
    ``FooterLabel`` group caption   ``cap + 1`` (0 if compact)
    ``KeyGroup``, non-compact       ``sum(kd) + n + 1``
    ``KeyGroup``, compact           ``sum(kd) + 2``
    ==============================  ===============================
    """
    if isinstance(item, KeyGroup):
        # Grouped children carry description="", and FooterKey.render() skips
        # padding entirely on that branch, so the key display is the whole
        # content. Their `margin: 0 1` collapses between siblings, which is why
        # this is `n + 1` and not `2 * n`.
        inner = sum(
            cell_len(child.key_display)
            for child in item.children
            if isinstance(child, FooterKey)
        )
        if item.has_class("-compact"):
            return inner + 2
        return inner + len(item.children) + 1
    if isinstance(item, OverflowHint):
        return _hint_width(str(item.content))
    if isinstance(item, FooterLabel):
        return cell_len(str(item.content)) + (0 if footer_compact else 1)
    if isinstance(item, FooterKey):
        key = cell_len(item.key_display)
        if item.has_class("-command-palette"):
            # Never data_bind-ed, so it always renders compact; the extra 3 is
            # its padding-right plus the `border-left: vkey` separator.
            return key + cell_len(item.description) + 3
        if not item.description:
            # Textual forces show=False on a binding with an empty description,
            # so a top-level shown key always has one. Defensive.
            return key
        return key + cell_len(item.description) + (2 if footer_compact else 3)
    return 0


def _pack(costs, width, max_rows, hint_cost, pinned_tail, reserve):
    """First-fit pass. Returns ``(rows_of_indices, dropped_count)``.

    ``reserve`` is trimmed from every non-pinned row so the pinned tail can share
    the final content row. The last ``pinned_tail`` items are never dropped.
    """
    keep = len(costs) - pinned_tail
    tail = sum(costs[keep:])
    trimmed = max(width - reserve, 1)
    rows: list[list[int]] = [[]]
    used = 0
    for index, cost in enumerate(costs):
        row_limit = width if index >= keep else trimmed
        if used and used + cost > row_limit:
            if len(rows) < max_rows:
                rows.append([])
                used = 0
            else:
                # Last row is full: drop the remaining droppable items, popping
                # back far enough that the hint AND the pinned tail still fit.
                needed = hint_cost + tail
                while rows[-1] and used + needed > width:
                    used -= costs[rows[-1].pop()]
                dropped = keep - sum(len(row) for row in rows)
                rows[-1].extend(range(keep, len(costs)))
                return rows, dropped
        rows[-1].append(index)
        used += cost
    return rows, 0


def plan_footer_rows(costs, width, max_rows, *, hint_cost=0, pinned_tail=0):
    """Split ``costs`` into rows. Returns ``(rows_of_indices, dropped_count)``.

    Greedy first-fit at full width, preserving declaration order so muscle memory
    holds. Row count is emergent rather than computed: content that fits stays on
    one row, so a wide terminal renders exactly as the stock footer does and the
    footer only grows when it must.

    The command-palette key is passed as ``pinned_tail`` — the last entries in
    ``costs``, never droppable. That is what makes its row *be* the last row by
    construction; reserving width for "the last row" instead cannot work, because
    the final row count is not known until packing finishes.

    Two passes at most: first with the pinned tail's width reserved from every
    row (so the palette key shares the final content row instead of sitting alone
    on one), and — only if that forces drops — again without the reservation, so
    coverage wins over tidiness at narrow widths.
    """
    if not costs:
        return [], 0
    if width <= 0 or max_rows < 1:
        return [list(range(len(costs)))], 0
    reserve = sum(costs[len(costs) - pinned_tail:]) if pinned_tail else 0
    rows, dropped = _pack(costs, width, max_rows, hint_cost, pinned_tail, reserve)
    if dropped:
        rows, dropped = _pack(costs, width, max_rows, hint_cost, pinned_tail, 0)
    return rows, dropped


class MultiRowFooter(Footer):
    """A ``Footer`` that wraps onto multiple rows instead of clipping.

    Args:
        max_rows: Row cap. ``None`` resolves ``footer_max_rows`` from userconfig.
        hint_action: Action whose key the ``+N more (…)`` affordance should name
            — typically the shortcuts editor. Pass the *action*, not a key: the
            key display is resolved from the composed binding, so it tracks a
            user remap for free. See :meth:`_resolve_hint_key`.
    """

    DEFAULT_CSS = """
    MultiRowFooter {
        layout: vertical;
        height: auto;

        HorizontalGroup.-footer-row {
            layout: horizontal;
            width: 1fr;
            height: 1;
        }

        OverflowHint {
            width: auto;
            height: 1;
            padding: 0 1;
            color: $footer-description-foreground;
            background: $footer-description-background;
            text-style: italic;
        }
    }
    """

    def __init__(self, *children, max_rows=None, hint_action=None, **kwargs):
        super().__init__(*children, **kwargs)
        self._max_rows = max_rows
        self._hint_action = hint_action

    @property
    def max_rows(self) -> int:
        """Effective row cap (explicit argument wins over the user setting)."""
        if self._max_rows is not None:
            return self._max_rows
        return _resolve_max_rows()

    def _resolve_hint_key(self, items) -> str | None:
        """Key display of ``hint_action``'s binding, or None if it has none.

        Resolved from the *composed* widgets rather than the keybinding registry.
        Textual already resolved the display through ``app.get_key_display``, so
        a user remap is reflected automatically. Going through
        ``resolve_key(<app scope>, "open_shortcuts_editor")`` would NOT work: that
        action is registered under the ``shared`` scope, and
        ``register_app_bindings`` deliberately does not shadow shared actions into
        the app scope, so the lookup returns None and a hardcoded fallback would
        go stale exactly for users who rebound the key.
        """
        if not self._hint_action:
            return None
        for item in items:
            if isinstance(item, KeyGroup):
                candidates = item.children
            else:
                candidates = (item,)
            for candidate in candidates:
                if (
                    isinstance(candidate, FooterKey)
                    and candidate.action == self._hint_action
                ):
                    return candidate.key_display
        return None

    def compose(self):
        # Run the parent generator through Textual's own public composer rather
        # than list()-ing it: Footer.compose() builds grouped bindings with a
        # `with KeyGroup(...)` context manager, which pushes onto
        # app._compose_stacks instead of yielding. A bare list() would produce
        # empty KeyGroups and corrupt this compose call's stack.
        items = _textual_compose(self, super().compose())
        if not items:
            return

        palette = [w for w in items if w.has_class("-command-palette")]
        ordered = [w for w in items if not w.has_class("-command-palette")]
        ordered.extend(palette)

        compact = self.compact
        costs = [footer_item_width(w, footer_compact=compact) for w in ordered]
        hint_key = self._resolve_hint_key(items)
        # Reserve an upper bound: the real dropped count is only known after
        # packing, and the resolved key display varies in width. Formatting with
        # the largest plausible N keeps the affordance from overflowing the row
        # it announces.
        hint_cost = _hint_width(_format_hint(len(ordered), hint_key))

        width = self.size.width or self.app.size.width
        rows, dropped = plan_footer_rows(
            costs,
            width,
            self.max_rows,
            hint_cost=hint_cost,
            pinned_tail=len(palette),
        )

        last = len(rows) - 1
        for index, row in enumerate(rows):
            widgets = [ordered[i] for i in row]
            if dropped and index == last:
                widgets.insert(
                    len(widgets) - len(palette),
                    OverflowHint(_format_hint(dropped, hint_key)),
                )
            yield HorizontalGroup(*widgets, classes="-footer-row")

    def on_resize(self) -> None:
        # Row count is a function of width, so a terminal resize must reflow —
        # `bindings_updated` alone is not enough. This settles: the recompose
        # changes the footer's auto height, which emits one more Resize, whose
        # recompose produces the same height and stops. Bounded and asserted in
        # tests/test_multirow_footer.py.
        self.call_after_refresh(self.recompose)
