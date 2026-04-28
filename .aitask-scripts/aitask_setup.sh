#!/usr/bin/env bash
set -euo pipefail

# aitask_setup.sh - Cross-platform dependency installer for aitask framework
# Invoked via: ait setup

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$HOME/.aitask/venv"
SHIM_DIR="$HOME/.local/bin"
VERSION_FILE="$SCRIPT_DIR/VERSION"
REPO="beyondeye/aitasks"

# Minimum Python version for the framework venv (TUI deps need >=3.11).
# Preferred is the version we install when no modern python is found.
AIT_VENV_PYTHON_MIN="${AIT_VENV_PYTHON_MIN:-3.11}"
AIT_VENV_PYTHON_PREFERRED="${AIT_VENV_PYTHON_PREFERRED:-3.13}"

# --- Color helpers ---
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[ait]${NC} $1"; }
success() { echo -e "${GREEN}[ait]${NC} $1"; }
warn()    { echo -e "${YELLOW}[ait]${NC} $1"; }
die()     { echo -e "${RED}[ait] Error:${NC} $1" >&2; exit 1; }

# --- OS detection ---
detect_os() {
    OS=""
    local kernel
    kernel="$(uname -s)"

    case "$kernel" in
        Darwin)
            OS="macos"
            ;;
        Linux)
            # Check WSL first
            if grep -qi microsoft /proc/version 2>/dev/null; then
                OS="wsl"
                return
            fi

            # Source os-release for distro detection
            if [[ -f /etc/os-release ]]; then
                # shellcheck disable=SC1091
                source /etc/os-release
                local id="${ID:-}"
                local id_like="${ID_LIKE:-}"

                case "$id" in
                    arch|manjaro|endeavouros)
                        OS="arch" ;;
                    ubuntu|debian|pop|linuxmint|elementary)
                        OS="debian" ;;
                    fedora|rhel|centos|rocky|alma)
                        OS="fedora" ;;
                    *)
                        # Fallback to ID_LIKE
                        case "$id_like" in
                            *arch*)   OS="arch" ;;
                            *debian*|*ubuntu*) OS="debian" ;;
                            *fedora*|*rhel*)   OS="fedora" ;;
                            *)        OS="linux-unknown" ;;
                        esac
                        ;;
                esac
            else
                OS="linux-unknown"
            fi
            ;;
        *)
            die "Unsupported operating system: $kernel"
            ;;
    esac
}

# --- Git platform detection (inline — duplicates detect_platform() from task_utils.sh) ---
# This is intentionally inlined rather than sourced because:
# 1. setup.sh defines its own die/info/warn/success helpers with "[ait]" prefix formatting
#    that would conflict with terminal_compat.sh's definitions (task_utils.sh depends on it)
# 2. setup.sh must be self-contained — it runs before the framework is fully initialized
_detect_git_platform() {
    local remote_url
    remote_url=$(git remote get-url origin 2>/dev/null || echo "")
    if [[ "$remote_url" == *"gitlab"* ]]; then
        echo "gitlab"
    elif [[ "$remote_url" == *"bitbucket"* ]]; then
        echo "bitbucket"
    elif [[ "$remote_url" == *"github"* ]]; then
        echo "github"
    else
        echo ""
    fi
}

# Check if a code agent CLI is installed on PATH.
# Uses `command -v` which is a shell builtin that only checks if a command
# exists on $PATH — it does NOT execute the agent or load anything.
_is_agent_installed() {
    case "$1" in
        claude)    command -v claude &>/dev/null ;;
        gemini)    command -v gemini &>/dev/null ;;
        codex)     command -v codex &>/dev/null ;;
        opencode)  command -v opencode &>/dev/null ;;
        *)         return 1 ;;
    esac
}

# --- CLI tools installation ---
install_cli_tools() {
    local os="$1"

    # Detect git platform to install the right CLI tool
    local platform
    platform=$(_detect_git_platform)

    # Build tools list: always fzf, jq, git; platform-specific CLI
    local tools=(fzf jq git zstd)
    case "$platform" in
        gitlab)
            tools+=(glab)
            info "Detected GitLab remote — will install glab CLI"
            ;;
        bitbucket)
            tools+=(bkt)
            info "Detected Bitbucket remote — will install bkt CLI"
            ;;
        github|"")
            tools+=(gh)
            if [[ -z "$platform" ]]; then
                info "Could not detect git remote platform — defaulting to GitHub CLI (gh)"
            fi
            ;;
    esac

    local missing=()
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &>/dev/null; then
            missing+=("$tool")
        fi
    done

    if [[ ${#missing[@]} -eq 0 ]]; then
        success "All CLI tools already installed (${tools[*]})"
        return
    fi

    info "Installing missing CLI tools: ${missing[*]}"

    case "$os" in
        arch)
            # Map tool names to Arch package names
            local pkgs=()
            local need_bkt_arch=false
            for tool in "${missing[@]}"; do
                case "$tool" in
                    gh) pkgs+=("github-cli") ;;
                    bkt) need_bkt_arch=true ;;
                    *)  pkgs+=("$tool") ;;
                esac
            done
            if [[ ${#pkgs[@]} -gt 0 ]]; then
                sudo pacman -S --needed --noconfirm "${pkgs[@]}"
            fi
            if $need_bkt_arch; then
                # NOTE: bkt (bitbucket-cli) is hosted on GitHub — these api.github.com URLs are intentional
                info "Installing Bitbucket CLI from GitHub release..."
                local bkt_ver bkt_url
                bkt_ver=$(curl -s "https://api.github.com/repos/avivsinai/bitbucket-cli/releases/latest" | jq -r '.tag_name' 2>/dev/null | sed 's/^v//')
                if [[ -n "$bkt_ver" && "$bkt_ver" != "null" ]]; then
                    bkt_url="https://github.com/avivsinai/bitbucket-cli/releases/download/v${bkt_ver}/bkt_${bkt_ver}_linux_x86_64.tar.gz"
                    curl -sLO "$bkt_url" \
                        && tar -xzf "bkt_${bkt_ver}_linux_x86_64.tar.gz" bkt \
                        && install -m 755 bkt "$HOME/.local/bin/bkt" \
                        && rm -f bkt "bkt_${bkt_ver}_linux_x86_64.tar.gz" \
                        || warn "Failed to install bkt. Install manually: https://github.com/avivsinai/bitbucket-cli/releases"
                else
                    warn "Could not determine latest bkt version. Install manually: https://github.com/avivsinai/bitbucket-cli/releases"
                fi
            fi
            ;;

        debian|wsl)
            local apt_pkgs=()
            local need_gh=false
            local need_glab=false
            local need_bkt_deb=false
            for tool in "${missing[@]}"; do
                case "$tool" in
                    gh) need_gh=true ;;
                    glab) need_glab=true ;;
                    bkt) need_bkt_deb=true ;;
                    *)  apt_pkgs+=("$tool") ;;
                esac
            done

            if $need_gh; then
                info "Adding GitHub CLI repository..."
                (type -p wget >/dev/null || sudo apt-get install wget -y -qq) \
                    && sudo mkdir -p -m 755 /etc/apt/keyrings \
                    && wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg \
                       | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
                    && sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
                    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
                       | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
                    && sudo apt-get update -qq
                apt_pkgs+=("gh")
            fi

            if $need_glab; then
                info "Installing GitLab CLI from release package..."
                local deb_arch
                deb_arch=$(dpkg --print-architecture)
                local glab_ver
                glab_ver=$(curl -s "https://gitlab.com/api/v4/projects/34675721/releases" | jq -r '.[0].tag_name' 2>/dev/null | sed 's/^v//')
                if [[ -n "$glab_ver" && "$glab_ver" != "null" ]]; then
                    local deb_file="glab_${glab_ver}_Linux_${deb_arch}.deb"
                    curl -sLO "https://gitlab.com/gitlab-org/cli/-/releases/v${glab_ver}/downloads/${deb_file}" \
                        && sudo dpkg -i "$deb_file" \
                        && rm -f "$deb_file" \
                        || warn "Failed to install glab .deb package. Install manually: https://gitlab.com/gitlab-org/cli/-/releases"
                else
                    warn "Could not determine latest glab version. Install manually: https://gitlab.com/gitlab-org/cli/-/releases"
                fi
            fi

            if $need_bkt_deb; then
                # NOTE: bkt (bitbucket-cli) is hosted on GitHub — these api.github.com URLs are intentional
                info "Installing Bitbucket CLI from release package..."
                local deb_arch
                deb_arch=$(dpkg --print-architecture)
                local bkt_ver
                bkt_ver=$(curl -s "https://api.github.com/repos/avivsinai/bitbucket-cli/releases/latest" | jq -r '.tag_name' 2>/dev/null | sed 's/^v//')
                if [[ -n "$bkt_ver" && "$bkt_ver" != "null" ]]; then
                    local deb_file="bkt_${bkt_ver}_${deb_arch}.deb"
                    curl -sLO "https://github.com/avivsinai/bitbucket-cli/releases/download/v${bkt_ver}/${deb_file}" \
                        && sudo dpkg -i "$deb_file" \
                        && rm -f "$deb_file" \
                        || warn "Failed to install bkt .deb package. Install manually: https://github.com/avivsinai/bitbucket-cli/releases"
                else
                    warn "Could not determine latest bkt version. Install manually: https://github.com/avivsinai/bitbucket-cli/releases"
                fi
            fi

            # Also ensure python3 and python3-venv are installed
            apt_pkgs+=("python3" "python3-venv")

            sudo apt-get install -y -qq "${apt_pkgs[@]}"
            ;;

        fedora)
            local dnf_pkgs=()
            local need_bkt_fedora=false
            for tool in "${missing[@]}"; do
                case "$tool" in
                    bkt) need_bkt_fedora=true ;;
                    *)   dnf_pkgs+=("$tool") ;;
                esac
            done
            if [[ ${#dnf_pkgs[@]} -gt 0 ]]; then
                sudo dnf install -y -q "${dnf_pkgs[@]}"
            fi
            if $need_bkt_fedora; then
                # NOTE: bkt (bitbucket-cli) is hosted on GitHub — these api.github.com URLs are intentional
                info "Installing Bitbucket CLI from GitHub release..."
                local bkt_ver bkt_url
                bkt_ver=$(curl -s "https://api.github.com/repos/avivsinai/bitbucket-cli/releases/latest" | jq -r '.tag_name' 2>/dev/null | sed 's/^v//')
                if [[ -n "$bkt_ver" && "$bkt_ver" != "null" ]]; then
                    bkt_url="https://github.com/avivsinai/bitbucket-cli/releases/download/v${bkt_ver}/bkt_${bkt_ver}_linux_x86_64.tar.gz"
                    curl -sLO "$bkt_url" \
                        && tar -xzf "bkt_${bkt_ver}_linux_x86_64.tar.gz" bkt \
                        && sudo install -m 755 bkt /usr/local/bin/bkt \
                        && rm -f bkt "bkt_${bkt_ver}_linux_x86_64.tar.gz" \
                        || warn "Failed to install bkt. Install manually: https://github.com/avivsinai/bitbucket-cli/releases"
                else
                    warn "Could not determine latest bkt version. Install manually: https://github.com/avivsinai/bitbucket-cli/releases"
                fi
            fi
            ;;

        macos)
            if ! command -v brew &>/dev/null; then
                die "Homebrew is required on macOS. Install from https://brew.sh"
            fi

            local brew_pkgs=()
            for tool in "${missing[@]}"; do
                case "$tool" in
                    bkt) brew_pkgs+=("avivsinai/tap/bitbucket-cli") ;;
                    *)   brew_pkgs+=("$tool") ;;
                esac
            done

            # Also install bash 5.x (macOS ships 3.2) and coreutils for gdate
            brew_pkgs+=("bash" "coreutils")

            brew install "${brew_pkgs[@]}"
            ;;

        linux-unknown)
            warn "Unknown Linux distribution. Please install these tools manually:"
            warn "  ${missing[*]}"
            warn "Continuing with the rest of setup..."
            return
            ;;
    esac

    success "CLI tools installed"
}

# --- Bash version verification ---
# Must work under Bash 3.2 (macOS default)
check_bash_version() {
    local required_major=4
    local current_major="${BASH_VERSINFO[0]}"
    local current_minor="${BASH_VERSINFO[1]}"

    if [[ "$current_major" -ge "$required_major" ]]; then
        success "Bash $BASH_VERSION meets minimum (4.0+)"
        return 0
    fi

    warn "Current Bash version is $BASH_VERSION (aitask requires 4.0+)"

    if [[ "$OS" = "macos" ]]; then
        # Look for brew-installed bash
        local brew_bash=""
        if [[ -x "/opt/homebrew/bin/bash" ]]; then
            brew_bash="/opt/homebrew/bin/bash"
        elif [[ -x "/usr/local/bin/bash" ]]; then
            brew_bash="/usr/local/bin/bash"
        fi

        if [[ -n "$brew_bash" ]]; then
            local brew_ver
            brew_ver="$("$brew_bash" -c 'echo $BASH_VERSION')"
            info "Homebrew Bash $brew_ver is available at: $brew_bash"
            info ""
            info "To use it, ensure it appears before /bin/bash in your PATH."
            local brew_prefix
            brew_prefix="$(dirname "$brew_bash")"
            info "  Add to your ~/.zshrc or ~/.bash_profile:"
            info "    export PATH=\"$brew_prefix:\$PATH\""
            info ""
            info "  To make it your default shell:"
            info "    sudo bash -c 'echo $brew_bash >> /etc/shells'"
            info "    chsh -s $brew_bash"
        else
            warn "Homebrew bash not found at expected paths."
            if command -v brew &>/dev/null; then
                info "Installing Bash via Homebrew..."
                brew install bash
                # Re-check after install
                if [[ -x "/opt/homebrew/bin/bash" ]]; then
                    brew_bash="/opt/homebrew/bin/bash"
                elif [[ -x "/usr/local/bin/bash" ]]; then
                    brew_bash="/usr/local/bin/bash"
                fi
                if [[ -n "$brew_bash" ]]; then
                    local brew_ver
                    brew_ver="$("$brew_bash" -c 'echo $BASH_VERSION')"
                    success "Installed Bash $brew_ver at $brew_bash"
                    info "Update your PATH as described above to use it."
                fi
            fi
        fi
        warn "Some aitask commands (stats, board, review) require Bash 4.0+."
    else
        warn "Please upgrade Bash to 4.0+ using your package manager."
    fi
}

