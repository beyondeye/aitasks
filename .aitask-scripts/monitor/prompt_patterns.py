"""Known 'agent is awaiting user input' prompt patterns for ait monitor.

Grouped per code agent, and since t1467 matching is **scoped to the pane's own
agent** — see `scope_patterns`. A pane whose command does not resolve to a known
agent still gets the full flat list (`all_patterns()`), so no detection that
worked before is lost; that fail-open is the common case, not an edge, because
`pane_current_command` is unreliable (a Codex pane reports `node`). See
`aidocs/framework/monitor_idle_and_prompt_detection.md`.

This file is the only place to edit when a new prompt wording shows up.
There is intentionally no project_config.yaml surface — these patterns are
treated like TUI_NAMES / DEFAULT_AGENT_PREFIXES (framework constants).

Workflow-*phase* meaning is NOT assigned here: `lib/workflow_phase.py` maps
these `name`s to a phase (`NATIVE_KIND_PHASE`) and uses the per-agent
`QUESTION_WIDGET_KINDS` entries as its currency markers. The Codex/OpenCode
surfaces were inventoried live in t1467; note that neither agent has an
`ExitPlanMode` analogue, so neither has a phase-bearing native dialog and their
`NATIVE_KIND_PHASE` rows are empty **by measurement**, not by omission.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass

# The canonical pane→agent mapper lives in `lib/`, which is one layer DOWN from
# `monitor/` (monitor_core puts lib on sys.path and imports from it, never the
# reverse). Reached here by a __file__-derived insert with a flat-import
# fallback, the idiom review_loop.py already uses, so this module keeps working
# however it is imported.
_LIB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
from agent_keys import (  # noqa: E402
    AGENT_KEYS,
    agent_key_from_command,
    agent_key_from_pane,
)


@dataclass(frozen=True)
class PromptPattern:
    name: str             # short id, surfaced as snap.awaiting_input_kind
    regex: re.Pattern[str]


# The two option lines of Claude Code's workspace-trust confirm dialog, each
# holding nothing but its (optionally pointer-prefixed) label. Named fragments
# rather than one inline literal so the adjacency requirement below stays
# readable in both orders. See `claude_trust_folder` for why each piece is
# shaped this way.
_TRUST_YES = r"^[ \t]*(?:❯[ \t]*)?Yes, I trust th(?:is folder|ese settings)[ \t]*$"
_TRUST_NO = (r"^[ \t]*(?:❯[ \t]*)?"
             r"No, (?:exit(?: Claude Code)?|continue without these permissions)[ \t]*$")


# Per code agent. Empty lists are placeholders for agents whose prompt
# wording has not been observed/needed yet.
PROMPT_PATTERNS_BY_AGENT: dict[str, list[PromptPattern]] = {
    "claude": [
        # Numbered-option question widget (the AskUserQuestion tool). Measured
        # against Claude Code 2.1.226 (t1420): this was matched by NOTHING, so an
        # agent parked on a question — the single most common "waiting on you"
        # state, and every task-workflow checkpoint — read as idle.
        # Listed FIRST because matching is first-wins: this is the specific
        # widget, `claude_help_bar` below is the tool-permission one.
        PromptPattern("claude_askuserquestion",
                      re.compile(r"Enter to select\s+·\s+↑/↓ to navigate")),
        # ExitPlanMode's plan-approval dialog. Also previously unmatched; its
        # wording is "Would you like to proceed?", which is why `claude_proceed`
        # below never covered it.
        # MUST stay bottom-anchored: matching happens against the last
        # _PROMPT_DETECTION_TAIL_LINES (6) lines only, and this dialog's question
        # text renders ~7 lines up — outside the window. The alternation below is
        # measured at distance 0 and 5 respectively, so either rendering lands
        # inside it.
        PromptPattern("claude_plan_approval",
                      re.compile(r"ctrl\+g to edit in|Yes, auto-accept edits")),
        # First-run workspace-trust dialog ("Accessing workspace:" / "Quick
        # safety check: Is this a project you created or one you trust?" /
        # confirm + cancel options). Matched by NOTHING before t1474, so an
        # agent blocked on it — typically before it has produced any output at
        # all — read as IDLE and the user was never told it was waiting.
        #
        # Anchored on the two OPTION LINES, not on the footer t1420 measured
        # ("Enter to confirm · Esc to cancel"): the options are the bottom-most
        # lines of the dialog, so they land inside the tail window whichever way
        # the question wraps, and that footer is shared with unrelated confirm
        # dialogs (terms acceptance) this name would misdescribe.
        #
        # Four constraints, each load-bearing:
        #  * `❯` is the ONLY accepted marker. It comes from a figures-style
        #    table (pointer:"❯", " " when unfocused) and the CLI ships no
        #    fallbackSymbols / isUnicodeSupported table, so there is no ASCII
        #    degradation path. ASCII `>` is deliberately rejected — it is the
        #    Markdown blockquote prefix, and quoted prose would fire on it.
        #    A numeric prefix is rejected for the same reason: this is a
        #    pointer-select, not a numbered menu.
        #  * Each option line must hold NOTHING but its label (`[ \t]*$`).
        #  * The two labels must be ADJACENT. Requiring merely that both appear
        #    "nearby" is not structural — arbitrary prose fits between them, so
        #    any document discussing the dialog would match.
        #  * Both orders are accepted: which label carries `❯` depends on the
        #    dialog's initial focus.
        # `exit(?: Claude Code)?` is required, not cosmetic: the sibling
        # settings-trust dialog's cancel label is "No, exit Claude Code", and
        # with `$` closing the line a bare `exit` would leave that arm dead.
        #
        # KNOWN LIMIT: no text matcher can separate this dialog from a verbatim,
        # geometry-faithful reproduction of it — a pane displaying the test
        # fixture, or a doc that pastes the option block, IS the dialog as far as
        # captured text goes. Accepted (advisory signal, transient wrong badge)
        # and pinned by _check_trust_pattern_known_false_positive. The practical
        # rule that follows: describe these labels inline in prose, never as a
        # copied two-line option block.
        PromptPattern("claude_trust_folder",
                      re.compile(rf"(?m){_TRUST_YES}\n{_TRUST_NO}"
                                 rf"|{_TRUST_NO}\n{_TRUST_YES}")),
        # The permission dialog's DEFAULT question text: Claude Code renders it
        # verbatim for command/Bash permission and for the Read/Edit file
        # permission fallback (verified against 2.1.226). It is NOT the
        # plan-mode prompt — ExitPlanMode asks "Would you like to proceed?" and
        # is `claude_plan_approval`'s job.
        # In practice this rarely fires, and that is structural rather than a
        # wording problem: the question renders ABOVE the option list, so it
        # usually falls outside _PROMPT_DETECTION_TAIL_LINES and the
        # bottom-anchored `claude_help_bar` is what matches those dialogs.
        # Kept as a cheap backstop for short renderings (t1474).
        PromptPattern("claude_proceed", re.compile(r"Do you want to proceed\?")),
        # Bottom-of-pane help bar shown whenever Claude Code blocks on input
        # (numbered selection, free-text amend prompt, etc.).
        PromptPattern("claude_help_bar",
                      re.compile(r"Esc to cancel\s+·\s+Tab to amend")),
    ],
    "codex": [
        # Codex's request-user-input widget — the direct analogue of Claude's
        # AskUserQuestion, and the surface a task-workflow checkpoint renders
        # through under Codex. Measured live against 0.146.0 in a 163x50 pane
        # (t1467): the footer sits at distance 1 from the pane bottom, well
        # inside _PROMPT_DETECTION_TAIL_LINES (6).
        #
        # Anchored on the key-binding legend rather than on the question text:
        # the question is arbitrary agent prose (and renders ~8 lines up, outside
        # the window), whereas the legend is fixed by the widget. Legends are
        # also the part of a TUI least likely to appear in quoted prose.
        # Listed FIRST because matching is first-wins: this is the specific
        # widget, `codex_permission` below is the tool-approval one.
        PromptPattern("codex_question",
                      re.compile(r"tab to add notes\s*\|\s*enter to submit answer")),
        # The exec-approval dialog's footer, measured at distance 1. Deliberately
        # NOT a NATIVE_KIND_PHASE key — a tool confirmation carries no workflow
        # phase (see lib/workflow_phase.py).
        PromptPattern("codex_permission",
                      re.compile(r"Press enter to confirm or esc to cancel")),
        # Matches both "Yes, proceed (y)" and "Yes proceed (y)" across versions.
        # Verified still live on 0.146.0 (t1467): it renders at distance 5, so it
        # remains a real backstop for the same dialog when the footer scrolls.
        PromptPattern("codex_yes_proceed", re.compile(r"Yes,? proceed \(y\)")),
    ],
    "opencode": [
        # OpenCode's interactive question widget. Measured live against 1.18.18
        # (t1467): footer at distance 2, inside the 6-line window.
        #
        # The separator runs are `\s+`, not fixed double spaces: OpenCode wraps a
        # right-hand status column into the same physical lines, which can reflow
        # the spacing. For the same reason nothing here anchors on `$` —
        # trailing content on the line is normal for this TUI.
        PromptPattern("opencode_question",
                      re.compile(r"↑↓\s+select\s+enter\s+submit\s+esc\s+dismiss")),
        # The permission dialog's option row (distance 2). Before t1467 OpenCode
        # had NO patterns at all, so an agent blocked on this dialog read as
        # IDLE and the user was never told it was waiting — the same class of
        # blindness t1474 fixed for Claude's trust dialog.
        #
        # Anchored on all three labels in order, which is geometry rather than a
        # quotable phrase: prose mentioning "Reject" or "Allow once" alone cannot
        # match, and the fixed order is what the widget renders.
        PromptPattern("opencode_permission",
                      re.compile(r"Allow once\s+Allow always\s+Reject")),
    ],
    "all": [],   # generic prompts that match across agents — add as needed
}


def scope_patterns(patterns: list[PromptPattern],
                   agent: str) -> list[PromptPattern]:
    """``patterns`` minus every pattern that provably belongs to a DIFFERENT agent.

    Subtractive rather than selective, and each of those three consequences is
    load-bearing:

    * an unrecognised ``agent`` (``""`` — a wrapper process, a companion TUI)
      removes nothing, so the pre-t1467 flat-list behaviour is the fail-open
      default and no working detection is lost;
    * a caller-supplied pattern whose name is in no registry group survives,
      because "not owned by another agent" is a weaker and safer test than
      "listed under this agent";
    * ``patterns=[]`` stays empty, so the explicit disable path is untouched.

    Order is preserved, so first-match-wins semantics are unchanged.
    """
    key = (agent or "").strip().lower()
    if key not in AGENT_KEYS:
        return patterns
    foreign = {p.name
               for group, group_patterns in PROMPT_PATTERNS_BY_AGENT.items()
               if group != key and group != "all"
               for p in group_patterns}
    if not foreign:
        return patterns
    return [p for p in patterns if p.name not in foreign]


def all_patterns() -> list[PromptPattern]:
    """Flatten the per-agent dict into a single list for today's matching."""
    out: list[PromptPattern] = []
    for patterns in PROMPT_PATTERNS_BY_AGENT.values():
        out.extend(patterns)
    return out
