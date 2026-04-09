---
priority: medium
effort: medium
depends: [t507_1]
issue_type: feature
status: Implementing
labels: [aitask_monitor]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-09 12:51
updated_at: 2026-04-09 21:58
---

## Context

Task t507 adds lazygit (or similar git TUIs) as a pseudo-native TUI in the aitasks framework. This child task adds a setup step to detect installed git TUIs, let the user choose one, and optionally install lazygit if nothing is found. Depends on t507_1 which adds the config field and detection utility.

## Key Files to Modify

- `.aitask-scripts/aitask_setup.sh` — Add a new function `setup_git_tui()` and call it from `main()` after `ensure_project_config_defaults` (which creates project_config.yaml). The setup script is ~2576 lines.

## Reference Files for Patterns

- `.aitask-scripts/aitask_setup.sh` lines 104-303: `install_cli_tools()` for OS-specific installation patterns (pacman on arch, brew on macOS, apt on debian, dnf on fedora)
- `.aitask-scripts/aitask_setup.sh` lines 89-99: `_is_agent_installed()` for tool detection pattern using `command -v`
- `.aitask-scripts/aitask_setup.sh` `_detect_git_platform()`: pattern for detecting capabilities from environment
- `.aitask-scripts/aitask_setup.sh` `main()` at line 2501: where to insert the new setup step call

## Implementation Plan

1. Add `setup_git_tui()` function to `aitask_setup.sh`:
   - Detect installed git TUIs: `command -v lazygit`, `command -v gitui`, `command -v tig`
   - If exactly one found, auto-select it with a confirmation message
   - If multiple found, use numbered menu (or fzf if available) to let user pick (default to lazygit if present)
   - If none found and interactive mode:
     - Ask if user wants to install lazygit
     - If yes, install platform-specifically:
       - Arch Linux: `sudo pacman -S --needed --noconfirm lazygit`
       - macOS: `brew install lazygit`
       - Fedora: `sudo dnf install -y lazygit`
       - Debian/Ubuntu: download from GitHub releases (lazygit has no official apt repo)
     - If user declines, set git_tui to empty/skip
   - Save selection to `project_config.yaml` under `tmux.git_tui` using python3 inline YAML update (follow existing config-patching patterns in setup) or yq if available
2. Call `setup_git_tui` from `main()` after `ensure_project_config_defaults`
3. Handle batch/non-interactive mode gracefully (auto-detect only, no prompts)

## Verification Steps

- Run `ait setup` in a test environment — verify the git TUI detection step appears
- Verify the selected tool is saved to `project_config.yaml` under `tmux.git_tui`
- Test with lazygit installed: should auto-detect and offer it as default
- Test with no git TUIs: should offer installation