# --- Modern-Python resolution and installation (used by setup_python_venv) ---

# Resolve a Python interpreter that meets $1 (e.g. "3.11"), defaulting to
# AIT_VENV_PYTHON_MIN. Echoes the absolute path or empty. Always returns 0.
find_modern_python() {
    local min="${1:-$AIT_VENV_PYTHON_MIN}"
    local major="${min%%.*}" minor="${min##*.}"
    local cand resolved candidates=(
        "$HOME/.aitask/bin/python3"
        "$HOME/.aitask/python/$AIT_VENV_PYTHON_PREFERRED/bin/python3"
        "$HOME/.aitask/venv/bin/python"
        python3.13 python3.12 python3.11 python3
    )
    for cand in "${candidates[@]}"; do
        if [[ "$cand" == /* ]]; then
            resolved="$cand"
        else
            resolved="$(command -v "$cand" 2>/dev/null || true)"
        fi
        [[ -z "$resolved" || ! -x "$resolved" ]] && continue
        if "$resolved" -c "import sys; sys.exit(0 if sys.version_info >= ($major, $minor) else 1)" 2>/dev/null; then
            echo "$resolved"
            return 0
        fi
    done
    return 0
}

# Install a modern Python user-scoped (no sudo). macOS uses brew; Linux uses uv.
install_modern_python() {
    case "$OS" in
        macos) _install_modern_python_macos ;;
        *)     _install_modern_python_linux ;;
    esac
}

_install_modern_python_macos() {
    if ! command -v brew >/dev/null 2>&1; then
        die "Homebrew not found. Install from https://brew.sh and re-run 'ait setup'."
    fi
    info "Installing python@$AIT_VENV_PYTHON_PREFERRED via Homebrew..."
    brew install "python@$AIT_VENV_PYTHON_PREFERRED" \
        || brew upgrade "python@$AIT_VENV_PYTHON_PREFERRED" \
        || die "brew install python@$AIT_VENV_PYTHON_PREFERRED failed."
    hash -r
}

_install_modern_python_linux() {
    local uv_dir="$HOME/.aitask/uv"
    if [[ ! -x "$uv_dir/bin/uv" ]]; then
        info "Downloading uv (astral-sh/uv) into $uv_dir (user-scoped, no sudo)..."
        if ! command -v curl >/dev/null 2>&1; then
            die "curl is required to download uv. Install curl and re-run 'ait setup'."
        fi
        UV_INSTALL_DIR="$uv_dir" \
        INSTALLER_NO_MODIFY_PATH=1 \
            sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh' \
            || die "uv install failed."
    fi
    info "Installing Python $AIT_VENV_PYTHON_PREFERRED via uv..."
    "$uv_dir/bin/uv" python install "$AIT_VENV_PYTHON_PREFERRED" \
        || die "uv python install $AIT_VENV_PYTHON_PREFERRED failed."
    local installed
    installed="$("$uv_dir/bin/uv" python find "$AIT_VENV_PYTHON_PREFERRED" 2>/dev/null)"
    [[ -z "$installed" || ! -x "$installed" ]] && \
        die "uv reported Python $AIT_VENV_PYTHON_PREFERRED installed but interpreter is not executable: ${installed:-<empty>}"
    mkdir -p "$HOME/.aitask/python/$AIT_VENV_PYTHON_PREFERRED/bin"
    ln -sf "$installed" "$HOME/.aitask/python/$AIT_VENV_PYTHON_PREFERRED/bin/python3"
    info "Python $AIT_VENV_PYTHON_PREFERRED installed at $installed (symlinked at ~/.aitask/python/$AIT_VENV_PYTHON_PREFERRED/bin/python3)."
    hash -r
}

# --- Python version verification ---
# Must work under Bash 3.2 (macOS default)
# Sets PYTHON_VERSION_OK=1 if version >= 3.9, 0 otherwise.
# On macOS, offers to install/upgrade via Homebrew.
# DEPRECATED: dead after t695_2 (no callers in setup_python_venv); removal in t695_4.
PYTHON_VERSION_OK=0
check_python_version() {
    local python_cmd="$1"
    PYTHON_VERSION_OK=0

    local py_version
    py_version="$("$python_cmd" -c 'import sys; print("{}.{}.{}".format(*sys.version_info[:3]))' 2>/dev/null)" || {
        warn "Could not determine Python version from $python_cmd"
        return
    }

    local py_major py_minor
    py_major="$(echo "$py_version" | cut -d. -f1)"
    py_minor="$(echo "$py_version" | cut -d. -f2)"

    if [[ "$py_major" -gt 3 ]] || \
       { [[ "$py_major" -eq 3 ]] && [[ "$py_minor" -ge 9 ]]; }; then
        success "Python $py_version meets minimum (3.9+)"
        PYTHON_VERSION_OK=1
        return
    fi

    warn "Python $py_version is too old (aitask board requires 3.9+)"

    if [[ "$OS" = "macos" ]] && command -v brew &>/dev/null; then
        if [[ -t 0 ]]; then
            printf "  Install/upgrade Python 3 via Homebrew? [Y/n] "
            read -r answer
        else
            info "(non-interactive: auto-accepting)"
            answer="Y"
        fi
        case "${answer:-Y}" in
            [Yy]*|"")
                brew install python@3 2>/dev/null || brew upgrade python@3 2>/dev/null || true
                hash -r  # refresh PATH cache
                # Re-check version after upgrade
                if command -v python3 &>/dev/null; then
                    local new_ver
                    new_ver="$(python3 -c 'import sys; print("{}.{}.{}".format(*sys.version_info[:3]))' 2>/dev/null)" || true
                    if [[ -n "$new_ver" ]]; then
                        local new_major new_minor
                        new_major="$(echo "$new_ver" | cut -d. -f1)"
                        new_minor="$(echo "$new_ver" | cut -d. -f2)"
                        if [[ "$new_major" -gt 3 ]] || \
                           { [[ "$new_major" -eq 3 ]] && [[ "$new_minor" -ge 9 ]]; }; then
                            success "Python upgraded to $new_ver"
                            PYTHON_VERSION_OK=1
                            return
                        fi
                    fi
                fi
                warn "Python upgrade did not result in 3.9+. The board TUI may not work."
                ;;
            *)
                warn "Skipped Python upgrade. The board TUI requires Python 3.9+."
                ;;
        esac
    else
        warn "Please upgrade Python to 3.9+ using your package manager."
    fi
}

# --- Python venv setup ---
setup_python_venv() {
    local python_cmd
    python_cmd="$(find_modern_python "$AIT_VENV_PYTHON_MIN")"
    if [[ -z "$python_cmd" ]]; then
        info "No Python >=$AIT_VENV_PYTHON_MIN found. Installing one (user-scoped)..."
        install_modern_python
        python_cmd="$(find_modern_python "$AIT_VENV_PYTHON_MIN")"
        [[ -z "$python_cmd" ]] && \
            die "Modern Python install completed but interpreter still not found. Aborting venv setup."
    fi
    info "Using Python for venv: $python_cmd ($("$python_cmd" --version 2>&1))"

    local min_major="${AIT_VENV_PYTHON_MIN%%.*}"
    local min_minor="${AIT_VENV_PYTHON_MIN##*.}"

    if [[ -d "$VENV_DIR" ]]; then
        # Check if existing venv Python is adequate
        local venv_ver=""
        venv_ver="$("$VENV_DIR/bin/python" -c 'import sys; print("{}.{}".format(*sys.version_info[:2]))' 2>/dev/null)" || venv_ver=""
        if [[ -n "$venv_ver" ]]; then
            local venv_major venv_minor
            venv_major="$(echo "$venv_ver" | cut -d. -f1)"
            venv_minor="$(echo "$venv_ver" | cut -d. -f2)"
            if [[ "$venv_major" -gt "$min_major" ]] || \
               { [[ "$venv_major" -eq "$min_major" ]] && [[ "$venv_minor" -ge "$min_minor" ]]; }; then
                info "Python virtual environment already exists at $VENV_DIR (Python $venv_ver)"
            else
                warn "Existing venv uses Python $venv_ver (< $AIT_VENV_PYTHON_MIN). Recreating..."
                rm -rf "$VENV_DIR"
                mkdir -p "$(dirname "$VENV_DIR")"
                "$python_cmd" -m venv "$VENV_DIR"
            fi
        else
            info "Python virtual environment already exists at $VENV_DIR"
        fi
    else
        info "Creating Python virtual environment at $VENV_DIR..."
        mkdir -p "$(dirname "$VENV_DIR")"
        "$python_cmd" -m venv "$VENV_DIR"
    fi

    local install_plotext=false
    if [[ -t 0 ]]; then
        info "Optional dependency: stats TUI chart panes (plotext)"
        printf "  Install plotext for 'ait stats-tui' chart panes? [y/N] "
        read -r answer
        case "${answer:-N}" in
            [Yy]*) install_plotext=true ;;
        esac
    fi

    info "Installing/upgrading Python dependencies..."
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip
    "$VENV_DIR/bin/pip" install --quiet 'textual>=8.1.1,<9' 'pyyaml==6.0.3' 'linkify-it-py==2.1.0' 'tomli>=2.4.0,<3'
    if [[ "$install_plotext" == true ]]; then
        "$VENV_DIR/bin/pip" install --quiet 'plotext==5.3.2'
        info "Installed optional stats graph dependency: plotext"
    else
        info "Skipped optional stats graph dependency (plotext)"
    fi

    # Expose venv-Python via stable symlinks (t695_3).
    # These are picked up by lib/aitask_path.sh's PATH prepend and by
    # lib/python_resolve.sh's candidate list (already references this path).
    mkdir -p "$HOME/.aitask/bin"
    ln -sf "$VENV_DIR/bin/python" "$HOME/.aitask/bin/python3"
    ln -sf "$VENV_DIR/bin/python" "$HOME/.aitask/bin/python"
    info "Created framework Python symlinks at ~/.aitask/bin/{python,python3}."

    success "Python venv ready at $VENV_DIR"
}

# --- Ensure ~/.local/bin is in shell profile PATH ---
# Appends PATH export to the user's shell profile if not already present.
# Idempotent: skips if PATH already contains the directory or profile already has the entry.
ensure_path_in_profile() {
    local dir_to_add="$1"

    # Already in PATH — nothing to do
    if [[ ":$PATH:" == *":$dir_to_add:"* ]]; then
        return
    fi

    # Determine target shell profile
    local profile_file=""
    local kernel
    kernel="$(uname -s)"

    if [[ "${SHELL:-}" == */zsh ]] || [[ "$kernel" == "Darwin" ]]; then
        profile_file="$HOME/.zshrc"
    elif [[ "${SHELL:-}" == */bash ]]; then
        profile_file="$HOME/.bashrc"
    else
        profile_file="$HOME/.profile"
    fi

    # Idempotency: check if a .local/bin PATH entry already exists
    if [[ -f "$profile_file" ]] && grep -qF '.local/bin' "$profile_file"; then
        info "$profile_file already contains a .local/bin PATH entry"
        return
    fi

    # Append the PATH line
    {
        echo ""
        echo "# Added by aitasks installer"
        echo 'export PATH="$HOME/.local/bin:$PATH"'
    } >> "$profile_file"

    info "Added $dir_to_add to PATH in $profile_file"
    warn "Restart your shell or run: source $profile_file"
}

# --- Global shim installation ---
install_global_shim() {
    # Non-blocking: if anything fails, warn and continue
    {
        mkdir -p "$SHIM_DIR"

        cat > "$SHIM_DIR/ait" << 'SHIM'
#!/usr/bin/env bash
# Global shim for ait - finds nearest project-local ait dispatcher
REPO="beyondeye/aitasks"

if [[ "${_AIT_SHIM_ACTIVE:-}" == "1" ]]; then
    echo "Error: ait dispatcher not found in any parent directory." >&2
    exit 1
fi
export _AIT_SHIM_ACTIVE=1

# Walk up to find project-local ait
dir="$PWD"
while [[ "$dir" != "/" ]]; do
    if [[ -x "$dir/ait" && -d "$dir/.aitask-scripts" ]]; then
        unset _AIT_SHIM_ACTIVE
        exec "$dir/ait" "$@"
    fi
    dir="$(dirname "$dir")"
done

# No project found — special-case "ait setup" to bootstrap
if [[ "${1:-}" == "setup" ]]; then
    echo ""
    echo "[ait] No aitasks project found in $PWD or any parent directory."
    echo ""
    echo "[ait] aitasks must be installed at the root of a git repository."
    echo "[ait] This will install the aitasks framework into: $PWD"
    echo ""
    echo "[ait] Make sure this is the root directory of the project where"
    echo "[ait] you want to manage tasks (the directory containing .git/)."
    echo ""

    if [[ -t 0 ]]; then
        printf "  Install aitasks framework here? [Y/n] "
        read -r answer
        case "${answer:-Y}" in
            [Yy]*|"") ;;
            *) echo "[ait] Aborted."; exit 0 ;;
        esac
    fi

    # Download install.sh to temp file (keeps stdin on terminal for interactive prompts)
    tmpfile="$(mktemp "${TMPDIR:-/tmp}/ait-install.XXXXXX")"
    trap 'rm -f "$tmpfile"' EXIT

    echo "[ait] Downloading installer from GitHub..."
    if command -v curl &>/dev/null; then
        if ! curl -fsSL --max-time 30 \
            "https://raw.githubusercontent.com/$REPO/main/install.sh" \
            -o "$tmpfile" 2>/dev/null; then
            echo "[ait] Error: Failed to download installer. Check your network." >&2
            exit 1
        fi
    elif command -v wget &>/dev/null; then
        if ! wget -q --timeout=30 \
            "https://raw.githubusercontent.com/$REPO/main/install.sh" \
            -O "$tmpfile" 2>/dev/null; then
            echo "[ait] Error: Failed to download installer. Check your network." >&2
            exit 1
        fi
    else
        echo "[ait] Error: curl or wget required to download the installer." >&2
        exit 1
    fi

    echo ""
    bash "$tmpfile" --dir "$PWD"
    install_rc=$?
    rm -f "$tmpfile"
    trap - EXIT

    if [[ $install_rc -ne 0 || ! -x "$PWD/ait" ]]; then
        echo "[ait] Error: Installation failed." >&2
        exit 1
    fi

    echo ""
    echo "[ait] Framework installed. Running setup..."
    echo ""
    unset _AIT_SHIM_ACTIVE
    exec "$PWD/ait" setup
