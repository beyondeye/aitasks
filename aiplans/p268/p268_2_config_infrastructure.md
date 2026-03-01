---
Task: t268_2_config_infrastructure.md
Parent Task: aitasks/t268_wrapper_for_claude_code.md
Sibling Tasks: aitasks/t268/t268_3_common_config_library.md, aitasks/t268/t268_9_refresh_code_models_skill.md
Archived Sibling Plans: aiplans/archived/p268/p268_1_core_wrapper_script.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

Task t268_1 already implemented most of t268_2's originally scoped work: seed model config files, `seed/codeagent_config.json`, `install.sh` functions, and `aitask_setup.sh` data branch init. The remaining work is adding `*.local.json` to the data branch gitignore so per-user config files are properly excluded from git.

## Files to Modify

| Action | File |
|--------|------|
| Modify | `.aitask-data/.gitignore` — add `*.local.json` pattern |
| Modify | `aiscripts/aitask_setup.sh` — add `*.local.json` gitignore entry in `setup_data_branch()` |
| Modify | `seed/gitignore_data_branch` — add pattern (if this seed file exists, otherwise skip) |

## Implementation Steps

### Step 1: Add `*.local.json` to `.aitask-data/.gitignore`

Add `aitasks/metadata/*.local.json` pattern with comment header.

### Step 2: Update `aitask_setup.sh` — add gitignore entry in `setup_data_branch()`

After the existing `userconfig.yaml` gitignore block, add an idempotent block that appends `*.local.json` pattern when not already present.

### Step 3: Check/update seed gitignore template

No `seed/gitignore_data_branch` file exists — skipped.

### Step 4: Verify

1. `.aitask-data/.gitignore` has the new pattern
2. `bash tests/test_codeagent.sh` — 36/36 pass
3. `shellcheck aiscripts/aitask_setup.sh` — no new warnings
4. Dummy `.local.json` file confirmed gitignored in data branch worktree

## Final Implementation Notes

- **Actual work done:** Added `aitasks/metadata/*.local.json` gitignore pattern to `.aitask-data/.gitignore` (direct edit) and to `aitask_setup.sh`'s `setup_data_branch()` function (for new project setup). Most of t268_2's original scope (seed files, config files, install.sh, setup.sh data init) was already done in t268_1.
- **Deviations from plan:** None. Step 3 was skipped as expected (no seed gitignore template exists).
- **Issues encountered:** None.
- **Key decisions:**
  - Used specific path `aitasks/metadata/*.local.json` instead of blanket `*.local.json` for precision
  - Used `grep -qF "*.local.json"` for idempotent detection (matches both the pattern itself and the specific path form)
- **Notes for sibling tasks:**
  - t268_3 (common config library) should use the per-project/per-user config split pattern established here: `<tool>_config.json` (per-project, git-tracked) and `<tool>_config.local.json` (per-user, gitignored via the `*.local.json` pattern)
  - t268_4 (board config split) can rely on the `*.local.json` gitignore rule being in place — no additional gitignore changes needed for `board_config.local.json`
  - The config resolution chain in `aitask_codeagent.sh` (flag → local → project → default) is the reference pattern for other TUI configs
