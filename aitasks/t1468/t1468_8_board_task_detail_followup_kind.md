---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [aitask_board, tui, task_metadata]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1468
implemented_with: claudecode/opus5
created_at: 2026-08-12 19:07
updated_at: 2026-08-14 12:56
---

## Context

Parent: t1468 — mark auto-spawned follow-up tasks with a machine-readable kind.
Depends only on **t1468_1** (the `followup_kind:` field and
`.aitask-scripts/lib/followup_kinds.py`), which is archived — so this child is
**independent of the t1468_5 → t1468_6 → t1468_7 chain** and can be picked
immediately. Created with `--no-sibling-dep` for exactly that reason.

Read the parent plan
`aiplans/p1468_mark_followup_task_provenance_and_surface_on_board.md`.

## Problem

Every `followup_kind` surface the board has is a **card** surface:

- `TaskCard.compose` (`board/aitask_board.py:3054-3057`)
- `InFlightTaskCard.compose` (`:3210-3213`)
- `TrailTaskCard.compose` (`:3437-3439`)
- `GroupHeader._followup_rollup` (`:2671-2696`)

All four render the glyph via `_followup_marker` (`:3338`) /
`_followup_glyph_text` (`:3372`).

**`TaskDetailScreen` (`:5808`) shows nothing.** Its metadata block renders
priority, effort, status, `issue_type`, both `risk_*` fields, depends, xdeps,
verifies, parent, children, folded, anchor, labels, `assigned_to`, issue, PR,
contributor, `implemented_with` and dates — and no `followup_kind`, read-only or
editable. `_original_values` (`:5846-5851`) carries exactly four editable keys
(priority / effort / status / issue_type), surfaced as `CycleField`s at
`:6042`, `:6045`, `:6049`, `:6052`.

So opening a task tells you nothing about its provenance, and the glyph on the
card is undecodable without one — **the board has no legend anywhere** (the
glyph contract lives only in `lib/followup_kinds.py` and the comment at
`aitask_board.py:65`).

The asymmetry that makes this worth fixing: `aitask_update.sh` already accepts
`--followup-kind`, so the CLI can set and correct the field, while the board —
where a mis-classified follow-up is actually noticed — can neither show nor
change it. t1468_6 will backfill ~95 historical follow-ups by heuristic; spot-
correcting those from the board is the natural review loop, and it does not
exist.

## Goal

Show `followup_kind` in the task detail screen, and make it editable there.

## Design decisions to settle in the plan

### 1. Editable, not read-only

Recommended: editable. The backfill review loop above is the justification. If
the plan chooses read-only, state why and how a user is expected to correct a
wrong kind without leaving the board.

### 2. Widget choice — `CycleField` does not obviously fit

The existing four editable fields cycle over 3-9 short options.
`followup_kind` has **8 values plus unset**:
`manual_verification`, `risk_mitigation`, `upstream_defect`,
`verification_failure`, `carry_over`, `qa_test_gap`, `review_finding`,
`docs_gap` (canonical order and per-kind glyph/colour in
`lib/followup_kinds.py`; never re-declare the vocabulary here — import it, as
`_followup_marker` does).

Cycling nine options to reach the one you want is poor UX. Evaluate a picker
modal instead — `IssueTypeFilterScreen` (`:5416`) is the nearest precedent —
against the cost of a second interaction. Record the trade-off.

Show the glyph alongside the name wherever the value is displayed, so the card
glyph becomes decodable from the detail screen. That is a large part of the
value here.

### 3. Keep it visually distinct from `issue_type`

`followup_kind` is deliberately **orthogonal** to `issue_type` — that
separation is what t1468 spent its design budget establishing (an upstream
defect genuinely *is* a bug; a mitigation may be a refactor). Render them as
two clearly distinct rows. Do not group, merge, or imply one derives from the
other.

## Sharp hazards

### Clearing the field is not a value assignment

`save_changes` (`:6144-6150`) does `self.task_data.metadata[key] = value` for
each changed key, then `save_with_timestamp()`. There is **no delete path**.
Selecting "none / not a follow-up" must *remove* the key, not write `""` or
`"none"` — an empty or sentinel value would be written into frontmatter and
then normalize back through `normalize_followup_kind` as an unknown kind
(`UNKNOWN_GLYPH` on every card). Decide the representation and implement the
removal explicitly.

### The dirty-check trips on unset

`_original_values` (`:5846-5851`) seeds each key with a **non-empty** default
(`"medium"`, `"Ready"`, `"feature"`). `followup_kind` is legitimately absent on
most tasks, so `None` vs `""` must be represented consistently on both sides of
`_current_values != self._original_values` (`:6120`) — otherwise the Save
button lights up the moment the screen opens on any non-follow-up task, with
nothing changed.

### Read-only mode

`TaskDetailScreen(read_only=True)` is used for archived and folded tasks
(`:4431`, `:5339`; gate at `:6034` `is_done_or_ro`). The new field must render
as a plain line there, never as an editable control — follow the `AnchorField`
precedent (`:4501-4520`), which is editable in the live screen and a read-only
line otherwise.

### Totality over the vocabulary

`_followup_marker` (`:3338-3368`) is documented as *"the board's totality
boundary over `followup_kind`"* — it normalizes through
`normalize_followup_kind` and falls back to `UNKNOWN_GLYPH` for a value outside
the vocabulary. Route the detail screen's display through that same boundary
rather than indexing `FOLLOWUP_KINDS` directly, so a hand-edited or
future-vocabulary value degrades identically on the card and in the detail
screen.

## Verification

1. A task with each of the 8 kinds renders its kind and glyph in the detail
   screen; a task with no `followup_kind` renders the unset state and does
   **not** mark the screen dirty on open.
2. Setting a kind from the board writes exactly `followup_kind: <value>` to
   frontmatter, and the card glyph updates on the next render.
3. Clearing the kind **removes the key** — assert the line is absent from the
   file, not present-and-empty. Re-open and confirm the unset state round-trips.
4. A value outside the vocabulary (hand-edited into a fixture) degrades to the
   same unknown marker in the detail screen as on the card — drive this case,
   do not assume it.
5. Read-only screens (archived / folded) show the kind as a plain line with no
   editable control.
6. Verify at render level (`render().plain`, plus composited strips for width
   **and** colour — a span cannot see an unresolved colour name), not by
   reading source. Note `lib/followup_kinds.py` carries a literal Rich style per
   kind; confirm each resolves in Textual (the t1453 class of defect).
7. `bash tests/run_all_python_tests.sh` — read the LAST line for the verdict.

## Coordination

- **t1468_5 / _6 / _7** — no dependency in either direction. t1468_6's backfill
  makes this screen more useful, and this screen makes t1468_6's output
  reviewable, but neither blocks the other.
- **t1470** (`surface_intrawave_parallel_safety_in_bytrail_view`) consumes
  `followup_kind` in the By-Trail view via the same `_followup_marker` seam.
  Display-only there; no overlap with this child's edit path, but both touch
  `aitask_board.py` — check the tree before starting.
- **t1243 children** (`_11`, `_12`) also edit `aitask_board.py`; `t1243_12`
  touches `TaskDetailScreen` directly. Sequence against it.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-14T09:56:18Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-14T12:48:38Z status=pass attempt=1 type=human
