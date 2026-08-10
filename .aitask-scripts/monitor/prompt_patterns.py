"""Known 'agent is awaiting user input' prompt patterns for ait monitor.

Grouped per code agent so future per-agent matching is trivial. Today every
pattern is applied to every AGENT pane regardless of which CLI is running
(see `all_patterns()`).

This file is the only place to edit when a new prompt wording shows up.
There is intentionally no project_config.yaml surface — these patterns are
treated like TUI_NAMES / DEFAULT_AGENT_PREFIXES (framework constants).

Workflow-*phase* meaning is NOT assigned here: `lib/workflow_phase.py` maps
these `name`s to a phase (`NATIVE_KIND_PHASE`) and uses `claude_askuserquestion`
as its currency marker. Codex/OpenCode prompt surfaces are inventoried and added
by **t1467** — the single Claude row below is not cross-agent coverage.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptPattern:
    name: str             # short id, surfaced as snap.awaiting_input_kind
    regex: re.Pattern[str]


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
        # Plan-mode and tool-permission confirmation prompt.
        PromptPattern("claude_proceed", re.compile(r"Do you want to proceed\?")),
        # Bottom-of-pane help bar shown whenever Claude Code blocks on input
        # (numbered selection, free-text amend prompt, etc.).
        PromptPattern("claude_help_bar",
                      re.compile(r"Esc to cancel\s+·\s+Tab to amend")),
    ],
    "codex": [
        # Matches both "Yes, proceed (y)" and "Yes proceed (y)" across versions.
        PromptPattern("codex_yes_proceed", re.compile(r"Yes,? proceed \(y\)")),
    ],
    "opencode": [],
    "all": [],   # generic prompts that match across agents — add as needed
}


def all_patterns() -> list[PromptPattern]:
    """Flatten the per-agent dict into a single list for today's matching."""
    out: list[PromptPattern] = []
    for patterns in PROMPT_PATTERNS_BY_AGENT.values():
        out.extend(patterns)
    return out
