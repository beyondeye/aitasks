---
Task: t825_idle_state_not_detected.md
Base branch: main
plan_verified: []
---

# t825 — Detect "agent awaiting user input" alongside idle in ait monitor

## Context

`ait monitor` (and `ait minimonitor`) failed to flag pane `agent-pick-777_27`
even though Claude Code was visibly blocked on a `Do you want to proceed?
(Yes/No)` confirmation prompt for several minutes.

Hands-on diagnosis with `tmux capture-pane -p -e -t %47`:

- Every capture tick the visible character `●` (U+25CF) toggles to U+0020 SPACE
  and back at line 82 (`● Explore(...)` ↔ `  Explore(...)`).
- This is Claude Code's subagent-activity dot animating, **even while the
  parent agent is paused on user input**.
- The existing `stripped` compare mode added in t715 only strips ANSI **CSI**
  sequences (SGR colors). The ●↔space toggle is a real Unicode character
  change that survives CSI stripping, so `idle_seconds` never grows past
  `idle_threshold` (5 s), `is_idle` stays False, and the IDLE badge never
  fires. (Reference: `aiplans/archived/p715_codex_idex_not_detected.md`.)

**Important nuance** (user feedback): we deliberately do NOT want to strip
the activity-dot toggle in general — a flashing dot with otherwise quiet
content can also mean a subagent is genuinely working. Treating it as idle
would mis-classify those cases. What we actually want is a **separate,
faster detection signal for "agent is awaiting user input"** (confirmation
prompts, tool-permission prompts) that surfaces even before the idle
threshold fires.

## Approach

Add a new positive-detection layer that runs alongside idle detection. When
the captured pane content (ANSI-stripped, last N lines) matches any known
prompt-pattern regex, mark the snapshot with a new `awaiting_input` flag.
The UI surfaces a dedicated `PROMPT` (magenta) state with priority
`awaiting_input > is_idle > active`.

Idle detection logic itself stays untouched — a subagent doing real work
with only a dot animating still shows as Active. Conversely, an agent
stuck on a Yes/No prompt is flagged immediately (no threshold wait).

**Pattern storage** (per user direction): patterns live in a single Python
module under `.aitask-scripts/monitor/` — **not** in `project_config.yaml`.
They are NOT user-configurable; treat them like the existing
`TUI_NAMES`/`DEFAULT_AGENT_PREFIXES` constants in the same directory:
edit-in-place when a new agent's prompt wording shows up.

The module organizes patterns **per code agent** (`claude`, `codex`,
`opencode`, `gemini`, `all`) even though today every pattern is applied to
every AGENT pane regardless of which CLI is running there. The grouping is
forward-looking — when we later have per-pane code-agent detection, we can
narrow each pane to its agent's pattern list with a one-line change.

## Implementation

### 1. New file: `.aitask-scripts/monitor/prompt_patterns.py`

The single source of truth for known "agent awaiting user input" patterns.

```python
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
    "gemini": [],
    "all": [],   # generic prompts that match across agents — add as needed
}


def all_patterns() -> list[PromptPattern]:
    """Flatten the per-agent dict into a single list for today's matching."""
    out: list[PromptPattern] = []
    for patterns in PROMPT_PATTERNS_BY_AGENT.values():
        out.extend(patterns)
    return out
```

### 2. `.aitask-scripts/monitor/tmux_monitor.py`

a. Add the import near the other monitor-local imports:

   ```python
   from .prompt_patterns import PromptPattern, all_patterns
   ```

b. Extend `PaneSnapshot` (line 164) with two new fields:

   ```python
   awaiting_input: bool = False
   awaiting_input_kind: str = ""   # name of the first matching prompt pattern
   ```

c. Extend `TmuxMonitor.__init__` with an optional kwarg
   `prompt_patterns: list[PromptPattern] | None = None`. Default to
   `all_patterns()` when None (so production code gets the bundled set
   automatically; tests can inject `[]` or a custom list):

   ```python
   self.prompt_patterns = list(prompt_patterns) if prompt_patterns is not None else all_patterns()
   ```

d. In `_finalize_capture` (line 495), after the existing
   `compare_value = _strip_ansi(content) if ...` line, compute the
   awaiting flag. Always run prompt matching against the ANSI-stripped
   form (visible text, not colors), and only for AGENT panes:

   ```python
   awaiting_input = False
   awaiting_input_kind = ""
   if pane.category == PaneCategory.AGENT and self.prompt_patterns:
       stripped_text = compare_value if mode == COMPARE_MODE_STRIPPED else _strip_ansi(content)
       for p in self.prompt_patterns:
           if p.regex.search(stripped_text):
               awaiting_input = True
               awaiting_input_kind = p.name
               break
   ```

   Pass both fields into the returned `PaneSnapshot(...)`.

