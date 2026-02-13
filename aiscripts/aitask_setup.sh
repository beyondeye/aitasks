#!/usr/bin/env bash
set -euo pipefail

# aitask_setup.sh - Cross-platform dependency installer for aitask framework
# Invoked via: ait setup

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$HOME/.aitask/venv"
SHIM_DIR="$HOME/.local/bin"
VERSION_FILE="$SCRIPT_DIR/../VERSION"
REPO="beyondeye/aitasks"

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

# --- CLI tools installation ---
install_cli_tools() {
    local os="$1"
    local tools=(fzf gh jq git)
    local missing=()

    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &>/dev/null; then
            missing+=("$tool")
        fi
    done

    if [[ ${#missing[@]} -eq 0 ]]; then
        success "All CLI tools already installed (fzf, gh, jq, git)"
        return
    fi

    info "Installing missing CLI tools: ${missing[*]}"

    case "$os" in
        arch)
            # Map tool names to Arch package names
            local pkgs=()
            for tool in "${missing[@]}"; do
                case "$tool" in
                    gh) pkgs+=("github-cli") ;;
                    *)  pkgs+=("$tool") ;;
                esac
            done
            sudo pacman -S --needed --noconfirm "${pkgs[@]}"
            ;;

        debian|wsl)
            # gh needs special repo setup on Debian/Ubuntu
            local apt_pkgs=()
            local need_gh=false
            for tool in "${missing[@]}"; do
                case "$tool" in
                    gh) need_gh=true ;;
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

            # Also ensure python3 and python3-venv are installed
            apt_pkgs+=("python3" "python3-venv")

            sudo apt-get install -y -qq "${apt_pkgs[@]}"
            ;;

        fedora)
            local dnf_pkgs=()
            for tool in "${missing[@]}"; do
                dnf_pkgs+=("$tool")
            done
            sudo dnf install -y -q "${dnf_pkgs[@]}"
            ;;

        macos)
            if ! command -v brew &>/dev/null; then
                die "Homebrew is required on macOS. Install from https://brew.sh"
            fi

            local brew_pkgs=()
            for tool in "${missing[@]}"; do
                brew_pkgs+=("$tool")
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

# --- Python venv setup ---
setup_python_venv() {
    local python_cmd=""
    if command -v python3 &>/dev/null; then
        python_cmd="python3"
    elif command -v python &>/dev/null; then
        python_cmd="python"
    else
        die "Python 3 not found. Install python3 and try again."
    fi

    if [[ ! -d "$VENV_DIR" ]]; then
        info "Creating Python virtual environment at $VENV_DIR..."
        mkdir -p "$(dirname "$VENV_DIR")"
        "$python_cmd" -m venv "$VENV_DIR"
    else
        info "Python virtual environment already exists at $VENV_DIR"
    fi

    info "Installing/upgrading Python dependencies..."
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip
    "$VENV_DIR/bin/pip" install --quiet textual pyyaml linkify-it-py

    success "Python venv ready at $VENV_DIR"
}

# --- Global shim installation ---
install_global_shim() {
    # Non-blocking: if anything fails, warn and continue
    {
        mkdir -p "$SHIM_DIR"

        cat > "$SHIM_DIR/ait" << 'SHIM'
#!/usr/bin/env bash
# Global shim for ait - finds nearest project-local ait dispatcher
if [[ "${_AIT_SHIM_ACTIVE:-}" == "1" ]]; then
    echo "Error: ait dispatcher not found in any parent directory." >&2
    exit 1
fi
export _AIT_SHIM_ACTIVE=1
dir="$PWD"
while [[ "$dir" != "/" ]]; do
    if [[ -x "$dir/ait" && -d "$dir/aiscripts" ]]; then
        exec "$dir/ait" "$@"
    fi
    dir="$(dirname "$dir")"
done
echo "Error: No ait project found in any parent directory of $PWD" >&2
echo "  Install aitasks in a project: curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash" >&2
exit 1
SHIM

        chmod +x "$SHIM_DIR/ait"

        # Check if SHIM_DIR is in PATH
        if [[ ":$PATH:" != *":$SHIM_DIR:"* ]]; then
            warn "$SHIM_DIR is not in your PATH."
            warn "Add this to your shell profile (~/.bashrc or ~/.zshrc):"
            warn "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        else
            success "Global shim installed at $SHIM_DIR/ait"
        fi
    } || {
        warn "Could not install global shim at $SHIM_DIR/ait (non-fatal)"
    }
}

