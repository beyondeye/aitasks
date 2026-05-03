---
Task: t732_3_cluster_c_branch_mode_and_upgrade_commit.md
Parent Task: aitasks/t732_fix_failing_pre_existing_test_suite.md
Sibling Tasks: aitasks/t732/t732_*.md
Archived Sibling Plans: aiplans/archived/p732/p732_*.md
Worktree: (current branch — fast profile sets create_worktree:false)
Branch: (current branch)
Base branch: main
---

# p732_3 — Cluster C: branch-mode + upgrade-commit regressions

## Goal

Make 3 tests green: `test_init_data.sh`, `test_t644_branch_mode_upgrade.sh`, `test_t167_integration.sh`. Two distinct sub-issues; t644+t167 likely share a root cause (t623_1 shim extraction).

## Coordination — read first

t623 ("more installation methods") is in flight. **Before patching, read `aiplans/archived/p623/p623_1_*.md`** to learn whether the new install/upgrade output is intentional or accidental. Decision tree:

- Intentional change → update test assertions to match new wording.
- Accidental drop → restore `committed to git` / version-tagged commit message in `aitask_setup.sh`/`install.sh`.

t623_2 (currently `Implementing`, packaging-CI only) does NOT touch runtime install/upgrade — no merge conflict expected. If you're tempted to expand scope into the broader install tree, sync with the t623 owner first.

## Confirmed failures (today)

### Sub-issue (a) — init-data
`tests/test_init_data.sh` 7/30 pass. Symlinks not recreated; data branch returns `NO_DATA_BRANCH`.

### Sub-issue (b) — upgrade-commit
- `tests/test_t644_branch_mode_upgrade.sh` 8/16 pass: master commit not made on upgrade, version tag missing from message, marker file not in commit.
- `tests/test_t167_integration.sh` 14/17 pass: install.sh sentinel-skip not announced, upgrade commit not reported, version tag missing.

## Steps

1. Read `aitasks/t732/t732_3_cluster_c_branch_mode_and_upgrade_commit.md` for full context.
2. Read `aiplans/archived/p623/p623_1_*.md` to understand t623_1 intent.
3. `git diff 8fb777bd d627c0f5 -- install.sh .aitask-scripts/aitask_setup.sh` to see exactly what t623_1 changed.
4. **Sub-issue (b) first** (likely shared root cause for t644+t167):
   - Search for `committed to git` and `Update aitasks framework` strings in `aitask_setup.sh`/`install.sh`.
   - Determine intentional-vs-accidental per coordination note above.
   - Patch and re-run `bash tests/test_t644_branch_mode_upgrade.sh && bash tests/test_t167_integration.sh`.
5. **Sub-issue (a)**:
   - `bash -x tests/test_init_data.sh 2>&1 | grep -A3 ALREADY_INIT` to trace the symlink/data-branch creation flow.
   - Read `.aitask-scripts/aitask_init_data.sh` (Mar 7 — older) and identify what neighbor changed (likely t695_3 or t699 shifted state-setting order).
   - Patch and re-run `bash tests/test_init_data.sh`.
6. Document fix-the-test vs fix-the-code decisions in Final Implementation Notes.

## Verification

- All 3 tests pass: `for t in tests/test_init_data.sh tests/test_t644_branch_mode_upgrade.sh tests/test_t167_integration.sh; do bash "$t" || break; done`.
- Manual smoke: `./ait setup` and `./ait upgrade` on a clean scratch dir produce expected outputs.

## Step 9

Archive via `./.aitask-scripts/aitask_archive.sh 732_3`.
