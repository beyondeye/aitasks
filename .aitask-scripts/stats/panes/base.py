"""PaneDef registry and shared rendering helpers for the stats TUI.

Each category module (overview/labels/agents/velocity) imports `register()`
and calls it at import time to populate `PANE_DEFS`. The TUI then looks up
panes by id and calls `pane.render(stats_data, content_container)`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from rich.text import Text
from textual.containers import Container
from textual.widgets import Static

if TYPE_CHECKING:
    from stats.stats_data import StatsData


@dataclass(frozen=True)
class PaneDef:
    id: str
    title: str
    category: str
    render: Callable[["StatsData", Container], None]


PANE_DEFS: dict[str, PaneDef] = {}


def register(pane: PaneDef) -> PaneDef:
    if pane.id in PANE_DEFS:
        raise ValueError(f"Duplicate pane id: {pane.id}")
    PANE_DEFS[pane.id] = pane
    return pane


def render_chart(
    setup_fn: Callable[[object], None],
    container: Container,
    width: int = 100,
    height: int = 22,
) -> None:
    """Build a plotext chart as an ANSI string and mount it as a Static.

    `setup_fn(plt)` receives the plotext module and must call the plotting
    primitives (`plot`, `bar`, `title`, `xticks`, …). This helper handles
    figure lifecycle (clear/size/theme/build) and the ANSI→Rich conversion.
    Falls back to a placeholder Static if plotext is unavailable.
    """
    try:
        import plotext as plt  # type: ignore
    except ImportError:
        container.mount(Static("[dim]plotext not installed — run 'ait setup'[/dim]"))
        return
    plt.clear_figure()
    plt.plotsize(width, height)
    plt.theme("pro")
    setup_fn(plt)
    output = plt.build()
    plt.clear_figure()
    container.mount(Static(Text.from_ansi(output)))


def empty_state(container: Container, message: str = "No data") -> None:
    container.mount(Static(f"[dim]{message}[/dim]"))