fi

echo "Error: No ait project found in any parent directory of $PWD" >&2
echo "  Run 'ait setup' to install aitasks in the current directory." >&2
echo "  Or: curl -fsSL https://raw.githubusercontent.com/$REPO/main/install.sh | bash" >&2
exit 1
SHIM

        chmod +x "$SHIM_DIR/ait"

        success "Global shim installed at $SHIM_DIR/ait"
        ensure_path_in_profile "$SHIM_DIR"
    } || {
        warn "Could not install global shim at $SHIM_DIR/ait (non-fatal)"
    }
}

# --- Ensure git repository exists (init only, no commit) ---
ensure_git_repo() {
    local project_dir="$SCRIPT_DIR/.."

    # Check if we're inside a git repo
    if git -C "$project_dir" rev-parse --is-inside-work-tree &>/dev/null; then
        local git_root abs_project_dir
        git_root="$(git -C "$project_dir" rev-parse --show-toplevel 2>/dev/null)" || true
        abs_project_dir="$(cd "$project_dir" && pwd -P)"

        if [[ -n "$git_root" && "$git_root" != "$abs_project_dir" ]]; then
            warn "aitasks is installed in a subdirectory, not the git root."
            info "  Git root:      $git_root"
            info "  aitasks dir:   $abs_project_dir"
            info "aitasks should be installed at the root of your git repository"
            info "for task IDs, locking, and sync to work correctly."
            if [[ -t 0 ]]; then
                printf "  Continue with setup anyway? [y/N] "
                read -r answer
                case "${answer:-N}" in
                    [Yy]*) ;;
                    *)
                        info "Aborted. Reinstall aitasks from the git root: $git_root"
                        exit 1
                        ;;
                esac
            fi
        else
            success "Git repository already initialized"
        fi
        return
    fi

    # Not a git repo — provide detailed explanation and offer to initialize
    local abs_project_dir
    abs_project_dir="$(cd "$project_dir" && pwd)"

    warn "No git repository found in $abs_project_dir"
    echo ""
    info "aitasks is tightly integrated with git. It uses git for:"
    info "  - Storing task and plan files as version-controlled markdown"
    info "  - Atomic task ID assignment (via a shared counter branch)"
    info "  - Task locking (prevents two agents picking the same task)"
    info "  - Multi-machine sync (push/pull task data across machines)"
    echo ""
    info "This directory should be the root of the project where you want"
    info "to manage tasks — the place where '.git/' lives (or will live)."
    echo ""

    if [[ -t 0 ]]; then
        printf "  Is this the correct project directory? [Y/n] "
        read -r dir_answer
        case "${dir_answer:-Y}" in
            [Yy]*|"") ;;
            *)
                info "Aborted. cd to the correct project directory and re-run 'ait setup'."
                exit 1
                ;;
        esac

        printf "  Initialize a git repository here? [Y/n] "
        read -r answer
    else
        info "(non-interactive: auto-accepting defaults)"
        answer="Y"
    fi
    case "${answer:-Y}" in
        [Yy]*|"")
            git -C "$project_dir" init
            success "Git repository initialized"
            ;;
        *)
            warn "Git repository not initialized."
            info "Note: aitask framework is designed to be tracked in git."
            info "You can run 'git init' later and commit the aitask files."
            ;;
    esac
}

# Module-level flag so warn_missing_remote_for_branch() prompts only once
# per setup run. Both setup_id_counter and setup_lock_branch consult this.
_AIT_SETUP_NO_REMOTE_ACKED=""

# Warn that a required orphan branch cannot be initialized because no git
# remote is configured. Explain the fix and prompt for acknowledgment.
# On acknowledgment, set the module-level flag and return 0 — the caller
# should then `return` to skip its lock/init step. On refusal, abort setup.
# Subsequent calls during the same run are no-ops (return 0 silently).
#
# Args: $1 = branch name (e.g. "aitask-locks"), $2 = purpose label
warn_missing_remote_for_branch() {
    local branch="$1"
    local purpose="$2"

    if [[ "$_AIT_SETUP_NO_REMOTE_ACKED" == "1" ]]; then
        info "Skipping '$branch' setup — no remote (already acknowledged)"
        return 0
    fi

    warn "No git remote 'origin' configured."
    info "Cannot initialize the '$branch' orphan branch without a remote."
    info "$purpose will not work for cross-machine coordination, and"
    info "later 'ait pick' calls may fail with LOCK_ERROR:fetch_failed."
    info ""
    info "To fix:"
    info "  git remote add origin <url>"
    info "  ait setup    # re-run after adding the remote"
    info ""

    local answer
    if [[ -t 0 ]]; then
        printf "  Continue setup without '%s' (acknowledge)? [Y/n] " "$branch"
        read -r answer
    else
        info "(non-interactive: auto-accepting acknowledgment)"
        answer="Y"
    fi

    case "${answer:-Y}" in
        [Yy]*|"")
            _AIT_SETUP_NO_REMOTE_ACKED=1
            warn "Continuing without '$branch'. Re-run 'ait setup' after adding the remote."
            return 0
            ;;
        *)
            die "Setup aborted. Configure a git remote and re-run 'ait setup'."
            ;;
    esac
}

# --- Task ID counter setup ---
setup_id_counter() {
    local project_dir="$SCRIPT_DIR/.."

    # Only setup if we have a git repo with a remote
    if ! git -C "$project_dir" rev-parse --is-inside-work-tree &>/dev/null; then
        return
    fi
    if ! git -C "$project_dir" remote get-url origin &>/dev/null; then
        warn_missing_remote_for_branch "aitask-ids" "Atomic task ID assignment"
        return
    fi

    # Check if branch already exists
    if git ls-remote --heads origin "aitask-ids" 2>/dev/null | grep -q "aitask-ids"; then
        success "Task ID counter branch already initialized"
        return
    fi

    info "Setting up shared task ID counter..."
    info "This creates a lightweight branch 'aitask-ids' on the remote to"
    info "prevent ID collisions when multiple PCs create tasks."

    if [[ -t 0 ]]; then
        printf "  Initialize task ID counter? [Y/n] "
        read -r answer
    else
        info "(non-interactive: auto-accepting default)"
        answer="Y"
    fi

    case "${answer:-Y}" in
        [Yy]*|"")
            (cd "$project_dir" && "$SCRIPT_DIR/aitask_claim_id.sh" --init)
            ;;
        *)
            warn "Skipped task ID counter setup."
            info "You can initialize later by re-running: ait setup"
            ;;
    esac
}

# --- Task lock branch setup ---
setup_lock_branch() {
    local project_dir="$SCRIPT_DIR/.."

    # Only setup if we have a git repo with a remote
    if ! git -C "$project_dir" rev-parse --is-inside-work-tree &>/dev/null; then
        return
    fi
    if ! git -C "$project_dir" remote get-url origin &>/dev/null; then
        warn_missing_remote_for_branch "aitask-locks" "Task locking"
        return
    fi

    # Check if branch already exists
    if git ls-remote --heads origin "aitask-locks" 2>/dev/null | grep -q "aitask-locks"; then
        success "Task lock branch already initialized"
        return
    fi

    info "Setting up task lock branch..."
    info "This creates a lightweight branch 'aitask-locks' on the remote to"
    info "prevent two users from picking the same task simultaneously."

    if [[ -t 0 ]]; then
        printf "  Initialize task lock branch? [Y/n] "
        read -r answer
    else
        info "(non-interactive: auto-accepting default)"
        answer="Y"
    fi

    case "${answer:-Y}" in
        [Yy]*|"")
            (cd "$project_dir" && "$SCRIPT_DIR/aitask_lock.sh" --init)
            ;;
        *)
            warn "Skipped task lock branch setup."
            info "You can initialize later by re-running: ait setup"
            ;;
    esac
}

# --- Assemble aitasks instructions from Layer 1 (shared) + optional Layer 2 (agent-specific) ---
# Usage: assemble_aitasks_instructions <project_dir> [agent_type]
# agent_type: claude, codex, geminicli, opencode (omit for shared-only)
assemble_aitasks_instructions() {
    local project_dir="$1"
    local agent_type="${2:-}"
    local shared="$project_dir/aitasks/metadata/aitasks_agent_instructions.seed.md"

    if [[ ! -f "$shared" ]]; then
        warn "Shared instructions seed not found: $shared"
        return 1
    fi

    # Layer 1: shared content
    cat "$shared"

    # Layer 2: agent-specific additions (if requested and file exists)
    if [[ -n "$agent_type" ]]; then
        local specific="$project_dir/aitasks/metadata/${agent_type}_instructions.seed.md"
        if [[ -f "$specific" ]]; then
            echo ""
            # Skip header lines that reference the shared file (lines before first ## heading)
            sed -n '/^## /,$p' "$specific"
        fi
    fi
}

# --- Insert or replace aitasks instructions using >>>aitasks/<<<aitasks markers ---
# Usage: insert_aitasks_instructions <target_file> <content>
# If markers exist: replaces content between them
# If no markers: appends marked block
# If file doesn't exist: creates it with marked block
insert_aitasks_instructions() {
    local target="$1"
    local content="$2"
    local marker_start=">>>aitasks"
    local marker_end="<<<aitasks"
    local marked_block
    marked_block="$(printf '%s\n%s\n%s' "$marker_start" "$content" "$marker_end")"

    if [[ ! -f "$target" ]]; then
        echo "$marked_block" > "$target"
        return
    fi

    if grep -qF "$marker_start" "$target"; then
        # Replace content between markers
        local tmpfile
        tmpfile="$(mktemp "${TMPDIR:-/tmp}/aitasks_insert_XXXXXX")"
        _awk_block="$marked_block" awk -v start="$marker_start" -v end="$marker_end" '
            BEGIN { block = ENVIRON["_awk_block"] }
            $0 == start { print block; skip=1; next }
            $0 == end && skip { skip=0; next }
            !skip { print }
        ' "$target" > "$tmpfile"
        mv "$tmpfile" "$target"
    else
        # Append marked block
        { echo ""; echo "$marked_block"; } >> "$target"
    fi
}

# --- CLAUDE.md auto-update for aitasks instructions ---
update_claudemd_git_section() {
    local project_dir="$1"
    local claudemd="$project_dir/CLAUDE.md"

    local content
    content="$(assemble_aitasks_instructions "$project_dir" "claude")" || return

    insert_aitasks_instructions "$claudemd" "$content"

    if grep -qF ">>>aitasks" "$claudemd"; then
        info "  Updated aitasks instructions in CLAUDE.md"
    fi
}

# --- AGENTS.md auto-update for aitasks instructions ---
# AGENTS.md is a cross-agent convention (codex reads it at repo root; other
# agents may too). Uses the shared aitasks layer only — agent-specific
# guidance stays in its own file (GEMINI.md, .codex/instructions.md).
update_agentsmd() {
    local project_dir="$1"
    local agentsmd="$project_dir/AGENTS.md"

    local content
    content="$(assemble_aitasks_instructions "$project_dir")" || return

    insert_aitasks_instructions "$agentsmd" "$content"

    if grep -qF ">>>aitasks" "$agentsmd"; then
        info "  Updated aitasks instructions in AGENTS.md"
    fi
}

