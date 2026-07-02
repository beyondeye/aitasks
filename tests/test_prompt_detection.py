"""Unit test for TmuxMonitor 'agent awaiting user input' detection (t825).

Exercises _finalize_capture directly — no tmux required. Covers:
  1. Claude Code's "Do you want to proceed?" confirmation prompt is detected
     and tagged with awaiting_input_kind=claude_proceed.
  2. Codex's "Yes, proceed (y)" / "Yes proceed (y)" wording is detected.
  3. Prompt detection only fires for AGENT panes (not TUI / OTHER).
  4. Passing prompt_patterns=[] disables detection entirely.
  5. Dot ↔ space toggle alone (no prompt text) is NOT awaiting (regression
     guard against re-introducing dot-stripping).
  6. Prompt text higher in scrollback does not create awaiting-input false
     positives after the active pane content has moved on.
  7. all_patterns() flattens the per-agent groups deterministically.

Run:
  python3 tests/test_prompt_detection.py
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
)
from monitor.prompt_patterns import (  # noqa: E402
    PROMPT_PATTERNS_BY_AGENT,
    all_patterns,
)


def make_pane(
    pane_id: str = "%test",
    category: PaneCategory = PaneCategory.AGENT,
    window_name: str = "agent-pick-825",
) -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index="1",
        window_name=window_name,
        pane_index="0",
        pane_id=pane_id,
        pane_pid=1,
        current_command="claude",
        width=80,
        height=24,
        category=category,
        session_name="aitasks",
    )


def test_awaiting_input_detected_for_matching_prompt() -> None:
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    content = (
        "● Bash(some command)\n"
        "  ⎿  output...\n"
        "\n"
        "Do you want to proceed?\n"
        "  1. Yes\n"
        "  2. No\n"
    )
    snap = mon._finalize_capture(pane, content)
    assert snap.awaiting_input, "claude_proceed prompt must mark awaiting_input"
    assert snap.awaiting_input_kind == "claude_proceed", (
        f"expected claude_proceed kind, got {snap.awaiting_input_kind!r}"
    )


def test_awaiting_input_codex_pattern() -> None:
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane(window_name="agent-pick-825-codex")
    content = (
        "Allow this command to run?\n"
        "  Yes, proceed (y)\n"
        "  No (n)\n"
    )
    snap = mon._finalize_capture(pane, content)
    assert snap.awaiting_input, "codex_yes_proceed prompt must mark awaiting_input"
    assert snap.awaiting_input_kind == "codex_yes_proceed", (
        f"expected codex_yes_proceed kind, got {snap.awaiting_input_kind!r}"
    )

    # And without the comma — same pattern still matches.
    mon2 = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    snap2 = mon2._finalize_capture(pane, "Yes proceed (y)\n")
    assert snap2.awaiting_input
    assert snap2.awaiting_input_kind == "codex_yes_proceed"


def test_awaiting_input_only_for_agent_panes() -> None:
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    content = "Do you want to proceed?\n"

    tui_pane = make_pane(pane_id="%tui", category=PaneCategory.TUI, window_name="board")
    snap_tui = mon._finalize_capture(tui_pane, content)
    assert not snap_tui.awaiting_input, "TUI panes must not run prompt matching"

    other_pane = make_pane(pane_id="%other", category=PaneCategory.OTHER, window_name="bash")
    snap_other = mon._finalize_capture(other_pane, content)
    assert not snap_other.awaiting_input, "OTHER panes must not run prompt matching"


def test_empty_patterns_means_no_awaiting_input() -> None:
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05, prompt_patterns=[])
    pane = make_pane()
    snap = mon._finalize_capture(pane, "Do you want to proceed?\n")
    assert not snap.awaiting_input, (
        "explicit empty prompt_patterns must disable detection"
    )
    assert snap.awaiting_input_kind == ""


def test_dot_toggle_alone_still_marks_active() -> None:
    """Regression guard: a flashing ●↔space animation with no prompt text is
    NOT awaiting_input. The deliberate decision (t825 plan) is that we do NOT
    strip the activity-dot in general — that would mis-classify subagents
    actively working with only the dot animating as idle/awaiting.
    """
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()
    a = "● Explore(grep -r foo)\n  └ scanning…\n"
    b = "  Explore(grep -r foo)\n  └ scanning…\n"
    mon._finalize_capture(pane, a)
    time.sleep(0.1)
    snap = mon._finalize_capture(pane, b)
    assert not snap.awaiting_input, (
        "dot toggle alone (no prompt text) must NOT mark awaiting_input"
    )
    assert snap.awaiting_input_kind == ""


def test_old_prompt_text_in_scrollback_is_not_awaiting() -> None:
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane(window_name="agent-raw-1")
    content = "\n".join([
        "Allow this command to run?",
        "  Yes, proceed (y)",
        "  No (n)",
        "",
        "command output line 1",
        "command output line 2",
        "command output line 3",
        "command output line 4",
        "command output line 5",
        "command output line 6",
        "command output line 7",
        "working normally now",
    ])
    snap = mon._finalize_capture(pane, content)
    assert not snap.awaiting_input, (
        "old prompt text outside the live bottom of the pane must not mark awaiting_input"
    )
    assert snap.awaiting_input_kind == ""


def test_all_patterns_flattens_per_agent_groups() -> None:
    expected = sum(len(v) for v in PROMPT_PATTERNS_BY_AGENT.values())
    flat = all_patterns()
    assert len(flat) == expected, (
        f"all_patterns() should flatten to {expected} entries, got {len(flat)}"
    )
    # At least one claude pattern and one codex pattern exist today.
    names = {p.name for p in flat}
    assert "claude_proceed" in names
    assert "codex_yes_proceed" in names


if __name__ == "__main__":
    tests = [
        ("test_awaiting_input_detected_for_matching_prompt",
         test_awaiting_input_detected_for_matching_prompt),
        ("test_awaiting_input_codex_pattern",
         test_awaiting_input_codex_pattern),
        ("test_awaiting_input_only_for_agent_panes",
         test_awaiting_input_only_for_agent_panes),
        ("test_empty_patterns_means_no_awaiting_input",
         test_empty_patterns_means_no_awaiting_input),
        ("test_dot_toggle_alone_still_marks_active",
         test_dot_toggle_alone_still_marks_active),
        ("test_old_prompt_text_in_scrollback_is_not_awaiting",
         test_old_prompt_text_in_scrollback_is_not_awaiting),
        ("test_all_patterns_flattens_per_agent_groups",
         test_all_patterns_flattens_per_agent_groups),
    ]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS: {name}")
        except AssertionError as e:
            failures += 1
            print(f"  FAIL: {name}: {e}")
        except Exception as e:
            failures += 1
            print(f"  ERROR: {name}: {e!r}")
    print()
    if failures:
        print(f"FAIL: {failures}/{len(tests)} tests failed")
        sys.exit(1)
    print(f"PASS: all {len(tests)} tests passed")
