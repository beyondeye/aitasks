"""Unit test for TmuxMonitor idle-detection compare modes (t715).

Exercises _finalize_capture directly — no tmux required. Covers:
  1. Default (stripped) mode ignores animated ANSI color changes.
  2. Raw mode preserves the legacy byte-equal behavior.
  3. Visible-text changes always reset idle, regardless of mode.
  4. cycle_compare_mode walks default → raw → stripped → default and
     clears stored last-content on each transition.
  5. The codex-cli 0.154.0 composer (t1797): the animation-free composer
     reaches idle, while the composer "starfield" (visible Braille glyphs)
     never does — the reason the starfield is disabled at launch rather than
     absorbed here.
  6. The codex-cli 0.160.1 composer under the post-t1944 launch overrides
     (animations on, starfield off): at rest it reaches idle, and while it
     works the per-second elapsed counter keeps it out of idle.

Run:
  python3 tests/test_idle_compare_modes.py
"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts"))
# The live-captured Codex frames live beside this file (review_loop_fixtures).
sys.path.insert(0, str(Path(__file__).resolve().parent))

import review_loop_fixtures as fx  # noqa: E402
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


def _check_default_mode_ignores_animated_color() -> None:
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


def _check_raw_mode_preserves_legacy_behavior() -> None:
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


def _check_visible_text_change_resets_idle() -> None:
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    mon._finalize_capture(pane, "\x1b[31mLine A\x1b[0m\n")
    time.sleep(0.1)
    snap = mon._finalize_capture(pane, "\x1b[31mLine B\x1b[0m\n")
    assert not snap.is_idle, "visible text change must reset idle timer"


def _check_cycle_compare_mode_sequence() -> None:
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


def _check_set_compare_mode_clears_last_content() -> None:
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    mon._finalize_capture(pane, "anything")
    assert pane.pane_id in mon._last_content
    mon.set_compare_mode(pane.pane_id, COMPARE_MODE_RAW)
    assert pane.pane_id not in mon._last_content


def _check_codex_animation_free_composer_reaches_idle() -> None:
    """t1797: two live ticks of the codex-cli 0.154.0 idle composer launched
    with `-c tui.animations=false` (the pre-t1944 launch override) are
    byte-identical, so the default stripped mode reaches idle."""
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    mon._finalize_capture(pane, fx.CODEX_0154_NOANIM_AT_REST_RAW)
    time.sleep(0.1)
    snap = mon._finalize_capture(pane, fx.CODEX_0154_NOANIM_AT_REST_TICK2_RAW)
    assert snap.is_idle, "the animation-free Codex composer must read idle"


def _check_codex_starfield_never_reaches_idle() -> None:
    """Characterization of the t1797 defect: the composer starfield draws
    VISIBLE Braille glyphs, which survive strip_ansi, so consecutive ticks
    differ and idle is never reached. The detector-side follow-up
    (codex_braille_detector_defense) is expected to flip this."""
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    mon._finalize_capture(pane, fx.CODEX_0154_STARFIELD_RAW_1)
    time.sleep(0.1)
    snap = mon._finalize_capture(pane, fx.CODEX_0154_STARFIELD_RAW_2)
    assert not snap.is_idle, "a starfield tick still counts as a change"


def _check_codex_0160_animated_composer_reaches_idle_at_rest() -> None:
    """t1944: animations on, starfield off — an at-rest codex-cli 0.160.1
    pane is still byte-stable, so it reads idle."""
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    mon._finalize_capture(pane, fx.CODEX_0160_ANIM_AT_REST_RAW)
    time.sleep(0.1)
    snap = mon._finalize_capture(pane, fx.CODEX_0160_ANIM_AT_REST_TICK2_RAW)
    assert snap.is_idle, "the at-rest 0.160 Codex composer must read idle"


def _check_codex_0160_working_counter_keeps_pane_active() -> None:
    """t1944: two live ticks 1.1 s apart of a working codex-cli 0.160.1 pane
    differ ONLY in the elapsed counter (`Working (6s` -> `(7s`), so idle is
    not reached — the repaint `tui.animations=false` had suppressed. The
    control (the second tick with its counter frozen at the first value)
    must read idle, which proves the counter is what keeps the pane active."""
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    mon._finalize_capture(pane, fx.CODEX_0160_ANIM_WORKING_RAW_1)
    time.sleep(0.1)
    snap = mon._finalize_capture(pane, fx.CODEX_0160_ANIM_WORKING_RAW_2)
    assert not snap.is_idle, "a counter tick counts as a change"

    frozen = fx.CODEX_0160_ANIM_WORKING_RAW_2.replace("7s", "6s")
    assert frozen != fx.CODEX_0160_ANIM_WORKING_RAW_2, "control must freeze the counter"
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    mon._finalize_capture(pane, fx.CODEX_0160_ANIM_WORKING_RAW_1)
    time.sleep(0.1)
    snap = mon._finalize_capture(pane, frozen)
    assert snap.is_idle, "with the counter frozen, nothing else changes"


def _check_codex_0160_fresh_idle_settles_inside_starfield_window() -> None:
    """t1944: a fresh, starfield-eligible 0.160.1 pane under the launch
    overrides reads idle, while the starfield control captured at the same
    instants never does."""
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    mon._finalize_capture(pane, fx.CODEX_0160_FRESH_IDLE_RAW)
    time.sleep(0.1)
    snap = mon._finalize_capture(pane, fx.CODEX_0160_FRESH_IDLE_TICK2_RAW)
    assert snap.is_idle, "the starfield keys keep a fresh pane settled"

    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    mon._finalize_capture(pane, fx.CODEX_0160_STARFIELD_RAW_1)
    time.sleep(0.1)
    snap = mon._finalize_capture(pane, fx.CODEX_0160_STARFIELD_RAW_2)
    assert not snap.is_idle, "the control's starfield keeps it active"


def main() -> int:
    _check_default_mode_ignores_animated_color()
    _check_raw_mode_preserves_legacy_behavior()
    _check_visible_text_change_resets_idle()
    _check_cycle_compare_mode_sequence()
    _check_set_compare_mode_clears_last_content()
    _check_codex_animation_free_composer_reaches_idle()
    _check_codex_starfield_never_reaches_idle()
    _check_codex_0160_animated_composer_reaches_idle_at_rest()
    _check_codex_0160_working_counter_keeps_pane_active()
    _check_codex_0160_fresh_idle_settles_inside_starfield_window()
    print("PASS")
    return 0


class ScriptChecksTest(unittest.TestCase):
    """Collects this file's script-style checks under unittest discovery (t1211).

    These checks use bare ``assert``, so a failure propagates out of ``main()``
    as an AssertionError with a full traceback — ``main()`` only ever returns 0.
    """

    def test_all_checks_pass(self):
        self.assertEqual(main(), 0, "script checks failed — see stdout above")


if __name__ == "__main__":
    sys.exit(main())