# --- Task data branch setup (aitask-data orphan branch + worktree + symlinks) ---
setup_data_branch() {
    local project_dir="$SCRIPT_DIR/.."

    # Only setup if we have a git repo
    if ! git -C "$project_dir" rev-parse --is-inside-work-tree &>/dev/null; then
        return
    fi

    # Already configured — worktree exists
    if [[ -d "$project_dir/.aitask-data/.git" || -f "$project_dir/.aitask-data/.git" ]]; then
        success "Task data branch already configured (.aitask-data/ worktree exists)"
        return
    fi

    # Detect migration scenario: aitasks/ exists as a real directory (not symlink)
    local needs_migration=false
    if [[ -d "$project_dir/aitasks" && ! -L "$project_dir/aitasks" ]]; then
        needs_migration=true
    fi

    local has_remote=false
    if git -C "$project_dir" remote get-url origin &>/dev/null; then
        has_remote=true
    fi

    if [[ "$needs_migration" == true ]]; then
        info "Detected existing task data on main branch."
        info "Setting up a separate 'aitask-data' branch will:"
        info "  - Move task/plan files to an independent branch"
        info "  - Create symlinks so all paths remain unchanged"
        info "  - Enable independent sync of task data across PCs"
    else
        info "Setting up separate task data branch..."
        info "This creates an 'aitask-data' orphan branch with a permanent"
        info "worktree at .aitask-data/ and symlinks for seamless access."
    fi

    if [[ -t 0 ]]; then
        printf "  Use a separate branch for task data? [Y/n] "
        read -r answer
    else
        info "(non-interactive: auto-accepting default)"
        answer="Y"
    fi

    case "${answer:-Y}" in
        [Yy]*|"")
            ;;
        *)
            warn "Skipped task data branch setup."
            info "You can set this up later by re-running: ait setup"
            return
            ;;
    esac

    # --- Step 1: Get or create aitask-data branch ---
    local branch_exists=false

    # Check remote first (if available)
    if [[ "$has_remote" == true ]]; then
        if git -C "$project_dir" ls-remote --heads origin "aitask-data" 2>/dev/null | grep -q "aitask-data"; then
            info "Found aitask-data branch on remote — fetching..."
            git -C "$project_dir" fetch origin aitask-data 2>/dev/null || true
            branch_exists=true
        fi
    fi

    # Check local
    if [[ "$branch_exists" == false ]] && git -C "$project_dir" show-ref --verify refs/heads/aitask-data &>/dev/null; then
        branch_exists=true
    fi

    # Create if not found
    if [[ "$branch_exists" == false ]]; then
        info "Creating aitask-data orphan branch..."
        local empty_tree_hash commit_hash
        empty_tree_hash=$(git -C "$project_dir" mktree < /dev/null)
        commit_hash=$(echo "ait: Initialize aitask-data branch" | git -C "$project_dir" commit-tree "$empty_tree_hash")
        git -C "$project_dir" update-ref refs/heads/aitask-data "$commit_hash"

        if [[ "$has_remote" == true ]]; then
            git -C "$project_dir" push -u origin aitask-data 2>/dev/null || warn "Could not push aitask-data branch to remote"
        fi
    fi

    # --- Step 2: Create worktree ---
    info "Creating .aitask-data/ worktree..."
    (cd "$project_dir" && git worktree add .aitask-data aitask-data 2>/dev/null) || {
        warn "Failed to create worktree. You may need to run: git worktree add .aitask-data aitask-data"
        return
    }

    # --- Step 3: Populate data ---
    if [[ "$needs_migration" == true ]]; then
        info "Migrating task data to aitask-data branch..."
        mkdir -p "$project_dir/.aitask-data/aitasks" "$project_dir/.aitask-data/aiplans"
        # Copy all existing data (preserving structure, including drafts)
        cp -a "$project_dir/aitasks/." "$project_dir/.aitask-data/aitasks/" 2>/dev/null || true
        if [[ -d "$project_dir/aiplans" ]]; then
            cp -a "$project_dir/aiplans/." "$project_dir/.aitask-data/aiplans/" 2>/dev/null || true
        fi
    else
        info "Creating task data directory structure..."
        mkdir -p "$project_dir/.aitask-data/aitasks/metadata"
        mkdir -p "$project_dir/.aitask-data/aitasks/archived"
        mkdir -p "$project_dir/.aitask-data/aiplans/archived"

        # Copy seed metadata if available
        if [[ -d "$project_dir/seed" ]]; then
            cp "$project_dir/seed/task_types.txt" "$project_dir/.aitask-data/aitasks/metadata/" 2>/dev/null || true
            cp "$project_dir/seed/project_config.yaml" "$project_dir/.aitask-data/aitasks/metadata/" 2>/dev/null || true
            cp "$project_dir/seed/code_areas.yaml" "$project_dir/.aitask-data/aitasks/metadata/" 2>/dev/null || true
            cp "$project_dir/seed/codeagent_config.json" "$project_dir/.aitask-data/aitasks/metadata/" 2>/dev/null || true
            cp "$project_dir/seed"/models_*.json "$project_dir/.aitask-data/aitasks/metadata/" 2>/dev/null || true
            cp "$project_dir/seed/"*_instructions.seed.md "$project_dir/.aitask-data/aitasks/metadata/" 2>/dev/null || true
            if [[ -d "$project_dir/seed/profiles" ]]; then
                mkdir -p "$project_dir/.aitask-data/aitasks/metadata/profiles"
                cp "$project_dir/seed/profiles/"*.yaml "$project_dir/.aitask-data/aitasks/metadata/profiles/" 2>/dev/null || true
            fi
        fi
    fi

    # Add aitasks/new/ to data branch .gitignore
    local data_gitignore="$project_dir/.aitask-data/.gitignore"
    if [[ ! -f "$data_gitignore" ]] || ! grep -qxF "aitasks/new/" "$data_gitignore" 2>/dev/null; then
        {
            echo "# Draft tasks (local, not committed)"
            echo "aitasks/new/"
        } >> "$data_gitignore"
    fi

    # Add userconfig.yaml to data branch .gitignore (per-user, not shared)
    if ! grep -qxF "aitasks/metadata/userconfig.yaml" "$data_gitignore" 2>/dev/null; then
        {
            echo ""
            echo "# Per-user config (local, not shared)"
            echo "aitasks/metadata/userconfig.yaml"
        } >> "$data_gitignore"
    fi

    # Add *.local.json to data branch .gitignore (per-user overrides, not shared)
    if ! grep -qF "*.local.json" "$data_gitignore" 2>/dev/null; then
        {
            echo ""
            echo "# Per-user overrides (*.local.json files, not shared)"
            echo "aitasks/metadata/*.local.json"
        } >> "$data_gitignore"
    fi

    # Add profiles/local/ to data branch .gitignore (per-user profiles, not shared)
    if ! grep -qF "profiles/local/" "$data_gitignore" 2>/dev/null; then
        {
            echo ""
            echo "# Per-user execution profiles (local, not shared)"
            echo "aitasks/metadata/profiles/local/"
        } >> "$data_gitignore"
    fi

    # --- Step 4: Commit and push on data branch ---
    (
        cd "$project_dir/.aitask-data"
        git add .
        if ! git diff --cached --quiet 2>/dev/null; then
            if [[ "$needs_migration" == true ]]; then
                git commit -m "ait: Migrate task data from main branch"
            else
                git commit -m "ait: Initialize task data structure"
            fi
            if [[ "$has_remote" == true ]]; then
                git push 2>/dev/null || warn "Could not push data branch to remote"
            fi
        fi
    )

    # --- Step 5: Clean up main (migration only) ---
    if [[ "$needs_migration" == true ]]; then
        info "Removing task data from main branch..."
        (
            cd "$project_dir"
            git rm -r --quiet aitasks/ 2>/dev/null || true
            git rm -r --quiet aiplans/ 2>/dev/null || true
            # Remove any remaining untracked files/dirs
            rm -rf aitasks/ aiplans/
        )
    fi

    # --- Step 6: Create symlinks ---
    (
        cd "$project_dir"
        if [[ ! -L "aitasks" ]]; then
            ln -sf .aitask-data/aitasks aitasks
        fi
        if [[ ! -L "aiplans" ]]; then
            ln -sf .aitask-data/aiplans aiplans
        fi
    )

    # --- Step 7: Update .gitignore on main ---
    local gitignore="$project_dir/.gitignore"
    local gitignore_changed=false

    # Migration: rewrite legacy trailing-slash entries to symlink-safe form.
    # Trailing-slash patterns (`aitasks/`) match directories only and miss
    # the symlinks setup_data_branch creates; bare entries (`aitasks`)
    # match both. Older repos may already have the legacy form committed.
    if [[ -f "$gitignore" ]] && \
       { grep -qxF "aitasks/" "$gitignore" 2>/dev/null || \
         grep -qxF "aiplans/" "$gitignore" 2>/dev/null; }; then
        local tmp_gitignore
        tmp_gitignore="$(mktemp "${TMPDIR:-/tmp}/aitask_gitignore_XXXXXX")"
        awk '
            /^aitasks\/$/ { print "aitasks"; next }
            /^aiplans\/$/ { print "aiplans"; next }
            { print }
        ' "$gitignore" > "$tmp_gitignore" && mv "$tmp_gitignore" "$gitignore"
        gitignore_changed=true
    fi

    if [[ ! -f "$gitignore" ]] || ! grep -qxF ".aitask-data/" "$gitignore" 2>/dev/null; then
        {
            echo ""
            echo "# Task data (lives on aitask-data branch, accessed via symlinks)"
            echo ".aitask-data/"
            echo "aitasks"
            echo "aiplans"
        } >> "$gitignore"
        gitignore_changed=true
    fi

    # --- Step 8: Update CLAUDE.md ---
    update_claudemd_git_section "$project_dir"

    # --- Step 9: Commit on main ---
    (
        cd "$project_dir"
        local files_to_add=()
        if [[ "$gitignore_changed" == true ]]; then
            files_to_add+=(".gitignore")
        fi
        if [[ -f "CLAUDE.md" ]]; then
            files_to_add+=("CLAUDE.md")
        fi
        if [[ ${#files_to_add[@]} -gt 0 ]]; then
            git add "${files_to_add[@]}" 2>/dev/null || true
        fi
        if ! git diff --cached --quiet 2>/dev/null; then
            if [[ "$needs_migration" == true ]]; then
                git commit -m "ait: Migrate task data to aitask-data branch"
            else
                git commit -m "ait: Configure task data branch with worktree and symlinks"
            fi
        fi
    )

    success "Task data branch configured successfully"
    info "  Worktree: .aitask-data/"
    info "  Symlinks: aitasks/ → .aitask-data/aitasks/, aiplans/ → .aitask-data/aiplans/"
    if [[ "$needs_migration" == true ]]; then
        info "  Migration: task/plan data moved from main to aitask-data branch"
    fi
}

ensure_project_config_defaults() {
    local project_dir="$SCRIPT_DIR/.."
    local seed_config="$project_dir/seed/project_config.yaml"
    local target_config="$project_dir/aitasks/metadata/project_config.yaml"
    local default_domain="aitasks.io"

    # If target is missing, try to create it from seed. install.sh installs
    # project_config.yaml into aitasks/metadata/ directly (and deletes seed/
    # afterwards), so in normal flow target exists here. The seed fallback
    # still matters for in-tree dev runs where seed/ is preserved.
    if [[ ! -f "$target_config" ]]; then
        if [[ ! -f "$seed_config" ]]; then
            warn "project_config.yaml is missing from aitasks/metadata/ and no seed template is available."
            warn "tmux default_session and git_tui setup will be skipped."
            warn "Re-run 'ait setup' to populate the project config from the seed."
            return
        fi
        mkdir -p "$(dirname "$target_config")"
        cp "$seed_config" "$target_config"
        success "Created project_config.yaml"
        return
    fi

    # Target exists — backfill codeagent_coauthor_domain if missing
    if grep -Eq '^[[:space:]]*codeagent_coauthor_domain:[[:space:]]*' "$target_config"; then
        return
    fi

    local tmp_file
    tmp_file="$(mktemp)"
    awk -v domain="$default_domain" '
        BEGIN { inserted = 0 }
        /^[[:space:]]*verify_build:[[:space:]]*$/ && inserted == 0 {
            print "codeagent_coauthor_domain: " domain
            print ""
            inserted = 1
        }
        { print }
        END {
            if (inserted == 0) {
                print ""
                print "codeagent_coauthor_domain: " domain
            }
        }
    ' "$target_config" > "$tmp_file"
    cat "$tmp_file" > "$target_config" && rm "$tmp_file"
    success "Updated project_config.yaml with codeagent_coauthor_domain"
}

# --- Draft directory and gitignore setup ---
setup_draft_directory() {
    local project_dir="$SCRIPT_DIR/.."
    local gitignore="$project_dir/.gitignore"
    local draft_dir="$project_dir/aitasks/new"

    # Create draft directory
    mkdir -p "$draft_dir"

    # Add to .gitignore if not already there
    if [[ -f "$gitignore" ]] && grep -qxF "aitasks/new/" "$gitignore"; then
        success "Draft directory already in .gitignore"
        return
    fi

    info "Adding aitasks/new/ to .gitignore (draft tasks are local-only)..."

    if [[ -f "$gitignore" ]]; then
        echo "" >> "$gitignore"
        echo "# Draft tasks (local, not committed)" >> "$gitignore"
        echo "aitasks/new/" >> "$gitignore"
    else
        {
            echo "# Draft tasks (local, not committed)"
            echo "aitasks/new/"
        } > "$gitignore"
    fi

    # Commit the change if inside a git repo
    if git -C "$project_dir" rev-parse --is-inside-work-tree &>/dev/null; then
        (cd "$project_dir" && git add .gitignore && git commit -m "ait: Add aitasks/new/ to .gitignore (draft tasks)" 2>/dev/null) || true
    fi

    success "Draft directory configured (aitasks/new/ in .gitignore)"
}

# --- Python cache artifact gitignore rule ---
# Runs after setup_draft_directory (which ensures .gitignore exists).
setup_python_cache_gitignore() {
    local project_dir="$SCRIPT_DIR/.."
    local gitignore="$project_dir/.gitignore"

    if [[ -f "$gitignore" ]] && grep -qxF "__pycache__/" "$gitignore"; then
        success "Python cache rule already in .gitignore"
        return
    fi

    info "Adding __pycache__/ to .gitignore (Python cache artifacts)..."

    if [[ -f "$gitignore" ]]; then
        echo "" >> "$gitignore"
        echo "# Python cache artifacts (generated by aitasks Python TUIs)" >> "$gitignore"
        echo "__pycache__/" >> "$gitignore"
    else
        {
            echo "# Python cache artifacts (generated by aitasks Python TUIs)"
            echo "__pycache__/"
        } > "$gitignore"
    fi

    # Commit the change if inside a git repo
    if git -C "$project_dir" rev-parse --is-inside-work-tree &>/dev/null; then
        (cd "$project_dir" && git add .gitignore && git commit -m "ait: Add __pycache__/ to .gitignore (Python cache artifacts)" 2>/dev/null) || true
    fi

    success "Python cache rule added to .gitignore"
}

# --- Version check ---
check_latest_version() {
    local local_version=""
    if [[ -f "$VERSION_FILE" ]]; then
        local_version="$(cat "$VERSION_FILE")"
    else
        return
    fi

    local latest_version=""
    latest_version="$(curl -sS --max-time 5 "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null \
        | grep '"tag_name"' | head -1 | sed 's/.*"tag_name": *"v\?\([^"]*\)".*/\1/')" || true

    if [[ -z "$latest_version" ]]; then
        return
    fi

    if [[ "$local_version" != "$latest_version" ]]; then
        echo ""
        info "Update available: $local_version → $latest_version"
        info "Run: ait upgrade latest"
    fi
}

# --- Merge Claude Code settings (union of permissions.allow) ---
merge_claude_settings() {
    local seed_file="$1"
    local dest_file="$2"
    local merged=""

    if command -v jq &>/dev/null; then
        merged="$(jq -s '
            .[0] as $existing |
            .[1] as $seed |
            $existing * {
                permissions: {
                    allow: (
                        ($existing.permissions.allow // []) +
                        (($seed.permissions.allow // []) - ($existing.permissions.allow // []))
                    )
                }
            }
        ' "$dest_file" "$seed_file")"
    elif command -v python3 &>/dev/null; then
        merged="$(python3 -c "
import json, sys
with open(sys.argv[1]) as f:
    existing = json.load(f)
with open(sys.argv[2]) as f:
    seed = json.load(f)
existing_allow = existing.get('permissions', {}).get('allow', [])
seed_allow = seed.get('permissions', {}).get('allow', [])
seen = set(existing_allow)
merged = list(existing_allow)
for entry in seed_allow:
    if entry not in seen:
        merged.append(entry)
        seen.add(entry)
existing.setdefault('permissions', {})['allow'] = merged
print(json.dumps(existing, indent=2))
" "$dest_file" "$seed_file")"
    else
        warn "Neither jq nor python3 found. Cannot merge settings automatically."
        warn "Please manually merge $seed_file into $dest_file"
        return
    fi

    if [[ -n "$merged" ]]; then
        echo "$merged" > "$dest_file"
        info "  Merged aitask permissions into .claude/settings.local.json"
    else
        warn "  Merge produced empty output — existing settings unchanged"
    fi
}

# Merge Gemini CLI TOML policy files (deduplicate rules by toolName+commandPrefix/commandRegex)
merge_gemini_policies() {
    local seed_file="$1"
    local dest_file="$2"

    local python_cmd=""
    if [[ -x "$VENV_DIR/bin/python" ]]; then
        python_cmd="$VENV_DIR/bin/python"
    elif command -v python3 &>/dev/null; then
        python_cmd="python3"
    else
        warn "python3 not found. Cannot merge Gemini policies automatically."
        warn "Please manually merge $seed_file into $dest_file"
        return
    fi

    local merged=""
    merged="$("$python_cmd" -c "
import sys, re

def parse_toml_rules(path):
    rules = []
    current = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line == '[[rule]]':
                if current:
                    rules.append(current)
                current = {}
            elif '=' in line:
                key, _, val = line.partition('=')
                key = key.strip()
                val = val.strip().strip('\"')
                current[key] = val
        if current:
            rules.append(current)
    return rules

def rule_key(r):
    tool = r.get('toolName', '')
    prefix = r.get('commandPrefix', '')
    regex = r.get('commandRegex', '')
    pattern = r.get('argsPattern', '')
    return (tool, prefix, regex, pattern)

def rule_to_toml(r):
    lines = ['[[rule]]']
    for key in ['toolName', 'commandPrefix', 'commandRegex', 'argsPattern', 'decision', 'priority']:
        if key in r:
            val = r[key]
            if key == 'priority':
                lines.append(f'{key} = {val}')
            else:
                lines.append(f'{key} = \"{val}\"')
    return '\n'.join(lines)

existing = parse_toml_rules(sys.argv[1])
seed = parse_toml_rules(sys.argv[2])

seen = set(rule_key(r) for r in existing)
for r in seed:
    k = rule_key(r)
    if k not in seen:
        existing.append(r)
        seen.add(k)

print('\n\n'.join(rule_to_toml(r) for r in existing) + '\n')
" "$dest_file" "$seed_file")"

    if [[ -n "$merged" ]]; then
        echo "$merged" > "$dest_file"
        info "  Merged aitask policy rules into .gemini/policies/aitasks-whitelist.toml"
    else
        warn "  Merge produced empty output — existing policies unchanged"
    fi
}

install_gemini_global_policy() {
    local source_policy="$1"
    local global_dir="$HOME/.gemini/policies"
    local fname
    local global_file

    fname="$(basename "$source_policy")"
    global_file="$global_dir/$fname"

    mkdir -p "$global_dir"

    if [[ ! -f "$global_file" ]]; then
        cp "$source_policy" "$global_file"
        success "  Created ~/.gemini/policies/$fname"
    else
        info "  Existing ~/.gemini/policies/$fname found — merging policies..."
        merge_gemini_policies "$source_policy" "$global_file"
    fi
}

# Merge Gemini CLI settings.json (ensure policyPaths contains .gemini/policies/)
merge_gemini_settings() {
    local seed_file="$1"
    local dest_file="$2"
    local merged=""

    if command -v jq &>/dev/null; then
        merged="$(jq -s '
            .[0] as $existing |
            .[1] as $seed |
            $existing * $seed |
            .policyPaths = (
                (($existing.policyPaths // []) + (($seed.policyPaths // []) - ($existing.policyPaths // [])))
            )
        ' "$dest_file" "$seed_file")"
    elif command -v python3 &>/dev/null; then
        merged="$(python3 -c "
import json, sys
with open(sys.argv[1]) as f:
    existing = json.load(f)
with open(sys.argv[2]) as f:
    seed = json.load(f)
for key, value in seed.items():
    if key == 'policyPaths':
        existing_paths = existing.get('policyPaths', [])
        for p in value:
            if p not in existing_paths:
                existing_paths.append(p)
        existing['policyPaths'] = existing_paths
    elif key not in existing:
        existing[key] = value
    elif isinstance(existing[key], dict) and isinstance(value, dict):
        existing[key].update(value)
print(json.dumps(existing, indent=2))
" "$dest_file" "$seed_file")"
    else
        warn "Neither jq nor python3 found. Cannot merge settings automatically."
        warn "Please manually merge $seed_file into $dest_file"
        return
    fi

    if [[ -n "$merged" ]]; then
        echo "$merged" > "$dest_file"
        info "  Merged aitask settings into .gemini/settings.json"
    else
        warn "  Merge produced empty output — existing settings unchanged"
    fi
}

# --- Claude Code setup (settings, permissions) ---
setup_claude_code() {
    local project_dir="$SCRIPT_DIR/.."
    local seed_file="$project_dir/aitasks/metadata/claude_settings.seed.json"
    local dest_dir="$project_dir/.claude"
    local dest_file="$dest_dir/settings.local.json"

    if [[ ! -f "$seed_file" ]]; then
        return
    fi

    echo ""
    info "The following Claude Code permissions are recommended for aitask skills:"
    info "These allow aitask skills to run without manual approval each time."
    echo ""
    grep '"Bash(' "$seed_file" | sed 's/^[[:space:]]*/  /' | sed 's/",\?$//' | sed 's/^  "/  /'
    echo ""

    if [[ -t 0 ]]; then
        printf "  Install these Claude Code permissions? [Y/n] "
        read -r answer
    else
        info "(non-interactive: auto-accepting default)"
        answer="Y"
    fi
    case "${answer:-Y}" in
        [Yy]*|"") ;;
        *)
            info "Skipped Claude Code permission settings."
            return
            ;;
    esac

    mkdir -p "$dest_dir"

    if [[ ! -f "$dest_file" ]]; then
        cp "$seed_file" "$dest_file"
        info "  Created .claude/settings.local.json with aitask permissions"
    else
        info "  Existing .claude/settings.local.json found — merging permissions..."
        merge_claude_settings "$seed_file" "$dest_file"
    fi
}

# --- Gemini CLI setup ---
setup_gemini_cli() {
    local project_dir="$SCRIPT_DIR/.."
    local staging_skills="$project_dir/aitasks/metadata/geminicli_skills"
    local staging_commands="$project_dir/aitasks/metadata/geminicli_commands"
    local staging_policies="$project_dir/aitasks/metadata/geminicli_policies"
    local staging_settings="$project_dir/aitasks/metadata/geminicli_settings.seed.json"
    local dest_skills="$project_dir/.gemini/skills"
    local dest_commands="$project_dir/.gemini/commands"
    local dest_policies="$project_dir/.gemini/policies"
    local dest_settings="$project_dir/.gemini/settings.json"

    if [[ ! -d "$staging_skills" && ! -d "$staging_commands" \
          && ! -d "$staging_policies" && ! -f "$staging_settings" ]]; then
        info "No Gemini CLI staging files found — skipping"
        info "  Re-run 'ait setup' to restore Gemini CLI support files"
        return
    fi

    echo ""
    info "Gemini CLI helper docs and commands ready for installation."
    echo ""

    if [[ -t 0 ]]; then
        printf "  Install Gemini CLI commands and helper docs? [Y/n] "
        read -r answer
    else
        info "(non-interactive: auto-accepting default)"
        answer="Y"
    fi
    case "${answer:-Y}" in
        [Yy]*|"") ;;
        *)
            info "Skipped Gemini CLI installation."
            return
            ;;
    esac

    # 1. Copy helper docs (skill wrappers are now unified in .agents/skills/)
    if [[ -d "$staging_skills" ]]; then
        mkdir -p "$dest_skills"
        for doc in geminicli_tool_mapping.md geminicli_planmode_prereqs.md; do
            if [[ -f "$staging_skills/$doc" ]]; then
                cp "$staging_skills/$doc" "$dest_skills/$doc"
            fi
        done
        success "  Installed Gemini CLI helper docs to .gemini/skills/"
    fi

    # 1b. Copy command wrappers
    if [[ -d "$staging_commands" ]]; then
        mkdir -p "$dest_commands"
        cp -r "$staging_commands/." "$dest_commands/"
        success "  Installed Gemini CLI command wrappers to .gemini/commands/"
    fi

    # 2. Assemble and insert instructions (Layer 1 + Layer 2, with markers)
    local content
    content="$(assemble_aitasks_instructions "$project_dir" "geminicli")" || true
    if [[ -n "$content" ]]; then
        insert_aitasks_instructions "$project_dir/GEMINI.md" "$content"
        info "  Installed GEMINI.md (with aitasks markers)"
    fi

    # 3. Install permission policies (with user approval)
    if [[ -d "$staging_policies" || -f "$staging_settings" ]]; then
        echo ""
        info "The following Gemini CLI permission policies are recommended for aitask skills:"
        info "These allow aitask skills to run shell commands without manual approval each time."
        echo ""
        if [[ -d "$staging_policies" ]]; then
            grep 'commandPrefix' "$staging_policies"/*.toml 2>/dev/null | sed 's/^.*commandPrefix[[:space:]]*=[[:space:]]*/  /' | sed 's/"//g'
        fi
        echo ""

        local policy_answer
        if [[ -t 0 ]]; then
            printf "  Install these Gemini CLI permission policies? [Y/n] "
            read -r policy_answer
        else
            info "(non-interactive: auto-accepting default)"
            policy_answer="Y"
        fi
        case "${policy_answer:-Y}" in
            [Yy]*|"") ;;
            *)
                info "Skipped Gemini CLI permission policies."
                return
                ;;
        esac

        # 3a. Install policies
        local first_installed_policy=""
        if [[ -d "$staging_policies" ]]; then
            mkdir -p "$dest_policies"
            for policy_file in "$staging_policies"/*.toml; do
                [[ -f "$policy_file" ]] || continue
                local fname
                fname="$(basename "$policy_file")"
                if [[ -z "$first_installed_policy" ]]; then
                    first_installed_policy="$dest_policies/$fname"
                fi
                if [[ ! -f "$dest_policies/$fname" ]]; then
                    cp "$policy_file" "$dest_policies/$fname"
                    success "  Created .gemini/policies/$fname"
                else
                    info "  Existing .gemini/policies/$fname found — merging policies..."
                    merge_gemini_policies "$policy_file" "$dest_policies/$fname"
                fi
            done
        fi

        # 3a.1 Offer global policy sync (explicit consent only)
        if [[ -n "$first_installed_policy" && -f "$first_installed_policy" ]]; then
            echo ""
            info "Gemini CLI currently ignores per-project policyPaths in some workflows."
            info "You can also install the aitasks allowlist globally so Gemini CLI uses it automatically."
            info ""
            info "  Source: $first_installed_policy"
            info "  Destination: ~/.gemini/policies/$(basename "$first_installed_policy")"
            info "  Behavior: create if missing, merge if it already exists"
            info ""
            info "Policy preview:"
            sed 's/^/  /' "$first_installed_policy"
            echo ""

            local global_policy_answer="N"
            if [[ -t 0 ]]; then
                printf "  Also install or merge this Gemini CLI allowlist globally? [y/N] "
                read -r global_policy_answer
            else
                info "(non-interactive: skipping global Gemini policy install because explicit consent is required)"
            fi

            case "${global_policy_answer:-N}" in
                [Yy]*)
                    install_gemini_global_policy "$first_installed_policy"
                    ;;
                *)
                    info "Skipped global Gemini CLI allowlist installation."
                    ;;
            esac
        fi

        # 3b. Install settings.json
        if [[ -f "$staging_settings" ]]; then
            if [[ ! -f "$dest_settings" ]]; then
                cp "$staging_settings" "$dest_settings"
                success "  Created .gemini/settings.json"
            else
                info "  Existing .gemini/settings.json found — merging settings..."
                merge_gemini_settings "$staging_settings" "$dest_settings"
            fi
        fi
    fi
}

# --- Merge Codex CLI config.toml (add aitask-specific settings) ---
merge_codex_settings() {
    local seed_file="$1"
    local dest_file="$2"

    # Prefer venv Python, fall back to system python3
    local python_cmd=""
    if [[ -x "$VENV_DIR/bin/python" ]]; then
        python_cmd="$VENV_DIR/bin/python"
    elif command -v python3 &>/dev/null; then
        python_cmd="python3"
    else
        warn "python3 not found. Cannot merge Codex settings automatically."
        warn "Please manually merge $seed_file into $dest_file"
        return
    fi

    local merged=""
    merged="$("$python_cmd" -c "
import sys

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        print('ERROR: No TOML parser available (need Python 3.11+ or tomli)', file=sys.stderr)
        sys.exit(1)

with open(sys.argv[1], 'rb') as f:
    existing = tomllib.load(f)
with open(sys.argv[2], 'rb') as f:
    seed = tomllib.load(f)

def deep_merge(base, overlay):
    result = dict(base)
    for key, value in overlay.items():
        if key not in result:
            result[key] = value
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        elif isinstance(result[key], list) and isinstance(value, list):
            existing_strs = [str(item) for item in result[key]]
            for item in value:
                if str(item) not in existing_strs:
                    result[key].append(item)
    return result

merged = deep_merge(existing, seed)

def toml_serialize(d, prefix=''):
    lines = []
    tables = []
    array_tables = []
    for k, v in d.items():
        full_key = f'{prefix}.{k}' if prefix else k
        if isinstance(v, dict):
            tables.append((full_key, v))
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            array_tables.append((full_key, v))
        elif isinstance(v, bool):
            lines.append(f'{k} = {str(v).lower()}')
        elif isinstance(v, str):
            lines.append(f'{k} = \"{v}\"')
        elif isinstance(v, (int, float)):
            lines.append(f'{k} = {v}')
        elif isinstance(v, list):
            items = ', '.join(f'\"{i}\"' if isinstance(i, str) else str(i) for i in v)
            lines.append(f'{k} = [{items}]')
    for line in lines:
        print(line)
    for full_key, table in tables:
        print(f'\n[{full_key}]')
        toml_serialize(table, full_key)
    for full_key, entries in array_tables:
        for entry in entries:
            print(f'\n[[{full_key}]]')
            toml_serialize(entry, full_key)
toml_serialize(merged)
" "$dest_file" "$seed_file")"

    if [[ -n "$merged" ]]; then
        echo "$merged" > "$dest_file"
        info "  Merged aitask settings into .codex/config.toml"
    else
        warn "  Merge produced empty output — existing config unchanged"
    fi
}

# --- Codex CLI setup (skills + config + instructions) ---
setup_codex_cli() {
    local project_dir="$SCRIPT_DIR/.."
    local staging_skills="$project_dir/aitasks/metadata/codex_skills"
    local dest_skills="$project_dir/.agents/skills"
    local dest_codex="$project_dir/.codex"

    if [[ ! -d "$staging_skills" ]]; then
        info "No Codex CLI staging files found — skipping"
        info "  Re-run 'ait setup' to restore Codex CLI support files"
        return
    fi

    local count=0
    if [[ -d "$staging_skills" ]]; then
        count=$(find "$staging_skills" -name "SKILL.md" -type f 2>/dev/null | wc -l | tr -d ' ')
    fi

    echo ""
    info "Found $count Codex CLI skill wrappers ready for installation."
    echo ""

    if [[ -t 0 ]]; then
        printf "  Install Codex CLI skills and config? [Y/n] "
        read -r answer
    else
        info "(non-interactive: auto-accepting default)"
        answer="Y"
    fi
    case "${answer:-Y}" in
        [Yy]*|"") ;;
        *)
            info "Skipped Codex CLI skill installation."
            return
            ;;
    esac

    # 1. Copy skill wrappers
    mkdir -p "$dest_skills"
    local installed=0
    for skill_dir in "$staging_skills"/aitask-*/; do
        [[ -d "$skill_dir" ]] || continue
        local skill_name
        skill_name="$(basename "$skill_dir")"
        mkdir -p "$dest_skills/$skill_name"
        cp "$skill_dir/SKILL.md" "$dest_skills/$skill_name/SKILL.md"
        installed=$((installed + 1))
    done
    # Copy shared helper docs (codex + gemini)
    for doc in codex_tool_mapping.md codex_interactive_prereqs.md geminicli_tool_mapping.md geminicli_planmode_prereqs.md; do
        if [[ -f "$staging_skills/$doc" ]]; then
            cp "$staging_skills/$doc" "$dest_skills/$doc"
        fi
    done
    success "  Installed $installed unified skill wrappers to .agents/skills/"

    # 2. Assemble and insert instructions (Layer 1 + Layer 2, with markers)
    local content
    content="$(assemble_aitasks_instructions "$project_dir" "codex")" || true
    if [[ -n "$content" ]]; then
        mkdir -p "$dest_codex"
        local dest_instructions="$dest_codex/instructions.md"
        insert_aitasks_instructions "$dest_instructions" "$content"
        info "  Installed .codex/instructions.md (with aitasks markers)"
    fi

    # 3. Merge config.toml seed
    local seed_config="$project_dir/aitasks/metadata/codex_config.seed.toml"
    if [[ -f "$seed_config" ]]; then
        mkdir -p "$dest_codex"
        local dest_config="$dest_codex/config.toml"
        if [[ ! -f "$dest_config" ]]; then
            cp "$seed_config" "$dest_config"
            info "  Created .codex/config.toml from seed"
        else
            info "  Existing .codex/config.toml found — merging aitask settings..."
            merge_codex_settings "$seed_config" "$dest_config"
        fi
    fi
}

