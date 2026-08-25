---
priority: medium
effort: low
depends: [1595]
issue_type: enhancement
status: Ready
labels: [ui, task-workflow]
gates: [risk_evaluated]
anchor: 1595
created_at: 2026-08-25 12:34
updated_at: 2026-08-25 12:34
---

## Origin

Deferred from t1595, which introduced the `plan_approved_at` frontmatter marker
("plan approved, implementation deliberately deferred") and its two read
surfaces: `ait ls -v` / `--plan-approved` and the planning step's existing-plan
prompt. t1595's own deliverable sketch names the board as a **separate task
depending on it** — this is that task.

## Problem

On the board a marked task is still indistinguishable from a never-touched one:

- the kanban card renders the same `📋 Ready` badge as an unplanned task and has
  no plan-existence indicator at all;
- the in-flight view filters `status == Implementing`, so an approved-and-stopped
  task (which is `Ready` by design) never appears there;
- `TaskDetailScreen` renders per-field widgets keyed on field name, and there is
  no widget for this one — the field is invisible in the detail view even though
  it is in the file.

This is the last surface where the parallel-planning workflow ("plan several
tasks, defer their implementations, pick them up later") is still blind.

## Key files

- `.aitask-scripts/board/aitask_board.py` — the card-status composition around
  the `📋 {status}` label (two call sites: the card and the detail screen), and
  `TaskDetailScreen.compose()` for a read-only field row.
- `aidocs/framework/aitasks_extension_points.md` — layer 3 of the "Adding a new
  frontmatter field" checklist, plus the `plan_approved_at` worked example, which
  currently records "Board layer 3 ships separately". Update it when this lands.
- `.aitask-scripts/tuis/board/reference.md` (per the same checklist's layer 5) —
  add the row once the board renders the field.

## Notes / constraints

- **Read-only surface.** The marker is written and cleared exclusively by the
  task-workflow (`plan-approved-stop.md` and the four clear sites); the board
  must not offer an edit affordance for it. It is NOT a board-owned key: it is
  deliberately absent from `BOARD_KEYS` / `BOARD_LAYOUT_KEYS`, and its merge rule
  is already wired (deletion-aware `_BASE_AWARE_FIELDS` in `board/aitask_merge.py`).
- **Visibility, not routing** — the same constraint t1595 carried from
  `aidocs/gates/ledger-driven-reentry.md`. Adding a board indicator must not
  create a path that starts implementation from a `Ready` task without going
  through the planning checkpoint and its remote drift check.
- Decide explicitly whether the in-flight view should grow a second section for
  these (they are `Ready`, so they are not in-flight in the current sense) or
  whether a card indicator alone is enough. Prefer the smaller change unless the
  parallel-planning workflow clearly needs the section.
- A card is a narrow surface — budget the indicator's width rather than
  appending a full `YYYY-MM-DD HH:MM` timestamp to the status line.

## Verification

- A task carrying `plan_approved_at` renders its indicator on the board card;
  one without it renders exactly as before (assert on the render, not on a probe).
- The detail screen shows the field for a marked task and omits the row entirely
  for an unmarked one.
- Consuming the marker (start implementation) makes the indicator disappear on
  the next board refresh.
