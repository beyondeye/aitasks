---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Implementing
labels: []
verifies: [t826_1, t826_2, t826_3]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-31 12:26
updated_at: 2026-06-01 12:22
boardidx: 120
---

Carry-over of deferred manual-verification items from t826_4. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [x] [t826_1] From /home/ddt/Work/aitasks_mobile: `ait projects add` — PASS 2026-06-01 12:22 auto: ait projects add from aitasks_mobile now works (sibling upgraded 0.19.2->0.22.0, has aitask_projects.sh); 'Registered aitasks_mobile -> /home/ddt/Work/aitasks_mobile', exit 0
- [defer] [t826_1] From aitasks_mobile: `ait create --batch --project aitasks --name cross_repo_test --type chore --priority low --effort low --commit` — DEFER 2026-06-01 12:22 auto: needs user judgment — command as written omits --desc (would re-fail 'Batch mode requires --desc or --desc-file'); running it with --desc creates+commits a real cross_repo_test task into aitasks/ (repo mutation). Defer to interactive.
- [defer] [t826_2] Select inactive project (`ait monitor` → `j` switcher → highlight `aitasks_mobile` → Enter) — DEFER 2026-06-01 12:22 auto: not autonomously reproducible — item note states the select->spawn->teleport flow needs an ATTACHED tmux client; detached driver spawns no session. Defer to interactive run from a real attached session.
- [x] [t826_3] `cd website && hugo build --gc --minify` — PASS 2026-06-01 12:22 auto: hugo build --gc --minify exit 0, built 203 pages (only deprecation warnings)
- [x] [t826_3] `cd website && ./serve.sh` — PASS 2026-06-01 12:22 auto: hugo server starts ('Web Server is available'); /docs/workflows/multi_project/ returns HTTP 200, title 'Multi-Project Workflow | aitasks'
- [x] [t826_3] Multi-project page contains all 7 required sections (Why / project: block / ait projects / aitask_create --project / cross-repo notation / TUI switcher behavior / Recipe) — PASS 2026-06-01 12:22 auto: all 7 sections present — Why logical project names / Per-project identity (project: block) / The ait projects command / Creating a task in a sibling project (--project) / Referring to cross-project tasks and files (notation) / Switching between projects (TUI switcher) / Recipe
- [x] [t826_3] Multi-project page explicitly states `ait monitor` is unchanged (live sessions only) — PASS 2026-06-01 12:22 auto: page states 'ait monitor is intentionally unchanged — its multi-project view stays scoped to live tmux sessions only'
- [x] [t826_3] Cross-repo notation documented with no-`t` form as preferred default (`aitasks#835_3`), `aitasks#t835_3` also accepted — PASS 2026-06-01 12:22 auto: notation documented — '<project>#835_3 (preferred)', '<project>#t835_3 the leading t is also accepted'
- [x] [t826_3] Cross-link from `aidocs/cross_repo_references.md` to the website page works — PASS 2026-06-01 12:22 auto: aidocs/cross_repo_references.md 'See also' references website/content/docs/workflows/multi_project.md (file exists, builds, serves HTTP 200)