# --- Merge OpenCode opencode.json (add aitask-specific settings) ---
merge_opencode_settings() {
    local seed_file="$1"
    local dest_file="$2"

    # Prefer venv Python, fall back to system python3
    local python_cmd=""
    if [[ -x "$VENV_DIR/bin/python" ]]; then
        python_cmd="$VENV_DIR/bin/python"
    elif command -v python3 &>/dev/null; then
        python_cmd="python3"
    else
        warn "python3 not found. Cannot merge OpenCode settings automatically."
        warn "Please manually merge $seed_file into $dest_file"
        return
    fi

    local merged=""
    merged="$("$python_cmd" -c "
import json, sys

with open(sys.argv[1]) as f:
    existing = json.load(f)
with open(sys.argv[2]) as f:
    seed = json.load(f)

def deep_merge(base, overlay):
    result = dict(base)
    for key, value in overlay.items():
        if key not in result:
            result[key] = value
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        elif isinstance(result[key], list) and isinstance(value, list):
            existing_items = [str(item) for item in result[key]]
            for item in value:
                if str(item) not in existing_items:
                    result[key].append(item)
    return result

merged = deep_merge(existing, seed)
print(json.dumps(merged, indent=2))
" "$dest_file" "$seed_file")"

    if [[ -n "$merged" ]]; then
        echo "$merged" > "$dest_file"
        info "  Merged aitask settings into opencode.json"
    else
        warn "  Merge produced empty output — existing config unchanged"
    fi
}

