#!/usr/bin/env bash
set -euo pipefail

# aitask_install.sh - Update aitasks to a new version
# Invoked via: ait install [latest|VERSION]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIT_DIR="$SCRIPT_DIR/.."
REPO="beyondeye/aitasks"

# --- Color helpers ---
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[ait]${NC} $1"; }
success() { echo -e "${GREEN}[ait]${NC} $1"; }
warn()    { echo -e "${YELLOW}[ait]${NC} $1"; }
die()     { echo -e "${RED}[ait] Error:${NC} $1" >&2; exit 1; }

# --- Usage ---
show_help() {
    cat <<EOF
Usage: ait install [latest|VERSION]

Update the aitasks framework to a new version.

Arguments:
  latest          Install the latest release (default)
  VERSION         Install a specific version (e.g., 0.2.1)

Options:
  --help          Show this help message

Examples:
  ait install             # Install latest version
  ait install latest      # Install latest version
  ait install 0.2.1       # Install specific version
EOF
    exit 0
}

# --- Resolve target version ---
resolve_version() {
    local requested="${1:-latest}"

    if [[ "$requested" == "latest" ]]; then
        local api_response=""
        api_response="$(curl -sS --max-time 10 \
            "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null)" || true

        if [[ -z "$api_response" ]]; then
            die "Could not reach GitHub API. Check your network connection."
        fi

        local version=""
        version="$(echo "$api_response" \
            | grep '"tag_name"' | head -1 \
            | sed 's/.*"tag_name": *"v\?\([^"]*\)".*/\1/')" || true

        if [[ -z "$version" ]]; then
            die "Could not determine latest version. No releases found at https://github.com/$REPO/releases"
        fi

        echo "$version"
    else
        # Strip leading 'v' if present
        requested="${requested#v}"

        # Validate version format (semver-ish: digits and dots)
        if [[ ! "$requested" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
            die "Invalid version format: $requested (expected: X.Y.Z)"
        fi
        echo "$requested"
    fi
}

# --- Download install.sh for a specific version ---
download_installer() {
    local version="$1"
    local dest="$2"

    local url="https://raw.githubusercontent.com/$REPO/v${version}/install.sh"
    info "Downloading installer for v${version}..."

    if ! curl -fsSL --max-time 30 "$url" -o "$dest" 2>/dev/null; then
        die "Could not download installer for v${version}. Version may not exist.\n  Check available releases: https://github.com/$REPO/releases"
    fi
}

# --- Main ---
main() {
    # Parse arguments
    case "${1:-latest}" in
        --help|-h) show_help ;;
    esac

    info "Checking latest version..."

    local target_version
    target_version="$(resolve_version "${1:-latest}")"

    # Read current version
    local current_version="unknown"
    if [[ -f "$AIT_DIR/aiscripts/VERSION" ]]; then
        current_version="$(cat "$AIT_DIR/aiscripts/VERSION")"
    fi

    # Check if already up to date
    if [[ "$current_version" == "$target_version" ]]; then
        success "Already up to date (v${current_version})"
        exit 0
    fi

    info "Current version: $current_version"
    info "Target version:  $target_version"
    echo ""

    # Download install.sh from the target version's tag
    local tmpdir
    tmpdir="$(mktemp -d)"
    # shellcheck disable=SC2064
    trap "rm -rf '$tmpdir'" EXIT

    download_installer "$target_version" "$tmpdir/install.sh"

    # Run install.sh with --force pointing to the project root
    info "Running installer..."
    echo ""
    bash "$tmpdir/install.sh" --force --dir "$AIT_DIR"

    # Clear the update check cache so the "update available" message disappears
    rm -f "$HOME/.aitask/update_check"
}

main "$@"
