"""applink's view of the monitor's snapshots (t2037_4).

applink reads pane status either from a ``MonitorClient`` (the shared monitor
status server's subscription, while a phone streams) or from a plain
``TmuxMonitor`` (in-process: no device connected yet, or
``AITASKS_MONITOR_SERVER=0``). Both the push loop and the router's idle gate
project what they read into applink's view through :func:`view_snapshots`, so
the two never disagree about a pane.

The projection is ``monitor_core.client_view_snapshots``:

- applink's own pane is dropped (t2034_2);
- a LIVE record of a parked agent that applink does not pin becomes the parked
  placeholder. Under the shared server another subscriber's pin makes the
  producer capture that agent live; without the substitution applink's view of
  it would flip between live and parked with other clients' pins. applink pins
  the windows its phones stream content for (``AppLinkServer._streamed_pins``).

A plain ``TmuxMonitor`` exposes neither ``parked_pairs`` nor ``capture_pins``,
so for it this is the own-pane drop alone — the in-process behaviour, where
applink never published a skip set and every agent is captured live.

Pure: no asyncio, no sockets.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from monitor.monitor_core import client_view_snapshots  # noqa: E402


def view_snapshots(monitor, snaps: dict, *, own_pane: str | None = None) -> dict:
    """``snaps`` (``pane_id -> PaneSnapshot``) as applink may show them."""
    parked_fn = getattr(monitor, "parked_pairs", None)
    parked = parked_fn() if callable(parked_fn) else frozenset()
    pins = getattr(monitor, "capture_pins", frozenset())
    if pins is None:
        pins = frozenset()
    return client_view_snapshots(
        snaps, own_pane=own_pane, parked_pairs=parked, pins=pins)
