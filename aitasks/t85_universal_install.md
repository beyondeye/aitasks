---
priority: high
effort: high
depends: []
issue_type: feature
status: Editing
labels: [bash, aitasks]
children_to_implement: [t85_11]
created_at: 2026-02-11 08:20
updated_at: 2026-02-11 14:24
boardcol: now
boardidx: 10
---

## Cross-Platform aitask Framework Distribution

Make the aitask framework (bash scripts, Python TUI, Claude Code skills) distributable as an independent package installable into any project repo via `curl | sh`. Support Arch Linux, Debian/Ubuntu, Fedora, macOS, and WSL.

### Key decisions
- **GitHub repo**: `beyondeye/aitasks`
- **Directory layout**: Scripts move from project root to `aiscripts/`, Python TUI to `aiscripts/board/`
- **CLI**: `ait` dispatcher at project root + `~/.local/bin/ait` global shim for bare `ait create` usage
- **Python**: Shared venv at `~/.aitask/venv/` (not per-project)
- **Committed to git**: `ait`, `aiscripts/`, `.claude/skills/aitask-*` are committed per project
- **Versioning**: `VERSION` file, `ait --version`, update check in `ait setup`

### Child tasks
- t85_1: Create beyondeye/aitasks GitHub repo with directory structure
- t85_2: Create `ait` dispatcher script
- t85_3: Fix cross-references in bash scripts for aiscripts/ directory
- t85_4: Fix skill file references for aiscripts/ directory
- t85_5: Write `aitask_setup.sh` cross-platform dependency installer
- t85_6: Update `aitask_board.sh` for shared venv
- t85_7: Write `install.sh` curl bootstrap script
- t85_8: Create GitHub Actions release workflow
- t85_9: Apply changes back to tubetime repo
- t85_10: Write README.md with install and usage docs