# --- Git repository setup ---
setup_git_repo() {
    local project_dir="$SCRIPT_DIR/.."

    # Check if we're inside a git repo
    if git -C "$project_dir" rev-parse --is-inside-work-tree &>/dev/null; then
        success "Git repository already initialized"
        return
    fi

    # Not a git repo — offer to initialize
    warn "No git repository found in $project_dir"
    info "The aitask framework is designed to be part of your project's git repository."
    if [[ -t 0 ]]; then
        printf "  Initialize a git repository here? [Y/n] "
        read -r answer
    else
        info "(non-interactive: auto-accepting default)"
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
            return
            ;;
    esac

    # Offer to make an initial commit of the framework files
    info "Would you like to commit the aitask framework files to git?"
    info "This will add:"
    info "  aiscripts/     - aitask scripts and tools"
    info "  aitasks/metadata/ - task metadata and configuration"
    info "  ait            - CLI dispatcher"
    info "  .claude/skills/ - Claude Code skills"
    if [[ -t 0 ]]; then
        printf "  Commit these files? [Y/n] "
        read -r answer
    else
        info "(non-interactive: auto-accepting default)"
        answer="Y"
    fi
    case "${answer:-Y}" in
        [Yy]*|"")
            ;;
        *)
            warn "Skipped initial commit."
            info "The aitask framework is designed to be part of your project repository."
            info "You can manually commit these files later with 'git add' and 'git commit'."
            printf "  Are you sure you want to skip? [y/N] "
            read -r answer2
            case "${answer2:-N}" in
                [Yy]*)
                    info "OK, skipping initial commit."
                    return
                    ;;
                *)
                    info "OK, proceeding with commit."
                    ;;
            esac
            ;;
    esac

    (
        cd "$project_dir"
        git add aiscripts/ aitasks/metadata/ ait .claude/skills/ VERSION install.sh 2>/dev/null || true
        git commit -m "Add aitask framework"
    )
    success "Initial commit created with aitask framework files"
}

# --- Task ID counter setup ---
setup_id_counter() {
    local project_dir="$SCRIPT_DIR/.."

    # Only setup if we have a git repo with a remote
    if ! git -C "$project_dir" rev-parse --is-inside-work-tree &>/dev/null; then
        return
    fi
    if ! git -C "$project_dir" remote get-url origin &>/dev/null; then
        info "No git remote configured — skipping task ID counter setup"
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
        info "No git remote configured — skipping task lock branch setup"
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
        (cd "$project_dir" && git add .gitignore && git commit -m "Add aitasks/new/ to .gitignore (draft tasks)" 2>/dev/null) || true
    fi

    success "Draft directory configured (aitasks/new/ in .gitignore)"
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
        info "Run: ait install latest"
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

# --- Install Claude Code permission settings ---
install_claude_settings() {
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

    setup_git_repo
    echo ""

    setup_draft_directory
    echo ""

    setup_id_counter
    echo ""

    setup_lock_branch
    echo ""

    setup_python_venv
    echo ""

    install_global_shim
    echo ""

    install_claude_settings
    echo ""

    check_latest_version

    echo ""
    success "Setup complete!"
    echo ""
    info "Summary:"
    info "  Python venv: $VENV_DIR"
    info "  Global shim: $SHIM_DIR/ait"
    if [[ -f "$VERSION_FILE" ]]; then
        info "  Version: $(cat "$VERSION_FILE")"
    fi
    echo ""
}

# Allow sourcing for testing without running main
[[ "${1:-}" == "--source-only" ]] && return 0 2>/dev/null || true

main "$@"
