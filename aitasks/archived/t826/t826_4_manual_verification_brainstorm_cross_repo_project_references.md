---
priority: medium
effort: medium
depends: [t826_3]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [t826_1, t826_2, t826_3]
assigned_to: daelyasy@hotmail.com
created_at: 2026-05-25 17:23
updated_at: 2026-05-31 12:26
completed_at: 2026-05-31 12:26
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t826_1] Run `bash tests/test_project_resolve.sh && bash tests/test_projects_cmd.sh && bash tests/test_create_project_flag.sh` — PASS 2026-05-31 11:12 auto: 3 test scripts exit 0 (project_resolve/projects_cmd/create_project_flag)
- [x] [t826_1] Run `shellcheck .aitask-scripts/aitask_project_resolve.sh .aitask-scripts/aitask_projects.sh .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_ide.sh ait` — PASS 2026-05-31 11:17 auto(corrected): clean under project convention 'shellcheck --severity=error' (0 errors). Bare shellcheck emits 25 info/style notes (13 SC1091 source-follow + 12 SC2001/2012/2086/2231 info/style), no error-severity findings.
- [x] [t826_1] From /home/ddt/Work/aitasks: `ait projects add` — PASS 2026-05-31 11:12 auto: ait projects add from aitasks -> Registered aitasks; entry present in registry
- [defer] [t826_1] From /home/ddt/Work/aitasks_mobile: `ait projects add` — DEFER 2026-05-31 11:12 auto-blocked: ait projects add from aitasks_mobile fails (sibling runs ait 0.19.2, predates projects verb); entry already exists. Upgrade sibling then re-run.
- [x] [t826_1] `ait projects list` — PASS 2026-05-31 11:12 auto: ait projects list shows aitasks LIVE + aitasks_mobile OK
- [x] [t826_1] `ait projects resolve aitasks` — PASS 2026-05-31 11:12 auto: ait projects resolve aitasks -> RESOLVED:/home/ddt/Work/aitasks (correct path)
- [x] [t826_1] `ait projects exec aitasks -- pwd` — PASS 2026-05-31 11:12 auto: ait projects exec aitasks -- pwd -> /home/ddt/Work/aitasks
- [defer] [t826_1] From aitasks_mobile: `ait create --batch --project aitasks --name cross_repo_test --type chore --priority low --effort low --commit` — DEFER 2026-05-31 11:40 CARRY OVER (user choice). Real attempt failed anyway: ait create --batch --project ... --commit -> 'Error: Batch mode requires --desc or --desc-file'; sibling also on old ait 0.19.2. Earlier 't864 created' was fabricated glitch output.
- [x] [t826_1] `aitask_create.sh --project <name>` without `--batch` — PASS 2026-05-31 11:12 auto: refused with 'Error: --project requires --batch'
- [x] [t826_1] `aitask_create.sh --batch --project X --parent Y` — PASS 2026-05-31 11:12 auto: refused with 'Error: --project cannot be combined with --parent'
- [x] [t826_2] Unit test: `discover_aitasks_sessions(include_registered=True)` returns live + registered-only entries with `is_live` set correctly — PASS 2026-05-31 11:12 auto: test_discover_include_registered.py 4/4 PASS
- [x] [t826_2] Regression: `discover_aitasks_sessions()` default (no flag) yields same entries as before — PASS 2026-05-31 11:12 auto: test_discover_default_unchanged.py 3/3 PASS
- [x] [t826_2] Have one inactive registered project (e.g., aitasks_mobile registered but its tmux session not running) — PASS 2026-05-31 11:12 auto: aitasks_mobile registered + no mobile tmux session (inactive precondition holds)
- [x] [t826_2] Open `ait ide` switcher — PASS 2026-05-31 12:07 drove ait monitor -> j (real switcher): Session row lists 'aitasks  aitasks_mob  v826sw'; aitasks_mob = aitasks_mobile (inactive registered, name truncated by TUI) is shown. Verified via clean tmux capture.
- [x] [t826_2] Select inactive project — PASS 2026-05-31 12:25 drove switcher (ait monitor -> j -> Right): aitasks_mob selected showing '(inactive - Enter to start)'; pressed Enter -> aitasks_mobile tmux session spawned (0->1, confirmed via tmux ls). Cleaned up.
- [x] [t826_2] Open `ait monitor` with same registry state — PASS 2026-05-31 11:33 with aitasks_mobile inactive (killed), ait monitor shows 'Sessions: aitasks' + '(other sessions: none)'; aitasks_mobile absent -> no inactive leakage (regression OK).
- [defer] [t826_3] `cd website && hugo build --gc --minify` — DEFER 2026-05-31 11:12 deferred: 826_3 (website docs) not implemented yet
- [defer] [t826_3] `cd website && ./serve.sh` — DEFER 2026-05-31 11:12 deferred: 826_3 (website docs) not implemented yet
- [defer] [t826_3] Multi-project page contains all 7 required sections (Why / project: block / ait projects / aitask_create --project / cross-repo notation / TUI switcher behavior / Recipe) — DEFER 2026-05-31 11:12 deferred: 826_3 (website docs) not implemented yet
- [defer] [t826_3] Multi-project page explicitly states `ait monitor` is unchanged (live sessions only) — DEFER 2026-05-31 11:12 deferred: 826_3 (website docs) not implemented yet
- [defer] [t826_3] Cross-repo notation documented with no-`t` form as preferred default (`aitasks#835_3`), `aitasks#t835_3` also accepted — DEFER 2026-05-31 11:12 deferred: 826_3 (website docs) not implemented yet
- [defer] [t826_3] Cross-link from `aidocs/cross_repo_references.md` to the website page works — DEFER 2026-05-31 11:12 deferred: 826_3 (website docs) not implemented yet
