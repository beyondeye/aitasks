"""Known 'agent is awaiting user input' prompt patterns for ait monitor.

Grouped per code agent so future per-agent matching is trivial. Today every
pattern is applied to every AGENT pane regardless of which CLI is running
(see `all_patterns()`).

This file is the only place to edit when a new prompt wording shows up.
There is intentionally no project_config.yaml surface — these patterns are
treated like TUI_NAMES / DEFAULT_AGENT_PREFIXES (framework constants).
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
