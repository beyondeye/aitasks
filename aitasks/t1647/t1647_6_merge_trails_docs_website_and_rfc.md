---
priority: medium
effort: medium
depends: [t1647_5]
issue_type: documentation
status: Ready
labels: [trails, web_site, docs]
gates: [risk_evaluated]
anchor: 1647
created_at: 2026-09-01 18:51
updated_at: 2026-09-01 18:51
---

## Context

Sixth child of t1647 (trail-to-trail merge). Document the finished feature:
the board `F` command + dialogs (t1647_5), the `/aitask-merge-trails` skill
(t1647_4), the merge workflow, and the RFC's merge flow. Current-state prose
only (aidocs/framework/documentation_conventions.md — no version history, no
"new in" phrasing).

**Coordination:** t1603_5 (Implementing at planning time) edits OTHER
sections of `website/content/docs/tuis/board/reference.md` (Task Card
Anatomy ~94, View Filters ~196, Task Metadata Fields ~397). Disjoint from
this child's sections, but same file — re-verify section anchors against the
landed state before editing.

## Files

1. `website/content/docs/tuis/board/reference.md`
   - By-Trail section (~L242-341): document `F` — add it to the
     "Keeping the view current" key table or an adjacent paragraph, with
     the cost note (launches an agent; the merge happens in the launched
     skill after its own confirmation, never in the board) and the
     visibility conditions (active trail + ≥2 trails).
   - Modal Dialogs Reference table (~L499): the table currently lists NO
     trail modals — close the gap: add rows for **Trail Select** (`s` in
     By-Trail), **Trail Detail** (`Enter` on a trail card), **Trail Merge
     (pick)** (`F` in By-Trail), **Trail Merge Confirm** (confirming the
     pick).
2. `website/content/docs/tuis/board/how-to.md` — By-Trail block
   (~L210-245): a "merge two trails" how-to (focus the surviving trail,
   `F`, pick, confirm, agent completes; where the result appears).
3. `website/content/docs/workflows/implementation-trails.md` — new
   "Merging Two Trails" section: when to merge (duplicate trail; expanded
   scope), the deep-wins depth rule and the downgrade confirmation, what
   retirement means (EVERY referencing task's entry is removed; the
   artifact remains recoverable from data-branch git history), the
   resumable retirement behavior, and the three invocation shapes
   (board `F`, `/aitask-merge-trails <approx-name>`,
   `/aitask-merge-trails <base> <folded>`). Link from the existing flow
   sections; do not restate their content.
4. `website/content/docs/skills/aitask-merge-trails.md` — new skill page
   (model: `aitask-trail.md` sibling page) + a row in
   `website/content/docs/skills/_index.md` (Task Creation & Analysis
   table, next to `/aitask-trail` — the list is manual).
5. `aidocs/implementation_trail_design.md` — add the merge flow to the RFC:
   invocation surfaces, the candidates/preflight line protocol (summary,
   pointing at the module docstrings as the pinned source),
   `merged_from` + `generation.inputs` provenance, deep-wins, the
   confirmation + stale-base guard + all-owner retirement semantics, and
   the RESUME/merge_conflict states. Keep §13 (alternatives) consistent:
   merge is explicit user intent, never auto-dedup (A6 stands).

## Tests / checks

- `cd website && hugo build --gc --minify` succeeds. Hugo does NOT fail on
  dead `#fragment` anchors and `--minify` unquotes `id=` — verify any
  in-page anchors manually (project memory: hugo_anchor_checks).
- `python3 -m unittest tests.test_implementation_trail_design` still green
  (the RFC edit must not break the design-contract guard).
- Grep sweep: no "superseded/replaced" language for folded trails — use
  "merged/incorporated/retired" per the folded-task vocabulary; describe
  the supported agents generically per documentation_conventions.

## Verification

- Hugo production build clean; new page renders in the local dev server
  (`cd website && ./serve.sh`) with working relrefs.
- The skills index row links resolve; the workflows page section reads as
  one flow with the existing page.

Parent plan: `aiplans/p1647_merge_trails_skill_shared_helpers_board_command_docs.md`.
