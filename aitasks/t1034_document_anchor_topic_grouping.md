---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: documentation
status: Implementing
labels: [documentation]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1016
created_at: 2026-06-18 16:46
updated_at: 2026-06-29 12:02
boardidx: 290
---

## Goal

Author a user-facing **narrative** website page for the anchor / topic-grouping
feature introduced by t1016. Today the only website coverage is two isolated
table rows — the `anchor` frontmatter row in
`website/content/docs/development/task-format.md` (t1016_2) and the board
`by-topic` base-filter row in `website/content/docs/tuis/board/reference.md`
(t1016_4). There is no prose page explaining the concept or its workflow.

This task is anchored to t1016 via `--followup-of 1016` (so `anchor: 1016`); it
is NOT a child of t1016 and does not block t1016's archival. It intentionally
groups under the archived root 1016 on the board's by-topic view (dogfooding the
"archived anchor root is a stable group key" case).

## Scope

Create a new page under `website/content/docs/workflows/` (e.g.
`anchor-topic-grouping.md` / `topic-anchoring.md`) covering:

- **The anchor concept** — what an anchor / topic group is, and why it exists
  (organize loosely-related and follow-up tasks around a subject WITHOUT forcing
  a rigid parent-child tree). Position it alongside parent-child, `depends`, and
  `labels` — it complements, does not replace them.
- **The flags** — `--anchor <id>` (explicit topic-root override) and
  `--followup-of <src>` (high-level: anchor to the source task's root).
- **The inheritance rule** — flattened-to-root: a follow-up's anchor always points
  at the root and never chains; a child auto-inherits `anchor = parent.anchor-or-id`;
  `--anchor` / `--followup-of` are mutually exclusive and both rejected alongside
  `--parent`; roots emit no `anchor:` line.
- **When to use which** — anchor vs parent-child vs `depends` vs `labels`.
- **The board by-topic workflow** — the `y` base view that clusters tasks into
  per-anchor swimlanes, and the editable anchor field in the task detail screen.

## Required cross-surface updates

- Add the page's bullet to the **hand-curated** `website/content/docs/workflows/_index.md`
  grouping (the sidebar auto-builds but the index body does NOT — it is a manual
  page list).
- Add cross-links from `docs/development/task-format.md` (anchor row) and
  `docs/tuis/board/reference.md` (by-topic row) to the new page.

## Authoring guidance (project conventions)

- **Document the current source of truth**, not this proposal or any archived
  design plan: read the live `.claude/skills/task-workflow/task-creation-batch.md`
  ("Topic anchoring" section) and `aitask_create.sh` semantics when writing.
- Current-state-only prose — no version history / "added in vX" in the body.
- Use invented placeholder project names if examples need them; never the
  author's real repos. Use "cross-repo / linked repo", never "sister".
- Build check: `cd website && hugo build --gc --minify` must succeed.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-29T09:02:18Z status=pass attempt=1 type=human
