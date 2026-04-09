---
Task: t507_2_git_tui_detection_and_selection_in_ait_setup.md
Parent Task: aitasks/t507_lazygit_integration_in_ait_monitorcommon_switch_tui.md
Sibling Tasks: aitasks/t507/t507_1_*.md, aitasks/t507/t507_3_*.md, aitasks/t507/t507_4_*.md
Archived Sibling Plans: aiplans/archived/p507/p507_*_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Implementation Plan: t507_2 — Git TUI Detection and Selection in `ait setup`

## Steps

### 1. Add `setup_git_tui()` function to `aitask_setup.sh`

File: `.aitask-scripts/aitask_setup.sh`

Add the function near other setup functions. Follow the patterns in `install_cli_tools()` for OS-specific installation.

```bash
setup_git_tui() {
    info "Configuring git management TUI..."

    local detected=()
    for tool in lazygit gitui tig; do
        if command -v "$tool" &>/dev/null; then
            detected+=("$tool")
        fi
    done

    local selected=""

    if [[ ${#detected[@]} -eq 0 ]]; then
        info "No git management TUI detected (lazygit, gitui, tig)."
        if [[ "${AIT_BATCH:-}" == "1" ]]; then
            info "Batch mode: skipping git TUI setup."
            return 0
        fi
        read -rp "Would you like to install lazygit? [Y/n] " answer
        if [[ "${answer,,}" != "n" ]]; then
            _install_lazygit
            if command -v lazygit &>/dev/null; then
                selected="lazygit"
            else
                warn "lazygit installation may have failed. Skipping git TUI config."
                return 0
            fi
        else
            info "Skipping git TUI configuration."
            return 0
        fi
    elif [[ ${#detected[@]} -eq 1 ]]; then
        selected="${detected[0]}"
        info "Detected git TUI: $selected"
    else
        info "Multiple git TUIs detected: ${detected[*]}"
        if [[ "${AIT_BATCH:-}" == "1" ]]; then
            # In batch mode, prefer lazygit
            for tool in lazygit gitui tig; do
                if command -v "$tool" &>/dev/null; then
                    selected="$tool"
                    break
                fi
            done
        else
            # Interactive selection
            PS3="Select git TUI to use (default: ${detected[0]}): "
            select choice in "${detected[@]}"; do
                if [[ -n "$choice" ]]; then
                    selected="$choice"
                    break
                else
                    selected="${detected[0]}"
                    break
                fi
            done
        fi
    fi

    if [[ -n "$selected" ]]; then
        _set_project_config_value "tmux.git_tui" "$selected"
        info "Git TUI configured: $selected"
    fi
}
```

### 2. Add `_install_lazygit()` helper

Platform-specific installation following patterns from `install_cli_tools()`:

```bash
_install_lazygit() {
    local os
    os=$(detect_os)
    info "Installing lazygit..."
    case "$os" in
        arch)
            sudo pacman -S --needed --noconfirm lazygit ;;
        debian)
            # Install from GitHub releases (no official apt repo)
            _install_lazygit_from_github ;;
        fedora)
            sudo dnf install -y lazygit ;;
        macos)
            brew install lazygit ;;
        *)
            warn "Unsupported OS for automatic lazygit installation."
            info "Please install lazygit manually: https://github.com/jesseduffield/lazygit#installation"
            return 1 ;;
    esac
}
```

### 3. Add `_install_lazygit_from_github()` for debian/ubuntu

Downloads the latest lazygit release binary from GitHub:

```bash
_install_lazygit_from_github() {
    local version
    version=$(curl -s "https://api.github.com/repos/jesseduffield/lazygit/releases/latest" | grep '"tag_name"' | sed -E 's/.*"v([^"]+)".*/\1/')
    if [[ -z "$version" ]]; then
        warn "Could not determine latest lazygit version."
        return 1
    fi
    local tmpdir
    tmpdir=$(mktemp -d)
    curl -Lo "$tmpdir/lazygit.tar.gz" "https://github.com/jesseduffield/lazygit/releases/latest/download/lazygit_${version}_Linux_x86_64.tar.gz"
    tar xf "$tmpdir/lazygit.tar.gz" -C "$tmpdir" lazygit
    sudo install "$tmpdir/lazygit" /usr/local/bin/lazygit
    rm -rf "$tmpdir"
}
```

### 4. Add `_set_project_config_value()` helper (if not exists)

A helper to set a nested YAML value in project_config.yaml using python3:

```bash
_set_project_config_value() {
    local key="$1" value="$2"
    local config_file="aitasks/metadata/project_config.yaml"
    python3 -c "
import yaml, sys
with open('$config_file') as f:
    data = yaml.safe_load(f) or {}
keys = '$key'.split('.')
d = data
for k in keys[:-1]:
    d = d.setdefault(k, {})
d[keys[-1]] = '$value'
with open('$config_file', 'w') as f:
    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
"
}
```

### 5. Call from `main()`

In `main()` function (around line 2501), add `setup_git_tui` after `ensure_project_config_defaults`:

```bash
ensure_project_config_defaults
setup_git_tui      # <-- new
setup_userconfig
```

## Post-Implementation

Proceed to Step 9 (Post-Implementation) for archival.

## Verification

- Run setup in a test environment with lazygit installed — should auto-detect and configure
- Run setup without any git TUI — should offer lazygit installation
- Check `project_config.yaml` after setup — should have `tmux.git_tui` set
