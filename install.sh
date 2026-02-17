#!/usr/bin/env bash
set -euo pipefail

# install.sh - Curl-friendly bootstrap installer for the aitask framework
# Usage: curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
#   or:  bash install.sh [--force] [--dir PATH] [--local-tarball PATH]

REPO="beyondeye/aitasks"
INSTALL_DIR="."
FORCE=false
LOCAL_TARBALL=""

# --- Color helpers ---
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[ait]${NC} $1"; }
success() { echo -e "${GREEN}[ait]${NC} $1"; }
warn()    { echo -e "${YELLOW}[ait]${NC} $1"; }
die()     { echo -e "${RED}[ait] Error:${NC} $1" >&2; exit 1; }

# --- Usage ---
usage() {
    cat <<EOF
Usage: install.sh [OPTIONS]

Install the aitask framework into a project directory.

Options:
  --force             Overwrite existing framework files (preserves data dirs)
  --dir PATH          Install to PATH instead of current directory
  --local-tarball PATH  Use a local tarball instead of downloading from GitHub
  --help              Show this help message

Examples:
  curl -fsSL https://raw.githubusercontent.com/$REPO/main/install.sh | bash
  bash install.sh --dir ~/my-project
  bash install.sh --force
  bash install.sh --local-tarball ./aitasks-0.1.0.tar.gz
EOF
    exit 0
}

# --- Argument parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)
            FORCE=true
            shift
            ;;
        --dir)
            [[ $# -ge 2 ]] || die "--dir requires a path argument"
            INSTALL_DIR="$2"
            shift 2
            ;;
        --local-tarball)
            [[ $# -ge 2 ]] || die "--local-tarball requires a path argument"
            LOCAL_TARBALL="$2"
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        *)
            die "Unknown option: $1. Use --help for usage."
            ;;
    esac
done

# Resolve INSTALL_DIR to absolute path
INSTALL_DIR="$(cd "$INSTALL_DIR" 2>/dev/null && pwd)" || die "Directory does not exist: $INSTALL_DIR"

# --- Prerequisites check ---
check_prerequisites() {
    if ! command -v tar &>/dev/null; then
        die "tar is required but not found. Install it and try again."
    fi

    DOWNLOAD_CMD=""
    if command -v curl &>/dev/null; then
        DOWNLOAD_CMD="curl"
    elif command -v wget &>/dev/null; then
        DOWNLOAD_CMD="wget"
    fi

    if [[ -z "$LOCAL_TARBALL" && -z "$DOWNLOAD_CMD" ]]; then
        die "curl or wget is required for downloading. Install one and try again."
    fi
}

# --- Safety check ---
check_existing_install() {
    if [[ -f "$INSTALL_DIR/ait" || -d "$INSTALL_DIR/aiscripts" ]]; then
        if $FORCE; then
            warn "Existing installation found. --force specified, overwriting framework files..."
        else
            die "aitasks already installed in $INSTALL_DIR (found ait or aiscripts/). Use --force to overwrite."
        fi
    fi
}

# --- Interactive confirmation ---
confirm_install() {
    # When piped (curl | bash), stdin is not a terminal — skip prompt
    if [[ -t 0 ]]; then
        echo ""
        info "Will install aitasks framework to: $INSTALL_DIR"
        printf "  Install here? [Y/n] "
        read -r answer
        case "${answer:-Y}" in
            [Yy]*|"") ;;
            *) info "Aborted."; exit 0 ;;
        esac
    fi
}

# --- Download tarball ---
download_tarball() {
    local dest="$1"

    if [[ -n "$LOCAL_TARBALL" ]]; then
        [[ -f "$LOCAL_TARBALL" ]] || die "Local tarball not found: $LOCAL_TARBALL"
        cp "$LOCAL_TARBALL" "$dest"
        return
    fi

    info "Fetching latest release from GitHub..."

    local api_response=""
    if [[ "$DOWNLOAD_CMD" == "curl" ]]; then
        api_response="$(curl -sS --max-time 15 "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null)" || true
    else
        api_response="$(wget -qO- --timeout=15 "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null)" || true
    fi

    if [[ -z "$api_response" ]]; then
        die "Could not reach GitHub API. Download manually from: https://github.com/$REPO/releases"
    fi

    local tarball_url=""
    tarball_url="$(echo "$api_response" \
        | grep '"browser_download_url".*\.tar\.gz"' \
        | head -1 \
        | sed 's/.*"\(http[^"]*\)".*/\1/')" || true

    if [[ -z "$tarball_url" ]]; then
        die "Could not find release tarball. Download manually from: https://github.com/$REPO/releases"
    fi

    info "Downloading: $tarball_url"

    if [[ "$DOWNLOAD_CMD" == "curl" ]]; then
        curl -sSL --max-time 120 "$tarball_url" -o "$dest" || die "Download failed."
    else
        wget -q --timeout=120 "$tarball_url" -O "$dest" || die "Download failed."
    fi
}