# --- OpenCode setup (skills + config + instructions) ---
setup_opencode() {
    local project_dir="$SCRIPT_DIR/.."
    local staging_skills="$project_dir/aitasks/metadata/opencode_skills"
    local staging_commands="$project_dir/aitasks/metadata/opencode_commands"
    local dest_skills="$project_dir/.opencode/skills"
    local dest_commands="$project_dir/.opencode/commands"
    local dest_opencode="$project_dir/.opencode"

    if [[ ! -d "$staging_skills" && ! -d "$staging_commands" ]]; then
        info "No OpenCode staging files found — skipping"
        info "  Re-run 'ait setup' to restore OpenCode support files"
        return
    fi

    local count
    count=$(find "$staging_skills" -name "SKILL.md" -type f 2>/dev/null | wc -l | tr -d ' ')

    echo ""
    info "Found $count OpenCode skill wrappers ready for installation."
    echo ""

    if [[ -t 0 ]]; then
        printf "  Install OpenCode skills and config? [Y/n] "
        read -r answer
    else
        info "(non-interactive: auto-accepting default)"
        answer="Y"
    fi
    case "${answer:-Y}" in
        [Yy]*|"") ;;
        *)
            info "Skipped OpenCode skill installation."
            return
            ;;
    esac

    # 1. Copy skill wrappers and helper docs
    if [[ -d "$staging_skills" ]]; then
        mkdir -p "$dest_skills"
        local installed=0
        for skill_dir in "$staging_skills"/aitask-*/; do
            [[ -d "$skill_dir" ]] || continue
            local skill_name
            skill_name="$(basename "$skill_dir")"
            mkdir -p "$dest_skills/$skill_name"
            cp "$skill_dir/SKILL.md" "$dest_skills/$skill_name/SKILL.md"
            installed=$((installed + 1))
        done

        if [[ -f "$staging_skills/opencode_tool_mapping.md" ]]; then
            cp "$staging_skills/opencode_tool_mapping.md" "$dest_skills/opencode_tool_mapping.md"
        fi
        if [[ -f "$staging_skills/opencode_planmode_prereqs.md" ]]; then
            cp "$staging_skills/opencode_planmode_prereqs.md" "$dest_skills/opencode_planmode_prereqs.md"
        fi

        success "  Installed $installed OpenCode skill wrappers to .opencode/skills/"
    fi

    # 1b. Copy command wrappers
    if [[ -d "$staging_commands" ]]; then
        mkdir -p "$dest_commands"
        cp -r "$staging_commands/." "$dest_commands/"
        success "  Installed OpenCode command wrappers to .opencode/commands/"
    fi

    # 2. Assemble and insert instructions (Layer 1 + Layer 2, with markers)
    local content
    content="$(assemble_aitasks_instructions "$project_dir" "opencode")" || true
    if [[ -n "$content" ]]; then
        mkdir -p "$dest_opencode"
        local dest_instructions="$dest_opencode/instructions.md"
        insert_aitasks_instructions "$dest_instructions" "$content"
        info "  Installed .opencode/instructions.md (with aitasks markers)"
    fi

    # 3. Merge opencode.json permission seed
    local seed_config="$project_dir/aitasks/metadata/opencode_config.seed.json"
    if [[ -f "$seed_config" ]]; then
        local dest_config="$project_dir/opencode.json"
        if [[ ! -f "$dest_config" ]]; then
            cp "$seed_config" "$dest_config"
            info "  Created opencode.json from seed"
        else
            info "  Existing opencode.json found — merging aitask settings..."
            merge_opencode_settings "$seed_config" "$dest_config"
        fi
    fi
}

# --- Set up all code agent integrations ---
setup_code_agents() {
    local project_dir="$SCRIPT_DIR/.."

    # Claude Code settings are always installed (core framework infrastructure)
    setup_claude_code

    # AGENTS.md is a cross-agent convention (codex reads it at repo root;
    # other agents may too). Install unconditionally so it is in place
    # whether or not specific agent CLIs are available.
    update_agentsmd "$project_dir"

    # Other agents: only set up if their CLI is installed
    if _is_agent_installed gemini; then
        echo ""
        setup_gemini_cli
    fi

    if _is_agent_installed codex; then
        echo ""
        setup_codex_cli
    fi

    if _is_agent_installed opencode; then
        echo ""
        setup_opencode
    fi
}

