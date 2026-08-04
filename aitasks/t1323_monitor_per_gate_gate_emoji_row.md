---
priority: medium
effort: medium
depends: [1322]
issue_type: enhancement
status: Ready
labels: [tui, monitor]
gates: [risk_evaluated]
anchor: 1322
created_at: 2026-07-29 11:05
updated_at: 2026-07-29 11:05
boardidx: 83968
---

## Problem

`ait monitor` and `ait minimonitor` already show gate state on a task-bound
agent card — but only as an **aggregate count**, e.g. `gates: 3/4 pass, 1
pending`. That answers "how many" but never "**which**": the user cannot tell
from the card whether `risk_evaluated` passed and `docs_updated` is pending, or
the reverse. Answering that today means opening the task-info dialog or reading
the task file's `## Gate Runs` blocks.

Show the **per-gate** state as emoji at the **start of the agent card's second
line**, in both TUIs.

## Current state (verified)

**Gate display already exists — this task changes its granularity and
placement, it does not add gate-awareness from scratch.**

- `monitor_app.py:1276-1287` (`_format_agent_card_text`) appends the summary to
  the **end of line 1**, after the status badge:
  ```python
  gates = self._gate_cache.summary_for(info)
  if gates:
      text += f"  [dim]gates: {gates}[/]"
  text += f"\n     [dim italic]t{task_id}: {info.title}[/]"
  ```
  The inline comment states the end-of-row-1 placement is deliberate ("keeps
  the card compact in the full monitor; minimonitor keeps it on a separate line
  — its rows are too narrow to append here").
- `minimonitor_app.py:632-646` (`_agent_card_text`) puts it on a **third**
  line: line 1 = dot/shadow/compare-glyph/name/status, line 2 = truncated task
  title, line 3 = `gates: …`.
- Both go through `GateSummaryCache.summary_for` (`monitor_core.py:2421`,
  keyed by `(st_mtime_ns, st_size)` of `TaskInfo.task_file_abs`) →
  `lib/gate_ledger.py:276` `compact_gate_summary(state)`.

**The per-gate detail is already parsed and thrown away.**
`compact_gate_summary` reduces `state.current` — a `dict[gate_name, GateRun]`
holding the **last run per gate** — to counts:

```python
runs = [r for r in state.current.values() if r.name not in state.filtered_gates]
...
parts = [f"{n_pass}/{total} pass"]
```

`lib/gate_ledger.py:62` already defines the icon vocabulary:

```python
ICONS = {"pass": "✅", "fail": "❌", "pending": "⏸",
         "running": "🔄", "skip": "⏭", "error": "⚠"}
```

So a per-gate emoji row needs **a new formatter beside `compact_gate_summary`
and nothing else** — no new parsing, no new file reads, no new cache.

**Semantics that must be preserved from `compact_gate_summary`:** runs of
profile-filtered gates (`state.filtered_gates`, t635_33) are excluded — a
failed historical run of a now-inactive gate must not surface as unmet. Its
docstring also notes the summary is derived from recorded runs
(`state.current`), **not** `declared_gates`, which is empty framework-wide
today; a declared-based enumeration would render an empty row for every task.

**Constraints on the second line.** Emoji are double-width and the second line
is already occupied: in minimonitor it holds the task title truncated at 30
chars inside a narrow docked column (window names truncate at 22,
`minimonitor_app.py:636`); in the full monitor line 2 is
`     t<id>: <title>` (5-space indent, dim italic). A row of N gate emoji with
per-gate identity must fit both without pushing the title off-screen.

**Docked followed-agent panel is out of scope by design.**
`minimonitor_app._own_agent_identity_text` (`:648`) is deliberately static — no
live dot, no compare glyph, no shadow glyph, built once
(`_own_panel_built`, `:242`). Gate emoji belong to the refreshing general list
only, unless the plan explicitly argues otherwise.

## Goal

From the agent list alone, the user can see which of a task's gates have
passed, which are pending, and which failed — without opening a dialog.

## Acceptance criteria

1. **New per-gate formatter** lives next to `compact_gate_summary` in
   `lib/gate_ledger.py`, takes a `TaskGateState`, and returns a per-gate emoji
   string built from `ICONS` and `state.current`. It applies the same
   `filtered_gates` exclusion and the same "derive from recorded runs, not
   `declared_gates`" rule, and returns `""` for an ungated task so the row is
   omitted entirely.
2. **Gate identity is legible.** The emoji alone cannot say *which* gate — the
   plan must choose and justify how each emoji is attributed (short gate
   prefix, ordered positional convention with a legend, tooltip/dialog, or
   similar) and that choice must survive more than two declared gates.
3. **Placement.** The row is rendered at the **start of the agent card's second
   line** in both `monitor_app._format_agent_card_text` and
   `minimonitor_app._agent_card_text`. Line 1 in the full monitor no longer
   carries the aggregate `gates: …` string (or the plan states why both are
   kept).
4. **Width budget.** A stated maximum width, honouring emoji double-width, with
   a defined overflow fallback when a task has more gates than fit — verified
   at minimonitor's real docked column width, not just a wide terminal.
   Truncation must never corrupt the row into a partial glyph.
5. **Terminals without emoji support** degrade to something readable rather
   than mojibake or misaligned columns; the fallback path is exercised by a
   test.
6. **No new I/O.** The existing `GateSummaryCache` (mtime-identity keyed) is
   reused. Minimonitor still `clear()`s it every refresh
   (`minimonitor_app.py:438`) while the full monitor deliberately does not
   (`monitor_app.py:892`) — do not change either cadence as a side effect.
7. **Tests.** Render-level assertions on the produced second line for: no
   gates, all pass, mixed pass/pending/fail, a filtered gate present in history,
   and the overflow case — for **both** card builders.
8. **Docs.** The emoji vocabulary and its placement are documented (gate docs
   and/or `aidocs/framework/monitor_idle_and_prompt_detection.md`), and the
   in-TUI legend from t1322 is extended to cover the gate row.

## Coordination

Depends on **t1322** (`monitor_completed_agent_status`), which introduces the
COMPLETED status, the `TaskInfoCache` freshness fix, and the first render-level
tests + status legend for these same two card builders. Land t1322 first so
this task extends a fresh `TaskInfo` and an existing test harness rather than
racing both changes through the same two functions.

Read `aidocs/framework/tui_conventions.md` before implementing.
