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
`claude_proceed`, `codex_yes_proceed`). The claude group ships
`claude_askuserquestion`, `claude_plan_approval`, `claude_trust_folder`,
`claude_proceed` and `claude_help_bar`; codex ships `codex_yes_proceed`.

Then add a unit test in
[`tests/test_prompt_detection.py`](../../tests/test_prompt_detection.py)
asserting that a representative captured pane snippet sets
`awaiting_input is True` and `awaiting_input_kind == "<your_name>"`.

### Three rules for the regex itself

These are the lessons from patterns that shipped and did not work (t1420,
t1474). Each one costs a line to follow and a release to discover.

- **Bottom-anchor it.** Matching runs against the last
  `_PROMPT_DETECTION_TAIL_LINES` (6) lines of the stripped capture, so anchor
  on text that renders at the very *bottom* of the dialog — the footer, or the
  option labels — never on the question line. A question rendered above an
  option list normally falls outside the window. `claude_proceed` is the worked
  example: its wording (`Do you want to proceed?`) is live and correct, it is
  the permission dialog's default question, and it still almost never fires,
  because it renders above the options and the bottom-anchored
  `claude_help_bar` matches those dialogs first.

- **Anchor on dialog structure, not on a quotable phrase.** Panes display
  plans, docs and test files, so any pattern that is a single phrase eventually
  fires on text *about* the dialog instead of the dialog. Prefer a line anchor
  plus a second element that only ever co-occurs in the real widget —
  `claude_trust_folder` requires the confirm *and* cancel labels on adjacent
  lines, each holding nothing else — and ship a negative control for every way
  prose could reproduce the anchor: quoted inline, blockquoted, bulleted,
  numbered, and both labels present but not in option geometry.

- **A verbatim reproduction is indistinguishable, so do not write one.**
  Whatever the matcher, a doc or fixture that reproduces a dialog *with its
  exact line geometry* is that dialog as far as the captured text is concerned,
  and will be flagged when displayed in a pane. This is irreducible, not a bug
  to fix. Describe dialog labels inline in prose (as this page does); never
  paste an option block into this document, a task, or a plan.

### What the capture actually contains

The refresh tick captures with `capture-pane -p -e`, which re-emits **SGR
colour runs and OSC 8 hyperlinks**. `strip_ansi`
([`monitor/ansi_utils.py`](../../.aitask-scripts/monitor/ansi_utils.py))
removes both, and everything that matches on pane text goes through it —
including `compare_value`, which is why a hyperlink whose target changes
between ticks used to keep a pane out of idle forever. A pattern written
against raw capture bytes rather than stripped text will not match.

## What NOT to do

- **Do not** strip the subagent activity dot (`●` U+25CF ↔ U+0020 SPACE) in
  the `stripped` compare mode. The dot toggle is a real Unicode character
  change and can also mean a subagent is genuinely working — stripping it
  would mis-classify active subagents as idle. The positive
  `awaiting_input` layer exists *because* we deliberately do not strip the
  dot.
- **Do not** assume this file is the only place per-agent pane text is
  matched. It owns **followed**-pane dialog detection. The minimonitor
  auto-recheck loop matches the **shadow** pane's *composer* (is the input line
  empty?) and *working indicator* in
  [`monitor/review_loop.py`](../../.aitask-scripts/monitor/review_loop.py),
  which imports `PROMPT_PATTERNS_BY_AGENT` from here and uses it as its
  negative half. So adding an agent's dialog pattern here strengthens the
  review loop too, but a *composer* pattern belongs there — see
  [`shadow_agent.md`](shadow_agent.md) → "Where the shadow's own patterns live".
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

### Matching is scoped to the pane's own agent (t1467)

Step 2 above searches `scope_patterns(self.prompt_patterns, agent)`, not the
whole flat list. `scope_patterns` is **subtractive**: it removes only patterns
that provably belong to a *different* agent. Three consequences, each
deliberate:

