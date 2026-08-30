---
Task: t1603_5_website_docs_board_planned_lane_and_phases.md
Parent Task: aitasks/t1603_surface_deferred_plan_marker_on_the_board.md
Sibling Tasks: aitasks/t1603/t1603_1_*.md, aitasks/t1603/t1603_2_*.md, aitasks/t1603/t1603_3_*.md, aitasks/t1603/t1603_4_*.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1603_5 — Website documentation

## Context

Children t1603_1..t1603_4 add a card badge, a detail row, a fourth in-flight
lane, workflow-phase chips, compact gate progress and an expanded gate section.
None of it is documented for users.

This is layer 5 of the "Adding a new frontmatter field" checklist in
`aidocs/framework/aitasks_extension_points.md`, whose closing sub-bullet reads:
*"This checklist, and (when the board renders the field) the board
`tuis/board/reference.md` row."* The board now renders it.

Depends on t1603_4 — this documents finished behaviour, not a moving target.

## ⚠ Path correction

The parent t1603 named `.aitask-scripts/tuis/board/reference.md`. **That path
does not exist.** The real document is
`website/content/docs/tuis/board/reference.md` (Hugo, `{{< relref >}}`
shortcodes). A generated mirror lives at `website/public/docs/tuis/board/` —
**never edit that**.

## Implementation Steps

### 1. Card badge — `### Task Card Anatomy` (~:94)

A `Ready` task with an approved-but-deferred plan renders `📋 Ready · Planned`.
No timestamp on the card; the approval time is the detail view's
`Plan approved: <ts>` row under Tracking & provenance. Update the ASCII diagram;
the block already notes that lines appear only when the data exists.

### 2. The two-axes model — the load-bearing part

Model this on `### Follow-up Provenance Glyphs` (`:135-171`), which is the
closest structural precedent: its own section with a table, a "reading it" list,
a Task-Detail subsection and a closing cross-reference to the CLI surface. Do
**not** cram this into the metadata table.

State explicitly:

- lanes answer *what happens next*; chips answer *where the task sits in the
  workflow*;
- **each task sits in exactly one lane with exactly one chip**;
- "independent" means neither axis determines the other — **not** that a task
  appears twice.

Carry all four rows verbatim; without **both** pairs a reader assumes the chip
merely restates the lane:

| # | Task | Status | Phase (chip) | Lane |
|---|---|---|---|---|
| A | approve-and-stop | `Ready` + marker | `plan_approved` | **Planned** |
| B | `resume_point == IMPLEMENT` | `Implementing` | `plan_approved` | **Agent can continue** |

| # | Task | Lane | Phase (chip) |
|---|---|---|---|
| C | pending human gate | Needs your action | `awaiting_review` |
| D | `resume_point == POSTIMPL` | Needs your action | `post_impl` |

A and B are **different tasks**. Explain why they share a phase: an
approve-and-stop task reverts to `Ready` but keeps its gate ledger.

Document the four lanes (Planned first) and the five phases, including
`needs_attended_agent` and why it exists — `docs_updated` is `type: machine` but
`kind: procedure`, so only an attended agent can run it.

### 3. Gate progress — two rules that read as bugs unless stated

- the fraction's **denominator is the enforced active set**, not the declared
  `gates:` list — a profile-filtered gate is not counted at all;
- a **stale signature counts as NOT satisfied** despite a ledger `pass`, because
  the archival guard treats it that way.

Also document the expanded `Gates` section in Task Detail (reached with `enter`
on a card) and its vocabulary: `skipped` is satisfied but distinct from
`passed`, and filtered gates are listed audit-only.

### 4. Honest degradation

Under a profile that records no gates, the view derives what it can from status,
plan presence and the marker, and says so. An `Implementing` task with neither a
ledger nor a plan file reports `implementing (unknown)` with **no** fraction.
Say plainly that "unknown" means *we cannot tell how far it got*, not *it has
not started*.

### 5. Frontmatter tables

Add `plan_approved_at` to `website/content/docs/development/task-format.md`
`### Frontmatter Fields`, and to the board reference's `### Task Metadata
Fields` (~:397) marked **Read-only** — written and cleared exclusively by the
task-workflow; the board offers no edit affordance.

Cross-reference `website/content/docs/commands/task-management.md`, which
already documents the `ait ls -v` `Plan: approved <ts>` segment (~:120).

## Verification

- `cd website && hugo build --gc --minify` succeeds (Hugo extended >= 0.155.3);
- every `{{< relref >}}` resolves — a broken one fails the build;
- **grep each documented literal** (lane titles, phase names, status glyphs)
  against `.aitask-scripts/board/aitask_board.py` rather than trusting the
  prose;
- rows A–D match the fixtures asserted in t1603_3's tests;
- current-state-only, no version history in the body
  (`aidocs/framework/documentation_conventions.md`);
- `website/public/` not hand-edited.

## Risk

### Code-health risk: low
- Documentation only; no source changes. · severity: low · → mitigation: none
  (accepted residual)

### Goal-achievement risk: medium
- Documented strings can drift from the shipped ones, which is exactly how doc
  rot starts; the grep-each-literal step is the guard, and it is manual.
  · severity: medium · → mitigation: none (accepted residual — a rendered-string
  drift test would belong to t1603_3, not to a docs task)

## Step 9 (Post-Implementation)

Standard closure: commit, merge per the plan header, archive the task and plan.
