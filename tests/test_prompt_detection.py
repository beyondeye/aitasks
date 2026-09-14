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
 12. `claude_proceed` requires the question to hold its WHOLE line (t1557), so
     text typed into the permission dialog's editable option row reports no kind
     — as does prose that puts anything else on the line (inline, bulleted,
     blockquoted, quote-marked). A line holding ONLY the question still matches
     wherever it comes from, including inside a fenced code block; that is rule
     3 of `monitor_idle_and_prompt_detection.md` (a verbatim reproduction is
     indistinguishable) and it is pinned here, not merely believed.
 13. Codex's startup update-available prompt is detected as
     `codex_update_prompt` at its PRODUCTION geometry — top-aligned, above a run
     of blank rows — through the per-pattern `skip_trailing_blank_rows` opt-in
     (t1522). The opt-in is proven load-bearing (the same regex without it sees
     nothing) and per-pattern (the shared window stays untrimmed); prose about
     the dialog, the sign-in screen that shares its hint, and scrollback do not
     claim the kind; the verbatim-reproduction limit is pinned.

Run:
  python3 tests/test_prompt_detection.py
"""
from __future__ import annotations

import dataclasses
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".aitask-scripts"))

import review_loop_fixtures as fx  # noqa: E402
from monitor.ansi_utils import strip_ansi  # noqa: E402
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
    current_command: str = "claude",
) -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index="1",
        window_name=window_name,
        pane_index="0",
        pane_id=pane_id,
        pane_pid=1,
        current_command=current_command,
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


def _check_claude_proceed_requires_a_whole_line() -> None:
    """The phrase must hold its whole line to report `claude_proceed` (t1557).

    Claude's tool-permission dialog renders option 1 as EDITABLE (`Tab` amends
    it), so a substring anchor let user-typed text put a second copy of the
    question inside the 6-line detection window while the real header stayed
    outside it — flipping the reported kind mid-dialog and firing the review
    loop's auto-recheck. The whole-line form rejects the copy (it renders as
    `❯ 1. Yes, <typed text>`) and keeps the real header, which renders alone on
    its line whenever it is in the window at all.

    The quoting negative control is **narrower than `claude_trust_folder`'s**,
    and deliberately so. Whole-line anchoring rejects only prose that puts
    something else on the line — inline mentions, bullets, blockquotes, quote
    marks. It does NOT distinguish a line holding *only* the question from the
    real header, so a doc or fixture reproducing it on its own line (a fenced
    code block included) still matches. That is rule 3 in
    `aidocs/framework/monitor_idle_and_prompt_detection.md` — a verbatim
    reproduction is indistinguishable, which is why the rule is "do not write
    one" rather than "match around it". Asserted below so the limit stays a
    pinned decision rather than a belief, exactly as
    `_check_trust_pattern_known_false_positive` does for the trust dialog.
    """
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane()

    # The real header — alone on its line — still reports the kind.
    snap = mon._finalize_capture(pane, "  Do you want to proceed?  \n")
    assert snap.awaiting_input_kind == "claude_proceed", (
        f"a whole-line header must still match, got {snap.awaiting_input_kind!r}"
    )

    # Nothing else in the claude group matches a bare option row or prose, so
    # the expected kind is the empty string, not merely "something else".
    rejected = {
        "typed into the editable option row":
            "❯ 1. Yes, Do you want to proceed?\n",
        "typed into the unselected option row":
            "  1. Yes, Do you want to proceed?\n",
        "prose quoting the question inline":
            "the dialog asks Do you want to proceed? before it runs\n",
        "bulleted prose":
            "- Do you want to proceed? is the default question wording\n",
        "blockquoted prose":
            "> Do you want to proceed?\n",
        "quote-marked on its own line":
            '"Do you want to proceed?"\n',
    }
    for label, body in rejected.items():
        mon2 = TmuxMonitor(session="aitasks", idle_threshold=0.05)
        snap2 = mon2._finalize_capture(make_pane(pane_id="%wl"), body)
        assert snap2.awaiting_input_kind == "", (
            f"{label}: must report no kind, got {snap2.awaiting_input_kind!r}"
        )
        assert not snap2.awaiting_input, f"{label}: must not be awaiting_input"

    # The accepted structural limit, pinned rather than assumed. A line holding
    # nothing but the question IS the header as far as captured text goes, so
    # these match — and must, or the real short-pane dialog would stop being
    # detected. The practical rule that follows is rule 3's: describe the
    # question inline in prose, never on a line of its own.
    known_limits = {
        "standalone quoted line": "Do you want to proceed?\n",
        "fenced code block": "```\nDo you want to proceed?\n```\n",
    }
    for label, body in known_limits.items():
        mon3 = TmuxMonitor(session="aitasks", idle_threshold=0.05)
        snap3 = mon3._finalize_capture(make_pane(pane_id="%kl"), body)
        assert snap3.awaiting_input_kind == "claude_proceed", (
            f"{label}: the known limit is accepted and must stay pinned — "
            f"got {snap3.awaiting_input_kind!r}. If this now reports no kind, "
            "check that the real short-pane dialog is still detected before "
            "treating it as an improvement."
        )


def _check_awaiting_input_codex_pattern() -> None:
    # `current_command="codex"` since t1467: matching is scoped to the pane's own
    # agent, so a codex wording no longer fires on a pane running Claude. The
    # invariant under test — codex's wording is detected on a codex pane — is
    # unchanged; only the fixture's pane identity is corrected. The cross-agent
    # case it used to exercise implicitly is now explicit in
    # `_check_cross_agent_negative_control`.
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane(window_name="agent-pick-825-codex", current_command="codex")
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
    assert "codex_update_prompt" in names


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


# --- characterization: pattern × pane-command matrix (t1467 pre-phase) --------
#
# Pins what classify_content answers TODAY, before per-agent scoping exists, so
# the scoping change can be shown to move exactly what it intends. Written and
# run green against UNMODIFIED monitor_core.py first — a characterization test
# authored after the change pins the change, not the contract.
#
# Today `current_command` is not consulted at all (`all_patterns()` is applied to
# every AGENT pane), so every command column answers identically. THAT sameness
# is the property being pinned, and the flip table below says which cells are
# expected to change.

# One minimal body per existing pattern, in first-match-wins order.
_CHARACTERIZATION_BODIES: list[tuple[str, str]] = [
    ("claude_askuserquestion", "Enter to select · ↑/↓ to navigate · Esc to cancel\n"),
    ("claude_plan_approval", "  1. Yes, auto-accept edits\n"),
    ("claude_trust_folder", "❯ Yes, I trust this folder\n  No, exit\n"),
    ("claude_proceed", "Do you want to proceed?\n"),
    ("claude_help_bar", "Esc to cancel · Tab to amend\n"),
    ("codex_yes_proceed", "  Yes, proceed (y)\n"),
    # Added with the pattern (t1522), not part of the t1467 prediction; its
    # production geometry (top-aligned, above blank rows) is exercised by
    # `_check_codex_update_prompt_detected`, not here.
    ("codex_update_prompt", "  3. Skip until next version\n\n  Press enter to continue\n"),
]

# Every command a real pane reports, including the two measured non-resolving
# ones (t1467: Codex's launcher makes the pane read `node`; companion TUIs read
# `python`).
_CHARACTERIZATION_COMMANDS = ["claude", "codex", "opencode", "node", "python", ""]

# Cells expected to CHANGE when per-agent scoping lands. Everything not listed
# here must stay byte-identical. Stated before the change, as a prediction.
#
#   (pattern, command) -> new kind
#
# The rule: a pattern whose owning agent is not the pane's resolved agent stops
# matching. Commands that do not resolve keep the flat list (fail-open), so
# `node` / `python` / "" are deliberately absent from this table.
_CHARACTERIZATION_EXPECTED_FLIPS: dict[tuple[str, str], str] = {
    ("claude_askuserquestion", "codex"): "",
    ("claude_askuserquestion", "opencode"): "",
    ("claude_plan_approval", "codex"): "",
    ("claude_plan_approval", "opencode"): "",
    ("claude_trust_folder", "codex"): "",
    ("claude_trust_folder", "opencode"): "",
    ("claude_proceed", "codex"): "",
    ("claude_proceed", "opencode"): "",
    ("claude_help_bar", "codex"): "",
    ("claude_help_bar", "opencode"): "",
    ("codex_yes_proceed", "claude"): "",
    ("codex_yes_proceed", "opencode"): "",
    ("codex_update_prompt", "claude"): "",
    ("codex_update_prompt", "opencode"): "",
}


def _characterize(pattern_name: str, body: str, command: str):
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    pane = make_pane(pane_id="%char", current_command=command)
    return mon._finalize_capture(pane, body)


def _check_characterization_pattern_command_matrix() -> None:
    """Every (pattern, pane-command) cell answers exactly as predicted.

    Run green FIRST against unmodified monitor_core.py with an empty flip table,
    which pinned the pre-t1467 behaviour (the pane command was not consulted, so
    every column matched). The flip table was then authored as a *prediction* and
    the scoping change made; the two failures it produced were exactly the two
    predicted cells. Every unlisted cell must still be byte-identical, which is
    what makes this a guard rather than a snapshot of whatever the code does.
    """
    for pattern_name, body in _CHARACTERIZATION_BODIES:
        for command in _CHARACTERIZATION_COMMANDS:
            expected = _CHARACTERIZATION_EXPECTED_FLIPS.get(
                (pattern_name, command), pattern_name)
            snap = _characterize(pattern_name, body, command)
            assert snap.awaiting_input_kind == expected, (
                f"{pattern_name} on current_command={command!r}: expected kind "
                f"{expected!r}, got {snap.awaiting_input_kind!r}"
            )
            assert snap.awaiting_input == bool(expected), (
                f"{pattern_name} on current_command={command!r}: expected "
                f"awaiting_input={bool(expected)}"
            )


def _check_scoping_provenance_is_reported() -> None:
    """`scoped` / `agent_key` distinguish the two matching regimes (t1467).

    Both directions, because a field that is always False (or always True) would
    satisfy a one-sided test while carrying no information.
    """
    resolved = _characterize("claude_help_bar",
                             "Esc to cancel · Tab to amend\n", "claude")
    assert resolved.scoped is True, "a resolved pane must report scoped=True"
    assert resolved.agent_key == "claude", (
        f"expected agent_key='claude', got {resolved.agent_key!r}")

    # `python` is a companion TUI pane: PaneCategory.AGENT by window name, but
    # its command resolves to no agent and it has no agent child either.
    unresolved = _characterize("claude_help_bar",
                               "Esc to cancel · Tab to amend\n", "python")
    assert unresolved.awaiting_input, (
        "fail-open: an unresolved pane must still match the flat list")
    assert unresolved.scoped is False, (
        "an unresolved pane must NOT report itself as scoped")
    assert unresolved.agent_key == "", (
        f"expected empty agent_key, got {unresolved.agent_key!r}")


def _check_cross_agent_negative_control() -> None:
    """A foreign agent's prompt text must not set a kind on a resolved pane.

    This is the discriminating test for the whole scoping change: it FAILS
    against the pre-t1467 build, where `all_patterns()` was applied to every
    AGENT pane regardless of which CLI was running.
    """
    cases = [
        ("claude", "codex_yes_proceed", "  Yes, proceed (y)\n"),
        ("claude", "opencode_permission", "  Allow once   Allow always   Reject\n"),
        ("codex", "claude_help_bar", "Esc to cancel · Tab to amend\n"),
        ("opencode", "claude_askuserquestion",
         "Enter to select · ↑/↓ to navigate · Esc to cancel\n"),
        ("claude", "codex_update_prompt",
         "  3. Skip until next version\n\n  Press enter to continue\n"),
        ("opencode", "codex_update_prompt",
         "  3. Skip until next version\n\n  Press enter to continue\n"),
    ]
    for command, foreign_kind, body in cases:
        snap = _characterize(foreign_kind, body, command)
        assert snap.awaiting_input_kind != foreign_kind, (
            f"a {command} pane must not report the foreign kind "
            f"{foreign_kind!r} (got {snap.awaiting_input_kind!r})")


def _check_custom_pattern_survives_scoping() -> None:
    """A caller-supplied pattern in no registry group is never dropped.

    Scoping is subtractive ("remove what provably belongs to another agent"),
    not selective ("keep what is listed under this agent") — this is the case
    that tells the two rules apart.
    """
    from monitor.prompt_patterns import PromptPattern as _PP
    import re as _re
    custom = _PP("project_custom_prompt", _re.compile(r"CUSTOM PROMPT MARKER"))
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05,
                      prompt_patterns=[custom])
    snap = mon._finalize_capture(
        make_pane(pane_id="%custom", current_command="codex"),
        "CUSTOM PROMPT MARKER\n")
    assert snap.awaiting_input_kind == "project_custom_prompt", (
        f"a custom pattern must survive scoping, got {snap.awaiting_input_kind!r}")


def _check_new_agent_patterns_detected() -> None:
    """The measured Codex / OpenCode widgets are detected on their own panes.

    Wordings and distances measured live (t1467): Codex 0.146.0 and OpenCode
    1.18.18, captured through `capture-pane -p -e` + strip_ansi. Each body below
    reproduces the pane tail geometry, so this exercises the 6-line window too,
    not just the regex.
    """
    cases = [
        ("codex", "codex_question",
         "  Question 1/1 (1 unanswered)\n"
         "  Which color would you like?\n"
         "\n"
         "  › 1. Blue (Recommended)  A calm, versatile choice.\n"
         "    2. Green               A fresh, natural choice.\n"
         "\n"
         "  tab to add notes | enter to submit answer | esc to interrupt\n"),
        ("codex", "codex_permission",
         "  $ touch /home/ddt/probe\n"
         "\n"
         "› 1. Yes, proceed (y)\n"
         "  2. Yes, and don't ask again (p)\n"
         "\n"
         "  Press enter to confirm or esc to cancel\n"),
        ("opencode", "opencode_question",
         "  ┃  Choose one of these three colors.\n"
         "  ┃  1. Red\n"
         "  ┃  2. Blue\n"
         "  ┃  3. Green\n"
         "  ┃\n"
         "  ┃  ↑↓ select  enter submit  esc dismiss\n"),
        ("opencode", "opencode_permission",
         "  ┃  △ Permission required\n"
         "  ┃    ← Access external directory ~\n"
         "  ┃\n"
         "  ┃  - /home/ddt/*\n"
         "  ┃\n"
         "  ┃   Allow once   Allow always   Reject      ctrl+f fullscreen\n"),
    ]
    for command, expected_kind, body in cases:
        snap = _characterize(expected_kind, body, command)
        assert snap.awaiting_input, (
            f"{expected_kind}: pane must read as awaiting input")
        assert snap.awaiting_input_kind == expected_kind, (
            f"expected {expected_kind!r}, got {snap.awaiting_input_kind!r}")


def _check_opencode_palette_pattern_and_its_window_limit() -> None:
    """`opencode_palette` (t1520) matches its header, and does NOT extend to
    followed-pane detection -- which is a documented limit, not an oversight.

    The palette is an OVERLAY rendered ABOVE the composer box, so in a real
    1.18.18 capture its header sits ~21 lines from the bottom, outside the
    6-line prompt-detection window. The consumer that needs it is the review
    loop, whose negative half scans the whole captured tail. Both halves are
    pinned here so nobody later "fixes" the second assertion by widening the
    window, or assumes `ait monitor` gained palette coverage.
    """
    palette_header = "  31             Commands                          esc\n"

    # 1. Within the window, the pattern matches -- the regex itself works.
    snap = _characterize("opencode_palette", palette_header, "opencode")
    assert snap.awaiting_input, "palette header inside the window must match"
    assert snap.awaiting_input_kind == "opencode_palette", (
        f"expected opencode_palette, got {snap.awaiting_input_kind!r}")

    # 2. At its REAL distance it does not -- followed-pane detection unchanged.
    realistic = (palette_header
                 + "\n".join(["  ┃"] * 3
                             + ["  ┃  Build · GPT-5.4 OpenAI · high",
                                "  ╹" + "▀" * 40,
                                "   /tmp/scratchrepo", "   work:master", ""]))
    snap2 = _characterize("n/a", realistic, "opencode")
    assert not snap2.awaiting_input, (
        "the palette renders above the composer, so it is out of the 6-line "
        f"window; got kind {snap2.awaiting_input_kind!r}")


def _check_new_agent_patterns_negative_controls() -> None:
    """Prose about these widgets, and their idle panes, must not match.

    The idle cases are measured captures of each TUI sitting at its composer —
    the state that must read as "not waiting", or every idle agent would show as
    blocked.
    """
    cases = {
        "codex idle composer": (
            "codex",
            "› Summarize recent commits\n"
            "\n"
            "  gpt-5.6-terra high · /tmp/scratchrepo · Context 1% used\n"),
        "opencode idle composer": (
            "opencode",
            "\n\n  /tmp/scratchrepo:master                          1.18.18\n"),
        "prose describing the codex footer": (
            "codex",
            "the widget footer reads 'tab to add notes' and then the submit hint\n"),
        "prose describing the opencode options": (
            "opencode",
            'the buttons are "Allow once" and "Reject" in that dialog\n'),
    }
    for label, (command, body) in cases.items():
        snap = _characterize("n/a", body, command)
        assert not snap.awaiting_input, (
            f"{label}: must NOT mark awaiting_input "
            f"(got kind {snap.awaiting_input_kind!r})")


def _check_characterization_disable_and_category_gates() -> None:
    """The two gates that must survive scoping untouched."""
    for command in _CHARACTERIZATION_COMMANDS:
        mon = TmuxMonitor(session="aitasks", idle_threshold=0.05, prompt_patterns=[])
        snap = mon._finalize_capture(
            make_pane(pane_id="%charoff", current_command=command),
            "Do you want to proceed?\n")
        assert not snap.awaiting_input, (
            f"prompt_patterns=[] must disable detection (command={command!r})")
        assert snap.awaiting_input_kind == ""

        for category in (PaneCategory.TUI, PaneCategory.OTHER):
            mon2 = TmuxMonitor(session="aitasks", idle_threshold=0.05)
            snap2 = mon2._finalize_capture(
                make_pane(pane_id=f"%char{category}", category=category,
                          current_command=command),
                "Do you want to proceed?\n")
            assert not snap2.awaiting_input, (
                f"{category} panes must not run prompt matching "
                f"(command={command!r})")


def _check_unrecognized_rendering_degrades_silently() -> None:
    """An unmatched dialog rendering must read as idle, never as a wrong kind.

    OpenCode ships a full i18n bundle, and its *desktop* UI translates the
    permission vocabulary (`settings.permissions.action.allow` exists in ~15
    languages). The TUI labels this task anchors on were measured to come from a
    hardcoded English array instead — so the localization exposure is smaller
    than feared, but it is an observation about one version, not a guarantee.

    This is the control for what happens when that observation stops holding:
    the pattern simply does not match, the pane reads as not-awaiting, and the
    phase falls back to the ledger. What must NOT happen is a *different*
    agent's pattern claiming the dialog — which is what per-agent scoping
    prevents and what the paired assertion below pins.
    """
    translated = {
        "opencode permission, translated": (
            "opencode",
            "  ┃  △ Autorisation requise\n"
            "  ┃\n"
            "  ┃   Autoriser une fois   Toujours autoriser   Refuser\n"),
        "codex approval, translated": (
            "codex",
            "  Voulez-vous exécuter la commande suivante ?\n"
            "\n"
            "› 1. Oui, continuer (y)\n"
            "\n"
            "  Appuyez sur entrée pour confirmer\n"),
    }
    for label, (command, body) in translated.items():
        snap = _characterize("n/a", body, command)
        assert not snap.awaiting_input, (
            f"{label}: an unmatched rendering must degrade to not-awaiting, "
            f"got kind {snap.awaiting_input_kind!r}")
        assert snap.awaiting_input_kind == "", label
        # And the scoping provenance still reports honestly.
        assert snap.scoped is True, f"{label}: the pane itself did resolve"


# --- codex startup update-available prompt (t1522) ---------------------------
#
# Live, the dialog is an inline pre-TUI screen rendered TOP-aligned, so its tail
# sits above a run of blank rows; `codex_update_prompt` opts into matching the
# tail with that run dropped (`skip_trailing_blank_rows`). Bodies are derived
# from the committed live capture rather than retyped, so this file adds no
# second verbatim copy of the dialog.

# Blank rows measured below the hint at 80x24 / 120x30 / 120x50
# (codex-cli 0.154.0, t1522).
_UPDATE_PROMPT_MEASURED_BLANK_RUNS = (14, 20, 40)


def _update_prompt_tail() -> str:
    """The dialog as captured, ANSI-stripped, ending on the hint row."""
    return strip_ansi(fx.CODEX_UPDATE_PROMPT_RAW)


def _blank_rows(n: int) -> str:
    """``n`` blank rows after a final row (the first newline ends that row)."""
    return "\n" * (n + 1)


def _update_prompt_with_selection(option: int) -> str:
    """The same dialog with the `›` marker moved to ``option`` (1-3)."""
    lines = _update_prompt_tail().splitlines()
    rows = [i for i, line in enumerate(lines)
            if line.lstrip("› ").startswith(("1. ", "2. ", "3. "))]
    assert len(rows) == 3, f"fixture shape changed: option rows at {rows}"
    for n, i in enumerate(rows, start=1):
        lines[i] = ("› " if n == option else "  ") + lines[i].lstrip("› ")
    return "\n".join(lines)


def _codex_snap(content: str, command: str = "codex", patterns=None):
    """Classify ``content`` on an AGENT pane running ``command``.

    ``pane_pid=0`` is the documented "no pid" value: an unresolved command
    (`node`) would otherwise send `agent_key_from_pane` to scan that pid's
    children on the host, making the fail-open case host-dependent.
    """
    kwargs = {} if patterns is None else {"prompt_patterns": patterns}
    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05, **kwargs)
    pane = dataclasses.replace(
        make_pane(pane_id="%upd", window_name="agent-pick-1522",
                  current_command=command),
        pane_pid=0)
    return mon._finalize_capture(pane, content)


def _check_codex_update_prompt_detected() -> None:
    """The update prompt reports `codex_update_prompt` in every measured shape.

    The blank-run cases are the production geometry — the ones the shared
    6-line window alone cannot see. `node` is Codex's npm launcher: the pane
    command does not resolve there, and the fail-open flat list must still
    find it.
    """
    tail = _update_prompt_tail()
    cases = {"as captured (bottom-anchored)": (tail, "codex")}
    for run in _UPDATE_PROMPT_MEASURED_BLANK_RUNS:
        cases[f"top-aligned, {run} blank rows below"] = (
            tail + _blank_rows(run), "codex")
    for option in (1, 2, 3):
        cases[f"option {option} selected, top-aligned"] = (
            _update_prompt_with_selection(option) + _blank_rows(20), "codex")
    cases["unresolved node launcher, top-aligned"] = (
        tail + _blank_rows(20), "node")
    for label, (content, command) in cases.items():
        snap = _codex_snap(content, command)
        assert snap.awaiting_input, f"{label}: must mark awaiting_input"
        assert snap.awaiting_input_kind == "codex_update_prompt", (
            f"{label}: expected codex_update_prompt, "
            f"got {snap.awaiting_input_kind!r}")


def _check_update_prompt_trim_is_load_bearing_and_per_pattern() -> None:
    """Both halves of the opt-in, each able to fail.

    1. Load-bearing: the same regex WITHOUT the opt-in cannot see the
       production geometry, so the flag — not the regex — is what makes the
       pattern live. (That is what any bottom-anchored pattern does on a
       top-aligned screen; it is `claude_trust_folder`'s geometry half.)
    2. Per-pattern: a Claude help bar above a run of blank rows still reports
       no kind. The shared window stays untrimmed for every pattern that did
       not opt in; a global trim was measured to change Claude's kind
       selection by pane height.
    """
    real = next(p for p in PROMPT_PATTERNS_BY_AGENT["codex"]
                if p.name == "codex_update_prompt")
    assert real.skip_trailing_blank_rows, "the shipped pattern must opt in"
    top_aligned = _update_prompt_tail() + _blank_rows(20)

    with_flag = _codex_snap(top_aligned, patterns=[real])
    assert with_flag.awaiting_input_kind == "codex_update_prompt", (
        "control: the opt-in pattern must match, got "
        f"{with_flag.awaiting_input_kind!r}")
    without_flag = dataclasses.replace(real, skip_trailing_blank_rows=False)
    snap = _codex_snap(top_aligned, patterns=[without_flag])
    assert not snap.awaiting_input, (
        "without the opt-in the top-aligned dialog must be invisible — if it "
        "matches, the flag is not what makes the pattern live "
        f"(got {snap.awaiting_input_kind!r})")

    mon = TmuxMonitor(session="aitasks", idle_threshold=0.05)
    help_bar = "Esc to cancel · Tab to amend\n" + _blank_rows(8)
    snap2 = mon._finalize_capture(make_pane(pane_id="%shared"), help_bar)
    assert not snap2.awaiting_input, (
        "the shared window must stay untrimmed for patterns that did not opt "
        f"in (got {snap2.awaiting_input_kind!r})")


def _check_codex_update_prompt_negative_controls() -> None:
    """Text ABOUT the dialog, or a neighbouring screen, must not claim its kind.

    Each case is a distinct way the anchor could be reproduced. Every body is
    padded with a blank run, so it is judged in the same trimmed window the
    real pattern sees — an un-padded case would test the wrong window.
    """
    hint = "  Press enter to continue"
    last_option = "  3. Skip until next version"
    cases = {
        "hint alone on its own line": hint,
        "hint quoted inline in prose":
            "the dialog says Press enter to continue under the options",
        "hint as a bullet": "- Press enter to continue",
        "option and hint in a blockquote":
            "> 3. Skip until next version\n>\n> Press enter to continue",
        "option label quoted in prose above the hint":
            f'the third option reads "Skip until next version"\n\n{hint}',
        "option row with trailing commentary":
            f"{last_option}   <- dismisses until the next release\n\n{hint}",
        "option row and hint with no blank row between":
            f"{last_option}\n{hint}",
        "option row and hint two blank rows apart":
            f"{last_option}\n\n\n{hint}",
        # Scope control: Codex's sign-in onboarding screen ends with the SAME
        # hint over a different last option (paraphrased, not captured).
        "sign-in onboarding tail":
            "  2. Sign in with a device code\n"
            "     Sign in from another device\n\n"
            "  3. Provide your own API key\n"
            "     Pay for what you use\n\n"
            f"{hint}",
        # Scrollback: the dialog was answered and later output followed.
        "update prompt followed by later output":
            _update_prompt_tail() + "\n"
            + "\n".join(f"  output line {n}" for n in range(1, 8)),
    }
    for label, body in cases.items():
        snap = _codex_snap(body + _blank_rows(20))
        assert snap.awaiting_input_kind != "codex_update_prompt", (
            f"{label}: must not be classified as the update prompt")

    # The neighbouring codex footer keeps its own kind.
    permission = ("› 1. Yes, proceed (y)\n"
                  "  2. Yes, and don't ask again (p)\n\n"
                  "  Press enter to confirm or esc to cancel\n")
    snap = _codex_snap(permission)
    assert snap.awaiting_input_kind == "codex_permission", (
        "the permission footer must stay codex_permission, got "
        f"{snap.awaiting_input_kind!r}")


def _check_codex_update_prompt_known_false_positive() -> None:
    """The one irreducible limit, asserted so it stays a decision (rule 3).

    A doc or test file showing the last option row, one blank row and the hint
    in exact geometry IS the dialog as far as captured text goes. Accepted:
    the signal is advisory and clears once the text scrolls. The mitigation is
    the documentation rule — describe the dialog in prose, never paste its rows.
    """
    snap = _codex_snap(
        "    3. Skip until next version\n\n    Press enter to continue\n")
    assert snap.awaiting_input_kind == "codex_update_prompt", (
        "the known-limit case changed behaviour; if it is now rejected the "
        "matcher was tightened — update the documented limit to match")


def main() -> int:
    tests = [
        ("_check_unrecognized_rendering_degrades_silently",
         _check_unrecognized_rendering_degrades_silently),
        ("_check_characterization_pattern_command_matrix",
         _check_characterization_pattern_command_matrix),
        ("_check_characterization_disable_and_category_gates",
         _check_characterization_disable_and_category_gates),
        ("_check_scoping_provenance_is_reported",
         _check_scoping_provenance_is_reported),
        ("_check_cross_agent_negative_control",
         _check_cross_agent_negative_control),
        ("_check_custom_pattern_survives_scoping",
         _check_custom_pattern_survives_scoping),
        ("_check_new_agent_patterns_detected",
         _check_new_agent_patterns_detected),
        ("_check_new_agent_patterns_negative_controls",
         _check_new_agent_patterns_negative_controls),
        ("_check_opencode_palette_pattern_and_its_window_limit",
         _check_opencode_palette_pattern_and_its_window_limit),
        ("_check_awaiting_input_detected_for_matching_prompt",
         _check_awaiting_input_detected_for_matching_prompt),
        ("_check_claude_proceed_requires_a_whole_line",
         _check_claude_proceed_requires_a_whole_line),
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
        ("_check_codex_update_prompt_detected",
         _check_codex_update_prompt_detected),
        ("_check_update_prompt_trim_is_load_bearing_and_per_pattern",
         _check_update_prompt_trim_is_load_bearing_and_per_pattern),
        ("_check_codex_update_prompt_negative_controls",
         _check_codex_update_prompt_negative_controls),
        ("_check_codex_update_prompt_known_false_positive",
         _check_codex_update_prompt_known_false_positive),
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
