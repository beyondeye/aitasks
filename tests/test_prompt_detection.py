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
  8. The workspace-trust dialog is detected as claude_trust_folder, in every
     focus/label variant (t1474).
  9. Prose that merely *quotes* the trust dialog is NOT detected — the negative
     controls for quoting, blockquotes, bullets, numbering, a lone confirm
     label, a blank line between the options, and the sibling terms dialog.
 10. The one irreducible false positive — a verbatim reproduction of the option
     block — is asserted, so the known limit is a pinned decision, not a belief.
 11. An OSC 8 hyperlink *inside* a prompt footer does not defeat matching, and a
     hyperlink target churning between ticks does not defeat idle detection —
     the two behavioural links to the strip_ansi OSC fix.

Run:
  python3 tests/test_prompt_detection.py
"""
from __future__ import annotations

import sys
import time
import unittest
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


def _check_awaiting_input_detected_for_matching_prompt() -> None:
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


def _check_awaiting_input_codex_pattern() -> None:
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


def _check_awaiting_input_only_for_agent_panes() -> None:
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    content = "Do you want to proceed?\n"

    tui_pane = make_pane(pane_id="%tui", category=PaneCategory.TUI, window_name="board")
    snap_tui = mon._finalize_capture(tui_pane, content)
    assert not snap_tui.awaiting_input, "TUI panes must not run prompt matching"

    other_pane = make_pane(pane_id="%other", category=PaneCategory.OTHER, window_name="bash")
    snap_other = mon._finalize_capture(other_pane, content)
    assert not snap_other.awaiting_input, "OTHER panes must not run prompt matching"


def _check_empty_patterns_means_no_awaiting_input() -> None:
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05, prompt_patterns=[])
    pane = make_pane()
    snap = mon._finalize_capture(pane, "Do you want to proceed?\n")
    assert not snap.awaiting_input, (
        "explicit empty prompt_patterns must disable detection"
    )
    assert snap.awaiting_input_kind == ""


def _check_dot_toggle_alone_still_marks_active() -> None:
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


def _check_old_prompt_text_in_scrollback_is_not_awaiting() -> None:
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


def _check_all_patterns_flattens_per_agent_groups() -> None:
    expected = sum(len(v) for v in PROMPT_PATTERNS_BY_AGENT.values())
    flat = all_patterns()
    assert len(flat) == expected, (
        f"all_patterns() should flatten to {expected} entries, got {len(flat)}"
    )
    # At least one claude pattern and one codex pattern exist today.
    names = {p.name for p in flat}
    assert "claude_proceed" in names
    assert "claude_trust_folder" in names
    assert "codex_yes_proceed" in names


# --- workspace-trust dialog (t1474) ------------------------------------------
#
# The first-run trust dialog blocks the agent before it has produced any output,
# so without a pattern it reads as idle and the user is never told it is waiting.
# Matching anchors on the two option lines; see prompt_patterns.claude_trust_folder
# for why the geometry (adjacency, `❯`-only marker, nothing else on the line) is
# what makes it structural rather than a phrase match.


def _trust_snap(content: str):
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    return mon._finalize_capture(make_pane(pane_id="%trust"), content)


def _check_trust_dialog_detected() -> None:
    variants = {
        "focus on confirm": (
            "❯ Yes, I trust this folder\n"
            "  No, exit\n"
        ),
        "focus on cancel": (
            "  Yes, I trust this folder\n"
            "❯ No, exit\n"
        ),
        "settings-trust sibling": (
            "❯ Yes, I trust these settings\n"
            "  No, exit Claude Code\n"
        ),
        "cancel keeps session": (
            "❯ Yes, I trust this folder\n"
            "  No, continue without these permissions\n"
        ),
        # Embedded in a realistic pane tail so this exercises the
        # _PROMPT_DETECTION_TAIL_LINES windowing, not just the regex. The
        # question line is deliberately far enough up to fall OUTSIDE the
        # window — which is exactly why the options, not the question, are the
        # anchor.
        "realistic pane tail": (
            "Accessing workspace:\n"
            "/home/user/project\n"
            "Quick safety check: Is this a project you created or one you\n"
            "trust? (Like your own code, a well-known open source project, or\n"
            "work from your team).\n"
            "Claude Code will be able to read, edit, and execute files here.\n"
            "\n"
            "❯ Yes, I trust this folder\n"
            "  No, exit\n"
        ),
    }
    for label, content in variants.items():
        snap = _trust_snap(content)
        assert snap.awaiting_input, f"trust dialog ({label}) must mark awaiting_input"
        assert snap.awaiting_input_kind == "claude_trust_folder", (
            f"trust dialog ({label}): expected claude_trust_folder, "
            f"got {snap.awaiting_input_kind!r}"
        )


def _check_trust_pattern_negative_controls() -> None:
    """Prose ABOUT the dialog must never be classified AS the dialog.

    Panes routinely display plans, docs and test files, so a pattern that is
    merely a quotable phrase eventually fires on text describing the widget.
    Each case below is a distinct way that could happen; a match here means the
    regex is too loose, and a matcher that fires on prose is worse than the
    missing pattern it replaces.
    """
    cases = {
        # The phrase this very task writes into its plan, docs and fixtures.
        "quick-safety phrase in prose":
            "Quick safety check: Is this a project you created or one you trust?\n",
        "confirm label quoted mid-sentence":
            'the button reads "Yes, I trust this folder" so we anchor on it\n',
        # Both labels present, but as prose rather than option geometry.
        "both labels quoted in one sentence":
            'the options are "Yes, I trust this folder" and "No, exit"\n',
        "both labels as a bullet list":
            "- Yes, I trust this folder\n- No, exit\n",
        "both labels as a numbered list":
            "1. Yes, I trust this folder\n2. No, exit\n",
        # The case ASCII `>` in the marker class would have let through.
        "both labels as a Markdown blockquote":
            "> Yes, I trust this folder\n> No, exit\n",
        "confirm label with trailing commentary":
            "Yes, I trust this folder   <- the confirm option\nNo, exit\n",
        # Proves the paired-label requirement is load-bearing.
        "confirm label with no cancel label":
            "❯ Yes, I trust this folder\n",
        "options separated by a blank line":
            "❯ Yes, I trust this folder\n\n  No, exit\n",
        # Scope control: a different widget must not be claimed under this name.
        "sibling terms-acceptance dialog":
            "❯ Yes, I accept\n  No, exit\n",
    }
    for label, content in cases.items():
        snap = _trust_snap(content)
        assert snap.awaiting_input_kind != "claude_trust_folder", (
            f"{label}: prose about the trust dialog must not be classified as "
            f"the dialog (got {snap.awaiting_input_kind!r})"
        )


def _check_trust_pattern_known_false_positive() -> None:
    """The one irreducible limit, asserted so it stays a decision.

    No text matcher can separate the live dialog from a verbatim,
    geometry-faithful reproduction of it: to the capture, they are the same
    bytes. This is accepted — the signal is advisory and the badge clears once
    the text scrolls — and the mitigation is a documentation rule (describe
    these labels inline in prose, never as a copied option block), not a
    tighter regex. Pinning it here means a future reader sees it was weighed.
    """
    snap = _trust_snap("    ❯ Yes, I trust this folder\n      No, exit\n")
    assert snap.awaiting_input_kind == "claude_trust_folder", (
        "the known-limit case changed behaviour; if this is now rejected the "
        "matcher was tightened — update the documented limit to match"
    )


def _check_osc_inside_prompt_footer_still_matches() -> None:
    """An OSC 8 sequence INSIDE a footer must not defeat prompt matching (t1474).

    Placement is what makes this a real control. A hyperlink wrapped *around*
    the whole footer leaves the pattern's text contiguous, so the match survives
    even without the OSC strip — such a test passes before and after and proves
    nothing. tmux emits the escape at the point the link starts, so a partially
    hyperlinked line puts the bytes mid-phrase: that is the case that fails with
    a CSI-only strip. Verified to discriminate against the pre-t1474 stripper.

    Runs through _finalize_capture, so it exercises the wiring, not just the regex.
    """
    esc = "\x1b"
    footer = (
        f"Enter to {esc}]8;;https://docs.example.com/keys{esc}\\"
        f"select{esc}]8;;{esc}\\ · ↑/↓ to navigate"
    )
    snap = _trust_snap(f"Which option?\n  1. Yes\n  2. No\n\n{footer}\n")
    assert snap.awaiting_input, (
        "a footer containing an OSC 8 hyperlink must still mark awaiting_input"
    )
    assert snap.awaiting_input_kind == "claude_askuserquestion", (
        f"expected claude_askuserquestion, got {snap.awaiting_input_kind!r}"
    )


def _check_osc_url_churn_does_not_defeat_idle() -> None:
    """Idle detection must ignore a hyperlink target that changes under it (t1474).

    This is the defect t1474 reports most directly: `compare_value` is the
    ANSI-stripped capture, and with OSC surviving the strip, two ticks whose
    *visible* text is identical but whose link target differs compare as
    "changed" — so the pane never reaches idle. Asserting on `is_idle` rather
    than on the stripped string keeps this a behavioural check at the same seam
    the monitor uses.
    """
    esc = "\x1b"

    def line(run: int) -> str:
        return (f"checking {esc}]8;;https://ci.example.com/run/{run}{esc}\\"
                f"build log{esc}]8;;{esc}\\ ...\n")

    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane(pane_id="%osc")
    mon._finalize_capture(pane, line(1))
    time.sleep(0.1)
    snap = mon._finalize_capture(pane, line(2))
    assert snap.is_idle, (
        "only the hyperlink target changed — the visible text is identical, so "
        "the pane must still read as idle"
    )


def main() -> int:
    tests = [
        ("_check_awaiting_input_detected_for_matching_prompt",
         _check_awaiting_input_detected_for_matching_prompt),
        ("_check_awaiting_input_codex_pattern",
         _check_awaiting_input_codex_pattern),
        ("_check_awaiting_input_only_for_agent_panes",
         _check_awaiting_input_only_for_agent_panes),
        ("_check_empty_patterns_means_no_awaiting_input",
         _check_empty_patterns_means_no_awaiting_input),
        ("_check_dot_toggle_alone_still_marks_active",
         _check_dot_toggle_alone_still_marks_active),
        ("_check_old_prompt_text_in_scrollback_is_not_awaiting",
         _check_old_prompt_text_in_scrollback_is_not_awaiting),
        ("_check_all_patterns_flattens_per_agent_groups",
         _check_all_patterns_flattens_per_agent_groups),
        ("_check_trust_dialog_detected", _check_trust_dialog_detected),
        ("_check_trust_pattern_negative_controls",
         _check_trust_pattern_negative_controls),
        ("_check_trust_pattern_known_false_positive",
         _check_trust_pattern_known_false_positive),
        ("_check_osc_inside_prompt_footer_still_matches",
         _check_osc_inside_prompt_footer_still_matches),
        ("_check_osc_url_churn_does_not_defeat_idle",
         _check_osc_url_churn_does_not_defeat_idle),
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
        return 1
    print(f"PASS: all {len(tests)} tests passed")
    return 0


class ScriptChecksTest(unittest.TestCase):
    """Collects this file's script-style checks under unittest discovery (t1211).

    ``main()`` catches each check's AssertionError to print a per-check tally,
    so the assertion here is on its return code; detail goes to stdout.
    """

    def test_all_checks_pass(self):
        self.assertEqual(main(), 0, "script checks failed — see stdout above")


if __name__ == "__main__":
    sys.exit(main())
