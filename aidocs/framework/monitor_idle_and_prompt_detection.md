# `ait monitor` — Idle vs. "Awaiting User Input" Detection

Specialist guidance for the two **independent** signals `ait monitor` and
`ait minimonitor` use to flag an AGENT pane that needs the user's attention:

| Signal | What it detects | Threshold | Source of truth |
|--------|-----------------|-----------|-----------------|
| `is_idle` | Pane content has not changed for ≥ `idle_threshold` seconds (default 5 s). | Time-based. | `_finalize_capture` in `.aitask-scripts/monitor/tmux_monitor.py`. |
| `awaiting_input` | The captured pane text contains a known "agent is paused on a prompt" regex. | Immediate (no wait). | `.aitask-scripts/monitor/prompt_patterns.py` (regex registry). |

UI priority is `awaiting_input > is_idle > active`. The two are
**deliberately independent**: a subagent doing real work with only the
activity dot (`●`) animating is `is_idle=False` *and*
`awaiting_input=False`; an agent stuck on a Yes/No prompt is flagged
immediately regardless of the idle timer.

## When to edit `prompt_patterns.py`

Edit
[`./.aitask-scripts/monitor/prompt_patterns.py`](../../.aitask-scripts/monitor/prompt_patterns.py)
when:

- The monitor fails to flag an agent that is visibly waiting on user input
  (confirmation prompt, tool-permission prompt, numbered selection menu).
- A new code-agent CLI is added (`opencode`, `gemini`, future tools).
- An existing agent changes its prompt wording across a release.

Add the new wording as a `PromptPattern(name=..., regex=re.compile(r"..."))`
under the matching code-agent group (`claude`, `codex`, `opencode`,
`gemini`, or `all` for cross-agent text). `name` is surfaced via
`PaneSnapshot.awaiting_input_kind`, so make it human-readable (e.g.
`claude_proceed`, `codex_yes_proceed`).

Then add a unit test in
[`tests/test_prompt_detection.py`](../../tests/test_prompt_detection.py)
asserting that a representative captured pane snippet sets
`awaiting_input is True` and `awaiting_input_kind == "<your_name>"`.

## What NOT to do

- **Do not** strip the subagent activity dot (`●` U+25CF ↔ U+0020 SPACE) in
  the `stripped` compare mode. The dot toggle is a real Unicode character
  change and can also mean a subagent is genuinely working — stripping it
  would mis-classify active subagents as idle. The positive
  `awaiting_input` layer exists *because* we deliberately do not strip the
  dot.
- **Do not** move prompt patterns into `aitasks/metadata/project_config.yaml`
  or any other user-configurable surface. These patterns are framework
  constants, same category as `TUI_NAMES` and `DEFAULT_AGENT_PREFIXES` in
  `.aitask-scripts/monitor/`. They are edited in-place when a new agent's
  prompt wording shows up; users do not need to know they exist.
- **Do not** apply prompt matching to TUI / OTHER panes. Matching is gated
  on `pane.category == PaneCategory.AGENT` inside `_finalize_capture` —
  preserve this gate when extending the logic.

## How matching is invoked

`TmuxMonitor.__init__` accepts an optional `prompt_patterns:
list[PromptPattern]` kwarg, defaulting to `all_patterns()` (the flattened
per-agent registry). Tests can inject `prompt_patterns=[]` to disable
matching, or a custom list to exercise specific regexes.

Inside `_finalize_capture`:

1. Existing idle-detection logic runs unchanged.
2. If the pane is an AGENT pane and `self.prompt_patterns` is non-empty,
   the ANSI-stripped pane text is searched against each pattern in order.
3. The first match wins — `snap.awaiting_input = True` and
   `snap.awaiting_input_kind = pattern.name`.

The per-agent grouping in `PROMPT_PATTERNS_BY_AGENT` is forward-looking:
today every pattern is applied to every AGENT pane via `all_patterns()`;
when per-pane code-agent detection lands later, the call site changes to
`PROMPT_PATTERNS_BY_AGENT[pane_agent]` with no other refactor required.

## UI rendering

Three sites consume `awaiting_input`/`is_idle` and must stay in sync via the
shared
[`format_pane_status(snap)`](../../.aitask-scripts/monitor/monitor_shared.py)
helper:

- `monitor_shared.py` — kill-confirmation dialog status line.
- `monitor_app.py` — agent card on the right pane and the SessionBar
  awaiting/idle counts.
- `minimonitor_app.py` — compact agent line and the one-line summary bar.

`format_pane_status` returns:

- `[bold magenta]PROMPT <s>s[/]` when `awaiting_input` is set.
- `[yellow]IDLE <s>s[/]` when `is_idle` is set and not awaiting.
- `[green]Active[/]` otherwise.

The summary bars decrement the idle count for panes that are also awaiting,
so a `PROMPT` pane never double-counts as `IDLE`. The auto-switch path in
`monitor_app._maybe_auto_switch` prefers awaiting panes over idle ones.
