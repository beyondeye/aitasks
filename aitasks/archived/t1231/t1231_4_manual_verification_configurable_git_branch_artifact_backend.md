---
priority: medium
effort: medium
depends: [t1231_3]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t1231_1, t1231_2, t1231_3]
assigned_to: dario-e@beyond-eye.com
anchor: 1065
followup_kind: manual_verification
created_at: 2026-07-27 08:45
updated_at: 2026-10-19 16:38
completed_at: 2026-10-19 16:38
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t1231_1] Two-machine round trip: on machine A configure `default_backend: gitbranch`, run `ait artifact create` on a file, then on machine B (a separate clone) run `ait artifact get` on the handle and confirm the bytes match. — PASS 2026-10-19 16:31 auto: branch-mode scratch project, bare remote + clones A/B with separate XDG caches; create on A, ait git push, pull + get on B; cmp identical (sha256 0417529…)
- [x] [t1231_1] Confirm `git log aitask-artifacts` contains the blob commit and `git log aitask-data` contains only the manifest + task file — no blob path on the data branch. — PASS 2026-10-19 16:31 auto: aitask-artifacts holds marker + blobs/04/… commit; aitask-data commit = task file + manifest + artifacts/gitbranch_store.json (R3 identity record, by design); no blobs/ path in aitask-data history
- [x] [t1231_1] Confirm `git status` in the working checkout shows a clean index after an artifact create (no staged files appeared, nothing was disturbed). — PASS 2026-10-19 16:31 auto: git diff --cached empty in main and .aitask-data after create; only dirty path was a fixture-copied .pyc (unrelated)
- [x] [t1231_1] Confirm the artifact branch is never checked out: `git worktree list` shows no new worktree and no blob files exist anywhere in the working tree. — PASS 2026-10-19 16:31 auto: git worktree list shows only main + pre-existing .aitask-data; no blobs/ or .ait-artifact-store files in the working tree
- [x] [t1231_1] Rename `artifacts.backends.gitbranch.branch` to an unused name and confirm `ait artifact get` FAILS CLOSED with a message naming `ait artifact gitbranch-migrate` (not `ait artifact move`). — PASS 2026-10-19 16:31 auto: branch renamed to aitask-artifacts-v2; get (warm and cold cache) exits 1 naming 'ait artifact gitbranch-migrate --from aitask-artifacts --to aitask-artifacts-v2'; no 'ait artifact move'
- [x] [t1231_1] Run `ait artifact gitbranch-migrate --from <old> --to <new>`, confirm `get` works again, the old branch is untouched, and the store_id is preserved on the new branch marker. — PASS 2026-10-19 16:31 auto: migrate MIGRATED:<id>; cold-cache get byte-identical; old branch blobs tree + marker blob hashes unchanged, only addition is the designed .ait-artifact-retired fence commit (writes refused); v2 marker carries same store_id
- [x] [t1231_1] Point the config at an existing ordinary branch (e.g. a scratch feature branch) and confirm `ait artifact create` refuses and leaves that branch's tip byte-unchanged. — PASS 2026-10-19 16:32 auto: config at pushed scratch-feature branch; create and init-store both exit 1 with the 'not an aitask artifact store … pick an unused branch name' error; local and remote tips byte-unchanged (8530f67); nothing committed
- [x] [t1231_1] Point the config at `main` and confirm the reserved-name validator rejects it outright. — PASS 2026-10-19 16:32 auto: branch: main -> artifact_registry.py rejects at activation ('must not be the reserved branch main'); create exits 1, main tip unchanged
- [x] [t1231_1] With the remote unreachable, confirm `ait artifact create --backend gitbranch` fails and leaves no manifest published on aitask-data. — PASS 2026-10-19 16:32 auto: origin renamed away; create --backend gitbranch exits 1 ('cannot reach origin'), rolled back; data HEAD unchanged, no artifacts/ manifest, no store ref created. Cosmetic: message contains a clipped git stderr fragment '(and the repository exists.)'
- [x] [t1231_1] Confirm existing suites are green: bash tests/test_artifact_gitbranch_backend.sh, tests/test_artifact_dir_backend.sh, tests/test_artifact_cli.sh, tests/test_artifact_share_resolution.sh, tests/test_attach_local_backend.sh. — PASS 2026-10-19 16:37 auto: test_artifact_gitbranch_backend 294/294, test_artifact_dir_backend 152/152, test_artifact_cli 251/251, test_artifact_share_resolution 98/98, test_attach_local_backend 112/112 -- all exit 0
- [x] [t1231_2] Open `ait settings` in a real terminal, press the new tab key, and confirm the Artifacts pane renders with both rows and the section hint. — PASS 2026-10-19 16:35 auto: tmux (isolated -L socket) in scratch project D; 'k' opens Artifacts pane with default_backend + gitbranch branch rows and the section hint. Cosmetic: long hint lines clip at the right edge instead of wrapping
- [x] [t1231_2] Confirm the tab title and footer hint show the correct key, and that rebinding it in the Shortcuts editor updates both. — PASS 2026-10-19 16:35 auto: title '(K) Artifacts' + hint a/b/c/g/k/m/p/s/t; rebind settings.switch_tab_artifacts to z in Shortcuts editor (saved to userconfig), after restart title '(Z) Artifacts', hint a/b/c/g/z/m/p/s/t, old k inert
- [x] [t1231_2] On a project with no `artifacts:` block, confirm the default_backend selector offers `gitbranch` (the bootstrap case). — PASS 2026-10-19 16:35 auto: D had no artifacts: block; selector shows local | dir | gitbranch
- [x] [t1231_2] Enter an invalid branch name and a reserved name (`main`); confirm each is rejected in the editor and that project_config.yaml is byte-unchanged afterwards. — PASS 2026-10-19 16:35 auto: 'bad..name', 'main', 'aitask-data' each rejected in-dialog (dialog stays open, red error); config sha256 unchanged, no commit. Cosmetic: long error text clipped in dialog
- [x] [t1231_2] Select `gitbranch`, save, and confirm project_config.yaml gained a well-formed block that `artifact_registry.py default-backend` accepts. — PASS 2026-10-19 16:35 auto: cycled to gitbranch (branch prefilled aitask-artifacts), Save -> artifacts: {backends: {gitbranch: {branch: aitask-artifacts}}, default_backend: gitbranch}; artifact_registry.py default-backend -> gitbranch rc0, backend-env OK; ait artifact create on it works
- [x] [t1231_2] Confirm mouse interaction works on the new tab (click the tab, click a row, click Save/Revert). — PASS 2026-10-19 16:35 auto: SGR mouse clicks via tmux: tab label click switches to Artifacts, row click focuses default_backend, Save and Revert buttons act on click
- [x] [t1231_2] Confirm Revert restores the pane without writing, and that unrelated keys elsewhere in project_config.yaml survived the save. — PASS 2026-10-19 16:35 auto: changed pane to local, Revert -> pane back to gitbranch + 'reverted' toast, config sha256 unchanged, no commit. Unrelated keys (unrelated_section.keep_me/nested) survived saves; as documented comments are dropped (t1260) and YAML 'yes' normalised to 'true'. Note: a Save with no edits still rewrites+commits the file
- [x] [t1231_3] Run `cd website && ./serve.sh` and read both new pages rendered; confirm sidebar placement, weights, and that no `relref` is broken. — PASS 2026-10-19 16:37 auto: read both pages (source + hugo-built HTML, not via serve.sh); sidebar: concepts Attachments(55) > Artifacts(57) > Execution profiles(60), commands Board(30) > Artifact(33) > Attach(34), both active; hugo build exit 0 so no broken relref; check_links.py --build SWEEP PASSED. Content matches observed behaviour; minor gap: no page says the data-branch manifest commit needs 'ait git push' before another clone can get
- [x] [t1231_3] Confirm the concepts/_index.md and commands/_index.md entries link correctly (the two sections use different link forms). — PASS 2026-10-19 16:37 auto: concepts/_index.md uses relref /docs/concepts/artifacts; commands/_index.md uses relative artifact/ and ../concepts/artifacts/; built hrefs resolve to existing pages; link sweep passed
- [fail] [t1231_3] Confirm the settings reference tables now match the live TUI — every tab, every key, including the previously-missing Shortcuts row. — FAIL 2026-10-19 16:37 follow-up t2068
- [x] [t1231_3] Prove the drift guard bites: remove the gitbranch row from concepts/artifacts.md, run bash tests/test_website_doc_lists.sh, confirm it exits 1, then restore the row by undoing the edit (not via git checkout). — PASS 2026-10-19 16:37 auto: in a git-archive copy of HEAD (shared worktree untouched): control rc=0; gitbranch row removed -> test_website_doc_lists.sh rc=1 ('concepts/artifacts.md documents backend gitbranch' FAIL); row re-inserted by reversing the edit (cmp byte-identical) -> rc=0
- [x] [t1231_3] Confirm `cd website && hugo build --gc --minify` succeeds. — PASS 2026-10-19 16:37 auto: hugo build --gc --minify (destination redirected to scratch so website/public untouched) exit 0

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1231_2** id=2026-10-19T10:06:12Z.8d566e073ef46ff5ed50e8ee from=t1231_2 from_verified=yes at=2026-10-19T10:06:12Z base=7b357af39d25cd5b5b35b2b66b20440c27050199 base_branch=main dirty=yes host=omg16
>
> | t1231_2 (Artifacts settings tab) is committed in 7b357af39 (not yet archived as of writing). Advisory context for the [t1231_2] checklist items; verify against the code:
> | 
> | - The tab key is `k` (the tab title renders "(K) Artifacts"; the hint reads a/b/c/g/k/m/p/s/t).
> | - Line 39's check: `artifact_registry.py` has no execute bit, so run it as `python3 .aitask-scripts/lib/artifact_registry.py --config <cfg> default-backend`.
> | - Exercise the tab in a scratch project, not this repository: saving rewrites project_config.yaml through yaml.safe_dump and drops every comment, including the seeded artifacts: block (accepted at planning; t1260 owns the fix).
> | - The selector also offers `dir`, but the tab has no row for dir.path. Save refuses `dir` as the default unless a valid absolute `artifacts.backends.dir.path` is already written into the YAML by hand. The registry's `backend-env dir` check makes that decision.
> | - Worth a manual look: an invalid or reserved branch (e.g. `main`) keeps the edit dialog open with a red error, and changing an existing branch shows a warning toast naming `ait artifact gitbranch-migrate --from <old> --to <new>`.

> **👁 note:read** id=2026-10-19T13:29:38Z.aeff358036f7e3360bf8ae15 by=t1231_4 at=2026-10-19T13:29:38Z mode=explicit ids=2026-10-19T10:06:12Z.8d566e073ef46ff5ed50e8ee