e. `load_monitor_config` (line 736) — **no YAML key added**. The patterns
   are module-level constants, not config. (This is the explicit design
   choice: no `prompt_patterns` block in project_config.yaml, no
   `seed/project_config.yaml` edit.)

### 3. UI rendering — single helper, three sites

Add a helper in `monitor_shared.py` (next to the other shared rendering
code) so the three status-builder sites stay in sync:

```python
def format_pane_status(snap: PaneSnapshot) -> str:
    if getattr(snap, "awaiting_input", False):
        return f"[bold magenta]PROMPT {int(snap.idle_seconds)}s[/]"
    if snap.is_idle:
        return f"[yellow]IDLE {int(snap.idle_seconds)}s[/]"
    return "[green]Active[/]"
```

Replace the three current status-building blocks with `format_pane_status(snap)`:

- `monitor_shared.py:429-433` (kill-confirmation dialog)
- `monitor_app.py:977-980` (agent card on the right pane)
- `minimonitor_app.py:437-442` (agent line in minimonitor)

### 4. Summary bars

In the one-line summary bars, add an "awaiting" count next to the idle
count and decrement idle for panes that are *also* awaiting (so PROMPT
doesn't double-count as IDLE):

- `monitor_app.py:117` area (`AgentBar` / one-line bar)
- `minimonitor_app.py:375-403` (compose summary)

```python
awaiting_count = sum(1 for a in agents if getattr(a, "awaiting_input", False))
idle_count = sum(1 for a in agents
                 if a.is_idle and not getattr(a, "awaiting_input", False))
awaiting_str = f" [bold magenta]{awaiting_count} awaiting[/]" if awaiting_count else ""
idle_str = f" [yellow]{idle_count} idle[/]" if idle_count else ""
```

### 5. Auto-switch preference

In `monitor_app.py` `_switch_to_idle()` (~line 861), prefer awaiting-input
panes over idle ones — they need attention more urgently:

```python
awaiting = [s for s in snaps
            if s.pane.category == PaneCategory.AGENT and getattr(s, "awaiting_input", False)]
if awaiting:
    awaiting.sort(key=lambda s: s.idle_seconds, reverse=True)
    self._focused_pane_id = awaiting[0].pane.pane_id
    return
# existing idle path follows
```

### 6. Tests

New file `tests/test_prompt_detection.py` (keeps t715 tests focused on
compare modes):

- `test_awaiting_input_detected_for_matching_prompt` — feed `_finalize_capture`
  with content containing `Do you want to proceed?` → `snap.awaiting_input
  is True`, `snap.awaiting_input_kind == "claude_proceed"`.
- `test_awaiting_input_codex_pattern` — feed content with `Yes, proceed
  (y)` → `awaiting_input_kind == "codex_yes_proceed"`.
- `test_awaiting_input_only_for_agent_panes` — same content in a TUI /
  OTHER pane → `awaiting_input is False` (no per-CLI prompt matching for
  non-agent panes).
- `test_empty_patterns_means_no_awaiting_input` — pass
  `prompt_patterns=[]` explicitly → even with matching text,
  `awaiting_input is False`.
- `test_dot_toggle_alone_still_marks_active` — codifies the deliberate
  decision: a pane with only `● ↔ space` animation but no prompt text is
  NOT idle (under threshold) and NOT awaiting. Protects against
  accidentally re-introducing dot-stripping later.
- `test_all_patterns_flattens_per_agent_groups` — sanity check on
  `prompt_patterns.all_patterns()`: returns one entry per non-empty group
  in `PROMPT_PATTERNS_BY_AGENT`.

## Verification

1. Unit tests:
   ```bash
   python3 tests/test_idle_compare_modes.py   # still PASS (no regressions)
   python3 tests/test_prompt_detection.py     # new — PASS
   ```

2. Live verification against `agent-pick-777_27` (or any Claude Code agent
   on a confirmation prompt):
   ```bash
   ait minimonitor
   # → expected: agent-pick-777_27 row shows magenta "PROMPT Xs" badge
   #   within one refresh tick (≤3 s default), without waiting for the
   #   5 s idle threshold.
   ```

3. Regression: spin up any pane with a Bash subagent actively running
   (`● Bash(sleep 30)` style) — should remain `Active`, not flagged as
   PROMPT or IDLE.

4. Shellcheck / framework integrity unchanged (no shell scripts touched).

## Step 9 — Post-Implementation

Standard task-workflow Step 9: archival via
`./.aitask-scripts/aitask_archive.sh 825`. Profile `fast` works on the
current branch — no separate worktree to clean up.

Out-of-scope follow-ups (record in Final Implementation Notes at commit
time only if actually identified during implementation):
- Adding prompt patterns for OpenCode / Gemini CLI once their exact prompt
  wording is observed.
- A future `ait monitor` debug command to print and stress-test configured
  patterns against a live pane.
- Per-pane agent detection so we can match only the relevant per-agent
  pattern group instead of `all_patterns()`.
