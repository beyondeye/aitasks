---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: [2367]
issue_type: feature
status: Implementing
labels: [trails, tui]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [2367]
assigned_to: dario-e@beyond-eye.com
anchor: 2175
implemented_with: claudecode/fable5_2
created_at: 2026-11-19 05:12
updated_at: 2026-11-27 02:04
---

## Context

Child of the sitrep work-directions task, independent of the store children. A direction shows its tasks inside existing implementation trails rather than generating its own trail. `ait trails` already opens a trail with one task's card focused (`ait trails --trail <handle> --task <id>`, the trails pane mailbox, `launch_or_focus_trails`), and the sitrep TUI already resolves trail membership (`sitrep_tui/sitrep_tui_trails.py` over `trail_links.export_project`).

## Scope

- **Critical path, as a pure function** (in `lib/`, importable by the trails app and by the sitrep helpers, no TUI imports): given a trail document and a highlight set of task ids, return the tasks that must land before any highlighted task — the transitive predecessors through `hard_depends` edges and wave order, with `advisory_precedes` reported as a separate, weaker class. Trace the real semantics of waves and each relation type in `lib/trail_schema.py` / the schema before fixing the rule; tasks already Done / archived are excluded from the path but reported. Highlighted tasks that are not members of the trail are returned as `not_in_trail`, never dropped silently.
- **CLI evidence**: a read verb (extend `aitask_trail_gather.sh` or `trail_links`; pick in the plan) that prints the highlight set's critical path for a trail in a line format the sitrep skill can quote: next actionable task(s), blockers, wave of each highlighted task.
- **`ait trails` overlay**: `--highlight <id,id,…>` (and the mailbox form for an already-running trails app; an older running app that does not know the form still opens the trail and says so, like the task form today). Highlighted cards and critical-path cards get distinct, documented markers that survive monochrome terminals (glyph plus style, not colour alone); the banner names the overlay ("direction: <title>, 3 highlighted, 4 on the critical path") and a key clears it. The overlay is per tab and is view state only: it never writes to the trail artifact.
- Works with the tabbed trails UI (focus restore after async re-render; see the open manual-verification task for trail tabs) and with the board's by-trail view only if that falls out of the shared renderer; otherwise leave the board out and say so.

## Tests

- Unit tests for the path function over fixture trails: a chain, a diamond, advisory-only edges, a highlighted task in a later wave with no explicit edge, done predecessors, a non-member, an empty highlight set.
- `tests/test_trails_focus_writer.py` / `test_trails_focus_mailbox_live.py` extended for the highlight form; a pilot test for the markers and the clear key.

## Docs

`aidocs/framework/tui_conventions.md` or the trails reference doc for the overlay contract; `website/content/docs/tuis/` trails page; `check_links.py --build`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-26T10:40:11Z status=pass attempt=1 type=human

> **✅ gate:plan_approved** run=2026-11-27T00:04:49Z status=pass attempt=2 type=human

> **✅ gate:review_approved** run=2026-11-27T06:39:32Z status=pass attempt=1 type=human
