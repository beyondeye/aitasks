---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [trails, board, ui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-21 16:43
updated_at: 2026-10-21 19:10
---

## Problem

When a trail card's details are opened (Enter / double-click) — in `ait trails`
and in `ait board`'s By-Trail view — the modal shows why the task holds its
place in the wave (rationale, classification, confidence, wave purpose, drift,
narrative, observations, evidence, exclusions), but **nothing about the task
itself**: no title line, no live status/metadata, and no way to read its
description. In `ait trails` there is no other route to the task content at all;
`ait board` deliberately bypasses its own `TaskDetailScreen` for trail cards
(RFC §9.1).

## Current code

- Both hosts route Enter through `TrailScreenMixin._open_trail_entry_detail`
  (`.aitask-scripts/board/board_trail_screen.py:688`), called from
  `aitask_board.py` `action_view_details` (~4526) and `trails_app.py`
  `action_view_details` (~703).
- It pushes `TrailDetailScreen(doc, reasons, entry=, wave=)`
  (`.aitask-scripts/board/board_trail_view.py:778`). `_sections()` renders only
  trail-document fields.
- The live card (`TrailTaskCard`) already holds the `Task` as
  `card.task_data` / `card.trail_view.task` (`.content` body, `.metadata`
  frontmatter), but it is never passed to the modal.
- `build_trail_lanes` (`board_trail_view.py:268`) resolves archived members via
  `archived_lookup(local_id)` and then discards the result
  (`TrailEntryView(entry, None, "archived", …)`), so archived ghosts have no
  task object to show.
- Missing and cross-repo ghosts carry only `_GhostTaskStub` (empty metadata).
- Trail schema `entry.snapshot` (`lib/implementation_trail.schema.json`) holds
  status/priority/effort/boardcol/depends/gates_pending/followup_kind — no title
  or summary.

## Constraint from the user

**Do not append the full task description into the detail modal body** — the
modal content is already very long. A short "what is this task" header plus an
explicit control to open the full description is the desired shape.

## Proposed change

1. **Compact task header** at the top of `TrailDetailScreen` (above the
   "Entry …" section), built from the live task file (the source of truth, not
   the trail snapshot): task number + title, status, priority, effort,
   issue_type, labels. One or two lines. Zero trail-generation cost.
2. **"Description" control** — a key binding and a button in the modal that
   opens the full task description read-only in its own screen (reuse
   `lib/section_viewer.py` `SectionViewerScreen`, as `board_detail_screen.py`
   does for plans, or an equivalent read-only Markdown modal). Pick a key that
   does not collide with the modal's `a` / `escape` or confuse with the host's
   `T` trail action. Follow the existing pattern in this screen: gate it in
   `check_action` AND re-check inside the action (a binding gate is not an
   action guard).
3. **Pass the task through**: `_open_trail_entry_detail` passes the card's
   resolved task (live) into `TrailDetailScreen`. Keep the archived task on the
   `TrailEntryView` built by `build_trail_lanes` so archived ghosts can show the
   header + description too.
4. **Ghosts without a local file** (missing, cross-repo): the header states why
   no description is available; the control is hidden/disabled. (Fetching a
   cross-repo task's description via `aitask_query_files.sh --project` is
   optional — decide during planning; if deferred, say so.)
5. Respect `board_trail_view.py` import contract (C1/C2 in its module
   docstring): it resolves no task directory itself — it should receive task
   objects, not look files up.

## Explicitly out of scope (possible follow-up)

A per-entry "task in simple words" summary written into the trail document.
It would need a new schema field, a change to the `/aitask-trail` writer
(extra agent work per entry on every generate/refresh) and a staleness story
when the task file is edited after generation. The user judged that simply
making the description available is likely good enough; revisit only if the
header + description viewer proves insufficient.

## Tests

- `TrailDetailScreen` with a live entry: header shows title/metadata from the
  task file; the description control opens a screen containing the task body.
- Archived ghost: header + description available after the
  `build_trail_lanes` change.
- Missing / cross-repo ghost: no description control reachable (both via
  `check_action` and by calling the action directly); header shows the reason.
- No entry (full-trail projection): unchanged behaviour.
- Both hosts (`ait trails` `TrailsApp` and `ait board` By-Trail) open the modal
  with the task wired through.
- Existing trail-detail tests keep passing (scoping / `a` toggle / totals line).

## Related

- t1526 fixes the same modal's `line()` helper for whitespace-only values —
  same file, separate bug; coordinate if both are in flight.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-21T16:10:37Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-21T19:08:23Z status=pass attempt=1 type=human
