---
Task: t326_1_rename_aiscripts_core_infrastructure.md
Parent Task: aitasks/t326_refactoring_of_installed_files.md
Sibling Tasks: aitasks/t326/t326_2_*.md, aitasks/t326/t326_3_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t326_1 — Rename aiscripts/ to .aitask-scripts/ (core infrastructure)

## Overview

Rename the `aiscripts/` directory to `.aitask-scripts/` and update all core executable code references. Create a backward-compat symlink so skills, docs, and tests (updated in t326_2 and t326_3) continue to work.

## Steps

### 1. Rename directory and create symlink
```bash
git mv aiscripts .aitask-scripts
ln -s .aitask-scripts aiscripts
```
The symlink ensures all existing references still resolve during the transition.

### 2. Update `ait` dispatcher
File: `ait`
- Line 7: `SCRIPTS_DIR="$AIT_DIR/aiscripts"` → `SCRIPTS_DIR="$AIT_DIR/.aitask-scripts"`
- Line 10: `local version_file="$AIT_DIR/aiscripts/VERSION"` → `"$AIT_DIR/.aitask-scripts/VERSION"`
- Line 78: Same version_file pattern → update
- Line 153: `source "$SCRIPTS_DIR/lib/task_utils.sh"` — uses $SCRIPTS_DIR, auto-resolves. No change needed.

### 3. Update `install.sh`
File: `install.sh`
Search for all `aiscripts/` occurrences (~13). Key patterns:
- Directory checks: `if [[ -d "aiscripts" ]]`
- chmod operations: `chmod +x aiscripts/*.sh aiscripts/lib/*.sh`
- VERSION file: `aiscripts/VERSION`
- Source directive: `source "$INSTALL_DIR/aiscripts/aitask_setup.sh"`
- Tarball extraction paths

Replace all with `.aitask-scripts/`.

### 4. Update `.gitignore`
File: `.gitignore`
- `aiscripts/__pycache__/` → `.aitask-scripts/__pycache__/`
- `aiscripts/**/__pycache__/` → `.aitask-scripts/**/__pycache__/`
- `aiscripts/board/__pycache__/` → `.aitask-scripts/board/__pycache__/`
- `aiscripts/codebrowser/__pycache__/` → `.aitask-scripts/codebrowser/__pycache__/`

### 5. Update `create_new_release.sh`
File: `create_new_release.sh`
Replace all `aiscripts/` references (~4) in tarball packaging paths.

### 6. Update `.github/workflows/release.yml`
File: `.github/workflows/release.yml`
- VERSION file path reference
- Tarball inclusion of `aiscripts/` directory

### 7. Update `.claude/settings.local.json`
File: `.claude/settings.local.json`
~28 entries like `"Bash(./aiscripts/aitask_*.sh:*)"` → `"Bash(./.aitask-scripts/aitask_*.sh:*)"`

### 8. Verify shell scripts (read-only check)
Most scripts use `SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)` which auto-resolves through the symlink. Grep for any hardcoded `aiscripts/` within `.aitask-scripts/*.sh` and update if found.

### 9. Update Python files
Files to check:
- `.aitask-scripts/board/aitask_board.py` — git status query references
- `.aitask-scripts/aitask_stats.py` — TASK_DIR default or path references
- `.aitask-scripts/lib/config_utils.py` — board_config.json path
- `.aitask-scripts/codebrowser/codebrowser_app.py`
- `.aitask-scripts/codebrowser/explain_manager.py`
- `.aitask-scripts/settings/settings_app.py`

### 10. Commit
```bash
git add .aitask-scripts/ aiscripts ait install.sh .gitignore create_new_release.sh .github/workflows/release.yml .claude/settings.local.json
git commit -m "refactor: Rename aiscripts/ to .aitask-scripts/ — core infrastructure (t326_1)"
```

## Verification
- `ls -la aiscripts` → symlink to .aitask-scripts
- `./ait --version` works
- `./ait ls` works (requires symlink for task_utils.sh reference)
- `shellcheck .aitask-scripts/aitask_*.sh` passes

## Step 9 (Post-Implementation)
After verification, proceed to archival per the task-workflow.
