---
priority: high
effort: high
depends: []
issue_type: refactor
status: Done
labels: [install_scripts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-07 22:41
updated_at: 2026-03-07 23:09
completed_at: 2026-03-07 23:09
---

Rename aiscripts/ directory to .aitask-scripts/ and update all core executable code references.

## Context
The aitasks framework is renaming aiscripts/ to .aitask-scripts/ to follow the dotfile convention used by other framework directories (.aitask-data/, .aitask-pr-data/). This child task handles the actual directory rename and all executable code that references aiscripts/ directly. A backward-compat symlink is created so that unchanged references (skills, docs, tests) still work until they are updated in subsequent child tasks.

## Key Files to Modify
- `ait` (dispatcher): Lines 7, 10, 78 — `SCRIPTS_DIR="$AIT_DIR/aiscripts"`, version file paths
- `install.sh`: ~13 occurrences — tarball extraction, chmod, VERSION, source statements
- `.gitignore`: pycache entries (`aiscripts/__pycache__/` etc.)
- `create_new_release.sh`: tarball paths (~4 occurrences)
- `.github/workflows/release.yml`: VERSION file path, tarball inclusion (~2 occurrences)
- `.claude/settings.local.json`: ~28 allowed Bash command patterns (`Bash(./aiscripts/`)
- Python files: `.aitask-scripts/board/aitask_board.py` (~8), `.aitask-scripts/aitask_stats.py`, `.aitask-scripts/lib/config_utils.py`, `.aitask-scripts/codebrowser/codebrowser_app.py`, `.aitask-scripts/codebrowser/explain_manager.py`, `.aitask-scripts/settings/settings_app.py`

## Reference Files for Patterns
- `ait` dispatcher: see SCRIPTS_DIR variable and exec statements
- `aiscripts/lib/task_utils.sh`: SCRIPT_DIR resolution pattern (`$(dirname "${BASH_SOURCE[0]}")`)

## Implementation Steps
1. `git mv aiscripts .aitask-scripts`
2. `ln -s .aitask-scripts aiscripts` (backward-compat symlink)
3. Update `ait` dispatcher: change `SCRIPTS_DIR` and version file paths
4. Update `install.sh`: all aiscripts/ path references
5. Update `.gitignore`: pycache entries
6. Update `create_new_release.sh` and `.github/workflows/release.yml`
7. Update `.claude/settings.local.json`: Bash command patterns
8. Verify shell scripts use `SCRIPT_DIR=$(dirname "${BASH_SOURCE[0]}")` (auto-resolves, no hardcoded paths)
9. Update Python files that import from or reference aiscripts/ paths
10. Commit changes

## Verification Steps
- `ls -la aiscripts` shows symlink to .aitask-scripts
- `ls .aitask-scripts/aitask_*.sh` lists all scripts
- `./ait --version` works
- `./ait ls` works
- `shellcheck .aitask-scripts/aitask_*.sh` passes (pre-existing issues ok, no new ones)
