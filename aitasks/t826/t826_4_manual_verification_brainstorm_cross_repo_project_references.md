---
priority: medium
effort: medium
depends: [t826_3]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [t826_1, t826_2, t826_3]
assigned_to: daelyasy@hotmail.com
created_at: 2026-05-25 17:23
updated_at: 2026-05-31 10:55
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t826_1] Run `bash tests/test_project_resolve.sh && bash tests/test_projects_cmd.sh && bash tests/test_create_project_flag.sh` — all pass
- [ ] [t826_1] Run `shellcheck .aitask-scripts/aitask_project_resolve.sh .aitask-scripts/aitask_projects.sh .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_ide.sh ait` — clean
- [ ] [t826_1] From /home/ddt/Work/aitasks: `ait projects add` — entry written to ~/.config/aitasks/projects.yaml with name `aitasks`
- [ ] [t826_1] From /home/ddt/Work/aitasks_mobile: `ait projects add` — second entry recorded
- [ ] [t826_1] `ait projects list` — both projects shown with statuses (LIVE / OK / STALE)
- [ ] [t826_1] `ait projects resolve aitasks` — prints /home/ddt/Work/aitasks
- [ ] [t826_1] `ait projects exec aitasks -- pwd` — prints the resolved root
- [ ] [t826_1] From aitasks_mobile: `ait create --batch --project aitasks --name cross_repo_test --type chore --priority low --effort low --commit` — task lands in /home/ddt/Work/aitasks/aitasks/, then clean up
- [ ] [t826_1] `aitask_create.sh --project <name>` without `--batch` — refused with clear error
- [ ] [t826_1] `aitask_create.sh --batch --project X --parent Y` — refused (mutual exclusion)
- [ ] [t826_2] Unit test: `discover_aitasks_sessions(include_registered=True)` returns live + registered-only entries with `is_live` set correctly
- [ ] [t826_2] Regression: `discover_aitasks_sessions()` default (no flag) yields same entries as before — no inactive entries leak into `ait monitor` or other existing callers
- [ ] [t826_2] Have one inactive registered project (e.g., aitasks_mobile registered but its tmux session not running)
- [ ] [t826_2] Open `ait ide` switcher — inactive project appears in the list
- [ ] [t826_2] Select inactive project — tmux session spawns (matching `ait ide` bootstrap behavior) and switcher teleports there
- [ ] [t826_2] Open `ait monitor` with same registry state — monitor shows ONLY live sessions (no inactive leakage); this is the regression check
- [ ] [t826_3] `cd website && hugo build --gc --minify` — clean build, no warnings
- [ ] [t826_3] `cd website && ./serve.sh` — new/updated multi_project page renders correctly, code blocks formatted, sidebar nav entry present
- [ ] [t826_3] Multi-project page contains all 7 required sections (Why / project: block / ait projects / aitask_create --project / cross-repo notation / TUI switcher behavior / Recipe)
- [ ] [t826_3] Multi-project page explicitly states `ait monitor` is unchanged (live sessions only)
- [ ] [t826_3] Cross-repo notation documented with no-`t` form as preferred default (`aitasks#835_3`), `aitasks#t835_3` also accepted
- [ ] [t826_3] Cross-link from `aidocs/cross_repo_references.md` to the website page works
