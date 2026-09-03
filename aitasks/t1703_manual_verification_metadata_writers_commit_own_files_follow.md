---
priority: medium
effort: medium
depends: [1677]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1677]
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: manual_verification
created_at: 2026-09-03 12:21
updated_at: 2026-09-03 13:15
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1677

## Verification Checklist

- [x] Edit a project-layer value in `ait settings` and save: the file is committed by that action and `./ait git status --porcelain` is clean afterwards. — PASS 2026-09-03 12:49 auto: live ait settings TUI in a scratch branch-mode repo; edited verify_build (Project Config tab), clicked Save Project Config -> toast 'ait: Update project_config.yaml', HEAD dc95ec0 contains only aitasks/metadata/project_config.yaml, ./ait git status --porcelain empty
- [x] Save a board **settings** (user-layer) change in `ait settings`: nothing is committed and no toast claims otherwise. — PASS 2026-09-03 12:50 auto: Board tab user-layer change (auto-refresh 0->5) + Save Board Settings; only toast was 'Board settings saved', HEAD unchanged (dc95ec0), worktree clean, value landed in board_config.local.json
- [x] Create a new **project** profile in `ait settings`: the file ends up tracked and committed; repeat for a **user** profile and confirm it is created, gitignored, and NOT committed. — PASS 2026-09-03 12:51 auto: project profile projprof.yaml -> commit b921189 'ait: Update projprof.yaml' (only that file), now in ./ait git ls-files; user profile userprof.yaml -> created in profiles/local/, matched .gitignore:11, HEAD unchanged, worktree clean
- [x] Delete a project profile in `ait settings`: the deletion is committed AND the profile disappears from the UI immediately, without a reload. — PASS 2026-09-03 12:52 auto: deleted project profile via (X) in live settings TUI -> commit d1a6f6e touching only profiles/projprof.yaml (1 file, 4 deletions); the Profile: selector dropped projprof.yaml in the same capture with no reload keystroke; worktree clean
- [x] Import a config bundle in `ait settings` that both creates a new project config and overwrites a pre-existing untracked one: only the created file is committed; the overwritten one is reported refused, not silently dropped. — PASS 2026-09-03 12:54 auto: live settings import of a 2-file bundle (1 new + 1 pre-existing untracked, overwrite=yes): commit e5aff71 contained ONLY newthing_config.json; the overwritten untracked_config.json produced an error toast 'Config saved but NOT committed (REFUSED:untracked:...)' with the remedy command -- reported, not dropped
- [x] Add / rename / delete / merge / reorder board columns in `ait board`: each gesture commits `board_config.json` and leaves the worktree clean. — PASS 2026-09-03 13:01 auto: live ait board column manager -- add c2f457c, rename 851748c, reorder 073ff47, merge b5a5e0e, delete 4c1270a; each commit touched only aitasks/metadata/board_config.json and ./ait git status --porcelain was empty after every gesture
- [x] Start `ait board` in a project with no `board_config.json`: the file is created but NOT committed at startup. — PASS 2026-09-03 13:01 auto: fresh fixture with no board_config.json; ait board startup created aitasks/metadata/board_config.json (353 bytes) but HEAD stayed at e5f03a1 and the file shows as '?? untracked' -- created, not committed
- [x] Run the chatlink wizard to a completed save: the summary states the config's git position and, on success, names the commit. — PASS 2026-09-03 13:05 auto: drove the real ait chatlink wizard through all 7 steps to a completed save; summary pane showed 'config: written / token: written' and the git position line 'committed: ait: Update chatlink_config.yaml' + '(the token file stays uncommitted/gitignored)'; commit c433e4b held only chatlink_config.yaml, worktree clean
- [x] With a failing pre-commit hook installed, repeat a Settings save, a board column edit and a wizard save: each reports the failure, the edit survives on disk, and the remedy command shown actually clears it when pasted (including `--allow-new` for a newly created file). — PASS 2026-09-03 13:11 auto: failing .git/hooks/pre-commit installed; settings save, settings new-profile, board add-column and chatlink wizard save each showed 'saved but NOT committed (git commit failed for <path>)' + remedy, and every edit survived on disk (dirty/untracked, HEAD unchanged). New-file remedy carried --allow-new. Hook removed, all four remedies pasted verbatim -> COMMITTED:1 each (exit 0), worktree clean
- [x] Run `ait sync` after a committed config edit: it no longer reports the file as ownerless and does not defer. — PASS 2026-09-03 13:12 auto: negative control first -- a hand-edited (ownerless) board_config.json made ait sync print 'ownerless, NOT auto-committed ... Clear it with ./.aitask-scripts/aitask_metadata_commit.sh'. After a real ait board column save committed the same file (8c4fa76), ait sync printed only 'Fetching / Pushing 1 commits / Sync complete' -- no ownerless line, no deferral (exit 0)
- [x] Navigate plans in the diffviewer: history lands in `diffviewer_history.local.json` and the tracked `diffviewer_history.json` is never rewritten. — PASS 2026-09-03 13:13 auto: live ait diffviewer in fixture with a tracked legacy diffviewer_history.json; selected two plans -> aitasks/metadata/diffviewer_history.local.json created with the MRU list, tracked diffviewer_history.json unchanged (same md5 f2f149ae..., same mtime 1788430379), ./ait git status --porcelain empty (local file gitignored)
- [x] Run `ait setup` on a repo missing chatlink_config.yaml while another session holds a dirty `board_config.json`: only the file setup wrote is committed. — PASS 2026-09-03 13:15 auto: fixture missing chatlink_config.yaml with a tracked+dirty board_config.json held by a 'concurrent session'; real ait setup committed 9b234c5 (chatlink_config.yaml, crew_runner_config.yaml + 4 agent seeds) and 5ae7190 (project_config.yaml) -- board_config.json appears in neither, stayed ' M' with concurrent_wip intact, and setup printed 'Pre-existing uncommitted changes ... left alone (not committed by setup)'
