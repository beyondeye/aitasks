---
priority: medium
effort: low
depends: [t1603_4]
issue_type: documentation
status: Implementing
labels: [docs, web_site, board]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1595
implemented_with: claudecode/opus5
created_at: 2026-08-30 13:29
updated_at: 2026-09-02 08:55
---

## Context

Part of t1603. Children t1603_1..t1603_4 add a card badge, a detail row, a
fourth in-flight lane, workflow-phase chips, compact gate progress and an
expanded gate section. None of that is documented for users yet.

This is layer 5 of the "Adding a new frontmatter field" checklist in
`aidocs/framework/aitasks_extension_points.md`, whose closing sub-bullet reads:
*"This checklist, and (when the board renders the field) the board
`tuis/board/reference.md` row."* The board now renders it, so the row is owed.

Depends on t1603_4 (documents the finished behaviour, not a moving target).

## ⚠ Path correction

The parent task t1603 named `.aitask-scripts/tuis/board/reference.md` in its
"Key files". **That path does not exist.** The real document is
`website/content/docs/tuis/board/reference.md` (Hugo content, uses
`{{< relref >}}` shortcodes). There is a generated mirror under
`website/public/docs/tuis/board/` — **do not edit that**.

## Key Files to Modify

- `website/content/docs/tuis/board/reference.md`
  - `### Task Card Anatomy` (~line 94) — the ASCII card diagram
  - `### Task Metadata Fields` (~line 397) — the frontmatter table
  - the in-flight material under `### View Filters` (~line 196)
- `website/content/docs/development/task-format.md` — `### Frontmatter Fields`
  table row for `plan_approved_at`
- `website/content/docs/commands/task-management.md` — cross-reference; it
  already documents the `ait ls -v` `Plan: approved <ts>` segment (~line 120)

## Reference Files for Patterns

- `website/content/docs/tuis/board/reference.md:135-171`
  `### Follow-up Provenance Glyphs` — the closest structural precedent: a
  dedicated section with a glyph table, a "Reading the glyphs" list, a
  "Reading and changing the kind in Task Detail" subsection, and a closing
  cross-reference line to the CLI surface. Model the phase/lane documentation on
  this rather than cramming it into the metadata table.
- `website/content/docs/tuis/board/reference.md:342-348`
  `#### Add-on filters (toggle)` — the table shape if a filter is added.

## What to document

### 1. The card badge

A `Ready` task carrying an approved-but-deferred plan renders
`📋 Ready · Planned`. No timestamp on the card — the approval time is in the
detail view's "Tracking & provenance" section as `Plan approved: <ts>`. Update
the Task Card Anatomy diagram; note (as that block already says) that lines
appear only when the corresponding data exists.

### 2. The two-axes model — this is the load-bearing part

The reference **must** state:

- lanes answer *what happens next*; chips answer *where the task sits in the
  workflow*;
- **each task sits in exactly one lane with exactly one chip**;
- "independent" means neither axis determines the other — **not** that a task
  appears twice.

And it must carry all four worked rows verbatim, because without **both** pairs
a reader will assume the chip merely restates the lane:

*Same phase, different lanes* (the lane is not derivable from the phase):

| # | Task | Status | Phase (chip) | Lane |
|---|---|---|---|---|
| A | approve-and-stop | `Ready` + marker | `plan_approved` | **Planned** |
| B | in-flight, `resume_point == IMPLEMENT` | `Implementing` | `plan_approved` | **Agent can continue** |

*Same lane, different phases* (the phase is not derivable from the lane):

| # | Task | Lane | Phase (chip) |
|---|---|---|---|
| C | pending human gate | Needs your action | `awaiting_review` |
| D | `resume_point == POSTIMPL` | Needs your action | `post_impl` |

A and B are two **different tasks**. Explain why they share a phase: an
approve-and-stop task reverts to `Ready` but keeps its gate ledger.

Document the four lanes (`Planned` first, then the three existing) and the five
phases, including `needs_attended_agent` and why it exists (`docs_updated` is
`type: machine` but `kind: procedure`, so only an attended agent can run it).

### 3. Gate progress — the two surprising rules

Both need stating explicitly or they read as bugs:

- the progress fraction's **denominator is the enforced active set**, not the
  declared `gates:` list — a profile-filtered gate is not counted at all;
- a **stale signature counts as NOT satisfied**, even though the ledger shows
  `pass`, because the archival guard treats it that way.

Also document the expanded `Gates` section in Task Detail (reached with `enter`
on a card) and its status vocabulary, including that `skipped` is satisfied but
distinct from `passed`, and that filtered gates are listed audit-only.

### 4. Honest degradation

Under a profile that records no gates, the view derives what it can from status,
plan presence and the marker, and says so. An `Implementing` task with neither a
ledger nor a plan file reports `implementing (unknown)` with **no** fraction —
document that "unknown" means *we cannot tell how far it got*, not *it has not
started*.

### 5. Frontmatter table

Add `plan_approved_at` to `website/content/docs/development/task-format.md` and
to the board reference's `### Task Metadata Fields` table, marked **Read-only**
— it is written and cleared exclusively by the task-workflow and the board
offers no edit affordance.

## Verification

- `cd website && hugo build --gc --minify` succeeds (Hugo extended >= 0.155.3);
- every `{{< relref >}}` target resolves — a broken relref fails the build;
- the documented lane names, phase names and status glyphs match the shipped
  strings in `.aitask-scripts/board/aitask_board.py` **exactly** (grep for each
  literal rather than trusting the prose);
- rows A–D as written match the fixtures asserted in t1603_3's tests;
- no version history in the doc body, per
  `aidocs/framework/documentation_conventions.md` (current-state-only rule);
- `website/public/` was not hand-edited.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-02T05:56:07Z status=pass attempt=1 type=human
