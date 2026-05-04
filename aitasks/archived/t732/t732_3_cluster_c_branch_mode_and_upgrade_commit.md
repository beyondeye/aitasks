---
priority: medium
effort: high
depends: []
issue_type: bug
status: Done
labels: [testing, branch_mode, upgrade, install_scripts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-03 16:30
updated_at: 2026-05-04 23:48
completed_at: 2026-05-04 23:48
---

## Context

Child 3 of t732. Cluster C: branch-mode / data-worktree integration AND upgrade-commit regressions. Three failing tests, two distinct sub-issues.

## Coordination note (active install refactor)

t623 ("more installation methods") is currently in flight:
- **t623_1 is done** (commit `d627c0f5` — "Extract global shim to packaging/shim/ait + strategy doc"). This is the **prime suspect** for the upgrade-commit failures (t644, t167) — it reshaped how `install.sh` and `aitask_setup.sh` create commits during upgrade.
- **t623_2 is currently `Implementing`** (dario-e@beyond-eye.com — Homebrew tap + `release-packaging.yml`). It is **packaging-CI only** and does NOT modify the runtime install/upgrade flow. No merge conflict expected.
- t623_3/4/5/6/7 (Ready) are also packaging-distribution scope — no overlap.

**Before patching either tests or code:** read `aiplans/archived/p623/p623_1_*.md` to determine whether the new upgrade output is intentional (→ update test assertions) or accidental (→ restore the missing `committed to git` / version-tagged commit message in `aitask_setup.sh`/`install.sh`). If extending fixes beyond the failing tests into the broader install tree, sync with the t623 owner first.

## Failing tests (verified on `main` @ `74c59788` today)

### Sub-issue (a): init-data symlink/data-branch flow

#### tests/test_init_data.sh (7 passed / 23 failed / 30 total)
First five failures:
```
FAIL: Already init output (expected 'ALREADY_INIT', got 'NO_DATA_BRANCH')
FAIL: aitasks/ is a symlink ('aitasks' is not a symlink)
FAIL: aiplans/ is a symlink ('aiplans' is not a symlink)
FAIL: aitask-data branch exists locally (expected 'yes', got 'no')
FAIL: Initialize from local branch output (expected 'INITIALIZED', got 'NO_DATA_BRANCH')
```
The init-data flow no longer creates the `aitask-data` branch / `aitasks→.aitask-data/aitasks` and `aiplans→.aitask-data/aiplans` symlinks under expected conditions.

### Sub-issue (b): upgrade-commit regressions (likely shared root cause)

#### tests/test_t644_branch_mode_upgrade.sh (8 passed / 8 failed / 16 total)
```
FAIL: A2: Master-branch commit reported (expected output containing 'committed to git')
FAIL: A3: Master gained exactly one commit (expected '3', got '2')
FAIL: A4: Master commit message references new version (expected output containing 'v99.0.0-t644test')
FAIL: A5: Master commit message says 'Update aitasks framework' …
FAIL: A6: New marker file in master commit …
FAIL: A9: No untracked framework files on master after upgrade …
FAIL: C2: Legacy mode gained exactly one commit (expected '3', got '2')
FAIL: C3: Legacy commit references new version …
```

#### tests/test_t167_integration.sh (14 passed / 3 failed / 17 total)
```
FAIL: A1: install.sh announces sentinel-skip (expected output containing 'skipping auto-commit')
FAIL: D1: Upgrade run reports a commit (expected output containing 'committed to git')
FAIL: D2: Upgrade commit message references new version (expected output containing 'v99.0.0-t167test')
```

Both expect upgrade to (1) print `committed to git`, (2) make the upgrade commit, (3) tag the message with the new version. All three behaviors regressed together — strong signal of a single root cause in the upgrade flow.

## Root cause hypothesis

- **(a) init-data**: Recent changes (likely t695_3 `~/.aitask/bin` PATH lib or t699 .gitignore symlink fix) altered the order/conditions under which `aitask_init_data.sh` creates the data branch and symlinks. Test scaffolds may be reading state in a different order than the script now writes.
- **(b) upgrade-commit**: t623_1 extracted the global shim to `packaging/shim/ait` and may have moved or removed the commit-creation code path that used to print `committed to git`. The "expected 3 commits, got 2" pattern says one commit step is being skipped entirely.

## Key files to investigate / modify

- `.aitask-scripts/aitask_init_data.sh` (Mar 7 — older, untouched recently — may be reading state set by newer code)
- `.aitask-scripts/aitask_setup.sh` (May 3 — recently modified) — search for `committed to git` and `Update aitasks framework`
- `install.sh` — search for `committed to git` and `skipping auto-commit`
- `packaging/shim/ait` — the new shim from t623_1
- `tests/test_init_data.sh`, `tests/test_t644_branch_mode_upgrade.sh`, `tests/test_t167_integration.sh` — possibly tests need to be updated to match new expected output (only if the new behavior is the intent)

## Reference patterns

- `aiplans/archived/p623/p623_1_*.md` — primary reference for understanding what t623_1 changed in the install/upgrade flow.
- Suspect commits to bisect against: `d627c0f5` t623_1 (shim extraction), `709380a5` t695_3 (PATH lib). Pre-t623_1 baseline: `8fb777bd` t722.
- `git log --oneline --all -- install.sh .aitask-scripts/aitask_setup.sh` to find recent changes.

## Implementation plan

1. **Read `aiplans/archived/p623/p623_1_*.md` first** to learn the intent of the shim extraction.
2. Run `git diff 8fb777bd d627c0f5 -- install.sh .aitask-scripts/aitask_setup.sh` to see exactly what t623_1 changed.
3. For sub-issue (b): determine whether the missing `committed to git` output is intentional. Patch either the script (restore the message + commit) or the tests (update assertions). Document the decision in the plan's Final Implementation Notes.
4. For sub-issue (a): trace the symlink/data-branch creation flow with `bash -x tests/test_init_data.sh 2>&1 | grep -A3 ALREADY_INIT` to identify what changed.
5. Iterate per-test until all three pass.

## Verification

- `bash tests/test_init_data.sh` passes (30/30).
- `bash tests/test_t644_branch_mode_upgrade.sh` passes (16/16).
- `bash tests/test_t167_integration.sh` passes (17/17).
- `./ait setup` and `./ait upgrade` on a clean scratch dir produce the expected outputs (manual smoke test).
