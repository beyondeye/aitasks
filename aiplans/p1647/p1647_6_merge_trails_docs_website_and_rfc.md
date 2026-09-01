---
Task: t1647_6_merge_trails_docs_website_and_rfc.md
Parent Task: aitasks/t1647_merge_trails_skill_shared_helpers_board_command_docs.md
Sibling Tasks: aitasks/t1647/t1647_1_*.md … t1647_5_*.md
Worktree: (none — profile 'fast', current branch)
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: t1647_6 — Merge-trails documentation (website + RFC)

## Context

Document the finished feature: board `F` command + dialogs (t1647_5), the
`/aitask-merge-trails` skill (t1647_4), the merge workflow, and the RFC merge
flow. Current-state prose only
(`aidocs/framework/documentation_conventions.md`): no version history, no
"new in" phrasing; folded-trail language is "merged / incorporated /
retired" — never "superseded / replaced"; describe supported agents
generically.

**Coordination:** t1603_5 (Implementing at planning time) edits OTHER
sections of `reference.md` (Task Card Anatomy ~94, View Filters ~196, Task
Metadata Fields ~397) — disjoint from this child's sections, same file.
Re-verify anchors against the landed state before editing.

## Steps

1. **`website/content/docs/tuis/board/reference.md`**
   - By-Trail section (~L242-341): document `F` alongside the existing
     five-key "Keeping the view current" table — a new row or adjacent
     paragraph: what it does (opens the fold picker, then a confirmation,
     then launches the merge agent), its cost (an agent run — the slowest
     class, like `R`), its visibility conditions (only with an active trail
     and at least two trails), and that the merge itself happens in the
     launched skill after its own confirmation — the board never writes the
     trail.
   - Modal Dialogs Reference table (~L499): the table lists NO trail modals
     today — close the gap with four rows: **Trail Select** (`s` in
     By-Trail — pick which trail the view shows), **Trail Detail** (`Enter`
     on a trail card — entry-first projection, `a` reveals withheld
     material), **Trail Merge (pick)** (`F` in By-Trail — choose the trail
     to fold into the active one; the active trail is excluded), **Trail
     Merge Confirm** (confirming the pick — names survivor, retired trail,
     shared-entry count).
2. **`website/content/docs/tuis/board/how-to.md`** — By-Trail block
   (~L210-245): a short "Merge two trails" how-to: enter By-Trail (`z`),
   select the SURVIVING trail (`s`), press `F`, pick the trail to fold,
   confirm, and let the launched agent complete its own confirmation; the
   view reloads when the merged version lands.
3. **`website/content/docs/workflows/implementation-trails.md`** — new
   "Merging Two Trails" section:
   - When to merge: a duplicate trail discovered late; a feature whose
     scope expanded across two trails. Overlap alone is not a reason —
     overlapping trails are legitimate; merging is always an explicit
     choice.
   - The three invocation shapes: board `F`; `/aitask-merge-trails
     <approximate-name>` (base candidates are presented for explicit
     selection — an approximate name never silently picks the survivor —
     then merge candidates are proposed);
     `/aitask-merge-trails <base> <folded>`.
   - Depth: the merged trail is deep if either source is deep, else lite;
     forcing lite over deep material requires confirming exactly what is
     dropped.
   - What retirement means: every task referencing the folded trail has its
     reference removed (the confirmation lists them all); the document
     remains recoverable from the task-data branch's git history; an
     interrupted retirement is resumable — re-running the merge offers only
     to complete it.
   - Link from the existing flow sections; do not restate their content.
4. **`website/content/docs/skills/aitask-merge-trails.md`** — new skill page
   (model: the `aitask-trail.md` page's structure: what it does, usage
   forms, the confirmation model, safety notes) + a row in
   `website/content/docs/skills/_index.md` (Task Creation & Analysis table,
   next to `/aitask-trail` — the list is manual).
5. **`aidocs/implementation_trail_design.md`** — add the merge flow to the
   RFC: invocation surfaces; the `aitask_trail_merge.sh`
   candidates/preflight protocol in summary (module docstrings stay the
   pinned source); `merged_from` + `generation.inputs` `other`-ref
   provenance; deep-wins; the single full-write-set confirmation, the
   post-confirmation two-handle stale-base guard (and its stated no-CAS
   residual), update-before-rm ordering, all-owner retirement, and the
   RESUME / merge_conflict states. Keep §13-A6 intact (merge is explicit
   user intent, never auto-dedup) and reference it.

## Checks

- `cd website && hugo build --gc --minify` succeeds. Hugo does NOT fail
  dead `#fragment` anchors and `--minify` unquotes `id=` — verify any
  in-page anchors by hand (project memory: hugo anchors).
- `python3 -m unittest tests.test_implementation_trail_design` still green
  (the RFC edit must not break the design-contract guard).
- Vocabulary sweep over the new prose: no "superseded/replaced" for merged
  trails; agent-generic phrasing.

## Verification

- Production build clean; new page renders under `./serve.sh` with working
  relrefs; the `_index.md` row links resolve.
- The workflows section reads as one flow with the existing page (no
  duplicated content).
