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
updated_at: 2026-06-01 13:37
boardidx: 120
---

Carry-over of deferred manual-verification items from t826_4. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [x] [t826_1] From /home/ddt/Work/aitasks_mobile: `ait projects add` — PASS 2026-06-01 12:22 auto: ait projects add from aitasks_mobile now works (sibling upgraded 0.19.2->0.22.0, has aitask_projects.sh); 'Registered aitasks_mobile -> /home/ddt/Work/aitasks_mobile', exit 0
- [x] [t826_1] From aitasks_mobile: `ait create --batch --project aitasks --name cross_repo_test --type chore --priority low --effort low --commit` — PASS 2026-06-01 13:31 verified: ran from aitasks_mobile with --desc added; created aitasks/t897_cross_repo_test.md (chore/low/low, committed 4ae24fd4), confirmed content, then deleted test task (commit e1057eb4). Cross-repo creation works on sibling 0.22.0.
- [x] [t826_2] Select inactive project (`ait monitor` → `j` switcher → highlight `aitasks_mobile` → Enter) — PASS 2026-06-01 13:37 user-verified in an attached tmux session: ait monitor -> j switcher -> select inactive aitasks_mobile -> Enter spawned the tmux session and switcher teleported into it
- [x] [t826_3] `cd website && hugo build --gc --minify` — PASS 2026-06-01 12:22 auto: hugo build --gc --minify exit 0, built 203 pages (only deprecation warnings)
- [x] [t826_3] `cd website && ./serve.sh` — PASS 2026-06-01 12:22 auto: hugo server starts ('Web Server is available'); /docs/workflows/multi_project/ returns HTTP 200, title 'Multi-Project Workflow | aitasks'
- [x] [t826_3] Multi-project page contains all 7 required sections (Why / project: block / ait projects / aitask_create --project / cross-repo notation / TUI switcher behavior / Recipe) — PASS 2026-06-01 12:22 auto: all 7 sections present — Why logical project names / Per-project identity (project: block) / The ait projects command / Creating a task in a sibling project (--project) / Referring to cross-project tasks and files (notation) / Switching between projects (TUI switcher) / Recipe
- [x] [t826_3] Multi-project page explicitly states `ait monitor` is unchanged (live sessions only) — PASS 2026-06-01 12:22 auto: page states 'ait monitor is intentionally unchanged — its multi-project view stays scoped to live tmux sessions only'
- [x] [t826_3] Cross-repo notation documented with no-`t` form as preferred default (`aitasks#835_3`), `aitasks#t835_3` also accepted — PASS 2026-06-01 12:22 auto: notation documented — '<project>#835_3 (preferred)', '<project>#t835_3 the leading t is also accepted'
- [x] [t826_3] Cross-link from `aidocs/cross_repo_references.md` to the website page works — PASS 2026-06-01 12:22 auto: aidocs/cross_repo_references.md 'See also' references website/content/docs/workflows/multi_project.md (file exists, builds, serves HTTP 200)
