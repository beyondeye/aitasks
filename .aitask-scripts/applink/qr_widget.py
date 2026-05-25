"""Compact QR widget for the applink TUI.

Renders a QR (or Micro QR) code as terminal text using half-block characters.
We deliberately bypass ``segno.QRCode.terminal()`` so we can:
  - control cell width (2 chars wide per QR cell keeps the code roughly square
    against a typical 2:1 terminal cell aspect ratio)
  - render Micro QR symbols the same way as standard QR symbols
"""
from __future__ import annotations

import segno
from textual.widgets import Static


class TerminalQR(Static):
    """Static widget that renders a QR (or Micro QR) code as compact half-block text."""

    # (top_cell, bottom_cell) -> two-char string for one rendered row.
    BLOCK_MAP = {
        (0, 0): "  ",   # both light
        (1, 0): "▀▀",   # top dark
        (0, 1): "▄▄",   # bottom dark
        (1, 1): "██",   # both dark
    }

    def __init__(
        self,
        data: str,
        *,
        micro: bool | None = None,
        border: int = 2,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._border = border
        self._micro = micro  # None = auto, True = force Micro, False = force standard
        self._data = data
        self._refresh_qr()

    def set_data(self, data: str) -> None:
        """Re-render with new payload (used by the regenerate-token action)."""
        self._data = data
        self._refresh_qr()

    def _refresh_qr(self) -> None:
        qr = segno.make(self._data, micro=self._micro)
        # ``qr.matrix`` is a tuple of bytearrays; cells are 0 (light) or 1 (dark).
        rows = [list(row) for row in qr.matrix]
        b = self._border
        width = len(rows[0]) + 2 * b
        # Add the quiet zone (light cells around the symbol).
        pad_row = [0] * width
        padded: list[list[int]] = [pad_row[:] for _ in range(b)]
        for row in rows:
            padded.append([0] * b + row + [0] * b)
        padded.extend([pad_row[:] for _ in range(b)])
        # Pair-up rows: half-block rendering collapses two rows into one line.
        if len(padded) % 2:
            padded.append(pad_row[:])
        lines: list[str] = []
        for top, bottom in zip(padded[0::2], padded[1::2]):
            lines.append("".join(self.BLOCK_MAP[(t, bot)] for t, bot in zip(top, bottom)))
        self.update("\n".join(lines))
