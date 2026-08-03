---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitor, aitask_monitormini, tmux]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-08-03 11:29
updated_at: 2026-08-03 11:39
---

Renaming a tmux agent window away from the `agent-` prefix degrades both
monitor TUIs. Observed live in the `thinkingapp` session after renaming
window 7 from `agent-explore-1` to `noam_bugs`:

- **minimonitor** stopped listing that window entirely (it disappeared from
  the agent list, with no fallback section to catch it).
- **`ait monitor`** moved it into the `OTHER` section, but shows **two** cards
  for it: `noam_bugs(1)` — the real codeagent pane — and `noam_bugs(2)` — the
  companion **minimonitor pane**, which must never be listed.

(The minimonitor's own static top pane still showing the old window name is
expected and out of scope — that content is captured once and not re-read.)

## Root cause

`PaneMonitor.classify_pane()` (`.aitask-scripts/monitor/monitor_core.py:1466`)
classifies purely by window-name prefix: `DEFAULT_AGENT_PREFIXES = ["agent-"]`
→ `AGENT`, else a `TUI_NAMES` match → `TUI`, else `OTHER`. A user rename flips
every pane in the window to `OTHER` in one step, and every downstream
`category == PaneCategory.AGENT` check silently changes behaviour.

## Defect A — companion pane leaks into monitor's OTHER list

`_parse_list_panes()` (`monitor_core.py:1536`):

```python
category = self.classify_pane(window_name)
# Filter companion panes (minimonitor/monitor) in agent windows
if category == PaneCategory.AGENT and _is_companion_process(pane_pid):
    continue
```

The companion test `_is_companion_process(pid)` (`monitor_core.py:245`) is
name-independent — it inspects `/proc/<pid>/cmdline` (with a `ps` fallback) for
`_COMPANION_KEYWORDS`. It would still correctly identify the minimonitor pane
after the rename; it is the **`category == PaneCategory.AGENT` gate** that stops
it from being consulted, so the companion pane survives into `panes` and gets
rendered as the second `OTHER` card.

Note the contrast with the shadow-helper filter a few lines above (`:1515`),
which is applied unconditionally before classification and therefore is *not*
affected by a rename. The companion filter should be equally unconditional: a
minimonitor/monitor companion pane is a helper regardless of what its window is
called.

## Defect B — minimonitor has no OTHER section

`monitor_app.py` builds a three-way zoned list and renders an `OTHER (n)` zone
(`monitor_app.py:1572-1666`, card text via `_format_other_card_text` at
`:1561`). `minimonitor_app.py` has **no** `PaneCategory.OTHER` handling at all —
every list-building and counting site filters to `AGENT` only:

- `:520` — `_find_own_agent_snapshot()`
- `:573` — `_rebuild_session_bar()` agent counts
- `:627` — `_compute_completed_panes()`
- `:768` — `_rebuild_pane_list()` (the main card list)
- `:1227` — project/session resolution path

So a renamed window is invisible in minimonitor. It needs an equivalent
uncategorized/"other" section so such windows remain reachable, mirroring the
full monitor.

## Defect C (collateral) — own-agent panel goes stale in a renamed window

`_find_own_agent_snapshot()` (`minimonitor_app.py:506`) matches on
`category == PaneCategory.AGENT` **and** `window_index`. Inside the renamed
window it returns `None`, so `_rebuild_own_panel()` returns early at `:743`
("not resolved yet — try again next cycle") and the docked `#mini-own-agent`
"this agent" panel is never rebuilt — it keeps whatever it last rendered.
Any keybinding that resolves its target through this helper (e.g. the shadow
target, per the monitor-only guard comment at `monitor_app.py:2684-2690`) is
affected the same way.

## Scope

1. **Fix A** — make the companion-pane filter unconditional in
   `_parse_list_panes`, so `_is_companion_process` decides on its own. Confirm
   no consumer depends on companion panes appearing as `OTHER`.
2. **Fix B** — add an uncategorized/"other" section to minimonitor, mirroring
   `monitor_app.py`'s OTHER zone (rendering, counting, and focus/selection
   behaviour appropriate to minimonitor's narrower layout — see the row-width
   constraints tracked in t1351).
3. **Fix C** — decide and implement the correct behaviour for the own-window
   agent inside a renamed window (see the design question below).

## Design question to settle during planning

Should a renamed window's codeagent pane keep being treated as an **AGENT**?

Two candidate directions, to be weighed in the plan:

- **Name-independent agent detection** — classify by process (the same kind of
  `/proc/<pid>/cmdline` inspection `_is_companion_process` already does, or a
  pane-scoped tmux user option stamped at spawn time, like the
  `@aitask_shadow_target` marker at `monitor_core.py:266+`). This would make
  renames harmless for A, B **and** C at once, and would keep task-id
  resolution working where the name still encodes one.
  Caveat: `_TASK_ID_RE` (`monitor_core.py:2697`) parses the task id out of the
  window name, so a renamed window loses its task binding regardless — that
  part cannot be recovered from the name and would need the same stamp-at-spawn
  treatment.
- **Keep prefix classification, add the OTHER fallback** — accept that a
  renamed window is "uncategorized" by design (the user renamed it precisely to
  take it out of the agent rotation) and only ensure it stays *visible* and that
  companion panes stay hidden.

The reported symptoms are satisfied by the second, cheaper direction plus Fix A;
the first is the durable fix. Planning should pick one explicitly rather than
leaving the prefix coupling implicit.

## Verification

- Unit coverage for `_parse_list_panes`: a companion-process pane in a
  non-`agent-` window must be filtered out (currently it is not). Existing
  neighbours: `tests/test_monitor_rename_window_target.sh`,
  `tests/test_monitor_shadow_zone.py`, `tests/test_multi_session_monitor.sh`.
- minimonitor rendering coverage for the new other section
  (`tests/test_multi_session_minimonitor.sh` and the `test_minimonitor_*.py`
  family).
- Live check: rename an `agent-*` window in a running session and confirm
  (a) minimonitor still lists it, (b) `ait monitor` shows exactly one OTHER
  card for it, (c) the minimonitor inside that window behaves per the decision
  taken on Fix C.
