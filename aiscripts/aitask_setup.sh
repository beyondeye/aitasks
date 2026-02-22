#!/usr/bin/env bash
set -euo pipefail

# aitask_setup.sh - Cross-platform dependency installer for aitask framework
# Invoked via: ait setup

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$HOME/.aitask/venv"
SHIM_DIR="$HOME/.local/bin"
VERSION_FILE="$SCRIPT_DIR/VERSION"
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

# --- Git platform detection (inline — task_utils.sh not available during setup) ---
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

# --- CLI tools installation ---
install_cli_tools() {
    local os="$1"

    # Detect git platform to install the right CLI tool
    local platform
    platform=$(_detect_git_platform)

    # Build tools list: always fzf, jq, git; platform-specific CLI
    local tools=(fzf jq git)
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
    if [[ -x "$dir/ait" && -d "$dir/aiscripts" ]]; then
        exec "$dir/ait" "$@"
    fi
    dir="$(dirname "$dir")"
done

# No project found — special-case "ait setup" to bootstrap
if [[ "${1:-}" == "setup" ]]; then
    echo ""
    echo "[ait] No aitasks project found in $PWD or any parent directory."
    echo "[ait] This will install the aitasks framework into: $PWD"
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
        (cd "$project_dir" && git add .gitignore && git commit -m "ait: Add aitasks/new/ to .gitignore (draft tasks)" 2>/dev/null) || true
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

        if [[ -z "$selected" ]]; then
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
                    if [[ "${display_lines[$i]}" == "$sel_line" && "${file_map[$i]}" != "ALL" ]]; then
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
    local paths_to_add=()
    local check_paths=(
        "aiscripts/"
        "aitasks/metadata/"
        "aireviewguides/"
        "ait"
        ".claude/skills/"
        ".gitignore"
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

    if [[ ${#paths_to_add[@]} -eq 0 ]]; then
        return
    fi

    # Check for untracked or modified framework files
    local untracked modified all_changes
    untracked="$(cd "$project_dir" && git ls-files --others --exclude-standard \
        "${paths_to_add[@]}" 2>/dev/null)" || true
    modified="$(cd "$project_dir" && git ls-files --modified \
        "${paths_to_add[@]}" 2>/dev/null)" || true
    all_changes="${untracked}${modified}"

    if [[ -z "$all_changes" ]]; then
        success "All framework files already committed to git"
        return
    fi

    info "Framework files not yet committed to git:"
    echo "$all_changes" | head -20 | sed 's/^/  /'
    local total_count
    total_count=$(echo "$all_changes" | wc -l)
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
            (
                cd "$project_dir"
                git add "${paths_to_add[@]}" 2>/dev/null || true
                # Only commit if there are staged changes
                if ! git diff --cached --quiet 2>/dev/null; then
                    git commit -m "ait: Add aitask framework"
                fi
            )
            success "Framework files committed to git"
            ;;
        *)
            info "Skipped committing framework files."
            info "You can manually commit later with 'git add' and 'git commit'."
            ;;
    esac
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

    ensure_git_repo
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

    setup_review_guides
    echo ""

    commit_framework_files
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