# --- Install skills ---
install_skills() {
    if [[ ! -d "$INSTALL_DIR/skills" ]]; then
        warn "No skills/ directory in tarball — skipping skill installation"
        return
    fi

    mkdir -p "$INSTALL_DIR/.claude/skills"

    for skill_dir in "$INSTALL_DIR/skills"/aitask-*/; do
        [[ -d "$skill_dir" ]] || continue
        local skill_name
        skill_name="$(basename "$skill_dir")"
        mkdir -p "$INSTALL_DIR/.claude/skills/$skill_name"
        cp "$skill_dir/SKILL.md" "$INSTALL_DIR/.claude/skills/$skill_name/SKILL.md"
        info "  Installed skill: $skill_name"
    done

    # Clean up staging directory
    rm -rf "$INSTALL_DIR/skills"
}

# --- Create data directories ---
create_data_dirs() {
    mkdir -p "$INSTALL_DIR/aitasks/metadata"
    mkdir -p "$INSTALL_DIR/aitasks/metadata/profiles"
    mkdir -p "$INSTALL_DIR/aitasks/archived"
    mkdir -p "$INSTALL_DIR/aiplans/archived"
}

# --- Install seed profiles ---
install_seed_profiles() {
    if [[ ! -d "$INSTALL_DIR/seed/profiles" ]]; then
        warn "No seed/profiles/ directory in tarball — skipping profile installation"
        return
    fi

    mkdir -p "$INSTALL_DIR/aitasks/metadata/profiles"

    for profile in "$INSTALL_DIR/seed/profiles"/*.yaml; do
        [[ -f "$profile" ]] || continue
        local bname
        bname="$(basename "$profile")"
        local dest="$INSTALL_DIR/aitasks/metadata/profiles/$bname"
        if [[ -f "$dest" && "$FORCE" != true ]]; then
            info "  Profile exists (kept): $bname"
        else
            cp "$profile" "$dest"
            info "  Installed profile: $bname"
        fi
    done

}

# --- Install seed task types ---
install_seed_task_types() {
    local src="$INSTALL_DIR/seed/task_types.txt"
    local dest="$INSTALL_DIR/aitasks/metadata/task_types.txt"

    if [[ ! -f "$src" ]]; then
        warn "No seed/task_types.txt in tarball — skipping task types installation"
        return
    fi

    if [[ -f "$dest" && "$FORCE" != true ]]; then
        info "  Task types file exists (kept): task_types.txt"
    else
        cp "$src" "$dest"
        info "  Installed task types: task_types.txt"
    fi
}

# --- Install seed review modes ---
install_seed_reviewmodes() {
    if [[ ! -d "$INSTALL_DIR/seed/reviewmodes" ]]; then
        warn "No seed/reviewmodes/ directory in tarball — skipping review mode installation"
        return
    fi

    mkdir -p "$INSTALL_DIR/aitasks/metadata/reviewmodes"

    # Copy review mode files recursively (supports tree structure)
    while IFS= read -r -d '' mode_file; do
        local rel_path="${mode_file#$INSTALL_DIR/seed/reviewmodes/}"
        local dest="$INSTALL_DIR/aitasks/metadata/reviewmodes/$rel_path"
        mkdir -p "$(dirname "$dest")"
        if [[ -f "$dest" && "$FORCE" != true ]]; then
            info "  Review mode exists (kept): $rel_path"
        else
            cp "$mode_file" "$dest"
            info "  Installed review mode: $rel_path"
        fi
    done < <(find "$INSTALL_DIR/seed/reviewmodes" -name "*.md" -type f -print0 2>/dev/null)

    # Copy .reviewmodesignore if present in seed
    local src_ignore="$INSTALL_DIR/seed/reviewmodes/.reviewmodesignore"
    local dest_ignore="$INSTALL_DIR/aitasks/metadata/reviewmodes/.reviewmodesignore"
    if [[ -f "$src_ignore" ]]; then
        if [[ -f "$dest_ignore" && "$FORCE" != true ]]; then
            info "  Filter file exists (kept): .reviewmodesignore"
        else
            cp "$src_ignore" "$dest_ignore"
            info "  Installed filter file: .reviewmodesignore"
        fi
    fi
}

# --- Install seed Claude Code permissions ---
install_seed_claude_settings() {
    local src="$INSTALL_DIR/seed/claude_settings.local.json"
    local dest="$INSTALL_DIR/aitasks/metadata/claude_settings.seed.json"

    if [[ ! -f "$src" ]]; then
        warn "No seed/claude_settings.local.json in tarball — skipping"
        return
    fi

    cp "$src" "$dest"
    info "  Stored Claude Code permissions seed at aitasks/metadata/claude_settings.seed.json"
}

# --- Show changelog between versions (upgrade only) ---
show_upgrade_changelog() {
    local tarball_path="$1"
    local install_dir="$2"

    # Only relevant during upgrade (existing install + --force)
    if [[ "$FORCE" != true ]]; then
        return
    fi

    local current_version=""
    if [[ -f "$install_dir/VERSION" ]]; then
        current_version="$(cat "$install_dir/VERSION")"
    elif [[ -f "$install_dir/aiscripts/VERSION" ]]; then
        current_version="$(cat "$install_dir/aiscripts/VERSION")"
    else
        return  # Can't determine current version, skip
    fi

    # Extract VERSION and CHANGELOG.md from tarball into temp dir
    local tmpextract
    tmpextract="$(mktemp -d)"

    tar -xzf "$tarball_path" -C "$tmpextract" aiscripts/VERSION 2>/dev/null || true
    tar -xzf "$tarball_path" -C "$tmpextract" CHANGELOG.md 2>/dev/null || true

    local new_version=""
    if [[ -f "$tmpextract/aiscripts/VERSION" ]]; then
        new_version="$(cat "$tmpextract/aiscripts/VERSION")"
    fi

    if [[ -z "$new_version" || "$current_version" == "$new_version" ]]; then
        rm -rf "$tmpextract"
        return
    fi

    info "Upgrading: v${current_version} → v${new_version}"

    if [[ -f "$tmpextract/CHANGELOG.md" ]]; then
        echo ""
        info "Changelog:"
        echo ""

        # Print all version sections newer than current_version
        local in_range=false
        while IFS= read -r line; do
            if [[ "$line" =~ ^##\ v ]]; then
                local heading_version
                heading_version="${line#\#\# v}"
                if [[ "$heading_version" == "$current_version" ]]; then
                    break  # Stop before current version's section
                fi
                in_range=true
            fi
            if $in_range; then
                echo "  $line"
            fi
        done < "$tmpextract/CHANGELOG.md"

        echo ""
    else
        warn "No CHANGELOG.md in release (changelog display requires aitasks >= next release)"
    fi

    rm -rf "$tmpextract"

    # Ask for confirmation (only when stdin is a terminal)
    if [[ -t 0 ]]; then
        printf "  Proceed with upgrade? [Y/n] "
        read -r answer
        case "${answer:-Y}" in
            [Yy]*|"") ;;
            *) info "Aborted."; exit 0 ;;
        esac
    fi
}

# --- Set permissions ---
set_permissions() {
    chmod +x "$INSTALL_DIR/ait"
    chmod +x "$INSTALL_DIR"/aiscripts/*.sh
    # Shared libraries in lib/ (sourced, not executed, but keep +x for consistency)
    find "$INSTALL_DIR/aiscripts/lib" -name '*.sh' -exec chmod +x {} + 2>/dev/null || true
}

# --- Main ---
main() {
    echo ""
    info "aitask framework installer"
    echo ""

    check_prerequisites
    check_existing_install
    confirm_install

    # Temp directory with cleanup
    local tmpdir
    tmpdir="$(mktemp -d)"
    # shellcheck disable=SC2064  # Intentional: expand $tmpdir now, not at signal time
    trap "rm -rf '$tmpdir'" EXIT

    local tarball_path="$tmpdir/aitasks.tar.gz"

    download_tarball "$tarball_path"

    # Show changelog and confirm (upgrade path only)
    show_upgrade_changelog "$tarball_path" "$INSTALL_DIR"

    info "Extracting to $INSTALL_DIR..."
    tar -xzf "$tarball_path" -C "$INSTALL_DIR"

    # Remove CHANGELOG.md from project (only in tarball for upgrade changelog display)
    rm -f "$INSTALL_DIR/CHANGELOG.md"
    # Clean up legacy VERSION at root (moved to aiscripts/VERSION in v0.3.0+)
    rm -f "$INSTALL_DIR/VERSION"

    info "Installing Claude Code skills..."
    install_skills

    info "Creating data directories..."
    create_data_dirs

    info "Installing execution profiles..."
    install_seed_profiles

    info "Installing seed task types..."
    install_seed_task_types

    info "Installing review modes..."
    install_seed_reviewmodes

    info "Storing Claude Code permissions seed..."
    install_seed_claude_settings

    # Clean up seed directory after all seed installers have run
    rm -rf "$INSTALL_DIR/seed"

    info "Setting permissions..."
    set_permissions

    echo ""
    echo "=== aitasks installed successfully ==="
    echo ""
    info "Next step: run 'ait setup' to install dependencies and configure Claude Code permissions."
    echo ""
    echo "Quick start:"
    echo "  ait setup      # Install dependencies and configure permissions"
    echo "  ait create     # Create a new task"
    echo "  ait ls -v 15   # List top 15 tasks"
    echo "  ait board      # Open task board"
    echo ""
    echo "Claude Code skills installed to .claude/skills/"
    echo ""
}

main "$@"
