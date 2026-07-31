---
priority: medium
effort: medium
depends: [t1223_6]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t1223_1, t1223_2, t1223_3, t1223_4, t1223_5, t1223_6]
assigned_to: dario-e@beyond-eye.com
anchor: 1223
created_at: 2026-07-23 18:42
updated_at: 2026-07-31 12:10
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t1223_1] `ait syncer` in a multi-repo setup renders three tabs (Branches, Versions, Settings) with Branches active on start. — PASS 2026-07-31 11:45 auto: headless tab tests confirm three panes and Branches activation
- [x] [t1223_1] The Branches tab behaves exactly as before the refactor: `s` syncs an aitask-data row, `u`/`p` act on a main row, `r` refreshes, `f` toggles fetch, and the detail pane still populates. — PASS 2026-07-31 11:45 auto: branch action and regression tests passed
- [x] [t1223_1] From the Versions and Settings tabs, `s`/`u`/`p`/`r`/`f` do nothing (footer hints follow the active tab), while `q`, `j` (switcher) and `?` (shortcuts) still work from every tab. — PASS 2026-07-31 11:45 auto: tab action-gating and footer tests passed
- [x] [t1223_1] Launch `ait syncer` in a single-repo setup: no Project column, layout and all actions unchanged from before this feature. — PASS 2026-07-31 11:45 auto: single-repo layout regression test passed
- [x] [t1223_2] Automated-only child — confirm `python3 tests/test_framework_version.py` passes on the verifier's machine (no manual surface of its own). — PASS 2026-07-31 11:45 auto: python3 tests/test_framework_version.py passed (42 tests)
- [x] [t1223_3] The Versions tab shows every discovered repo with its real `.aitask-scripts/VERSION` value; the Latest column matches `ait upgrade`'s own notion of latest. — PASS 2026-07-31 11:45 auto: version-row and latest-resolution tests passed
- [x] [t1223_3] With fetch toggled off (`f`), the Versions tab makes no network call and marks Latest as stale rather than blanking or blocking the UI. — PASS 2026-07-31 11:45 auto: fetch-off network and stale-cell test passed
- [defer] [t1223_3] Upgrade a scratch repo (no live session) to a pinned version: a shell spawns rooted in that repo, State reads `upgrading…` while the pane lives, then `re-check needed` once it exits. — DEFER 2026-07-31 12:10
- [x] [t1223_3] The State column never claims success: the version cell keeps showing the OLD version with a stale marker until the re-check key is pressed, which then reports the new one. — PASS 2026-07-31 11:45 auto: lifecycle test confirms no unobserved success and stale re-check state
- [x] [t1223_3] Open `ait board` (or any framework TUI) in the scratch repo and retry the upgrade: it is REFUSED, and the message names the offending window(s). Close the window, re-check, and the upgrade now proceeds. — PASS 2026-07-31 11:45 auto: active-target refusal and no-spawn tests passed
- [defer] [t1223_3] Attempt to upgrade the repo the syncer is running from: the TUI EXITS FIRST, then the upgrade runs in the vacated window. Confirm nothing under `.aitask-scripts/` changed while the TUI was still alive. — DEFER 2026-07-31 11:45 auto: requires live self-upgrade handoff and process-lifecycle observation
- [defer] [t1223_3] Run `ait syncer` and quit with `Ctrl-C`: the temporary handoff directory is gone afterwards (no leftover under the mktemp root). — DEFER 2026-07-31 11:45 auto: requires live Ctrl-C handoff cleanup observation
- [x] [t1223_3] Launch `syncer_app.py` directly (not via `ait syncer`) and attempt a self-upgrade: it is refused with a message telling you to relaunch via `ait syncer` or run `ait upgrade` from a shell. No shell is spawned. — PASS 2026-07-31 11:45 auto: direct self-target refusal and no-spawn tests passed
- [x] [t1223_4] Automated-only child — confirm `python3 tests/test_cross_repo_settings.py` and the untouched `python3 tests/test_config_utils.py` both pass on the verifier's machine. — PASS 2026-07-31 11:45 auto: cross-repo settings (40) and config utilities (67) suites passed
- [x] [t1223_4] After a project-layer push, inspect the destination repo with `git diff`: exactly one key under `defaults` changed and no other operation was touched or reordered. — PASS 2026-07-31 11:45 auto: exact pushed-key and unrelated-key preservation tests passed
- [x] [t1223_5] The Settings tab shows a repo × operation matrix of effective values with provenance markers, and rows where repos disagree are visibly highlighted. — PASS 2026-07-31 11:45 auto: settings matrix and divergence tests passed
- [x] [t1223_5] Push one operation's default agent from repo A to repo B: the layer prompt appears every time (project vs local) with no pre-selected default, and the push reports a per-destination outcome. — PASS 2026-07-31 11:45 auto: layer-selection and outcome-flow tests passed
- [x] [t1223_5] Push to a destination whose `codeagent_config.local.json` already sets that operation: the masked three-way prompt appears naming the masking value; verify each branch (cancel / write local / clear override and write project) leaves the documented on-disk result. — PASS 2026-07-31 11:45 auto: masked three-way routing and persistence tests passed
- [x] [t1223_5] Push a value whose model is absent from the destination's `models_<agent>.json`: it is refused with a named reason, other destinations in the same push still apply, and nothing is written for the refused one. — PASS 2026-07-31 11:45 auto: named rejection and partial sibling-apply tests passed
- [x] [t1223_5] In a single-repo setup the Settings tab renders read-only and the push action is unavailable. — PASS 2026-07-31 11:45 auto: single-repo read-only and no-push test passed
- [defer] [t1223_6] `cd website && hugo build --gc --minify` succeeds with no broken relref, and the syncer page renders correctly in the local dev server. — DEFER 2026-07-31 11:45 auto: Hugo build passed; local dev-server visual rendering needs human observation
- [defer] [t1223_6] Read the published syncer page: the active-target refusal, the declared tmux-scoped detection bound, the self-upgrade exit, the "launched / result unknown" reporting, and the settings layer prompt with masking are each documented and match the as-built behavior observed above. — DEFER 2026-07-31 11:45 auto: documentation text inspected; live behavior comparison needs human observation
