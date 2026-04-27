"""Reusable polling-activity indicator for the brainstorm TUI.

A single-character circle widget with three states:
  - off:   blank/transparent, does not draw attention
  - dim:   slowly cycles through three brightness levels (~0.8 s/step)
  - flash: briefly bright (~0.2 s) then returns to dim cycle

Use start()/stop() to bracket the lifetime of an underlying poll, and
flash() to acknowledge a poll-fire.
"""

from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static


class PollingIndicator(Static):
    """Visual heartbeat for a background poller."""

    GLYPH = "●"
    DIM_INTERVAL = 0.8       # seconds per dim-cycle step
    FLASH_DURATION = 0.2     # seconds the bright flash stays on

    DEFAULT_CSS = """
    PollingIndicator {
        width: 1;
        height: 1;
        padding: 0;
        margin: 0;
        content-align: center middle;
        color: $background;
    }
    PollingIndicator.-dim-1 { color: $accent-darken-3; }
    PollingIndicator.-dim-2 { color: $accent-darken-2; }
    PollingIndicator.-dim-3 { color: $accent-darken-1; }
    PollingIndicator.-flash { color: $accent; text-style: bold; }
    """

    state: reactive[str] = reactive("off")

    def __init__(self, **kwargs) -> None:
        super().__init__(self.GLYPH, **kwargs)
        self._cycle_timer = None
        self._flash_timer = None
        self._dim_idx = 0

    def start(self) -> None:
        """Begin the dim-cycle. No-op if already running."""
        if self._cycle_timer is not None:
            return
        self._dim_idx = 0
        self.state = "dim"
        self._apply_dim_class()
        self._cycle_timer = self.set_interval(self.DIM_INTERVAL, self._dim_tick)

    def stop(self) -> None:
        """Stop dim-cycle and any in-flight flash. Returns to off."""
        if self._cycle_timer is not None:
            self._cycle_timer.stop()
            self._cycle_timer = None
        if self._flash_timer is not None:
            self._flash_timer.stop()
            self._flash_timer = None
        self.state = "off"

    def flash(self) -> None:
        """Briefly switch to bright; then return to dim (or off)."""
        if self._flash_timer is not None:
            self._flash_timer.stop()
        self.state = "flash"
        self._flash_timer = self.set_timer(self.FLASH_DURATION, self._end_flash)

    def watch_state(self, _old: str, new: str) -> None:
        for cls in ("-dim-1", "-dim-2", "-dim-3", "-flash"):
            self.remove_class(cls)
        if new == "dim":
            self._apply_dim_class()
        elif new == "flash":
            self.add_class("-flash")

    def _apply_dim_class(self) -> None:
        for cls in ("-dim-1", "-dim-2", "-dim-3"):
            self.remove_class(cls)
        self.add_class(f"-dim-{self._dim_idx + 1}")

    def _dim_tick(self) -> None:
        self._dim_idx = (self._dim_idx + 1) % 3
        if self._flash_timer is None and self.state == "dim":
            self._apply_dim_class()

    def _end_flash(self) -> None:
        self._flash_timer = None
        if self._cycle_timer is not None:
            self.state = "dim"
            self._apply_dim_class()
        else:
            self.state = "off"
