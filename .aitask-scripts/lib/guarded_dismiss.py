"""Guarded ``Screen.dismiss``: never pop a screen that is not the active one (t1816).

Textual's ``Screen.dismiss`` unconditionally calls ``app.pop_screen()``, which
pops *whatever screen is on top*, not the screen being dismissed. A stale key
still dispatched to an already-closed modal (e.g. rapid ``Esc`` presses) then
pops the screen beneath it — destroying a wizard — and once the stack is down to
one screen raises ``ScreenStackError`` and kills the TUI.

Derive modals from ``GuardedModalScreen`` (or mix ``GuardedDismissMixin`` in
before another ``Screen`` base) and keep call sites plain ``self.dismiss(...)``:
the guard lives in the base class. See ``aidocs/framework/tui_conventions.md``.
"""

from __future__ import annotations

from textual._context import NoActiveAppError
from textual.app import ScreenStackError
from textual.await_complete import AwaitComplete
from textual.screen import ModalScreen


def is_active_screen(screen) -> bool:
    """True when ``screen`` is the app's current top screen.

    Only the two documented "there is no active screen" states count as
    inactive: no app in context (``NoActiveAppError``, from ``MessagePump.app``)
    and an empty stack during shutdown (``ScreenStackError``, from
    ``App.screen``). Anything else — ``UnknownModeError``, an app-side bug —
    propagates, so a real fault is never disguised as "the dialog would not
    close".
    """
    try:
        return screen.app.screen is screen
    except (NoActiveAppError, ScreenStackError):
        return False


class GuardedDismissMixin:
    """Make ``dismiss`` a no-op unless this screen is the active one.

    Mix in BEFORE the ``Screen`` base. Dismissing an inactive screen does not
    pop anything and does not fire the result callback; it is logged when an app
    is reachable. Like Textual's own ``dismiss``, it must be called with an event
    loop running (``AwaitComplete`` needs one).
    """

    def dismiss(self, result=None):
        # Resolve the app once, outside is_active_screen: ``self.log`` is
        # ``self.app._logger``, so logging from a detached screen would re-raise
        # the very NoActiveAppError that classified it as inactive.
        try:
            app = self.app
        except NoActiveAppError:
            return AwaitComplete.nothing()  # detached: nothing to pop, nowhere to log
        try:
            active = app.screen is self
        except ScreenStackError:
            active = False  # empty stack during shutdown
        if not active:
            app.log.warning(
                f"guarded dismiss ignored: {self!r} is not the active screen"
            )
            return AwaitComplete.nothing()
        return super().dismiss(result)


class GuardedModalScreen(GuardedDismissMixin, ModalScreen):
    """``ModalScreen`` whose ``dismiss()`` is a no-op unless it is the active screen."""
