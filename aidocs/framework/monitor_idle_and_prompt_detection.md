# `ait monitor` — Idle, "Awaiting User Input", and Completed Detection

Specialist guidance for the three **independent** signals `ait monitor` and
`ait minimonitor` use to classify an AGENT pane:

| Signal | What it detects | Threshold | Source of truth |
|--------|-----------------|-----------|-----------------|
| `is_idle` | Pane content has not changed for ≥ `idle_threshold` seconds (default 5 s). | Time-based. | `_finalize_capture` in `.aitask-scripts/monitor/monitor_core.py`. |
| `awaiting_input` | The captured pane text contains a known "agent is paused on a prompt" regex. | Immediate (no wait). | `.aitask-scripts/monitor/prompt_patterns.py` (regex registry). |
| *completed* | The pane's **task** is finished — frontmatter `status: Done`, or the task file already resolves under `aitasks/archived/`. | Immediate. | `is_task_completed()` in `.aitask-scripts/monitor/monitor_shared.py`. |

UI priority is `awaiting_input > completed > is_idle > active`. The signals are
**deliberately independent**: a subagent doing real work with only the
activity dot (`●`) animating is `is_idle=False` *and*
`awaiting_input=False`; an agent stuck on a Yes/No prompt is flagged
immediately regardless of the idle timer.

`completed` is different in kind from the other two — it is a property of the
pane's **task**, not of its captured text, so it is not a `PaneSnapshot` field.
Both signals are checked because `aitask_archive.sh` writes `status: Done`
*before* it moves the file, so a refresh tick can land between the two and see
either alone. A completed agent parked on its final prompt still renders
`PROMPT`: that is actionable now, whereas "done" is not.

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

The state→colour mapping is defined **once**, in
[`monitor_shared.py`](../../.aitask-scripts/monitor/monitor_shared.py):
`_state_color(snap, completed=False)`, wrapped by `format_state_dot` (the
agent's own `●`), `format_shadow_glyph` (a bound shadow's `◆`) and
`format_pane_status` (the text badge).

`format_pane_status` returns:

- `[bold magenta]PROMPT <s>s[/]` when `awaiting_input` is set.
- `[bold dodger_blue1]DONE <s>s[/]` when the pane's task is completed and not
  awaiting. `dodger_blue1` (`#0087ff`) rather than plain `blue`: Textual resolves
  `blue` to `#000080`, only a 1.1:1 contrast ratio against the `#1a1a1a` card
  background — effectively invisible. Verified by tmux capture, not by a string
  assertion, which cannot see contrast.
- `[yellow]IDLE <s>s[/]` when `is_idle` is set and neither of the above.
- `[green]Active[/]` otherwise.

`completed` is an **explicit parameter**, never inferred inside the helper: a
shadow pane has no task of its own, so inferring it would make
`format_shadow_glyph` colour shadows by their followed agent's task state.
`format_shadow_glyph` is deliberately single-argument and can never render in
the completed colour.

Consumers of these signals:

- `monitor_shared.py` — kill-confirmation dialog status line.
- `monitor_app.py` — agent card, the SessionBar awaiting/done/idle counts, the
  `CODE AGENTS` header legend, and `_maybe_auto_switch`.
- `minimonitor_app.py` — compact agent line and the one-line summary bar. The
  docked followed-agent panel (`_own_agent_identity_text`) is static by design
  and shows **no** status, including COMPLETED.
- `applink/pusher.py` — the `pane_status` push carries `idle_seconds`,
  `is_idle`, `awaiting_input`, `awaiting_input_kind` plus the optional
  `title` / `status` fields for the mobile client.
- `applink/router.py` — the `not_idle` restart gate reads `is_idle` only.

The summary bars partition agents on the same ladder the badges use, so each
agent lands in **at most one** bucket: `done` excludes awaiting panes and `idle`
excludes both. The auto-switch path in `monitor_app._maybe_auto_switch` prefers
awaiting panes and skips completed ones entirely — a finished agent is idle
forever and would otherwise permanently capture focus.

### Where "completed" comes from

`TaskInfoCache` (`monitor_core.py`) resolves each agent pane's task and is
**identity-keyed** on `(st_mtime_ns, st_size)` of the task file, so an archive
landing mid-session is picked up on the next tick. Two rules matter when
editing it:

- The identity is sampled **before** the content read in `_resolve`. The archive
  script's rewrites are rename-based, so a read racing a rewrite returns the old
  inode's bytes; an identity sampled afterwards would pin that stale content
  permanently.
- On `OSError` (the file **moved** to `archived/`) it **re-resolves** — unlike
  `GateSummaryCache`, which fails closed to `""`. Failing closed here would
  blank the pane's task title on exactly the tick its task completes.

Each app computes the completed set once per refresh
(`_compute_completed_panes`) and that set is the **sole** source of the card
badge, the bar counter and the auto-switch filter — re-deriving completion from
a later `get_task_info` call could make them disagree within a tick.
