---
Task: t1957_5_docs_trail_cross_repo.md
Parent Task: aitasks/t1957_trail_cross_repo_blockers_and_linked_trails.md
Sibling Tasks: aitasks/t1957/t1957_1_*.md, aitasks/t1957/t1957_2_*.md, aitasks/t1957/t1957_3_*.md, aitasks/t1957/t1957_4_*.md
Archived Sibling Plans: aiplans/archived/p1957/p1957_*_*.md
Base branch: main
Output branch: main
---

Parent plan (decisions, linked-trail definition, risk record):
`aiplans/p1957_trail_cross_repo_blockers_and_linked_trails.md`.
The task file `aitasks/t1957/t1957_5_docs_trail_cross_repo.md` carries the full context,
reference files and line anchors.


## t1957_5 — Docs

`website/content/docs/workflows/cross_project_dependencies.md` (trail
indicator, ghost live status, linked-trail definition, jump) and
`website/content/docs/tuis/trails/` pages (+ board By-Trail mention and the
new `L` key in the keybinding table). Current-state prose only. Run
`cd website && python3 check_links.py --build`.

## Step 9 reference

After implementation and review, follow task-workflow Step 9 (merge if
applicable, archive this child; the parent t1957 archives automatically when its
last child is archived).