# --- Review guides setup ---
setup_review_guides() {
    local project_dir="$SCRIPT_DIR/.."
    local seed_dir="$project_dir/seed/reviewguides"
    local dest_dir="$project_dir/aireviewguides"

    # If no seed directory, check if review guides already installed
    if [[ ! -d "$seed_dir" ]]; then
        if [[ -d "$dest_dir" ]]; then
            local count
            count=$(find "$dest_dir" -name "*.md" -type f 2>/dev/null | wc -l)
            if [[ $count -gt 0 ]]; then
                success "Review guides already installed ($count guides in aireviewguides/)"
            else
                warn "No seed/reviewguides/ directory found — skipping review guide setup"
                info "Review guides can be added manually to aireviewguides/"
            fi
        else
            warn "No seed/reviewguides/ directory found — skipping review guide setup"
            info "Review guides can be added manually to aireviewguides/"
        fi
        return
    fi

    # Count available seed modes (recursive scan for tree structure)
    local seed_files=()
    while IFS= read -r -d '' f; do
        seed_files+=("$f")
    done < <(find "$seed_dir" -name "*.md" -type f -print0 2>/dev/null)

    if [[ ${#seed_files[@]} -eq 0 ]]; then
        warn "No review guide files found in seed/reviewguides/"
        return
    fi

    info "Found ${#seed_files[@]} review guide templates available for installation."

    if [[ -t 0 ]]; then
        printf "  Install review guides? [Y/n] "
        read -r answer
        case "${answer:-Y}" in
            [Yy]*|"") ;;
            *)
                info "Skipped review guide installation."
                return 0
                ;;
        esac
    else
        info "(non-interactive: auto-accepting default)"
    fi

    # Build display list: extract name and description from YAML frontmatter
    local display_lines=()
    local file_map=()  # parallel array: display_line -> filepath

    # Add "Install all" option first
    display_lines+=(">>> Install all ${#seed_files[@]} review guides")
    file_map+=("ALL")

    for f in "${seed_files[@]}"; do
        local rel_path name desc
        rel_path="${f#$seed_dir/}"
        name=""
        desc=""
        local in_yaml=false
        while IFS= read -r line; do
            if [[ "$line" == "---" ]]; then
                if [[ "$in_yaml" == true ]]; then
                    break
                else
                    in_yaml=true
                    continue
                fi
            fi
            if [[ "$in_yaml" == true ]]; then
                if [[ "$line" =~ ^name:[[:space:]]*(.*) ]]; then
                    name="${BASH_REMATCH[1]}"
                elif [[ "$line" =~ ^description:[[:space:]]*(.*) ]]; then
                    desc="${BASH_REMATCH[1]}"
                fi
            fi
        done < "$f"

        # Fallback if frontmatter missing
        [[ -z "$name" ]] && name="$rel_path"
        [[ -z "$desc" ]] && desc="(no description)"

        # Check if already installed (using relative path)
        local marker=""
        if [[ -f "$dest_dir/$rel_path" ]]; then
            marker=" [installed]"
        fi

        # Show category prefix for modes in subdirectories
        local category_prefix=""
        if [[ "$rel_path" == */* ]]; then
            category_prefix="[$(dirname "$rel_path")] "
        fi

        display_lines+=("${category_prefix}${name} — $desc$marker")
        file_map+=("$f")
    done

    # Add "Skip" option at the end
    display_lines+=(">>> Skip review guide installation")
    file_map+=("SKIP")

    # Create destination directory
    mkdir -p "$dest_dir"

    local selected_indices=()

    if [[ -t 0 ]]; then
        # Interactive: use fzf multi-select
        local fzf_input=""
        for line in "${display_lines[@]}"; do
            fzf_input+="$line"$'\n'
        done
        # Remove trailing newline
        fzf_input="${fzf_input%$'\n'}"

        local selected
        selected=$(echo "$fzf_input" | fzf --multi \
            --prompt="Review guides (Tab to select, Enter to confirm): " \
            --header="Select review guides to install" \
            --height=15 --no-info) || true

        if [[ -z "$selected" ]] || echo "$selected" | grep -q "^>>> Skip review guide installation"; then
            info "No review guides selected — skipping"
            return
        fi

        # Check if "Install all" was selected
        if echo "$selected" | grep -q "^>>> Install all"; then
            # Select all files
            selected_indices=("${!seed_files[@]}")
        else
            # Map selected display lines back to file indices
            while IFS= read -r sel_line; do
                for i in "${!display_lines[@]}"; do
                    if [[ "${display_lines[$i]}" == "$sel_line" && "${file_map[$i]}" != "ALL" && "${file_map[$i]}" != "SKIP" ]]; then
                        selected_indices+=("$((i - 1))")  # -1 because file_map[0] is "ALL"
                        break
                    fi
                done
            done <<< "$selected"
        fi
    else
        # Non-interactive: install all
        info "(non-interactive: installing all review guides)"
        selected_indices=("${!seed_files[@]}")
    fi

    # Copy selected files (preserving subdirectory structure)
    local installed=0
    local skipped=0
    for idx in "${selected_indices[@]}"; do
        local src="${seed_files[$idx]}"
        local rel_path="${src#$seed_dir/}"
        local dest="$dest_dir/$rel_path"
        mkdir -p "$(dirname "$dest")"
        if [[ -f "$dest" ]]; then
            info "  Skipping existing: $rel_path"
            skipped=$((skipped + 1))
        else
            cp "$src" "$dest"
            info "  Installed: $rel_path"
            installed=$((installed + 1))
        fi
    done

    # Copy .reviewguidesignore if present in seed and not already installed
    if [[ -f "$seed_dir/.reviewguidesignore" && ! -f "$dest_dir/.reviewguidesignore" ]]; then
        cp "$seed_dir/.reviewguidesignore" "$dest_dir/.reviewguidesignore"
        info "  Installed filter file: .reviewguidesignore"
    fi

    if [[ $installed -gt 0 ]]; then
        success "Installed $installed review guide(s)"
    fi
    if [[ $skipped -gt 0 ]]; then
        info "Skipped $skipped existing guide(s) (preserved user customizations)"
    fi
    if [[ $installed -eq 0 && $skipped -eq 0 ]]; then
        info "No review guides were installed"
    fi
}

# --- Contribution check CI/CD setup ---
# Creates the 'contribution' label on the remote and installs the platform-specific
# CI/CD workflow that triggers aitask_contribution_check.sh on new contribution issues.

_create_contribution_label() {
    local platform="$1"

    case "$platform" in
        github)
            if command -v gh &>/dev/null && gh auth status &>/dev/null 2>&1; then
                if gh label list --limit 200 --json name -q '.[].name' 2>/dev/null | grep -qxF "contribution"; then
                    success "Label 'contribution' already exists on GitHub"
                else
                    if gh label create "contribution" --color "0e8a16" --description "External contribution via aitask-contribute" 2>/dev/null; then
                        success "Created 'contribution' label on GitHub"
                    else
                        warn "Could not create 'contribution' label — create it manually in GitHub Settings > Labels"
                    fi
                fi
            else
                warn "gh CLI not authenticated — create 'contribution' label manually in GitHub Settings > Labels"
            fi
            ;;
        gitlab)
            if command -v glab &>/dev/null && glab auth status &>/dev/null 2>&1; then
                if glab label create "contribution" --color "#0e8a16" --description "External contribution via aitask-contribute" 2>/dev/null; then
                    success "Created 'contribution' label on GitLab"
                else
                    # Label may already exist; glab returns error on duplicate
                    info "Label 'contribution' may already exist on GitLab (or creation failed)"
                fi
            else
                warn "glab CLI not authenticated — create 'contribution' label manually in GitLab > Labels"
            fi
            ;;
        bitbucket)
            info "Bitbucket does not support issue labels via API — no label creation needed"
            ;;
        "")
            warn "No git remote detected — cannot create 'contribution' label automatically"
            info "Create it manually after configuring your remote."
            ;;
    esac
}

_install_contribution_ci_workflow() {
    local platform="$1"
    local project_dir="$2"
    local seed_ci_dir="$3"

    local src_file=""
    local dest_file=""
    local dest_dir=""

    case "$platform" in
        github)
            src_file="$seed_ci_dir/github/contribution-check.yml"
            dest_dir="$project_dir/.github/workflows"
            dest_file="$dest_dir/contribution-check.yml"
            ;;
        gitlab)
            src_file="$seed_ci_dir/gitlab/contribution-check-job.yml"
            dest_file="$project_dir/.gitlab-ci.yml"
            ;;
        bitbucket)
            src_file="$seed_ci_dir/bitbucket/contribution-check-pipeline.yml"
            dest_file="$project_dir/bitbucket-pipelines.yml"
            ;;
        "")
            info "No git remote detected — skipping CI/CD workflow installation"
            info "Run 'ait setup' again after configuring your remote."
            return
            ;;
    esac

    if [[ ! -f "$src_file" ]]; then
        warn "Seed CI template not found: $src_file"
        return
    fi

    # Idempotency: check if already installed
    if [[ "$platform" == "github" && -f "$dest_file" ]]; then
        success "GitHub Actions contribution check workflow already installed"
        return
    fi
    if [[ "$platform" != "github" && -f "$dest_file" ]]; then
        if grep -q "contribution-check" "$dest_file" 2>/dev/null; then
            success "Contribution check job already present in $(basename "$dest_file")"
            return
        fi
    fi

    if [[ -t 0 ]]; then
        printf "  Install contribution check CI/CD workflow? [Y/n] "
        read -r answer
        case "${answer:-Y}" in
            [Yy]*|"") ;;
            *)
                info "Skipped contribution check workflow installation."
                return
                ;;
        esac
    else
        info "(non-interactive: auto-accepting contribution check workflow)"
    fi

    case "$platform" in
        github)
            mkdir -p "$dest_dir"
            cp "$src_file" "$dest_file"
            success "Installed contribution check workflow: .github/workflows/contribution-check.yml"
            ;;
        gitlab)
            if [[ -f "$dest_file" ]]; then
                echo "" >> "$dest_file"
                echo "# --- Contribution overlap check (installed by ait setup) ---" >> "$dest_file"
                cat "$src_file" >> "$dest_file"
                success "Appended contribution check job to .gitlab-ci.yml"
            else
                {
                    echo "# .gitlab-ci.yml — auto-generated by ait setup"
                    echo ""
                    cat "$src_file"
                } > "$dest_file"
                success "Created .gitlab-ci.yml with contribution check job"
            fi
            ;;
        bitbucket)
            if [[ -f "$dest_file" ]]; then
                echo "" >> "$dest_file"
                echo "# --- Contribution overlap check (installed by ait setup) ---" >> "$dest_file"
                cat "$src_file" >> "$dest_file"
                success "Appended contribution check pipeline to bitbucket-pipelines.yml"
            else
                {
                    echo "# bitbucket-pipelines.yml — auto-generated by ait setup"
                    echo ""
                    cat "$src_file"
                } > "$dest_file"
                success "Created bitbucket-pipelines.yml with contribution check pipeline"
            fi
            ;;
    esac
}

setup_contribution_check() {
    local project_dir="$SCRIPT_DIR/.."
    local seed_ci_dir="$project_dir/seed/ci"
    local platform
    platform=$(_detect_git_platform)

    # Skip if no seed CI templates available
    if [[ ! -d "$seed_ci_dir" ]]; then
        return
    fi

    info "Contribution overlap check CI/CD integration"

    _create_contribution_label "$platform"
    _install_contribution_ci_workflow "$platform" "$project_dir" "$seed_ci_dir"
}

# --- Commit all framework files to git ---
# Runs at the END of setup, after all steps have created their files.
# This ensures review modes, .gitignore, and other late-stage files are included.
commit_framework_files() {
    local project_dir="$SCRIPT_DIR/.."

    # Bail if not in a git repo
    if ! git -C "$project_dir" rev-parse --is-inside-work-tree &>/dev/null; then
        return
    fi

    # Build the list of framework paths to check (only those that exist)
    # NOTE: This list is duplicated in install.sh commit_installed_files().
    # If you change one, change the other. install.sh runs stand-alone via
    # curl|bash before extraction, so it cannot source a shared helper.
    local paths_to_add=()
    local check_paths=(
        ".aitask-scripts/"
        "aitasks/metadata/"
        "aireviewguides/"
        "ait"
        ".claude/skills/"
        ".agents/"
        ".codex/"
        ".gemini/"
        ".opencode/"
        ".gitignore"
        ".github/workflows/"
        "CLAUDE.md"
        "GEMINI.md"
        "AGENTS.md"
        "opencode.json"
    )

    for p in "${check_paths[@]}"; do
        if [[ -e "$project_dir/$p" ]]; then
            paths_to_add+=("$p")
        fi
    done

    # Also check for install.sh (may not exist in tarball installs)
    if [[ -f "$project_dir/install.sh" ]]; then
        paths_to_add+=("install.sh")
    fi

    # Check for CI config files that may have been installed by setup_contribution_check
    for ci_file in ".gitlab-ci.yml" "bitbucket-pipelines.yml"; do
        if [[ -f "$project_dir/$ci_file" ]]; then
            paths_to_add+=("$ci_file")
        fi
    done

    if [[ ${#paths_to_add[@]} -eq 0 ]]; then
        return
    fi

    # Check for untracked or modified framework files.
    # Exclude interpreter cache artifacts even if local ignore rules are incomplete.
    # In branch mode (`aitasks/`, `aiplans/` are symlinks into a `.aitask-data`
    # worktree), additionally exclude those paths — they are committed by
    # commit_framework_data_files(). In legacy mode, leave them in.
    local untracked modified all_changes
    local cache_artifacts_re='(^|/)__pycache__/|\.py[co]$|\.pyd$'
    local data_branch_re=''
    if [[ -d "$project_dir/.aitask-data/.git" || -f "$project_dir/.aitask-data/.git" ]]; then
        data_branch_re='^(aitasks|aiplans)/'
    fi
    _filter_changes() {
        if [[ -n "$data_branch_re" ]]; then
            grep -Ev "$cache_artifacts_re" | grep -Ev "$data_branch_re"
        else
            grep -Ev "$cache_artifacts_re"
        fi
    }
    untracked="$(cd "$project_dir" && git ls-files --others --exclude-standard \
        "${paths_to_add[@]}" 2>/dev/null | _filter_changes)" || true
    modified="$(cd "$project_dir" && git ls-files --modified \
        "${paths_to_add[@]}" 2>/dev/null | _filter_changes)" || true
    all_changes="$(printf "%s\n%s\n" "$untracked" "$modified" | sed '/^$/d')"

    local changed_files=()
    while IFS= read -r changed_file; do
        [[ -n "$changed_file" ]] || continue
        changed_files+=("$changed_file")
    done <<< "$all_changes"

    if [[ ${#changed_files[@]} -eq 0 ]]; then
        success "All framework files already committed to git"
        return
    fi

    local total_count
    total_count="${#changed_files[@]}"
    echo ""
    info "────────────────────────────────────────────────────"
    info "READY TO COMMIT $total_count FRAMEWORK FILES"
    info "────────────────────────────────────────────────────"
    # Iterate via bash array indexing — avoids `printf | head` SIGPIPE which,
    # under `set -o pipefail` + `set -e`, kills the script mid-list when the
    # array is longer than the head limit.
    local _i
    for ((_i=0; _i<total_count && _i<20; _i++)); do
        printf '  %s\n' "${changed_files[_i]}"
    done
    if [[ $total_count -gt 20 ]]; then
        info "  ... and $((total_count - 20)) more files"
    fi

    if [[ -t 0 ]]; then
        printf "  Commit framework files to git? [Y/n] "
        read -r answer
    else
        info "(non-interactive: auto-accepting default)"
        answer="Y"
    fi
    case "${answer:-Y}" in
        [Yy]*|"")
            local add_output commit_output
            if ! add_output=$(cd "$project_dir" && git add -- "${changed_files[@]}" 2>&1); then
                warn "git add failed:"
                printf '%s\n' "$add_output" | awk '{print "    " $0}'
                warn "Framework files NOT committed. Run 'git add -A && git commit' manually."
                return
            fi
            if ! (cd "$project_dir" && git diff --cached --quiet 2>/dev/null); then
                if ! commit_output=$(cd "$project_dir" && git commit -m "ait: Add aitask framework" 2>&1); then
                    warn "git commit failed:"
                    printf '%s\n' "$commit_output" | awk '{print "    " $0}'
                    warn "Framework files staged but NOT committed. Run 'git commit' manually."
                    return
                fi
            fi

            # Post-commit verification: anything still untracked under the
            # framework paths indicates a gitignore rule, pathspec quirk, or
            # a new file produced between the list and the commit. Apply the
            # same data-branch filter — those files are committed separately
            # by commit_framework_data_files() in branch mode.
            local still_untracked
            still_untracked="$(cd "$project_dir" && git ls-files --others --exclude-standard \
                "${paths_to_add[@]}" 2>/dev/null | _filter_changes)" || true
            if [[ -n "$still_untracked" ]]; then
                warn "Some framework files remain untracked after commit:"
                # awk reads all stdin — no SIGPIPE even if list is huge.
                printf '%s\n' "$still_untracked" | awk 'NR<=20 {print "    " $0}'
                warn "Run 'git status' to investigate, then 'git add -A && git commit' to finalize."
            else
                success "Framework files committed to git"
            fi
            ;;
        *)
            warn "Skipped committing framework files. These files remain UNTRACKED:"
            for ((_i=0; _i<total_count && _i<10; _i++)); do
                printf '    %s\n' "${changed_files[_i]}"
            done
            if [[ $total_count -gt 10 ]]; then
                info "    ... and $((total_count - 10)) more"
            fi
            info "You can manually commit later with 'git add' and 'git commit'."
            ;;
    esac
}

# --- Commit data-branch framework files (branch-mode only) ---
# Setup-time analogue of install.sh's commit_installed_data_files().
# In branch mode, framework metadata living on the aitask-data branch
# (aitasks/metadata/, optionally aireviewguides/) gets written through
# symlinks during setup but never reaches the data worktree's index unless
# we commit it here. Keeps `ait setup` and `ait upgrade` symmetric.
commit_framework_data_files() {
    local project_dir="$SCRIPT_DIR/.."
    local data_dir="$project_dir/.aitask-data"

    # Legacy mode (no separate data worktree) — nothing to do.
    if [[ ! -d "$data_dir/.git" && ! -f "$data_dir/.git" ]]; then
        return
    fi

    if ! git -C "$data_dir" rev-parse --is-inside-work-tree &>/dev/null; then
        return
    fi

    # Framework-owned config dirs that may live on the data branch. Never
    # commit task or plan content here — those are user data.
    local data_check_paths=("aitasks/metadata/" "aireviewguides/")
    local data_paths=()
    for p in "${data_check_paths[@]}"; do
        [[ -e "$data_dir/$p" ]] && data_paths+=("$p")
    done

    if [[ ${#data_paths[@]} -eq 0 ]]; then
        return
    fi

    local cache_artifacts_re='(^|/)__pycache__/|\.py[co]$|\.pyd$'
    local untracked modified all_changes
    untracked="$(git -C "$data_dir" ls-files --others --exclude-standard \
        "${data_paths[@]}" 2>/dev/null | grep -Ev "$cache_artifacts_re")" || true
    modified="$(git -C "$data_dir" ls-files --modified \
        "${data_paths[@]}" 2>/dev/null | grep -Ev "$cache_artifacts_re")" || true
    all_changes="$(printf '%s\n%s\n' "$untracked" "$modified" | sed '/^$/d')"

    if [[ -z "$all_changes" ]]; then
        success "Framework data files already committed to aitask-data branch"
        return
    fi

    local changed_files=()
    while IFS= read -r changed_file; do
        [[ -n "$changed_file" ]] || continue
        changed_files+=("$changed_file")
    done <<< "$all_changes"

    local total_count=${#changed_files[@]}
    echo ""
    info "────────────────────────────────────────────────────"
    info "READY TO COMMIT $total_count FRAMEWORK DATA FILES (aitask-data branch)"
    info "────────────────────────────────────────────────────"
    local _i
    for ((_i=0; _i<total_count && _i<20; _i++)); do
        printf '  %s\n' "${changed_files[_i]}"
    done
    if [[ $total_count -gt 20 ]]; then
        info "  ... and $((total_count - 20)) more files"
    fi

    if [[ -t 0 ]]; then
        printf "  Commit framework data files to aitask-data branch? [Y/n] "
        read -r answer
    else
        info "(non-interactive: auto-accepting default)"
        answer="Y"
    fi
    case "${answer:-Y}" in
        [Yy]*|"")
            local add_output commit_output
            if ! add_output=$(git -C "$data_dir" add -- "${changed_files[@]}" 2>&1); then
                warn "git add failed (data branch):"
                printf '%s\n' "$add_output" | awk '{print "    " $0}'
                warn "Framework data files NOT committed."
                return
            fi
            if ! git -C "$data_dir" diff --cached --quiet 2>/dev/null; then
                if ! commit_output=$(git -C "$data_dir" \
                    commit -m "ait: Add aitask framework data" 2>&1); then
                    warn "git commit failed (data branch):"
                    printf '%s\n' "$commit_output" | awk '{print "    " $0}'
                    warn "Framework data files staged but NOT committed."
                    return
                fi
            fi
            success "Framework data files committed to aitask-data branch"
            ;;
        *)
            warn "Skipped committing framework data files. These remain UNTRACKED on aitask-data:"
            for ((_i=0; _i<total_count && _i<10; _i++)); do
                printf '    %s\n' "${changed_files[_i]}"
            done
            if [[ $total_count -gt 10 ]]; then
                info "    ... and $((total_count - 10)) more"
            fi
            info "You can manually commit later with './ait git add' and './ait git commit'."
            ;;
    esac
}

# --- Git TUI detection and configuration ---
# Uses `cat > file` instead of `mv tmpf file` so we write THROUGH symlinks
# to the actual file content, rather than replacing the path's inode (which
# can break symlinks or behave inconsistently across filesystems/mv variants).
_set_git_tui_config() {
    local config_file="$1" value="$2"
    local tmpf
    tmpf=$(mktemp)

    if grep -qE '^[[:space:]]*git_tui:' "$config_file"; then
        # Update existing git_tui line
        sed "s/^\([[:space:]]*\)git_tui:.*/\1git_tui: $value/" "$config_file" > "$tmpf" \
            && cat "$tmpf" > "$config_file" && rm "$tmpf"
    else
        # Append tmux section with git_tui
        {
            cat "$config_file"
            printf '\ntmux:\n  git_tui: %s\n' "$value"
        } > "$tmpf" && cat "$tmpf" > "$config_file" && rm "$tmpf"
    fi
}

_install_lazygit_from_github() {
    local version arch
    version=$(curl -s "https://api.github.com/repos/jesseduffield/lazygit/releases/latest" \
        | grep '"tag_name"' | head -1 | sed -E 's/.*"v([^"]+)".*/\1/')
    if [[ -z "$version" ]]; then
        warn "Could not determine latest lazygit version."
        return 1
    fi
    case "$(uname -m)" in
        x86_64)  arch="x86_64" ;;
        aarch64) arch="arm64" ;;
        armv*)   arch="armv6" ;;
        *)       warn "Unsupported architecture: $(uname -m)"; return 1 ;;
    esac
    local tmpdir
    tmpdir=$(mktemp -d)
    curl -Lo "$tmpdir/lazygit.tar.gz" \
        "https://github.com/jesseduffield/lazygit/releases/latest/download/lazygit_${version}_Linux_${arch}.tar.gz"
    tar xf "$tmpdir/lazygit.tar.gz" -C "$tmpdir" lazygit
    sudo install "$tmpdir/lazygit" /usr/local/bin/lazygit
    rm -rf "$tmpdir"
}