* an unrecognised agent removes nothing, so behaviour is exactly the pre-t1467
  flat list — no working detection is ever lost;
* a caller-supplied pattern whose name is in no registry group survives;
* `prompt_patterns=[]` still disables matching entirely, because the filter runs
  over the **supplied list**, never over the module dict.

`agent` comes from `lib/agent_keys.agent_key_from_pane(pane.current_command,
pane.pane_pid)` — the canonical mapper, shared with `lib/workflow_phase.py`
(which re-exports it) so the two cannot drift. It lives in `lib/` because the
dependency runs one way, `monitor/` → `lib/`, and `workflow_phase.py` must stay
runnable as a standalone CLI. `tests/test_workflow_phase_standalone.sh` pins
both properties.

#### `pane_current_command` is not authoritative — resolution is a ladder

Measured 2026-08-13 on a live session:

| launcher shape | example | `pane_current_command` | resolves? |
|---|---|---|---|
| native binary | Claude Code, OpenCode | `claude`, `opencode` | rung 1 |
| node wrapper spawning the real binary | Codex (npm install) | `node` | rung 2 |
| companion TUI in an `agent-*` window | minimonitor | `python` | neither |

So `agent_key_from_pane` tries the pane's own command, then **one level** of
child processes (`pgrep -P` + `ps -o comm=`, the pair that works on both Linux
and BSD). One level only: a real Codex already runs `codex-code-mode-host` at
depth 2, so a deeper walk would resolve a pane to whatever it happened to spawn.
Ambiguity (children resolving to different agents) and every failure path return
`""`, which is the pre-t1467 answer. The result is cached per
`(pane_pid, current_command)` — this sits on the per-tick refresh path.

`""` means **"could not resolve"**, never "not an agent". Because the fallback
is common rather than exceptional, the result carries its own provenance:
`PaneSnapshot.agent_key` / `.scoped`, forwarded to the phase signal
(`PhaseSignal.resolution`) and to the applink `pane_status` frame
(`awaiting_input_scoped`, `agent_key` — additive optional fields, no protocol
`v` bump). Consumers read those instead of re-deriving the agent, so the value
that scoped the match is the value everyone downstream sees.

The durable fix is an engine-owned `@aitask_agent` pane option stamped at launch;
until it exists, nothing may treat `current_command` as identity.

## UI rendering

The state→colour mapping is defined **once**, in
[`monitor_shared.py`](../../.aitask-scripts/monitor/monitor_shared.py):
`_state_color(snap, completed=False)`, wrapped by `format_state_dot` (the
agent's own `●`), `format_shadow_glyph` (a bound shadow's `◆`) and
`format_pane_status` (the text badge).

`format_pane_status` returns:

- `[bold magenta]PROMPT <s>s[/]` when `awaiting_input` is set.
- `[bold #1e90ff]DONE <s>s[/]` when the pane's task is completed and not
  awaiting. A **hex literal, not a colour name**: Textual's markup parser knows
  CSS colour names only, and an unknown name fails silently — the span keeps the
  unresolved string (so no span-level assertion can see it) while the compositor
  paints the default foreground and drops the `bold`. `#1e90ff` is CSS
  `dodgerblue`; plain CSS `blue` would be `#000080`, only a 1.1:1 contrast ratio
  against the `#1a1a1a` card background and effectively invisible. The style is
  named once as `monitor_shared.STATE_STYLE_DONE`; its value is ratified and its
  rendering proved composited in `tests/test_markup_colour_contract.py`.
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
  `title` / `status` fields for the mobile client. `awaiting_input_kind` is an
  **open** string on the wire: adding a pattern adds a value, which needs no
  protocol `v` bump (`aidocs/applink/protocol.md` "Versioning" — clients ignore
  what they don't recognise). *Renaming or removing* one is the breaking edit,
  because a client keying off a specific value silently stops matching.
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
