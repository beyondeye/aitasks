"""Shared row/keyboard-navigation helpers for brainstorm TUI hosts.

Extracted in t1047 to remove a byte-for-byte duplication that the t983_11
relocation left behind: ``_navigate_rows`` / ``_focus_within`` existed
identically on both ``BrainstormApp`` (the App's main screen) and
``ActionsWizardScreen`` (a pushed ``ModalScreen``).

The copied ``_navigate_rows`` hard-coded ``self.query_one(TabbedContent)`` for
its "up past the top row → focus the tab bar" boundary. That holds on the App's
main screen but **not** inside a modal (which has no ``TabbedContent``), so the
modal copy raised ``NoMatches`` and broke every wizard arrow-nav routed through
it. Here the tab-bar lookup is an overridable hook (:meth:`_nav_tab_bar`): the
App returns its ``Tabs`` widget, the modal inherits the default ``None`` and
simply stops at the top boundary.

The mixin is pure Textual — it only relies on ``self.focused`` and
``self.query_one`` (present on both ``App`` and ``Screen``) — so it carries no
brainstorm-specific imports and is independently testable.
"""

from __future__ import annotations


class RowNavMixin:
    """Up/down navigation among focusable rows in a container.

    Mixed into both ``BrainstormApp`` and ``ActionsWizardScreen``. Hosts that
    live inside a tab bar override :meth:`_nav_tab_bar` to enable the
    focus-handoff-to-tabs boundary behaviour.
    """

    def _nav_tab_bar(self):
        """Return the ``Tabs`` widget to hand focus to at the top boundary.

        Default ``None`` (no enclosing tab bar): up past the first row simply
        stops. ``BrainstormApp`` overrides this to return its main-screen
        ``Tabs`` so Browse/Session keep their tab-bar focus handoff.
        """
        return None

    def _navigate_rows(self, direction: int, container_id: str, row_types: tuple) -> bool:
        """Navigate up/down among focusable rows in a container.

        Returns True if the event was handled.
        direction: -1 for up, +1 for down.
        """
        try:
            container = self.query_one(f"#{container_id}")
        except Exception:
            return False

        focusable = [w for w in container.children if isinstance(w, row_types) and w.can_focus]
        if not focusable:
            return False

        focused = self.focused
        tabs_widget = self._nav_tab_bar()

        # If focus is on the Tabs bar and direction is down, focus first row
        if tabs_widget is not None and focused is tabs_widget:
            if direction == 1:
                focusable[0].focus()
                focusable[0].scroll_visible()
                return True
            return False

        # If no row is focused, focus the first (down) or last (up) row
        if not isinstance(focused, row_types):
            target = focusable[0] if direction == 1 else focusable[-1]
            target.focus()
            target.scroll_visible()
            return True

        # Find current index
        try:
            idx = focusable.index(focused)
        except ValueError:
            focusable[0].focus()
            focusable[0].scroll_visible()
            return True

        new_idx = idx + direction

        # At boundary: up past top → focus tabs (if any); down past bottom → stop
        if new_idx < 0:
            if tabs_widget is not None:
                tabs_widget.focus()
            return True  # no tab bar → stop at top, don't wrap
        if new_idx >= len(focusable):
            return True  # Stop at bottom, don't wrap

        focusable[new_idx].focus()
        focusable[new_idx].scroll_visible()
        return True

    def _focus_within(self, container) -> bool:
        """True if the currently focused widget is `container` or a descendant."""
        node = self.focused
        while node is not None:
            if node is container:
                return True
            node = node.parent
        return False
