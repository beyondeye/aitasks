---
priority: medium
effort: medium
depends: [t1231_3]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [t1231_1, t1231_2, t1231_3]
anchor: 1065
followup_kind: manual_verification
created_at: 2026-07-27 08:45
updated_at: 2026-08-13 23:06
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1231_1] Two-machine round trip: on machine A configure `default_backend: gitbranch`, run `ait artifact create` on a file, then on machine B (a separate clone) run `ait artifact get` on the handle and confirm the bytes match.
- [ ] [t1231_1] Confirm `git log aitask-artifacts` contains the blob commit and `git log aitask-data` contains only the manifest + task file — no blob path on the data branch.
- [ ] [t1231_1] Confirm `git status` in the working checkout shows a clean index after an artifact create (no staged files appeared, nothing was disturbed).
- [ ] [t1231_1] Confirm the artifact branch is never checked out: `git worktree list` shows no new worktree and no blob files exist anywhere in the working tree.
- [ ] [t1231_1] Rename `artifacts.backends.gitbranch.branch` to an unused name and confirm `ait artifact get` FAILS CLOSED with a message naming `ait artifact gitbranch-migrate` (not `ait artifact move`).
- [ ] [t1231_1] Run `ait artifact gitbranch-migrate --from <old> --to <new>`, confirm `get` works again, the old branch is untouched, and the store_id is preserved on the new branch marker.
- [ ] [t1231_1] Point the config at an existing ordinary branch (e.g. a scratch feature branch) and confirm `ait artifact create` refuses and leaves that branch's tip byte-unchanged.
- [ ] [t1231_1] Point the config at `main` and confirm the reserved-name validator rejects it outright.
- [ ] [t1231_1] With the remote unreachable, confirm `ait artifact create --backend gitbranch` fails and leaves no manifest published on aitask-data.
- [ ] [t1231_1] Confirm existing suites are green: bash tests/test_artifact_gitbranch_backend.sh, tests/test_artifact_dir_backend.sh, tests/test_artifact_cli.sh, tests/test_artifact_share_resolution.sh, tests/test_attach_local_backend.sh.
- [ ] [t1231_2] Open `ait settings` in a real terminal, press the new tab key, and confirm the Artifacts pane renders with both rows and the section hint.
- [ ] [t1231_2] Confirm the tab title and footer hint show the correct key, and that rebinding it in the Shortcuts editor updates both.
- [ ] [t1231_2] On a project with no `artifacts:` block, confirm the default_backend selector offers `gitbranch` (the bootstrap case).
- [ ] [t1231_2] Enter an invalid branch name and a reserved name (`main`); confirm each is rejected in the editor and that project_config.yaml is byte-unchanged afterwards.
- [ ] [t1231_2] Select `gitbranch`, save, and confirm project_config.yaml gained a well-formed block that `artifact_registry.py default-backend` accepts.
- [ ] [t1231_2] Confirm mouse interaction works on the new tab (click the tab, click a row, click Save/Revert).
- [ ] [t1231_2] Confirm Revert restores the pane without writing, and that unrelated keys elsewhere in project_config.yaml survived the save.
- [ ] [t1231_3] Run `cd website && ./serve.sh` and read both new pages rendered; confirm sidebar placement, weights, and that no `relref` is broken.
- [ ] [t1231_3] Confirm the concepts/_index.md and commands/_index.md entries link correctly (the two sections use different link forms).
- [ ] [t1231_3] Confirm the settings reference tables now match the live TUI — every tab, every key, including the previously-missing Shortcuts row.
- [ ] [t1231_3] Prove the drift guard bites: remove the gitbranch row from concepts/artifacts.md, run bash tests/test_website_doc_lists.sh, confirm it exits 1, then restore the row by undoing the edit (not via git checkout).
- [ ] [t1231_3] Confirm `cd website && hugo build --gc --minify` succeeds.
