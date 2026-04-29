"""Unit test for TmuxMonitor idle-detection compare modes (t715).

Exercises _finalize_capture directly — no tmux required. Covers:
  1. Default (stripped) mode ignores animated ANSI color changes.
  2. Raw mode preserves the legacy byte-equal behavior.
  3. Visible-text changes always reset idle, regardless of mode.
  4. cycle_compare_mode walks default → raw → stripped → default and
     clears stored last-content on each transition.

Run:
  python3 tests/test_idle_compare_modes.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts"))

from monitor.tmux_monitor import (  # noqa: E402
    TmuxMonitor,
    TmuxPaneInfo,
    PaneCategory,
    COMPARE_MODE_RAW,
    COMPARE_MODE_STRIPPED,
)


def make_pane(pane_id: str = "%test") -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index="1",
        window_name="agent-pick-715",
        pane_index="0",
        pane_id=pane_id,
        pane_pid=1,
        current_command="codex",
        width=80,
        height=24,
        category=PaneCategory.AGENT,
        session_name="aitasks",
    )


def test_default_mode_ignores_animated_color() -> None:
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    a = "\x1b[38;2;156;164;198m• Running\x1b[0m\nWait...\n"
    b = "\x1b[38;2;124;130;159m• Running\x1b[0m\nWait...\n"
    mon._finalize_capture(pane, a)
    time.sleep(0.1)
    snap = mon._finalize_capture(pane, b)
    assert snap.is_idle, (
        "stripped mode (default) must ignore ANSI color animation"
    )


def test_raw_mode_preserves_legacy_behavior() -> None:
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    mon.set_compare_mode(pane.pane_id, COMPARE_MODE_RAW)
    a = "\x1b[38;2;156;164;198m• Running\x1b[0m\nWait...\n"
    b = "\x1b[38;2;124;130;159m• Running\x1b[0m\nWait...\n"
    mon._finalize_capture(pane, a)
    time.sleep(0.1)
    snap = mon._finalize_capture(pane, b)
    assert not snap.is_idle, (
        "raw mode must keep counting ANSI color changes as activity"
    )


def test_visible_text_change_resets_idle() -> None:
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    mon._finalize_capture(pane, "\x1b[31mLine A\x1b[0m\n")
    time.sleep(0.1)
    snap = mon._finalize_capture(pane, "\x1b[31mLine B\x1b[0m\n")
    assert not snap.is_idle, "visible text change must reset idle timer"


def test_cycle_compare_mode_sequence() -> None:
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    # Seed last_content so we can verify it gets cleared on each cycle.
    mon._finalize_capture(pane, "\x1b[31mhello\x1b[0m\n")
    assert pane.pane_id in mon._last_content

    # default → raw
    mode, is_default = mon.cycle_compare_mode(pane.pane_id)
    assert mode == COMPARE_MODE_RAW and not is_default
    assert pane.pane_id not in mon._last_content

    # raw → stripped (override, not default)
    mon._finalize_capture(pane, "\x1b[31mhello\x1b[0m\n")
    mode, is_default = mon.cycle_compare_mode(pane.pane_id)
    assert mode == COMPARE_MODE_STRIPPED and not is_default
    assert pane.pane_id not in mon._last_content

    # stripped → default (no override; effective mode is still stripped
    # because that is the global default)
    mon._finalize_capture(pane, "\x1b[31mhello\x1b[0m\n")
    mode, is_default = mon.cycle_compare_mode(pane.pane_id)
    assert mode == COMPARE_MODE_STRIPPED and is_default
    assert pane.pane_id not in mon._last_content


def test_set_compare_mode_clears_last_content() -> None:
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    mon._finalize_capture(pane, "anything")
    assert pane.pane_id in mon._last_content
    mon.set_compare_mode(pane.pane_id, COMPARE_MODE_RAW)
    assert pane.pane_id not in mon._last_content


if __name__ == "__main__":
    test_default_mode_ignores_animated_color()
    test_raw_mode_preserves_legacy_behavior()
    test_visible_text_change_resets_idle()
    test_cycle_compare_mode_sequence()
    test_set_compare_mode_clears_last_content()
    print("PASS")