_install_lazygit() {
    info "Installing lazygit..."
    case "$OS" in
        arch)
            sudo pacman -S --needed --noconfirm lazygit ;;
        debian)
            _install_lazygit_from_github ;;
        fedora)
            sudo dnf install -y lazygit ;;
        macos)
            brew install lazygit ;;
        *)
            warn "Unsupported OS ($OS) for automatic lazygit installation."
            info "Install manually: https://github.com/jesseduffield/lazygit#installation"
            return 1 ;;
    esac
}

setup_git_tui() {
    local project_dir="$SCRIPT_DIR/.."
    local config_file="$project_dir/aitasks/metadata/project_config.yaml"

    if [[ ! -f "$config_file" ]]; then
        info "No project_config.yaml found — skipping git TUI setup."
        return
    fi

    # Check if already configured (non-empty value)
    local current
    current=$(grep -E '^[[:space:]]*git_tui:' "$config_file" 2>/dev/null | sed 's/.*git_tui:[[:space:]]*//' || true)
    if [[ -n "$current" ]]; then
        success "Git TUI already configured: $current"
        return
    fi

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
        if [[ -t 0 ]]; then
            printf "  Install lazygit? [Y/n] "
            read -r answer
        else
            info "(non-interactive: skipping git TUI installation)"
            return
        fi
        if [[ "${answer,,}" != "n" ]]; then
            _install_lazygit
            if command -v lazygit &>/dev/null; then
                selected="lazygit"
            else
                warn "lazygit installation may have failed. Skipping git TUI config."
                return
            fi
        else
            info "Skipping git TUI configuration."
            return
        fi
    elif [[ ${#detected[@]} -eq 1 ]]; then
        selected="${detected[0]}"
        info "Detected git TUI: $selected"
    else
        info "Multiple git TUIs detected: ${detected[*]}"
        if [[ -t 0 ]]; then
            local i=1
            for tool in "${detected[@]}"; do
                printf "  %d) %s\n" "$i" "$tool"
                ((i++))
            done
            printf "  Select git TUI [1]: "
            read -r choice_num
            choice_num="${choice_num:-1}"
            if [[ "$choice_num" =~ ^[0-9]+$ ]] && (( choice_num >= 1 && choice_num <= ${#detected[@]} )); then
                selected="${detected[$((choice_num - 1))]}"
            else
                selected="${detected[0]}"
            fi
        else
            # Non-interactive: prefer first detected (lazygit > gitui > tig)
            selected="${detected[0]}"
            info "(non-interactive: auto-selecting $selected)"
        fi
    fi

    if [[ -n "$selected" ]]; then
        _set_git_tui_config "$config_file" "$selected"
        # Verify the write actually took effect — guards against silent
        # symlink/mv/sed failures reported on some setups.
        local after_write
        after_write=$(grep -E '^[[:space:]]*git_tui:' "$config_file" 2>/dev/null | sed 's/.*git_tui:[[:space:]]*//' || true)
        if [[ "$after_write" != "$selected" ]]; then
            warn "Git TUI config write failed — expected '$selected' but got '$after_write'"
            warn "Config file: $(readlink -f "$config_file" 2>/dev/null || echo "$config_file")"
        else
            success "Git TUI configured: $selected"
        fi
    fi
}

# --- Tmux default_session detection and configuration ---
_set_tmux_default_session_config() {
    local config_file="$1" value="$2"
    local tmpf
    tmpf=$(mktemp)

    if grep -qE '^[[:space:]]*default_session:' "$config_file"; then
        # Update existing default_session line
        sed "s/^\([[:space:]]*\)default_session:.*/\1default_session: $value/" "$config_file" > "$tmpf" \
            && cat "$tmpf" > "$config_file" && rm "$tmpf"
    elif grep -qE '^tmux:[[:space:]]*$' "$config_file"; then
        # tmux: section exists, append default_session inside it
        awk -v val="$value" '
            /^tmux:[[:space:]]*$/ { print; print "  default_session: " val; next }
            { print }
        ' "$config_file" > "$tmpf" && cat "$tmpf" > "$config_file" && rm "$tmpf"
    else
        # No tmux: section — append whole block
        { cat "$config_file"; printf '\ntmux:\n  default_session: %s\n' "$value"; } > "$tmpf" \
            && cat "$tmpf" > "$config_file" && rm "$tmpf"
    fi
}

setup_tmux_default_session() {
    local project_dir="$SCRIPT_DIR/.."
    local config_file="$project_dir/aitasks/metadata/project_config.yaml"

    if [[ ! -f "$config_file" ]]; then
        info "No project_config.yaml found — skipping tmux default_session setup."
        return
    fi

    # Skip if already set (non-empty value)
    local current
    current=$(grep -E '^[[:space:]]*default_session:' "$config_file" 2>/dev/null | sed 's/.*default_session:[[:space:]]*//' || true)
    if [[ -n "$current" ]]; then
        success "tmux default_session already configured: $current"
        return
    fi

    info "Configuring default tmux session name..."

    local default_name="aitasks"
    local session_name
    if [[ -t 0 ]]; then
        printf "  tmux session name [%s]: " "$default_name"
        read -r session_name
        session_name="${session_name:-$default_name}"
    else
        session_name="$default_name"
        info "(non-interactive: using default '$session_name')"
    fi

    # tmux session names cannot contain . or :
    if [[ "$session_name" == *"."* || "$session_name" == *":"* ]]; then
        warn "Session name contains invalid chars (. or :); falling back to '$default_name'"
        session_name="$default_name"
    fi

    _set_tmux_default_session_config "$config_file" "$session_name"

    # Verify the write took effect
    local after_write
    after_write=$(grep -E '^[[:space:]]*default_session:' "$config_file" 2>/dev/null | sed 's/.*default_session:[[:space:]]*//' || true)
    if [[ "$after_write" != "$session_name" ]]; then
        warn "tmux default_session write failed — expected '$session_name' but got '$after_write'"
    else
        success "tmux default_session configured: $session_name"
    fi
}

# --- Optional starter ~/.tmux.conf (opt-in, never overwrites) ---
setup_starter_tmux_conf() {
    local template="$SCRIPT_DIR/templates/tmux.conf"

    if [[ ! -f "$template" ]]; then
        return
    fi

    if [[ -f "$HOME/.tmux.conf" ]]; then
        info "tmux config already present at ~/.tmux.conf — leaving untouched."
        return
    fi
    if [[ -f "$HOME/.config/tmux/tmux.conf" ]]; then
        info "tmux config already present at ~/.config/tmux/tmux.conf — leaving untouched."
        return
    fi

    local target=""
    if [[ -d "$HOME/.config/tmux" ]]; then
        target="$HOME/.config/tmux/tmux.conf"
    else
        target="$HOME/.tmux.conf"
    fi

    if [[ ! -t 0 ]]; then
        return
    fi

    info "No tmux config detected at $target."
    printf "  Install aitasks-recommended starter tmux.conf? Enables: mouse on, right-click menu, top status bar, sensible defaults. [y/N] "
    local answer=""
    read -r answer
    case "${answer:-N}" in
        [Yy]*) ;;
        *) info "Skipped starter tmux.conf."; return ;;
    esac

    mkdir -p "$(dirname "$target")"
    cp "$template" "$target"
    success "Installed starter tmux.conf at $target"
}

# --- Per-user config (userconfig.yaml) ---
setup_userconfig() {
    local project_dir
    project_dir="$(pwd)"

    # Determine where aitasks/metadata lives
    local metadata_dir
    if [[ -d "$project_dir/.aitask-data/aitasks/metadata" ]]; then
        metadata_dir="$project_dir/.aitask-data/aitasks/metadata"
    elif [[ -d "$project_dir/aitasks/metadata" ]]; then
        metadata_dir="$project_dir/aitasks/metadata"
    else
        warn "No aitasks/metadata directory found — skipping userconfig setup"
        return
    fi

    local config_file="$metadata_dir/userconfig.yaml"

    if [[ -f "$config_file" ]]; then
        local existing_email
        existing_email=$(grep '^email:' "$config_file" 2>/dev/null | sed 's/^email: *//')
        success "Per-user config already exists (email: ${existing_email:-<not set>})"
        return
    fi

    info "Setting up per-user config (userconfig.yaml)..."
    info "This file is gitignored and stores your local identity."

    # Try to get a default from git config
    local default_email
    default_email=$(git config user.email 2>/dev/null || echo "")

    local email=""
    if [[ -t 0 ]]; then
        if [[ -n "$default_email" ]]; then
            printf "  Your email [%s]: " "$default_email"
        else
            printf "  Your email: "
        fi
        read -r email
        email="${email:-$default_email}"
    else
        # Non-interactive: use git config email if available
        email="$default_email"
        if [[ -n "$email" ]]; then
            info "(non-interactive: using git config email: $email)"
        else
            info "(non-interactive: no email available, skipping userconfig)"
            return
        fi
    fi

    if [[ -z "$email" ]]; then
        info "No email provided — skipping userconfig creation."
        info "You can create it manually later: aitasks/metadata/userconfig.yaml"
        return
    fi

    {
        echo "# Local user configuration (gitignored, not shared)"
        echo "email: $email"
    } > "$config_file"

    success "Created userconfig.yaml (email: $email)"
}

# --- Main ---
main() {
    echo ""
    info "aitask framework setup"
    echo ""

    detect_os
    info "Detected OS: $OS"
    echo ""

    install_cli_tools "$OS"
    echo ""

    check_bash_version
    echo ""

    ensure_git_repo
    echo ""

    setup_data_branch
    echo ""

    setup_draft_directory
    echo ""

    setup_python_cache_gitignore
    echo ""

    setup_id_counter
    echo ""

    setup_lock_branch
    echo ""

    ensure_project_config_defaults
    echo ""

    setup_git_tui
    echo ""

    setup_tmux_default_session
    echo ""

    setup_starter_tmux_conf
    echo ""

    setup_userconfig
    echo ""

    setup_python_venv
    echo ""

    install_global_shim
    echo ""

    setup_code_agents
    echo ""

    setup_review_guides
    echo ""

    setup_contribution_check
    echo ""

    commit_framework_files
    echo ""

    commit_framework_data_files
    echo ""

    check_latest_version

    echo ""
    success "Setup complete!"
    echo ""
    info "Summary:"
    info "  Bash: $BASH_VERSION ($(command -v bash))"
    info "  Python venv: $VENV_DIR"
    if [[ -x "$VENV_DIR/bin/python" ]]; then
        info "  Python: $("$VENV_DIR/bin/python" -c 'import sys; print("{}.{}.{}".format(*sys.version_info[:3]))' 2>/dev/null || echo unknown)"
    fi
    info "  Global shim: $SHIM_DIR/ait"
    if [[ -f "$VERSION_FILE" ]]; then
        info "  Version: $(cat "$VERSION_FILE")"
    fi
    echo ""
}

# Allow sourcing for testing without running main
[[ "${1:-}" == "--source-only" ]] && return 0 2>/dev/null || true

main "$@"
